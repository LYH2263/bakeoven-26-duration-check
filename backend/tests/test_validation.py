"""Validation rules for products/batches: API rejection, direct-DB-insert
failure, boundary values, and seed/gantt stability.

Backed by SQLite (CHECK constraints are enforced there too); the API is
exercised through FastAPI's TestClient with get_db overridden, so no
Postgres is needed. TestClient is used without its context manager so the
lifespan (which targets the real database) does not run.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint, create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Batch, ConflictLog, Oven, Product
from app.services.migrate import apply_migrations
from app.services.seed import seed_if_empty

engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestSession()
    seed_if_empty(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    return TestClient(app)


def _count(model) -> int:
    # Fresh connection per call so we never read through a stale transaction.
    with engine.connect() as conn:
        return conn.scalar(select(func.count()).select_from(model))


# --- seed data still boots and gantt blocks are unchanged -------------------


def test_seed_counts_and_gantt_blocks_unchanged(client):
    assert _count(Product) == 3
    assert _count(Batch) == 3
    blocks = client.get("/api/gantt").json()
    got = [(b["code"], b["phase"], b["start_min"], b["end_min"]) for b in blocks]
    assert got == [
        ("BO-0900", "ferment", 540, 580),
        ("BO-0900", "bake", 580, 615),
        ("BO-1000", "ferment", 600, 600),
        ("BO-1000", "bake", 600, 630),
        ("BO-1030", "ferment", 630, 655),
        ("BO-1030", "bake", 655, 675),
    ]


# --- writes via the API are rejected with the field name --------------------


def test_api_rejects_negative_ferment(client):
    r = client.post("/api/products", json={"name": "坏配方", "ferment_min": -1, "bake_min": 30})
    assert r.status_code == 400
    assert "ferment_min" in r.json()["detail"]
    assert _count(Product) == 3


def test_api_rejects_zero_bake(client):
    r = client.post("/api/products", json={"name": "零烘烤", "ferment_min": 10, "bake_min": 0})
    assert r.status_code == 400
    assert "bake_min" in r.json()["detail"]
    assert _count(Product) == 3


def test_api_rejects_negative_start(client):
    r = client.post("/api/batches", json={"product_id": 1, "oven_id": 3, "start_min": -1})
    assert r.status_code == 400
    assert "start_min" in r.json()["detail"]
    assert _count(Batch) == 3


def test_api_rejects_full_day_start(client):
    r = client.post("/api/batches", json={"product_id": 1, "oven_id": 3, "start_min": 24 * 60})
    assert r.status_code == 400
    assert "start_min" in r.json()["detail"]
    assert _count(Batch) == 3


def test_validation_runs_before_overlap_check(client):
    # A long recipe occupying [0, 1200) on the empty oven 3: an invalid
    # negative start would overlap it, so a 400 (not 409) proves validation
    # ran before the overlap check.
    r = client.post("/api/products", json={"name": "长时面包", "ferment_min": 600, "bake_min": 600})
    assert r.status_code == 200
    r = client.post("/api/batches", json={"product_id": 4, "oven_id": 3, "start_min": 0})
    assert r.status_code == 200
    logs_before = _count(ConflictLog)

    r = client.post("/api/batches", json={"product_id": 4, "oven_id": 3, "start_min": -5})
    assert r.status_code == 400
    assert "start_min" in r.json()["detail"]
    assert _count(Batch) == 4
    assert _count(ConflictLog) == logs_before


# --- legal boundary values are accepted -------------------------------------


def test_boundary_recipe_zero_ferment_one_bake_ok(client):
    r = client.post("/api/products", json={"name": "边界配方", "ferment_min": 0, "bake_min": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["ferment_min"] == 0
    assert body["bake_min"] == 1
    assert _count(Product) == 4


def test_boundary_start_zero_ok(client):
    r = client.post("/api/batches", json={"product_id": 3, "oven_id": 3, "start_min": 0})
    assert r.status_code == 200
    assert r.json()["start_min"] == 0
    assert _count(Batch) == 4


# --- direct DB writes bypassing the app hit the CHECK constraints -----------


def test_direct_insert_negative_bake_fails(db):
    with pytest.raises(IntegrityError) as exc:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO products (name, ferment_min, bake_min) VALUES ('直插负烘烤', 10, -5)")
            )
    assert "ck_products_bake_min_gte_1" in str(exc.value)


def test_direct_insert_negative_ferment_fails(db):
    with pytest.raises(IntegrityError) as exc:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO products (name, ferment_min, bake_min) VALUES ('直插负发酵', -1, 30)")
            )
    assert "ck_products_ferment_min_gte_0" in str(exc.value)


def test_direct_insert_negative_start_fails(db):
    with pytest.raises(IntegrityError) as exc:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO batches (product_id, oven_id, code, start_min, status, created_at)"
                    " VALUES (1, 3, 'BO-负开工', -1, 'scheduled', CURRENT_TIMESTAMP)"
                )
            )
    assert "ck_batches_start_min_gte_0" in str(exc.value)


def test_direct_insert_full_day_start_fails(db):
    with pytest.raises(IntegrityError) as exc:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO batches (product_id, oven_id, code, start_min, status, created_at)"
                    " VALUES (1, 3, 'BO-越界', 1440, 'scheduled', CURRENT_TIMESTAMP)"
                )
            )
    assert "ck_batches_start_min_lt_1440" in str(exc.value)


def test_direct_insert_boundaries_ok(db):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO products (name, ferment_min, bake_min) VALUES ('直插边界', 0, 1)")
        )
        conn.execute(
            text(
                "INSERT INTO batches (product_id, oven_id, code, start_min, status, created_at)"
                " VALUES (1, 3, 'BO-边界', 1439, 'scheduled', CURRENT_TIMESTAMP)"
            )
        )
    assert _count(Product) == 4
    assert _count(Batch) == 4


# --- migration stays in sync with the models --------------------------------


def test_migration_file_covers_model_constraints():
    sql = (
        Path(__file__).resolve().parents[1] / "migrations" / "001_recipe_start_checks.sql"
    ).read_text(encoding="utf-8")
    model_names = {
        c.name
        for table in (Product.__table__, Batch.__table__)
        for c in table.constraints
        if isinstance(c, CheckConstraint)
    }
    assert model_names == {
        "ck_products_ferment_min_gte_0",
        "ck_products_bake_min_gte_1",
        "ck_batches_start_min_gte_0",
        "ck_batches_start_min_lt_1440",
    }
    for name in model_names:
        assert name in sql
    for expr in ("ferment_min >= 0", "bake_min >= 1", "start_min >= 0", "start_min < 1440"):
        assert expr in sql


def test_apply_migrations_skips_non_postgres():
    assert apply_migrations(engine) == []
