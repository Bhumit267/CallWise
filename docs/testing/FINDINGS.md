# Callwise Findings & Known Discrepancies Log

This document records bugs, gaps, inconsistencies, or unverified items identified during the creation of the Callwise manual testing kit. Per the project testing guidelines, these items are tracked here rather than silently patched in application code.

---

## Logged Findings

### FINDING-01: Hardcoded Personal Email in Login Page Demo Autofill [FIXED]
- **File:** `web/app/(auth)/login/page.tsx`
- **Severity:** Low (Privacy / Pre-production Hygiene)
- **Status:** **FIXED**
- **What was wrong:** The login page rendered a quick helper button with the label `"Autofill dental.owner@test.com"` which pre-populated personal email credentials.
- **Resolution:** Replaced with generic demo credentials for the seeded BrightSmile owner: `dental.owner@test.com` / `password123` with the label `"Autofill Demo (BrightSmile Owner)"`.

---

### FINDING-02: 2-Hour Reminder Voice Call Logs Misleading Status "sent" [FIXED]
- **File:** `src/callwise/reminders/scheduler.py`
- **Severity:** Low (Audit Log Accuracy / Semantics)
- **Status:** **FIXED**
- **What was wrong:** When the reminder daemon processed an upcoming appointment within 2 hours, `trigger_reminder_call()` simulated the call via console logging but recorded `status="sent"` in the notifications table.
- **Resolution:** Updated status to `status="simulated"` to accurately reflect simulated console audio notifications. Updated test assertions in `tests/test_reminders.py`.

---

### FINDING-03: Default Development Secret Key in Config [FIXED]
- **Files:** `src/callwise/config.py`, `src/callwise/api/main.py`, `tests/test_config_security.py`.
- **Severity:** Medium (Production Security)
- **Status:** **FIXED**
- **What was wrong:** `SECRET_KEY` had a fallback default value of `"callwise-dev-secret-key-change-in-prod-min32bytes!"` without an environment guard.
- **Resolution:** Added `environment` setting to `Settings`. In `callwise.api.main`, added a production startup security validator that rejects startup if `environment == "production"` and `SECRET_KEY` matches the default dev value or is shorter than 32 bytes. Added unit test suite in `tests/test_config_security.py`.

---

### FINDING-04: Pytest Test Suite Ran Directly Against Dev Database [FIXED]
- **Files:** `tests/conftest.py`, `tests/test_booking.py`, `tests/test_api_write.py`, `tests/test_tenant_isolation.py`, and test files across the suite.
- **Severity:** High (Development / Manual Testing Data Integrity)
- **Status:** **FIXED** (via `tests/conftest.py`)
- **What was wrong:** Previously, `pytest` executed against the primary development database (`callwise` on port 5433). Because many tests commit test fixtures directly, thousands of orphaned rows (e.g., "Test Apex Dental", "Tenant A Line", "Worker Test Biz") accumulated in the development database.
- **Resolution:** Implemented `tests/conftest.py`. At the very top of `conftest.py`, before any `callwise` application code or `settings` instance is imported, `DATABASE_URL` and `DATABASE_URL_SYNC` are explicitly intercepted and pointed to `callwise_test`. A safety guard immediately aborts execution if the target database name does not end in `_test`. A session fixture creates a fresh `callwise_test` database via the `postgres` maintenance connection, runs `alembic upgrade head` programmatically, and drops the test database at session teardown. Pytest can now be safely executed at any time without polluting the manual testing database.

---

### FINDING-05: Windows Application Control Blocks Direct `.exe` Script Launchers
- **Files:** `alembic.exe`, `pytest.exe`, `uvicorn.exe` in `.venv/Scripts/`
- **Severity:** Medium (Windows Developer Experience & Reproducibility)
- **What is wrong:** Under Windows Application Control / Code Integrity policies, executing direct `.exe` wrapper binaries located inside virtual environment directories (`.venv\Scripts\alembic.exe`, `.venv\Scripts\pytest.exe`, `.venv\Scripts\uvicorn.exe`) triggers an OS security error:
  `"An Application Control policy has blocked this file (os error 4551)"`.
  Running `uv run alembic upgrade head` attempts to execute this `.exe` stub, which fails on hardened Windows systems.
