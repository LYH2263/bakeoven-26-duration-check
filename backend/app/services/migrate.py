"""Apply idempotent SQL migrations from backend/migrations at startup."""

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def apply_migrations(engine: Engine) -> list[str]:
    """Run every migrations/*.sql in filename order; return applied file names.

    Migrations are written to be idempotent, so re-running them on an
    existing database is a no-op. Only PostgreSQL is supported; other
    dialects (e.g. SQLite in tests) get their schema — constraints
    included — from ``Base.metadata.create_all`` instead.
    """
    if engine.dialect.name != "postgresql" or not MIGRATIONS_DIR.is_dir():
        return []
    applied: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        with engine.begin() as conn:
            conn.execute(text(path.read_text(encoding="utf-8")))
        applied.append(path.name)
    return applied
