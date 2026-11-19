"""Hourly ingest: persist one GIOS snapshot into our own database.

Contract:
- idempotent within an hour: a second run updates rows in place
  instead of duplicating them (the hourly scheduler may retry);
- fault-tolerant per station: one broken entry costs one
  ``failed_stations`` count, never the rest of the snapshot.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import gios
from app.config import Settings
from app.gios import GiosStation
from app.models import Measurement, Station


@dataclass
class IngestResult:
    new_stations: int = 0
    updated_stations: int = 0
    inserted_measurements: int = 0
    failed_stations: int = 0


def run_ingest(
    session: Session,
    *,
    fetch: Callable[[], list[GiosStation]] | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> IngestResult:
    """Pull one snapshot (``fetch`` is injectable for tests) and store it."""
    settings = settings or Settings()
    fetcher = fetch or (lambda: gios.fetch_all(settings))
    hour = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)

    result = IngestResult()
    for st in fetcher():
        try:
            # Savepoint = transaction inside the transaction: a failure
            # rolls back only this station, keeping everything before it.
            # Counters grow only after the savepoint commits, so they
            # never report work that was rolled back.
            with session.begin_nested():
                delta = _process_station(session, st, hour)
        except Exception:
            result.failed_stations += 1
        else:
            result.new_stations += delta.new_stations
            result.updated_stations += delta.updated_stations
            result.inserted_measurements += delta.inserted_measurements
            result.failed_stations += delta.failed_stations
    session.commit()
    return result


def _process_station(session: Session, st: GiosStation, hour: datetime) -> IngestResult:
    delta = IngestResult()
    _upsert_station(session, st, delta)
    _write_measurement(session, st, hour, delta)
    return delta


def _upsert_station(session: Session, st: GiosStation, delta: IngestResult) -> None:
    row = session.get(Station, st.id)
    if row is None:
        session.add(Station(id=st.id, name=st.name, city=st.city, lat=st.lat, lon=st.lon))
        delta.new_stations += 1
    else:
        row.name, row.city, row.lat, row.lon = st.name, st.city, st.lat, st.lon
        delta.updated_stations += 1


def _write_measurement(session: Session, st: GiosStation, hour: datetime, delta: IngestResult) -> None:
    if st.pm25 is None and st.pm10 is None:
        delta.failed_stations += 1  # catalog row kept, but no usable reading this hour
        return

    row = session.scalar(
        select(Measurement).where(
            Measurement.station_id == st.id,
            Measurement.measured_hour == hour,
        )
    )
    if row is None:
        session.add(
            Measurement(station_id=st.id, measured_hour=hour, pm25=st.pm25, pm10=st.pm10)
        )
        delta.inserted_measurements += 1
    else:
        row.pm25, row.pm10 = st.pm25, st.pm10  # retry in the same hour -> refresh in place
