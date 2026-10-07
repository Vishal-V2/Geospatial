import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class UploadedFile(Base):
    __tablename__ = "files"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    filename: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="PROCESSING")
    crs: Mapped[str | None] = mapped_column(String, nullable=True)
    feature_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    features: Mapped[list["Feature"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class Feature(Base):
    __tablename__ = "features"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    layer: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry_type: Mapped[str] = mapped_column(String)
    geometry: Mapped[dict | None] = mapped_column(JSON)
    crs: Mapped[str | None] = mapped_column(String)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    measurement_supported: Mapped[bool] = mapped_column(Boolean, default=False)
    area_sq_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    projected_crs: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    file: Mapped[UploadedFile] = relationship(back_populates="features")