"""Run the shared PostgreSQL compute supervisor with real registered OR handlers."""

from app.workers.supervisor import main

if __name__ == "__main__":
    raise SystemExit(main())
