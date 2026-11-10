# Callwise Demonstration & Live Walkthrough Guide 📞🤖

Callwise is a multi-tenant voice and chat AI receptionist built for local businesses. This guide provides end-to-end instructions for exploring the web dashboard, testing phone calls via softphones and SIP trunks, embedding the web widget, executing live API requests, and reviewing conversational transcripts.

---

## 1. Quickstart Login (Seed User)

Callwise comes pre-seeded with full demonstration businesses (Apex Dental Clinic and Serenity Spa).

- **Web Dashboard URL:** [http://localhost:3000](http://localhost:3000)
- **Login URL:** [http://localhost:3000/login](http://localhost:3000/login)
- **Demo Credentials:**
  - **Email:** `dental.owner@test.com`
  - **Password:** `Password123!`
  - *(Tip: Click the "Autofill dental.owner@test.com" button on the login screen to fill credentials instantly).*

---

## 2. Web Dashboard Tour

Once logged in, you can navigate across all tenant operations via the left sidebar:

1. **Dashboard Overview (`/`)**:
   - High-level KPIs: Total Calls Today, Appointments Booked, Messages Taken, Unanswered Inquiries.
   - Real-time upcoming schedule and recent call log preview.
   - Quick business switcher for multi-tenant account owners.

2. **Calls & Transcripts (`/calls`)**:
   - Complete call and chat history with date, caller ID, channel source badge (`phone`, `chat`, `web`), duration, and sentiment.
   - Click any call row to open the **Call Detail Drawer**:
     - View full multi-turn conversational transcript.
     - Inspect tool calls executed during the turn (e.g. `search_knowledge`, `book_appointment`, `take_message`).
     - Review itemized token usage and latency breakdowns.

3. **Appointments & Calendar (`/calendar`)**:
   - Interactive weekly scheduling view synchronized with business operating hours.
   - Direct slot booking and rescheduling.
   - Double-booking prevention enforced via PostgreSQL row-level locks (`SELECT ... FOR UPDATE`).

4. **Inbox & Follow-Ups (`/inbox`)**:
   - Voicemails, callback messages, and lead capture inquiries.
   - Status tracking (`pending`, `completed`, `dismissed`) with staff notes.

5. **Knowledge Base (`/knowledge`)**:
   - Dynamic document ingestion: Upload PDF, plain text, Markdown, or scrape public business web pages.
   - Automated semantic chunking and embedding storage in `pgvector`.
   - Live query tester to preview retrieval similarity scores before publishing.

6. **Phone Numbers & SIP Trunks (`/phone-numbers`)**:
   - Manage inbound telephone numbers assigned to your business.
   - LiveKit SIP trunk and BYO-carrier status badges.
   - Step-by-step softphone setup guide.

7. **Website Chat Widget (`/widget`)**:
   - Live interactive widget iframe mockup.
   - One-click copy for the HTML `<script>` embed snippet.
   - Customizer: Branding color pickers, bot display name, greeting message, and allowed CORS origins.
   - Regenerate public API key button.

8. **Usage & Cost Tracking (`/usage`)**:
   - Live quota meters for Minutes, Widget Chats, and Concurrent Calls.
   - 14-day daily usage history chart.
   - Itemized estimated infrastructure cost calculations (LLM, STT, TTS, SIP telephony).

9. **Team Management & RBAC (`/team`)**:
   - Invite staff members with granular roles (`owner`, `manager`, `staff`).
   - Role permission matrices enforced by PostgreSQL Row Level Security (RLS).

10. **Audit Logs (`/audit-logs`)**:
    - Immutable security audit log tracking all configuration changes, logins, knowledge uploads, and user invitations.

11. **Business Settings (`/settings`)**:
    - Timezone selector, spoken greeting, tone of voice, notification email, and live transfer phone number.
    - Weekly operating hours schedule editor with closed days and lunch break blocks.

---

## 3. Website Chat Widget Embedding

### Option A: HTML Script Embed
Add this snippet before the closing `</body>` tag on any website:

```html
<!-- Callwise AI Receptionist Chat Widget -->
<script 
  src="http://localhost:3000/widget.js" 
  data-business-key="cw_live_11111111111111111111111111111111"
  defer>
</script>
```

### Option B: Standalone Iframe Page
You can test the widget in isolation by opening:
`http://localhost:3000/widget-frame/cw_live_11111111111111111111111111111111`

---

## 4. Telephony Setup & Softphone Testing (Zero Cost)

Callwise supports live voice calls via LiveKit SIP trunks and free SIP softphones:

### Testing with Free Softphones (Linphone / Zoiper / MicroSIP):
1. Download [Linphone](https://www.linphone.org/) or [MicroSIP](https://www.microsip.org/).
2. Create a free SIP account (e.g., at `sip2sip.info` or an internal Asterisk PBX).
3. In Callwise Dashboard -> **Phone Numbers**, link the extension or phone number (e.g. `+15551234567`).
4. Start the voice worker:
   ```powershell
   uv run python -m callwise.cli run-agent --business-id 11111111-1111-1111-1111-111111111111
   ```
5. Place a test call from your softphone to the assigned number. The AI receptionist will pick up and speak the customized greeting.

---

## 5. Live REST API Testing with `curl`

### 1. Health & Readiness Check
```bash
curl -i http://localhost:8000/health
```
**Expected Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "kill_switch_active": false,
  "version": "0.1.0"
}
```

### 2. Prometheus Metrics
```bash
curl -i http://localhost:8000/metrics
```
**Expected Response:** Prometheus exposition text showing `callwise_calls_total`, `callwise_circuit_breaker_state`, and `callwise_active_calls`.

### 3. Public Widget Configuration Retrieval
```bash
curl -i http://localhost:8000/api/widget/config/cw_live_11111111111111111111111111111111
```

### 4. Interactive Public Chat Message
```bash
curl -i -X POST http://localhost:8000/api/widget/chat \
  -H "Content-Type: application/json" \
  -d '{
    "public_key": "cw_live_11111111111111111111111111111111",
    "session_id": "demo-session-123",
    "message": "What time do you open on Tuesday?"
  }'
```

### 5. Staff Authentication & Session Token
```bash
curl -i -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dental.owner@test.com",
    "password": "Password123!"
  }'
