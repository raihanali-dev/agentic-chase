"""Async SQLite engine and session factory."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_DB_PATH = os.getenv("SQLITE_PATH", "./agentic_chase.db")
if not Path(_DB_PATH).is_absolute():
    _DB_PATH = str(Path(__file__).resolve().parent / _DB_PATH)

DATABASE_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    from models import (  # noqa: F401
        Chat,
        Directive,
        Message,
        PendingAction,
        Persona,
        Project,
        Setting,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
