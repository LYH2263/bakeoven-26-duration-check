from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

MINUTES_PER_DAY = 24 * 60


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("ferment_min >= 0", name="ck_products_ferment_min_nonnegative"),
        CheckConstraint("bake_min >= 1", name="ck_products_bake_min_positive"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    ferment_min: Mapped[int] = mapped_column(Integer)
    bake_min: Mapped[int] = mapped_column(Integer)


class Oven(Base):
    __tablename__ = "ovens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(40), unique=True)
    capacity_note: Mapped[str] = mapped_column(String(80), default="")


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (
        CheckConstraint(
            f"start_min >= 0 AND start_min < {MINUTES_PER_DAY}",
            name="ck_batches_start_min_within_day",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    oven_id: Mapped[int] = mapped_column(ForeignKey("ovens.id"))
    code: Mapped[str] = mapped_column(String(40), unique=True)
    start_min: Mapped[int] = mapped_column(Integer)  # minutes from 00:00
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConflictLog(Base):
    __tablename__ = "conflict_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_code: Mapped[str] = mapped_column(String(40))
    oven_id: Mapped[int] = mapped_column(Integer)
    detail: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
