# Horizon

Web system for operating lease residual value pricing.

## Stack
- **Backend:** Django 5.2 LTS + Django REST Framework (Python 3.13, managed with `uv`)
- **Database:** PostgreSQL 17 on the homelab (`TrueNAS-1:5432`, database `horizon_dev`)
- **Frontend:** Vue 3 + TypeScript + Vite + Vuetify 4 (MDI icons) + Pinia + vue-i18n
- **Languages:** English (default), Brazilian Portuguese and Spanish — each user picks one under
  *Settings*, and the choice is saved to the database

## First run
```bash
cp .env.example .env              # if it does not exist yet; set the password
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

## Day to day
```bash
./dev.sh start      # start backend and frontend in the background
./dev.sh status     # is everything up?
./dev.sh logs       # follow both logs (Ctrl+C leaves; servers keep running)
./dev.sh restart    # stop + start
./dev.sh stop       # stop both
```
Every command also accepts a single service: `./dev.sh restart backend`.
PIDs and logs are kept in `.run/`.

In VS Code:
- **Run → Start Debugging (F5)** with *Horizon (backend + frontend)* runs both under the debugger
  (breakpoints in Django); the debug toolbar has Restart and Stop.
- **Terminal → Run Task…** has *Horizon: start / stop / restart / status / logs* (wrappers around `dev.sh`).

To run them in the foreground instead (two terminals):
```bash
cd backend && uv run python manage.py runserver   # API at http://localhost:8000
cd frontend && npm run dev                        # UI at http://localhost:5173
```
- Application: http://localhost:5173
- Django admin: http://localhost:8000/admin

### Access from other machines (tests)
By default only this machine can open Horizon. To open it to the local network or, through
NAT / port forwarding on the router, to the internet (tests only — still the dev servers), set
in `.env`:
```bash
DEV_LISTEN_HOST=0.0.0.0   # Vite listens on every interface (port 5173)
ALLOWED_HOSTS=*           # or the names/addresses used, e.g. 192.168.1.100,horizon.example.com
DEBUG=False               # Django's debug pages would show the environment (database password)
```
and restart the servers. Django stays on 127.0.0.1 — only the Vite server (5173) is reachable;
it forwards `/api` to Django keeping the address the browser used, so the CSRF check works
without listing origins. Firewall/NAT rules are configured outside Horizon.

### Behind a reverse proxy with HTTPS (e.g. Nginx Proxy Manager)
The proxy answers in HTTPS and forwards to the Vite server (`http://<this machine>:5173`), so
Django sees plain HTTP while the browser sends `Origin: https://…`. Then **every origin the
browser uses must be in `CSRF_TRUSTED_ORIGINS`, exactly as in the address bar — scheme, name
and port** (the proxy's public port, not 5173):
```bash
CSRF_TRUSTED_ORIGINS=http://localhost:5173,https://horizon.example.com,https://horizon.example.com:8443
```
Without it, pages load (reading needs no CSRF check) but every save fails with "Could not save.
Try again." — Django answers 403 "CSRF Failed: Origin checking failed" (see `.run/backend.log`
or the browser's Network tab). Restart the servers after changing `.env`.

### Uploaded files (photos and documents)
They are stored in `MEDIA_ROOT` (default `backend/media`, git-ignored), while the database keeps
only their names. When several machines use the same database (e.g. the homelab's PostgreSQL),
point `MEDIA_ROOT` on all of them to the same shared folder (e.g. a TrueNAS share); otherwise a
photo uploaded on one machine answers 404 on the others (initials instead of the photo).

## Tests and quality
```bash
cd backend  && uv run pytest && uv run ruff check .
cd frontend && npm run test:unit -- --run && npm run lint && npm run type-check
```