- **Steps to reproduce:**
  1. On a Windows machine with Application Control enabled, run: `uv run alembic upgrade head`.
  2. The command fails with OS error 4551.
- **Recommendation:** Always invoke Python CLI tools as module commands via the verified Python interpreter:
  - `uv run python -m alembic upgrade head`
  - `uv run python -m pytest tests/`
  - `uv run python -m uvicorn callwise.api.main:app`
  - `uv run python -m callwise.cli <command>`
  All documentation and testing kit instructions must strictly use the `uv run python -m ...` pattern.


---

### FINDING-06: Navigation and Page UI Expose Owner/Manager Features to Staff; /team Shows Misleading Empty State [FIXED]
- **Files:** `web/app/(dashboard)/layout.tsx`, `web/app/(dashboard)/team/page.tsx`, `web/app/(dashboard)/settings/page.tsx`, `web/types/api.ts`, `web/contexts/auth-context.tsx`.
- **Severity:** Medium (UX / Interface Polish / RBAC Visibility)
- **Status:** **FIXED**
- **What was wrong:**
  1. In `web/app/(dashboard)/layout.tsx`, `navItems` was a static list that rendered links to all 13 dashboard sections (including "Team & Access", "Phone Numbers", "Website Widget", "Usage & Limits", and "Settings") unconditionally for all authenticated users, regardless of whether their role was `staff`, `manager`, or `owner`.
  2. In `web/app/(dashboard)/team/page.tsx`, `fetchTeamData()` issued `Promise.all([apiClient('/api/team/members'), apiClient('/api/team/invites')])`. Because `GET /api/team/invites` requires at least `manager` (`require_manager`), the API rejected the request with HTTP `403 Forbidden`. The page caught the error, left `members` and `invites` as empty arrays (`[]`), and rendered:
     - Header counters: *"Active Team & Invites: 0"*
     - Table empty state: *"No active members found"*
     - An active *"Invite Member"* button
     - A red error banner at the top: *"Action requires at least 'manager' role. Your role is 'staff'."*
     This misled staff users into believing the business had no active members rather than informing them that viewing team invites and managing access is restricted to managers and owners.
  3. In `web/app/(dashboard)/settings/page.tsx`, the page displayed fully editable input fields and active save buttons (e.g. *"Save Voice Profile"*, *"Save Routing"*, *"Add Service"*). When staff modified a field and clicked Save, `PUT /api/settings/profile` returned HTTP `403 Forbidden`.
- **Resolution:**
  1. **Dynamic Sidebar Filtering by Role:** In `web/app/(dashboard)/layout.tsx`, added `minRole: 'manager'` to administrative routes ("Phone Numbers", "Website Widget", "Usage & Limits", and "Team & Access"). Filtered `navItems` against `role` so staff members are only presented with staff-permitted navigation links.
  2. **Staff Read-Only Team View:** In `web/app/(dashboard)/team/page.tsx`, when `role === 'staff'`, only `/api/team/members` is fetched (bypassing `/api/team/invites` to eliminate the 403 error). Rendered a clean read-only member table, hid the "Invite Member" button, and hid the "Pending Invitations" section.
  3. **Staff Read-Only Settings View:** In `web/app/(dashboard)/settings/page.tsx`, when `role === 'staff'`, displayed a clear informational banner explaining that settings are managed by owners/managers, disabled "Save Voice Profile" and "Save Routing", and hid service mutation buttons ("Add New Service", "Edit", "Delete").
  4. **Frontend Type Alignment:** Extended `Role` type in `web/types/api.ts` and `web/contexts/auth-context.tsx` to include `'manager'` to match backend RBAC hierarchy. Verified clean production build (`npm --prefix web run build`).


---

### FINDING-07: Signup Page Request Schema Mismatch (422 Unprocessable Content) & "[object Object]" Error Display [FIXED]
- **Files:** `web/contexts/auth-context.tsx`, `web/app/(auth)/signup/page.tsx`, `web/lib/api.ts`, `web/types/api.ts`.
- **Severity:** High (Broken Public Signup Flow / User Registration)
- **Status:** **FIXED**
- **What was wrong:**
  1. `web/contexts/auth-context.tsx` sent `full_name` instead of `owner_name` and omitted the required `business_type` field expected by FastAPI's `SignupRequest` (`POST /api/auth/signup`), causing HTTP 422 Unprocessable Content.
  2. `web/lib/api.ts` passed raw Pydantic validation error arrays directly into `message`, rendering unformatted `[object Object],[object Object]` text in the UI.
