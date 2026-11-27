from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import db
from app.models import Measurement, Station

app = FastAPI(title="luft api")

# Window sizes accepted by GET /stations/{id}/measurements?range=
RANGES: dict[str, timedelta] = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}


def _iso_utc(dt: datetime) -> str:
    """Render a stored timestamp as ISO-8601 UTC (sqlite drops tzinfo on the way out)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request, exc: StarletteHTTPException) -> JSONResponse:
    """All HTTP errors as {"error": "..."} (spec: JSON errors use this shape)."""
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


_engine = db.make_engine()  # connects lazily; real DATABASE_URL comes from the environment
SessionFactory = db.make_session_factory(_engine)


def get_db():
    """Yield a database session for one request (FastAPI dependency)."""
    with SessionFactory() as session:
        yield session


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe: returns 200 as long as the service is up."""
    return {"status": "ok"}


@app.get("/stations")
def list_stations(q: str | None = None, session: Session = Depends(get_db)) -> list[dict]:
    """All stations ordered by city then name; `q` filters name and city
    case-insensitively."""
    stmt = select(Station).order_by(Station.city, Station.name)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(Station.name.ilike(pattern), Station.city.ilike(pattern))
        )
    return [
        {"id": s.id, "name": s.name, "city": s.city, "lat": s.lat, "lon": s.lon}
        for s in session.scalars(stmt)
    ]


@app.get("/stations/{station_id}/measurements")
def station_measurements(
    station_id: int, range: str = "24h", session: Session = Depends(get_db)
) -> dict:
    """Hourly points for one station within `range` (24h or 7d), oldest first."""
    if range not in RANGES:
        raise HTTPException(status_code=422, detail="nieobsługiwany zakres")
    if session.get(Station, station_id) is None:
        raise HTTPException(status_code=404, detail="nieznana stacja")

    cutoff = datetime.now(timezone.utc) - RANGES[range]
    stmt = (
        select(Measurement)
        .where(
            Measurement.station_id == station_id,
            Measurement.measured_hour >= cutoff,
        )
        .order_by(Measurement.measured_hour)
    )
    points = [
        {"measured_hour": _iso_utc(m.measured_hour), "pm25": m.pm25, "pm10": m.pm10}
        for m in session.scalars(stmt)
    ]
    return {"station_id": station_id, "points": points}
