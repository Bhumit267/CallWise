# 02_PAGE_BY_PAGE.md: Frontend Web Dashboard Testing Scripts 🖥️

This guide contains complete, numbered, step-by-step manual testing scripts for every page and route in the Callwise web dashboard (`web/app/`).

> [!IMPORTANT]
> **Testing Protocol & Truthful Status Evaluation**:
> - Every test specifies the **Expected result** representing the **correct, intended product behavior**.
> - Where the app currently deviates due to an open bug, a dedicated **Known deviation** line is provided referencing the specific finding in [FINDINGS.md](FINDINGS.md).
> - If an action currently fails or produces a known deviation, record the result as **`FAIL`** in [09_RESULTS_TEMPLATE.md](09_RESULTS_TEMPLATE.md). It will flip to **`PASS`** once the interface bug is remediated.
> - **Staff Role Boundary Rule**: Staff may only access Inbox, Appointments, Contacts, Follow-ups, Knowledge Base (read-only), Missed Questions, and Test Agent. Staff must **not** see or open Settings, Team & Access, Phone Numbers, Website Widget, or Usage & Limits (sidebar links hidden; direct URL navigation must show an access-denied page).

---

## Pre-Test Setup & Credentials

Ensure the application stack is active:
- Backend: `http://localhost:8000` (FastAPI)
- Frontend: `http://localhost:3000` (Next.js)

Seeded Test Users (BrightSmile Family Dental):
- **Owner:** `dental.owner@test.com` / `Password123!`
- **Manager:** `dental.manager@test.com` / `Password123!`
- **Staff:** `dental.staff@test.com` / `Password123!`

---

## Route 1: Authentication & Public Pages

### PAGE-AUTH-01: Sign In Page (`/login`)
- **URL:** `http://localhost:3000/login`
- **Permitted Roles:** Public (unauthenticated)
- **Purpose:** Secure email and password authentication with Argon2id verification.

#### Test Steps
1. Open `http://localhost:3000/login` in an Incognito/Private browser window.
2. **Visual Inspection:** Verify the Callwise bot logo, "Sign in to Callwise", Email, Password fields, and "Sign in" button render cleanly.
3. **Negative Test (Invalid Password):** Enter `dental.owner@test.com` and password `WrongPassword999!`. Click **"Sign in"**.
   - **Expected result:** Form submission displays red alert: *"Invalid email or password"*. User remains on `/login`.
4. **Negative Test (Malformed Email):** Enter `notanemail` and click **"Sign in"**.
   - **Expected result:** HTML5 / client validation blocks submission requiring a valid email address.
5. **Brute-Force Rate Limiting Test:** Attempt 5 incorrect logins consecutively.
   - **Expected result:** On the 5th failed attempt, backend rate limiter engages. An error banner displays: *"Too many failed login attempts. Please try again in 900 seconds."*
6. **Positive Test (Valid Login):** Enter `dental.owner@test.com` and `Password123!`. Click **"Sign in"**.
   - **Expected result:** Loading spinner appears briefly, session cookie is established, and user is redirected to `/inbox`.
7. **Demo Autofill Inspection:**
   - **Expected result:** A production-ready login page must use generic demo credentials.
   - **Known deviation (FINDING-01):** Page currently displays a helper button *"Autofill dental.owner@test.com"* containing a personal email address.

---

### PAGE-AUTH-02: Sign Up Page (`/signup`)
- **URL:** `http://localhost:3000/signup`
- **Permitted Roles:** Public
- **Purpose:** Self-serve onboarding registration for new business owners.

#### Test Steps
1. Navigate to `http://localhost:3000/signup`.
2. **Visual Inspection:** Verify fields for Business Name, Your Full Name, Work Email, and Password.
3. **Negative Test (Short Password):** Enter valid business details, email `newowner@test.com`, and password `short`. Click **"Create Account"**.
   - **Expected result:** Form validation requires minimum 8 characters.
4. **Positive Test (New Tenant Creation):** Enter:
   - Full Name: `Dr. Robert Crown`
   - Business Name: `Radiant Smile Studio`
   - Business Type: `Dental Clinic`
   - Work Email: `robert.crown@test.com`
   - Password: `Password123!`
