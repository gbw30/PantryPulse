"""Export public contracts without DB connection, inference, solve or network access."""

import argparse

from app.main import app
from scripts.or_common import write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    write(args.output, app.openapi())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
