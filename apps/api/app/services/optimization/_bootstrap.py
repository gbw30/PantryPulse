"""Apply OR offline limits before importing the native solver; no application imports."""

import ctypes
import os
import resource
import signal
import sys


def main():
    expected = int(os.environ["PP_OR_PARENT_PID"])
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL) != 0:
        raise OSError(ctypes.get_errno(), "OR child parent-death signal unavailable")
    if os.getppid() != expected:
        os._exit(70)
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:6])
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    bound = 8 * 1024**3 if hard == resource.RLIM_INFINITY else min(hard, 8 * 1024**3)
    resource.setrlimit(resource.RLIMIT_AS, (bound, bound))
    os.execvpe(sys.argv[1], sys.argv[1:], os.environ)


if __name__ == "__main__":
    main()