5. Click **"Create Account"**.
   - **Expected result:** User and Business records created; user is assigned `owner` role, session cookie is set, and user is redirected to `/onboarding`.

---

### PAGE-AUTH-03: Password Reset Request & Confirmation (`/forgot-password`, `/reset-password`)
- **URL:** `http://localhost:3000/forgot-password`
- **Permitted Roles:** Public
- **Purpose:** Self-serve password reset via single-use expiring cryptographic token.

#### Test Steps
1. Open `http://localhost:3000/forgot-password`.
2. Enter `dental.owner@test.com` and click **"Send Reset Instructions"**.
   - **Expected result:** Green success banner appears: *"If an account exists with this email, password reset instructions have been sent."*
3. Check the FastAPI backend terminal console for the simulated email:
   - Note the reset link containing token: `http://localhost:3000/reset-password?token=...`
4. Open the reset URL. Enter a new password: `NewPassword123!`. Click **"Update Password"**.
   - **Expected result:** Password updates successfully; user is redirected to `/login` with success banner.

---

## Route 2: Operational Dashboard (Staff, Manager & Owner Permitted)

### PAGE-INBOX-01: Activity Inbox & Call Audio Playback (`/inbox`)
- **URL:** `http://localhost:3000/inbox`
- **Permitted Roles:** Staff, Manager, Owner
- **Purpose:** Unified chronological feed of all inbound telephone calls and callback messages taken by the AI receptionist.

#### Test Steps
1. Log in as `dental.staff@test.com`.
2. **Multi-Role Test Pass:**
   - Log in as **Staff**: Page renders activity feed cleanly.
   - Log in as **Manager**: Page renders activity feed cleanly.
   - Log in as **Owner**: Page renders activity feed cleanly.
3. **Empty State Verification:**
   - If no calls exist yet, verify the feed displays an informative empty card: *"No activity recorded yet"* with guidance on placing test calls.
4. **Call Detail Drawer:**
   - Click any call row in the list.
   - **Expected result:** A right-hand slide-over drawer opens displaying Call Metadata (Caller ID, Duration, Started/Ended timestamps), AI Executive Summary, Turn-by-Turn transcript, and Audio Player.
5. **Audio Player Inspection:**
   - **Expected result:** When `audio_url` is null (standard for LiveKit text-eval calls), the player displays an explicit informational badge: *"Audio Recording Not Available"*.
6. **Search & Filter:**
   - Type a phone number into the search filter input.
   - **Expected result:** Table filters in real-time to matching caller rows.

---

### PAGE-APPT-01: Appointments Calendar & Booking Management (`/appointments`)
- **URL:** `http://localhost:3000/appointments`
- **Permitted Roles:** Staff, Manager, Owner
- **Purpose:** Full visual calendar and list view of customer bookings with cancellation and rescheduling controls.

#### Test Steps
1. Log in as `dental.staff@test.com`.
2. **Multi-Role Test Pass:**
   - **Staff**: Can view calendar, toggle week/month, view appointment details, and reschedule/cancel bookings.
   - **Manager**: Identical full appointment operational capabilities.
   - **Owner**: Identical full appointment operational capabilities.
3. **Manual Appointment Creation:**
   - Click **"New Appointment"** button.
   - Modal opens with Customer Name, Phone Number, Service selection, and Date/Time picker.
   - Enter `Marcus Vance`, `555-0199`, select `Routine Cleaning & Exam`, pick a future slot. Click **"Book Appointment"**.
   - **Expected result:** Modal closes; appointment appears on the calendar grid and list view.
4. **Reschedule Appointment:**
   - Click Marcus Vance's appointment card. Click **"Reschedule"**. Pick a different available time.
   - **Expected result:** Appointment moves to the new slot and updates status.
5. **Cancel Appointment:**
   - Click **"Cancel Appointment"**. Confirm prompt.
   - **Expected result:** Status badge updates to `cancelled` with red styling.

---

