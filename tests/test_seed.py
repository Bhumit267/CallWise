"""Unit and integration tests for demo business seed data and CLI commands."""

import pytest
from typer.testing import CliRunner

from callwise.cli import app
from callwise.db.models import Business
from callwise.db.seed import DENTAL_CLINIC_ID, SALON_SPA_ID, run_seed
from callwise.db.session import get_sync_session


def test_seed_creates_demo_businesses():
    """Verify seed function inserts the dental clinic and hair salon."""
    businesses = run_seed()
    assert len(businesses) == 2

    with get_sync_session() as session:
        dental = session.get(Business, DENTAL_CLINIC_ID)
        assert dental is not None
        assert dental.name == "BrightSmile Family Dental"
        assert dental.business_type == "Dental Clinic"
        assert dental.timezone == "America/New_York"
        assert dental.hours["monday"]["open"] == "08:00"
        assert dental.hours["sunday"]["closed"] is True

        salon = session.get(Business, SALON_SPA_ID)
        assert salon is not None
        assert salon.name == "Luxe Glow Salon & Spa"
        assert salon.business_type == "Hair Salon & Spa"
        assert salon.timezone == "America/Los_Angeles"
        assert salon.hours["tuesday"]["open"] == "10:00"
        assert salon.hours["monday"]["closed"] is True


def test_seed_is_idempotent():
    """Verify running seed multiple times does not produce duplicates."""
    run_seed()
    run_seed()

    with get_sync_session() as session:
        dental = session.get(Business, DENTAL_CLINIC_ID)
        salon = session.get(Business, SALON_SPA_ID)
        assert dental is not None
        assert salon is not None


def test_cli_seed_and_list():
    """Verify CLI commands for seeding and listing businesses."""
    runner = CliRunner()
    seed_result = runner.invoke(app, ["seed"])
    assert seed_result.exit_code == 0
    assert "[OK] Seeded 2 demo businesses" in seed_result.output

    list_result = runner.invoke(app, ["list-businesses"])
    assert list_result.exit_code == 0
    assert "BrightSmile Family Dental" in list_result.output
    assert "Luxe Glow Salon & Spa" in list_result.output
