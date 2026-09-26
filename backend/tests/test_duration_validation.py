"""时长与开工校验：接口拒绝（带字段名、条数不变）、直插库失败、边界值。"""

from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import IntegrityError

from app.models.models import Batch, Oven, Product
from app.services.seed import seed_if_empty
from app.services.validation import (
    FieldValidationError,
    validate_recipe,
    validate_start_min,
)

MIGRATION_SQL = (
    Path(__file__).resolve().parents[1] / "migrations" / "001_add_duration_start_checks.sql"
)


@pytest.fixture()
def seeded(client, db_session):
    seed_if_empty(db_session)
    return client


# ---------- 校验器本身：错误必须带字段名 ----------


def test_validators_accept_legal_boundaries():
    validate_recipe(ferment_min=0, bake_min=1)
    validate_start_min(0)
    validate_start_min(24 * 60 - 1)


@pytest.mark.parametrize(
    ("fn", "kwargs", "field"),
    [
        (validate_recipe, {"ferment_min": -1, "bake_min": 10}, "ferment_min"),
        (validate_recipe, {"ferment_min": 10, "bake_min": 0}, "bake_min"),
        (validate_recipe, {"ferment_min": 10, "bake_min": -5}, "bake_min"),
        (validate_start_min, {"value": -1}, "start_min"),
        (validate_start_min, {"value": 24 * 60}, "start_min"),
    ],
)
def test_validators_name_the_offending_field(fn, kwargs, field):
    with pytest.raises(FieldValidationError) as err:
        fn(**kwargs)
    assert err.value.field == field
    assert field in str(err.value)


# ---------- 模型与迁移文件：同一套约束、同名 ----------


def test_models_carry_named_check_constraints():
    product_checks = {
        c.name for c in Product.__table__.constraints if isinstance(c, CheckConstraint)
    }
    assert "ck_products_ferment_min_nonnegative" in product_checks
    assert "ck_products_bake_min_positive" in product_checks
    batch_checks = {
        c.name for c in Batch.__table__.constraints if isinstance(c, CheckConstraint)
    }
    assert "ck_batches_start_min_within_day" in batch_checks


def test_migration_sql_covers_the_same_constraints():
    sql = MIGRATION_SQL.read_text(encoding="utf-8")
    assert "ck_products_ferment_min_nonnegative" in sql
    assert "ck_products_bake_min_positive" in sql
    assert "ck_batches_start_min_within_day" in sql
    assert "ferment_min >= 0" in sql
    assert "bake_min >= 1" in sql
    assert "start_min >= 0 AND start_min < 1440" in sql


# ---------- 种子与甘特：迁移约束下仍可用、色块不变 ----------


def test_seed_and_gantt_blocks_unchanged(seeded):
    products = seeded.get("/api/products").json()
    assert [p["name"] for p in products] == ["乡村欧包", "黄油可颂", "布朗尼"]
    batches = seeded.get("/api/batches").json()
    assert [b["code"] for b in batches] == ["BO-0900", "BO-1000", "BO-1030"]

    blocks = [
        (b["code"], b["phase"], b["start_min"], b["end_min"])
        for b in seeded.get("/api/gantt").json()
    ]
    assert blocks == [
        ("BO-0900", "ferment", 9 * 60, 9 * 60 + 40),
        ("BO-0900", "bake", 9 * 60 + 40, 9 * 60 + 75),
        ("BO-1000", "ferment", 10 * 60, 10 * 60),  # 布朗尼发酵 0 分钟
        ("BO-1000", "bake", 10 * 60, 10 * 60 + 30),
        ("BO-1030", "ferment", 10 * 60 + 30, 10 * 60 + 55),
        ("BO-1030", "bake", 10 * 60 + 55, 10 * 60 + 75),
    ]


# ---------- 经接口拒绝：422、指出字段、条数不变、不进重叠判断 ----------


def _counts(client):
    return (
        len(client.get("/api/products").json()),
        len(client.get("/api/batches").json()),
        len(client.get("/api/conflicts").json()),
    )


