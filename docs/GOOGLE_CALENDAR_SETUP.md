# Google Calendar Integration Guide

Callwise provides real-time calendar synchronization with Google Calendar (API v3) and an automatic zero-config local database fallback.

This guide outlines:
1. How the system operates **without** Google Cloud (Current Active Mode).
2. How to connect a real **Google Cloud / Google Calendar** account when you are ready.
3. How verification and fallback resilience work.

---

## 1. Operating Without Google Cloud (Local / Simulation Mode)

By default, Callwise operates without requiring any Google Cloud account, API keys, or billing:
- **Busy Times & Slot Calculations:** Calculated directly against the PostgreSQL `appointments` table (`status = 'booked'`).
- **Event Creation & Sync:** When an appointment is scheduled, Callwise issues a synthetic tracking identifier (`gcal_sim_<uuid>`), dispatches local notifications/emails, and confirms the booking.
- **Rescheduling & Cancellation:** Handled entirely locally without external network dependencies.
- **Provider Flag:** In `.env`, the provider can be set to:
  ```env
  CALENDAR_PROVIDER=local
  ```
  *(Or `CALENDAR_PROVIDER=google` without credentials, which will gracefully fallback to local storage).*

---

## 2. Step-by-Step: Connecting Real Google Calendar

When you are ready to connect Callwise to a live Google Calendar, follow these steps:

### Step 1: Create or Open a Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `Callwise-Voice-AI`) or select an existing project.

### Step 2: Enable the Google Calendar API
1. In the Google Cloud Console, navigate to **APIs & Services** > **Library**.
2. Search for **Google Calendar API**.
3. Click on **Google Calendar API** and click **Enable**.

### Step 3: Create a Service Account & Download Credentials
1. Navigate to **APIs & Services** > **Credentials**.
2. Click **Create Credentials** > **Service Account**.
3. Enter a name (e.g. `callwise-calendar-sync`) and click **Create and Continue**.
4. (Optional) Assign a role (e.g. Viewer or leave empty) and click **Done**.
5. Click on the newly created Service Account email address.
6. Go to the **Keys** tab > **Add Key** > **Create new key**.
7. Choose **JSON** and click **Create**.
8. A `.json` key file will download to your computer.

### Step 4: Share Your Google Calendar with the Service Account
1. Open [Google Calendar](https://calendar.google.com/).
2. Under "My calendars" on the left, find the calendar you want Callwise to manage (or create a dedicated calendar, e.g. "BrightSmile Appointments").
3. Hover over the calendar name, click the **three dots** (Options), and select **Settings and sharing**.
4. Scroll down to **Share with specific people or groups** and click **Add people and groups**.
5. Paste the **Service Account Email** address (e.g. `callwise-calendar-sync@<project-id>.iam.gserviceaccount.com`).
6. Set permissions to **"Make changes to events"**.
7. Click **Send**.
8. In the calendar settings, look under **Integrate calendar** and copy the **Calendar ID** (e.g. `primary` or `your_calendar_id@group.calendar.google.com`).

### Step 5: Place the Credentials File in Callwise
1. Move the downloaded JSON file into your Callwise project folder under a `credentials/` directory:
   ```bash
   mkdir credentials
   # Move your downloaded json file:
   # credentials/google_service_account.json
   ```
   *(Note: The `credentials/` folder is included in `.gitignore` to prevent committing secret keys).*

### Step 6: Update Your `.env` Configuration
Open your `.env` file in the project root and set:
```env
# Calendar Provider Configuration
CALENDAR_PROVIDER=google
GOOGLE_CALENDAR_CREDENTIALS_FILE=credentials/google_service_account.json
GOOGLE_CALENDAR_ID=primary
```
*(Replace `primary` with your specific Calendar ID if using a secondary calendar).*

---

## 3. How the Integration Works Under the Hood

### API v3 Endpoints Used:
- **Check Availability / Busy Blocks:**
  `GET https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events?timeMin=...&timeMax=...&singleEvents=true`
  Returns busy events and merges them with locally booked slots to prevent double-booking.
- **Create Appointment:**
  `POST https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events`
  Inserts summary, start time, end time, caller details, and booking reference.
- **Update / Reschedule:**
  `PATCH https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}`
- **Cancel / Delete:**
  `DELETE https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}`

### Fallback Resilience Guarantee:
If Google Cloud is temporarily unreachable or network latency spikes, Callwise logs an error and automatically falls back to local database availability checking so **callers are never blocked from booking**.

---

## 4. Verification and Testing

You can verify calendar functionality at any time using pytest:
```bash
uv run pytest tests/test_google_calendar.py -v
```

This tests:
- Provider factory resolution (`google` vs `local`).
- Graceful local fallback when credentials are absent.
- Full HTTP mock transport validation for RFC 3339 timezone conversions, event creation, update, and deletion.
