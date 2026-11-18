# Callwise Findings & Known Discrepancies Log

This document records bugs, gaps, inconsistencies, or unverified items identified during the creation of the Callwise manual testing kit. Per the project testing guidelines, these items are tracked here rather than silently patched in application code.

---

## Logged Findings

### FINDING-01: Hardcoded Personal Email in Login Page Demo Autofill [FIXED]
- **File:** `web/app/(auth)/login/page.tsx`
- **Severity:** Low (Privacy / Pre-production Hygiene)
- **Status:** **FIXED**
- **What was wrong:** The login page rendered a quick helper button with the label `"Autofill dental.owner@test.com"` which pre-populated personal email credentials.
- **Resolution:** Replaced with generic demo credentials for the seeded clinic owner: `aarav.owner@test.com` / `Password123!` with the label `"Autofill Demo (Aarav Clinic Owner)"`.

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
  2. **Automated Self-Cleaning Teardown:** Built an automated post-test cleanup routine into `signup.test.js` using Python database commands to purge the newly created test tenant immediately after asserting navigation to `/onboarding`. Verified database business count remains exactly 2 (`Aarav Health & Dental Clinic` and `Luxe Glow Salon & Spa`).
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
  - **LiveKit Cloud Verification:** Container started in multi-tenant mode, registered with LiveKit Cloud worker pool (`AW_KDYFNncwXhWg` on `wss://callwise-0zxd56h9.livekit.cloud`), and is actively waiting for voice session jobs.

---

