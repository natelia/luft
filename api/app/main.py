from fastapi import Depends, FastAPI
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import db
from app.models import Station

app = FastAPI(title="luft api")

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
