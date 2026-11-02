"""Command Line Interface for Callwise using Typer."""

import json
from typing import Optional
import uuid
import typer
from sqlalchemy import select
from tabulate import tabulate

from callwise import __version__
from callwise.config import settings
from callwise.db.models import Business
from callwise.db.seed import run_seed
from callwise.db.session import get_sync_session

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
    typer.echo(
        f"Database URL: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'configured'}"
    )
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


@app.command("create-business")
def create_business(
    name: str = typer.Option(..., "--name", "-n", help="Business name"),
    business_type: str = typer.Option(..., "--type", "-t", help="Type of business (e.g. Dental Clinic)"),
    greeting: str = typer.Option(..., "--greeting", "-g", help="Spoken greeting for callers"),
    tone: str = typer.Option("Warm and professional", "--tone", help="Agent persona tone"),
    business_timezone: str = typer.Option("America/New_York", "--timezone", "-tz", help="IANA Timezone"),
    hours_json: Optional[str] = typer.Option(
        None,
        "--hours",
        help="JSON string or file path for weekly hours schedule",
    ),
):
    """Create a new business tenant record."""
    if hours_json:
        try:
            # Check if it is a filepath
            with open(hours_json, "r", encoding="utf-8") as f:
                hours = json.load(f)
        except (OSError, ValueError):
            try:
                hours = json.loads(hours_json)
            except json.JSONDecodeError as err:
                typer.secho(f"Error parsing hours JSON: {err}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
    else:
        # Default standard schedule: Mon-Fri 09:00 - 17:00, Sat-Sun closed
        hours = {
            "monday": {"open": "09:00", "close": "17:00", "closed": False},
            "tuesday": {"open": "09:00", "close": "17:00", "closed": False},
            "wednesday": {"open": "09:00", "close": "17:00", "closed": False},
            "thursday": {"open": "09:00", "close": "17:00", "closed": False},
            "friday": {"open": "09:00", "close": "17:00", "closed": False},
            "saturday": {"open": None, "close": None, "closed": True},
            "sunday": {"open": None, "close": None, "closed": True},
        }

    with get_sync_session() as session:
        business = Business(
            name=name,
            business_type=business_type,
            greeting=greeting,
            tone=tone,
            timezone=business_timezone,
            hours=hours,
        )
        session.add(business)
        session.flush()
        business_id = str(business.id)

    typer.secho(f"[OK] Successfully created business: {name}", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"ID: {business_id}")
    typer.echo(f"Type: {business_type}")
    typer.echo(f"Timezone: {business_timezone}")
    typer.echo(f"Greeting: {greeting}")


@app.command("seed")
def seed():
    """Seed demo businesses (Dental Clinic and Hair Salon) with fake data."""
    typer.echo("Seeding demo businesses into database...")
    businesses = run_seed()
    typer.secho(f"[OK] Seeded {len(businesses)} demo businesses:", fg=typer.colors.GREEN, bold=True)

    rows = []
    for b in businesses:
        rows.append([str(b.id), b.name, b.business_type, b.timezone, b.tone])

    typer.echo(tabulate(rows, headers=["ID", "Name", "Type", "Timezone", "Tone"], tablefmt="grid"))


@app.command("list-businesses")
def list_businesses():
    """List all registered business tenants."""
    with get_sync_session() as session:
        businesses = session.scalars(select(Business).order_by(Business.name)).all()

        if not businesses:
            typer.echo("No businesses found. Run 'callwise seed' to create demo businesses.")
            return

        rows = []
        for b in businesses:
            rows.append([str(b.id), b.name, b.business_type, b.timezone, b.tone])

        typer.echo(tabulate(rows, headers=["ID", "Name", "Type", "Timezone", "Tone"], tablefmt="grid"))


if __name__ == "__main__":
    app()
