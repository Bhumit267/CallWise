"""Basic tests to verify the project scaffold and settings."""

from callwise import __version__
from callwise.config import Settings
from callwise.cli import app
from typer.testing import CliRunner


def test_version_defined():
    """Verify package version is defined."""
    assert __version__ == "0.1.0"


def test_settings_defaults():
    """Verify default settings values."""
    settings = Settings()
    assert settings.llm_provider in ("groq", "gemini", "ollama")
    assert settings.tts_provider in ("deepgram", "cartesia")
    assert settings.stt_provider == "deepgram"
    assert settings.embedding_dimension == 384


def test_cli_version():
    """Verify CLI version command runs cleanly."""
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Callwise version: 0.1.0" in result.output
