"""Linux process-group execution boundary (WQ-04, ADR 0005 A2).

Each step child runs in its own session/process group, carries a per-boundary nonce in its
environment and asks the kernel to SIGKILL it if its parent dies. Stop = SIGTERM to the
group, SIGKILL after the grace, then a /proc scan must show no live member. Identity is
boot id + PID namespace + pgid + leader pid + leader start ticks + nonce; a bare PID, a
process name or a broad match is never used to signal anything.

Limitation: a descendant that leaves the process group (setsid) is outside this boundary.
Registered handlers must not do that. Native Windows has no driver: ``capable`` is False.
"""

import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_PROC = Path("/proc")
_ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR", "VIRTUAL_ENV")
_THREAD_VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
BOUNDARY_ENV = "PP_WQ_BOUNDARY"
PARENT_ENV = "PP_WQ_PARENT_PID"


def linux_containment_available() -> bool:
    return (
        sys.platform.startswith("linux")
        and hasattr(os, "killpg")
        and (_PROC / "self" / "stat").exists()
        and (_PROC / "self" / "ns" / "pid").exists()
        and Path("/proc/sys/kernel/random/boot_id").exists()
    )


@dataclass(frozen=True, slots=True)
class HostIdentity:
    boot_id: str
    pid_namespace: str

    def as_text(self) -> str:
        return f"boot={self.boot_id};pidns={self.pid_namespace}"


def current_host_identity() -> HostIdentity | None:
    if not linux_containment_available():
        return None
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    pidns = os.readlink("/proc/self/ns/pid")
    return HostIdentity(boot_id=boot, pid_namespace=pidns)


@dataclass(frozen=True, slots=True)
class ProcStat:
    pid: int
    state: str
    ppid: int
    pgrp: int
    start_ticks: int


