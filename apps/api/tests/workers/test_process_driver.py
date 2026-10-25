"""WQ-04 Linux process containment (WQ-T12, T14, T23 transport). Real child processes.

Skips (NOT RUN) on hosts without Linux /proc process control, such as native Windows.
"""

import json
import os
import signal
import subprocess
import sys
import time
import uuid

import pytest

from app.workers.process_driver import (
    BoundaryIdentity,
    PosixProcessDriver,
    current_host_identity,
    linux_containment_available,
)

pytestmark = pytest.mark.skipif(
    not linux_containment_available(), reason="NOT RUN: Linux /proc process control unavailable"
)

API_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def child_argv(contract="test.echo.v1", step="TEST_METHOD"):
    return [
        sys.executable,
        "-m",
        "app.workers.child",
        "--registry",
        "test",
        "--contract",
        contract,
        "--step",
        step,
    ]


def envelope(behavior=None, value=1):
    return json.dumps(
        {
            "input": {"value": value, "behavior": behavior or {}},
            "prior": [],
            "context": {
                "job_id": str(uuid.uuid4()),
                "attempt_id": str(uuid.uuid4()),
                "remaining_s": 30,
                "search_limit_s": 15,
            },
        }
    ).encode()


def wait_exit(driver, handle, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if driver.poll(handle) is not None:
            return
        time.sleep(0.02)
    raise AssertionError("child did not exit")


def wait_members(driver, identity, n, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if len(driver.members(identity)) >= n:
            return
        time.sleep(0.02)
    raise AssertionError(f"expected {n} members, saw {driver.members(identity)}")


@pytest.fixture
def driver():
    return PosixProcessDriver(cwd=API_ROOT)


def test_host_identity_names_boot_and_pid_namespace():
    host = current_host_identity()
    assert host.boot_id and host.pid_namespace


def test_child_runs_in_its_own_group_and_returns_bounded_json(driver):
    handle = driver.start(child_argv(), envelope(value=5), max_stdout_bytes=4096)
    identity = handle.identity
    assert identity.pgid == identity.leader_pid != os.getpgid(0)
    wait_exit(driver, handle)
    out = driver.collect(handle)
    assert not out.overflow
    result = json.loads(out.stdout)
    assert result["status"] == "COMPLETED" and result["output"]["value"] == 5
    assert driver.confirm_empty(identity)


def test_child_environment_carries_no_database_secrets(driver, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret")
    monkeypatch.setenv("PP_TEST_DATABASE_URL", "postgresql://secret")
    # Inspect the executed application, rather than racing systemd/exec's transient
    # empty /proc environ. A launched wrapper alone does not establish child state.
    handle = driver.start(
        [sys.executable, "-c", "import json,os;print(json.dumps(dict(os.environ)))"],
        b"",
        max_stdout_bytes=16384,
    )
    try:
        wait_exit(driver, handle)
        output = driver.collect(handle)
        assert output.returncode == 0, output.stderr.decode()
        environ = json.loads(output.stdout)
        assert not any("DATABASE_URL" in key for key in environ)
        assert not any("secret" in value for value in environ.values())
        assert environ["PP_WQ_BOUNDARY"] == handle.identity.nonce
    finally:
        driver.force_stop(handle)
        driver.dispose(handle)


def test_stop_kills_descendants_in_the_group(driver):  # WQ-T12
    handle = driver.start(
        child_argv(), envelope({"sleep_s": 60, "spawn_descendant": True}), max_stdout_bytes=4096
    )
    wait_members(driver, handle.identity, 2)
    descendants = [p for p in driver.members(handle.identity) if p != handle.identity.leader_pid]
    assert descendants
    assert not driver.confirm_empty(handle.identity)
    driver.request_stop(handle)
    wait_exit(driver, handle)
    end = time.monotonic() + 5
    while not driver.confirm_empty(handle.identity) and time.monotonic() < end:
        driver.force_stop(handle)
        time.sleep(0.05)
    assert driver.confirm_empty(handle.identity)
    for pid in descendants:
        assert not _alive_non_zombie(pid)


def test_force_stop_handles_a_child_ignoring_sigterm(driver):
    handle = driver.start(
        child_argv(), envelope({"sleep_s": 60, "ignore_sigterm": True}), max_stdout_bytes=4096
    )
    wait_members(driver, handle.identity, 1)
    wait_sigterm_ignored(handle.identity.leader_pid)
    driver.request_stop(handle)
    time.sleep(0.3)
    assert driver.poll(handle) is None
    driver.force_stop(handle)
    wait_exit(driver, handle)
    assert driver.confirm_empty(handle.identity)


def test_output_overflow_is_flagged_not_truncated_into_success(driver):  # WQ-T23
    handle = driver.start(child_argv(), envelope({"output_bytes": 50_000}), max_stdout_bytes=1024)
    wait_exit(driver, handle)
    out = driver.collect(handle)
    assert out.overflow
    assert len(out.stdout) <= 1024


def test_unknown_contract_is_rejected_by_the_child(driver):  # WQ-T23
    handle = driver.start(child_argv(contract="os.system"), envelope(), max_stdout_bytes=4096)
    wait_exit(driver, handle)
    result = json.loads(driver.collect(handle).stdout)
    assert result["status"] == "FAILED" and result["error_code"] == "UNREGISTERED_CONTRACT"


def test_orphaned_group_from_a_dead_parent_is_found_and_killed_by_identity(driver):  # WQ-T12/13
    # A separate "supervisor" process starts a child group, prints its identity, then dies.
    script = (
        "import json, os, sys\n"
        "from app.workers.process_driver import PosixProcessDriver\n"
        "d = PosixProcessDriver(cwd=os.getcwd())\n"
        f"argv = {child_argv()!r}\n"
        "env = json.dumps({'input': {'value': 1, 'behavior': {'sleep_s': 120,"
        " 'spawn_descendant': True}}, 'prior': [], 'context': {'job_id': '00000000-0000-4000-8000-"
        "000000000001', 'attempt_id': '00000000-0000-4000-8000-000000000002', 'remaining_s': 1,"
        " 'search_limit_s': 1}}).encode()\n"
        "h = d.start(argv, env, max_stdout_bytes=1024)\n"
        "print(json.dumps(h.identity.to_json()), flush=True)\n"
        "import time; time.sleep(1.0)\n"
        "os._exit(0)\n"
    )
    parent = subprocess.run(
        [sys.executable, "-c", script], cwd=API_ROOT, capture_output=True, text=True, timeout=30
    )
    identity = BoundaryIdentity.from_json(json.loads(parent.stdout.strip().splitlines()[-1]))
    # PDEATHSIG kills the leader; the grandchild may survive in the orphaned group.
    evidence = driver.cleanup_foreign(identity, timeout_s=5)
    assert evidence is not None
    assert evidence["method"] in ("PROCESS_GROUP_SCAN", "PROCESS_GROUP_KILLED")
    assert driver.confirm_empty(identity)


def test_foreign_cleanup_refuses_another_namespace_or_boot(driver):  # WQ-T14
    host = current_host_identity()
    other_ns = BoundaryIdentity(
        boot_id=host.boot_id,
        pid_namespace="pid:[1]",
        pgid=os.getpid(),
        leader_pid=os.getpid(),
        leader_start_ticks=1,
        nonce=str(uuid.uuid4()),
    )
    assert driver.cleanup_foreign(other_ns, timeout_s=1) is None
    rebooted = BoundaryIdentity(
        boot_id="00000000-0000-0000-0000-000000000000",
        pid_namespace=host.pid_namespace,
        pgid=os.getpid(),
        leader_pid=os.getpid(),
        leader_start_ticks=1,
        nonce=str(uuid.uuid4()),
    )
    evidence = driver.cleanup_foreign(rebooted, timeout_s=1)
    assert evidence == {"method": "HOST_REBOOTED", "recorded_boot_id": rebooted.boot_id}
    assert os.getpid() > 0  # this test process was not signalled


def test_foreign_cleanup_never_kills_an_unrelated_group(driver):  # WQ-T14
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    try:
        time.sleep(0.2)
        host = current_host_identity()
        forged = BoundaryIdentity(
            boot_id=host.boot_id,
            pid_namespace=host.pid_namespace,
            pgid=unrelated.pid,
            leader_pid=unrelated.pid,
            leader_start_ticks=driver.start_ticks(unrelated.pid),
            nonce=str(uuid.uuid4()),  # not the marker in its environment
        )
        assert driver.cleanup_foreign(forged, timeout_s=1) is None
        assert unrelated.poll() is None
        reused = BoundaryIdentity(
            boot_id=host.boot_id,
            pid_namespace=host.pid_namespace,
            pgid=unrelated.pid,
            leader_pid=unrelated.pid,
            leader_start_ticks=driver.start_ticks(unrelated.pid) - 1,
            nonce=str(uuid.uuid4()),
        )
        # Leader PID alive with a different start time: the recorded group is gone.
        assert driver.cleanup_foreign(reused, timeout_s=1) == {
            "method": "LEADER_PID_REUSED",
            "pgid": unrelated.pid,
        }
        assert unrelated.poll() is None
    finally:
        unrelated.send_signal(signal.SIGKILL)
        unrelated.wait()


def wait_sigterm_ignored(pid, timeout=15):
    """Readiness from the kernel: SIGTERM's bit is set in the leader's SigIgn mask."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        with open(f"/proc/{pid}/status") as f:
            mask = next(line for line in f if line.startswith("SigIgn:")).split()[1]
        if int(mask, 16) & (1 << (signal.SIGTERM - 1)):
            return
        time.sleep(0.02)
    raise AssertionError("child never ignored SIGTERM")


def _alive_non_zombie(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            stat = f.read()
    except FileNotFoundError:
        return False
    return stat[stat.rindex(")") + 2] != "Z"
