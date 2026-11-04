from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models import Birthday, InAppNotification, NotificationLog, Reminder, User
from ..schemas import InboxOut, MarkReadIn, NotificationLogOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationLogOut])
async def delivery_logs(
    status: str | None = Query(default=None, pattern="^(sent|failed)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(NotificationLog, Reminder.title, Birthday.name)
        .outerjoin(Reminder, Reminder.id == NotificationLog.reminder_id)
        .outerjoin(Birthday, Birthday.id == NotificationLog.birthday_id)
        .where(NotificationLog.user_id == user.id)
    )
    if status:
        stmt = stmt.where(NotificationLog.status == status)
    rows = (await db.execute(stmt.order_by(NotificationLog.sent_at.desc()).limit(limit).offset(offset))).all()
    out = []
    for log, r_title, b_name in rows:
        item = NotificationLogOut.model_validate(log, from_attributes=True)
        item.subject = r_title or (f"{b_name}'s birthday" if b_name else None)
        out.append(item)
    return out


@router.get("/inbox", response_model=InboxOut)
async def inbox(limit: int = Query(default=20, ge=1, le=100), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    unread = await db.scalar(
        select(func.count()).select_from(InAppNotification).where(InAppNotification.user_id == user.id, InAppNotification.is_read.is_(False))
    )
    items = (await db.scalars(
        select(InAppNotification).where(InAppNotification.user_id == user.id).order_by(InAppNotification.created_at.desc()).limit(limit)
    )).all()
    return InboxOut(unread=unread or 0, items=list(items))


@router.post("/inbox/read")
async def mark_read(data: MarkReadIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = update(InAppNotification).where(InAppNotification.user_id == user.id)
    if data.ids:
        stmt = stmt.where(InAppNotification.id.in_(data.ids))
    await db.execute(stmt.values(is_read=True))
    await db.commit()
    return {"ok": True}