### FINDING-12: PostgreSQL Row-Level Security (RLS) Policy is Fail-Open When Tenant Session Variable is Unset
- **Files:** `alembic/versions/7f955143fbe0_add_postgres_rls_policies.py`, `src/callwise/api/deps.py`, `tests/test_tenant_isolation.py`.
- **Severity:** High (Tenant Isolation / Defense-in-Depth)
- **Status:** **OPEN / LOGGED (AWAITING REMEDIATION IN PRODUCTION ARCHITECTURE)**
- **README-Safe Summary:** In the current local development configuration, the application connects to PostgreSQL as superuser `postgres` (bypassing RLS), and RLS policies are written to evaluate to true when `app.current_business_id` is unset; tenant isolation in dev is maintained at the application/API query layer while test suites verify database-level RLS by explicitly assuming the non-superuser `callwise_app` role.
- **What is wrong:**
  1. **Superuser Bypass:** In development, the application connects as `POSTGRES_USER=postgres` (a PostgreSQL superuser). Superusers bypass PostgreSQL RLS policies unconditionally by default.
  2. **Test Role Switching:** The test suites (`tests/test_tenant_isolation.py` and `tests/test_db_models_rls_isolation.py`) only pass because they explicitly execute `SET LOCAL ROLE callwise_app;` within the test transaction to drop superuser privileges to the non-superuser role created in migration `7f955143fbe0`.
  3. **Empirical Behavior Observed in `callwise_test` as `callwise_app`:**
     - **Scenario 1 (UNSET):** With `app.current_business_id` unset (`RESET app.current_business_id;`), executing `SELECT id, business_id, name FROM contacts;` returned **2 rows** (all seeded contacts across both Tenant A and Tenant B). **Proven Fail-Open.**
     - **Scenario 2 (SET to Tenant A):** With `app.current_business_id = '<Tenant A UUID>'`, the same query returned **1 row** (only Tenant A's contact).
     - **Scenario 3 (Cross-Tenant Query):** Executing `SELECT * FROM contacts WHERE business_id = '<Tenant B UUID>'` while locked to Tenant A returned **0 rows** (blocked by RLS).
  4. **Fail-Open Policy Logic in Migration `7f955143fbe0`:**
     ```sql
     USING (
         current_setting('app.current_business_id', true) IS NULL
         OR current_setting('app.current_business_id', true) = ''
         OR business_id::text = current_setting('app.current_business_id', true)
     )
     ```
     When `app.current_business_id` is unset or empty, the condition `current_setting('app.current_business_id', true) IS NULL` evaluates to `TRUE`. Any query executed under `callwise_app` that omits setting the session variable will silently read all rows across all tenants rather than returning zero rows (fail-closed).
- **Smallest Recommended Fix:**
  1. Point the production application database connection string (`DATABASE_URL`) to the non-superuser `callwise_app` role (`NOSUPERUSER NOBYPASSRLS`).
  2. Update the policy to fail-closed: require `current_setting('app.current_business_id', true)` to be non-null, non-empty, and match `business_id::text`, returning 0 rows if unset.
  3. Enforce table-level RLS on table owners: `ALTER TABLE <table_name> FORCE ROW LEVEL SECURITY;`.

---

### FINDING-13: Cross-Tenant Data Injection via Body-Supplied Foreign IDs & RLS-Blinded Phone Uniqueness Collision
- **Files Changed:**
  - `src/callwise/api/follow_ups.py`
  - `src/callwise/api/phone_numbers.py`
  - `src/callwise/api/appointments.py`
  - `src/callwise/api/widget.py`
  - `src/callwise/api/onboarding.py`
  - `tests/test_runtime_tenant_isolation.py`
- **Severity:** **CRITICAL (Cross-Tenant Association, Session Integrity & Resource Hijacking)**
- **Status:** **FIXED / VERIFIED AT RUNTIME**
- **What was wrong:**
  1. **Cross-Tenant Contact Linkage (`POST /api/follow-ups`):** `create_follow_up` directly assigned `payload.contact_id` without verifying tenant ownership (`Contact.business_id == business.id`). Allowed Tenant A to link tasks to Tenant B's contacts (`HTTP 201 Created`).
  2. **Cross-Tenant Staff Assignment (`POST /api/follow-ups` and `PATCH /api/follow-ups/{id}`):** Both handlers directly assigned `payload.assigned_to_user_id` without checking if the user belonged to the business (`Membership.user_id == id AND Membership.business_id == business.id`).
  3. **RLS-Blinded Global Phone Collision (`POST /api/phone-numbers`):** Pre-check uniqueness query under tenant-scoped RLS could not see other tenants' phone numbers. The subsequent INSERT raised an unhandled `UniqueViolationError` on `ix_phone_numbers_e164_number`, crashing with `HTTP 500`.
  4. **Status Code Misalignment on Missing Service (`POST /api/appointments`):** `book_appointment` raised `ServiceNotFoundError` when passed a foreign `service_id`, but the endpoint handler caught it under `BookingError` and returned `HTTP 400 Bad Request` instead of `HTTP 404 Not Found`.
  5. **Cross-Tenant Call Session Hijacking (`POST /api/widget/chat`, `POST /api/widget/lead`, `POST /api/onboarding/test-agent`):** Supplying a foreign `call_id` in request payloads failed to validate `Call.business_id == business.id`, allowing session collision or primary key errors.
- **How it was fixed:**
  1. In `src/callwise/api/follow_ups.py`:
     - On `POST`, validated `payload.contact_id` against `Contact.business_id == business.id` (raises `HTTP 404 "Contact '{id}' not found."` on failure).
     - On `POST` and `PATCH`, validated `payload.assigned_to_user_id` against `Membership.business_id == business.id` (raises `HTTP 404 "User '{id}' not found in business."` on failure).
  2. In `src/callwise/api/phone_numbers.py`:
     - Preserved strict tenant scoping (no tenant-bypass query).
     - Wrapped insertion in `try ... except IntegrityError: await db.rollback(); raise HTTPException(status_code=409, detail="This phone number is not available.")`.
     - Confirmed the database session remains clean, unpoisoned, and immediately usable for subsequent queries.
  3. In `src/callwise/api/appointments.py`:
     - Caught `ServiceNotFoundError` explicitly and raised `HTTP 404 Not Found`.
  4. In `src/callwise/api/widget.py` & `src/callwise/api/onboarding.py`:
     - If `payload.call_id` is supplied, validated `Call.id == payload.call_id AND Call.business_id == business.id`; if not found or foreign, raised generic `HTTP 404 "Call session not found."`.
  5. In `tests/test_runtime_tenant_isolation.py`:
     - Extended `test_body_supplied_foreign_ids_isolation` to test all create/update endpoints across both attack directions (Aarav attacking Luxe, Luxe attacking Aarav) and across Owner, Manager, and Staff roles. Verified all return 404/403 and zero records are created in DB.
     - Extended `test_phone_number_cross_tenant_collision` to test both directions, verifying strict 409 status code, generic message, zero tenant metadata disclosure, and verified database session usability after rollback. All 4 isolation test suites pass 100%.

---

### FINDING-14: Voice Agent Bound to Single Business at Startup (Resolved via Multi-Tenant Per-Call Routing)
- **Files Changed:**
  - `src/callwise/agent/voice_agent.py`
  - `src/callwise/cli.py`
  - `src/callwise/config.py`
  - `src/callwise/db/models.py`
  - `src/callwise/api/onboarding.py`
  - `alembic/versions/d8f419c83204_add_voice_sessions_table.py`
  - `Dockerfile.agent`
  - `docker-compose.yml`
  - `.env.example`
  - `tests/test_voice_per_call_routing.py`
- **Severity:** High (Multi-Tenancy & Voice Routing Architecture)
- **Status:** **FIXED / VERIFIED AT RUNTIME**
- **What was wrong:**
  The voice worker process was previously bound to a single business tenant at startup via the `BUSINESS_ID` environment variable and CLI `-b` argument (`WorkerOptions(entrypoint_fnc=entrypoint)` with automatic dispatch). Incoming voice calls or WebRTC rooms assigned to the worker could not dynamically resolve the tenant, meaning only the single pre-configured business could answer calls.
- **How it was fixed:**
  1. **Dynamic Inbound Call Resolution:** Refactored `voice_agent.py` so each incoming call inspects caller identity and attributes dynamically inside `entrypoint(ctx)`.
  2. **SIP Telephony Routing:** For legitimate SIP participants (`participant.kind == ParticipantKind.PARTICIPANT_KIND_SIP`), extracts dialed number (`sip.trunkPhoneNumber` or `sip.dialedNumber`), normalizes to E.164, and looks up `phone_numbers` table. Non-SIP participants attempting to supply `sip.*` attributes are strictly ignored and rejected.
  3. **Single Source of Truth on Web Voice (`VoiceSession`):** Created a short-lived, single-use `voice_sessions` database table. On token creation (`POST /api/onboarding/test-agent/webrtc-token`), backend creates a `VoiceSession` and embeds only `{"voice_session_id": "<uuid>"}` in token metadata. The voice worker validates the session in the DB, marking it used upon connection. Client-supplied `business_id` in room or token metadata is untrusted and ignored.
  4. **Anti-Spam Rejection Rate Limiting:** Implemented `VoiceRejectionRateLimiter` capping rejection audio playback (max 3/hour per caller, max 30/min globally) to prevent TTS credit burning. Rejected calls create 0 `Call`, 0 `Contact`, and 0 `UsageRecord` rows.
  5. **Production Startup Guard:** Added a strict guard in `start_voice_worker` that raises `RuntimeError` if `ALLOW_DEFAULT_BUSINESS` is enabled in `production` mode.
  6. **Comprehensive Automated Test Suite:** Added `tests/test_voice_per_call_routing.py` (14 tests covering SIP routing, spoof rejection, session lifecycle, rate limiting, and cross-tenant isolation). All 14 tests pass without requiring LiveKit native C/Rust libraries.




