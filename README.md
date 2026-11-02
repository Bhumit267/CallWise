# Callwise 📞🤖

Callwise is a multi-tenant voice AI receptionist for businesses. All business-specific knowledge, greetings, operational hours, and configurations are driven strictly from the database rather than hardcoded in the codebase.

## Key Features (Phase 1)
- **Multi-Tenant from Day One**: Every table references a `business_id`; all queries are scoped by business.
- **Dynamic System Prompts**: Generic engine whose personality, greeting, hours, tone, and policies are populated from database rows.
- **Strict Hallucination Prevention**: If knowledge search yields no relevant match, the receptionist gracefully declines, offers to take a message, and logs the query to `knowledge_misses`.
- **Interchangeable Providers**:
  - **LLM**: Groq (default, Llama 3.3 70B), Gemini Flash, or local Ollama behind a common `LLMProvider` interface with exponential backoff on 429 rate limits.
  - **STT**: Deepgram Nova-2.
  - **TTS**: Deepgram Aura or Cartesia behind a common `TTSProvider` interface.
  - **VAD**: Silero.
  - **Embeddings**: Local sentence-transformers (`all-MiniLM-L6-v2`) behind an `EmbeddingProvider` interface.
  - **Real-time Voice Pipeline**: LiveKit Agents Python framework with WebRTC and text-eval fallback mode.
  - **Database**: PostgreSQL with `pgvector` extension via Docker Compose.

---

## Project Structure

```text
callwise/
  docker-compose.yml        (PostgreSQL + pgvector container)
  .env.example              (Environment variable template)
  README.md                 (Setup and usage guide)
  pyproject.toml            (Project dependencies and packaging metadata)
  alembic/                  (Database migration scripts)
  src/callwise/
    config.py               (Settings loaded from environment variables)
    db/                     (SQLAlchemy models and async/sync session management)
    providers/              (LLM, TTS, and Embedding provider interfaces & adapters)
    knowledge/              (Document loaders, chunker, vector ingest, and search)
    agent/                  (Voice agent system prompt builder, tools, hours logic, worker)
    calls/                  (Transcript recording, LLM call summary, and latency metrics)
    cli.py                  (Typer-based command line interface)
  tests/                    (Pytest test suite)
  evals/                    (Q&A evaluation test suites for demo businesses)
```

---

## Setup Instructions

### 1. Prerequisites
- **Python 3.11+** installed
- **uv** (recommended) or `pip` + `venv`
  - To install `uv`: `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Docker** and **Docker Compose** installed and running

### 2. Configure Environment Variables
Copy the sample environment file to `.env`:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in your API credentials:
- `GROQ_API_KEY` (Free API key from [Groq Console](https://console.groq.com/))
- `DEEPGRAM_API_KEY` (Free tier from [Deepgram Console](https://console.deepgram.com/))
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (Free Cloud Project from [LiveKit Cloud](https://cloud.livekit.io/))
- Optional: `GEMINI_API_KEY`, `CARTESIA_API_KEY`

### 3. Start PostgreSQL with pgvector
Start the PostgreSQL container with `pgvector` enabled:

```bash
docker compose up -d
```

Verify that the container is healthy:
```bash
docker compose ps
```

### 4. Install Dependencies
Using `uv`:
```bash
uv sync
```
Or with standard pip inside a virtual environment:
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"
```

### 5. Run the Test Suite
Run the test suite using pytest:
```bash
uv run pytest
```

### 6. Explore the CLI & Run E2E Workflows
Verify the installation and test the full feature set using the Typer CLI:

```bash
# Show available commands
uv run callwise --help

# View active system settings and providers
uv run callwise info

# 1. Seed demo businesses (Dental Clinic and Hair Salon)
uv run callwise seed
uv run callwise list-businesses

# 2. Ingest business knowledge documents & partner URLs
uv run callwise ingest-file --business-id 11111111-1111-1111-1111-111111111111 --file evals/data/dental_knowledge.md --title "Dental Clinic Knowledge Base"
uv run callwise ingest-file --business-id 22222222-2222-2222-2222-222222222222 --file evals/data/salon_knowledge.md --title "Salon & Spa Knowledge Base"
uv run callwise list-documents --business-id 11111111-1111-1111-1111-111111111111

# 3. Test knowledge retrieval & anti-hallucination logging
uv run callwise search-knowledge --business-id 11111111-1111-1111-1111-111111111111 --query "How much is teeth whitening?"
uv run callwise search-knowledge --business-id 11111111-1111-1111-1111-111111111111 --query "Do you fix submarine carburetors?"
uv run callwise list-misses --business-id 11111111-1111-1111-1111-111111111111

# 4. Check timezone-aware operational hours
uv run callwise check-hours --business-id 11111111-1111-1111-1111-111111111111
uv run callwise check-hours --business-id 22222222-2222-2222-2222-222222222222

# 5. Interactive text console chat (no audio required)
uv run callwise chat --business-id 11111111-1111-1111-1111-111111111111

# 6. Inspect calls, turn-by-turn transcripts, latencies, and summaries
uv run callwise list-calls
uv run callwise show-call --call-id <CALL_ID>
uv run callwise list-messages

# 7. Run automated benchmark evaluations (20 test questions)
uv run callwise run-evals

# 8. Run LiveKit voice agent worker (for live phone/WebRTC calls)
uv run callwise run-agent --business-id 11111111-1111-1111-1111-111111111111
```
