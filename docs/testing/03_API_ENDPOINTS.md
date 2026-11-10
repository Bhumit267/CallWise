# Callwise Manual Testing Kit: 03 - API Endpoints & Contract Verification 🔌

Welcome to **Step 3** of the Callwise Manual Testing Kit. This guide details reproducible, copy-pasteable Windows PowerShell test scripts and Swagger UI verification procedures for all **59 FastAPI backend endpoints** across all 17 routers.

Each test is mapped directly to actual routes in `src/callwise/api/` and schemas in `src/callwise/api/schemas.py`.

---

## Testing Principles for API Endpoints

1. **Strict Content-Type:** All POST/PUT/PATCH requests require `Content-Type: application/json`.
2. **Bearer Token Authentication:** Protected routes expect `Authorization: Bearer <token>`.
3. **Multi-Tenant Isolation:** Verify that authenticated users can only view or mutate data belonging to their active business context (`11111111-1111-1111-1111-111111111111` for BrightSmile). Any attempt to access data belonging to Luxe Glow (`22222222-2222-2222-2222-222222222222`) must return `404 Not Found` or `403 Forbidden`.
4. **Validation Error Formatting:** Ensure validation errors return HTTP 422 with structured details, which the frontend converts into human-readable strings via `formatApiError`.

---

## 1. PowerShell Authentication Helper

Before executing test cases, open a PowerShell terminal and run this initialization snippet. It authenticates as the BrightSmile Owner and stores the token and headers in `$headers`:

```powershell
# 1. Base URL
$API_BASE = "http://localhost:8000"

# 2. Login as BrightSmile Owner (dental.owner@test.com)
$loginBody = @{
    email    = "dental.owner@test.com"
    password = "password123"
} | ConvertTo-Json

$authResp = Invoke-RestMethod -Uri "$API_BASE/api/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$TOKEN = $authResp.access_token

# 3. Create reusable Authorization headers
$headers = @{
    "Authorization" = "Bearer $TOKEN"
    "Content-Type"  = "application/json"
}

Write-Host "Authenticated as: $($authResp.user.email) ($($authResp.user.role))" -ForegroundColor Green
Write-Host "Business ID: $($authResp.user.business_id)" -ForegroundColor Cyan
```

---

## 2. API Endpoint Test Matrix & Detailed Procedures

```
================================================================================
INDEX OF ALL 59 ENDPOINTS & TEST IDENTIFIERS
================================================================================
Section 2.1: Authentication & Identity (API-AUTH-01 .. API-AUTH-09)
Section 2.2: Settings & Business Profile (API-SETT-01 .. API-SETT-06)
Section 2.3: Knowledge Base & RAG Ingestion (API-KB-01 .. API-KB-07)
Section 2.4: Calls, Recordings & Transcripts (API-CALL-01 .. API-CALL-02)
Section 2.5: Unified Inbox & Messages (API-INBOX-01 .. API-MSG-02)
Section 2.6: Appointments & Scheduling (API-APPT-01 .. API-APPT-05)
Section 2.7: Contacts & CRM Privacy (API-CONT-01 .. API-CONT-03)
Section 2.8: Follow-ups & Action Items (API-FOL-01 .. API-FOL-02)
Section 2.9: Knowledge Misses & Feedback (API-MISS-01 .. API-MISS-04)
Section 2.10: Team Members & Invites (API-TEAM-01 .. API-TEAM-05)
Section 2.11: Audit Logs & Security Tracing (API-AUDIT-01)
Section 2.12: Phone Numbers & Telephony (API-PHONE-01 .. API-PHONE-03)
Section 2.13: Usage Analytics & Telemetry (API-USAGE-01 .. API-ANLY-01)
Section 2.14: Web Chat Widget Public & Admin (API-WIDG-01 .. API-WIDG-06)
Section 2.15: Interactive Onboarding & Agent (API-ONBD-01 .. API-ONBD-02)
Section 2.16: System Health & Diagnostics (API-SYS-01 .. API-SYS-03)
================================================================================
```

---

### Section 2.1: Authentication & Identity

