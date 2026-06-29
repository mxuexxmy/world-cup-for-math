"""SQLAlchemy database engine and session management."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL, DATABASE_URL_SYNC

# Async engine for FastAPI
async_engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine for seeding and scraping
sync_engine = create_engine(DATABASE_URL_SYNC, echo=False)
SyncSession = sessionmaker(sync_engine)


class Base(DeclarativeBase):
    pass


def migrate_db_sync() -> None:
    """Apply Alembic migrations to latest revision."""
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    command.upgrade(cfg, "head")


async def get_db():
    """FastAPI dependency: yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Ensure schema is up to date via Alembic."""
    migrate_db_sync()


def init_db_sync():
    """Migrate schema synchronously (for seeding)."""
    migrate_db_sync()
