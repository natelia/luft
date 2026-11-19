from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, Measurement, Station


@pytest.fixture
def session():
    """A session bound to a private in-memory sqlite database.

    StaticPool keeps a single connection so every session in a test talks
    to the same in-memory database (a fresh connection would get a new one).
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_station_and_measurement_roundtrip(session):
    session.add(
        Station(id=400, name="Kraków, Al. Krasińskiego", city="Kraków", lat=50.06, lon=19.94)
    )
    session.commit()

    m = Measurement(
        station_id=400,
        measured_hour=datetime(2026, 11, 19, 12, tzinfo=timezone.utc),
        pm25=31.0,
        pm10=49.0,
    )
    session.add(m)
    session.commit()

    assert m.id is not None


def test_duplicate_station_hour_rejected(session):
    session.add(Station(id=400, name="x", city="y", lat=1.0, lon=1.0))
    session.commit()
    hour = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)

    session.add(Measurement(station_id=400, measured_hour=hour, pm25=1.0))
    session.commit()

    session.add(Measurement(station_id=400, measured_hour=hour, pm25=2.0))
    with pytest.raises(IntegrityError):
        session.commit()
