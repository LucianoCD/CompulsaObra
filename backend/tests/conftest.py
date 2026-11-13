"""Fixtures de prueba compartidas para la suite de pytest."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import auth_rate_limiter
from app.main import app
from app.services.seed import seed_demo_data_if_needed


@pytest.fixture(scope="session")
def test_engine():
    # Usar StaticPool para que la base SQLite in-memory persista entre conexiones y sesiones
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(scope="function")
def db(test_engine):
    auth_rate_limiter.reset()
    Session = sessionmaker(bind=test_engine)
    session = Session()
    seed_demo_data_if_needed(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
