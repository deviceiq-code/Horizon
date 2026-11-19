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
    case-insensitive, `verticals` M2M = the business verticals they work in), CRUD at
    `/api/account-managers/` (DRF ModelViewSet). **The account manager owns the relation**:
    verticals are assigned on the account manager, never on the vertical.
  - `customers/` — lessees (`Customer`: legal/trade name, tax ID, contact, address, active flag,
    `primary_account_manager` — required FK, PROTECT — and `secondary_account_managers` — M2M,
    never including the primary). An account manager who is primary or secondary of any customer
    cannot be deleted (409; secondaries checked in `AccountManagerViewSet.destroy`). `customers/tax_ids.py` validates CPF and CNPJ, including the
    alphanumeric CNPJ (in force since July 2026). CRUD at `/api/customers/`.
  - `catalogs/` — small reference tables ("Cadastros"), one model each, under `/api/catalogs/<table>/`.
    `Vertical` (business vertical): name (unique, case-insensitive), enabled flag, notes — these
    apply to all its sub-verticals. Its account managers are read-only here
    (`account_managers_detail`, reverse of `AccountManager.verticals`). `?is_enabled=true` filters.
    `SubVertical`: risk (low/medium/high), allowed terms in months (ArrayField, any whole number
    1–360) and one recommended term among them. Every vertical has exactly one general
    sub-vertical ("General", stored with an empty name, shown translated), created with it, never
    renamed or deleted. The API nests `sub_verticals` in the vertical; sending it replaces the list.
    Defaults for a new vertical's General (medium; 12/24/36/48/60; recommended 36) live only in
    `catalogs/models.py` and are served at `/api/catalogs/verticals/defaults/`.
    DRF 3.18 reports nested list errors by position: `{"sub_verticals": {"1": {"field": [...]}}}`.
    `Manufacturer` and `AssetClass` feed the upcoming asset lists, at
    `/api/catalogs/manufacturers/` and `/api/catalogs/asset-classes/`.
    **Remarketing rating** (both): 0–5 star ratings in half steps (`DecimalField(2, 1)`, default 0
    — not filled in = 0 stars, never null). Manufacturer: reputation, product_quality,
    after_sales. AssetClass: liquidity, value_retention, technology_renewal, usage_breadth.
    Their simple average is `catalogs/ratings.py::average_stars` (pure function, 2 places, half
    up), returned read-only as `remarketing_average` and sortable as `?ordering=remarketing_score`
    (DB annotation with the same formula). Pending decision: whether technology_renewal (5 = fast
    renewal, usually bad for remarketing) should count inverted, and weights.
    `Manufacturer`: name (unique), ratings, enabled.
    `AssetClass`: name (unique per sub-vertical), icon (`mdi-*`; offered list in the frontend's
    `asset-classes/icons.ts`), `sub_vertical` FK with PROTECT (only sub-verticals of enabled
    verticals can be assigned; a sub-vertical/vertical with asset classes cannot be removed),
    ratings, keywords (ArrayField, lowercase, unique, max 30 × 50 chars; searchable), notes,
    enabled.
    `/api/catalogs/sub-verticals/` lists sub-verticals as picker options ("Vertical / Sub").
  - `pricing/` — **Average Prices** (core module), `/api/average-prices/`. `AveragePrice` rows are
    **immutable**: no PUT/PATCH; a change is a new row with `supersedes=<id>` (the old one gets
    `is_current=False` and stays as history). `DELETE /<id>/` erases one version for good
    (`AveragePrice.delete_version`: relinks the chain); `DELETE /<id>/history/` (the grid's
    delete) only hides every version (`deleted_at`/`deleted_by`). The current version is always
    the newest one not deleted. `GET /<id>/history/` returns `{versions, average}` (hidden versions
    are left out while the row is listed); the average of the versions is `pricing/averages.py`
    (pure, tested).
    Each row
    snapshots what it was based on: `sub_vertical` (from the asset class), `specs` (template
    fields + values), and `PricePoint`s for exactly the sub-vertical's `allowed_terms` at creation
    (each entered as `value` or `percent` of `original_value`; `value` is resolved and stored).
    `currency` per row (only BRL for now). Monthly curve: `pricing/curves.py` (pure, tested):
    month 0 = original value, straight lines between terms, stops at the last term; terms worth
    more than the previous point are only a warning (`increasing_terms`). `POST /preview/`
    resolves typed values (the form never computes prices). `GET /spec-suggestions/?asset_class=
    &key=&search=` offers specification values already used in that asset class
    (`catalogs/specs.py::suggest_values`: case/accent-insensitive, most used first).
    Catalog items used in prices cannot be deleted (409), even if the price was deleted.
    **Documents and photo** (`PriceDocument`, rules in `pricing/documents.py`): belong to the row,
    not a version — every version shares `AveragePrice.lineage` (UUID). `/<id>/documents/`
    (GET/POST multipart "file"), `/<id>/documents/<doc>/` (DELETE),
    `/<id>/documents/<doc>/download/` (`?inline=1` for PDF/images); `/<id>/photo/` (GET/POST
    replaces/DELETE; images only). Files live in `MEDIA_ROOT` (`.env`, default `backend/media`,
    not served publicly — only through the API, logged in), random stored names; size limit
    `PRICE_DOCUMENT_MAX_MB` (25). Deleting a document removes its file; erasing the last version
    of a row removes its documents. List rows carry `documents_count` and `photo_id`.
    Pricing tests share fixtures in `pricing/conftest.py` and helpers in `pricing/testing.py`.
  - `catalogs/specs.py` — specification templates per asset class (`AssetClass.spec_template`,
    read-only in the asset class API, edited at `/api/catalogs/asset-classes/<id>/spec-template/`;
    fields: label, kind text|number, unit, required) and the snapshot of values stored with each
    price. In the UI: `asset-classes/SpecTemplateDialog.vue`, opened from a row action of the
    Asset classes grid.
  - `config/filters.py` — `EnabledFilter` (`?is_enabled=true|false`) for any model with `is_enabled`.
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
    router and the side menu (`placement: 'system'` puts a module in the bottom group, next to
    Settings). `account-managers/` is the reference module.
  - `src/modules/catalogs/` — the "Catalogs" page: one tab (and child route) per reference table,
    listed in `tabs.ts`. A new small table is a new tab here, not a new module.
  - `src/components/ServerCrudTable.vue` — generic CRUD grid (search, New, edit/delete with
    confirmation, notifications; optional `expandable` + `expanded-row` slot); pages pass columns, texts and `item.<key>` cell slots, open
    their own form on `create`/`edit` and call the exposed `reload()` after saving. Use it for new
    simple CRUD pages (Manufacturers and Asset classes do).
  - `src/modules/average-prices/` — grid (ServerCrudTable; edit = "New version"; delete = all
    versions; rows with previous versions expand to list all versions and their average), form (asset
    class decides terms and spec fields; values resolved by `/preview/`), detail (terms, monthly
    curve table, history with the average of the versions). `PriceVersionsList.vue` lists
    versions (by date and time, no numbers) and erases one; used in the detail's history and the
    grid's expanded row. Text specification fields use `SpecSuggestField.vue` (combobox with
    server suggestions; new values allowed). Detail: `PricePhoto.vue` (thumbnail in the header,
    click to enlarge) and `PriceDocuments.vue` ("Documents" tab; drag and drop). File uploads
    go through `api()` with a `FormData` body. Sizes: `src/utils/bytes.ts`. Money typed by users: `src/utils/money.ts` (`parseMoney` accepts the
    UI language's thousands/decimal separators, returns canonical strings; `formatMoney` displays).
  - Decimal inputs (e.g. ratings): text field with `inputmode="decimal"` (not `type="number"`,
    which drops "7,5" in some browsers), `rules.decimalRange(min, max, places)`, and
    `normalizeDecimal()` (src/utils/decimal.ts) before sending. Display with `$n(value, 'rating')`.
  - `src/components/RemoteAutocomplete.vue` — generic single/multiple picker with server-side
    search; module pickers wrap it: `AccountManagerPicker.vue`, `VerticalPicker.vue` (enabled only),
    `SubVerticalPicker.vue` ("Vertical / Sub-vertical", enabled verticals only).
    Multiple mode has per-chip X only (no "clear all") and clears the typed text after each pick.
    `exclude` hides records chosen elsewhere (e.g. the primary account manager in the secondaries);
    `rules` makes it required. Tests pick options with `pickOption`/`openDropdown` (test-utils).
  - Remarketing UI (`src/modules/catalogs/remarketing/`): `RemarketingEditor.vue` (star inputs +
    live average preview, display only — the API's `remarketing_average` is authoritative),
    `StarRatingInput.vue` (v-rating, half stars, clicking the selected star again sets 0),
    `RemarketingAverage.vue` (average stars + number; hover shows each rating). In jsdom, v-rating
    is clicked through its labels (order 0, 0.5, 1 … 5 → index = value × 2).
  - Asset class form pieces (`src/modules/catalogs/asset-classes/`): `IconPicker.vue`,
    `KeywordsField.vue` (Enter/comma adds).
  - `src/modules/catalogs/verticals/TermsField.vue` — list of terms in months as chips with
    "Add term" (type months, Enter adds, Esc cancels).
  - Vuetify comboboxes/autocompletes with chips behave differently in jsdom and real browsers;
    when changing them, check in a real browser too. A combobox renders an
    `<input type="hidden">` before the visible one (`typeInto` skips it).
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