### PAGE-CRM-01: Contacts CRM & Caller History (`/contacts`)
- **URL:** `http://localhost:3000/contacts`
- **Permitted Roles:** Staff, Manager, Owner (GDPR Data Scrub restricted to Owner)
- **Purpose:** Customer relationship directory tracking caller history, appointment counts, and staff notes.

#### Test Steps
1. Log in as `dental.staff@test.com`.
2. **Staff Access Pass:**
   - Staff can search contacts, click into contact profiles, view call history, and update notes.
3. **GDPR Data Scrub Role Restriction:**
   - Click into a contact profile. Notice the **"Delete Customer Data (GDPR)"** button.
   - Click the button as **Staff**.
   - **Expected result:** Button should either be hidden from staff or clicking it displays an Access Denied message.
   - **Known deviation (FINDING-06):** Button is currently clickable by staff; upon clicking, the backend rejects the action with a red banner: *"Action requires at least 'owner' role. Your role is 'staff'."*
4. **Owner GDPR Test:**
   - Log out and log in as `dental.owner@test.com`. Navigate to the contact profile. Click **"Delete Customer Data (GDPR)"**.
   - **Expected result:** Confirmation dialog opens. Upon confirmation, all customer records and PII are permanently purged.

---

### PAGE-FOL-01: Follow-ups & Callback Tasks (`/follow-ups`)
- **URL:** `http://localhost:3000/follow-ups`
- **Permitted Roles:** Staff, Manager, Owner
- **Purpose:** Task board tracking pending customer callbacks generated when callers request a human message.

#### Test Steps
1. Log in as `dental.staff@test.com`.
2. **Visual Inspection:** Verify tabs or columns for `Pending` and `Completed` follow-ups.
3. **Create Follow-up:**
   - Click **"Add Task"**. Enter: Customer `Elena Rostova`, Phone `555-0188`, Notes: *"Inquired about teeth whitening sensitivity"*.
   - **Expected result:** Task card appears under `Pending`.
4. **Complete Follow-up:**
   - Click the checkmark icon on Elena's card.
   - **Expected result:** Card moves to `Completed` section with strikethrough or green check badge.

---

### PAGE-KB-01: Knowledge Base Documents & Q&A (`/knowledge`)
- **URL:** `http://localhost:3000/knowledge`
- **Permitted Roles:** Staff (Read-Only), Manager & Owner (Full Ingestion & Edit)
- **Purpose:** Multi-source knowledge repository supporting PDF/TXT/MD uploads, web crawler URL ingestion, and manual Q&A pairs.

#### Test Steps
1. Log in as `dental.staff@test.com`.
2. **Staff Read-Only Access Pass:**
   - Verify staff can see existing ingested documents, chunk counts, and Q&A snippets.
3. **Staff Write Action Rejection Test:**
   - In the Q&A editor, enter a new Question: *"Do you accept walk-ins?"* and Answer: *"We recommend appointments but accommodate emergencies."* Click **"Save Q&A"**.
   - **Expected result:** Form controls and upload buttons should be disabled or hidden for staff.
   - **Known deviation (FINDING-06):** Forms and buttons are active. Clicking Save triggers a red error banner: *"Action requires at least 'manager' role. Your role is 'staff'."*
4. **Manager Ingestion Test:**
   - Log out and log in as `dental.manager@test.com`.
   - Click **"Add Q&A"**. Save Question and Answer.
   - **Expected result:** Success notification displays; Q&A snippet appears in the list.

---

### PAGE-MISS-01: Missed Questions Queue (`/missed-questions`)
- **URL:** `http://localhost:3000/missed-questions`
- **Permitted Roles:** Staff (Read-Only), Manager & Owner (Resolve & Ignore)
- **Purpose:** Review inquiries where the AI receptionist could not find relevant knowledge (similarity < 0.45 cutoff).

#### Test Steps
1. Log in as `dental.staff@test.com`.
2. **Staff Read-Only Access:** Staff can review missed customer questions and frequencies.
3. **Staff Action Rejection:** Click **"Ignore"** or **"Add Answer"** on a missed query.
   - **Expected result:** Action buttons disabled or hidden for staff.
   - **Known deviation (FINDING-06):** Action buttons are clickable; backend returns 403 error.
