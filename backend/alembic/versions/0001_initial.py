"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("smtp_host", sa.String(255)),
        sa.Column("smtp_port", sa.Integer()),
        sa.Column("smtp_user", sa.String(255)),
        sa.Column("smtp_pass", sa.Text()),
        sa.Column("from_email", sa.String(255)),
        sa.Column("enable_email_reminders", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("enable_birthday_emails", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("enable_daily_digest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reminder_timing", sa.Integer(), nullable=False, server_default="9"),
        sa.Column("delivery_method", sa.String(16), nullable=False, server_default="email"),
        sa.Column("webhook_url", sa.Text()),
        sa.Column("feed_token", sa.String(64), nullable=False),
        sa.Column("inbound_token", sa.String(32), nullable=False),
        sa.Column("last_digest_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_feed_token", "users", ["feed_token"], unique=True)
    op.create_index("ix_users_inbound_token", "users", ["inbound_token"], unique=True)

    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(32), nullable=False, server_default="Personal"),
        sa.Column("recurrence", sa.String(16), nullable=False, server_default="none"),
        sa.Column("rolling_interval_days", sa.Integer()),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("recipient_email", sa.String(255)),
        sa.Column("custom_message", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snooze_until", sa.DateTime(timezone=True)),
        sa.Column("last_sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index("ix_reminders_due_at", "reminders", ["due_at"])
    op.create_index("ix_reminders_snooze_until", "reminders", ["snooze_until"])

    op.create_table(
        "birthdays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("custom_message", sa.Text()),
        sa.Column("interests", sa.Text()),
        sa.Column("timezone", sa.String(64)),
        sa.Column("last_wished_year", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_birthdays_user_id", "birthdays", ["user_id"])

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("reminders.id", ondelete="SET NULL")),
        sa.Column("birthday_id", sa.Integer(), sa.ForeignKey("birthdays.id", ondelete="SET NULL")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False, server_default="email"),
        sa.Column("kind", sa.String(16), nullable=False, server_default="reminder"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("message", sa.Text()),
    )
    op.create_index("ix_notification_logs_user_id", "notification_logs", ["user_id"])
    op.create_index("ix_notification_logs_sent_at", "notification_logs", ["sent_at"])

    op.create_table(
        "in_app_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_in_app_notifications_user_id", "in_app_notifications", ["user_id"])

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(255), nullable=False),
        sa.Column("auth", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    op.create_index("ux_push_subscriptions_endpoint", "push_subscriptions", ["endpoint"], unique=True)


def downgrade() -> None:
    op.drop_table("push_subscriptions")
    op.drop_table("in_app_notifications")
    op.drop_table("notification_logs")
    op.drop_table("birthdays")
    op.drop_table("reminders")
    op.drop_table("users")
