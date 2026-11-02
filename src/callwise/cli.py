"""Command Line Interface for Callwise using Typer."""

from datetime import datetime
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


@app.command("ingest-file")
def cli_ingest_file(
    business_id: str = typer.Option(..., "--business-id", "-b", help="Target business tenant UUID"),
    file_path: str = typer.Option(..., "--file", "-f", help="Path to PDF, TXT, or Markdown file"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Custom document title"),
):
    """Ingest a local document (PDF/TXT/MD) into the business knowledge base."""
    try:
        biz_uuid = uuid.UUID(business_id)
    except ValueError:
        typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Ingesting file '{file_path}'...")
    try:
        from callwise.knowledge.ingest import ingest_file
        doc = ingest_file(biz_uuid, file_path, title=title)
        typer.secho(f"[OK] Ingested document: {doc.title}", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"Document ID: {doc.id}")
        typer.echo(f"Source: {doc.source_uri}")
    except Exception as err:
        typer.secho(f"Ingestion failed: {err}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("ingest-url")
def cli_ingest_url(
    business_id: str = typer.Option(..., "--business-id", "-b", help="Target business tenant UUID"),
    url: str = typer.Option(..., "--url", "-u", help="Public http(s) URL to scrape"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Custom document title"),
):
    """Ingest a public web page into the business knowledge base (SSRF protected)."""
    try:
        biz_uuid = uuid.UUID(business_id)
    except ValueError:
        typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Fetching and ingesting URL: {url}...")
    try:
        from callwise.knowledge.ingest import ingest_url
        doc = ingest_url(biz_uuid, url, title=title)
        typer.secho(f"[OK] Ingested document: {doc.title}", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"Document ID: {doc.id}")
        typer.echo(f"Source: {doc.source_uri}")
    except Exception as err:
        typer.secho(f"Ingestion failed: {err}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("list-documents")
def cli_list_documents(
    business_id: str = typer.Option(..., "--business-id", "-b", help="Business tenant UUID"),
):
    """List all ingested documents for a business tenant."""
    try:
        biz_uuid = uuid.UUID(business_id)
    except ValueError:
        typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    with get_sync_session() as session:
        from callwise.db.models import Document
        docs = session.scalars(
            select(Document).where(Document.business_id == biz_uuid).order_by(Document.created_at)
        ).all()

        if not docs:
            typer.echo(f"No documents found for business '{business_id}'.")
            return

        rows = []
        for d in docs:
            chunk_count = len(d.chunks)
            rows.append([str(d.id), d.title, d.source_type, chunk_count, d.source_uri[:40]])

        typer.echo(
            tabulate(
                rows,
                headers=["ID", "Title", "Type", "Chunks", "Source"],
                tablefmt="grid",
            )
        )


@app.command("search-knowledge")
def cli_search_knowledge(
    business_id: str = typer.Option(..., "--business-id", "-b", help="Business tenant UUID"),
    query: str = typer.Option(..., "--query", "-q", help="Search question or keyword"),
    threshold: Optional[float] = typer.Option(None, "--threshold", help="Custom similarity threshold cutoff"),
    top_k: int = typer.Option(3, "--top-k", "-k", help="Maximum number of matches"),
):
    """Search tenant knowledge base and display matches or explicit NO_MATCH."""
    try:
        biz_uuid = uuid.UUID(business_id)
    except ValueError:
        typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Searching knowledge for business {business_id}...")
    typer.echo(f"Query: \"{query}\"")

    from callwise.knowledge.search import search_knowledge
    result = search_knowledge(
        business_id=biz_uuid,
        query=query,
        threshold=threshold,
        top_k=top_k,
    )

    if not result.is_match:
        typer.secho(f"[NO MATCH] {result.message}", fg=typer.colors.YELLOW, bold=True)
        if result.top_score > 0:
            typer.echo(f"Top candidate score was: {result.top_score:.4f}")
        return

    typer.secho(
        f"[MATCH FOUND] {len(result.matches)} chunk(s) matched (Top score: {result.top_score:.4f}):",
        fg=typer.colors.GREEN,
        bold=True,
    )

    rows = []
    for m in result.matches:
        snippet = m.content[:90] + ("..." if len(m.content) > 90 else "")
        rows.append([f"{m.similarity:.4f}", m.source_title, snippet])

    typer.echo(
        tabulate(
            rows,
            headers=["Similarity", "Source Title", "Content Snippet"],
            tablefmt="grid",
        )
    )


@app.command("check-hours")
def cli_check_hours(
    business_id: str = typer.Option(..., "--business-id", "-b", help="Business tenant UUID"),
    at_timestamp: Optional[str] = typer.Option(None, "--at", help="Optional ISO datetime to test (e.g. 2026-11-02T14:30:00Z)"),
):
    """Check whether a business is currently open or closed with timezone awareness."""
    try:
        biz_uuid = uuid.UUID(business_id)
    except ValueError:
        typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    at_dt = None
    if at_timestamp:
        try:
            at_dt = datetime.fromisoformat(at_timestamp.replace("Z", "+00:00"))
        except ValueError as err:
            typer.secho(f"Invalid timestamp format: {err}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    with get_sync_session() as session:
        business = session.get(Business, biz_uuid)
        if not business:
            typer.secho(f"Business not found: {business_id}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        from callwise.agent.hours import get_business_hours_status
        status = get_business_hours_status(business, at_time=at_dt)

    typer.secho(f"=== {business.name} Business Hours ===", bold=True)
    if status.is_open:
        typer.secho(f"Status: [OPEN NOW]", fg=typer.colors.GREEN, bold=True)
    else:
        typer.secho(f"Status: [CLOSED]", fg=typer.colors.YELLOW, bold=True)

    typer.echo(f"Local Time: {status.current_time_local}")
    typer.echo(f"Today ({status.day_of_week}): {status.today_schedule}")
    if status.next_open_time:
        typer.echo(f"Next Open: {status.next_open_time}")
    typer.echo(f"Spoken Answer: \"{status.spoken_summary}\"")
    typer.echo(f"\nWeekly Schedule:\n{status.weekly_schedule_summary}")

@app.command("chat")
def cli_chat(
    business_id: str = typer.Option(..., "--business-id", "-b", help="Business tenant UUID"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM Provider: groq, gemini, or ollama"),
):
    """Start an interactive console text chat with the receptionist (no audio required)."""
    try:
        biz_uuid = uuid.UUID(business_id)
    except ValueError:
        typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    with get_sync_session() as session:
        business = session.get(Business, biz_uuid)
        if not business:
            typer.secho(f"Business not found: {business_id}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    import asyncio
    from callwise.agent.text_agent import TextAgent

    agent = TextAgent(business, provider_name=provider)
    typer.secho(f"\n=== Callwise Text Console: {business.name} ===", fg=typer.colors.CYAN, bold=True)
    typer.echo(f"Active Provider: {agent.provider_name.upper()}")
    typer.echo("Type 'exit', 'quit', or 'q' to end the session.\n")

    # Spoken initial greeting
    typer.secho(f"Receptionist: {business.greeting}", fg=typer.colors.GREEN, bold=True)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            typer.secho("\n[Session Terminated]", fg=typer.colors.YELLOW)
            break

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit", "q"]:
            typer.secho("\n[Call Ended]", fg=typer.colors.YELLOW)
            break

        response = asyncio.run(agent.ask(user_input))
        typer.secho(f"Receptionist: {response}", fg=typer.colors.GREEN)


@app.command("run-agent")
def cli_run_agent(
    business_id: str = typer.Option(..., "--business-id", "-b", help="Business tenant UUID"),
):
    """Launch the LiveKit voice agent worker for a business tenant."""
    try:
        biz_uuid = uuid.UUID(business_id)
    except ValueError:
        typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Starting LiveKit voice agent worker for business {business_id}...")
    from callwise.agent.voice_agent import start_voice_worker
    start_voice_worker(biz_uuid)


if __name__ == "__main__":
    app()

