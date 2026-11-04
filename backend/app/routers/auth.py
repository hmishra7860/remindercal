import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import NotificationLog, User, utcnow
from ..net_safety import UnsafeTarget, assert_public_host
from ..schemas import LoginIn, ProfileUpdate, SMTPUpdate, TokenOut, UserCreate, UserOut
from ..security import create_access_token, encrypt_secret, hash_password, verify_password
from ..services import email_service

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(u: User) -> UserOut:
    base = settings.public_base_url.rstrip("/")
    return UserOut(
        id=u.id,
        full_name=u.full_name,
        email=u.email,
        timezone=u.timezone,
        smtp_host=u.smtp_host,
        smtp_port=u.smtp_port,
        smtp_user=u.smtp_user,
        smtp_configured=bool(u.smtp_host and u.smtp_port and u.smtp_user and u.smtp_pass),
        from_email=u.from_email,
        enable_email_reminders=u.enable_email_reminders,
        enable_birthday_emails=u.enable_birthday_emails,
        enable_daily_digest=u.enable_daily_digest,
        reminder_timing=u.reminder_timing,
        delivery_method=u.delivery_method,
        webhook_url=u.webhook_url,
        feed_url=f"{base}/api/users/{u.feed_token}/feed.ics",
        inbound_address=f"save+{u.inbound_token}@{settings.inbound_domain}",
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    email = data.email.lower()
    if await db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(
        full_name=data.full_name.strip(),
        email=email,
        password_hash=hash_password(data.password),
        timezone=data.timezone or "UTC",
        from_email=email,
        feed_token=secrets.token_urlsafe(24),
        inbound_token=secrets.token_hex(6),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id), user=user_out(user))


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenOut(access_token=create_access_token(user.id), user=user_out(user))


@router.get("/profile", response_model=UserOut)
async def get_profile(user: User = Depends(get_current_user)):
    return user_out(user)


@router.put("/profile", response_model=UserOut)
async def update_profile(data: ProfileUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if field in ("timezone",) and value is None:
            continue
        setattr(user, field, value)
    if user.delivery_method in ("slack", "teams") and not user.webhook_url:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A webhook URL is required for Slack/Teams delivery")
    await db.commit()
    return user_out(user)


@router.put("/profile/smtp", response_model=UserOut)
async def update_smtp(data: SMTPUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        await assert_public_host(data.smtp_host, data.smtp_port)
    except UnsafeTarget as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    user.smtp_host = data.smtp_host.strip()
    user.smtp_port = data.smtp_port
    user.smtp_user = data.smtp_user.strip()
    if data.smtp_pass:
        user.smtp_pass = encrypt_secret(data.smtp_pass)
    user.from_email = data.from_email or user.from_email or user.email
    await db.commit()
    return user_out(user)


@router.post("/profile/smtp/test")
async def test_smtp(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Send a test email to the account owner using their own SMTP settings."""
    try:
        await email_service.send_email(
            user, user.email, "✅ ReminderCal SMTP test",
            "<p>Your SMTP settings work. ReminderCal can now send email from your own address. 🎉</p>",
            "Your SMTP settings work. ReminderCal can now send email from your own address.",
        )
        db.add(NotificationLog(user_id=user.id, email=user.email, channel="email", kind="test", status="sent",
                               message=f"Handed off to SMTP server {user.smtp_host}", sent_at=utcnow()))
        await db.commit()
        return {"ok": True, "message": f"Test email sent to {user.email}"}
    except Exception as exc:  # noqa: BLE001
        db.add(NotificationLog(user_id=user.id, email=user.email, channel="email", kind="test", status="failed",
                               message=f"{type(exc).__name__}: {exc}", sent_at=utcnow()))
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"SMTP test failed: {exc}")


@router.post("/profile/feed-token/regenerate", response_model=UserOut)
async def regenerate_feed_token(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.feed_token = secrets.token_urlsafe(24)
    await db.commit()
    return user_out(user)
