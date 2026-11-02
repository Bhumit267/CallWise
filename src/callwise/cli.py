"""Command Line Interface for Callwise using Typer."""

from datetime import datetime, timezone
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

    async def _run_chat_loop():
        from callwise.agent.text_agent import TextAgent
        from callwise.calls.manager import end_call_async
        from callwise.db.models import Call
        from callwise.db.session import get_async_session

        call_id = uuid.uuid4()
        async with get_async_session() as session:
            call_obj = Call(
                id=call_id,
                business_id=biz_uuid,
                caller_number="console",
                llm_provider=provider or settings.llm_provider,
                llm_model=settings.groq_model,
            )
            session.add(call_obj)
            await session.commit()

        agent = TextAgent(business, call_id=call_id, provider_name=provider)
        typer.secho(f"\n=== Callwise Text Console: {business.name} ===", fg=typer.colors.CYAN, bold=True)
        typer.echo(f"Active Provider: {agent.provider_name.upper()}")
        typer.echo("Type 'exit', 'quit', or 'q' to end the session.\n")

        # Spoken initial greeting
        typer.secho(f"Receptionist: {business.greeting}", fg=typer.colors.GREEN, bold=True)

        while True:
            try:
                user_input = await asyncio.to_thread(input, "\nYou: ")
                user_input = user_input.strip()
            except (KeyboardInterrupt, EOFError):
                typer.secho("\n[Session Terminated]", fg=typer.colors.YELLOW)
                break

            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                typer.secho("\n[Call Ended]", fg=typer.colors.YELLOW)
                break

            response = await agent.ask(user_input)
            typer.secho(f"Receptionist: {response}", fg=typer.colors.GREEN)

        typer.echo("\nClosing call session and generating summary...")
        finished_call = await end_call_async(call_id, generate_summary=True)
        if finished_call and finished_call.summary:
            typer.secho(f"\n[Call Summary]: {finished_call.summary}", fg=typer.colors.CYAN, bold=True)
            turns_count = len(finished_call.turns) if finished_call and finished_call.turns else 0
            dur = finished_call.duration_seconds or 0.0
            typer.echo(f"Duration: {dur:.1f}s | Recorded Turns: {turns_count}\n")

    asyncio.run(_run_chat_loop())


@app.command("run-agent")
def cli_run_agent(
    business_id: str = typer.Option(..., "--business-id", "-b", help="Business tenant UUID"),
    mode: str = typer.Option(
        "dev",
        "--mode",
        "-m",
        help="Worker mode: 'dev' (connect to LiveKit Cloud / Playground) or 'console' (local mic/speaker)",
    ),
):
    """Launch the LiveKit voice agent worker for a business tenant."""
    try:
        biz_uuid = uuid.UUID(business_id)
    except ValueError:
        typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Starting LiveKit voice agent worker for business {business_id} in '{mode}' mode...")
    from callwise.agent.voice_agent import start_voice_worker
    start_voice_worker(biz_uuid, mode=mode)


@app.command("list-calls")
def cli_list_calls(
    business_id: Optional[str] = typer.Option(None, "--business-id", "-b", help="Filter by business UUID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max calls to return"),
):
    """List recent phone/chat calls, durations, and AI summaries."""
    with get_sync_session() as session:
        from callwise.db.models import Call
        stmt = select(Call).order_by(Call.started_at.desc()).limit(limit)
        if business_id:
            try:
                biz_uuid = uuid.UUID(business_id)
                stmt = stmt.where(Call.business_id == biz_uuid)
            except ValueError:
                typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        calls = session.scalars(stmt).all()
        if not calls:
            typer.echo("No calls recorded.")
            return

        rows = []
        for c in calls:
            biz_name = c.business.name if c.business else str(c.business_id)[:8]
            summary_snip = (
                (c.summary[:55] + "...")
                if c.summary and len(c.summary) > 55
                else (c.summary or "In-progress")
            )
            started_str = c.started_at.strftime("%Y-%m-%d %H:%M:%S") if c.started_at else "-"
            rows.append([
                str(c.id)[:8] + "...",
                biz_name[:20],
                c.caller_number or "unknown",
                started_str,
                f"{c.duration_seconds:.1f}s",
                len(c.turns),
                summary_snip,
            ])

        typer.echo(
            tabulate(
                rows,
                headers=["Call ID", "Business", "Caller", "Started At", "Duration", "Turns", "Summary"],
                tablefmt="grid",
            )
        )


