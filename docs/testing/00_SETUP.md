# 00_SETUP.md: Clean Machine to Running System 🚀

This guide walks you through setting up Callwise from scratch on a Windows machine (using PowerShell), verifying every prerequisite, starting all background and web services, seeding deterministic demonstration data, performing a quick smoke test, and resetting state when needed.

> [!IMPORTANT]
> **Windows Application Control Notice**:
> Under Windows Application Control or Code Integrity policies, executing `.exe` launcher stubs directly (such as `uv run alembic`, `uv run pytest`, or `uv run uvicorn`) will fail with OS error `4551 ("An Application Control policy has blocked this file")`.
> To prevent this block, **always run tools via the Python module syntax**:
> - Use `uv run python -m alembic ...` (NOT `uv run alembic ...`)
> - Use `uv run python -m uvicorn ...` (NOT `uv run uvicorn ...`)
> - Use `uv run python -m pytest ...` (NOT `uv run pytest ...`)
> - Use `uv run python -m callwise.cli ...` (NOT `uv run callwise ...`)

> [!NOTE]
> **Automated Test Isolation**:
> Automated tests executed via `uv run python -m pytest tests/` automatically redirect to an isolated, temporary database (`callwise_test`) configured in `tests/conftest.py`. The test suite automatically creates `callwise_test`, runs Alembic migrations, executes tests, and tears it down upon completion. Running `pytest` will **never** alter or pollute your `callwise` development database.

---

## 1. Prerequisites Check

Before starting, open a PowerShell terminal and confirm the following development tools are installed:

```powershell
# 1. Python (3.12 or 3.13)
python --version

# 2. uv (Fast Python package manager)
uv --version

# 3. Node.js (v20+) and npm
node --version
npm --version

# 4. Docker Desktop (must be running with Linux container backend)
docker --version
docker compose version
```

### Expected Output
- `Python 3.12.x` or `Python 3.13.x`
- `uv 0.x.x`
- `v20.x.x` or higher
- `Docker version 27.x.x` (or Docker Desktop active)

### Troubleshooting
- **If `uv` is not recognized**: Install via PowerShell:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **If Docker is stopped**: Start **Docker Desktop** from the Windows Start menu and wait for the whale icon in the taskbar to become solid green/steady.

---

## 2. Environment Configuration

Navigate to the project root:

```powershell
cd E:\Callwise
```

Ensure `.env` exists by copying `.env.example`:

```powershell
if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
```

### Essential Environment Variables in `.env`
Inspect `.env` to verify key defaults:

| Variable | Recommended Local Value | Note |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5433/callwise` | Default container port is `5433` |
| `DATABASE_URL_SYNC` | `postgresql+psycopg://postgres:postgres@localhost:5433/callwise` | Required by Alembic migrations |
| `SECRET_KEY` | `callwise-dev-secret-key-change-in-prod-min32bytes!` | For dev only; see [FINDINGS.md](FINDINGS.md#finding-03) |
| `EMAIL_PROVIDER` | `console` | Prints outbound emails to terminal |
| `CALENDAR_PROVIDER`| `local` | Uses PostgreSQL appointment table |
| `TELEPHONY_PROVIDER`| `mock` | For inbound local testing |
| `LLM_PROVIDER` | `groq` (or `gemini`) | Primary LLM reasoning |
| `GROQ_API_KEY` | `gsk_...` | Set your active Groq API key |
| `GEMINI_API_KEY` | `AIza...` | Set your active Google Gemini key |

---

## 3. Install Dependencies

Install all Python virtual environment packages and frontend Node modules:

```powershell
# 1. Sync Python dependencies
uv sync --all-extras

# 2. Install frontend dependencies
cd web
npm install
cd ..
```

---

## 4. Start PostgreSQL with pgvector

Callwise requires PostgreSQL 16 with the `pgvector` extension enabled, accessible on port `5433`:

```powershell
docker compose up -d
```

### Confirm Container is Running
```powershell
docker compose ps
```
### Expected Output
```
NAME                IMAGE                     COMMAND                  SERVICE    STATUS
callwise-postgres   pgvector/pgvector:pg16   "docker-entrypoint.s…"   postgres   Up (healthy)
```

---

## 5. Apply Database Migrations & Run Seed Data

Run Alembic schema migrations via module syntax, then seed demo tenants:

```powershell
# 1. Run migrations to latest head (using module execution to bypass Application Control block)
uv run python -m alembic upgrade head

# 2. Seed realistic businesses & service menus
uv run python -m callwise.cli seed
```

### Verify Exactly 2 Businesses Exist Before Testing
Confirm that the database is clean and contains only the 2 seeded businesses:

```powershell
(uv run python -m callwise.cli list-businesses | Select-String "^\| [0-9a-f]{8}-").Count
```

### Expected Output
```
2
```
If this count is greater than 2, see [Section 10](#10-how-to-reset-database-data) below to reset before starting manual testing.

---

## 6. Seeded Demo Data Reference

The `seed` routine populates the database with two isolated tenant businesses and pre-configured service catalogs:

### Business Tenant 1: BrightSmile Family Dental
- **UUID:** `11111111-1111-1111-1111-111111111111`
- **Business Type:** Dental Clinic
- **Timezone:** `America/New_York` (EST/EDT)
- **Transfer Number:** `+1-617-555-0100`
- **Notification Email:** `frontdesk@brightsmilefamilydental.com`
- **Operating Hours:**
  - Monday–Thursday: 08:00 – 17:00
  - Friday: 08:00 – 13:00
  - Saturday & Sunday: Closed
- **Services Catalog:**
  1. *Routine Cleaning & Exam* (60 min, $120.00)
  2. *Zoom In-Office Teeth Whitening* (60 min, $350.00)
  3. *Porcelain Dental Crown* (90 min, $950.00)
  4. *Emergency Dental Exam* (30 min, $85.00)

### Business Tenant 2: Luxe Glow Salon & Spa
- **UUID:** `22222222-2222-2222-2222-222222222222`
- **Business Type:** Hair Salon & Spa
- **Timezone:** `America/Los_Angeles` (PST/PDT)
- **Transfer Number:** `+1-310-555-0200`
- **Notification Email:** `reception@luxeglowsalon.com`
- **Operating Hours:**
  - Monday: Closed
  - Tuesday–Thursday: 10:00 – 19:00
  - Friday: 10:00 – 20:00
  - Saturday: 09:00 – 18:00
  - Sunday: 11:00 – 16:00
- **Services Catalog:**
  1. *Women's Haircut & Blowout* (45 min, $75.00)
  2. *Full Custom Balayage* (120 min, $220.00)
  3. *Keratin Smoothing Treatment* (90 min, $275.00)
  4. *Signature Glow Facial* (60 min, $110.00)

---

## 7. Run Comprehensive Diagnostic (`callwise doctor`)

Execute the built-in 12-point health check to verify all subsystems:

```powershell
uv run python -m callwise.cli doctor
```

### Expected Output
```
============================================================
         CALLWISE SYSTEM DIAGNOSTIC (DOCTOR)         
============================================================
+--------------------------+----------+-----------------------------------------+
| Subsystem Component      | Status   | Diagnostic Details                      |
+==========================+==========+=========================================+
| Database Connection      | [OK]     | Connected (<100ms latency)              |
| pgvector Extension       | [OK]     | Installed (v0.8.7)                      |
| Database Migrations      | [OK]     | Current head: b3d9c18f2a01              |
| Primary LLM (Groq)       | [OK]     | Configured                              |
| Fallback LLM (Gemini)    | [OK]     | Configured & Ready                      |
| STT Provider (Deepgram)  | [OK]     | Ready                                   |
| TTS Provider             | [OK]     | Using deepgram                          |
| Telephony Provider       | [OK]     | mock configured                         |
| Email Provider           | [OK]     | Using console                           |
| Emergency Kill Switch    | [OK]     | Inactive (Normal operations)            |
| Circuit Breakers         | [OK]     | All circuits closed and healthy         |
| Disk Storage Permissions | [OK]     | Backup directory writable               |
+--------------------------+----------+-----------------------------------------+
Passed: 12. All critical systems are operational!
```

---

## 8. Starting Application Services

For complete manual testing, open separate PowerShell windows for each service:

### Terminal 1: Backend FastAPI API (Port 8000)
```powershell
cd E:\Callwise
uv run python -m uvicorn callwise.api.main:app --host 0.0.0.0 --port 8000
```
- **What you should see:**
  `INFO: Application startup complete.`
  `Uvicorn running on http://0.0.0.0:8000`
- **Swagger Documentation:** `http://localhost:8000/api/docs`
- **Health Check Endpoint:** `http://localhost:8000/api/health`

### Terminal 2: Next.js Frontend Dashboard (Port 3000)
```powershell
cd E:\Callwise\web
npm run dev
```
- **What you should see:**
  `▲ Next.js 14.2.35`
  `- Local: http://localhost:3000`
  `✓ Ready in 1500ms`

### Terminal 3: Background Ingestion Worker (Polls jobs queue)
```powershell
cd E:\Callwise
uv run python -m callwise.cli run-worker --interval 5
```
- **What you should see:**
  `[INFO] Starting Callwise Background Worker (interval: 5.0s)`
  `[INFO] Ingestion worker polling for jobs...`

### Terminal 4: Reminder Scheduler Daemon (Polls appointments for reminders)
```powershell
cd E:\Callwise
uv run python -m callwise.cli run-scheduler --interval 60
```
- **What you should see:**
  `[INFO] Starting appointment reminder scheduler daemon...`

### Terminal 5: Voice Pipeline Agent (Primary Path: Docker Container)
> [!IMPORTANT]
> **Windows Smart App Control / Application Control Block**:
> On Windows workstations with Smart App Control or Application Control active, running the LiveKit voice agent natively (`uv run python -m callwise.cli run-agent`) is blocked by Windows Code Integrity because LiveKit's upstream wheel packages contain native C++ extension modules (`livekit/local_inference/_native.pyd`).
> **The supported path for running the voice agent on Windows is Docker**.
> 
> **Tests Blocked if Docker is NOT used:**
> - Interactive voice conversations in LiveKit Agents Playground
> - Real-time WebRTC audio sessions
> - Live telephone voice calls via SIP / Twilio forwarding

To run the voice agent container in `dev` mode for BrightSmile Family Dental (`11111111-1111-1111-1111-111111111111`):

#### Method A: Docker Compose (Recommended)
```powershell
docker compose --profile voice up agent
# or for an interactive one-off run with automatic cleanup:
docker compose --profile voice run --rm agent
```

#### Method B: Direct Docker Run
```powershell
# Run the voice agent container on the shared callwise_default Docker network
docker run --rm -it `
  --name callwise-voice-agent `
  --network callwise_default `
  --env-file .env `
  -e DATABASE_URL="postgresql+asyncpg://postgres:postgres@callwise-postgres:5432/callwise" `
  -e DATABASE_URL_SYNC="postgresql://postgres:postgres@callwise-postgres:5432/callwise" `
  callwise-agent -b 11111111-1111-1111-1111-111111111111 -m dev
```

- **What you should see:**
  The agent registers with LiveKit Cloud worker pool:
  ```text
  Starting LiveKit voice agent worker for business 11111111-1111-1111-1111-111111111111 in 'dev' mode...
  INFO livekit.agents - starting worker {"version": "1.8.11", "rtc-version": "1.2.0"}
  INFO livekit.agents - registered worker {"agent_name": "", "deployment": "", "id": "AW_...", "url": "wss://callwise-....livekit.cloud", "region": "...", "protocol": 18}
  ```

- **Testing via LiveKit Playground (Secure):**
  1. Log into your [LiveKit Cloud Project Dashboard](https://cloud.livekit.io).
  2. Navigate to your project, open the **Agents** or **Sandbox / Playground** section directly within your authenticated dashboard.
  3. **Security Note:** Never paste your `LIVEKIT_API_SECRET` into third-party websites or external playground tools. The dashboard playground connects automatically using your project's authenticated session.
  4. Click **Connect** and talk to the agent via your microphone.

- **Explicit Dispatch & Agent Name Configuration:**
  - By default, the worker registers with automatic room dispatch (`agent_name: ""`), responding to any room created in the project.
  - If your LiveKit Cloud project uses explicit dispatch (where rooms or SIP trunks request an agent by name), set `agent_name` in `WorkerOptions` inside `src/callwise/agent/voice_agent.py` (e.g. `WorkerOptions(entrypoint_fnc=..., agent_name="callwise-receptionist")`) or specify it via the CLI.


---

## 9. End-to-End Smoke Test

Run this quick test script to confirm API and Frontend connectivity:

```powershell
# 1. Test Backend Health Endpoint
Invoke-RestMethod -Uri "http://localhost:8000/api/health" -Method Get

# 2. Test Prometheus Metrics Exposition
Invoke-RestMethod -Uri "http://localhost:8000/api/metrics" -Method Get | Select-String "callwise_calls_total"

# 3. Test Frontend Landing Route
Invoke-WebRequest -Uri "http://localhost:3000/login" -UseBasicParsing | Select-Object StatusCode
```

### Expected Output
- `status: ok`, `database: connected`
- `callwise_calls_total 0.0`
- `StatusCode: 200`

---

## 10. How to Reset Database Data

If you need to return to a pristine state:

### Option A: Complete Database Volume Reset & Re-seed
```powershell
# 1. Tear down container and wipe data volume
docker compose down -v

# 2. Spin up fresh Postgres with pgvector
docker compose up -d

# 3. Run migrations via python module
uv run python -m alembic upgrade head

# 4. Seed demo businesses
uv run python -m callwise.cli seed

# 5. Confirm count is exactly 2
(uv run python -m callwise.cli list-businesses | Select-String "^\| [0-9a-f]{8}-").Count
```

### Option B: Snapshot & Instant Restore
```powershell
# Create snapshot of current clean state
uv run python -m callwise.cli db backup --output-dir backups

# Restore snapshot if data is modified during manual testing
uv run python -m callwise.cli db restore backups\<backup_file>.sql.gz --confirm
```