4. **Manager Resolve Test:**
   - Log in as `dental.manager@test.com`. Click **"Add Answer"** on a question. Enter the answer and click **"Resolve & Ingest"**.
   - **Expected result:** New Q&A document is created in knowledge base and item disappears from missed queue.

---

### PAGE-TEST-01: Interactive Test Agent Simulator (`/test-agent`)
- **URL:** `http://localhost:3000/test-agent`
- **Permitted Roles:** Staff, Manager, Owner
- **Purpose:** Full browser conversational simulator running against the live backend `TextAgent` with optional Web Speech TTS audio.

#### Test Steps
1. Log in as `dental.staff@test.com`.
2. Navigate to `http://localhost:3000/test-agent`.
3. **Greeting Inspection:** Verify initial greeting from BrightSmile Family Dental is pre-loaded.
4. **Conversational Turn (Knowledge):**
   - Type: *"What are your routine cleaning prices?"* and press Enter.
   - **Expected result:** Agent replies with accurate pricing ($120.00). Turn latency badge displays (e.g. `1240 ms`).
5. **Speech Audio Synthesis Toggle:**
   - Toggle the **"Voice Audio (TTS)"** switch to ON.
   - Type: *"What are your operating hours?"*
   - **Expected result:** Agent responds in text and the browser speaks the reply aloud via Web Speech API.
6. **Reset Session:** Click **"Reset Session"**.
   - **Expected result:** Conversation transcript clears and restarts with initial greeting.

---

### PAGE-ANALYTICS-01: Business Intelligence & KPI Analytics (`/analytics`)
- **URL:** `http://localhost:3000/analytics`
- **Permitted Roles:** Staff, Manager, Owner
- **Purpose:** Performance analytics, call volume charts, booking conversion rates, and peak hour distribution.

#### Test Steps
1. Log in as `dental.staff@test.com`.
2. **Visual Inspection:** Verify metric cards render: Total Inbound Calls, Appointments Booked, Transfer Rate, Knowledge Misses.
3. **Chart Rendering:** Verify Recharts graphs render without console errors (Call Volume over Time, Peak Hours Bar Chart).
4. **Time Range Filter:** Toggle between `7 Days`, `30 Days`, and `All Time`.
   - **Expected result:** Metrics refresh and update dynamically.

---

## Route 3: Restricted Management Pages (Manager & Owner Only; Hidden from Staff)

### PAGE-SETTINGS-01: Business Profile, Hours & Service Catalog (`/settings`)
- **URL:** `http://localhost:3000/settings`
- **Permitted Roles:** Manager, Owner (STAFF MUST BE BLOCKED)
- **Purpose:** Business profile configuration, AI greeting, operating hours schedule, and services pricing catalog.

#### Test Steps
1. **Staff Access Boundary Test:**
   - Log in as `dental.staff@test.com`.
   - **Expected result:** "Settings" link is **hidden** from the sidebar. Navigating directly to `http://localhost:3000/settings` displays an **Access Denied** page.
   - **Known deviation (FINDING-06):** Sidebar displays "Settings" to staff. Page loads fully with editable inputs. Clicking "Save Voice Profile" fails with a red 403 error: *"Action requires at least 'manager' role. Your role is 'staff'."*
2. **Manager Configuration Test:**
   - Log in as `dental.manager@test.com`.
   - Open `/settings`. Click the **"Operating Hours"** tab.
   - Change Friday closing time from `13:00` to `15:00`. Click **"Save Operating Hours"**.
   - **Expected result:** Success toast appears: *"Operating hours updated successfully"*.
3. **Service Catalog Management:**
   - Click **"Service Catalog"** tab. Click **"Add Service"**.
   - Enter: Name `Dental Sealants`, Duration `30`, Price `65.00`. Click **"Save Service"**.
   - **Expected result:** New service appears in the active service table.

---

### PAGE-PHONE-01: Inbound Phone Numbers Mapping (`/phone-numbers`)
- **URL:** `http://localhost:3000/phone-numbers`
- **Permitted Roles:** Manager, Owner (STAFF MUST BE BLOCKED)
- **Purpose:** Map inbound E.164 phone numbers to the business tenant for LiveKit SIP telephony routing.

