"""
Create the TalentMatch AI tables in Supabase.

Usage (from the backend/ folder):
    python -m app.create_tables          # create missing tables and enable RLS
    python -m app.create_tables --sql    # only print the CREATE TABLE SQL, change nothing

Safe to run repeatedly: existing tables and their data are never dropped.
The API also runs this automatically on startup.
"""
import sys

from sqlalchemy.schema import CreateIndex, CreateTable

from app.database import Base, check_database_connection, engine, init_db


def print_schema_sql() -> None:
    from sqlalchemy.dialects import postgresql

    from app import models  # noqa: F401

    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        print(f"{str(CreateTable(table).compile(dialect=dialect)).strip()};\n")
        for index in sorted(table.indexes, key=lambda i: i.name):
            print(f"{str(CreateIndex(index).compile(dialect=dialect)).strip()};")
        print(f'ALTER TABLE "{table.name}" ENABLE ROW LEVEL SECURITY;\n')


def main() -> int:
    if "--sql" in sys.argv:
        print_schema_sql()
        return 0

    connected, message = check_database_connection()
    print(message)
    if not connected:
        return 1

    tables = init_db()
    from sqlalchemy import inspect

    existing = set(inspect(engine).get_table_names())
    for table in tables:
        print(f"  [{'ok' if table in existing else 'MISSING'}] {table}")
    return 0 if all(t in existing for t in tables) else 1


if __name__ == "__main__":
    sys.exit(main())
