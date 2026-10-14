from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

import app.models  # noqa: F401  (registers the tables on SQLModel.metadata)


def make_engine(data_dir: Path) -> Engine:
    """SQLite file in the data directory; tables are created on first use."""
    engine = create_engine(
        f"sqlite:///{data_dir / 'postcall.db'}",
        connect_args={"check_same_thread": False},  # the job worker has its own sessions
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")  # readers do not block the job worker
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    return engine
