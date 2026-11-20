from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def normalize_database_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        return database_url

    query = dict(url.query)
    sslmode = query.get("sslmode")
    if isinstance(sslmode, tuple):
        raise ValueError("PostgreSQL connection URL must have only one sslmode.")
    if sslmode is None:
        query["sslmode"] = "require"
    elif sslmode.lower() not in {"require", "verify-ca", "verify-full"}:
        raise ValueError(
            "PostgreSQL connections must use sslmode=require, verify-ca, or verify-full."
        )

    return url.set(
        drivername="postgresql+psycopg",
        query=query,
    ).render_as_string(hide_password=False)


def create_database_engine(database_url: str) -> Engine:
    options: dict[str, int | bool] = {"pool_pre_ping": True}
    if not database_url.startswith("sqlite"):
        options.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
        )

    return create_engine(normalize_database_url(database_url), **options)


engine = create_database_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
