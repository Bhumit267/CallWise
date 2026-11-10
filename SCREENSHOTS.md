# Callwise Web Dashboard Screen Checklist 📸

This document details all 12 frontend views in the Callwise web application ([`web/`](file:///e:/Callwise/web)), documenting the route, UI purpose, interactive components, and verification status.

---

## Screen Checklist

| # | Screen Name | Route | Purpose & Key Features | Status |
|---|---|---|---|---|
| 1 | **Sign In / Authentication** | `/login` | Email/password login, demo autofill shortcut, show/hide password toggle, lockout notice. | Verified |
| 2 | **Dashboard Overview** | `/` | Operational KPIs (Calls Today, Bookings, Messages, Misses), upcoming appointments, recent calls. | Verified |
| 3 | **Calls & Transcripts** | `/calls` | Call log with search, duration, channel source badges (`phone`, `chat`, `web`), sentiment tags. | Verified |
| 4 | **Call Detail Drawer** | Slide-over drawer on `/calls` | Multi-turn conversational transcript, tool execution inspector, latency and token metrics. | Verified |
| 5 | **Appointments Calendar** | `/calendar` | Weekly view, business operating hours grid, status filters, double-booking prevention. | Verified |
| 6 | **Inbox & Voicemail Follow-ups** | `/inbox` | Customer callback requests, missed calls, lead details, status toggle (pending, resolved). | Verified |
| 7 | **Knowledge Base Manager** | `/knowledge` | Multi-file document upload (PDF, TXT, MD, URLs), chunk viewer, semantic search tester. | Verified |
| 8 | **Phone Numbers & SIP Trunks** | `/phone-numbers` | Provisioned E.164 phone numbers, provider badges, softphone setup instructions. | Verified |
| 9 | **Website Chat Widget** | `/widget` | Live interactive widget mockup, one-click script embed copy, theme color & origin editor. | Verified |
| 10 | **Usage & Cost Tracking** | `/usage` | Minute/chat/concurrency progress meters, 14-day history chart, estimated cost tables. | Verified |
| 11 | **Team & RBAC Management** | `/team` | User invitation modal, role assignments (`owner`, `manager`, `staff`), member removal. | Verified |
| 12 | **Security Audit Logs** | `/audit-logs` | Immutable log of administrative actions, logins, configuration updates, and exports. | Verified |
| 13 | **Business Settings** | `/settings` | Operating hours schedule editor, tone of voice, greeting, transfer number, timezone. | Verified |
| 14 | **Standalone Widget Frame** | `/widget-frame/[key]` | Isolated iframe chat client for zero-dependency website embedding. | Verified |

---

## Detailed Screen Specifications

### 1. Sign In (`/login`)
- **Elements**: Callwise robot branding, Email and Password inputs, "Remember me" option, "Forgot password?" link.
- **Convenience Features**: 
  - "Autofill dental.owner@test.com" button for instantaneous local testing.
  - Show/Hide password toggle icon.
  - Rate limiting notice when maximum failed attempts is reached.

### 2. Dashboard Overview (`/`)
- **Metric Cards**:
  - *Total Inbound Calls* (with week-over-week trend)
  - *Appointments Booked*
  - *Messages Taken & Follow-ups Needed*
  - *Knowledge Misses* (unanswered queries requiring documentation)
- **Widgets**:
  - Today's Appointments Timeline
  - Recent Call Activity with direct drawer inspection

### 3. Calls & Transcripts (`/calls`)
- **Filters**: Date range picker, search by caller name or phone, channel filter (`All`, `Phone`, `Chat Widget`).
- **Data Table**:
  - Caller Name & Masked Phone
  - Channel badge: `phone` (green icon), `chat` (blue icon)
  - Timestamp & Duration
  - Sentiment & Summary snippet
- **Actions**: Audio recording playback button, "View Transcript" drawer opener.

### 4. Call Detail Drawer
- **Components**:
  - Slide-out panel from the right edge with blur backdrop.
  - Chat bubbles color-coded by speaker (Caller = Gray/Left, AI Receptionist = Blue/Right).
  - Expandable Tool Call badges (shows arguments and tool output JSON).
  - Telephony & AI metadata: Latency (ms), Tokens used, LLM Provider, TTS Provider.

### 5. Appointments & Calendar (`/calendar`)
- **Layout**: 7-day calendar view with 30-minute slot intervals.
- **Visuals**:
  - Operating hours rendered in white; closed hours rendered in light gray hatching.
  - Booked appointments colored by service category.
- **Modals**:
  - New Appointment dialog (service select, customer details, conflict validation).
  - Appointment details dialog (reschedule, cancel with confirmation).

### 6. Knowledge Base Manager (`/knowledge`)
- **Actions**:
  - "Upload Document" drag-and-drop zone supporting `.pdf`, `.txt`, `.md`.
  - "Scrape Website URL" modal with SSRF protection.
- **Inspection**:
  - Document cards with chunk count, upload timestamp, and status.
  - "Search Test" input to preview top-3 semantic vector matches with similarity percentages.

### 7. Website Chat Widget Customizer (`/widget`)
- **Interactive Preview**:
  - Full-fidelity floating widget launcher and chat window rendered on the right side of the screen.
- **Settings Form**:
  - Public Key display with copy and regenerate buttons.
  - HTML Embed code snippet with one-click copy.
  - Bot Display Name (e.g. "Apex Receptionist").
  - Primary Theme Color picker (hex value with preview).
  - Allowed Domains (comma-separated origins for CORS security).

### 8. Usage & Cost Tracking (`/usage`)
- **Progress Gauges**:
  - Voice Minutes Used vs. Monthly Cap (e.g. 142 / 500 min).
  - Chat Widget Sessions vs. Monthly Cap (e.g. 48 / 1,000 sessions).
  - Max Concurrent Calls.
- **Cost Table**: Itemized cost estimates per call based on token counts and telephony duration.

