# Sistema Horizon

Sistema web para precificação de residuais de leasing operacional.

## Stack
- **Backend:** Django 5.2 LTS + Django REST Framework (Python 3.13, gerenciado com `uv`)
- **Banco:** PostgreSQL 17 no homelab (`TrueNAS-1:5432`, banco `horizon_dev`)
- **Frontend:** Vue 3 + TypeScript + Vite + Vuetify 4 (ícones MDI) + Pinia

## Primeira execução
```bash
cp .env.example .env              # se ainda não existir; ajuste a senha
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

## Dia a dia (dois terminais)
```bash
# Terminal 1 — API em http://localhost:8000
cd backend && uv run python manage.py runserver

# Terminal 2 — interface em http://localhost:5173
cd frontend && npm run dev
```
- Aplicação: http://localhost:5173
- Admin do Django: http://localhost:8000/admin

## Testes e qualidade
```bash
cd backend  && uv run pytest && uv run ruff check .
cd frontend && npm run test:unit -- --run && npm run lint && npm run type-check
```