@app.command("show-call")
def cli_show_call(
    call_id: str = typer.Option(..., "--call-id", "-c", help="Call UUID to inspect"),
):
    """Show turn-by-turn transcript, latencies, messages, and summary for a call."""
    try:
        c_uuid = uuid.UUID(call_id)
    except ValueError:
        typer.secho(f"Invalid call UUID: {call_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    with get_sync_session() as session:
        from callwise.db.models import Call
        call_obj = session.get(Call, c_uuid)
        if not call_obj:
            typer.secho(f"Call not found: {call_id}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        typer.secho(f"\n=== Call Details: {call_obj.id} ===", fg=typer.colors.CYAN, bold=True)
        typer.echo(f"Business: {call_obj.business.name if call_obj.business else call_obj.business_id}")
        typer.echo(f"Caller: {call_obj.caller_number or 'unknown'}")
        typer.echo(f"Started: {call_obj.started_at}")
        typer.echo(f"Ended: {call_obj.ended_at or 'In-progress'}")
        typer.echo(f"Duration: {call_obj.duration_seconds:.1f}s")
        typer.echo(f"LLM Provider: {call_obj.llm_provider or settings.llm_provider} ({call_obj.llm_model or settings.groq_model})")

        if call_obj.messages:
            typer.secho(f"\n--- Messages Taken ({len(call_obj.messages)}) ---", fg=typer.colors.YELLOW, bold=True)
            for m in call_obj.messages:
                typer.echo(f"- From {m.caller_name} ({m.callback_number}): \"{m.reason}\"")

        if call_obj.knowledge_misses:
            typer.secho(f"\n--- Knowledge Misses ({len(call_obj.knowledge_misses)}) ---", fg=typer.colors.MAGENTA, bold=True)
            for km in call_obj.knowledge_misses:
                typer.echo(f"- Query: \"{km.query}\"")

        typer.secho("\n--- Transcript ---", fg=typer.colors.BLUE, bold=True)
        if not call_obj.turns:
            typer.echo("No dialogue turns recorded.")
        else:
            for t in sorted(call_obj.turns, key=lambda x: x.timestamp):
                spk = "CALLER" if t.speaker == "caller" else "AGENT "
                color = typer.colors.WHITE if t.speaker == "caller" else typer.colors.GREEN
                latency_str = f" [{t.latency_ms:.0f}ms]" if t.latency_ms is not None else ""
                t_str = t.timestamp.strftime("%H:%M:%S")
                typer.secho(f"[{t_str}] {spk}{latency_str}: {t.text}", fg=color)

        typer.secho("\n--- AI Executive Summary ---", fg=typer.colors.GREEN, bold=True)
        typer.echo(call_obj.summary or "No summary generated.")
        typer.echo("")


@app.command("list-messages")
def cli_list_messages(
    business_id: Optional[str] = typer.Option(None, "--business-id", "-b", help="Filter by business UUID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max messages to return"),
):
    """List callback messages taken by the AI receptionist."""
    with get_sync_session() as session:
        from callwise.db.models import Message
        stmt = select(Message).order_by(Message.created_at.desc()).limit(limit)
        if business_id:
            try:
                biz_uuid = uuid.UUID(business_id)
                stmt = stmt.where(Message.business_id == biz_uuid)
            except ValueError:
                typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        msgs = session.scalars(stmt).all()
        if not msgs:
            typer.echo("No messages found.")
            return

        rows = []
        for m in msgs:
            biz_name = m.business.name if m.business else str(m.business_id)[:8]
            created_str = m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else "-"
            rows.append([
                str(m.id)[:8] + "...",
                biz_name[:20],
                m.caller_name,
                m.callback_number,
                m.reason[:40] + ("..." if len(m.reason) > 40 else ""),
                str(m.call_id)[:8] + "..." if m.call_id else "-",
                created_str,
            ])

        typer.echo(
            tabulate(
                rows,
                headers=["ID", "Business", "Caller", "Phone", "Reason", "Call ID", "Created At"],
                tablefmt="grid",
            )
        )


@app.command("list-misses")
def cli_list_misses(
    business_id: Optional[str] = typer.Option(None, "--business-id", "-b", help="Filter by business UUID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max misses to return"),
):
    """List queries where knowledge retrieval was below similarity cutoff."""
    with get_sync_session() as session:
        from callwise.db.models import KnowledgeMiss
        stmt = select(KnowledgeMiss).order_by(KnowledgeMiss.created_at.desc()).limit(limit)
        if business_id:
            try:
                biz_uuid = uuid.UUID(business_id)
                stmt = stmt.where(KnowledgeMiss.business_id == biz_uuid)
            except ValueError:
                typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
                raise typer.Exit(code=1)

        misses = session.scalars(stmt).all()
        if not misses:
            typer.echo("No knowledge misses recorded.")
            return

        rows = []
        for km in misses:
            biz_name = km.business.name if km.business else str(km.business_id)[:8]
            created_str = km.created_at.strftime("%Y-%m-%d %H:%M:%S") if km.created_at else "-"
            rows.append([
                str(km.id)[:8] + "...",
                biz_name[:20],
                km.query[:60] + ("..." if len(km.query) > 60 else ""),
                str(km.call_id)[:8] + "..." if km.call_id else "-",
                created_str,
            ])

        typer.echo(
            tabulate(
                rows,
                headers=["ID", "Business", "Query", "Call ID", "Recorded At"],
                tablefmt="grid",
            )
        )


@app.command("run-evals")
def cli_run_evals(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider (groq or gemini)"),
    business_id: Optional[str] = typer.Option(None, "--business-id", "-b", help="Filter evals by business UUID"),
    no_save: bool = typer.Option(False, "--no-save", help="Do not save report to evals/reports/"),
):
    """Run evaluation benchmarks across answerable, unanswerable, and prohibited questions."""
    biz_uuid = None
    if business_id:
        try:
            biz_uuid = uuid.UUID(business_id)
        except ValueError:
            typer.secho(f"Invalid business UUID: {business_id}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    typer.echo("Starting Callwise evaluation benchmarks...")
    from evals.eval_runner import format_report_console, run_evaluations, save_report

    try:
        report = run_evaluations(
            provider_name=provider,
            business_id=biz_uuid,
            save_output=not no_save,
        )
        report_output = format_report_console(report)
        typer.echo(report_output)

        if not no_save:
            typer.secho(
                f"\n[OK] Reports saved to evals/reports/ (JSON & Markdown)",
                fg=typer.colors.GREEN,
            )
    except Exception as exc:
        typer.secho(f"Evaluation run failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

