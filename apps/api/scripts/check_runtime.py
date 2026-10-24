"""Dependency smoke check, not an allocation correctness test."""

import argparse
import os

import alembic
import ortools
import psycopg
import sqlalchemy
from ortools.sat.python import cp_model

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--database", action="store_true", help="Read-only configured DB connection check"
)
args = parser.parse_args()

model = cp_model.CpModel()
value = model.new_int_var(0, 1, "smoke_value")
model.maximize(value)
solver = cp_model.CpSolver()
solver.parameters.num_search_workers = 1
status = solver.solve(model)
assert status == cp_model.OPTIMAL and solver.value(value) == 1
print(f"OR-Tools {ortools.__version__}: native CP-SAT smoke OPTIMAL")
print(
    f"SQLAlchemy {sqlalchemy.__version__}, Alembic {alembic.__version__}, "
    f"psycopg {psycopg.__version__}"
)

if args.database:
    engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as connection:
        database = connection.scalar(sqlalchemy.text("SELECT current_database()"))
        print(f"Database connection: {database}")
    engine.dispose()