```

---

## 6. Sample Conversational Transcripts

### Scenario 1: Factual Knowledge Retrieval & Pricing
```text
Caller:  "Hi, how much does a comprehensive dental cleaning and exam cost?"
AI:      "Hello! At Apex Dental Clinic, our comprehensive dental examination, digital x-rays, and standard cleaning package is $150. For new patients, we also include a complimentary consultation. Would you like to check available appointment times?"
Caller:  "Do you accept Delta Dental insurance?"
AI:      "Yes, we accept Delta Dental PPO and Premier networks, as well as MetLife and Cigna. We are happy to verify your specific co-pay before your visit."
```

### Scenario 2: Booking an Appointment with Slot Reservation
```text
Caller:  "I'd like to book a Teeth Whitening appointment for this Friday afternoon."
AI:      "I can certainly help you with that. For Teeth Whitening on Friday, November 13th, I have openings at 1:30 PM, 2:30 PM, and 4:00 PM. Which of those times works best for you?"
Caller:  "2:30 PM sounds perfect."
AI:      "Great. May I have your full name, mobile number, and email address to confirm the reservation?"
Caller:  "My name is Sarah Connor, phone is 555-0199, email is sarah@connor.net."
AI:      "Thank you, Sarah! Your Teeth Whitening appointment is booked for Friday, November 13th at 2:30 PM with Dr. Miller. Your confirmation code is BK-8F2. We have sent confirmation details to your email and will send an SMS reminder 24 hours prior."
```

### Scenario 3: Appointment Cancellation with Caller Identity Verification
```text
Caller:  "Hi, I need to cancel my appointment."
AI:      "I can assist you with that. Could you please provide your 6-character booking code, or the full name and phone number on the reservation?"
Caller:  "The code is BK-8F2."
AI:      "To protect your privacy, could you also confirm the full name or telephone number associated with booking BK-8F2?"
Caller:  "Sarah Connor, 555-0199."
AI:      "Thank you, Sarah. I have verified your identity. I have cancelled your Teeth Whitening appointment for Friday at 2:30 PM. There is no cancellation fee as you provided more than 24 hours notice. Would you like to reschedule for a later date?"
```

### Scenario 4: Live Human Transfer with Fallback Message Taking
```text
Caller:  "I need to speak with the doctor or office manager right now about an urgent billing discrepancy."
AI:      "I completely understand. Let me check if our office manager is currently available to take your call."
[System: Executes transfer_to_human tool -> destination transfer_number dialed -> 15s timeout with no answer]
AI:      "I apologize, our office manager is currently assisting another patient and is unavailable. May I take down your contact details and a brief note so they can call you back as soon as possible?"
Caller:  "Yes, please tell them Sarah called regarding invoice #1042."
AI:      "I have noted your message regarding invoice #1042. Our office manager has received an alert and will call you back at 555-0199 promptly. Thank you for your patience!"
```

### Scenario 5: Abuse & Flood Protection (Nonsense Repetition)
```text
Caller:  "asdfghjkl"
AI:      "Are you still there? How can I help you today?"
Caller:  "qwertzuiop"
AI:      "I am having trouble understanding your request. Could you please rephrase what you need?"
Caller:  "zxcvbnm1234"
AI:      "I am having difficulty understanding your request. May I take down your name and callback number so someone from our team can follow up directly?"
[System: Triggers owner security alert email: "Security Alert: Caller Abuse Detected (+15550199)"]
```

### Scenario 6: Emergency Kill Switch Activation
```text
[System: Administrator executes `callwise killswitch enable --reason "Database migration"`]
Caller:  "Hello, I want to book a massage."
AI:      "Our automated receptionist is temporarily offline for routine maintenance. May I take down your name and callback number so our staff can follow up with you directly?"
```

---

## 7. CLI Maintenance Commands

```powershell
# 1. Run full system diagnostic
uv run python -m callwise.cli doctor

# 2. Run multi-provider comparative evaluations (Groq vs Gemini)
uv run python -m callwise.cli run-evals --compare

# 3. Execute concurrency and load testing (50 requests, concurrency 5)
uv run python -m callwise.cli load-test --requests 50 --concurrency 5

# 4. Create and restore compressed database backups
uv run python -m callwise.cli db backup --output-dir backups
uv run python -m callwise.cli db restore backups/callwise_backup_20261107_120000.sql.gz --yes

# 5. Manage emergency kill switch
uv run python -m callwise.cli killswitch status
uv run python -m callwise.cli killswitch enable --reason "Scheduled maintenance"
uv run python -m callwise.cli killswitch disable

# 6. Manage caller blocklist
uv run python -m callwise.cli blocklist add 11111111-1111-1111-1111-111111111111 "+15559998888" --reason "Telemarketing flood" --days 30
uv run python -m callwise.cli blocklist list 11111111-1111-1111-1111-111111111111
uv run python -m callwise.cli blocklist remove 11111111-1111-1111-1111-111111111111 "+15559998888"
```

