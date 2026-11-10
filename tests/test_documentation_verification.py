"""Automated documentation verification for README.md, DEMO.md, SCREENSHOTS.md, and SECURITY.md."""

from pathlib import Path
import pytest


def test_readme_documentation_completeness():
    """Verify README.md covers all 4 phases, architecture, setup, docker, and CLI reference."""
    readme_path = Path("README.md")
    assert readme_path.exists()
    content = readme_path.read_text(encoding="utf-8")

    # Architecture & System diagram
    assert "System Architecture" in content
    assert "mermaid" in content
    assert "InboundRouter" in content

    # Phases 1 through 4
    assert "Phase 1: Foundations" in content
    assert "Phase 2: Booking, Verification & Live Transfer" in content
    assert "Phase 3: Web Dashboard" in content
    assert "Phase 4: Production Telephony, Chat Widget" in content

    # Quickstart and Docker setup
    assert "Quickstart & Setup Guide" in content
    assert "docker compose -f docker-compose.prod.yml up" in content
    assert "bhumit@gmail.com" in content

    # CLI Command reference
    assert "callwise doctor" in content
    assert "callwise run-evals" in content
    assert "callwise load-test" in content
    assert "callwise killswitch" in content
    assert "callwise db backup" in content

    # Documentation links
    assert "DEMO.md" in content
    assert "SCREENSHOTS.md" in content
    assert "SECURITY.md" in content


def test_demo_walkthrough_guide_completeness():
    """Verify DEMO.md contains login credentials, softphone setup, curl commands, and transcripts."""
    demo_path = Path("DEMO.md")
    assert demo_path.exists()
    content = demo_path.read_text(encoding="utf-8")

    # Login credentials
    assert "bhumit@gmail.com" in content
    assert "Password123!" in content

    # Dashboard and softphone guides
    assert "Dashboard Overview" in content
    assert "Calls & Transcripts" in content
    assert "Linphone" in content or "Zoiper" in content
    assert "widget.js" in content

    # Live curl API commands
    assert "curl -i http://localhost:8000/health" in content
    assert "curl -i http://localhost:8000/metrics" in content
    assert "/api/widget/chat" in content

    # Sample transcripts
    assert "Scenario 1: Factual Knowledge Retrieval" in content
    assert "Scenario 2: Booking an Appointment" in content
    assert "Scenario 3: Appointment Cancellation" in content
    assert "Scenario 4: Live Human Transfer" in content
    assert "Scenario 5: Abuse & Flood Protection" in content
    assert "Scenario 6: Emergency Kill Switch" in content


def test_screenshots_checklist_completeness():
    """Verify SCREENSHOTS.md lists all dashboard screens and widgets."""
    screenshots_path = Path("SCREENSHOTS.md")
    assert screenshots_path.exists()
    content = screenshots_path.read_text(encoding="utf-8")

    # Key dashboard screens
    assert "/login" in content
    assert "/calls" in content
    assert "/calendar" in content
    assert "/inbox" in content
    assert "/knowledge" in content
    assert "/phone-numbers" in content
    assert "/widget" in content
    assert "/usage" in content
    assert "/team" in content
    assert "/audit-logs" in content
    assert "/settings" in content
    assert "/widget-frame/[key]" in content


def test_security_checklist_completeness():
    """Verify SECURITY.md details threat modeling and defense controls."""
    sec_path = Path("SECURITY.md")
    assert sec_path.exists()
    content = sec_path.read_text(encoding="utf-8")

    # Threat matrix and core defenses
    assert "Multi-Tenant Isolation" in content
    assert "Row Level Security (RLS)" in content
    assert "Argon2id" in content
    assert "Cross-Site Request Forgery (CSRF)" in content
    assert "Prompt Injection" in content
    assert "Server-Side Request Forgery (SSRF)" in content
    assert "PII Redaction" in content
    assert "Emergency Kill Switch" in content
    assert "Circuit Breaker" in content

