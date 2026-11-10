# 01_ACCOUNTS_AND_ROLES.md: Test Accounts & RBAC Matrix 👥

This guide documents the role-based access control (RBAC) hierarchy in Callwise, provides a standardized set of test users across both demonstration tenants, and includes deterministic methods to create or reset them.

---

## 1. RBAC Roles & Hierarchy

Callwise implements three distinct membership roles enforced at both the API layer (via FastAPI's `require_role` dependency in `src/callwise/api/permissions.py`) and UI presentation layer:

```
┌─────────────────────────────────────────────────────────────┐
│                          OWNER                              │
│   Full tenant control, team invites, role edits, deletion    │
└──────────────────────────────┬──────────────────────────────┘
                               │ inherits
┌──────────────────────────────▼──────────────────────────────┐
│                    MANAGER / ADMIN                          │
│   Profile, operating hours, services catalog, knowledge base│
└──────────────────────────────┬──────────────────────────────┘
                               │ inherits
┌──────────────────────────────▼──────────────────────────────┐
│                          STAFF                              │
│   View activity inbox, listen to calls, review appointments │
└─────────────────────────────────────────────────────────────┘
```

### Official Product RBAC Specification vs. Current Implementation Reality

Per product specification, **Staff** is an operational reception role meant exclusively for handling day-to-day customer communication and booking. Staff members:
- **May access:** **Inbox & Activity**, **Appointments & Calendar**, **Contacts CRM**, **Follow-ups**, **Knowledge Base** (read-only), **Missed Questions**, and the **Interactive Test Agent**.
- **May NOT access or see:** **Settings**, **Team & Access**, **Phone Numbers**, **Website Widget**, or **Usage & Limits**. For staff, all sidebar navigation links to these sections must be hidden, and direct URL navigation must display an access-denied page.

The following matrix documents the **Official Product Intended Design**, the **Backend API enforcement**, the **Current UI Presentation Reality**, and the **Status Flag** (cross-referencing **FINDING-06** where the app currently deviates).

| Page / Feature Area | Action | Staff | Manager / Admin | Owner | Backend Enforcing Dependency & File | Current UI Presentation Reality | Status Flag |
|---|---|:---:|:---:|:---:|---|---|:---:|
| **Inbox & Activity** | View list & details | ✅ | ✅ | ✅ | `require_staff` in `api/inbox.py` & `api/calls.py` | Shows to all roles | Intended Design |
| **Appointments** | View calendar & list | ✅ | ✅ | ✅ | `require_staff` in `api/appointments.py` | Shows to all roles | Intended Design |
| **Appointments** | Create / Reschedule / Cancel | ✅ | ✅ | ✅ | `require_staff` in `api/appointments.py` | Staff can manage appointments | Intended Design |
| **Contacts CRM** | View contacts & notes | ✅ | ✅ | ✅ | `require_staff` in `api/contacts.py` | Shows to all roles | Intended Design |
| **Contacts CRM** | Edit contact details | ✅ | ✅ | ✅ | `require_staff` in `api/contacts.py` | Staff can update contact info | Intended Design |
| **Contacts CRM** | GDPR Data Scrub | ❌ | ❌ | ✅ | `require_owner` in `api/contacts.py` | Button shown to non-owners; backend rejects with 403 | Frontend UI Bug (FINDING-06) |
| **Follow-ups** | View & update status | ✅ | ✅ | ✅ | `require_staff` in `api/follow_ups.py` | Shows to all roles | Intended Design |
| **Knowledge Base** | View sources & QA items | ✅ | ✅ | ✅ | `require_staff` in `api/knowledge.py` | Shows to all roles | Intended Design |
| **Knowledge Base** | Upload doc / Add QA | ❌ | ✅ | ✅ | `require_manager` in `api/knowledge.py` | UI displays active forms to staff; backend rejects with 403 | Frontend UI Bug (FINDING-06) |
| **Knowledge Base** | Delete source / Re-ingest | ❌ | ✅ | ✅ | `require_manager` in `api/knowledge.py` | UI displays active buttons to staff; backend rejects with 403 | Frontend UI Bug (FINDING-06) |
| **Missed Questions** | View list | ✅ | ✅ | ✅ | `require_staff` in `api/knowledge_misses.py` | Shows to all roles | Intended Design |
| **Missed Questions** | Resolve / Ignore miss | ❌ | ✅ | ✅ | `require_manager` in `api/knowledge_misses.py` | UI displays active buttons to staff; backend rejects with 403 | Frontend UI Bug (FINDING-06) |
| **Test Agent** | Run interactive chat | ✅ | ✅ | ✅ | `require_staff` in `api/onboarding.py` | Shows to all roles | Intended Design |
| **Analytics** | View KPI dashboard | ✅ | ✅ | ✅ | `require_staff` in `api/analytics.py` | Shows to all roles | Intended Design |
| **Settings** | **View or Edit Settings** | **❌ (Hidden)** | **✅** | **✅** | `require_manager` in `api/settings.py` (writes) | Link shown to staff; forms editable; backend rejects writes with 403 | **Frontend UI Bug (FINDING-06)** |
| **Phone Numbers** | **View or Manage Numbers** | **❌ (Hidden)** | **✅** | **✅** | `require_manager` in `api/phone_numbers.py` (writes) | Link shown to staff; form active; backend rejects writes with 403 | **Frontend UI Bug (FINDING-06)** |
| **Website Widget** | **View or Manage Widget** | **❌ (Hidden)** | **✅** | **✅** | `require_manager` / `owner` in `api/widget.py` | Link shown to staff; inputs active; backend rejects writes with 403 | **Frontend UI Bug (FINDING-06)** |
| **Usage & Limits** | **View Usage & Limits** | **❌ (Hidden)** | **✅** | **✅** | `require_manager` in `api/usage.py` (intended) | Link shown to staff; metrics visible | **Frontend UI Bug (FINDING-06)** |
| **Team & Access** | **View or Manage Team** | **❌ (Hidden)** | **✅** | **✅** | `require_manager` / `owner` in `api/team.py` | Link shown to staff; loads /team; shows misleading empty state + 403 banner | **Frontend UI Bug (FINDING-06)** |
| **Audit Logs** | **View Audit Trail** | **❌ (Hidden)** | **✅** | **✅** | `require_manager` in `api/audit_logs.py` | Tab rendered to staff inside /team; backend rejects with 403 | **Frontend UI Bug (FINDING-06)** |

*(Note: In the web frontend, `manager` is labeled as "Manager / Admin" in modals and tooltips).*

---

## 2. Standardized Manual Testing Accounts

To ensure complete isolation and reproducible test execution, the following test accounts are configured across both seeded demo businesses.

### Tenant 1: BrightSmile Family Dental
- **Business UUID:** `11111111-1111-1111-1111-111111111111`
- **Timezone:** `America/New_York`

| Role | Name | Email Address | Password | User UUID |
|---|---|---|---|---|
| **Owner** | Dr. Sarah Dental | `dental.owner@test.com` | `Password123!` | `aaaaaaaa-1111-0000-0000-000000000001` |
| **Manager** | Mark Manager | `dental.manager@test.com` | `Password123!` | `aaaaaaaa-1111-0000-0000-000000000002` |
| **Staff** | Stacy Staff | `dental.staff@test.com` | `Password123!` | `aaaaaaaa-1111-0000-0000-000000000003` |

### Tenant 2: Luxe Glow Salon & Spa
- **Business UUID:** `22222222-2222-2222-2222-222222222222`
- **Timezone:** `America/Los_Angeles`

| Role | Name | Email Address | Password | User UUID |
|---|---|---|---|---|
| **Owner** | Chloe Glow | `salon.owner@test.com` | `Password123!` | `bbbbbbbb-2222-0000-0000-000000000001` |
| **Manager** | Mike Stylist | `salon.manager@test.com` | `Password123!` | `bbbbbbbb-2222-0000-0000-000000000002` |
| **Staff** | Samantha Assistant | `salon.staff@test.com` | `Password123!` | `bbbbbbbb-2222-0000-0000-000000000003` |

---

## 3. How to Create or Reset These Accounts

Because the standard `callwise seed` CLI command only creates business metadata and services (leaving user creation to onboarding or invites), Callwise provides an automated seeding script in `scripts/testing/seed_test_accounts.py`.

### Automated PowerShell Command
Run the account seeding script from the project root:

```powershell
uv run python scripts/testing/seed_test_accounts.py
```

### Expected Output
```
=== Seeding Manual Testing Accounts ===
[CREATED] User: dental.owner@test.com (Name: Dr. Sarah Dental)
  └─ Added membership: owner in 11111111-1111-1111-1111-111111111111
[CREATED] User: dental.manager@test.com (Name: Mark Manager)
  └─ Added membership: manager in 11111111-1111-1111-1111-111111111111
[CREATED] User: dental.staff@test.com (Name: Stacy Staff)
  └─ Added membership: staff in 11111111-1111-1111-1111-111111111111
[CREATED] User: salon.owner@test.com (Name: Chloe Glow)
  └─ Added membership: owner in 22222222-2222-2222-2222-222222222222
[CREATED] User: salon.manager@test.com (Name: Mike Stylist)
  └─ Added membership: manager in 22222222-2222-2222-2222-222222222222
[CREATED] User: salon.staff@test.com (Name: Samantha Assistant)
  └─ Added membership: staff in 22222222-2222-2222-2222-222222222222
=== Test Accounts Seeded Successfully ===
```
*(Verified by running: all 6 accounts created with valid Argon2id password hashes).*

---

## 4. Alternative Method: Direct UI Invitation & Signup

If you prefer to test user creation through the web interface itself:

### Method A: Public Signup Flow (Creates new Owner + new Business)
1. Open `http://localhost:3000/signup`.
2. Fill in:
   - **Business Name:** `Apex Testing Lab`
   - **Business Type:** `Dental Clinic`
   - **Your Full Name:** `Test Owner`
   - **Email:** `new.owner@example.com`
   - **Password:** `Password123!` (minimum 8 characters)
3. Click **"Create Account"**.
4. The system creates the `User` and `Business` records, assigns the `owner` role in `memberships`, establishes an authenticated session, and redirects to the `/onboarding` wizard.

### Method B: Team Member Invitation Flow (Creates Manager or Staff)
1. Sign in as an **Owner** or **Manager** (e.g. `dental.owner@test.com`).
2. Navigate to **Team & Access** (`http://localhost:3000/team`).
3. Click the **"Invite Member"** button in the top right.
4. Fill in:
   - **Email:** `invited.colleague@test.com`
   - **Role:** Select `Manager` or `Staff Member`.
5. Click **"Send Invitation"**.
6. Because `EMAIL_PROVIDER=console` is active, open the backend terminal running FastAPI (`uv run python -m uvicorn callwise.api.main:app`) to inspect the generated invitation link:
   ```
   [ConsoleEmailProvider] Sending email to: invited.colleague@test.com
   Subject: You've been invited to join BrightSmile Family Dental on Callwise
   Body: Click here to accept: http://localhost:3000/accept-invite?token=...
   ```
7. Open the invitation link in an incognito window, enter a full name and password, and complete signup.

---

## 5. Verifying Login & Tenant Switching

To confirm account setup in the web dashboard:
1. Open `http://localhost:3000/login`.
2. Enter `dental.owner@test.com` and `Password123!`.
3. Verify the top navbar shows the badge **`Owner`** and business name **`BrightSmile Family Dental`**.
4. Log out using the exit icon in the bottom left.
5. Log in as `dental.staff@test.com` and verify the badge shows **`Staff`**.

