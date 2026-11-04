"""Notification dispatch engine: reminders, birthdays and daily digests."""
import datetime as dt
import logging

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import SessionLocal
from ..models import Birthday, InAppNotification, NotificationLog, Reminder, User, utcnow
from ..security import create_action_token
from . import email_service, push, recurrence, templates, webhook

log = logging.getLogger(__name__)

LOCK_BIRTHDAYS = 7001
LOCK_DIGESTS = 7002
LOCK_INBOUND = 7003


async def try_advisory_lock(session: AsyncSession, key: int) -> bool:
    """Transaction-scoped advisory lock so multiple replicas never double-send."""
    return bool(await session.scalar(select(func.pg_try_advisory_xact_lock(key))))


def _is_self(user: User, email: str | None) -> bool:
    return not email or email.strip().lower() == user.email.lower()


def _record(session, user, *, kind, channel, recipient, ok, message, reminder_id=None, birthday_id=None):
    session.add(
        NotificationLog(
            user_id=user.id,
            reminder_id=reminder_id,
            birthday_id=birthday_id,
            email=recipient,
            channel=channel,
            kind=kind,
            status="sent" if ok else "failed",
            message=(message or "")[:1000],
            sent_at=utcnow(),
        )
    )


async def _send_email(session, user, to, subject, html_body, text_body, *, kind, reminder_id=None, birthday_id=None) -> bool:
    try:
        await email_service.send_email(user, to, subject, html_body, text_body)
        _record(session, user, kind=kind, channel="email", recipient=to, ok=True,
                message=f"Handed off to SMTP server {user.smtp_host}", reminder_id=reminder_id, birthday_id=birthday_id)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Email to %s failed: %s", to, exc)
        _record(session, user, kind=kind, channel="email", recipient=to, ok=False,
                message=f"{type(exc).__name__}: {exc}", reminder_id=reminder_id, birthday_id=birthday_id)
        return False


async def _send_webhook(session, user, title, text, *, kind, reminder_id=None, birthday_id=None) -> bool:
    label = f"{user.delivery_method.title()} webhook"
    try:
        await webhook.post_webhook(user.delivery_method, user.webhook_url, title, text, settings.public_base_url)
        _record(session, user, kind=kind, channel=user.delivery_method, recipient=label, ok=True,
                message="Payload accepted by webhook endpoint", reminder_id=reminder_id, birthday_id=birthday_id)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Webhook failed: %s", exc)
        _record(session, user, kind=kind, channel=user.delivery_method, recipient=label, ok=False,
                message=f"{type(exc).__name__}: {exc}", reminder_id=reminder_id, birthday_id=birthday_id)
        return False


async def _inapp(session, user, title, body, url="/dashboard.html"):
    session.add(InAppNotification(user_id=user.id, title=title[:200], body=body, created_at=utcnow()))
    try:
        await push.send_to_user(session, user.id, title, body or "", url)
    except Exception as exc:  # noqa: BLE001
        log.warning("Push failed: %s", exc)


async def _deliver_to_owner(session, user, *, subject, html_body, text_body, kind, email_enabled,
                            reminder_id=None, birthday_id=None):
    """Send to the account owner through their chosen channel (Slack/Teams webhook or SMTP email)."""
    if user.delivery_method in ("slack", "teams") and user.webhook_url:
        await _send_webhook(session, user, subject, text_body, kind=kind, reminder_id=reminder_id, birthday_id=birthday_id)
    elif email_enabled:
        await _send_email(session, user, user.email, subject, html_body, text_body,
                          kind=kind, reminder_id=reminder_id, birthday_id=birthday_id)


# ------------------------------------------------------------------ reminders
def _when_text(r: Reminder) -> str:
    return f"{r.date.strftime('%A, %d %B %Y')} at {r.time.strftime('%H:%M')} ({r.timezone})"


async def dispatch_reminder(session: AsyncSession, user: User, r: Reminder) -> None:
    subject = f"🔔 Reminder: {r.title}"
    to_self = _is_self(user, r.recipient_email)
    base = settings.public_base_url.rstrip("/")

    done_url = snooze_url = None
    if to_self:
        done_url = f"{base}/api/reminders/{r.id}/done?token={create_action_token(r.id, 'done')}"
        snooze_url = f"{base}/api/reminders/{r.id}/snooze?token={create_action_token(r.id, 'snooze')}"

    html_body, text_body = templates.reminder_email(
        title=r.title, description=r.description, category=r.category, when_text=_when_text(r),
        custom_message=r.custom_message, sender_name=user.full_name, done_url=done_url, snooze_url=snooze_url,
    )

    await _inapp(session, user, subject, r.description or _when_text(r))

    if to_self:
        plain = text_body if user.delivery_method == "email" else f"{r.description or ''}\n{r.custom_message or ''}".strip() or _when_text(r)
        await _deliver_to_owner(session, user, subject=subject, html_body=html_body, text_body=plain,
                                kind="reminder", email_enabled=user.enable_email_reminders, reminder_id=r.id)
    elif user.enable_email_reminders:
        await _send_email(session, user, r.recipient_email, subject, html_body, text_body, kind="reminder", reminder_id=r.id)


