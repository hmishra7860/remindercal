"""Minimal RFC 5545 iCalendar generator for the dynamic feed."""
import datetime as dt

from ..models import Birthday, Reminder

RRULES = {"daily": "FREQ=DAILY", "weekly": "FREQ=WEEKLY", "monthly": "FREQ=MONTHLY", "yearly": "FREQ=YEARLY"}


def _esc(value: str) -> str:
    return (
        value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
        .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    )


def _fold(line: str) -> str:
    raw = line.encode("utf-8")
    parts: list[str] = []
    limit = 75
    while len(raw) > limit:
        cut = limit
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(raw[:cut].decode("utf-8"))
        raw = raw[cut:]
        limit = 74
    parts.append(raw.decode("utf-8"))
    return "\r\n ".join(parts)


def _utc(d: dt.datetime) -> str:
    return d.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(user_name: str, reminders: list[Reminder], birthdays: list[Birthday]) -> str:
    now = _utc(dt.datetime.now(dt.timezone.utc))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ReminderCal//Calendar Feed//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_esc('ReminderCal - ' + user_name)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]

    for r in reminders:
        if r.status == "done" and r.recurrence == "none":
            continue
        start = r.due_at
        lines += [
            "BEGIN:VEVENT",
            f"UID:reminder-{r.id}@remindercal",
            f"DTSTAMP:{now}",
            f"DTSTART:{_utc(start)}",
            f"DTEND:{_utc(start + dt.timedelta(minutes=15))}",
            f"SUMMARY:{_esc('🔔 ' + r.title)}",
            f"CATEGORIES:{_esc(r.category)}",
        ]
        desc = "\n".join(x for x in [r.description, r.custom_message] if x)
        if desc:
            lines.append(f"DESCRIPTION:{_esc(desc)}")
        if r.recurrence in RRULES:
            lines.append(f"RRULE:{RRULES[r.recurrence]}")
        lines += [
            "BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(r.title)}", "TRIGGER:PT0S", "END:VALARM",
            "END:VEVENT",
        ]

    for b in birthdays:
        dob = b.date_of_birth
        lines += [
            "BEGIN:VEVENT",
            f"UID:birthday-{b.id}@remindercal",
            f"DTSTAMP:{now}",
            f"DTSTART;VALUE=DATE:{dob.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(dob + dt.timedelta(days=1)).strftime('%Y%m%d')}",
            "RRULE:FREQ=YEARLY",
            f"SUMMARY:{_esc('🎂 ' + b.name + chr(39) + 's birthday')}",
            "CATEGORIES:Birthday",
            "TRANSP:TRANSPARENT",
        ]
        if b.interests:
            lines.append(f"DESCRIPTION:{_esc('Interests: ' + b.interests)}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
