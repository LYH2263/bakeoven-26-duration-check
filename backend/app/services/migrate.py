"""Apply idempotent SQL migrations from backend/migrations to the database.

Runs at app startup (after ``Base.metadata.create_all``) and can also be
executed manually against an existing database:

    python -m app.services.migrate

Each ``*.sql`` file is executed in filename order inside its own
transaction. Migration files must be re-runnable (e.g. guard with
``IF NOT EXISTS`` on pg_constraint) because they run on every startup.
"""

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def run_migrations(engine: Engine) -> list[str]:
    """Execute every migrations/*.sql file in order; return applied filenames."""
    applied: list[str] = []
    if not MIGRATIONS_DIR.is_dir():
        return applied
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        with engine.begin() as conn:
            conn.execute(text(path.read_text(encoding="utf-8")))
        applied.append(path.name)
    return applied


if __name__ == "__main__":
    from app.database import engine

    print("applied migrations:", ", ".join(run_migrations(engine)) or "none")
