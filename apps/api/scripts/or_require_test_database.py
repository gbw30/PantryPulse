"""A full integration gate must not silently pass when all PostgreSQL tests skip."""
import os

from sqlalchemy.engine import make_url


def main():
    value = os.environ.get("PP_TEST_DATABASE_URL", "")
    try:
        url = make_url(value)
        valid = url.drivername.startswith("postgresql") and url.database.endswith("_test")
    except (ValueError, AttributeError):
        valid = False
    if not valid:
        print("Set PP_TEST_DATABASE_URL to a dedicated PostgreSQL database ending in _test")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
