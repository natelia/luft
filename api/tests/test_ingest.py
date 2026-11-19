from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.gios import GiosStation
from app.ingest import run_ingest
from app.models import Base, Measurement, Station

HOUR = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)


def station(sid, pm25=31.1, pm10=49.0):
    return GiosStation(id=sid, name=f"st-{sid}", city="Miasto", lat=1.0, lon=2.0, pm25=pm25, pm10=pm10)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_ingest_inserts_station_and_measurement(session):
    result = run_ingest(session, fetch=lambda: [station(400)], now=HOUR)

    assert result.new_stations == 1
    assert result.inserted_measurements == 1
    m = session.scalar(select(Measurement))
    assert m.station_id == 400
    assert m.pm25 == 31.1
    assert m.pm10 == 49.0


def test_double_run_same_hour_no_duplicates(session):
    run_ingest(session, fetch=lambda: [station(400)], now=HOUR)

    result = run_ingest(session, fetch=lambda: [station(400, pm25=32.0)], now=HOUR)

    assert result.inserted_measurements == 0
    assert result.updated_stations == 1
    assert session.scalar(select(func.count(Measurement.id))) == 1
    assert session.scalar(select(Measurement)).pm25 == 32.0  # updated in place, not duplicated


def test_partial_failure_returns_count(session):
    snapshot = [
        station(1),
        station(2),
        station(3, pm25=None, pm10=None),  # sensor dead this hour
        station(4, pm25=None, pm10=None),
    ]

    result = run_ingest(session, fetch=lambda: snapshot, now=HOUR)

    assert result.inserted_measurements == 2
    assert result.failed_stations == 2
    assert session.scalar(select(func.count(Measurement.id))) == 2


def test_write_error_is_contained(session):
    # A malformed station entry (no id) must not cost us the whole snapshot.
    result = run_ingest(session, fetch=lambda: [station(400), station(None)], now=HOUR)

    assert result.failed_stations == 1
    assert result.inserted_measurements == 1
    assert session.scalar(select(func.count(Station.id))) == 1
