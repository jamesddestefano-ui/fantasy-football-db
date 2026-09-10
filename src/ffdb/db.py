from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB = Path("data/fantasy.db")


def database_url(path: Path | None = None) -> str:
    configured = os.getenv("FFDB_DATABASE_URL")
    if configured:
        return configured
    target = (path or DEFAULT_DB).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{target}"


def make_engine(path: Path | None = None, url: str | None = None) -> Engine:
    engine = create_engine(url or database_url(path), future=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def session_factory(engine: Engine):
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine):
    session = session_factory(engine)()
    try:
        with session.begin():
            yield session
    finally:
        session.close()

