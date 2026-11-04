from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ReminderCal"
    database_url: str = "postgresql+asyncpg://remindercal:remindercal@db:5432/remindercal"

    # Security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7
    action_token_expire_days: int = 30

    # URLs
    public_base_url: str = "http://localhost:8080"
    cors_origins: str = "http://localhost:8080"

    # Behaviour
    snooze_minutes: int = 60
    scheduler_enabled: bool = True
    # Set true only for local dev (e.g. MailHog on a private IP). Blocks SSRF otherwise.
    allow_private_targets: bool = False

    # Web Push (VAPID) - generate with scripts/generate_vapid.py
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@remindercal.com"

    # Forward-to-create (inbound parsing)
    inbound_domain: str = "remindercal.com"
    inbound_webhook_secret: str = ""
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    imap_poll_seconds: int = 120

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
