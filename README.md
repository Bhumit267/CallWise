# Callwise 📞🤖

Callwise is an enterprise-grade, multi-tenant voice and chat AI receptionist platform designed for local service businesses (dental clinics, salons, spas, repair shops, and professional offices).

All tenant configuration—including knowledge documents, operating hours, service menus, pricing, cancellation policies, telephone routing, chat widget customization, and notification alerts—is driven dynamically from PostgreSQL with kernel-level Row Level Security (RLS) tenant isolation.

---

## System Architecture

```mermaid
flowchart TD
    InboundCaller([Caller: Phone or WebRTC]) --> SIP[LiveKit SIP Telephony / Router]
    WebVisitor([Visitor: Web Chat Widget]) --> WidgetAPI[Chat Widget Endpoint / Router]

    subgraph Ingress & Protection
        SIP --> InboundRouter[Inbound Router: Blocklist, Rate Limit, Kill Switch]
        WidgetAPI --> InboundRouter
        InboundRouter --> KillSwitch{Kill Switch Active?}
        KillSwitch -- Yes --> FallbackMsg[Fallback Message-Taking Prompt]
        KillSwitch -- No --> AgentCore[Text & Voice Agent Core]
    end

    subgraph Agent Core & Subsystems
        AgentCore --> CircuitBreaker[Circuit Breaker: Groq Primary / Gemini Secondary]
        AgentCore --> VAD[Silero VAD: Silence Detection]
        AgentCore --> Tools[CallwiseToolset: 9 Dynamic Tools]
        Tools --> Hours[Operating Hours Engine: Timezone Aware]
        Tools --> KB[Knowledge Engine: pgvector Vector Search]
        Tools --> Booking[Booking Engine: Race-Condition Safe]
        Tools --> Transfer[Live Human Transfer Engine: Hours Gated]
    end

    subgraph Multi-Tenant Database
        Booking --> DB[(PostgreSQL 16 + pgvector)]
        Hours --> DB
        KB --> DB
        RLS[PostgreSQL Row Level Security Policies] --> DB
    end

    subgraph Background Daemons & Web Stack
        Reminders[Reminder Daemon: 24h Email & 2h Voice Call] --> DB
        Worker[Ingestion Worker: Async Audio & Docs] --> DB
        Dashboard[Next.js 14 Dashboard: Cookie Auth & RBAC] --> DB
        Caddy[Caddy Reverse Proxy: Auto HTTPS & Compression] --> Dashboard
        Caddy --> AgentCore
    end
```

---

## Key Features & Phases

### Phase 1: Foundations & Core Receptionist
- **Multi-Tenant from Day One**: Every database table is indexed and foreign-keyed by `business_id`.
- **Dynamic Personas**: Spoken greetings, tone, and policies are built dynamically per business tenant.
- **Strict Hallucination Prevention**: If knowledge similarity falls below the cutoff, the agent declines speculation, logs a `knowledge_miss`, and offers to take a message.
- **Interchangeable Providers**:
  - **LLM**: Groq (Llama 3.3 70B), Gemini Flash, or local Ollama with exponential backoff.
  - **STT**: Deepgram Nova-2.
  - **TTS**: Deepgram Aura or Cartesia.
  - **Embeddings**: Sentence-transformers (`all-MiniLM-L6-v2`) stored via `pgvector`.
  - **Voice Pipeline**: LiveKit Agents Python framework with WebRTC and text-eval fallback mode.

### Phase 2: Booking, Verification & Live Transfer
- **Timezone-Aware Availability Engine**: Generates 30-minute bookable slots conforming to operating hours, excluding existing appointments, and enforcing minimum notice windows.
- **Double-Booking & Race Condition Prevention**: Uses PostgreSQL tenant row-level locking (`SELECT ... FOR UPDATE`) to eliminate concurrent double-booking.
- **6-Character Booking Codes**: Generates secure booking codes (e.g., `BK-4X2`) stored as SHA-256 hashes with phone number masking (`***-***-1234`).
- **Caller Verification & Lockout Protection**: Modifying or cancelling appointments requires verification against customer name and phone, with strict 3-attempt lockout per session.
- **Dual-Channel Automated Reminders**:
  - 24 hours prior: Email confirmation and reminder.
  - 2 hours prior: Automated phone reminder call.
  - Background scheduler daemon with `SELECT ... FOR UPDATE SKIP LOCKED` for reliable, zero-duplicate delivery.
- **Live Call Transfer to Human**: Gated by business hours and transfer destination number with automated fallback message taking and owner alert emails.
- **Google Calendar Synchronization**: Interchangeable `CalendarProvider` interface (`LocalCalendarProvider` and `GoogleCalendarProvider`) synchronizing busy blocks via Google Calendar v3 REST API.

### Phase 3: Web Dashboard, Multi-Tenant Isolation & Role-Based Access Control
- **Next.js 14 App Router Dashboard**: Full responsive management interface for Call logs, Transcripts, Scheduling, Knowledge Base, Team, Audit Trail, and Settings.
- **PostgreSQL Row Level Security (RLS)**: Database-kernel enforced multi-tenant isolation setting `app.current_business_id` per connection.
- **Argon2id Authentication & Sessions**: Cryptographic 64-character session tokens stored as SHA-256 hashes, with HTTP-only SameSite cookies and progressive rate-limiting lockout.
- **Role-Based Access Control (RBAC)**: Fine-grained permissions for `Owner`, `Manager`, and `Staff`.
- **Double-Submit CSRF Defense**: Cryptographic cookie and header tokens validated on all state-mutating requests.

