from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
 
from app import models  # noqa: F401
from app.db.base import Base

from app.core.application import create_app
from app.db.session import get_db
from app.models.enums import RoleName
from app.models.role import Role


@pytest.fixture
def client() -> Iterator[TestClient]:
    application = create_app()
    application.dependency_overrides[get_db] = lambda: None
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def auth_client(db_session: Session) -> Iterator[TestClient]:
    for role_name in RoleName:
        if db_session.query(Role).filter_by(name=role_name).one_or_none() is None:
            db_session.add(Role(name=role_name))
    db_session.commit()

    application = create_app()
    application.dependency_overrides[get_db] = lambda: db_session
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()