async def process_due_reminders() -> None:
    now = utcnow()
    async with SessionLocal() as session:
        stmt = (
            select(Reminder)
            .where(
                or_(
                    and_(Reminder.status == "pending", Reminder.due_at <= now),
                    and_(Reminder.snooze_until.isnot(None), Reminder.snooze_until <= now),
                )
            )
            .order_by(Reminder.due_at)
            .limit(50)
            .with_for_update(skip_locked=True)
        )
        reminders = (await session.scalars(stmt)).all()
        for r in reminders:
            try:
                user = await session.get(User, r.user_id)
                if user is None:
                    continue
                due_fire = r.status == "pending" and r.due_at <= now
                snooze_fire = r.snooze_until is not None and r.snooze_until <= now
                await dispatch_reminder(session, user, r)
                if snooze_fire:
                    r.snooze_until = None
                if due_fire:
                    recurrence.advance_after_send(r, now)
                else:
                    r.last_sent_at = now
            except Exception:  # noqa: BLE001
                log.exception("Failed processing reminder %s", r.id)
        await session.commit()


# ------------------------------------------------------------------ birthdays
async def dispatch_birthday(session: AsyncSession, user: User, b: Birthday, age: int) -> None:
    await _inapp(session, user, f"🎂 {b.name} turns {age} today", b.interests or "Don't forget to wish them!", "/birthdays.html")

    if b.email:
        if user.enable_birthday_emails:
            html_body, text_body = templates.birthday_email(
                name=b.name, age=age, custom_message=b.custom_message, sender_name=user.full_name)
            await _send_email(session, user, b.email, f"🎂 Happy Birthday, {b.name}!", html_body, text_body,
                              kind="birthday", birthday_id=b.id)
    else:
        text = f"{b.name} turns {age} today."
        if b.interests:
            text += f" Interests: {b.interests}."
        html_body, text_body = templates.reminder_email(
            title=f"{b.name}'s birthday", description=text, category="Personal",
            when_text="Today", custom_message=b.custom_message, sender_name=user.full_name)
        await _deliver_to_owner(session, user, subject=f"🎂 {b.name}'s birthday today", html_body=html_body,
                                text_body=text, kind="birthday", email_enabled=user.enable_email_reminders,
                                birthday_id=b.id)


async def process_birthdays() -> None:
    now = utcnow()
    async with SessionLocal() as session:
        if not await try_advisory_lock(session, LOCK_BIRTHDAYS):
            return
        rows = (await session.execute(select(Birthday, User).join(User, User.id == Birthday.user_id))).all()
        for b, u in rows:
            try:
                local = now.astimezone(recurrence.to_zone(b.timezone or u.timezone))
                # ">=" means a late scheduler still delivers the same day; last_wished_year prevents repeats
                if local.hour < u.reminder_timing or b.last_wished_year == local.year:
                    continue
                if recurrence.birthday_in_year(b.date_of_birth, local.year) != local.date():
                    continue
                await dispatch_birthday(session, u, b, local.year - b.date_of_birth.year)
                b.last_wished_year = local.year
            except Exception:  # noqa: BLE001
                log.exception("Failed processing birthday %s", b.id)
        await session.commit()


# ------------------------------------------------------------------ daily digest
async def process_digests() -> None:
    now = utcnow()
    async with SessionLocal() as session:
        if not await try_advisory_lock(session, LOCK_DIGESTS):
            return
        users = (await session.scalars(select(User).where(User.enable_daily_digest.is_(True)))).all()
        for u in users:
            try:
                local = now.astimezone(recurrence.to_zone(u.timezone))
                if local.hour < u.reminder_timing or u.last_digest_date == local.date():
                    continue
                today = local.date()
                reminders = (await session.scalars(
                    select(Reminder).where(Reminder.user_id == u.id, Reminder.date == today, Reminder.status != "done")
                    .order_by(Reminder.time))).all()
                bdays = (await session.scalars(select(Birthday).where(Birthday.user_id == u.id))).all()
                lines_r = [f"{r.time.strftime('%H:%M')} - {r.title}" for r in reminders]
                lines_b = []
                for b in bdays:
                    nb = recurrence.next_birthday(b.date_of_birth, today)
                    days = (nb - today).days
                    if days <= 7:
                        when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
                        lines_b.append(f"{b.name} turns {nb.year - b.date_of_birth.year} {when}")
                u.last_digest_date = today
                if not lines_r and not lines_b:
                    continue
                html_body, text_body = templates.digest_email(name=u.full_name, reminders=lines_r, birthdays=lines_b)
                await _deliver_to_owner(session, u, subject="☀️ Your ReminderCal daily digest", html_body=html_body,
                                        text_body=text_body, kind="digest", email_enabled=True)
            except Exception:  # noqa: BLE001
                log.exception("Failed digest for user %s", u.id)
        await session.commit()
