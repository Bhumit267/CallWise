# Callwise Manual Testing Kit 🧪

Welcome to the **Callwise Manual Testing Kit**. This comprehensive guide provides step-by-step instructions for manually testing every web page, API endpoint, voice/chat interaction, background daemon, security boundary, and resilience safeguard in Callwise.

Calls are **INBOUND ONLY**: you place calls to the business; the business never makes outbound telemarketing calls to you.

---

## Testing Principles & Rules
1. **Never guess:** Every route, parameter, CLI option, and test case is mapped directly to actual code in `src/callwise/` and `web/`.
2. **Zero code changes:** This kit tests the existing system as built. Any bugs, edge cases, or gaps identified during testing are logged in [FINDINGS.md](FINDINGS.md).
3. **Reproducible PowerShell commands:** All terminal commands are formatted specifically for Windows PowerShell and are copy-pasteable.
4. **Isolated fake data:** Only synthetic demonstration data is used. Never use real personal phone numbers or payment information.
5. **No plain-text secrets:** Configuration steps reference environment variable names only (`.env`).

---

## Kit Structure & Execution Order

We recommend following the kit in sequence from setup to final resilience checks:

| Step | File | Purpose | Est. Time |
|:---:|:---|:---|:---:|
| **0** | [00_SETUP.md](00_SETUP.md) | Clean-machine prerequisites, DB migrations, seed data, smoke test & reset procedures. | ~15 min |
| **1** | [01_ACCOUNTS_AND_ROLES.md](01_ACCOUNTS_AND_ROLES.md) | Test user accounts across 2 tenants for `owner`, `manager`, and `staff` roles. | ~10 min |
| **2** | [02_PAGE_BY_PAGE.md](02_PAGE_BY_PAGE.md) | Comprehensive test scripts for all 21 frontend routes, empty/loading/error states, mobile & keyboard. | ~45 min |
| **3** | [03_API_ENDPOINTS.md](03_API_ENDPOINTS.md) | PowerShell and Swagger tests for all 59 FastAPI endpoints, positive & negative cases. | ~35 min |
| **4** | [04_VOICE_AND_CHAT_FLOWS.md](04_VOICE_AND_CHAT_FLOWS.md) | Inbound conversational test flows (knowledge, booking, cancellation, lockout, prompts, softphone). | ~40 min |
| **5** | [05_BACKGROUND_JOBS_AND_EMAIL.md](05_BACKGROUND_JOBS_AND_EMAIL.md) | Testing ingestion workers, appointment reminder daemons, and email notifications. | ~20 min |
| **6** | [06_SECURITY_AND_ISOLATION.md](06_SECURITY_AND_ISOLATION.md) | Tenant isolation, RBAC role enforcement, CSRF, XSS, SSRF, and rate limiting validation. | ~30 min |
| **7** | [07_LIMITS_AND_RESILIENCE.md](07_LIMITS_AND_RESILIENCE.md) | Circuit breaker, kill switch, usage caps, database disconnect, and backup/restore drills. | ~25 min |
| **—** | [08_CHECKLIST.md](08_CHECKLIST.md) | Master unified checkbox list indexed with persistent IDs (e.g., `PAGE-INBOX-01`, `API-APPT-05`). | Reference |
| **—** | [09_RESULTS_TEMPLATE.md](09_RESULTS_TEMPLATE.md) | Test result logging matrix, defect severity matrix, and bug report submission template. | Reference |
| **—** | [FINDINGS.md](FINDINGS.md) | Discrepancies and gaps found in the codebase during testing kit compilation. | Reference |

**Total Estimated Duration:** ~3.5 to 4 hours for complete end-to-end verification.

---

## Status Legend

When executing tests and logging results in [09_RESULTS_TEMPLATE.md](09_RESULTS_TEMPLATE.md), use these standardized status tags:

- **`PASS`**: The feature behaved exactly as specified in the test script. All expected UI elements, HTTP status codes, and database updates matched.
- **`FAIL`**: The feature failed to work, produced an unexpected error/crash, or violated security/isolation requirements. Log details in [FINDINGS.md](FINDINGS.md).
- **`BLOCKED`**: The test could not be executed because a prerequisite service, credential, or dependent feature failed earlier.
- **`SKIP`**: The test requires optional external hardware or paid third-party credentials (e.g., live Twilio SIP trunk) not currently provisioned in your local environment.

---

## One-Hour Express Pass ("Top 20 Most Critical Tests")

If you have limited time and need to verify the core functionality of Callwise within **60 minutes**, run these 20 prioritized tests:

1. **`SETUP-01`**: Start Docker PostgreSQL and run `callwise doctor` diagnostic.
2. **`SETUP-02`**: Seed database tenants with `callwise seed`.
3. **`AUTH-01`**: Log into dashboard at `http://localhost:3000/login` with `dental.owner@test.com`.
4. **`PAGE-INBOX-01`**: View Unified Inbox feed of calls and callback messages.
5. **`PAGE-APPT-01`**: View Appointments calendar and table view.
6. **`PAGE-KB-01`**: Verify ingested knowledge documents and chunk counts.
7. **`PAGE-TEST-01`**: Open Test Agent console and complete an interactive greeting turn.
8. **`VOICE-KNOW-01`**: Inquire about business services/pricing and verify accurate RAG retrieval.
9. **`VOICE-KNOW-02`**: Ask an unanswerable question and verify polite decline + knowledge miss logged.
10. **`VOICE-BOOK-01`**: Book a 30-minute appointment; verify 6-character code (`BK-XXXXXX`) generated.
11. **`VOICE-BOOK-02`**: Attempt to double-book the same slot; verify collision prevention.
12. **`VOICE-VERIF-01`**: Cancel the appointment with correct booking code and phone number.
13. **`VOICE-VERIF-02`**: Attempt cancellation with wrong code 3 times; verify session lockout.
14. **`API-SMOKE-01`**: Execute `scripts/testing/api_smoke.ps1` against FastAPI backend.
15. **`SEC-ISO-01`**: Attempt to read Tenant B's appointments using Tenant A's session cookie.
16. **`SEC-RBAC-01`**: Attempt to invite a new team member using a `staff` role account.
17. **`WIDGET-01`**: Load public chat widget and exchange a message with the receptionist.
18. **`JOBS-INGEST-01`**: Upload a new text snippet in Knowledge Base and verify worker processing.
19. **`RESIL-KILL-01`**: Enable `callwise killswitch enable` and verify all inbound queries divert to message-taking.
20. **`RESIL-BACKUP-01`**: Execute `callwise db backup` to verify database dump creation.

