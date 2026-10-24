"""
alembic/env.py — Alembic migration environment.

Customised from the default template to:
  1. Load DATABASE_URL from the .env file (via our Settings class).
  2. Import all models so Alembic can detect schema changes automatically.
  3. Support both offline (SQL script) and online (live DB) migration modes.
"""

import sys
import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Add quiz-backend/ to Python path ─────────────────────────────────────────
# This lets Alembic import "from app.xxx import ..." even when run from the
# quiz-backend/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Load application settings (reads .env) ───────────────────────────────────
from app.config import get_settings

settings = get_settings()

# ── Import all models so Alembic sees every table ────────────────────────────
# If you add a new model file, import it here too.
import app.models  # noqa: F401 — side-effect: registers models with Base

from app.database import Base

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url from our Settings (reads .env automatically).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData object containing all our table definitions.
# Alembic uses this to generate migration scripts automatically.
target_metadata = Base.metadata


# ── Migration helpers ─────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This generates an SQL script without connecting to the database.
    Useful when you want to review SQL before running it, or when you
    don't have direct database access.

    Usage:
        alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    This connects directly to the database and applies schema changes.
    This is the mode used by 'alembic upgrade head'.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Detect column type changes
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
