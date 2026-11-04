"""Date/recurrence helpers. All scheduling math lives here."""
import calendar
import datetime as dt
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc


def to_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


def compute_due_at(date: dt.date, time: dt.time, tz_name: str | None) -> dt.datetime:
    local = dt.datetime.combine(date, time.replace(tzinfo=None), tzinfo=to_zone(tz_name))
    return local.astimezone(UTC)


def add_months(d: dt.date, months: int) -> dt.date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def step_date(d: dt.date, recurrence: str) -> dt.date:
    if recurrence == "daily":
        return d + dt.timedelta(days=1)
    if recurrence == "weekly":
        return d + dt.timedelta(days=7)
    if recurrence == "monthly":
        return add_months(d, 1)
    if recurrence == "yearly":
        return add_months(d, 12)
    return d


def birthday_in_year(dob: dt.date, year: int) -> dt.date:
    try:
        return dob.replace(year=year)
    except ValueError:  # Feb 29 on a non-leap year
        return dt.date(year, 2, 28)


def next_birthday(dob: dt.date, today: dt.date) -> dt.date:
    d = birthday_in_year(dob, today.year)
    if d < today:
        d = birthday_in_year(dob, today.year + 1)
    return d


def advance_after_send(r, now: dt.datetime) -> None:
    """Update a Reminder after its due notification was dispatched."""
    r.last_sent_at = now
    if r.recurrence in ("none", "rolling"):
        # rolling reminders wait for "Mark as Done" to schedule the next one
        r.status = "sent"
        return
    d = r.date
    for _ in range(5000):  # safety cap
        d = step_date(d, r.recurrence)
        if compute_due_at(d, r.time, r.timezone) > now:
            break
    r.date = d
    r.due_at = compute_due_at(d, r.time, r.timezone)
    r.status = "pending"


def mark_done(r, now: dt.datetime) -> str:
    """Mark a reminder as done. Returns a human-readable outcome."""
    r.snooze_until = None
    if r.recurrence == "rolling":
        interval = r.rolling_interval_days or 14
        local_now = now.astimezone(to_zone(r.timezone))
        new_date = (local_now + dt.timedelta(days=interval)).date()
        r.date = new_date
        r.due_at = compute_due_at(new_date, r.time, r.timezone)
        r.status = "pending"
        return f"Done! Next reminder scheduled for {new_date.isoformat()} (in {interval} days)."
    if r.recurrence == "none":
        r.status = "done"
        return "Marked as done."
    return f"Done! Next occurrence is on {r.date.isoformat()}."


def snooze(r, now: dt.datetime, minutes: int) -> dt.datetime:
    """Push a reminder forward. Returns the new fire time."""
    target = now + dt.timedelta(minutes=minutes)
    if r.status == "pending" and r.last_sent_at is None:
        # never fired yet: push the scheduled time itself
        r.due_at = max(r.due_at, now) + dt.timedelta(minutes=minutes)
        local = r.due_at.astimezone(to_zone(r.timezone))
        r.date, r.time = local.date(), local.time().replace(second=0, microsecond=0)
        return r.due_at
    r.snooze_until = target
    return target
