"""Tests for production container setup, Caddy, health checks, doctor command, and backup/restore."""

from pathlib import Path
import gzip
import pytest
from httpx import AsyncClient, ASGITransport
import yaml

from callwise.api.main import app
from callwise.calls.killswitch import disable_kill_switch, enable_kill_switch
from callwise.db.backup import create_database_backup, restore_database_backup


@pytest.fixture(autouse=True)
def ensure_clean_killswitch():
    disable_kill_switch()
    yield
    disable_kill_switch()


# =========================================================================
# 1. HEALTH CHECK ENDPOINT TESTS (/health & /api/health)
# =========================================================================

@pytest.mark.asyncio
async def test_health_check_healthy():
    """Verify /health and /api/health return healthy status and database connection."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test root /health
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["kill_switch_active"] is False
        assert data["version"] == "0.1.0"

        # Test /api/health
        api_res = await client.get("/api/health")
        assert api_res.status_code == 200
        api_data = api_res.json()
        assert api_data["status"] == "ok"
        assert api_data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_check_reflects_kill_switch():
    """Verify health check accurately reports kill switch state."""
    enable_kill_switch(reason="Testing health check reflection")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["kill_switch_active"] is True


# =========================================================================
# 2. DOCTOR COMMAND DIAGNOSTIC TESTS
# =========================================================================

def test_cli_doctor_command():
    """Verify callwise doctor command executes and completes diagnostic checks successfully."""
    from typer.testing import CliRunner
    from callwise.cli import app as cli_app

    runner = CliRunner()
    result = runner.invoke(cli_app, ["doctor"])
    assert result.exit_code == 0
    assert "CALLWISE SYSTEM DIAGNOSTIC" in result.output
    assert "Database Connection" in result.output
    assert "pgvector Extension" in result.output
    assert "All critical systems are operational!" in result.output


# =========================================================================
# 3. DATABASE BACKUP AND RESTORE TESTS
# =========================================================================

def test_database_backup_and_restore(tmp_path):
    """Verify backup file creation, gzip compression, and restore execution."""
    # 1. Create backup in isolated temporary path
    backup_path = create_database_backup(output_dir=tmp_path)

    assert backup_path.exists()
    assert backup_path.name.endswith(".sql.gz")
    assert backup_path.stat().st_size > 0

    # 2. Verify decompressed content contains valid SQL statements
    with gzip.open(backup_path, "rt", encoding="utf-8") as gz:
        content = gz.read()
        assert "CREATE EXTENSION" in content or "INSERT INTO" in content or "Callwise Database Backup" in content

    # 3. Test restore function
    success = restore_database_backup(backup_path)
    assert success is True


def test_restore_nonexistent_file_raises():
    """Verify restoring a missing file raises FileNotFoundError."""
    missing = Path("backups/nonexistent_file.sql.gz")
    with pytest.raises(FileNotFoundError):
        restore_database_backup(missing)


# =========================================================================
# 4. DOCKER AND CONTAINER ARTIFACT VERIFICATION
# =========================================================================

def test_backend_dockerfile_structure():
    """Verify backend Dockerfile has multi-stage build, unprivileged user, and health check."""
    dockerfile = Path("Dockerfile")
    assert dockerfile.exists()
    content = dockerfile.read_text(encoding="utf-8")

    assert "FROM python:3.12-slim AS builder" in content
    assert "FROM python:3.12-slim AS runner" in content
    assert "useradd -u 1001" in content
    assert "USER callwise" in content
    assert "HEALTHCHECK" in content
    assert "EXPOSE 8000" in content


def test_web_dockerfile_structure():
    """Verify web Dockerfile has multi-stage build, unprivileged user, and health check."""
    dockerfile = Path("web/Dockerfile")
    assert dockerfile.exists()
    content = dockerfile.read_text(encoding="utf-8")

    assert "FROM node:20-alpine AS deps" in content
    assert "FROM node:20-alpine AS builder" in content
    assert "FROM node:20-alpine AS runner" in content
    assert "USER nextjs" in content
    assert "HEALTHCHECK" in content
    assert "EXPOSE 3000" in content


def test_caddyfile_configuration():
    """Verify Caddyfile defines reverse proxies for /api, /health, and frontend."""
    caddyfile = Path("Caddyfile")
    assert caddyfile.exists()
    content = caddyfile.read_text(encoding="utf-8")

    assert "handle /health" in content
    assert "handle /api/*" in content
    assert "reverse_proxy backend:8000" in content
    assert "reverse_proxy web:3000" in content
    assert "encode gzip zstd" in content


def test_docker_compose_production_configuration():
    """Verify docker-compose.prod.yml defines all services and valid YAML."""
    compose_file = Path("docker-compose.prod.yml")
    assert compose_file.exists()
    data = yaml.safe_load(compose_file.read_text(encoding="utf-8"))

    services = data.get("services", {})
    assert "postgres" in services
    assert "backend" in services
    assert "worker" in services
    assert "scheduler" in services
    assert "web" in services
    assert "caddy" in services

    # Verify dependency chains and health checks
    assert "healthcheck" in services["postgres"]
    assert "healthcheck" in services["backend"]
    assert "healthcheck" in services["web"]


def test_backup_and_restore_scripts():
    """Verify POSIX shell and PowerShell backup/restore scripts exist."""
    assert Path("scripts/backup.sh").exists()
    assert Path("scripts/restore.sh").exists()
    assert Path("scripts/backup.ps1").exists()
    assert Path("scripts/restore.ps1").exists()

