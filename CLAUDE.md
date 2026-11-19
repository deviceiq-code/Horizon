# CLAUDE.md — Horizon System

## What it is
Multi-user web system for **operating lease residual value pricing**
(estimating an asset's residual value at the end of the contract). Single developer (Fernando).

## Language
- **All development is in English**: identifiers, comments, database tables/columns, API fields,
  translation keys, commit messages and documentation.
- The system's **default language is English** (`en`); Brazilian Portuguese (`pt-br`) and Spanish
  (`es`) are translations.
- Talk to Fernando in **Brazilian Portuguese**.

## Stack
- `backend/` — Django 5.2 LTS + DRF, Python 3.13, dependencies managed with **uv** (never pip directly).
  - `config/` — settings, urls. Configuration via `.env` at the repo root (django-environ).
  - `accounts/` — session authentication and user preferences (`UserPreferences`: language and
    theme), endpoints under `/api/auth/` (`login/`, `logout/`, `me/`, `preferences/`).
  - `assets/` — domain app (no models yet; business rules to be defined).
  - `account_managers/` — first business module (`AccountManager`: full_name, email unique
    case-insensitive), CRUD at `/api/account-managers/` (DRF ModelViewSet).
  - `customers/` — lessees (`Customer`: legal/trade name, tax ID, contact, address, account manager
    FK with PROTECT, active flag). `customers/tax_ids.py` validates CPF and CNPJ, including the
    alphanumeric CNPJ (in force since July 2026). CRUD at `/api/customers/`.
  - `config/pagination.py` — default pagination for lists (`?page=`, `?page_size=`, max 200).
  - `config/filters.py` — `NullsLastOrderingFilter` (empty values last in both directions); use it
    when a sortable column can be empty.
  - `locale/` — backend translations (`<locale>/LC_MESSAGES/django.po` + versioned `.mo`).
- `frontend/` — Vue 3 + TypeScript + Vite + Vuetify 4 (Material Design, MDI icons) + Pinia + Vue Router + vue-i18n.
  - `src/api.ts` — HTTP client (sends session cookie, X-CSRFToken and Accept-Language headers).
  - `src/stores/auth.ts` — logged-in user state.
  - `src/stores/preferences.ts` — language/theme in use; saved to the account via `PATCH /api/auth/preferences/`.
  - `src/i18n/` — vue-i18n; `locales/en.ts` is the reference, others are typed with `Messages`.
  - `src/layouts/MainLayout.vue` — top bar + side icon rail (expands on hover) for authenticated pages.
  - `src/modules/` — one folder per business module; `src/modules/index.ts` (`MODULES`) feeds the
    router and the side menu. `account-managers/` is the reference module.
  - `src/stores/notifications.ts` — global snackbar (`notify(text, 'success' | 'error')`).
  - `src/components/ConfirmDialog.vue` — generic confirmation dialog.
  - `src/composables/useServerTable.ts` — grid state/loading for `v-data-table-server`.
  - `src/composables/useValidationRules.ts` — translated field rules (required, email, maxLength).
  - `src/utils/countries.ts` — ISO country codes; names via `Intl.DisplayNames` in the UI language.
  - In dev, Vite proxies `/api` to `http://localhost:8000`.
- Database: PostgreSQL 17 on the homelab (`TrueNAS-1:5432`, database `horizon_dev`).
  The test database (`test_horizon_dev`) is created/dropped by pytest-django.

## Commands
- Dev servers (both, in background): `./dev.sh start|stop|restart|status|logs [backend|frontend]`
  — PIDs/logs in `.run/`. Stop the servers you started before finishing a task.
- Backend: `cd backend && uv run python manage.py runserver` | `uv run pytest` | `uv run ruff check . && uv run ruff format .`
- Migrations: `uv run python manage.py makemigrations && uv run python manage.py migrate`
- Frontend: `cd frontend && npm run dev` | `npm run test:unit -- --run` | `npm run lint` | `npm run type-check`

## Conventions
- **Money and percentages: always `Decimal` / `models.DecimalField`** (NUMERIC in Postgres). Never `float`.
  In the frontend, monetary values travel as strings and are only formatted for display.
- All residual calculation rules live in pure backend functions (e.g. `assets/calculations.py`),
  with unit tests. The frontend never recalculates prices on its own.
- API: DRF with session authentication; everything requires login by default (`IsAuthenticated`).
- **New business module** (follow `account_managers` / `src/modules/account-managers/`):
  - Backend: own Django app with model + serializer (normalize/validate input there) + ModelViewSet
    with `SearchFilter`/`OrderingFilter`, router under `/api/<module>/`, admin, tests, translations.
    Foreign keys to other modules use `on_delete=PROTECT`; the referenced module's viewset turns
    `ProtectedError` into HTTP 409 with a translated `detail` (see `AccountManagerViewSet.destroy`).
  - Frontend: `src/modules/<module>/` with `index.ts` (AppModule: route name, `mdi-*` icon,
    `titleKey`), `api.ts` (uses `listQuery`/`ListParams`), list view with `useServerTable` +
    `v-data-table-server`, and a form dialog with `useValidationRules`; register it in `MODULES`.
    Delete errors go through `deleteErrorMessage` (shows the server's 409 reason).
    Translation keys in a `<module>` section.
  - Component tests mount Vuetify via `src/test-utils.ts` (`mountWithPlugins`, `typeInto`, `click`);
    always let Vue settle between inputs (firing them together makes Vuetify validation race).
- Never commit `.env` or passwords. New settings go into `.env.example`.
- Before finishing a task: run tests, ruff, lint and type-check.
- **Internationalization** (en default, pt-br, es — Django-style lowercase codes):
  - Frontend: **no hard-coded visible text in templates/code** — always `$t('key')` / `t('key')`,
    with the key added to `en.ts`, `pt-br.ts` and `es.ts`. The test `src/i18n/__tests__/i18n.spec.ts`
    fails if a key is missing. Dates/numbers: `$d(value, 'short')`, `$n(value, 'decimal')`.
  - Backend: user-facing text with `gettext`/`gettext_lazy as _` (English msgids).
    Translations in `backend/locale/`. Without `gettext` installed, compile with
    `uvx --from babel pybabel compile -d locale -D django` (or `sudo apt install gettext` and use
    `makemessages`/`compilemessages`).
  - API response language: for logged-in users it comes from `UserPreferences`; for anonymous
    visitors, from the `Accept-Language` header (`src/api.ts` sends the current UI language).
  - New language: `LANGUAGES` in `config/settings.py` + `backend/locale/<locale>/` +
    `frontend/src/i18n/locales/<code>.ts` + entry in `LANGUAGES`/`messages` in `src/i18n/index.ts`.
- UI: only open-source libraries without license keys (MIT/Apache/BSD). **Vuetify** components
  (auto-imported via `vite-plugin-vuetify`), `mdi-*` icons, theme in `src/plugins/vuetify.ts`.
  **Do not use PrimeVue/PrimeUI** — commercial license since v5.
