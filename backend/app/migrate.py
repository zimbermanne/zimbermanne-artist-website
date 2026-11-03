"""Tiny additive migration: `create_all` never alters existing tables, so new columns are added here."""
from sqlalchemy import inspect, text

from .database import Base


def _sql_type(col) -> str:
    t = col.type.__class__.__name__
    if t == "Integer":
        return "INTEGER DEFAULT 0"
    if t == "Boolean":
        return "BOOLEAN DEFAULT FALSE"
    length = getattr(col.type, "length", None)
    return f"VARCHAR({length}) DEFAULT ''" if length else "TEXT"


def add_missing_columns(engine) -> list[str]:
    added = []
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have:
                    conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {_sql_type(col)}'))
                    added.append(f"{table.name}.{col.name}")
    return added
