"""OR-DEC-011/018 [PROVISIONAL]: real inherited CPU/address-space and group RSS limits."""

import json
import os
import signal
import sys
import time
from pathlib import Path
from uuid import uuid4

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


def test_actual_cgroup_oom_bounds_aggregate_descendant_memory_without_parent_polling(monkeypatch):
    from app.workers.process_driver import systemd_scope_available

    if not systemd_scope_available():
        pytest.skip("NOT RUN: user systemd cgroup manager inaccessible")
    # Keep a unique parent slice alive outside the bounded workload's scope. The
    # kernel may kill any workload process and systemd may collect that scope;
    # hierarchical kernel counters remain readable from this independent observer.
    slice_name = f"pantrypulse_oom_test_{uuid4().hex}.slice"
    monkeypatch.setenv("PP_WQ_WORKER_SLICE", slice_name)
    driver = PosixProcessDriver(
        cwd=os.getcwd(), memory_limit_bytes=256 * 1024**2, systemd_scope=True
    )
    holder_script = (
        "import pathlib,time;"
        "relative=pathlib.Path('/proc/self/cgroup').read_text().strip().split('::')[1];"
        "print(str(pathlib.Path(relative).parent),flush=True);time.sleep(60)"
    )
    holder = driver.start([sys.executable, "-c", holder_script], b"", max_stdout_bytes=4096)
    workload = None
    try:
        until(lambda: b"\n" in holder.stdout.data())
        relative = holder.stdout.data().decode().strip()
        group = Path("/sys/fs/cgroup") / relative.lstrip("/")
        assert group.name == slice_name

        def oom_kills():
            return int(
                dict(line.split() for line in (group / "memory.events").read_text().splitlines())[
                    "oom_kill"
                ]
            )

        before = oom_kills()
        child = "import time;x=bytearray(176*1024**2);time.sleep(60)"
        script = (
            "import subprocess,sys;"
            "x=bytearray(96*1024**2);"
            f"p=subprocess.Popen([sys.executable,'-c',{child!r}]);p.wait()"
        )
        workload = driver.start([sys.executable, "-c", script], b"", max_stdout_bytes=4096)
        # No RSS backstop or parent termination is invoked. Each process fits its
        # RLIMIT_AS separately; only aggregate scope memory triggers kernel OOM.
        until(lambda: driver.poll(workload) is not None)
        until(lambda: driver.confirm_empty(workload.identity))
        output = driver.collect(workload)
        assert not output.overflow
        assert output.returncode in (0, -signal.SIGTERM, -signal.SIGKILL), output.stderr.decode()
        assert oom_kills() > before, "Require actual kernel OOM kill, not Python MemoryError"
    finally:
        if workload is not None:
            driver.force_stop(workload)
            driver.dispose(workload)
        driver.force_stop(holder)
        driver.dispose(holder)
