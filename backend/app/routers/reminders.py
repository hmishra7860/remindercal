import datetime as dt
from html import escape

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..deps import bearer, get_current_user, user_from_credentials
from ..models import Reminder, User, utcnow
from ..schemas import ReminderIn, ReminderOut
from ..security import decode_token
from ..services import recurrence

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _apply(r: Reminder, data: ReminderIn, user: User) -> None:
    tz = data.timezone or user.timezone or "UTC"
    t = (data.time or dt.time(user.reminder_timing, 0)).replace(second=0, microsecond=0, tzinfo=None)
    r.title = data.title.strip()
    r.description = data.description
    r.category = data.category
    r.recurrence = data.recurrence
    r.rolling_interval_days = data.rolling_interval_days
    r.date = data.date
    r.time = t
    r.timezone = tz
    r.recipient_email = str(data.recipient_email).lower() if data.recipient_email else None
    r.custom_message = data.custom_message
    r.due_at = recurrence.compute_due_at(data.date, t, tz)


async def _owned(db: AsyncSession, user: User, reminder_id: int) -> Reminder:
    r = await db.get(Reminder, reminder_id)
    if not r or r.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder not found")
    return r


@router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
async def create_reminder(data: ReminderIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    r = Reminder(user_id=user.id, status="pending")
    _apply(r, data, user)
    db.add(r)
    await db.commit()
    return r


@router.get("", response_model=list[ReminderOut])
async def list_reminders(
    category: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Reminder).where(Reminder.user_id == user.id)
    if category:
        stmt = stmt.where(Reminder.category == category)
    if status_filter:
        stmt = stmt.where(Reminder.status == status_filter)
    return (await db.scalars(stmt.order_by(Reminder.due_at))).all()


@router.get("/{reminder_id}", response_model=ReminderOut)
async def get_reminder(reminder_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _owned(db, user, reminder_id)


@router.put("/{reminder_id}", response_model=ReminderOut)
async def update_reminder(reminder_id: int, data: ReminderIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    r = await _owned(db, user, reminder_id)
    _apply(r, data, user)
    if r.due_at > utcnow():  # rescheduled into the future -> arm it again
        r.status = "pending"
        r.snooze_until = None
        r.last_sent_at = None if r.recurrence == "none" else r.last_sent_at
    await db.commit()
    return r


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(reminder_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    r = await _owned(db, user, reminder_id)
    await db.delete(r)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- actions
def _page(title: str, message: str, *, form_action: str | None = None, button: str = "Confirm", ok: bool = True) -> HTMLResponse:
    color = "#16a34a" if ok else "#dc2626"
    form = ""
    if form_action:
        form = (f'<form method="post" action="{escape(form_action, quote=True)}">'
                f'<button style="margin-top:18px;padding:12px 26px;border:0;border-radius:8px;background:#5b5bd6;color:#fff;font-size:16px;font-weight:600;cursor:pointer">{escape(button)}</button></form>')
    link = settings.public_base_url.rstrip("/")
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ReminderCal</title></head><body style="margin:0;background:#f4f5fb;font-family:-apple-system,Segoe UI,Roboto,sans-serif;">
<div style="max-width:440px;margin:12vh auto;background:#fff;border-radius:16px;padding:36px;text-align:center;box-shadow:0 4px 24px rgba(30,30,80,.1)">
<div style="font-size:44px">🔔</div><h2 style="color:{color};margin:10px 0">{escape(title)}</h2>
<p style="color:#555;line-height:1.5">{escape(message)}</p>{form}
<p style="margin-top:26px"><a href="{escape(link, quote=True)}" style="color:#5b5bd6">Open ReminderCal</a></p></div></body></html>"""
    return HTMLResponse(html)


async def _perform(action: str, r: Reminder, minutes: int) -> str:
    now = utcnow()
    if action == "done":
        return recurrence.mark_done(r, now)
    when = recurrence.snooze(r, now, minutes)
    return f"Snoozed. You'll be reminded again at {when.astimezone(recurrence.to_zone(r.timezone)).strftime('%H:%M on %d %b')} ({r.timezone})."


async def _handle_action(action: str, reminder_id: int, request: Request, token: str | None, minutes: int,
                         creds: HTTPAuthorizationCredentials | None, db: AsyncSession):
    # 1) Email-button flow: signed token, no login needed.
    if token:
        try:
            payload = decode_token(token)
        except jwt.PyJWTError:
            return _page("Link expired", "This link is invalid or has expired.", ok=False)
        if payload.get("type") != "action" or payload.get("rid") != reminder_id or payload.get("act") != action:
            return _page("Invalid link", "This link does not match the requested action.", ok=False)
        r = await db.get(Reminder, reminder_id)
        if not r:
            return _page("Not found", "This reminder no longer exists.", ok=False)
        if request.method == "GET":
            # Confirmation step: email scanners that pre-fetch links must not trigger the action.
            label = "Mark as done" if action == "done" else f"Snooze for {minutes} minutes"
            return _page(r.title, f"{label}?", form_action=f"{request.url.path}?token={token}&minutes={minutes}", button=label)
        message = await _perform(action, r, minutes)
        await db.commit()
        return _page("All set ✔", message)

    # 2) API flow: normal bearer authentication.
    user = await user_from_credentials(creds, db)
    r = await _owned(db, user, reminder_id)
    message = await _perform(action, r, minutes)
    await db.commit()
    return {"message": message, "reminder": ReminderOut.model_validate(r)}


@router.api_route("/{reminder_id}/snooze", methods=["GET", "POST"])
async def snooze_reminder(
    reminder_id: int, request: Request, token: str | None = None,
    minutes: int = Query(default=settings.snooze_minutes, ge=1, le=10080),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_db),
):
    return await _handle_action("snooze", reminder_id, request, token, minutes, creds, db)


@router.api_route("/{reminder_id}/done", methods=["GET", "POST"])
async def done_reminder(
    reminder_id: int, request: Request, token: str | None = None,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_db),
):
    return await _handle_action("done", reminder_id, request, token, settings.snooze_minutes, creds, db)