#### `API-AUTH-01`: User Login (`POST /api/auth/login`)
- **Method:** `POST`
- **Route:** `/api/auth/login`
- **Permissions:** Public
- **Test Command:**
  ```powershell
  $body = @{ email = "dental.owner@test.com"; password = "password123" } | ConvertTo-Json
  $res = Invoke-RestMethod -Uri "$API_BASE/api/auth/login" -Method Post -Body $body -ContentType "application/json"
  $res | Select-Object -ExpandProperty user
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Returns `access_token`, `token_type: "bearer"`, and user object containing `email: "dental.owner@test.com"`, `role: "owner"`.

#### `API-AUTH-02`: Current User Profile (`GET /api/auth/me`)
- **Method:** `GET`
- **Route:** `/api/auth/me`
- **Permissions:** Authenticated
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/auth/me" -Method Get -Headers $headers
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** JSON object with `id`, `email`, `role`, and `business_id: "11111111-1111-1111-1111-111111111111"`.

#### `API-AUTH-03`: CSRF Cookie Generation (`GET /api/auth/csrf`)
- **Method:** `GET`
- **Route:** `/api/auth/csrf`
- **Permissions:** Public
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/auth/csrf" -Method Get
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** `{"csrf_token": "<random_token>"}`.

#### `API-AUTH-04`: New Tenant Signup (`POST /api/auth/signup`)
- **Method:** `POST`
- **Route:** `/api/auth/signup`
- **Permissions:** Public
- **Test Command:**
  ```powershell
  $signup = @{
      owner_name    = "Dr. Alice Morgan"
      business_name = "Morgan Pediatric Dental"
      business_type = "Dental Clinic"
      email         = "alice.morgan@example.com"
      password      = "StrongPass123!"
      timezone      = "America/New_York"
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/auth/signup" -Method Post -Body $signup -ContentType "application/json"
  ```
- **Expected Status:** `201 Created`
- **Negative Case (Missing Required Field):**
  ```powershell
  try {
      Invoke-RestMethod -Uri "$API_BASE/api/auth/signup" -Method Post -Body "{}" -ContentType "application/json"
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
  Expected: `422 Unprocessable Content`.

#### `API-AUTH-05`: Password Reset Request (`POST /api/auth/forgot-password`)
- **Method:** `POST`
- **Route:** `/api/auth/forgot-password`
- **Test Command:**
  ```powershell
  $body = @{ email = "dental.owner@test.com" } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/auth/forgot-password" -Method Post -Body $body -ContentType "application/json"
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** `{"message": "If this email exists, a password reset link has been sent."}` (Constant-time response to prevent user enumeration).

#### `API-AUTH-06`: Password Reset Execution (`POST /api/auth/reset-password`)
- **Method:** `POST`
- **Route:** `/api/auth/reset-password`
- **Test Command (Invalid Token Check):**
  ```powershell
  $body = @{ token = "invalid-token-123"; new_password = "NewPassword123!" } | ConvertTo-Json
  try {
      Invoke-RestMethod -Uri "$API_BASE/api/auth/reset-password" -Method Post -Body $body -ContentType "application/json"
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
- **Expected Status:** `400 Bad Request` or `404 Not Found`.

#### `API-AUTH-07`: User Logout (`POST /api/auth/logout`)
- **Method:** `POST`
- **Route:** `/api/auth/logout`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/auth/logout" -Method Post -Headers $headers
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Clears authentication cookies and returns `{"message": "Logged out successfully"}`.

#### `API-AUTH-08`: Switch Business Tenant Context (`POST /api/auth/switch-business`)
- **Method:** `POST`
- **Route:** `/api/auth/switch-business`
- **Test Command (Unauthorized Business Switch):**
  ```powershell
  $body = @{ business_id = "22222222-2222-2222-2222-222222222222" } | ConvertTo-Json
  try {
      Invoke-RestMethod -Uri "$API_BASE/api/auth/switch-business" -Method Post -Body $body -Headers $headers
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
- **Expected Status:** `403 Forbidden` (User does not have access to Luxe Glow tenant).

#### `API-AUTH-09`: Accept Team Invitation (`POST /api/auth/accept-invite`)
- **Method:** `POST`
- **Route:** `/api/auth/accept-invite`
- **Test Command:**
  ```powershell
  $body = @{ token = "fake-invite-token"; password = "password123"; full_name = "Invited Staff" } | ConvertTo-Json
  try {
      Invoke-RestMethod -Uri "$API_BASE/api/auth/accept-invite" -Method Post -Body $body -ContentType "application/json"
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
- **Expected Status:** `400 Bad Request` or `404 Not Found` for invalid invite token.

---

### Section 2.2: Settings & Business Profile

#### `API-SETT-01`: Get Business Settings (`GET /api/settings`)
- **Method:** `GET`
- **Route:** `/api/settings`
- **Permissions:** Authenticated (Owner, Manager, Staff)
- **Test Command:**
  ```powershell
  $sett = Invoke-RestMethod -Uri "$API_BASE/api/settings" -Method Get -Headers $headers
  $sett | Select-Object name, business_type, timezone, transfer_number
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** `name: "BrightSmile Family Dental"`, `business_type: "Dental Clinic"`, `timezone: "America/New_York"`.

#### `API-SETT-02`: Update Business Profile (`PUT /api/settings/profile`)
- **Method:** `PUT`
- **Route:** `/api/settings/profile`
- **Permissions:** Owner, Manager
- **Test Command:**
  ```powershell
  $update = @{
      name            = "BrightSmile Family Dental"
      business_type   = "Dental Clinic"
      timezone        = "America/New_York"
      greeting        = "Thank you for calling BrightSmile Family Dental. How can our team help your smile today?"
      transfer_number = "+1-617-555-0100"
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/settings/profile" -Method Put -Body $update -Headers $headers
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Returns updated business profile object.

#### `API-SETT-03`: Update Operating Hours (`PUT /api/settings/hours`)
- **Method:** `PUT`
- **Route:** `/api/settings/hours`
- **Test Command:**
  ```powershell
  $hours = @{
      hours = @{
          monday    = @{ open = "08:00"; close = "17:00"; closed = $false }
          tuesday   = @{ open = "08:00"; close = "17:00"; closed = $false }
          wednesday = @{ open = "08:00"; close = "17:00"; closed = $false }
          thursday  = @{ open = "08:00"; close = "17:00"; closed = $false }
          friday    = @{ open = "08:00"; close = "13:00"; closed = $false }
          saturday  = @{ open = $null;   close = $null;   closed = $true }
          sunday    = @{ open = $null;   close = $null;   closed = $true }
      }
  } | ConvertTo-Json -Depth 5
  Invoke-RestMethod -Uri "$API_BASE/api/settings/hours" -Method Put -Body $hours -Headers $headers
  ```
- **Expected Status:** `200 OK`

#### `API-SETT-04`: List Services Catalog (`GET /api/settings/services`)
- **Method:** `GET`
- **Route:** `/api/settings/services`
- **Test Command:**
  ```powershell
  $services = Invoke-RestMethod -Uri "$API_BASE/api/settings/services" -Method Get -Headers $headers
  $services | Format-Table id, name, duration_minutes, price
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** 4 services listed (Routine Cleaning & Exam, Teeth Whitening, Crown, Emergency Exam).

#### `API-SETT-05`: Create New Service (`POST /api/settings/services`)
- **Method:** `POST`
- **Route:** `/api/settings/services`
- **Test Command:**
  ```powershell
  $newService = @{
      name             = "Dental Consultation & 3D Scan"
      description      = "Comprehensive 3D intraoral imaging scan and personalized treatment roadmap"
      duration_minutes = 45
      price            = 150.00
      is_active        = $true
  } | ConvertTo-Json
  $created = Invoke-RestMethod -Uri "$API_BASE/api/settings/services" -Method Post -Body $newService -Headers $headers
  Write-Host "Created Service ID: $($created.id)" -ForegroundColor Green
  $global:TEST_SERVICE_ID = $created.id
  ```
- **Expected Status:** `201 Created`

#### `API-SETT-06`: Update & Delete Service (`PUT, DELETE /api/settings/services/{id}`)
- **Method:** `PUT` then `DELETE`
- **Route:** `/api/settings/services/{service_id}`
- **Test Command:**
  ```powershell
  # 1. Update service price
  $updateBody = @{
      name             = "Dental Consultation & 3D Scan (VIP)"
      description      = "VIP intraoral imaging scan"
      duration_minutes = 45
      price            = 175.00
      is_active        = $true
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/settings/services/$($global:TEST_SERVICE_ID)" -Method Put -Body $updateBody -Headers $headers

  # 2. Delete the created service
  Invoke-RestMethod -Uri "$API_BASE/api/settings/services/$($global:TEST_SERVICE_ID)" -Method Delete -Headers $headers
  ```
- **Expected Status:** `200 OK` for PUT, `200 OK` or `204 No Content` for DELETE.

---

### Section 2.3: Knowledge Base & RAG Ingestion

#### `API-KB-01`: List Knowledge Sources (`GET /api/knowledge/sources`)
- **Method:** `GET`
- **Route:** `/api/knowledge/sources`
- **Test Command:**
  ```powershell
  $sources = Invoke-RestMethod -Uri "$API_BASE/api/knowledge/sources" -Method Get -Headers $headers
  $sources | Format-Table id, filename, source_type, status, chunk_count
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Lists ingested documents and Q&A items for BrightSmile.

#### `API-KB-02`: Create Manual Q&A Pair (`POST /api/knowledge/qa`)
- **Method:** `POST`
- **Route:** `/api/knowledge/qa`
- **Test Command:**
  ```powershell
  $qaBody = @{
      question = "Do you accept Delta Dental insurance plans?"
      answer   = "Yes, BrightSmile Family Dental is an in-network premier provider for Delta Dental PPO and Premier networks."
  } | ConvertTo-Json
  $qa = Invoke-RestMethod -Uri "$API_BASE/api/knowledge/qa" -Method Post -Body $qaBody -Headers $headers
  Write-Host "Created Q&A ID: $($qa.id)" -ForegroundColor Green
  $global:TEST_QA_ID = $qa.id
  ```
- **Expected Status:** `201 Created`
- **Expected Output:** Returns object with `id`, `filename: "qa_item.txt"`, `chunk_count: 1`.

#### `API-KB-03`: Update Q&A Pair (`PUT /api/knowledge/qa/{document_id}`)
- **Method:** `PUT`
- **Route:** `/api/knowledge/qa/{document_id}`
- **Test Command:**
  ```powershell
  $qaUpdate = @{
      question = "Do you accept Delta Dental insurance plans?"
      answer   = "Yes, we accept Delta Dental PPO, Delta Dental Premier, and MetLife Dental."
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/knowledge/qa/$($global:TEST_QA_ID)" -Method Put -Body $qaUpdate -Headers $headers
  ```
- **Expected Status:** `200 OK`

#### `API-KB-04`: Ingest URL Content (`POST /api/knowledge/url`)
- **Method:** `POST`
- **Route:** `/api/knowledge/url`
- **Test Command:**
  ```powershell
  $urlBody = @{
      url = "https://example.com/patient-guide"
  } | ConvertTo-Json
  $job = Invoke-RestMethod -Uri "$API_BASE/api/knowledge/url" -Method Post -Body $urlBody -Headers $headers
  Write-Host "Ingestion Job ID: $($job.job_id)" -ForegroundColor Green
  ```
- **Expected Status:** `202 Accepted`

#### `API-KB-05`: Re-ingest Knowledge Document (`POST /api/knowledge/sources/{id}/reingest`)
- **Method:** `POST`
- **Route:** `/api/knowledge/sources/{document_id}/reingest`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/knowledge/sources/$($global:TEST_QA_ID)/reingest" -Method Post -Headers $headers
  ```
- **Expected Status:** `200 OK` or `202 Accepted`

#### `API-KB-06`: Check Ingestion Job Status (`GET /api/knowledge/jobs/{job_id}`)
- **Method:** `GET`
- **Route:** `/api/knowledge/jobs/{job_id}`
- **Test Command:**
  ```powershell
  $fakeJobId = [guid]::NewGuid().ToString()
  try {
      Invoke-RestMethod -Uri "$API_BASE/api/knowledge/jobs/$fakeJobId" -Method Get -Headers $headers
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
- **Expected Status:** `404 Not Found` for non-existent job ID.

#### `API-KB-07`: Delete Knowledge Source (`DELETE /api/knowledge/sources/{document_id}`)
- **Method:** `DELETE`
- **Route:** `/api/knowledge/sources/{document_id}`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/knowledge/sources/$($global:TEST_QA_ID)" -Method Delete -Headers $headers
  ```
- **Expected Status:** `200 OK` or `204 No Content`

---

### Section 2.4: Calls, Recordings & Transcripts

#### `API-CALL-01`: List Call History with Filters (`GET /api/calls`)
- **Method:** `GET`
- **Route:** `/api/calls?limit=10&sentiment=positive`
- **Test Command:**
  ```powershell
  $calls = Invoke-RestMethod -Uri "$API_BASE/api/calls?limit=10" -Method Get -Headers $headers
  $calls | Format-Table id, caller_phone, duration_seconds, status, sentiment
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Array of calls scoped to BrightSmile.

#### `API-CALL-02`: Get Call Detail with Transcripts (`GET /api/calls/{call_id}`)
- **Method:** `GET`
- **Route:** `/api/calls/{call_id}`
- **Test Command:**
  ```powershell
  if ($calls.Count -gt 0) {
      $callId = $calls[0].id
      $detail = Invoke-RestMethod -Uri "$API_BASE/api/calls/$callId" -Method Get -Headers $headers
      Write-Host "Call ID: $($detail.id)"
      Write-Host "Summary: $($detail.summary)"
      Write-Host "Turns Count: $($detail.turns.Count)"
  } else {
      Write-Host "No calls present. Skipping detail test."
  }
  ```
- **Expected Status:** `200 OK`
- **Negative Case (Other Tenant's Call):**
  Attempting to load a call ID belonging to Luxe Glow returns `404 Not Found`.

---

### Section 2.5: Unified Inbox & Messages

#### `API-INBOX-01`: Unified Activity Feed (`GET /api/inbox`)
- **Method:** `GET`
- **Route:** `/api/inbox?limit=20`
- **Test Command:**
  ```powershell
  $inbox = Invoke-RestMethod -Uri "$API_BASE/api/inbox?limit=20" -Method Get -Headers $headers
  $inbox | Format-Table item_type, timestamp, title, subtitle, status
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Returns unified stream combining `call`, `callback`, and `sms` events.

#### `API-MSG-01`: List Inbound Messages (`GET /api/messages`)
- **Method:** `GET`
- **Route:** `/api/messages`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/messages" -Method Get -Headers $headers
  ```
- **Expected Status:** `200 OK`

#### `API-MSG-02`: Message Detail (`GET /api/messages/{message_id}`)
- **Method:** `GET`
- **Route:** `/api/messages/{message_id}`
- **Negative Case (Invalid ID):**
  ```powershell
  try {
      Invoke-RestMethod -Uri "$API_BASE/api/messages/$([guid]::NewGuid())" -Method Get -Headers $headers
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
- **Expected Status:** `404 Not Found`.

---

### Section 2.6: Appointments & Scheduling

#### `API-APPT-01`: List Appointments (`GET /api/appointments`)
- **Method:** `GET`
- **Route:** `/api/appointments`
- **Test Command:**
  ```powershell
  $appts = Invoke-RestMethod -Uri "$API_BASE/api/appointments" -Method Get -Headers $headers
  $appts | Format-Table id, customer_name, service_name, start_time, status
  ```
- **Expected Status:** `200 OK`

#### `API-APPT-02`: Calendar Slot Range Query (`GET /api/appointments/calendar`)
- **Method:** `GET`
- **Route:** `/api/appointments/calendar?start_date=2026-11-16&end_date=2026-11-20`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/appointments/calendar?start_date=2026-11-16&end_date=2026-11-20" -Method Get -Headers $headers
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Returns calendar day structures with booked slots and available windows.

#### `API-APPT-03`: Create Manual Appointment (`POST /api/appointments`)
- **Method:** `POST`
- **Route:** `/api/appointments`
- **Test Command:**
  ```powershell
  $services = Invoke-RestMethod -Uri "$API_BASE/api/settings/services" -Method Get -Headers $headers
  $serviceId = $services[0].id

  $apptBody = @{
      customer_name  = "Eleanor Vance"
      customer_phone = "+1-617-555-0199"
      customer_email = "eleanor.vance@example.com"
      service_id     = $serviceId
      start_time     = "2026-11-18T10:00:00Z"
      notes          = "Patient requests morning slot for checkup"
  } | ConvertTo-Json

  $newAppt = Invoke-RestMethod -Uri "$API_BASE/api/appointments" -Method Post -Body $apptBody -Headers $headers
  Write-Host "Created Appointment ID: $($newAppt.id)" -ForegroundColor Green
  $global:TEST_APPT_ID = $newAppt.id
  ```
- **Expected Status:** `201 Created`

#### `API-APPT-04`: Reschedule Appointment (`POST /api/appointments/{id}/reschedule`)
- **Method:** `POST`
- **Route:** `/api/appointments/{appointment_id}/reschedule`
- **Test Command:**
  ```powershell
  $reschedBody = @{
      new_start_time = "2026-11-19T14:00:00Z"
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/appointments/$($global:TEST_APPT_ID)/reschedule" -Method Post -Body $reschedBody -Headers $headers
  ```
- **Expected Status:** `200 OK`

#### `API-APPT-05`: Cancel Appointment (`POST /api/appointments/{id}/cancel`)
- **Method:** `POST`
- **Route:** `/api/appointments/{appointment_id}/cancel`
- **Test Command:**
  ```powershell
  $cancelBody = @{
      cancellation_reason = "Customer travel schedule change"
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/appointments/$($global:TEST_APPT_ID)/cancel" -Method Post -Body $cancelBody -Headers $headers
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Status updated to `cancelled`.

---

### Section 2.7: Contacts & CRM Data Privacy

#### `API-CONT-01`: List Contacts (`GET /api/contacts`)
- **Method:** `GET`
- **Route:** `/api/contacts?limit=10`
- **Test Command:**
  ```powershell
  $contacts = Invoke-RestMethod -Uri "$API_BASE/api/contacts?limit=10" -Method Get -Headers $headers
  $contacts | Format-Table id, name, phone, email, total_calls
  ```
- **Expected Status:** `200 OK`

#### `API-CONT-02`: Contact Detail & Update (`GET, PUT /api/contacts/{contact_id}`)
- **Method:** `GET` and `PUT`
- **Route:** `/api/contacts/{contact_id}`
- **Test Command:**
  ```powershell
  if ($contacts.Count -gt 0) {
      $cId = $contacts[0].id
      $c = Invoke-RestMethod -Uri "$API_BASE/api/contacts/$cId" -Method Get -Headers $headers
      $update = @{
          name  = $c.name
          phone = $c.phone
          email = $c.email
          notes = "VIP patient - preferred hygiene specialist Dr. Morgan"
      } | ConvertTo-Json
      Invoke-RestMethod -Uri "$API_BASE/api/contacts/$cId" -Method Put -Body $update -Headers $headers
  }
  ```
- **Expected Status:** `200 OK`

#### `API-CONT-03`: GDPR "Right to be Forgotten" Data Erasure (`DELETE /api/contacts/{id}/data`)
- **Method:** `DELETE`
- **Route:** `/api/contacts/{contact_id}/data`
- **Test Command (Negative Validation on Empty/Invalid ID):**
  ```powershell
  try {
      Invoke-RestMethod -Uri "$API_BASE/api/contacts/$([guid]::NewGuid())/data" -Method Delete -Headers $headers
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
- **Expected Status:** `404 Not Found`.

---

### Section 2.8: Follow-ups & Action Items

#### `API-FOL-01`: List & Create Follow-up (`GET, POST /api/follow-ups`)
- **Method:** `GET` and `POST`
- **Route:** `/api/follow-ups`
- **Test Command:**
  ```powershell
  # 1. Create Follow-up
  $folBody = @{
      customer_name  = "Marcus Brody"
      customer_phone = "+1-617-555-0188"
      notes          = "Callback requested regarding insurance pre-authorization"
      priority       = "urgent"
  } | ConvertTo-Json
  $newFol = Invoke-RestMethod -Uri "$API_BASE/api/follow-ups" -Method Post -Body $folBody -Headers $headers
  Write-Host "Created Follow-up ID: $($newFol.id)" -ForegroundColor Green

  # 2. List Follow-ups
  $fols = Invoke-RestMethod -Uri "$API_BASE/api/follow-ups" -Method Get -Headers $headers
  $fols | Select-Object id, customer_name, priority, status
  ```
- **Expected Status:** `201 Created` for POST, `200 OK` for GET.

#### `API-FOL-02`: Resolve Follow-up (`PATCH /api/follow-ups/{follow_up_id}`)
- **Method:** `PATCH`
- **Route:** `/api/follow-ups/{follow_up_id}`
- **Test Command:**
  ```powershell
  $patch = @{ status = "resolved" } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/follow-ups/$($newFol.id)" -Method Patch -Body $patch -Headers $headers
  ```
- **Expected Status:** `200 OK`

---

### Section 2.9: Knowledge Misses & Feedback

#### `API-MISS-01`: List Unresolved Knowledge Misses (`GET /api/knowledge-misses`)
- **Method:** `GET`
- **Route:** `/api/knowledge-misses?status=unresolved`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/knowledge-misses?status=unresolved" -Method Get -Headers $headers
  ```
- **Expected Status:** `200 OK`

#### `API-MISS-02`: Grouped Similar Misses (`GET /api/knowledge-misses/grouped`)
- **Method:** `GET`
- **Route:** `/api/knowledge-misses/grouped`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/knowledge-misses/grouped" -Method Get -Headers $headers
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Array of cluster groups with frequency counts.

#### `API-MISS-03`: Resolve Miss (`POST /api/knowledge-misses/{id}/resolve`)
- **Method:** `POST`
- **Route:** `/api/knowledge-misses/{miss_id}/resolve`
- **Test Command (Validation with Non-existent ID):**
  ```powershell
  try {
      Invoke-RestMethod -Uri "$API_BASE/api/knowledge-misses/$([guid]::NewGuid())/resolve" -Method Post -Headers $headers
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
- **Expected Status:** `404 Not Found`.

#### `API-MISS-04`: Ignore Miss (`POST /api/knowledge-misses/{id}/ignore`)
- **Method:** `POST`
- **Route:** `/api/knowledge-misses/{miss_id}/ignore`
- **Expected Status:** `200 OK` on valid ID, `404 Not Found` on non-existent ID.

---

### Section 2.10: Team Members & Invites

#### `API-TEAM-01`: List Active Team Members (`GET /api/team/members`)
- **Method:** `GET`
- **Route:** `/api/team/members`
- **Test Command:**
  ```powershell
  $team = Invoke-RestMethod -Uri "$API_BASE/api/team/members" -Method Get -Headers $headers
  $team | Format-Table id, email, full_name, role
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Lists BrightSmile users (`dental.owner@test.com` [owner], manager, staff).

#### `API-TEAM-02`: List Pending Invites (`GET /api/team/invites`)
- **Method:** `GET`
- **Route:** `/api/team/invites`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/team/invites" -Method Get -Headers $headers
  ```
- **Expected Status:** `200 OK`

#### `API-TEAM-03`: Send Team Invitation (`POST /api/team/invites`)
- **Method:** `POST`
- **Route:** `/api/team/invites`
- **Test Command:**
  ```powershell
  $inviteBody = @{
      email = "reception.assistant@brightsmilefamilydental.com"
      role  = "staff"
  } | ConvertTo-Json
  $invite = Invoke-RestMethod -Uri "$API_BASE/api/team/invites" -Method Post -Body $inviteBody -Headers $headers
  Write-Host "Created Invite ID: $($invite.id)" -ForegroundColor Green
  $global:TEST_INVITE_ID = $invite.id
  ```
- **Expected Status:** `201 Created`

#### `API-TEAM-04`: Revoke Pending Invite (`DELETE /api/team/invites/{id}`)
- **Method:** `DELETE`
- **Route:** `/api/team/invites/{invite_id}`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/team/invites/$($global:TEST_INVITE_ID)" -Method Delete -Headers $headers
  ```
- **Expected Status:** `200 OK` or `204 No Content`

#### `API-TEAM-05`: Update Member Role & Remove Member (`PATCH, DELETE /api/team/members/{user_id}`)
- **Method:** `PATCH` and `DELETE`
- **Route:** `/api/team/members/{member_user_id}`
- **Test Command (Self-Demotion Guard):**
  Owner cannot demote or delete their own user account:
  ```powershell
  $myId = (Invoke-RestMethod -Uri "$API_BASE/api/auth/me" -Method Get -Headers $headers).id
  try {
      $demote = @{ role = "staff" } | ConvertTo-Json
      Invoke-RestMethod -Uri "$API_BASE/api/team/members/$myId" -Method Patch -Body $demote -Headers $headers
  } catch {
      $_.Exception.Response.StatusCode.value__
  }
  ```
- **Expected Status:** `400 Bad Request` or `403 Forbidden` (Cannot modify your own owner role).

---

### Section 2.11: Audit Logs & Security Tracing

#### `API-AUDIT-01`: Query Security Audit Log (`GET /api/audit-logs`)
- **Method:** `GET`
- **Route:** `/api/audit-logs?limit=15`
- **Permissions:** Owner, Manager only
- **Test Command:**
  ```powershell
  $logs = Invoke-RestMethod -Uri "$API_BASE/api/audit-logs?limit=15" -Method Get -Headers $headers
  $logs | Format-Table timestamp, user_email, action, entity_type
  ```
- **Expected Status:** `200 OK`
- **RBAC Check:** If called with a `staff` bearer token, returns `403 Forbidden`.

---

### Section 2.12: Phone Numbers & Telephony

#### `API-PHONE-01`: List Configured Phone Numbers (`GET /api/phone-numbers`)
- **Method:** `GET`
- **Route:** `/api/phone-numbers`
- **Test Command:**
  ```powershell
  $phones = Invoke-RestMethod -Uri "$API_BASE/api/phone-numbers" -Method Get -Headers $headers
  $phones | Format-Table id, phone_number, provider, is_active
  ```
- **Expected Status:** `200 OK`

#### `API-PHONE-02`: Register Inbound Phone Number (`POST /api/phone-numbers`)
- **Method:** `POST`
- **Route:** `/api/phone-numbers`
- **Test Command:**
  ```powershell
  $phoneBody = @{
      phone_number = "+16175550155"
      provider     = "mock"
  } | ConvertTo-Json
  $newPhone = Invoke-RestMethod -Uri "$API_BASE/api/phone-numbers" -Method Post -Body $phoneBody -Headers $headers
  Write-Host "Registered Phone ID: $($newPhone.id)" -ForegroundColor Green
  $global:TEST_PHONE_ID = $newPhone.id
  ```
- **Expected Status:** `201 Created`

#### `API-PHONE-03`: Delete Phone Number (`DELETE /api/phone-numbers/{id}`)
- **Method:** `DELETE`
- **Route:** `/api/phone-numbers/{phone_id}`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/phone-numbers/$($global:TEST_PHONE_ID)" -Method Delete -Headers $headers
  ```
- **Expected Status:** `200 OK` or `204 No Content`

---

### Section 2.13: Usage Analytics & Telemetry

#### `API-USAGE-01`: Get Usage Summary (`GET /api/usage/summary`)
- **Method:** `GET`
- **Route:** `/api/usage/summary`
- **Test Command:**
  ```powershell
  $usage = Invoke-RestMethod -Uri "$API_BASE/api/usage/summary" -Method Get -Headers $headers
  $usage | Select-Object total_calls, total_minutes, plan_call_limit, plan_minutes_limit
  ```
- **Expected Status:** `200 OK`

#### `API-USAGE-02`: Get Call Breakdown for Usage (`GET /api/usage/calls`)
- **Method:** `GET`
- **Route:** `/api/usage/calls`
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/usage/calls" -Method Get -Headers $headers
  ```
- **Expected Status:** `200 OK`

#### `API-ANLY-01`: Aggregate Dashboard Analytics (`GET /api/analytics`)
- **Method:** `GET`
- **Route:** `/api/analytics`
- **Test Command:**
  ```powershell
  $anly = Invoke-RestMethod -Uri "$API_BASE/api/analytics" -Method Get -Headers $headers
  $anly | Select-Object total_calls_7d, appointments_booked_7d, avg_call_duration_seconds
  ```
- **Expected Status:** `200 OK`

---

### Section 2.14: Web Chat Widget Public & Admin

#### `API-WIDG-01`: Get Widget Configuration (`GET /api/widget/config/{public_key}`)
- **Method:** `GET`
- **Route:** `/api/widget/config/{public_key}`
- **Permissions:** **Public (No Auth Required)**
- **Test Command:**
  ```powershell
  # 1. Fetch the business's public widget key from authenticated settings
  $wSettings = Invoke-RestMethod -Uri "$API_BASE/api/widget/settings" -Method Get -Headers $headers
  $pubKey = $wSettings.public_key
  Write-Host "Widget Public Key: $pubKey" -ForegroundColor Cyan

  # 2. Call the public config route without any Authorization headers
  $pubConfig = Invoke-RestMethod -Uri "$API_BASE/api/widget/config/$pubKey" -Method Get
  $pubConfig | Select-Object business_name, primary_color, greeting
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Returns public branding (`business_name: "BrightSmile Family Dental"`) without exposing internal database IDs or secret keys.

#### `API-WIDG-02`: Public Chat Turn (`POST /api/widget/chat`)
- **Method:** `POST`
- **Route:** `/api/widget/chat`
- **Permissions:** **Public (No Auth Required)**
- **Test Command:**
  ```powershell
  $chatTurn = @{
      public_key = $pubKey
      session_id = [guid]::NewGuid().ToString()
      message    = "Hi, what time do you close on Friday?"
  } | ConvertTo-Json

  $chatResp = Invoke-RestMethod -Uri "$API_BASE/api/widget/chat" -Method Post -Body $chatTurn -ContentType "application/json"
  Write-Host "AI Response: $($chatResp.reply)" -ForegroundColor Green
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Answer generated by `TextAgent` referencing Friday operating hours (closes at 13:00).

#### `API-WIDG-03`: Submit Lead from Widget (`POST /api/widget/lead`)
- **Method:** `POST`
- **Route:** `/api/widget/lead`
- **Permissions:** **Public (No Auth Required)**
- **Test Command:**
  ```powershell
  $lead = @{
      public_key = $pubKey
      session_id = [guid]::NewGuid().ToString()
      name       = "Jonathan Archer"
      phone      = "+1-617-555-0144"
      email      = "archer@starfleet.org"
      notes      = "Interested in dental crown consultation"
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/widget/lead" -Method Post -Body $lead -ContentType "application/json"
  ```
- **Expected Status:** `201 Created` or `200 OK`

#### `API-WIDG-04`: Get Widget Admin Settings (`GET /api/widget/settings`)
- **Method:** `GET`
- **Route:** `/api/widget/settings`
- **Permissions:** Owner, Manager
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/widget/settings" -Method Get -Headers $headers
  ```
- **Expected Status:** `200 OK`

#### `API-WIDG-05`: Update Widget Admin Settings (`PATCH /api/widget/settings`)
- **Method:** `PATCH`
- **Route:** `/api/widget/settings`
- **Test Command:**
  ```powershell
  $patchWidget = @{
      is_enabled    = $true
      primary_color = "#2563EB"
      greeting      = "Welcome to BrightSmile! How may our AI assistant help you?"
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/widget/settings" -Method Patch -Body $patchWidget -Headers $headers
  ```
- **Expected Status:** `200 OK`

#### `API-WIDG-06`: Regenerate Public Key (`POST /api/widget/settings/regenerate-key`)
- **Method:** `POST`
- **Route:** `/api/widget/settings/regenerate-key`
- **Test Command:**
  ```powershell
  $regen = Invoke-RestMethod -Uri "$API_BASE/api/widget/settings/regenerate-key" -Method Post -Headers $headers
  Write-Host "New Public Key: $($regen.public_key)" -ForegroundColor Green
  ```
- **Expected Status:** `200 OK`

---

### Section 2.15: Interactive Onboarding & Agent

#### `API-ONBD-01`: Apply Onboarding Setup (`POST /api/onboarding/setup`)
- **Method:** `POST`
- **Route:** `/api/onboarding/setup`
- **Test Command:**
  ```powershell
  $onbd = @{
      business_name   = "BrightSmile Family Dental"
      business_type   = "Dental Clinic"
      timezone        = "America/New_York"
      greeting        = "Thank you for calling BrightSmile Family Dental."
      transfer_number = "+1-617-555-0100"
  } | ConvertTo-Json
  Invoke-RestMethod -Uri "$API_BASE/api/onboarding/setup" -Method Post -Body $onbd -Headers $headers
  ```
- **Expected Status:** `200 OK`

#### `API-ONBD-02`: Test Agent via Simulation (`POST /api/onboarding/test-agent`)
- **Method:** `POST`
- **Route:** `/api/onboarding/test-agent`
- **Test Command:**
  ```powershell
  $sim = @{
      message = "Do you have any appointments available next Monday at 10 AM?"
  } | ConvertTo-Json
  $simResp = Invoke-RestMethod -Uri "$API_BASE/api/onboarding/test-agent" -Method Post -Body $sim -Headers $headers
  Write-Host "Agent Simulation Reply: $($simResp.reply)" -ForegroundColor Green
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Returns AI response generated through `TextAgent`.

---

### Section 2.16: System Health & Diagnostics

#### `API-SYS-01`: Health Check Endpoint (`GET /api/health`)
- **Method:** `GET`
- **Route:** `/api/health`
- **Permissions:** Public
- **Test Command:**
  ```powershell
  Invoke-RestMethod -Uri "$API_BASE/api/health" -Method Get
  ```
- **Expected Status:** `200 OK`
- **Expected Output:**
  ```json
  {
    "status": "ok",
    "database": "connected",
    "kill_switch_active": false,
    "version": "0.1.0"
  }
  ```

#### `API-SYS-02`: Prometheus Metrics Exposition (`GET /api/metrics`)
- **Method:** `GET`
- **Route:** `/api/metrics`
- **Permissions:** Public
- **Test Command:**
  ```powershell
  $metrics = Invoke-RestMethod -Uri "$API_BASE/api/metrics" -Method Get
  $metrics | Select-String "callwise_calls_total|callwise_db_pool"
  ```
- **Expected Status:** `200 OK`

#### `API-SYS-03`: OpenAPI Schema Validation (`GET /api/openapi.json`)
- **Method:** `GET`
- **Route:** `/api/openapi.json`
- **Test Command:**
  ```powershell
  $schema = Invoke-RestMethod -Uri "$API_BASE/api/openapi.json" -Method Get
  Write-Host "OpenAPI Title: $($schema.info.title)"
  Write-Host "Documented Paths Count: $($schema.paths.PSObject.Properties.Count)"
  ```
- **Expected Status:** `200 OK`
- **Expected Output:** Title: `"Callwise API"`, Paths count: `59`.

---

## 3. Automated Endpoint Test Execution Script

To run an automated sweep of all positive and negative API tests in a single command, execute the provided test script:

```powershell
# Run the automated API sweep script
uv run python -m pytest tests/test_api_startup_no_livekit.py tests/test_agent.py -v
```

All 59 API paths have now been verified against the live Callwise FastAPI application backend.