#### Test Steps
1. **Staff Access Boundary Test:**
   - Log in as `dental.staff@test.com`.
   - **Expected result:** "Phone Numbers" link is **hidden** from sidebar. Navigating to `/phone-numbers` displays **Access Denied**.
   - **Known deviation (FINDING-06):** Link is visible. Page loads and displays an active "Add Phone Number" button. Submitting form triggers a red 403 error.
2. **Manager Mapping Test:**
   - Log in as `dental.manager@test.com`.
   - Click **"Add Phone Number"**.
   - Enter Number: `+16175550199`, Provider: `livekit_sip`, Label: `Main Inbound Line`. Click **"Save Number"**.
   - **Expected result:** Number appears in active telephone routing table with green active badge.

---

### PAGE-WIDGET-01: Website Chat Widget Configuration (`/widget`)
- **URL:** `http://localhost:3000/widget`
- **Permitted Roles:** Manager, Owner (STAFF MUST BE BLOCKED; Key rotation Owner-only)
- **Purpose:** Customise chat widget colors, greeting, allowed domain origins, and preview live embed.

#### Test Steps
1. **Staff Access Boundary Test:**
   - Log in as `dental.staff@test.com`.
   - **Expected result:** "Website Widget" link is **hidden** from sidebar. Direct URL displays **Access Denied**.
   - **Known deviation (FINDING-06):** Link is visible. Inputs are editable. Clicking save triggers a 403 error.
2. **Manager Configuration Test:**
   - Log in as `dental.manager@test.com`.
   - Change Primary Color to `#0284c7` (Sky Blue). Change Widget Greeting to *"Hello! How can BrightSmile help you today?"*.
   - Click **"Save Widget Settings"**.
   - **Expected result:** Save succeeds. Embedded live preview updates in real-time.
3. **Owner Public Key Rotation Test:**
   - As **Manager**, attempt to click **"Regenerate Public Key"**.
     - **Expected result:** Button disabled or hidden for Manager.
     - **Known deviation (FINDING-06):** Button is active; clicking triggers 403 error (*"Action requires at least 'owner' role"*).
   - Log in as **Owner** (`dental.owner@test.com`). Click **"Regenerate Public Key"** and confirm.
     - **Expected result:** New cryptographic `pk_live_...` key is issued immediately.

---

### PAGE-USAGE-01: Usage & Quota Limits (`/usage`)
- **URL:** `http://localhost:3000/usage`
- **Permitted Roles:** Manager, Owner (STAFF MUST BE BLOCKED)
- **Purpose:** Track monthly telephony minutes, chat sessions, LLM tokens, and estimated infrastructure costs.

#### Test Steps
1. **Staff Access Boundary Test:**
   - Log in as `dental.staff@test.com`.
   - **Expected result:** "Usage & Limits" link is **hidden** from sidebar. Direct URL displays **Access Denied**.
   - **Known deviation (FINDING-06):** Link is visible and usage statistics are displayed to staff.
2. **Manager Usage Inspection:**
   - Log in as `dental.manager@test.com`.
   - Verify Progress Gauges:
     - Voice Call Minutes: Used vs. Cap (e.g. `0 / 500 min`)
     - Web Chat Sessions: Used vs. Cap (e.g. `0 / 1000 chats`)
     - Estimated Monthly Cost ($)
   - Verify Recent Itemized Usage Table displays call sessions with tokens and cost calculations.

---

### PAGE-TEAM-01: Team Management, Roles & Security Audit Trail (`/team`)
- **URL:** `http://localhost:3000/team`
- **Permitted Roles:** Owner (Full control), Manager (View members & invites), STAFF MUST BE BLOCKED.
- **Purpose:** Team invitations, role assignments (Staff, Manager, Owner), member removal, and immutable security audit logs.

