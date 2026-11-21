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
  - **Account managers are users** with the system role "Account Manager" (`users`,
    `ACCOUNT_MANAGER`); administrators manage them in Users (no separate screen; the former
    address opens Users filtered by that role). The business verticals they work in are on the
    user's profile (`UserProfile.verticals`, set by administrators; none is allowed; cleared
    when the role is removed). `GET /api/account-managers/` is a read-only list (active users
    with the role) for pickers, to everyone signed in. A user who is a customer's account
    manager cannot be deleted nor lose the role (409). The `account_managers` app only keeps
    the migrations of the former table (converted to users).
  - **People's photos** (account managers, users): `config/photos.py` (`PhotoMixin.set_photo`,
    `photo_response` for GET/POST/DELETE `/<id>/photo/`, `photo_version`). Users' photos live in
    `users.UserProfile` (`UserProfile.for_user`); anyone signed in can see them, administrators
    change them. Frontend: `src/components/PhotoField.vue` (form: crops square in the browser,
    `src/utils/image.ts::squareImage`, 192×192 JPEG; v-model = pending change, applied after
    saving) and `src/components/PersonAvatar.vue` (circle, initials without a photo; also in
    the top bar). **The account manager owns the relation**:
    verticals are assigned on the account manager, never on the vertical.
  - `customers/` — lessees (`Customer`: legal/trade name, tax ID, contact, address, active flag,
    `primary_account_manager` — required FK to a user with the Account Manager role, PROTECT —
    and `secondary_account_managers` — M2M of such users, never including the primary). `customers/tax_ids.py` validates CPF and CNPJ, including the
    alphanumeric CNPJ (in force since July 2026). CRUD at `/api/customers/`.
  - `catalogs/` — small reference tables ("Cadastros"), one model each, under `/api/catalogs/<table>/`.
    `Vertical` (business vertical): name (unique, case-insensitive), enabled flag, notes — these
    apply to all its sub-verticals. Its account managers are read-only here
    (`account_managers_detail`: users with the Account Manager role whose profile lists the vertical). `?is_enabled=true` filters.
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
    replaces/DELETE; images only), `POST /<id>/photo/from-url/` ({url, source_url}; the server
    downloads it), `GET /<id>/photo-suggestions/?q=` (SearXNG). `PriceDocument.source_url` keeps
    where an internet photo came from (`photo_source_url` in the rows). Files live in `MEDIA_ROOT` (`.env`, default `backend/media`,
    not served publicly — only through the API, logged in), random stored names; size limit
    `PRICE_DOCUMENT_MAX_MB` (25). Deleting a document removes its file; erasing the last version
    of a row removes its documents. List rows carry `documents_count` and `photo_id`.
    Pricing tests share fixtures in `pricing/conftest.py` and helpers in `pricing/testing.py`.
  - `efmv/` — **eFMV Analyses** (Pricing), `/api/efmv-analyses/`. `EfmvAnalysis`: code
    `EFMV-<year>-<NNNN>` (year + sequence, next number per year), account manager (user with the
    role; must be the customer's primary or secondary), customer, created by/at; ≥ 1
    `EfmvScenario` (official name = `title`: "<term> Months - <name>", or "<term> Months" — the
    name is optional — `efmv.models.scenario_title`, translated; unique per analysis by term +
    name case-insensitively; the tab shows it (`draft.ts::scenarioTitle`) and the list's
    `scenario_names` are titles; scenarios — and tabs — are ordered by term as a number, then
    name; tabs switch without animation; term 1–360 months, scope,
    `vertical` — required by the API — and optional `sub_vertical` of it: the assets it admits,
    by the average price's sub-vertical; `efmv.models.in_scope`; items outside are flagged
    `out_of_scope` in previews and refused on save; Vertical/SubVertical PROTECT) with
    `EfmvScenarioItem`s (an average price's `lineage` — the **current** version always counts —,
    a quantity and a `unit_value` typed by the analyst — when not typed, the current average
    price's value counts (`value_from_price` in previews) and is stored on save; the same
    price may repeat in several rows — e.g. another value per delivery state; and an optional `efmv_value` — one unit at the end of the term, typed; null = the
    price's curve at the scenario's term, `pricing/curves.py::value_at`, returned as
    `curve_value` and followed when the term or the price changes, `efmv_from_curve`). Items carry the price's `specs` for display. Each item is placed against the current average price's value
    (`pricing/positioning.py`, pure: `variation_percent` and `price_position` → below /
    slightly_below / compatible / slightly_above / above, compared at 2 places, inclusive
    limits) and flagged `expired` when that version is older than the validity; the analysis
    returns `is_outdated` (scenarios `has_expired`). Writes are nested (`scenarios` replaces them all); a
    term beyond an asset's curve (its last term) is refused per item. Figures come only from
    `efmv/calculations.py` (pure, tested): LO = Σ quantity × typed unit value; HW/SW/SV shares of
    the LO with 2 places (Average Prices are hardware; SW and SV to come); eFMV at EOL = the items' eFMV
    weighted over the LO (`efmv_total` = Σ quantity × eFMV value; `efmv_percent` = that / LO,
    %, 2 places; null without LO); each counted item's `weight_percent` = its total / LO
    (`calculations.weight_percent`; null when left out of the totals). `POST /scenario-preview/` gives the figures of a scenario
    being edited; deleted prices and items out of the curve are flagged and left out of them.
    `?search=` also finds a code. Customers: `?account_manager=<user id>` (primary or
    secondary) and `?is_active=`.
  - **Pricing control panel** (`PricingSettings` singleton in `pricing/models.py`,
    `PricingSettings.current()`), `/api/pricing/settings/` (`pricing/control_panel.py`; GET
    everyone signed in, PATCH administrators): `compatible_percent` (5), `below_percent` /
    `above_percent` (10, each greater than the compatible range), `validity_months` (12, from
    the date of the price's current version) and `accept_expired` (true; false = analyses
    refuse expired prices). Frontend: `src/modules/pricing-settings/` ("Control Panel" in the
    Pricing app, administrators only).
  - `users/` — user and role management (administrators only): `Role` (name unique
    case-insensitive, description, `is_system`, `users` M2M → `user.roles`); users can have many
    roles. System role "Administrator" (`key="administrator"`, created by a migration) cannot be
    changed or deleted and gives access to everything: check with
    `users.permissions.is_administrator(user)` / `IsAdministrator` (Django superusers count too) —
    never `is_staff`. `/api/users/` (password write-only: required on create, optional on edit,
    Django password validators) and `/api/roles/`. Lock-out rules: nobody deletes/deactivates
    themselves or removes their own Administrator role; at least one active administrator
    remains; users with records → 409 (deactivate instead); roles in use → 409.
    `/api/auth/me/` returns `is_admin` and `roles`. Employee data lives in `UserProfile` (one per
    user, created with it): identity document (type cpf|rg|national_id|passport|other + number,
    CPF validated, unique), employee number (optional, unique), nationality (ISO 3166-1),
    birth date, job title, department, work location, manager (user), hire date, phones;
    `UserSerializer` reads/writes them as flat fields. Users without a password yet
    (`has_password` false) cannot sign in until an administrator sets one. The user form has
    tabs (Account, Personal Data, Employment, Account Manager).
    **Showing a user:** always `users.display.display_name(user)` (in serializers
    `display_name_in(self.context, user)`), never `get_full_name()`/`username` directly — it
    follows the System settings `user_name_display` (username | first_name | full_name) and
    `full_name_order` (first_last "First Last" | last_first "Last, First").
  - `system/` — system-wide settings edited by administrators in the app (`SystemSettings`
    singleton, `SystemSettings.current()`), at `/api/system/settings/` (GET: everyone sees what
    is enabled, e.g. `photo_search_enabled`; PATCH and `test-searxng/`: administrators only).
    `searxng_url` turns on photo search. `system/web.py`: SearXNG image search
    (`search_images`; the instance must have `formats: [html, json]`) and `fetch_image` — safe
    download (public addresses only, DNS pinned, redirects re-checked, size limit, real image
    type by magic bytes). Never fetch user-given URLs any other way.
  - `catalogs/specs.py` — specification templates per asset class (`AssetClass.spec_template`,
    read-only in the asset class API, edited at `/api/catalogs/asset-classes/<id>/spec-template/`;
    fields: label, kind text|number|boolean|choice|rating, unit (numbers only), required, options
    (choice only); values stored as text — booleans "true"/"false", choices as written in the
    template, ratings 0–5 in half steps "3.5") and the snapshot of values stored with each
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
    The top bar shows only the signed-in user (photo or initials + name); clicking opens their
    menu (Sign out). Language and theme are changed in Settings (the language selector stays on
    the login page only).
    Module pages use `<v-container fluid class="module-page">` (full width, small side margin;
    `src/styles/main.css`). The path bar is sticky under the top bar (height
    `--horizon-path-bar-height`); on screens ≥ 960 px the column titles of every grid in a page
    (`.v-data-table` in `.v-main`) stick right under it while the rows scroll — so grids must not
    get their own vertical scroll (no `height`/`fixed-header` on page grids; dialogs may).
  - **Suite of apps** (like Microsoft 365), the suite being "Horizon": `src/apps.ts`
    (`SUITE_APPS`): "Pricing" (`/pricing/…`), "Remarketing" and "Partners and Alliances"
    (partnerships, incentive programs, discounts, fees) — both coming soon — and
    "Administração" (`/admin/…`: Customers, Catalogs — shared by every app — plus Users and
    System Settings, administrators only). App names have no "Horizon" and stay in English in
    every language; areas are translated. Every module has an `app`; `moduleRoutes()` mounts its routes under the app's
    prefix with `meta.app/module/titleKey/adminOnly` and redirects the former address without
    the prefix. Navigation: the top bar shows the app name and the app launcher
    (`AppLauncher.vue`); under it the path bar (`AppBreadcrumbs.vue`: Horizon › app › module ›
    tab, from `meta.titleKey` — child routes such as Catalogs tabs set their own); the side
    menu lists the current app's modules (outside an app: the apps); `/` is the suite's home
    (app cards). The user's own settings (`/settings`) open from the user menu.
  - `src/modules/` — one folder per business module; `src/modules/index.ts` (`MODULES`) feeds the
    router and the side menu (`adminOnly: true` hides it from non-administrators and the router guard refuses its
    routes). `account-managers/` is the reference module. `users/` (Users and Roles tabs,
    `?tab=roles`; system roles show translated via `roleText.ts`).
  - `src/modules/catalogs/` — the "Catalogs" page: one tab (and child route) per reference table,
    listed in `tabs.ts`. A new small table is a new tab here, not a new module.
  - `src/components/ServerCrudTable.vue` — generic CRUD grid (search, New, edit/delete with
    confirmation, notifications; optional `expandable` + `expanded-row` slot; column filters:
    `filters` object + `filter.<key>` slots, a row under the titles turned on/off with the
    "Filters" button — remembered per grid with `filters-storage-key`, turning off clears them); pages pass columns, texts and `item.<key>` cell slots, open
    their own form on `create`/`edit` and call the exposed `reload()` after saving. Use it for new
    simple CRUD pages (Manufacturers and Asset classes do).
  - `src/modules/average-prices/` — grid (ServerCrudTable; edit = "New version"; delete = all
    versions; rows with previous versions expand to list all versions and their average; column
    filters in `AveragePriceFilters.ts` → `?asset_class=&model=&original_value_min/max=&
    created_from/to=`), form (asset
    class decides terms and spec fields; values resolved by `/preview/`), detail (terms, monthly
    curve table, history with the average of the versions). `PriceVersionsList.vue` lists
    versions (by date and time, no numbers) and erases one; used in the detail's history and the
    grid's expanded row. Text specification fields use `SpecSuggestField.vue` (combobox with
    server suggestions; new values allowed). Detail: `PricePhoto.vue` (thumbnail in the header,
    click to enlarge; menu: file, `PhotoSearchDialog.vue`, `PhotoUrlDialog.vue`) and `PriceDocuments.vue` ("Documents" tab; drag and drop). File uploads
    go through `api()` with a `FormData` body. Sizes: `src/utils/bytes.ts`. Money typed by users: `src/utils/money.ts` (`parseMoney` accepts the
    UI language's thousands/decimal separators, returns canonical strings; `formatMoney` displays).
  - `src/modules/efmv-analyses/` — list (ServerCrudTable) and a page per analysis
    (`/pricing/efmv-analyses/new`, `/:id`; child routes of a RouterView parent), one form:
    a compact header with what is fixed (account manager — the user by default when they
    have the role —, `CustomerPicker.vue` with that account manager's customers, creation
    date) and one tab per scenario (`ScenarioPanel.vue`: name, term, scope and
    `ScenarioTotalsBar.vue` on top; assets grid below — "+ Row" adds an empty row whose
    Asset cell is `AveragePricePicker.vue` (options "Model (spec values)", manufacturer · asset
    class as subtitle; empty rows are dropped when saving); spreadsheet-like grid: row
    number (the scenario's Vertical picker — `VerticalScopePicker.vue`, each vertical
    followed by its sub-verticals — comes first and filters the asset picker; "+ Row" waits
    for it), Quantity, asset (class · specifications · price date or expired flag), Unit Value
    (the average price's value as placeholder; empty = that value), Position, eFMV (the
    curve's value at the term as placeholder; empty = that value), total, Weight (read only); plain fields fill the cells (focus/error shown on the cell), Tab goes through the
    editable cells, Enter/↓ and Shift+Enter/↑ move rows in the same column (Enter on the last
    row adds one), remove buttons appear on hover and are out of the Tab order; figures
    from `/scenario-preview/` after each change). Tabs needing attention are marked and
    saving opens the first. Exception to the page-grid rule: on screens ≥ 960 px the page
    fills the window and only the assets grid scrolls (fixed header). Form state in `draft.ts`.
  - Decimal inputs (e.g. ratings): text field with `inputmode="decimal"` (not `type="number"`,
    which drops "7,5" in some browsers), `rules.decimalRange(min, max, places)`, and
    `normalizeDecimal()` (src/utils/decimal.ts) before sending. Display with `$n(value, 'rating')`.
  - `src/components/RemoteAutocomplete.vue` — generic single/multiple picker with server-side
    search (options may carry a `subtitle`, shown as a second line); module pickers wrap it: `AccountManagerPicker.vue`, `VerticalPicker.vue` (enabled only),
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
  - Settings: `src/views/SettingsView.vue` is the user's own (language, mode, color theme);
    global settings are the `system-settings` module (Administration, administrators only),
    one card each (e.g. `src/components/SystemSettingsCard.vue`).
  - `src/stores/systemSettings.ts` — system settings (loaded once).
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
- **New business module** (follow `customers` / `src/modules/customers/`):
  - Backend: own Django app with model + serializer (normalize/validate input there) + ModelViewSet
    with `SearchFilter`/`OrderingFilter`, router under `/api/<module>/`, admin, tests, translations.
    Foreign keys to other modules use `on_delete=PROTECT`; the referenced module's viewset turns
    `ProtectedError` into HTTP 409 with a translated `detail` (see `UserViewSet.destroy`).
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
  - **Names in Title Case** (titles, menu, tabs, column headers, field labels, buttons and
    dialog titles — not sentences, hints or messages): every word capitalized except connector
    words (en: and, or, of, the, a, by, for, from, in, on, per, to, with…; pt-br: e, ou, de,
    da, do, com, por, para, em, como…; es: y, o, de, del, la, con, por, para, en, desde…).
    Hyphenated words capitalize both parts ("Sub-Vertical"); text in parentheses stays as is
    ("Allowed Terms (months)"). E.g. "Asset Classes", "Classes de Ativo", "Valores por Prazo".
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
  - **Themes** (`src/themes.ts`): each theme has colors and a font, in a light and a dark
    version (Vuetify themes "<id>-light"/"<id>-dark"); the user's mode (light/dark/system)
    picks the version (App.vue). User preference `color_theme` (backend
    `accounts.models.ColorTheme`). Themes: "Metallic Foundations" (default; #3D52A0, #7091E6,
    #8697C4, #ADBBDA, #EDE8F5), "Earthy and Serene" (#3E362E, #865D36, #93785B, #AC8968,
    #A69080) and "Sleek and Futuristic" (#2C3531, #116466, #D9B08C, #FFCB9A, #D1E8E2); all use
    the Ubuntu font (`@fontsource/ubuntu`, imported in main.ts). New theme = entry in
    `COLOR_THEMES` + choice in `ColorTheme`. Use theme colors (`primary`, `app-bar`…), never
    hard-coded ones.
  - UI: only open-source libraries without license keys (MIT/Apache/BSD). **Vuetify** components
  (auto-imported via `vite-plugin-vuetify`), `mdi-*` icons, themes in `src/themes.ts`.
  **Do not use PrimeVue/PrimeUI** — commercial license since v5.
