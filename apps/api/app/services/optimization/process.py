"""Small offline OR child boundary; no scheduler, persistence or application worker."""

import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

API_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class ProcessResult:
    stdout: bytes
    stderr: bytes
    returncode: int
    reason: str | None
    pgid: int


def live_members(pgid):
    """Observe this Linux group; zombies are dead and cannot execute further work."""
    members = []
    for item in Path("/proc").iterdir():
        if not item.name.isdigit():
            continue
        try:
            stat = (item / "stat").read_text()
            fields = stat[stat.rindex(")") + 2 :].split()
            if int(fields[2]) == pgid and fields[0] != "Z":
                members.append(int(item.name))
        except (OSError, ValueError, IndexError):
            continue
    return members


class _Reader(threading.Thread):
    def __init__(self, stream, limit):
        super().__init__(daemon=True)
        self.stream, self.limit = stream, limit
        self.chunks, self.size, self.overflow = [], 0, False

    def run(self):
        while chunk := self.stream.read1(65536):
            retained = chunk[: max(0, self.limit - self.size)]
            if retained:
                self.chunks.append(retained)
            self.size += len(retained)
            if len(retained) < len(chunk):
                self.overflow = True

    def value(self):
        return b"".join(self.chunks)


def _marker(pid, nonce):
    try:
        return f"PP_OR_BOUNDARY={nonce}".encode() in Path(
            f"/proc/{pid}/environ"
        ).read_bytes().split(b"\0")
    except OSError:
        return False


def run_child(
    argv, data, *, deadline, stop_grace=2.0, kill_margin=0.25, maximum_output=8 * 1024**2
):
    """Stop the owned group before deadline; reap the direct child or fail explicitly.

    Affinity and per-process address-space limits are inherited. This is not a
    kernel aggregate-memory/CPU-quota or application crash-recovery guarantee.
    """
    # OR-DEC-011 [PROVISIONAL]: only offline method containment is OR-owned.
    if sys.platform != "linux" or not hasattr(os, "sched_getaffinity"):
        raise RuntimeError("OFFLINE_PROCESS_CONTAINMENT_UNAVAILABLE")
    if not 0 < kill_margin < stop_grace or maximum_output < 1 or len(data) > 4 * 1024**2:
        raise ValueError("INVALID_OFFLINE_BOUNDARY")
    if deadline <= time.monotonic():
        raise ValueError("OFFLINE_DEADLINE_ALREADY_EXPIRED")
    nonce = str(uuid4())
    environment = {
        key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TZ") if key in os.environ
    }
    environment.update(
        PP_OR_BOUNDARY=nonce, PP_OR_PARENT_PID=str(os.getpid()), PYTHONUNBUFFERED="1"
    )
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        environment[name] = "1"
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("_bootstrap.py")), *argv],
        cwd=API_ROOT,
        env=environment,
        start_new_session=True,
        close_fds=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = _Reader(process.stdout, maximum_output), _Reader(process.stderr, 16384)
    stdout.start()
    stderr.start()

    def feed():
        try:
            process.stdin.write(data)
            process.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass

    feeder = threading.Thread(target=feed, daemon=True)
    feeder.start()

    def send(sig):
        members = live_members(process.pid)
        if not members:
            return
        # An unreaped live leader holds the group identity. After reaping, require
        # an inherited nonce before signaling descendants; never target a reused PID.
        if process.returncode is not None and not any(_marker(pid, nonce) for pid in members):
            raise RuntimeError("OFFLINE_CLEANUP_IDENTITY_UNCONFIRMED")
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass

    reason = None
    try:
        soft_end = deadline - stop_grace
        while True:
            code = process.poll()
            members = live_members(process.pid)
            if code is not None and not members:
                break
            if stdout.overflow or stderr.overflow:
                reason = "OUTPUT_LIMIT"
                break
            if code is not None and members:
                reason = "CHILD_DESCENDANTS_REMAINED"
                break
            if time.monotonic() >= soft_end:
                reason = "DEADLINE_EXCEEDED"
                break
            time.sleep(0.01)
        if reason:
            send(signal.SIGTERM)
            while live_members(process.pid) and time.monotonic() < deadline - kill_margin:
                process.poll()
                time.sleep(0.005)
            if live_members(process.pid):
                send(signal.SIGKILL)
            while live_members(process.pid) and time.monotonic() < deadline:
                time.sleep(0.002)
        if live_members(process.pid):
            raise RuntimeError("OFFLINE_CLEANUP_UNCONFIRMED")
        process.wait(timeout=max(0.001, deadline - time.monotonic()))
        stdout.join(timeout=0.1)
        stderr.join(timeout=0.1)
        if stdout.is_alive() or stderr.is_alive():
            raise RuntimeError("OFFLINE_OUTPUT_DRAIN_UNCONFIRMED")
        if stdout.overflow or stderr.overflow:
            reason = "OUTPUT_LIMIT"
        return ProcessResult(
            stdout.value(), stderr.value(), process.returncode, reason, process.pid
        )
    finally:
        if process.poll() is None or live_members(process.pid):
            send(signal.SIGKILL)
        process.wait(timeout=1)
        feeder.join(timeout=0.1)
        stdout.join(timeout=0.1)
        stderr.join(timeout=0.1)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
