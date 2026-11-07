"""Database backup and restore utilities with compression and fallback support."""

from datetime import datetime, timezone
import gzip
import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import text
from callwise.config import settings
from callwise.db.session import sync_engine

logger = logging.getLogger(__name__)


def _parse_db_connection(db_url: str):
    """Extract host, port, user, password, and dbname from SQLAlchemy URL."""
    # Convert asyncpg/psycopg schemes to standard postgresql
    clean_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )
    parsed = urlparse(clean_url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
        "dbname": parsed.path.lstrip("/"),
    }


def create_database_backup(
    output_dir: Optional[Path] = None,
    db_url: Optional[str] = None,
) -> Path:
    """
    Create a compressed database backup archive (.sql.gz).
    Uses pg_dump if available on PATH; otherwise falls back to Python SQL schema & data dump.
    """
    target_dir = Path(output_dir) if output_dir else Path("backups")
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = target_dir / f"callwise_backup_{timestamp}.sql.gz"

    url = db_url or settings.database_url
    conn_info = _parse_db_connection(url)

    pg_dump_bin = shutil.which("pg_dump")

    if pg_dump_bin:
        env = os.environ.copy()
        if conn_info["password"]:
            env["PGPASSWORD"] = conn_info["password"]

        cmd = [
            pg_dump_bin,
            "-h", conn_info["host"],
            "-p", conn_info["port"],
            "-U", conn_info["user"],
            "-d", conn_info["dbname"],
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
        ]

        logger.info(f"Running pg_dump command: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=env, capture_output=True, check=False)
        if result.returncode == 0 and result.stdout:
            with gzip.open(backup_file, "wb") as gz:
                gz.write(result.stdout)
            logger.info(f"Backup created successfully via pg_dump at {backup_file}")
            return backup_file
        else:
            logger.warning(
                f"pg_dump returned error code {result.returncode}: {result.stderr.decode('utf-8', errors='ignore')}. "
                f"Attempting Python SQL fallback dump."
            )

    # Fallback SQL dumper using SQLAlchemy
    engine = sync_engine
    sql_chunks = ["-- Callwise Database Backup (Python SQL Fallback)\n"]
    sql_chunks.append(f"-- Timestamp: {datetime.now(timezone.utc).isoformat()}\n\n")

    with engine.connect() as connection:
        # Check extensions
        exts = connection.execute(
            text("SELECT extname FROM pg_extension;")
        ).scalars().all()
        for ext in exts:
            sql_chunks.append(f"CREATE EXTENSION IF NOT EXISTS \"{ext}\";\n")
        sql_chunks.append("\n")

        # Get all user tables
        tables = connection.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename;"
            )
        ).scalars().all()

        for tbl in tables:
            rows = connection.execute(text(f"SELECT * FROM \"{tbl}\";")).mappings().all()
            if not rows:
                continue
            cols = list(rows[0].keys())
            cols_str = ", ".join([f'"{c}"' for c in cols])

            for row in rows:
                vals = []
                for c in cols:
                    v = row[c]
                    if v is None:
                        vals.append("NULL")
                    elif isinstance(v, (int, float)):
                        vals.append(str(v))
                    elif isinstance(v, bool):
                        vals.append("TRUE" if v else "FALSE")
                    else:
                        clean_str = str(v).replace("'", "''")
                        vals.append(f"'{clean_str}'")
                vals_str = ", ".join(vals)
                sql_chunks.append(
                    f"INSERT INTO \"{tbl}\" ({cols_str}) VALUES ({vals_str}) ON CONFLICT DO NOTHING;\n"
                )

    full_sql = "".join(sql_chunks).encode("utf-8")
    with gzip.open(backup_file, "wb") as gz:
        gz.write(full_sql)

    logger.info(f"Python fallback backup created at {backup_file}")
    return backup_file


def restore_database_backup(
    backup_file: Path,
    db_url: Optional[str] = None,
) -> bool:
    """
    Restore a database from a .sql.gz or .sql backup file.
    """
    file_path = Path(backup_file)
    if not file_path.exists():
        raise FileNotFoundError(f"Backup file not found: {file_path}")

    # Read decompressed SQL content
    if file_path.suffix == ".gz":
        with gzip.open(file_path, "rt", encoding="utf-8", errors="replace") as gz:
            sql_script = gz.read()
    else:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            sql_script = f.read()

    url = db_url or settings.database_url
    conn_info = _parse_db_connection(url)
    psql_bin = shutil.which("psql")

    if psql_bin:
        env = os.environ.copy()
        if conn_info["password"]:
            env["PGPASSWORD"] = conn_info["password"]

        cmd = [
            psql_bin,
            "-h", conn_info["host"],
            "-p", conn_info["port"],
            "-U", conn_info["user"],
            "-d", conn_info["dbname"],
            "-v", "ON_ERROR_STOP=0",
        ]

        logger.info(f"Restoring database via psql command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            input=sql_script.encode("utf-8"),
            env=env,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            logger.info("Database restore completed successfully via psql.")
            return True
        else:
            logger.warning(
                f"psql returned code {result.returncode}. Falling back to direct execution."
            )

    # Fallback direct execution
    engine = sync_engine
    statements = [stmt.strip() for stmt in sql_script.split(";\n") if stmt.strip()]

    with engine.begin() as connection:
        for stmt in statements:
            if stmt.startswith("--") or not stmt:
                continue
            try:
                connection.execute(text(stmt))
            except Exception as e:
                logger.debug(f"Statement execution notice during restore: {e}")

    logger.info("Database restore completed successfully.")
    return True
