import datetime as dt
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .net_safety import validate_webhook_url_syntax

Category = Literal["Work", "Personal", "Finance", "Health"]
Recurrence = Literal["none", "daily", "weekly", "monthly", "yearly", "rolling"]
DeliveryMethod = Literal["email", "slack", "teams"]


def _check_tz(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    try:
        ZoneInfo(v)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unknown timezone '{v}'") from exc
    return v


def _blank_to_none(v):
    if isinstance(v, str) and not v.strip():
        return None
    return v


# ---------------- auth / users ----------------
class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    timezone: str | None = "UTC"

    _tz = field_validator("timezone")(_check_tz)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = None
    enable_email_reminders: bool | None = None
    enable_birthday_emails: bool | None = None
    enable_daily_digest: bool | None = None
    reminder_timing: int | None = Field(default=None, ge=0, le=23)
    delivery_method: DeliveryMethod | None = None
    webhook_url: str | None = None

    _tz = field_validator("timezone")(_check_tz)

    @field_validator("webhook_url", mode="before")
    @classmethod
    def _webhook(cls, v):
        v = _blank_to_none(v)
        if v is None:
            return None
        return validate_webhook_url_syntax(v)


class SMTPUpdate(BaseModel):
    smtp_host: str = Field(min_length=1, max_length=255)
    smtp_port: int = Field(ge=1, le=65535)
    smtp_user: str = Field(min_length=1, max_length=255)
    smtp_pass: str | None = Field(default=None, max_length=255)  # omit to keep existing
    from_email: EmailStr | None = None


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    timezone: str
    smtp_host: str | None
    smtp_port: int | None
    smtp_user: str | None
    smtp_configured: bool
    from_email: str | None
    enable_email_reminders: bool
    enable_birthday_emails: bool
    enable_daily_digest: bool
    reminder_timing: int
    delivery_method: str
    webhook_url: str | None
    feed_url: str
    inbound_address: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------- reminders ----------------
class ReminderIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: Category = "Personal"
    recurrence: Recurrence = "none"
    rolling_interval_days: int | None = Field(default=None, ge=1, le=3650)
    date: dt.date
    time: dt.time | None = None
    timezone: str | None = None
    recipient_email: EmailStr | None = None
    custom_message: str | None = Field(default=None, max_length=2000)

    _tz = field_validator("timezone")(_check_tz)

    @field_validator("recipient_email", "description", "custom_message", "time", mode="before")
    @classmethod
    def _blank(cls, v):
        return _blank_to_none(v)

    @model_validator(mode="after")
    def _rolling(self):
        if self.recurrence == "rolling" and not self.rolling_interval_days:
            self.rolling_interval_days = 14
        if self.recurrence != "rolling":
            self.rolling_interval_days = None
        return self


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    category: str
    recurrence: str
    rolling_interval_days: int | None
    date: dt.date
    time: dt.time
    timezone: str
    recipient_email: str | None
    custom_message: str | None
    status: str
    due_at: dt.datetime
    snooze_until: dt.datetime | None
    last_sent_at: dt.datetime | None
    created_at: dt.datetime


# ---------------- birthdays ----------------
class BirthdayIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None
    date_of_birth: dt.date
    custom_message: str | None = Field(default=None, max_length=2000)
    interests: str | None = Field(default=None, max_length=1000)
    timezone: str | None = None

    _tz = field_validator("timezone")(_check_tz)

    @field_validator("email", "custom_message", "interests", mode="before")
    @classmethod
    def _blank(cls, v):
        return _blank_to_none(v)

    @field_validator("date_of_birth")
    @classmethod
    def _not_future(cls, v: dt.date):
        if v > dt.date.today() + dt.timedelta(days=1):
            raise ValueError("Date of birth cannot be in the future")
        return v


class BirthdayOut(BaseModel):
    id: int
    name: str
    email: str | None
    date_of_birth: dt.date
    custom_message: str | None
    interests: str | None
    timezone: str | None
    age: int  # age they are turning on their next birthday
    next_birthday: dt.date
    days_left: int


# ---------------- notifications ----------------
class NotificationLogOut(BaseModel):
    id: int
    kind: str
    channel: str
    email: str
    status: str
    message: str | None
    sent_at: dt.datetime
    reminder_id: int | None
    birthday_id: int | None
    subject: str | None = None


class InAppOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str | None
    is_read: bool
    created_at: dt.datetime


class InboxOut(BaseModel):
    unread: int
    items: list[InAppOut]


class MarkReadIn(BaseModel):
    ids: list[int] | None = None


class PushSubscribeIn(BaseModel):
    endpoint: str
    keys: dict[str, str]
