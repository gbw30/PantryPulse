"""Solver-free full candidate replay; exits 0 verified, 3 invalid candidate, 2 bad source."""

import argparse
from pathlib import Path

from app.schemas.or_outputs import Candidate
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.verify import verify
from scripts.or_common import snapshot, write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    try:
        problem = prepare_problem(snapshot(args.snapshot))
    except (ValueError, OSError, TypeError):
        return 2
    try:
        candidate = Candidate.model_validate_json(Path(args.candidate).read_text())
    except (ValueError, OSError, TypeError):
        write(args.report, {"passed": False, "violations": ["INVALID_CANDIDATE_SCHEMA"]})
        return 3
    report = verify(problem, candidate)
    write(args.report, report)
    return 0 if report.passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
