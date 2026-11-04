"""Web Push (VAPID) delivery."""
import asyncio
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import PushSubscription

log = logging.getLogger(__name__)


def push_enabled() -> bool:
    return bool(settings.vapid_public_key and settings.vapid_private_key)


def _send_one(sub: PushSubscription, payload: str) -> int | None:
    """Blocking call. Returns HTTP status on failure, None on success."""
    try:
        webpush(
            subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            ttl=3600,
        )
        return None
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", 0) or 0
        log.warning("Web push failed (%s): %s", status, exc)
        return status or 500
    except Exception as exc:  # noqa: BLE001
        log.warning("Web push error: %s", exc)
        return 500


async def send_to_user(session: AsyncSession, user_id: int, title: str, body: str, url: str = "/dashboard.html") -> None:
    if not push_enabled():
        return
    subs = (await session.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id))).all()
    payload = json.dumps({"title": title, "body": body, "url": url})
    for sub in subs:
        status = await asyncio.to_thread(_send_one, sub, payload)
        if status in (404, 410):  # subscription expired
            await session.delete(sub)
