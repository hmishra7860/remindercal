import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from .config import settings
from .database import engine
from .routers import auth, birthdays, feed, inbound, notifications, push, reminders
from .scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = start_scheduler() if settings.scheduler_enabled else None
    yield
    if scheduler:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, reminders, birthdays, notifications, push, feed, inbound):
    app.include_router(module.router)


@app.get("/health", tags=["system"])
async def health():
    """Liveness/Readiness probe: verifies database connectivity."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "unhealthy", "detail": str(exc)})
    return {"status": "ok"}


# Request rate / latency metrics at GET /metrics (scraped by Prometheus, not exposed through Nginx)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