- **Resolution:**
  1. Updated `web/contexts/auth-context.tsx` to send `owner_name` and `business_type`.
  2. Added a Business Type select input to `web/app/(auth)/signup/page.tsx` with options (Dental Clinic, Hair Salon & Spa, Veterinary & Pet Care, Home Services & Repair, Professional Office, Other).
  3. Implemented `formatApiError()` in `web/lib/api.ts` to convert Pydantic validation error lists into clean, readable text strings (e.g. `business_type: Field required`).
  4. Updated `web/types/api.ts` to include optional `businessType` in `AuthContextType.signup`.


---

### FINDING-08: Missing Favicon (`/favicon.ico`) Triggers Console 404 [FIXED]
- **Files:** `web/app/icon.svg`, `web/public/favicon.ico`.
- **Severity:** Low (Browser Console Cosmetic / Polish)
- **Status:** **FIXED**
- **What was wrong:** Browsers automatically request `/favicon.ico` on every page load unless a favicon link tag or static icon file exists in the web directory. In `web/public/`, only `widget.js` existed; neither `web/public/favicon.ico` nor `web/app/favicon.ico` was provided. This resulted in a visible browser console error:
  `GET http://localhost:3000/favicon.ico 404 (Not Found)`.
- **Resolution:** Created a branded SVG icon (`web/app/icon.svg`) matching the Callwise robot visual branding and generated a multi-resolution `web/public/favicon.ico`. Verified HTTP `200 OK` on `GET http://localhost:3000/favicon.ico`.

---

### FINDING-09: Frontend Regression Tests (Signup E2E & formatApiError) Native Integration & Self-Cleaning Teardown [FIXED]
- **Files:** `web/tests/unit/format-api-error.test.js`, `web/tests/e2e/signup.test.js`, `web/package.json`.
- **Severity:** Low (Testing Infrastructure / Developer Experience)
- **Status:** **FIXED**
- **What was wrong:** The signup E2E and formatApiError tests resided in ad-hoc test scripts outside the frontend project root, and the E2E signup test left orphaned test businesses and accounts in the development database.
- **Resolution:**
  1. **Standardized Test Organization:** Integrated unit and E2E suites into `web/tests/unit/format-api-error.test.js` and `web/tests/e2e/signup.test.js`.
  2. **Automated Self-Cleaning Teardown:** Built an automated post-test cleanup routine into `signup.test.js` using Python database commands to purge the newly created test tenant immediately after asserting navigation to `/onboarding`. Verified database business count remains exactly 2 (`BrightSmile Family Dental` and `Luxe Glow Salon & Spa`).
  3. **NPM Test Automation:** Configured `test:unit`, `test:e2e`, and `test` scripts in `web/package.json` (`npm --prefix web test`), achieving 100% test pass rate.

---

### FINDING-10: Web API Imports Voice Pipeline Stack at Startup, Crashing Web Server on Systems with Blocked Native DLLs [FIXED]
- **Files:** `src/callwise/agent/__init__.py`, `src/callwise/agent/voice_agent.py`, `src/callwise/agent/tools.py`, `tests/test_api_startup_no_livekit.py`.
- **Severity:** High (System Availability / Cross-Platform Portability)
- **Status:** **FIXED**
- **What was wrong:**
  At startup, `callwise.api.main` imported `onboarding.py`, which imported `TextAgent` from `callwise.agent`.
  In `callwise.agent.__init__.py`, `voice_agent.py` was unconditionally imported at module load time.
  In `voice_agent.py`, all voice plugins (`google`, `groq`, `deepgram`, `cartesia`, `openai`, `silero`) were imported at the top of the file.
  Because `livekit.plugins.google` imports `grpc`, and `livekit.agents` imports native C-extensions (`livekit-local-inference` and `livekit-blingfire`), any environment where Windows Application Control / Smart App Control or system policies block unsigned native `.pyd`/DLL files crashed the entire FastAPI web API at startup with `ImportError: DLL load failed while importing cygrpc / _native: An Application Control policy has blocked this file`—even though the web dashboard and onboarding agent only use the text agent (`TextAgent`) and standard HTTP endpoints.
