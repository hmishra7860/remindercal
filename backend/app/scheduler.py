from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .services import dispatcher, inbound


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    common = dict(max_instances=1, coalesce=True, misfire_grace_time=120)

    # Fires due reminders (each reminder carries its own timezone -> stored as UTC due_at)
    scheduler.add_job(dispatcher.process_due_reminders, "interval", seconds=60, id="reminders", **common)
    # Timezone-aware sweeps: send only when the recipient's local hour reaches their delivery window
    scheduler.add_job(dispatcher.process_birthdays, "cron", minute="0,15,30,45", id="birthdays", **common)
    scheduler.add_job(dispatcher.process_digests, "cron", minute="5,20,35,50", id="digests", **common)
    if settings.imap_host:
        scheduler.add_job(inbound.poll_imap, "interval", seconds=settings.imap_poll_seconds, id="inbound", **common)

    scheduler.start()
    return scheduler
