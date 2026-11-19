import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import make_session_factory
from app.main import app, get_db
from app.models import Base


@pytest.fixture
def session_factory():
    """One private in-memory database per test, wired into the app via
    dependency override — the FastAPI equivalent of pointing request
    specs at the test database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)

    def _override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield factory
    app.dependency_overrides.clear()


@pytest.fixture
def client(session_factory) -> TestClient:
    """HTTP client bound to the FastAPI app; no real network involved."""
    return TestClient(app)


@pytest.fixture
def seed(session_factory):
    """Insert Station rows for a test to build on."""

    def _seed(*stations):
        with session_factory() as session:
            session.add_all(stations)
            session.commit()

    return _seed
