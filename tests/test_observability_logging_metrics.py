"""Tests for structured JSON logging, PII data redaction, Prometheus metrics, and CI workflow."""

import json
import logging
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
import yaml

from callwise.api.main import app
from callwise.config import settings
from callwise.observability.logging import (
    JSONFormatter,
    RedactionFilter,
    redact_sensitive_text,
    setup_logging,
)
from callwise.observability.metrics import MetricsRegistry, metrics


# =========================================================================
# 1. PII AND CREDENTIAL REDACTION TESTS
# =========================================================================

def test_redact_credit_cards():
    """Verify credit card numbers are masked."""
    text = "User provided card 4532-1234-5678-9012 for billing verification."
    redacted = redact_sensitive_text(text)
    assert "4532-1234-5678-9012" not in redacted
    assert "[REDACTED_CARD]" in redacted


def test_redact_ssn():
    """Verify SSNs are masked."""
    text = "Caller SSN is 123-45-6789 recorded during onboarding."
    redacted = redact_sensitive_text(text)
    assert "123-45-6789" not in redacted
    assert "[REDACTED_SSN]" in redacted


def test_redact_bearer_tokens():
    """Verify authorization Bearer tokens are masked."""
    text = "Header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
    redacted = redact_sensitive_text(text)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    assert "Bearer [REDACTED_TOKEN]" in redacted


def test_redact_passwords_and_api_keys():
    """Verify passwords and API keys are masked."""
    text1 = 'Received body: {"password": "SuperSecretPassword123!"}'
    assert "SuperSecretPassword123!" not in redact_sensitive_text(text1)
    assert "[REDACTED_PASSWORD]" in redact_sensitive_text(text1)

    text2 = 'Initialized client with api_key="gsk_12345678901234567890"'
    assert "gsk_12345678901234567890" not in redact_sensitive_text(text2)
    assert "[REDACTED_KEY]" in redact_sensitive_text(text2)


# =========================================================================
# 2. STRUCTURED JSON FORMATTER AND LOGGING TESTS
# =========================================================================

def test_json_formatter_fields():
    """Verify JSONFormatter produces valid JSON with required observability fields."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="callwise.agent.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Inbound call processed successfully",
        args=(),
        exc_info=None,
    )
    record.call_id = "test-call-uuid-123"
    record.business_id = "test-biz-uuid-456"
    record.latency_ms = 142.5

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["level"] == "INFO"
    assert data["logger"] == "callwise.agent.test"
    assert data["message"] == "Inbound call processed successfully"
    assert data["call_id"] == "test-call-uuid-123"
    assert data["business_id"] == "test-biz-uuid-456"
    assert data["latency_ms"] == 142.5
    assert "timestamp" in data


def test_redaction_filter_scrubs_record():
    """Verify RedactionFilter cleans record msg and args before output."""
    redaction_filter = RedactionFilter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.WARNING,
        pathname="test.py",
        lineno=20,
        msg="Attempted charge on 4532 1234 5678 9012",
        args=(),
        exc_info=None,
    )
    redaction_filter.filter(record)
    assert "4532 1234 5678 9012" not in record.msg
    assert "[REDACTED_CARD]" in record.msg


def test_setup_logging_initialization():
    """Verify setup_logging configures root logger without error."""
    setup_logging(log_format="json", log_level="DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) >= 1

    # Switch back to text format
    setup_logging(log_format="text", log_level="INFO")


# =========================================================================
# 3. PROMETHEUS METRICS REGISTRY TESTS
# =========================================================================

def test_metrics_registry_tracking():
    """Verify custom MetricsRegistry records and exports Prometheus format."""
    reg = MetricsRegistry()

    # Track calls
    reg.track_call(status="completed", session_type="phone", duration_seconds=45.2)
    reg.track_call(status="completed", session_type="chat", duration_seconds=12.0)
    reg.track_call(status="failed", session_type="phone")

    # Track LLM turns
    reg.track_llm_turn(provider="groq", status="success", latency_seconds=0.45)
    reg.track_llm_turn(provider="gemini", status="failure", latency_seconds=1.2)

    # Track abuse and rate limit
    reg.track_abuse_event("nonsense_repetition")
    reg.track_rate_limit("hourly_calls")
    reg.track_usage_cost(0.015)

    output = reg.render_prometheus()

    assert "# TYPE callwise_calls_total counter" in output
    assert 'callwise_calls_total{session_type="phone",status="completed"} 1.0' in output
    assert 'callwise_calls_total{session_type="chat",status="completed"} 1.0' in output
    assert 'callwise_calls_total{session_type="phone",status="failed"} 1.0' in output

    assert "# TYPE callwise_llm_turns_total counter" in output
    assert 'callwise_llm_turns_total{provider="groq",status="success"} 1.0' in output

    assert "# TYPE callwise_call_duration_seconds summary" in output
    assert 'callwise_circuit_breaker_state' in output
    assert 'callwise_usage_cost_usd_total' in output


@pytest.mark.asyncio
async def test_metrics_endpoint_scraping():
    """Verify /metrics and /api/metrics return 200 text/plain Prometheus output."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 200
        assert "text/plain" in res.headers["content-type"]
        assert "callwise_circuit_breaker_state" in res.text

        api_res = await client.get("/api/metrics")
        assert api_res.status_code == 200
        assert "callwise_circuit_breaker_state" in api_res.text


@pytest.mark.asyncio
async def test_metrics_disabled_returns_404(monkeypatch):
    """Verify /metrics returns 404 when enable_metrics is False."""
    monkeypatch.setattr(settings, "enable_metrics", False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/metrics")
        assert res.status_code == 404


# =========================================================================
# 4. CI WORKFLOW CONFIGURATION TESTS
# =========================================================================

def test_github_actions_ci_workflow():
    """Verify .github/workflows/ci.yml exists and has valid GitHub Actions YAML."""
    ci_path = Path(".github/workflows/ci.yml")
    assert ci_path.exists()

    content = ci_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)

    assert data["name"] == "Callwise CI"
    triggers = data.get("on") or data.get(True, {})
    assert "push" in triggers
    assert "pull_request" in triggers

    jobs = data.get("jobs", {})
    assert "backend-tests" in jobs
    assert "frontend-build" in jobs

    backend_steps = [s.get("name", "") for s in jobs["backend-tests"].get("steps", [])]
    assert any("Install Dependencies" in s for s in backend_steps)
    assert any("Run Database Migrations" in s for s in backend_steps)
    assert any("Execute Full Test Suite" in s for s in backend_steps)

    frontend_steps = [s.get("name", "") for s in jobs["frontend-build"].get("steps", [])]
    assert any("Install Frontend Dependencies" in s for s in frontend_steps)
    assert any("Build Next.js" in s for s in frontend_steps)
