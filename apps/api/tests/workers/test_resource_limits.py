"""OR-DEC-011/018 [PROVISIONAL]: real inherited CPU/address-space and group RSS limits."""

import json
import os
import sys
import time

import pytest

from app.workers.process_driver import PosixProcessDriver, linux_containment_available

pytestmark = pytest.mark.skipif(
    not linux_containment_available(),
    reason="Linux resource controls unavailable",
)


def until(predicate, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("resource-control condition not reached")


def test_cpu_affinity_and_address_space_limit_are_actual_and_inherited():
    driver = PosixProcessDriver(cwd=os.getcwd(), thread_limit=2, memory_limit_bytes=256 * 1024**2)
    script = (
        "import json,os,resource,subprocess,sys; "
        "child=subprocess.check_output([sys.executable,'-c',"
        "'import os;print(len(os.sched_getaffinity(0)))']); "
        "print(json.dumps({'cpus':len(os.sched_getaffinity(0)),"
        "'child_cpus':int(child),'memory':resource.getrlimit(resource.RLIMIT_AS)[0]}))"
    )
    handle = driver.start([sys.executable, "-c", script], b"", max_stdout_bytes=4096)
    try:
        until(lambda: driver.poll(handle) is not None)
        out = driver.collect(handle)
        assert out.returncode == 0, out.stderr.decode()
        result = json.loads(out.stdout)
        assert 1 <= result["cpus"] <= 2
        assert result["child_cpus"] == result["cpus"]
        assert result["memory"] == 256 * 1024**2
    finally:
        driver.force_stop(handle)
        driver.dispose(handle)


def test_kernel_rejects_memory_allocation_above_per_process_bound():
    driver = PosixProcessDriver(cwd=os.getcwd(), memory_limit_bytes=64 * 1024**2)
    script = "try:\n x=bytearray(128*1024**2)\nexcept MemoryError:\n print('KERNEL_LIMIT_ENFORCED')"
    handle = driver.start([sys.executable, "-c", script], b"", max_stdout_bytes=4096)
    try:
        until(lambda: driver.poll(handle) is not None)
        out = driver.collect(handle)
        assert out.returncode == 0, out.stderr.decode()
        assert b"KERNEL_LIMIT_ENFORCED" in out.stdout
    finally:
        driver.force_stop(handle)
        driver.dispose(handle)


def test_aggregate_descendant_rss_limit_stops_and_reaps_entire_boundary():
    driver = PosixProcessDriver(
        cwd=os.getcwd(), memory_limit_bytes=256 * 1024**2, systemd_scope=False
    )
    script = (
        "import subprocess,sys,time; "
        "p=subprocess.Popen([sys.executable,'-c',"
        "'import time;x=bytearray(140*1024**2);time.sleep(60)']); "
        "x=bytearray(140*1024**2);time.sleep(60)"
    )
    handle = driver.start([sys.executable, "-c", script], b"", max_stdout_bytes=4096)
    try:
        until(lambda: driver.limits_exceeded(handle))
        assert handle.peak_rss_bytes > driver.memory_limit_bytes
        assert len(driver.members(handle.identity)) >= 2
        driver.force_stop(handle)
        until(lambda: driver.poll(handle) is not None)
        until(lambda: driver.confirm_empty(handle.identity))
        assert driver.effective_limits()["aggregate_memory_hard_kernel_ceiling"] is False
    finally:
        driver.force_stop(handle)
        driver.dispose(handle)


def test_actual_cgroup_cpu_and_memory_limits_cover_descendants():
    from app.workers.process_driver import systemd_scope_available

    if not systemd_scope_available():
        pytest.skip("NOT RUN: user systemd cgroup manager inaccessible")
    driver = PosixProcessDriver(
        cwd=os.getcwd(),
        thread_limit=2,
        memory_limit_bytes=96 * 1024**2,
        systemd_scope=True,
    )
    script = (
        "import json,pathlib,os; "
        "group=pathlib.Path('/sys/fs/cgroup'+pathlib.Path('/proc/self/cgroup').read_text()"
        ".strip().split('::')[1]); "
        "print(json.dumps({'memory':int((group/'memory.max').read_text()),"
        "'swap':int((group/'memory.swap.max').read_text()),"
        "'cpu':(group/'cpu.max').read_text().split(),"
        "'affinity':len(os.sched_getaffinity(0)),"
        "'oom_group':int((group/'memory.oom.group').read_text())}))"
    )
    handle = driver.start([sys.executable, "-c", script], b"", max_stdout_bytes=4096)
    try:
        until(lambda: driver.poll(handle) is not None)
        out = driver.collect(handle)
        assert out.returncode == 0, out.stderr.decode()
        actual = json.loads(out.stdout)
        assert actual["memory"] == 96 * 1024**2
        assert actual["swap"] == 0
        quota, period = map(int, actual["cpu"])
        assert quota / period == 2
        assert actual["affinity"] <= 2
        assert driver.effective_limits()["aggregate_memory_hard_kernel_ceiling"] is True
    finally:
        driver.force_stop(handle)
        driver.dispose(handle)


def test_actual_cgroup_oom_bounds_aggregate_descendant_memory_without_parent_polling():
    from app.workers.process_driver import systemd_scope_available

    if not systemd_scope_available():
        pytest.skip("NOT RUN: user systemd cgroup manager inaccessible")
    driver = PosixProcessDriver(
        cwd=os.getcwd(),
        memory_limit_bytes=256 * 1024**2,
        systemd_scope=True,
    )
    child = (
        "import pathlib,time;"
        "pathlib.Path('/proc/self/oom_score_adj').write_text('1000');"
        "x=bytearray(176*1024**2);time.sleep(60)"
    )
    script = f"""
import json, pathlib, signal, subprocess, sys
relative = pathlib.Path('/proc/self/cgroup').read_text().strip().split('::')[1]
group = pathlib.Path('/sys/fs/cgroup') / relative.lstrip('/')
def report(signaled=False, child_exit=None):
    print(json.dumps({{'signaled': signaled, 'child_exit': child_exit,
                      'events': (group / 'memory.events').read_text()}}), flush=True)
def stopped(signum, frame):
    report(signaled=True)
    sys.exit(0)
signal.signal(signal.SIGTERM, stopped)
p = subprocess.Popen([sys.executable, '-c', {child!r}])
x = bytearray(96 * 1024**2)
report(child_exit=p.wait())
"""
    handle = driver.start([sys.executable, "-c", script], b"", max_stdout_bytes=4096)
    try:
        # Each allocation fits RLIMIT_AS separately. systemd may stop the whole scope
        # after the child OOM; its SIGTERM handler records the kernel counter first.
        until(lambda: driver.poll(handle) is not None)
        until(lambda: driver.confirm_empty(handle.identity))
        output = driver.collect(handle)
        assert output.returncode == 0, output.stderr.decode()
        result = json.loads(output.stdout)
        assert result["signaled"] or result["child_exit"] == -9
        counters = dict(line.split() for line in result["events"].splitlines())
        assert int(counters["oom_kill"]) >= 1
    finally:
        driver.force_stop(handle)
        driver.dispose(handle)
