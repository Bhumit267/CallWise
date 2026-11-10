import pytest
from unittest.mock import patch
from callwise.config import Settings
from callwise.api.main import create_app


def test_production_environment_rejects_default_secret_key():
    """Verify production startup fails if SECRET_KEY is left at default dev value."""
    with patch("callwise.api.main.settings", Settings(environment="production", secret_key="callwise-dev-secret-key-change-in-prod-min32bytes!")):
        with pytest.raises(ValueError, match="CRITICAL SECURITY CONFIGURATION ERROR"):
            create_app()


def test_production_environment_accepts_secure_secret_key():
    """Verify production startup succeeds when a strong secret key is provided."""
    secure_key = "a" * 64
    with patch("callwise.api.main.settings", Settings(environment="production", secret_key=secure_key)):
        app = create_app()
        assert app is not None


def test_development_environment_allows_default_secret_key():
    """Verify development environment starts without error on default dev key."""
    with patch("callwise.api.main.settings", Settings(environment="development")):
        app = create_app()
        assert app is not None

