# CLAUDE.md — Sistema Horizon

## O que é
Sistema web multiusuário para **precificação de residuais de leasing operacional**
(estimar o valor residual de ativos ao fim do contrato). Desenvolvedor único (Fernando).
Idioma do projeto: **português do Brasil** — nomes de domínio, mensagens, commits e UI.

## Stack
- `backend/` — Django 5.2 LTS + DRF, Python 3.13, dependências com **uv** (nunca pip direto).
  - `config/` — settings, urls. Configuração via `.env` na raiz (django-environ).
  - `contas/` — autenticação por sessão (endpoints em `/api/auth/`).
  - `ativos/` — app do domínio (ainda sem modelos; regras de negócio a definir).
- `frontend/` — Vue 3 + TypeScript + Vite + PrimeVue (Aura) + Pinia + Vue Router.
  - `src/api.ts` — cliente HTTP (envia cookie de sessão e cabeçalho X-CSRFToken).
  - `src/stores/auth.ts` — estado do usuário logado.
  - Em dev, o Vite faz proxy de `/api` para `http://localhost:8000`.
- Banco: PostgreSQL 17 no homelab (`TrueNAS-1:5432`, banco `horizon_dev`).
  O banco de testes (`test_horizon_dev`) é criado/apagado pelo pytest-django.

## Comandos
- Backend: `cd backend && uv run python manage.py runserver` | `uv run pytest` | `uv run ruff check . && uv run ruff format .`
- Migrações: `uv run python manage.py makemigrations && uv run python manage.py migrate`
- Frontend: `cd frontend && npm run dev` | `npm run test:unit -- --run` | `npm run lint` | `npm run type-check`

## Convenções
- **Dinheiro e percentuais: sempre `Decimal` / `models.DecimalField`** (NUMERIC no Postgres). Nunca `float`.
  No frontend, valores monetários trafegam como string e só são formatados para exibição.
- Toda regra de cálculo de residual fica em funções puras no backend (ex.: `ativos/calculos.py`),
  com testes unitários. O frontend nunca recalcula preços por conta própria.
- API: DRF com autenticação por sessão; tudo exige login por padrão (`IsAuthenticated`).
- Nunca commitar `.env` nem senhas. Configurações novas vão no `.env.example`.
- Antes de concluir uma tarefa: rodar testes, ruff, lint e type-check.
