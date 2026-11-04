"""Forward-to-create: turn forwarded calendar invites / emails into reminders.

Two entry points feed the same parser:
  * POST /inbound/email  (webhook from Mailgun / SendGrid / Postmark / any forwarder)
  * An IMAP poller that reads a catch-all mailbox receiving save+<token>@your-domain
"""
import asyncio
import datetime as dt
import email
import imaplib
import logging
import re
from email import policy

from dateutil import parser as dateparser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import SessionLocal
from ..models import InAppNotification, Reminder, User, utcnow
from .dispatcher import LOCK_INBOUND, try_advisory_lock
from .recurrence import compute_due_at, to_zone

log = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"save\+([A-Za-z0-9]+)@", re.IGNORECASE)
LEAD_MINUTES = 15


def find_token(*address_blobs: str) -> str | None:
    for blob in address_blobs:
        m = TOKEN_RE.search(blob or "")
        if m:
            return m.group(1)
    return None


def _events_from_ics(ics_text: str) -> list[dict]:
    from icalendar import Calendar

    events: list[dict] = []
    try:
        cal = Calendar.from_ical(ics_text)
    except Exception as exc:  # noqa: BLE001
        log.warning("Bad ICS: %s", exc)
        return events
    for comp in cal.walk("VEVENT"):
        try:
            start = comp.decoded("DTSTART")
        except Exception:  # noqa: BLE001
            continue
        events.append({
            "title": str(comp.get("SUMMARY", "Meeting")),
            "start": start,
            "description": str(comp.get("DESCRIPTION", "") or ""),
            "location": str(comp.get("LOCATION", "") or ""),
            "url": str(comp.get("URL", "") or ""),
        })
    return events


def _event_from_text(subject: str, text: str) -> dict | None:
    """Best-effort fallback: look for 'When:' / 'Time:' / 'Date:' lines."""
    for line in (text or "").splitlines():
        if re.match(r"\s*(when|time|date|start)\s*:", line, re.IGNORECASE):
            try:
                start = dateparser.parse(line.split(":", 1)[1], fuzzy=True)
            except (ValueError, OverflowError):
                continue
            zoom = re.search(r"https?://\S*(zoom\.us|teams\.microsoft\.com|meet\.google\.com)\S*", text or "")
            return {"title": subject, "start": start, "description": "", "location": "", "url": zoom.group(0) if zoom else ""}
    return None


def _clean_subject(subject: str) -> str:
    return re.sub(r"^\s*((fwd?|re|invitation|updated invitation)\s*:\s*)+", "", subject or "", flags=re.IGNORECASE).strip() or "Forwarded event"


async def create_reminders(session: AsyncSession, user: User, subject: str, text: str, ics_list: list[str]) -> list[Reminder]:
    subject = _clean_subject(subject)
    events: list[dict] = []
    for ics in ics_list:
        events += _events_from_ics(ics)
    if not events:
        ev = _event_from_text(subject, text)
        if ev:
            events.append(ev)

    tz = to_zone(user.timezone)
    now = utcnow()
    created: list[Reminder] = []

    if not events:  # nothing parseable: park it for tomorrow so the user can review it
        tomorrow = (now.astimezone(tz) + dt.timedelta(days=1)).date()
        events = [{"title": subject, "start": tomorrow, "description": "Forwarded email - no date detected, please review.\n\n" + (text or "")[:500],
                   "location": "", "url": ""}]

    for ev in events:
        start = ev["start"]
        if isinstance(start, dt.datetime):
            if start.tzinfo is None:
                start = start.replace(tzinfo=tz)
            fire = start.astimezone(tz) - dt.timedelta(minutes=LEAD_MINUTES)
            if start.astimezone(dt.timezone.utc) < now:
                continue  # event already happened
            r_date, r_time = fire.date(), fire.time().replace(second=0, microsecond=0)
        else:  # all-day
            r_date, r_time = start, dt.time(user.reminder_timing, 0)

        title = ev["title"][:200]
        due = compute_due_at(r_date, r_time, user.timezone)
        dup = await session.scalar(select(Reminder.id).where(Reminder.user_id == user.id, Reminder.title == title, Reminder.due_at == due))
        if dup:
            continue
        desc_parts = [ev["description"][:1000], f"Where: {ev['location']}" if ev["location"] else "", f"Link: {ev['url']}" if ev["url"] else ""]
        r = Reminder(
            user_id=user.id, title=title, description="\n".join(p for p in desc_parts if p) or None,
            category="Work", recurrence="none", date=r_date, time=r_time, timezone=user.timezone,
            status="pending", due_at=due,
        )
        session.add(r)
        created.append(r)

    if created:
        session.add(InAppNotification(
            user_id=user.id, title=f"📥 {len(created)} reminder(s) created from forwarded email",
            body=", ".join(r.title for r in created)[:500], created_at=now))
    return created


async def handle_inbound(session: AsyncSession, recipients: str, subject: str, text: str, ics_list: list[str]) -> int:
    token = find_token(recipients)
    if not token:
        return 0
    user = await session.scalar(select(User).where(User.inbound_token == token))
    if not user:
        return 0
    created = await create_reminders(session, user, subject, text, ics_list)
    await session.flush()
    return len(created)


# ---------------------------------------------------------------- IMAP poller
def _fetch_unseen_raw() -> list[bytes]:
    box = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    out: list[bytes] = []
    try:
        box.login(settings.imap_user, settings.imap_password)
        box.select(settings.imap_folder)
        _, data = box.search(None, "UNSEEN")
        for num in data[0].split():
            _, msg_data = box.fetch(num, "(RFC822)")
            out.append(msg_data[0][1])
            box.store(num, "+FLAGS", "\\Seen")
    finally:
        try:
            box.logout()
        except Exception:  # noqa: BLE001
            pass
    return out


def parse_raw_message(raw: bytes) -> tuple[str, str, str, list[str]]:
    msg = email.message_from_bytes(raw, policy=policy.default)
    recipients = " ".join(str(msg.get(h, "")) for h in ("To", "Cc", "Delivered-To", "X-Original-To", "Envelope-To"))
    subject = str(msg.get("Subject", ""))
    body = msg.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body else ""
    ics: list[str] = []
    for part in msg.walk():
        name = (part.get_filename() or "").lower()
        if part.get_content_type() == "text/calendar" or name.endswith(".ics"):
            payload = part.get_payload(decode=True)
            if payload:
                ics.append(payload.decode(part.get_content_charset() or "utf-8", "replace"))
    return recipients, subject, text, ics


async def poll_imap() -> None:
    if not settings.imap_host:
        return
    async with SessionLocal() as session:
        if not await try_advisory_lock(session, LOCK_INBOUND):
            return
        try:
            raws = await asyncio.to_thread(_fetch_unseen_raw)
        except Exception as exc:  # noqa: BLE001
            log.warning("IMAP poll failed: %s", exc)
            return
        for raw in raws:
            try:
                recipients, subject, text, ics = parse_raw_message(raw)
                await handle_inbound(session, recipients, subject, text, ics)
            except Exception:  # noqa: BLE001
                log.exception("Failed to process inbound email")
        await session.commit()
