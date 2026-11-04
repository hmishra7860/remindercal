import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    # Bring-your-own SMTP (password is stored encrypted)
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smtp_user: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_pass: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    enable_email_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_birthday_emails: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_daily_digest: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_timing: Mapped[int] = mapped_column(Integer, default=9)  # local hour of day (0-23)

    delivery_method: Mapped[str] = mapped_column(String(16), default="email")  # email | slack | teams
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    feed_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    inbound_token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    last_digest_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(32), default="Personal")
    # none | daily | weekly | monthly | yearly | rolling
    recurrence: Mapped[str] = mapped_column(String(16), default="none")
    rolling_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date: Mapped[dt.date] = mapped_column(Date)
    time: Mapped[dt.time] = mapped_column(Time)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    custom_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # pending | sent | done
    status: Mapped[str] = mapped_column(String(16), default="pending")
    due_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    snooze_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Birthday(Base):
    __tablename__ = "birthdays"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[dt.date] = mapped_column(Date)
    custom_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    interests: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_wished_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reminder_id: Mapped[int | None] = mapped_column(ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True)
    birthday_id: Mapped[int | None] = mapped_column(ForeignKey("birthdays.id", ondelete="SET NULL"), nullable=True)
    email: Mapped[str] = mapped_column(String(255))  # recipient (email address or channel label)
    channel: Mapped[str] = mapped_column(String(16), default="email")  # email | slack | teams
    kind: Mapped[str] = mapped_column(String(16), default="reminder")  # reminder | birthday | digest | test
    sent_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    status: Mapped[str] = mapped_column(String(16))  # sent | failed
    message: Mapped[str | None] = mapped_column(Text, nullable=True)


class InAppNotification(Base):
    __tablename__ = "in_app_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
