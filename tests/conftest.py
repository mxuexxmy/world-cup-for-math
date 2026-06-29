"""Pytest config — never use production worldcup.db in tests."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROD_DB = ROOT / "worldcup.db"


@pytest.fixture(autouse=True)
def _block_prod_db_mutation(monkeypatch, tmp_path, request):
    """Route tests to a temporary SQLite file unless explicitly opted out."""
    if request.node.get_closest_marker("uses_prod_db"):
        return
    test_db = tmp_path / "pytest.db"
    sync_url = f"sqlite:///{test_db.as_posix()}"
    async_url = f"sqlite+aiosqlite:///{test_db.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", async_url)
    monkeypatch.setenv("DATABASE_URL_SYNC", sync_url)
    # config module caches URLs at import — patch for modules that read app.config
    import app.config as cfg
    monkeypatch.setattr(cfg, "DATABASE_URL", async_url)
    monkeypatch.setattr(cfg, "DATABASE_URL_SYNC", sync_url)

    import app.models.database as dbmod
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.orm import sessionmaker

    sync_engine = create_engine(sync_url, echo=False)
    async_engine = create_async_engine(async_url, echo=False)
    monkeypatch.setattr(dbmod, "sync_engine", sync_engine)
    monkeypatch.setattr(dbmod, "async_engine", async_engine)
    monkeypatch.setattr(dbmod, "SyncSession", sessionmaker(sync_engine))
    monkeypatch.setattr(
        dbmod, "async_session_factory",
        async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False),
    )
    from app.models.database import Base
    import app.models.team  # noqa: F401 — register models
    import app.models.match  # noqa: F401
    import app.models.prediction  # noqa: F401
    import app.models.odds  # noqa: F401
    Base.metadata.create_all(sync_engine)