### Phase 4: Production Telephony, Chat Widget, Limits, Observability & Self-Hosting
- **LiveKit SIP Telephony Routing**: Inbound telephone routing mapping dialed E.164 numbers to business tenants and resolving caller identity.
- **Website Chat Widget**:
  - Zero-dependency embeddable script (`web/public/widget.js` and `web-widget/embed.js`).
  - Standalone isolated iframe interface (`/widget-frame/[key]`).
  - Dashboard configuration: theme colors, greeting, lead capture, and domain origin restrictions.
- **Usage Tracking & Limit Enforcement**: Itemized token and duration tracking with cost estimation, monthly minutes/chat quotas, and graceful degradation.
- **Emergency Kill Switch & Provider Circuit Breaker**:
  - Dynamic kill switch via CLI (`callwise killswitch enable`) or environment flag.
  - Three-state circuit breaker (`CLOSED` $\rightarrow$ `OPEN` $\rightarrow$ `HALF_OPEN`) with automatic failover between Groq and Gemini.
- **Abuse & Flood Protection**: Per-caller hourly rate limits, tenant phone blocklist, and keyboard smash / nonsense repetition detection.
- **Production Docker Setup with Caddy**: Multi-stage Dockerfiles for backend and Next.js, Caddy reverse proxy with automated TLS and compression, and `docker-compose.prod.yml`.
- **System Diagnostics & Maintenance**: `callwise doctor` diagnostic command and compressed database backup/restore tools (`scripts/backup.sh`, `scripts/restore.sh`).
- **Structured JSON Logging & Metrics**: PII redaction filter scrubbing cards/SSNs/passwords and Prometheus exposition endpoint (`/metrics`).
- **Comparative Evals & Load Testing**: Multi-provider side-by-side benchmark evaluations (`callwise run-evals --compare`) and async concurrency load tester (`scripts/load_test.py`).

---

## Quickstart & Setup Guide

### 1. Prerequisites
- **Python 3.12+**
- **uv** (recommended) or standard `pip`
- **Node.js 20+** (for frontend dashboard)
- **Docker & Docker Compose**

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
# Windows
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Configure your credentials in `.env`:
- `GROQ_API_KEY`: Groq API key (Llama 3.3 70B)
- `GEMINI_API_KEY`: Google Gemini API key (secondary/fallback LLM)
- `DEEPGRAM_API_KEY`: Deepgram API key (STT & TTS)
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`: LiveKit Cloud project credentials
- `DATABASE_URL`: `postgresql+asyncpg://postgres:postgres@localhost:5433/callwise`

### 3. Start PostgreSQL with pgvector
```bash
docker compose up -d
```

### 4. Install Dependencies & Run Database Migrations
```bash
uv sync --all-extras
uv run alembic upgrade head
```

### 5. Seed Demonstration Tenants
```bash
uv run python -m callwise.cli seed
```

### 6. Run System Diagnostics
```bash
uv run python -m callwise.cli doctor
```

### 7. Launch Web Dashboard & API
```powershell
# Terminal 1: Backend API
uv run python -m uvicorn callwise.api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Next.js Frontend
cd web
npm install
npm run dev
```

Log in at [http://localhost:3000/login](http://localhost:3000/login) with:
- **Email:** `dental.owner@test.com`
- **Password:** `Password123!`

---

## Production Deployment with Docker Compose & Caddy

Run the complete multi-container production stack (PostgreSQL + pgvector, FastAPI Backend, Background Ingestion Worker, Appointment Reminder Daemon, Next.js Dashboard, and Caddy Reverse Proxy):

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Access the unified service via Caddy reverse proxy at [http://localhost](http://localhost) (or configured `DOMAIN`).

---

## CLI Command Reference

Execute CLI commands with `uv run python -m callwise.cli <command>`:

| Command | Description |
|---|---|
| `callwise doctor` | Run comprehensive 12-point system diagnostic health check. |
| `callwise seed` | Seed database with demo tenants (Apex Dental Clinic and Serenity Spa). |
| `callwise run-evals [--compare]` | Run benchmark evaluation suite or side-by-side Groq vs Gemini comparison. |
| `callwise load-test [-n 50] [-c 5]` | Run concurrent traffic and load simulation test. |
| `callwise killswitch [status\|enable\|disable]` | Inspect or toggle global emergency kill switch. |
| `callwise blocklist [add\|list\|remove]` | Manage tenant telephone abuse blocklist. |
| `callwise db backup [--output-dir ...]` | Create compressed database backup (`.sql.gz`). |
| `callwise db restore <backup_file>` | Restore database from compressed backup archive. |
| `callwise run-scheduler` | Run appointment reminder daemon (24h email & 2h phone call). |
| `callwise run-worker` | Run asynchronous background document and audio ingestion worker. |
| `callwise chat --business-id <UUID>` | Interactive CLI conversational text chat with AI receptionist. |
| `callwise run-agent --business-id <UUID>` | Start LiveKit WebRTC voice agent worker for live calls. |

---

## Documentation Links

- 📖 **[DEMO.md](DEMO.md)**: Full interactive walkthrough guide, softphone setup, curl commands, and conversational transcripts.
- 📸 **[SCREENSHOTS.md](SCREENSHOTS.md)**: Detailed specifications and checklist of all 14 web dashboard views.
- 🛡️ **[SECURITY.md](SECURITY.md)**: Defense-in-depth security architecture, threat model, and mitigation matrix.