@pytest.mark.parametrize("start_min", [-1, 24 * 60])
def test_create_batch_rejects_bad_start_min(seeded, start_min):
    before = _counts(seeded)
    resp = seeded.post(
        "/api/batches", json={"product_id": 1, "oven_id": 1, "start_min": start_min}
    )
    assert resp.status_code == 422
    assert "start_min" in resp.json()["detail"]
    assert _counts(seeded) == before  # 批次不变，且未写入冲突日志（先于重叠判断）


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"name": "负发酵", "ferment_min": -1, "bake_min": 30}, "ferment_min"),
        ({"name": "零烘烤", "ferment_min": 10, "bake_min": 0}, "bake_min"),
        ({"name": "负烘烤", "ferment_min": 10, "bake_min": -1}, "bake_min"),
    ],
)
def test_create_product_rejects_bad_recipe(seeded, payload, field):
    before = _counts(seeded)
    resp = seeded.post("/api/products", json=payload)
    assert resp.status_code == 422
    assert field in resp.json()["detail"]
    assert _counts(seeded) == before  # 产品条数不变


def test_overlap_conflict_still_409_for_valid_input(seeded):
    # 与 BO-0900 的发酵段 [540,580) 重叠的合法开工分钟：仍走重叠判断
    resp = seeded.post(
        "/api/batches", json={"product_id": 1, "oven_id": 1, "start_min": 545}
    )
    assert resp.status_code == 409
    assert len(seeded.get("/api/conflicts").json()) == 2  # 种子 1 条 + 新冲突 1 条


# ---------- 合法边界：发酵 0 / 烘烤 1 / 开工 0 可以写入 ----------


def test_boundary_values_accepted_via_api(seeded):
    resp = seeded.post(
        "/api/products", json={"name": "边界产品", "ferment_min": 0, "bake_min": 1}
    )
    assert resp.status_code == 200
    product_id = resp.json()["id"]

    resp = seeded.post(
        "/api/batches", json={"product_id": product_id, "oven_id": 1, "start_min": 0}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["start_min"] == 0
    assert body["ferment_end"] == 0
    assert body["bake_end"] == 1

    blocks = [
        (b["code"], b["phase"], b["start_min"], b["end_min"])
        for b in seeded.get("/api/gantt").json()
        if b["batch_id"] == body["id"]
    ]
    assert blocks == [(body["code"], "ferment", 0, 0), (body["code"], "bake", 0, 1)]


def test_boundary_values_accepted_on_direct_insert(db_session):
    db_session.add(Product(name="直插边界", ferment_min=0, bake_min=1))
    db_session.add(Oven(label="直插炉"))
    db_session.flush()
    product = db_session.query(Product).filter_by(name="直插边界").one()
    oven = db_session.query(Oven).filter_by(label="直插炉").one()
    db_session.add(
        Batch(product_id=product.id, oven_id=oven.id, code="BO-EDGE", start_min=0)
    )
    db_session.commit()
    assert db_session.query(Batch).filter_by(code="BO-EDGE").count() == 1


# ---------- 绕过应用直接插库：约束必须拒绝 ----------


def test_direct_insert_negative_bake_min_fails(db_session):
    db_session.add(Product(name="负烘烤", ferment_min=10, bake_min=-1))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_direct_insert_negative_ferment_min_fails(db_session):
    db_session.add(Product(name="负发酵", ferment_min=-1, bake_min=10))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("start_min", [-1, 24 * 60])
def test_direct_insert_out_of_range_start_min_fails(db_session, start_min):
    db_session.add(Product(name="直插产品", ferment_min=10, bake_min=10))
    db_session.add(Oven(label="直插炉"))
    db_session.flush()
    product = db_session.query(Product).filter_by(name="直插产品").one()
    oven = db_session.query(Oven).filter_by(label="直插炉").one()
    db_session.add(
        Batch(product_id=product.id, oven_id=oven.id, code="BO-BAD", start_min=start_min)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