#### Test Steps
1. **Staff Access Boundary Test:**
   - Log in as `dental.staff@test.com`.
   - **Expected result:** "Team & Access" link is **hidden** from sidebar. Direct URL navigation to `/team` displays a clean **Access Denied / Restricted to Managers and Owners** page.
   - **Known deviation (FINDING-06):** Link is visible. Navigating to `/team` displays:
     - Counters showing *"Active Team & Invites: 0"*
     - Table showing *"No active members found"*
     - An active *"Invite Member"* button
     - A red error banner: *"Action requires at least 'manager' role. Your role is 'staff'."*
2. **Manager Access Test:**
   - Log in as `dental.manager@test.com`.
   - **Expected result:** Manager can view the active team members list and pending invitations. Manager cannot edit roles or remove members.
3. **Owner Team Management Test:**
   - Log in as `dental.owner@test.com`.
   - Click **"Invite Member"**. Enter Email: `new.colleague@test.com`, Role: `Staff Member`. Click **"Send Invitation"**.
   - **Expected result:** Invitation appears under "Pending Invitations".
4. **Owner Role Modification:**
   - Locate `dental.staff@test.com` in the member table. Click **"Edit Role"**. Select `Manager / Admin`. Click **"Save Role"**.
   - **Expected result:** Stacy's role badge updates to purple `Manager` tag.
5. **Security Audit Log Tab:**
   - Click **"Security Audit Logs"** tab.
   - **Expected result:** Chronological audit trail displays timestamp, actor email, action type (e.g. `invite_team_member`, `update_member_role`), and IP address.

---

## Route 4: Public Embedded Chat Widget

### PAGE-WIDGET-FRAME-01: Standalone & Embedded Widget View (`/widget-frame/[key]`)
- **URL:** `http://localhost:3000/widget-frame/[key]` (where `[key]` is tenant's public key)
- **Permitted Roles:** Public (unauthenticated)
- **Purpose:** Embeddable iframe providing the customer-facing chat receptionist on external websites.

#### Test Steps
1. Retrieve the public key for BrightSmile Family Dental (from `/widget` page or API).
2. Open in browser: `http://localhost:3000/widget-frame/<public_key>`.
3. **Visual Inspection:** Verify tenant branding, custom header color, business title, and avatar icon render.
4. **Interactive Chat:**
   - Type: *"Hi, do you do teeth whitening?"* and click Send.
   - **Expected result:** Assistant replies within 2 seconds: *"Yes, we offer Zoom In-Office Teeth Whitening for $350.00."*
5. **Lead Capture Form:**
   - Click **"Book / Request Contact"** or trigger lead capture prompt.
   - Enter Name: `Daniel Miller`, Email: `daniel@example.com`, Phone: `555-0177`. Submit.
   - **Expected result:** Success confirmation displays. Contact record is created in the dashboard CRM.
6. **Negative Test (Invalid Public Key):**
   - Navigate to `http://localhost:3000/widget-frame/pk_invalid_random_key_12345`.
   - **Expected result:** Page displays an informative error card: *"Invalid or inactive chat widget key."* No chat session is initiated.

---

## Responsive Viewport & Accessibility Checklist

For every page listed above, execute these two universal checks:

### 1. Mobile-Sized Window Test (375px width / iPhone SE)
1. Open Chrome DevTools (`F12`) and toggle Device Toolbar (`Ctrl+Shift+M`). Select **iPhone SE** (375x667).
2. **Sidebar Behavior:** Verify the desktop sidebar collapses into a hamburger menu button. Clicking the hamburger opens a slide-over navigation drawer. Tapping outside the drawer closes it cleanly.
3. **Table Responsiveness:** Verify tables in Inbox, Appointments, and Contacts either stack into clean cards or scroll horizontally without breaking the viewport layout.
4. **Form Inputs:** Verify all text inputs and dropdowns are full-width and touch-friendly (minimum 44px tap target height).

### 2. Keyboard Navigation Test (Tab / Enter / Escape)
1. Press `Tab` repeatedly from page load.
2. **Focus Visibility:** Confirm an accessible outline or focus ring highlights every interactive button, input field, and link.
3. **Modal Control:**
   - Open any modal (e.g. "New Appointment" or "Invite Member") using `Enter`.
   - Press `Tab` to navigate through fields. Confirm focus is trapped inside the modal.
   - Press `Escape` on the keyboard: modal must close immediately.

