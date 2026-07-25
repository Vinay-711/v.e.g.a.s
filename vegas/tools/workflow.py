"""
Workflow tools for VEGAS AIOS.

Integrates Google Calendar and Gmail via OAuth2, plus a morning briefing
that composes calendar, news, and pending-task data into one spoken digest.
"""

import base64
import os
from datetime import datetime, time, timezone, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from vegas.safety import requires_confirmation

# ---------------------------------------------------------------------------
# Google OAuth helpers
# ---------------------------------------------------------------------------

_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]
_TOKEN_PATH = Path.home() / ".vegas" / "token.json"
_NOT_CONNECTED = (
    "VEGAS: Google account not connected yet — set GOOGLE_OAUTH_CREDENTIALS_PATH "
    "in your .env to the path of your OAuth client_secret JSON and re-run. "
    "See README for details."
)


def _get_google_creds():
    """
    Loads cached credentials from ~/.vegas/token.json, refreshing or running
    the OAuth consent flow as needed. Returns None if the client-secret file
    isn't configured.
    """
    from vegas.config import config

    cred_path = config.GOOGLE_OAUTH_CREDENTIALS_PATH
    if not cred_path or not Path(cred_path).exists():
        return None

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds: Optional[Credentials] = None

    if _TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_PATH), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds or not creds.valid:
            import sys
            import os
            # Prevent blocking headless servers without an interactive TTY
            if not sys.stdin.isatty() and os.environ.get("HEADLESS"):
                return None
            try:
                flow = InstalledAppFlow.from_client_secrets_file(cred_path, _SCOPES)
                creds = flow.run_local_server(port=0, open_browser=True if sys.stdin.isatty() else False)
            except Exception:
                return None

        if creds and creds.valid:
            _TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            _TOKEN_PATH.write_text(creds.to_json())

    return creds


def _build_service(api: str, version: str):
    """Returns an authenticated Google API service, or None."""
    creds = _get_google_creds()
    if creds is None:
        return None
    from googleapiclient.discovery import build

    return build(api, version, credentials=creds)


# ---------------------------------------------------------------------------
# Tool: list_todays_events
# ---------------------------------------------------------------------------

def list_todays_events() -> str:
    """
    Reads the user's primary Google Calendar and returns today's remaining
    events formatted as a spoken-friendly agenda.
    """
    service = _build_service("calendar", "v3")
    if service is None:
        return _NOT_CONNECTED

    try:
        now = datetime.now(timezone.utc)
        # Midnight tonight in UTC (good-enough for a daily view)
        local_now = datetime.now().astimezone()
        midnight = datetime.combine(
            local_now.date() + timedelta(days=1),
            time.min,
            tzinfo=local_now.tzinfo,
        )

        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=midnight.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=20,
            )
            .execute()
        )
        events = result.get("items", [])

        if not events:
            return "You have no more events scheduled for today."

        lines = [f"You have {len(events)} event(s) remaining today:\n"]
        for ev in events:
            start = ev["start"].get("dateTime", ev["start"].get("date", ""))
            # Extract a short time string
            try:
                t = datetime.fromisoformat(start).strftime("%I:%M %p")
            except Exception:
                t = start
            summary = ev.get("summary", "(No title)")
            lines.append(f"  • {t} — {summary}")

        return "\n".join(lines)

    except Exception as exc:
        return f"VEGAS: Failed to fetch calendar events — {exc}"


# ---------------------------------------------------------------------------
# Tool: draft_email (requires confirmation)
# ---------------------------------------------------------------------------

@requires_confirmation
def draft_email(to: str, subject: str, body: str) -> str:
    """
    Creates a Gmail DRAFT addressed to `to` with the given subject and body.
    The email is never sent — only saved as a draft for the user to review.
    Wrapped with @requires_confirmation so the user must approve before the
    draft is created.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.
    """
    service = _build_service("gmail", "v1")
    if service is None:
        return _NOT_CONNECTED

    try:
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        draft_id = draft.get("id", "unknown")
        return (
            f"Gmail draft created successfully.\n"
            f"Draft ID: {draft_id}\n"
            f"To: {to}\n"
            f"Subject: {subject}\n"
            f"Open Gmail to review and send."
        )
    except Exception as exc:
        return f"VEGAS: Failed to create Gmail draft — {exc}"


# ---------------------------------------------------------------------------
# Tool: morning_briefing
# ---------------------------------------------------------------------------

def morning_briefing() -> str:
    """
    Composes a spoken-friendly morning digest combining today's calendar,
    top news headlines, and pending tasks/confirmations.
    """
    # 1. Calendar
    try:
        agenda = list_todays_events()
    except Exception:
        agenda = "Calendar data unavailable."

    # 2. News — reuse the existing open_world_monitor tool from vegas.tools.web
    try:
        from vegas.tools.web import open_world_monitor

        news_raw = open_world_monitor()
        # Extract just the headline lines for a spoken summary
        news_lines = [
            ln.strip()
            for ln in news_raw.splitlines()
            if ln.strip()
            and not ln.startswith("=")
            and not ln.startswith("-")
            and "VEGAS" not in ln
            and "SECTION" not in ln
            and "STATUS" not in ln
            and "MONITOR" not in ln
        ]
        news = "\n".join(news_lines[:6]) if news_lines else "No news available."
    except Exception:
        news = "News data unavailable."

    # 3. Pending tasks
    try:
        from vegas.tools.memory import whats_pending

        pending = whats_pending()
    except Exception:
        pending = "No pending tasks."

    # Compose
    parts = [
        "Good morning! Here's your daily briefing.\n",
        "📅 CALENDAR",
        agenda,
        "\n📰 NEWS HIGHLIGHTS",
        news,
        "\n📋 PENDING TASKS",
        pending,
        "\nThat's your briefing. Have a productive day!",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp) -> None:
    """Registers workflow tools with FastMCP."""
    mcp.tool()(list_todays_events)
    mcp.tool()(draft_email)
    mcp.tool()(morning_briefing)
