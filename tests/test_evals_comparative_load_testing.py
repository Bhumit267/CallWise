"""Tests for multi-provider comparative evaluations and concurrency load testing."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from callwise.api.main import app
from evals.eval_runner import (
    CategoryStats,
    ComparativeReport,
    EvalReport,
    EvalResult,
    format_comparative_report_console,
    run_comparative_evaluations_async,
    save_comparative_report,
)
from scripts.load_test import LoadTestResult, run_load_test


# =========================================================================
# 1. COMPARATIVE EVALUATION TESTS
# =========================================================================

def _create_mock_eval_report(provider: str, accuracy: float, latency: float, hallucinations: int = 0) -> EvalReport:
    """Helper to generate a mock EvalReport for testing."""
    return EvalReport(
        timestamp="2026-11-07T12:00:00Z",
        provider=provider.upper(),
        model=f"model-{provider}",
        total_questions=10,
        passed_questions=int(10 * (accuracy / 100.0)),
        failed_questions=10 - int(10 * (accuracy / 100.0)),
        overall_accuracy_pct=accuracy,
        total_hallucinations=hallucinations,
        avg_latency_ms=latency,
        category_breakdown={
            "answerable": CategoryStats(total=4, passed=4, accuracy_pct=100.0, avg_latency_ms=latency),
            "unanswerable": CategoryStats(total=3, passed=3, accuracy_pct=100.0, avg_latency_ms=latency),
            "prohibited": CategoryStats(total=3, passed=3, accuracy_pct=100.0, avg_latency_ms=latency),
        },
        business_breakdown={},
        results=[
            EvalResult(
                question_id="Q1",
                question_text="What are your hours?",
                category="answerable",
                business_name="Apex Dental",
                response_text="We are open 8am to 5pm.",
                passed=True,
                is_hallucination=False,
                latency_ms=latency,
            )
        ],
    )


@pytest.mark.asyncio
async def test_run_comparative_evaluations_structure():
    """Verify comparative evaluation generates side-by-side comparison across providers."""
    mock_groq = _create_mock_eval_report(provider="groq", accuracy=95.0, latency=420.0, hallucinations=0)
    mock_gemini = _create_mock_eval_report(provider="gemini", accuracy=90.0, latency=610.0, hallucinations=0)

    async def mock_run_eval(provider_name: str, **kwargs):
        if provider_name == "groq":
            return mock_groq
        return mock_gemini

    with patch("evals.eval_runner.run_evaluations_async", side_effect=mock_run_eval):
        comp = await run_comparative_evaluations_async(providers=["groq", "gemini"])

        assert isinstance(comp, ComparativeReport)
        assert comp.providers == ["GROQ", "GEMINI"]
        assert comp.winner_accuracy == "GROQ"
        assert comp.winner_latency == "GROQ"
        assert len(comp.comparison_table) >= 5

        # Format console test
        table_output = format_comparative_report_console(comp)
        assert "Callwise Multi-Provider Comparative Benchmark Evaluation" in table_output
        assert "GROQ" in table_output
        assert "GEMINI" in table_output
        assert "Overall Accuracy" in table_output


def test_save_comparative_report(tmp_path, monkeypatch):
    """Verify comparative report is saved in both JSON and Markdown formats."""
    monkeypatch.setattr("evals.eval_runner.REPORTS_DIR", tmp_path)

    mock_groq = _create_mock_eval_report(provider="groq", accuracy=95.0, latency=400.0)
    mock_gemini = _create_mock_eval_report(provider="gemini", accuracy=92.0, latency=550.0)

    comp_report = ComparativeReport(
        timestamp="2026-11-07T12:00:00Z",
        providers=["GROQ", "GEMINI"],
        reports={"groq": mock_groq, "gemini": mock_gemini},
        comparison_table=[
            {"Metric": "Overall Accuracy (%)", "GROQ": "95.0%", "GEMINI": "92.0%"},
            {"Metric": "Average Turn Latency", "GROQ": "400.0 ms", "GEMINI": "550.0 ms"},
        ],
        winner_accuracy="GROQ",
        winner_latency="GROQ",
    )

    json_saved = save_comparative_report(comp_report, filename_prefix="test_comparative")
    assert json_saved.exists()
    assert json_saved.suffix == ".json"

    # Verify JSON content
    with open(json_saved, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["winner_accuracy"] == "GROQ"
        assert "GROQ" in data["providers"]
        assert "GEMINI" in data["providers"]

    # Verify corresponding Markdown file exists
    md_saved = json_saved.with_suffix(".md")
    assert md_saved.exists()
    md_content = md_saved.read_text(encoding="utf-8")
    assert "# Callwise Multi-Provider Comparative Benchmark Report" in md_content
    assert "Side-by-Side Performance Comparison" in md_content
    assert "| Overall Accuracy (%) |" in md_content


# =========================================================================
# 2. LOAD AND CONCURRENCY TESTING TESTS
# =========================================================================

def test_load_test_result_percentiles():
    """Verify statistical percentile calculations on LoadTestResult."""
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    result = LoadTestResult(
        target_url="http://test/health",
        total_requests=10,
        concurrency=2,
        duration_seconds=1.0,
        latencies_ms=latencies,
        status_counts={200: 10},
        error_count=0,
        rate_limited_count=0,
    )

    assert result.min_latency == 10.0
    assert result.max_latency == 100.0
    assert result.mean_latency == 55.0
    assert result.median_latency == 50.0
    assert result.p95_latency == 100.0
    assert result.rps == 10.0

    dict_repr = result.to_dict()
    assert dict_repr["requests_per_second"] == 10.0
    assert dict_repr["latency_ms"]["median_p50"] == 50.0

    console_out = result.format_console()
    assert "CALLWISE LOAD & CONCURRENCY TEST RESULTS" in console_out
    assert "Throughput (RPS)" in console_out


@pytest.mark.asyncio
async def test_run_load_test_execution():
    """Verify run_load_test performs concurrent requests through ASGI client transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await run_load_test(
            url="http://test/api/health",
            total_requests=15,
            concurrency=3,
            method="GET",
            client=client,
        )

        assert res.total_requests == 15
        assert res.concurrency == 3
        assert len(res.latencies_ms) == 15
        assert res.duration_seconds > 0
        assert res.rps > 0
        assert res.status_counts.get(200) == 15
        assert res.error_count == 0
        assert res.rate_limited_count == 0


def test_cli_load_test_runner():
    """Verify load-test CLI command executes with mock."""
    from typer.testing import CliRunner
    from callwise.cli import app as cli_app

    runner = CliRunner()
    mock_res = LoadTestResult(
        target_url="http://localhost:8000/api/health",
        total_requests=5,
        concurrency=1,
        duration_seconds=0.1,
        latencies_ms=[10.0, 12.0, 15.0, 11.0, 14.0],
        status_counts={200: 5},
        error_count=0,
        rate_limited_count=0,
    )

    with patch("scripts.load_test.run_load_test", AsyncMock(return_value=mock_res)):
        res = runner.invoke(cli_app, ["load-test", "--requests", "5", "--concurrency", "1"])
        assert res.exit_code == 0
        assert "CALLWISE LOAD & CONCURRENCY TEST RESULTS" in res.output
        assert "Throughput (RPS)" in res.output

