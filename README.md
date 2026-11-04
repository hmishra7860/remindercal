# 🔔 ReminderCal

Push-based reminder and birthday platform. Emails are sent from **your own address** (bring-your-own SMTP), birthdays have a dedicated engine, and every delivery is logged.

**Stack:** Vanilla JS frontend · FastAPI + async SQLAlchemy + APScheduler · PostgreSQL 16 (asyncpg, Alembic) · Docker Compose / K3s · Nginx · Prometheus, Grafana, Node Exporter, cAdvisor, Alertmanager.

> This code was generated from the project specification and has **not been run or tested**. Expect to fix small issues on first launch.

## Quick start (Docker Compose)

```bash
cp .env.example .env          # then edit SECRET_KEY and POSTGRES_PASSWORD
docker compose up -d --build
```

Open http://localhost:8080, create an account, then go to **Settings → Email (SMTP)** and enter your SMTP details (Gmail: `smtp.gmail.com`, port 587, App Password). Use **Send test email** to verify.

Migrations run automatically on backend start (`alembic upgrade head`).
API docs: http://localhost:8080/api/docs

Monitoring (optional): `docker compose --profile monitoring up -d`
Prometheus :9090 · Alertmanager :9093 · Grafana :3000 (admin / `GRAFANA_PASSWORD`).

## Project layout

```
backend/    FastAPI app (app/routers, app/services), Alembic migrations, Dockerfile
frontend/   index/dashboard/reminders/birthdays/settings pages, js/, css/, sw.js
nginx/      nginx.conf + Dockerfile (serves frontend, proxies /api/ -> backend)
monitoring/ Prometheus, alert rules, Alertmanager, Grafana provisioning
k8s/        K3s manifests (namespace, postgres, backend, frontend+ingress, monitoring)
scripts/    generate_vapid.py
```

## Feature map

| Spec item | Where |
|---|---|
| BYO-SMTP | `PUT /auth/profile/smtp`, `services/email_service.py` (password encrypted at rest) |
| Birthday engine | `services/dispatcher.py` (`process_birthdays`), `services/templates.py` |
| Delivery logs | `GET /notifications`, Settings → Delivery logs |
| Custom messages | `custom_message` on reminders/birthdays, highlighted blockquote in emails |
| Actionable emails | Done / Snooze buttons → `/reminders/{id}/done` and `/snooze` (signed token) |
| Web Push | `frontend/sw.js`, `services/push.py`, `/push/*` |
| In-app bell | polls `GET /notifications/inbox` every 30 s |
| Slack / Teams | Settings → Notifications → Delivery method, `services/webhook.py` (httpx) |
| Forward-to-create | `POST /inbound/email` webhook **or** IMAP poller, `services/inbound.py` |
| Timezone-aware dispatch | IANA tz per user/reminder/birthday; scheduler sweeps compare local hour |
| Keep-in-touch | `recurrence = rolling`; "Mark as Done" sets next date = now + interval |
| `.ics` feed | `GET /users/{token}/feed.ics` (token regenerable in Settings) |
| Monitoring | `monitoring/` (+ `k8s/40-monitoring.yaml`); alerts: BackendDown, HighCPU/Memory/Disk, SlowAPIResponse |

## Notes and deliberate choices

- **Action links need one click.** Email buttons open a small confirmation page and the action runs on that page's button (POST). This stops email security scanners that pre-fetch links from marking reminders done or snoozing them by accident. Authenticated API calls (`GET`/`POST` with a bearer token) act immediately.
- **Forward address uses a random token** (`save+<token>@domain`), not the numeric user id, so addresses can't be guessed.
- **Inbound email:** point your provider's inbound webhook to `POST /api/inbound/email` with header `X-Inbound-Secret: <INBOUND_WEBHOOK_SECRET>`, or set the `IMAP_*` variables to poll a catch-all mailbox. You must configure MX/forwarding for `INBOUND_DOMAIN` yourself.
- **Web Push** needs VAPID keys: `python scripts/generate_vapid.py` (inside the backend container), put the values in `.env`. Browsers require HTTPS (localhost is allowed).
- **SSRF protection:** SMTP hosts and webhook URLs that resolve to private/loopback addresses are rejected. For local testing with MailHog set `ALLOW_PRIVATE_TARGETS=true`.
- **Birthday/digest timing:** sent once per year/day once the recipient's local time reaches your delivery hour, so a brief outage delays rather than skips them.
- **Calendar feed:** event times are exported in UTC; recurring events may shift by an hour across daylight-saving changes in some calendar apps.
- Changing `SECRET_KEY` makes stored SMTP passwords undecryptable (re-enter them in Settings).

## Deploy to K3s

```bash
docker build -t remindercal-backend:latest ./backend
docker build -t remindercal-frontend:latest -f nginx/Dockerfile .
docker save remindercal-backend:latest remindercal-frontend:latest | sudo k3s ctr images import -

# edit secrets, host name and URLs first
kubectl apply -f k8s/00-namespace-config.yaml -f k8s/10-postgres.yaml \
              -f k8s/20-backend.yaml -f k8s/30-frontend-ingress.yaml
kubectl apply -f k8s/40-monitoring.yaml        # optional
```

Edit `k8s/00-namespace-config.yaml` (domain, secrets) before applying. Use a registry instead of `ctr images import` for multi-node clusters. Prometheus in `40-monitoring.yaml` uses `emptyDir` storage; add a PVC if you need history to survive restarts.

## API summary

Auth: `POST /auth/register`, `POST /auth/login`, `GET|PUT /auth/profile`, `PUT /auth/profile/smtp`, `POST /auth/profile/smtp/test`
Reminders: `POST|GET /reminders`, `GET|PUT|DELETE /reminders/{id}`, `GET|POST /reminders/{id}/snooze`, `GET|POST /reminders/{id}/done`
Birthdays: `POST|GET /birthdays`, `GET|PUT|DELETE /birthdays/{id}`
System: `GET /notifications`, `GET /notifications/inbox`, `GET /health`, `GET /metrics`, `GET /users/{token}/feed.ics`

(Behind Nginx every path is prefixed with `/api`.)
