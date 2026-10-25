"""Linux child limits applied before any handler import, inherited by descendants.

OR-DEC-011/018 [PROVISIONAL]: affinity bounds CPU parallelism; RLIMIT_AS bounds each
process. The parent additionally observes aggregate process-group RSS and terminates
on excess. RSS polling is not a kernel-enforced aggregate memory ceiling.
"""

import argparse
import ctypes
import os
import resource
import signal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu-count", required=True, type=int)
    parser.add_argument("--memory-bytes", required=True, type=int)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or args.cpu_count < 1 or args.memory_bytes < 1:
        parser.error("positive limits and command required")
    expected = int(os.environ["PP_WQ_PARENT_PID"])
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL) != 0:
        raise OSError(ctypes.get_errno(), "parent death signal unavailable")
    if os.getppid() != expected:
        os._exit(70)
    allowed = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, allowed[: args.cpu_count])
    _, inherited_hard = resource.getrlimit(resource.RLIMIT_AS)
    memory = args.memory_bytes
    if inherited_hard != resource.RLIM_INFINITY:
        memory = min(memory, inherited_hard)
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    os.execvpe(command[0], command, os.environ)


if __name__ == "__main__":
    main()
