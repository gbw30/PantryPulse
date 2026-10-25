"""Real OR-only child execution: no database, scheduler or shared workers."""

import json
import os
import sys
import time

import pytest

from app.services.optimization.process import live_members, run_child

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux OR offline containment")


def execute(script, *, wall=2, cap=4096):
    return run_child(
        [sys.executable, "-c", script],
        b"",
        deadline=time.monotonic() + wall,
        stop_grace=0.2,
        kill_margin=0.1,
        maximum_output=cap,
    )


def test_executed_or_child_has_no_application_credentials(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test-secret")
    monkeypatch.setenv("PP_TEST_DATABASE_URL", "postgresql://test-secret")
    monkeypatch.setenv("PP_PRESENTER_PASSWORD_HASH", "test-secret")
    result = execute("import json,os;print(json.dumps(dict(os.environ)))")
    assert result.returncode == 0 and result.reason is None
    values = json.loads(result.stdout)
    assert not any("test-secret" in value for value in values.values())
    assert not any("DATABASE" in key or "PRESENTER" in key for key in values)
    assert values["PP_OR_BOUNDARY"]


def test_or_child_inherits_actual_cpu_and_address_space_limits():
    script = (
        "import json,os,resource;print(json.dumps([len(os.sched_getaffinity(0)),"
        "resource.getrlimit(resource.RLIMIT_AS)[0]]))"
    )
    result = execute(script)
    assert result.reason is None
    cpus, memory = json.loads(result.stdout)
    assert 1 <= cpus <= 6
    assert 0 < memory <= 8 * 1024**3


def test_hung_boundary_stops_descendant_and_reaps_direct_child(tmp_path):
    # OR-DEC-011 [PROVISIONAL]: real offline child termination, not durable job evidence.
    pidfile = tmp_path / "descendant.pid"
    child = "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"
    script = (
        "import pathlib,signal,subprocess,sys,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        f"p=subprocess.Popen([sys.executable,'-c',{child!r}]);"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(p.pid));time.sleep(60)"
    )
    started = time.monotonic()
    result = execute(script, wall=1)
    assert result.reason == "DEADLINE_EXCEEDED"
    assert time.monotonic() - started < 2
    assert pidfile.exists()
    assert live_members(result.pgid) == []
    with pytest.raises(ChildProcessError):
        os.waitpid(result.pgid, os.WNOHANG)


def test_output_overflow_cannot_return_success():
    result = execute(
        "import sys,time;sys.stdout.write('x'*100000);sys.stdout.flush();time.sleep(60)"
    )
    assert result.reason == "OUTPUT_LIMIT"
    assert len(result.stdout) <= 4096
    assert live_members(result.pgid) == []


def test_leader_exit_cannot_leave_a_live_descendant():
    result = execute(
        "import subprocess,sys;subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])"
    )
    assert result.reason == "CHILD_DESCENDANTS_REMAINED"
    assert live_members(result.pgid) == []
