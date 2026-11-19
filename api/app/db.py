"""Engine and session factories: how the app talks to the database."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings


def make_engine(url: str | None = None) -> Engine:
    """Create an engine from an explicit URL or the configured DATABASE_URL."""
    return create_engine(url or Settings().database_url, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a factory producing sessions bound to the given engine."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
