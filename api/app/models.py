"""Database models: air-quality stations and their hourly measurements."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class all models inherit from; holds the table registry."""


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # GIOS station id
    name: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Station(id={self.id!r}, city={self.city!r})"


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (UniqueConstraint("station_id", "measured_hour"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    # UTC by convention; rendered in Europe/Warsaw at the API layer.
    measured_hour: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pm25: Mapped[float | None] = mapped_column(Float, nullable=True)  # µg/m³, None = no sensor value
    pm10: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Measurement(station_id={self.station_id!r}, measured_hour={self.measured_hour!r})"
