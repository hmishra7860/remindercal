from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Birthday, Reminder, User
from ..services.ics import build_ics

router = APIRouter(tags=["calendar"])


@router.get("/users/{token}/feed.ics")
async def calendar_feed(token: str, db: AsyncSession = Depends(get_db)):
    """Secret-URL iCalendar feed (subscribe from Google Calendar, Outlook or Apple Calendar)."""
    user = await db.scalar(select(User).where(User.feed_token == token))
    if not user:
        raise HTTPException(404, "Feed not found")
    reminders = (await db.scalars(select(Reminder).where(Reminder.user_id == user.id))).all()
    birthdays = (await db.scalars(select(Birthday).where(Birthday.user_id == user.id))).all()
    body = build_ics(user.full_name, list(reminders), list(birthdays))
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="remindercal.ics"', "Cache-Control": "private, max-age=300"},
    )
