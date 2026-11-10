"""Pytest root configuration and test session fixtures.

Forces tests to run strictly against an isolated test database (ending in _test)
so the primary development database is never polluted with ephemeral test fixtures.
"""

import os
import sys

# ---------------------------------------------------------------------------
# 1. IMMEDIATE ENVIRONMENT REDIRECTION (MUST RUN BEFORE ANY CALLWISE IMPORTS)
# ---------------------------------------------------------------------------
# Determine target test database name (must end in _test)
ORIGINAL_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/callwise",
)
ORIGINAL_SYNC_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg://postgres:postgres@localhost:5433/callwise",
)

# Extract base connection components and enforce _test suffix
if "/callwise_test" not in ORIGINAL_DATABASE_URL:
    if ORIGINAL_DATABASE_URL.endswith("/callwise"):
        TEST_ASYNC_URL = ORIGINAL_DATABASE_URL + "_test"
    else:
        # Replace the database name with callwise_test
        base, sep, db = ORIGINAL_DATABASE_URL.rpartition("/")
        TEST_ASYNC_URL = f"{base}/callwise_test"
else:
    TEST_ASYNC_URL = ORIGINAL_DATABASE_URL

if "/callwise_test" not in ORIGINAL_SYNC_URL:
    if ORIGINAL_SYNC_URL.endswith("/callwise"):
        TEST_SYNC_URL = ORIGINAL_SYNC_URL + "_test"
    else:
        base, sep, db = ORIGINAL_SYNC_URL.rpartition("/")
        TEST_SYNC_URL = f"{base}/callwise_test"
else:
    TEST_SYNC_URL = ORIGINAL_SYNC_URL

# Safety Guard: Abort immediately if database name does not end in _test
db_name = TEST_ASYNC_URL.rpartition("/")[-1]
if not db_name.endswith("_test"):
    raise RuntimeError(
        f"CRITICAL SAFETY VIOLATION: Test database name '{db_name}' must end with '_test'! "
        f"Aborting pytest run to prevent polluting development or production database."
    )

# Force environment variables before any pydantic settings or database modules load
os.environ["DATABASE_URL"] = TEST_ASYNC_URL
os.environ["DATABASE_URL_SYNC"] = TEST_SYNC_URL

# ---------------------------------------------------------------------------
# 2. PYTEST SESSION FIXTURES: SETUP MIGRATIONS & TEARDOWN DATABASE
# ---------------------------------------------------------------------------
import pytest
from alembic.config import Config
from alembic import command
import psycopg


def _clean_pg_url(url: str) -> str:
    """Strip asyncpg/psycopg prefixes for standard psycopg connection."""
    clean = url.replace("postgresql+asyncpg://", "postgresql://")
    clean = clean.replace("postgresql+psycopg://", "postgresql://")
    return clean


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Session-scoped autouse fixture:
    1. Connects to postgres maintenance DB and creates the isolated test database.
    2. Runs Alembic migrations to apply current schema.
    3. Yields for test suite execution.
    4. Drops or truncates test database at session conclusion.
    """
    # Guard check again at session start
    from callwise.config import settings
    active_db = settings.database_url.rpartition("/")[-1]
    if not active_db.endswith("_test"):
        raise RuntimeError(
            f"Active settings database '{active_db}' does not end in '_test'. Aborting."
        )

    # 1. Maintenance connection to create fresh test DB
    sync_url = _clean_pg_url(settings.database_url_sync)
    base_server_url, _, target_db = sync_url.rpartition("/")
    maintenance_url = f"{base_server_url}/postgres"

    # Create fresh test database
    with psycopg.connect(maintenance_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"DROP DATABASE IF EXISTS {target_db} WITH (FORCE);"
            )
            cur.execute(f"CREATE DATABASE {target_db};")

    # 2. Run Alembic migrations on the new test database
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield

    # 3. Teardown: drop test database cleanly at end of test session
    try:
        from callwise.db.session import async_engine, sync_engine
        sync_engine.dispose()
    except Exception:
        pass

    try:
        with psycopg.connect(maintenance_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DROP DATABASE IF EXISTS {target_db} WITH (FORCE);"
                )
    except Exception as exc:
        print(f"[conftest] Warning during test DB cleanup: {exc}", file=sys.stderr)

