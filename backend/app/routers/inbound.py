import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from ..config import settings
from ..database import get_db
from ..services import inbound

router = APIRouter(prefix="/inbound", tags=["inbound"])


@router.post("/email")
async def inbound_email(
    request: Request,
    secret: str | None = None,
    x_inbound_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Webhook for inbound-email providers (Mailgun, SendGrid, Postmark, ...).

    Accepts JSON {to, subject, text, ics: [..]} or multipart/form-data with the usual
    provider field names. Protected by INBOUND_WEBHOOK_SECRET.
    """
    if not settings.inbound_webhook_secret:
        raise HTTPException(503, "Inbound email is not enabled")
    provided = x_inbound_secret or secret or ""
    if not hmac.compare_digest(provided, settings.inbound_webhook_secret):
        raise HTTPException(401, "Invalid secret")

    ics_list: list[str] = []
    if "application/json" in request.headers.get("content-type", ""):
        data = await request.json()
        recipients = str(data.get("to") or data.get("recipient") or "")
        subject = str(data.get("subject") or "")
        text = str(data.get("text") or data.get("body-plain") or "")
        raw_ics = data.get("ics") or []
        ics_list = [raw_ics] if isinstance(raw_ics, str) else [str(x) for x in raw_ics]
    else:
        form = await request.form()
        recipients = str(form.get("to") or form.get("recipient") or "")
        subject = str(form.get("subject") or "")
        text = str(form.get("text") or form.get("body-plain") or "")
        for value in form.values():
            if isinstance(value, UploadFile) and (
                (value.filename or "").lower().endswith(".ics") or (value.content_type or "") == "text/calendar"
            ):
                ics_list.append((await value.read()).decode("utf-8", "replace"))

    count = await inbound.handle_inbound(db, recipients, subject, text, ics_list)
    await db.commit()
    return {"created": count}