- **Resolution:**
  1. **Lazy Module Attributes in `agent/__init__.py`:** Replaced top-level imports of `create_voice_agent` and `start_voice_worker` with PEP 562 `__getattr__` dynamic module loading so importing `TextAgent` never imports `voice_agent`.
  2. **Lazy Plugin & Agent Loading in `voice_agent.py`:** Removed top-level LiveKit plugin imports (`google`, `groq`, `deepgram`, etc.) and `livekit.agents` top-level imports. Moved plugin imports inside `create_llm_plugin()`, `create_tts_plugin()`, `create_voice_agent()`, and `start_voice_worker()` only when configured and called. When `LLM_PROVIDER=groq`, `google` and `grpc` are never loaded.
  3. **Lazy Function Tool in `tools.py`:** Moved `from livekit.agents import function_tool` inside `get_livekit_tools()` so importing `CallwiseToolset` never loads LiveKit.
  4. **Regression Test:** Added `tests/test_api_startup_no_livekit.py` verifying `callwise.api.main`, `TextAgent`, and the onboarding router load successfully even when LiveKit and gRPC are blocked.

---

### FINDING-11: Voice Agent Native Execution Blocked by Windows Application Control / Smart App Control; Docker is the Supported Path
- **Files:** `Dockerfile.agent`, `docker-compose.yml`, `.dockerignore`, `docs/testing/00_SETUP.md`, `docs/testing/FINDINGS.md`.
- **Severity:** High (Voice Subsystem Availability on Windows 11)
- **Status:** **RESOLVED (CONTAINERIZED WORKER READY & VERIFIED)**
- **What was wrong:**
  The LiveKit voice pipeline agent (`livekit-agents`) depends internally on compiled native extension modules (`livekit/local_inference/_native.pyd` and `livekit/blingfire/_native.pyd`).
  On Windows workstations with Windows Defender Application Control (WDAC) or Smart App Control (SAC) enabled, Windows kernel code integrity refuses to load these `.pyd` files (`ImportError: DLL load failed while importing _native: An Application Control policy has blocked this file`).
  Because this code resides inside LiveKit's upstream precompiled wheels, this cannot be resolved by application Python code changes without disabling Windows SAC.
- **Resolution & Supported Path:**
  1. The supported path to run the LiveKit voice agent on Windows developer machines is via a Linux container (`Dockerfile.agent`), where the full LiveKit ecosystem, Silero VAD, PyTorch/ONNX, and audio pipelines run without Windows Application Control restrictions.
  2. The voice agent container runs on the shared Docker network (`callwise_default`), connecting directly to the PostgreSQL container (`callwise-postgres:5432`) and external cloud APIs (LiveKit Cloud, Deepgram, Groq).
  3. Pre-downloads all models at build time as unprivileged user `callwise`:
     - LiveKit plugin models & Silero VAD: `/home/callwise/.cache/livekit`
     - HuggingFace sentence-transformers (`all-MiniLM-L6-v2`): `/home/callwise/.cache/huggingface/hub`
  4. Added `agent` service to `docker-compose.yml` with `profiles: ["voice"]` so default `docker compose up -d` is unaffected.
- **Informational Build & Runtime Metrics:**
  - **Docker Image:** `callwise-agent:latest`
  - **Image Content Size:** `3.4 GB` (`9.97 GB` virtual uncompressed disk usage including PyTorch, HuggingFace embeddings, Silero VAD models)
  - **Initial Build Duration:** ~16 minutes (downloading PyTorch & full ML dependencies over network); layer export & packaging completed in 5m 46s.
  - **LiveKit Cloud Verification:** Container started in `dev` mode for BrightSmile Family Dental (`11111111-1111-1111-1111-111111111111`), registered with LiveKit Cloud worker pool (`AW_KDYFNncwXhWg` on `wss://callwise-0zxd56h9.livekit.cloud`), and is actively waiting for voice session jobs.