def read_stat(pid: int) -> ProcStat | None:
    try:
        raw = (_PROC / str(pid) / "stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    # comm (field 2) may contain spaces and parentheses; fields resume after the last ')'.
    rest = raw[raw.rindex(")") + 2 :].split()
    return ProcStat(
        pid=pid,
        state=rest[0],
        ppid=int(rest[1]),
        pgrp=int(rest[2]),
        start_ticks=int(rest[19]),
    )


@dataclass(frozen=True, slots=True)
class BoundaryIdentity:
    boot_id: str
    pid_namespace: str
    pgid: int
    leader_pid: int
    leader_start_ticks: int
    nonce: str

    def to_json(self) -> dict[str, Any]:
        return {"kind": "linux_process_group", **asdict(self)}

    @classmethod
    def from_json(cls, data: Any) -> "BoundaryIdentity":
        if not isinstance(data, dict) or data.get("kind") != "linux_process_group":
            raise ValueError("unrecognized execution boundary identity")
        return cls(
            boot_id=str(data["boot_id"]),
            pid_namespace=str(data["pid_namespace"]),
            pgid=int(data["pgid"]),
            leader_pid=int(data["leader_pid"]),
            leader_start_ticks=int(data["leader_start_ticks"]),
            nonce=str(data["nonce"]),
        )


@dataclass(frozen=True, slots=True)
class ChildOutput:
    stdout: bytes
    stderr: bytes
    overflow: bool
    returncode: int | None


class _BoundedReader(threading.Thread):
    def __init__(self, stream: Any, limit: int):
        super().__init__(daemon=True)
        self.stream = stream
        self.limit = limit
        self.chunks: list[bytes] = []
        self.size = 0
        self.overflow = False

    def run(self) -> None:
        try:
            while True:
                chunk = self.stream.read1(65536) if hasattr(self.stream, "read1") else b""
                if not chunk:
                    return
                if self.size + len(chunk) > self.limit:
                    keep = max(0, self.limit - self.size)
                    self.chunks.append(chunk[:keep])
                    self.size += keep
                    self.overflow = True
                    continue  # keep draining so the child never blocks; discard the rest
                self.chunks.append(chunk)
                self.size += len(chunk)
        except (OSError, ValueError):
            return

    def data(self) -> bytes:
        return b"".join(self.chunks)


@dataclass(slots=True)
class ChildHandle:
    process: subprocess.Popen
    identity: BoundaryIdentity
    stdout: _BoundedReader
    stderr: _BoundedReader
    started_monotonic: float
    term_sent_at: float | None = None
    kill_sent_at: float | None = None


class PosixProcessDriver:
    def __init__(self, *, cwd: str | os.PathLike[str], thread_limit: int = 6):
        self.cwd = str(cwd)
        self.thread_limit = int(thread_limit)
        self.capable = linux_containment_available()
        # The deadline watchdog and main loop share handles. Keep the unreaped-leader
        # identity check atomic with signaling so another thread cannot reap it mid-check.
        self._process_lock = threading.RLock()

    # --- identity --------------------------------------------------------------------------

    @staticmethod
    def host_identity_text() -> str:
        host = current_host_identity()
        return host.as_text() if host else "unavailable"

    @staticmethod
    def start_ticks(pid: int) -> int:
        stat = read_stat(pid)
        if stat is None:
            raise ProcessLookupError(pid)
        return stat.start_ticks

    def members(self, identity: BoundaryIdentity) -> list[int]:
        """Live (non-zombie) processes in the recorded group, in this PID namespace."""
        found = []
        for entry in _PROC.iterdir():
            if not entry.name.isdigit():
                continue
            stat = read_stat(int(entry.name))
            if stat is not None and stat.pgrp == identity.pgid and stat.state != "Z":
                found.append(stat.pid)
        return sorted(found)

    @staticmethod
    def _has_marker(pid: int, nonce: str) -> bool:
        try:
            environ = (_PROC / str(pid) / "environ").read_bytes()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            return False
        return f"{BOUNDARY_ENV}={nonce}".encode() in environ.split(b"\0")

    def _same_host(self, identity: BoundaryIdentity) -> bool:
        host = current_host_identity()
        return (
            host is not None
            and host.boot_id == identity.boot_id
            and host.pid_namespace == identity.pid_namespace
        )

    def confirm_empty(self, identity: BoundaryIdentity) -> bool:
        try:
            return self._same_host(identity) and not self.members(identity)
        except OSError:
            return False  # unreadable /proc is not evidence of an empty boundary

    # --- lifecycle -------------------------------------------------------------------------

    def _child_env(self, nonce: str) -> dict[str, str]:
        env = {k: os.environ[k] for k in _ENV_ALLOWLIST if k in os.environ}
        for var in _THREAD_VARS:
            env[var] = str(self.thread_limit)
        env["PYTHONUNBUFFERED"] = "1"
        env[BOUNDARY_ENV] = nonce
        env[PARENT_ENV] = str(os.getpid())
        return env

    def start(
        self,
        argv: list[str],
        stdin_bytes: bytes,
        *,
        max_stdout_bytes: int,
        max_stderr_bytes: int = 16_384,
    ) -> ChildHandle:
        if not self.capable:
            raise RuntimeError("process containment is unavailable on this host")
        host = current_host_identity()
        nonce = str(uuid.uuid4())
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
            env=self._child_env(nonce),
            start_new_session=True,
            close_fds=True,
        )
        try:
            stat = read_stat(process.pid)
        except PermissionError:
            stat = None  # retain the live handle; recovery must establish its own evidence
        identity = BoundaryIdentity(
            boot_id=host.boot_id,
            pid_namespace=host.pid_namespace,
            pgid=process.pid,
            leader_pid=process.pid,
            leader_start_ticks=stat.start_ticks if stat else -1,
            nonce=nonce,
        )
        stdout = _BoundedReader(process.stdout, max_stdout_bytes)
        stderr = _BoundedReader(process.stderr, max_stderr_bytes)
        stdout.start()
        stderr.start()

        def feed() -> None:
            try:
                process.stdin.write(stdin_bytes)
                process.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass

        threading.Thread(target=feed, daemon=True).start()
        return ChildHandle(process, identity, stdout, stderr, time.monotonic())

    def poll(self, handle: ChildHandle) -> int | None:
        """Nonblocking; reaps the leader when it has exited."""
        with self._process_lock:
            return handle.process.poll()

    def _signal_group(self, handle: ChildHandle, sig: int) -> None:
        with self._process_lock:
            self._signal_group_locked(handle, sig)

    def _signal_group_locked(self, handle: ChildHandle, sig: int) -> None:
        identity = handle.identity
        if handle.process.returncode is None:
            # Unreaped leader (alive or zombie) still holds the pgid: it is ours.
            targets_ok = True
        else:
            try:
                live = self.members(identity)
            except OSError:
                return
            if not live:
                return
            targets_ok = all(self._has_marker(pid, identity.nonce) for pid in live)
        if not targets_ok:
            return
        try:
            os.killpg(identity.pgid, sig)
        except ProcessLookupError:
            pass

    def request_stop(self, handle: ChildHandle) -> None:
        handle.term_sent_at = handle.term_sent_at or time.monotonic()
        self._signal_group(handle, signal.SIGTERM)

    def force_stop(self, handle: ChildHandle) -> None:
        handle.kill_sent_at = handle.kill_sent_at or time.monotonic()
        self._signal_group(handle, signal.SIGKILL)

    def collect(self, handle: ChildHandle, timeout_s: float = 2.0) -> ChildOutput:
        handle.stdout.join(timeout_s)
        handle.stderr.join(timeout_s)
        return ChildOutput(
            stdout=handle.stdout.data(),
            stderr=handle.stderr.data(),
            overflow=handle.stdout.overflow,
            returncode=handle.process.returncode,
        )

    def dispose(self, handle: ChildHandle) -> None:
        """Release per-attempt transport; never reuse pipes after a forced stop."""
        for stream in (handle.process.stdin, handle.process.stdout, handle.process.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass

    # --- recovery of a boundary started by another (lost) supervisor ------------------------

    def cleanup_foreign(self, identity: BoundaryIdentity, *, timeout_s: float) -> dict | None:
        """Return concrete containment evidence, or None when it cannot be established."""
        try:
            return self._cleanup_foreign(identity, timeout_s=timeout_s)
        except OSError:
            return None

    def _cleanup_foreign(self, identity: BoundaryIdentity, *, timeout_s: float) -> dict | None:
        host = current_host_identity()
        if host is None:
            return None
        if host.boot_id != identity.boot_id:
            return {"method": "HOST_REBOOTED", "recorded_boot_id": identity.boot_id}
        if host.pid_namespace != identity.pid_namespace:
            return None
        leader = read_stat(identity.leader_pid)
        if (
            leader is not None
            and identity.leader_start_ticks >= 0
            and leader.start_ticks != identity.leader_start_ticks
        ):
            # The PID was reused, which the kernel allows only after the group emptied.
            return {"method": "LEADER_PID_REUSED", "pgid": identity.pgid}
        live = self.members(identity)
        if not live:
            return {"method": "PROCESS_GROUP_SCAN", "pgid": identity.pgid, "killed": 0}
        if not all(self._has_marker(pid, identity.nonce) for pid in live):
            return None
        try:
            os.killpg(identity.pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            if not self.members(identity):
                return {
                    "method": "PROCESS_GROUP_KILLED",
                    "pgid": identity.pgid,
                    "killed": len(live),
                }
            time.sleep(0.02)
        return None
