# Horizon System

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

## Day to day (two terminals)
```bash
# Terminal 1 — API at http://localhost:8000
cd backend && uv run python manage.py runserver

# Terminal 2 — UI at http://localhost:5173
cd frontend && npm run dev
```
- Application: http://localhost:5173
- Django admin: http://localhost:8000/admin

## Tests and quality
```bash
cd backend  && uv run pytest && uv run ruff check .
cd frontend && npm run test:unit -- --run && npm run lint && npm run type-check
```
