"""Command Line Interface for Callwise using Typer."""

import typer
from callwise import __version__
from callwise.config import settings

app = typer.Typer(
    name="callwise",
    help="Callwise: Multi-tenant Voice AI Receptionist CLI.",
    no_args_is_help=True,
)


@app.command()
def version():
    """Print Callwise version and active configuration."""
    typer.echo(f"Callwise version: {__version__}")
    typer.echo(f"LLM Provider: {settings.llm_provider}")
    typer.echo(f"TTS Provider: {settings.tts_provider}")
    typer.echo(f"STT Provider: {settings.stt_provider}")


@app.command()
def info():
    """Display current system settings and provider configurations."""
    typer.echo("=== Callwise System Settings ===")
    typer.echo(f"Database URL: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'configured'}")
    typer.echo(f"LLM Provider: {settings.llm_provider}")
    if settings.llm_provider == "groq":
        typer.echo(f"  Model: {settings.groq_model}")
        typer.echo(f"  API Key: {'Set' if settings.groq_api_key else 'Missing'}")
    elif settings.llm_provider == "gemini":
        typer.echo(f"  Model: {settings.gemini_model}")
        typer.echo(f"  API Key: {'Set' if settings.gemini_api_key else 'Missing'}")
    elif settings.llm_provider == "ollama":
        typer.echo(f"  Model: {settings.ollama_model}")
        typer.echo(f"  Base URL: {settings.ollama_base_url}")
    typer.echo(f"TTS Provider: {settings.tts_provider}")
    typer.echo(f"STT Provider: {settings.stt_provider}")
    typer.echo(f"Embedding Model: {settings.embedding_model_name} (Dim: {settings.embedding_dimension})")


if __name__ == "__main__":
    app()
