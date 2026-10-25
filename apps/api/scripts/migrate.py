"""Run Alembic with an explicit direct URL; never print credentials or auto-run on startup."""

import argparse
import os
import re
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("upgrade", "downgrade", "current"))
    parser.add_argument("revision", nargs="?")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--schema", default="public")
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL_UNPOOLED")
    if args.env_file:
        values = []
        for line in args.env_file.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"^\s*DATABASE_URL_UNPOOLED\s*=\s*(.*)$", line)
            if match:
                values.append(match[1].strip().strip('"').strip("'"))
        if len(values) != 1:
            parser.error("env file must contain exactly one active DATABASE_URL_UNPOOLED")
        url = values[0]
    if not url or "-pooler" in (make_url(url).host or ""):
        parser.error("an explicit non-pooled DATABASE_URL_UNPOOLED is required")
    if args.operation != "current" and args.revision is None:
        parser.error("upgrade/downgrade require an explicit revision")
    from app.database import database_engine

    config = Config(str(API_ROOT / "alembic.ini"))
    config.attributes["schema"] = args.schema
    engine = database_engine(url)
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            if args.operation == "current":
                command.current(config)
            else:
                getattr(command, args.operation)(config, args.revision)
        print("Migration command completed.")
    except Exception as error:
        # Do not print connection strings, bound values or potentially secret SQL errors.
        print(f"Migration failed ({type(error).__name__}); transaction rolled back.",
              file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
