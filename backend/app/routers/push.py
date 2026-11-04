from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import PushSubscription, User
from ..schemas import PushSubscribeIn

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-key")
async def vapid_key():
    if not settings.vapid_public_key:
        raise HTTPException(503, "Web Push is not configured on this server (VAPID keys missing)")
    return {"public_key": settings.vapid_public_key}


@router.post("/subscribe")
async def subscribe(data: PushSubscribeIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    p256dh, auth = data.keys.get("p256dh"), data.keys.get("auth")
    if not p256dh or not auth:
        raise HTTPException(422, "Invalid subscription keys")
    existing = await db.scalar(select(PushSubscription).where(PushSubscription.endpoint == data.endpoint))
    if existing:
        existing.user_id, existing.p256dh, existing.auth = user.id, p256dh, auth
    else:
        db.add(PushSubscription(user_id=user.id, endpoint=data.endpoint, p256dh=p256dh, auth=auth))
    await db.commit()
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(data: PushSubscribeIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(PushSubscription).where(PushSubscription.endpoint == data.endpoint, PushSubscription.user_id == user.id))
    await db.commit()
    return {"ok": True}
