"""Alembic environment configuration."""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import get_settings  # noqa: E402
from src.database.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _expand_sqlite_path(url: str) -> str:
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "", 1)
        expanded = Path(path).expanduser()
        return f"sqlite:///{expanded}"
    if url.startswith("sqlite://"):
        path = url.replace("sqlite://", "", 1)
        expanded = Path(path).expanduser()
        return f"sqlite://{expanded}"
    return url


def _normalize_url(url: str) -> str:
    if "+aiosqlite" in url:
        url = url.replace("+aiosqlite", "")
    return _expand_sqlite_path(url)


def get_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return _normalize_url(url)
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return _normalize_url(configured)
    return _normalize_url(get_settings().database.url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
