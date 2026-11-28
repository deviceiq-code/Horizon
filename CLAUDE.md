# CLAUDE.md — Horizon

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
  - `partners/` — Services and Partnerships (no models yet; planned: a catalog of
    services for eFMV analyses, partners, incentive programs, discounts, fees).
  - `remarketing/` — Remarketing, the sale of used assets (no models yet; planned: offers built
    from the stock, sales, buyers, sales channels). The inventory — formerly this app — is
    Asset Management (`inventory/`).
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
  - `service_providers/` — **Service Providers** (a catalog, like customers): `ServiceProvider`
    (legal/trade name, tax ID unique per country, contact name, email, phone, address, active,
    notes, keywords) and `services` — ArrayField of `ServiceKind` (fixed list: warehousing,
    transport, inspection, refurbishment, repair, data_erasure, packaging, sales, disposal; at
    least one, kept in the list's order). `/api/service-providers/` (`?service=`). One that runs
    warehouses cannot be deleted (409) nor lose warehousing (400).
  - `inventory/` — **Inventory** of Asset Management (phases, decisions and RN → tests in
    `docs/inventory.md` — keep it updated). Phase 1 (foundation): `codes.py` (pure: Luhn,
    Horizon ID `H`+8 digits+check digit, container `C`…, `parse_code`, warehouse codes),
    `states.py` (pure: `AssetStatus`, `AreaType`, `TRANSITIONS` RN-01, `AREA_STATUSES` RN-02,
    `DomainError`), `services.py` (**the only writer of an asset's status/location/container**,
    RN-07: entry, move asset/container — child events per asset, RN-08 —, status change,
    reversal, label reprint, label ranges; atomic + `select_for_update`), immutable
    `MovementEvent`, `Location` tree (code = parent's + "-" + segment, never changes; global
    `VIRTUAL-TRANSIT`), `Container`, `Asset` (own spec values; serial unique per model when
    captured), `LabelRange`; Postgres sequences `inventory_horizon_id_seq` /
    `inventory_container_code_seq`. Phase 2: `Appointment` (receiving/shipping, `APT-…`,
    overlaps only warned), `ExpectedItem` (the appointment's list; pasted lists parsed by
    `expected.py`), `ReceivingLot` (`LOT-…`, from an appointment or unscheduled; not per
    contract), triage and reconciliation in `receiving.py` (pure `reconciliation.py`),
    `AccessoryBalance` (never negative), `Occurrence`, `LotAttachment`. Phase 3: `inspection.py`
    (reports — `InspectionReport` versioned, approved never changes, approver ≠ technician —,
    photos, findings valued by `PenaltyRate`, erasure certificates with the lot's
    `LotErasureTool`, part harvesting) and pure `grades.py`; **grade code "B1C"** = conservation
    A–D · functioning 1/2/3/0 · completeness C/P/I (`GRADE_CODES`; meanings in `GradeLevel`;
    `Asset.condition_grade`); kit checklist items `{item, essential}`;
    `AssetClass.required_photo_kinds`; the report page is printable (PDF by the browser). Phase 4:
    `followups.py` — access blocks (`BlockFollowUp`, deadline from the notification; released →
    new version + IN_INSPECTION; expired → chargeable + supervisor's decision), disputes
    (`Dispute`; asset `held_for_dispute`; analyst ≠ technician; upheld → new approved version),
    charges, `check_deadlines` (daily routine, idempotent; management command + cron, README)
    and `Alert`s — **always one user's** (`user` required, `read_at`; unique per user + event
    `key`): `followups.alert(role_key=…)` gives each active user with the role their own (nobody
    with it → the administrators); the API lists only the signed-in user's. Four **severities**
    (`AlertSeverity`; icon and color): info ("i" in a circle, blue), warning ("!" in a
    triangle, orange), error ("!" in a circle, red), success — completion — (a check in a
    circle, green); `followups.KIND_SEVERITY` gives each event's (or `severity=`). Two
    **scopes** (`AlertScope`): user, or system — global: `followups.notify_everyone` gives every
    active user their own copy, shown with a "System" chip. Empty: `NotificationsEmpty.vue`. Frontend: top bar
    bell `components/AlertsMenu.vue` (Haze's look: title + "You have N unread messages",
    mark-all icon, items `NotificationItem.vue` — the severity's icon and color, title, message,
    time ago; unread tinted + dot —, "View All Notifications") and the page
    `views/NotificationsView.vue` (`/notifications`: All / Unread (N), Today / Yesterday /
    Earlier, Mark All as Read, Load More); kinds' look, target page, grouping and time ago in
    `src/alerts.ts`; the unread count in `stores/alerts.ts` — checked every 15 s and when the
    window comes back into view; a new one pops up top right (`AlertsMenu`'s snackbar, click
    opens it; those already there when the page opened do not); `DeadlineSetting`, `Holiday`,
    `AgingLimit`; pure `deadlines.py` (business days). Phase 5: `disposals.py` — `Disposal` (`DSP-…`;
    relocation | lessee_sale | third_party_sale — buyer = a customer — | discard — a provider
    offering disposal — | parts — recorded by `inspection.disassemble`), `DisposalItem` (asset
    or accessory quantity, `unit_value` per unit), `DisposalFile` (document | certificate |
    other): reserve (AVAILABLE → RESERVED; held → refused; scrap joins discards and stays
    SCRAP), pick (read the shipping area, then each ID against the list → moved there),
    ship (all picked, document; discard: certificate — RN-23 → WRITTEN_OFF), cancel (all
    back); stock query `GET /stock/` + `/stock/assets/` (current report's data for pricing).
    Pages Stock and Disposals (`StockView.vue`, `DisposalsView.vue`, `DisposalView.vue`). Phase 6: `transfers.py`
    — `Transfer` (`TRF-…`; requested → approved by a supervisor → picking → in_transit →
    received | received_with_discrepancy, or cancelled before sending; `transit_days`, late →
    `transfer_late` alert, RN-25), `TransferItem` (asset with `status_before`, or accessory
    quantity; `container` it travels in), `TransferFile` (fiscal document required to send);
    eligible: available, scrap, blocked, awaiting inspection — never held; a container read =
    all its assets (they travel in it); RN-24 picking against the list; `services.transfer_out`
    / `transfer_in` (IN_TRANSIT at VIRTUAL-TRANSIT and back to the previous status where the
    receiver reads — RN-02); damage only an occurrence; surplus recorded; finish → shortages
    (`Occurrence.transfer`). Pages `TransfersView.vue`, `TransferView.vue`. Phase 7: `counting.py` —
    `InventoryCount` (`INV-…`; cyclic = chosen locations + descendants, general = whole
    warehouse; its locations are frozen: `services.check_not_counting` in `_record`), blind
    `CountReading`s, `find_divergences` (pure) on close → `CountDivergence` = adjustment approved
    or rejected with a reason by a supervisor who did not count (RN-26): not found → written
    off as lost (`services.adjust_lost`) + LOST occurrence; elsewhere → `adjust_place`;
    balance → `adjust_balance`; RN-19 `report_location_mismatch` (Movement's optional "Read
    Origin", `ui_state.readOrigin`). `indicators.py` (pure ratios + `panel()`), page
    `IndicatorsView.vue` (tiles and Vuetify bars, no chart library); `OccurrencesView.vue`
    lists every occurrence. **Blind count**: expected
    lists never reach receivers (`EXPECTED_READERS`). Roles: `users.models` receiver,
    inspection_technician, storekeeper, inventory_supervisor, commercial_finance,
    remarketing_analyst (`inventory/permissions.py`; frontend `inventory/roles.ts`). API
    refusals: 400 `{detail, field}`. `Warehouse.code` is generated ("SP01": state or country +
    number) and never changes. `Warehouse`: name (unique case-insensitive),
    `ownership` own | outsourced, `service_provider` (PROTECT; required only when outsourced —
    an active provider offering warehousing, checked when chosen; own = none), `verticals` it
    serves (M2M through `WarehouseVertical`, PROTECT: a served vertical cannot be deleted; at
    least one; only enabled ones can be added), contact on site, address, active, notes,
    keywords. `/api/inventory/warehouses/` (`?ownership=&vertical=&service_provider=`).
  - **Environments** (`config/environments.py`): Live and Development (Test), the same system
    over two databases — each with its own data and sessions (users shared, below) and its own files
    folder (`MEDIA_ROOT` / `MEDIA_ROOT_DEVELOPMENT`; storage `EnvironmentStorage`). `.env`:
    `DATABASE_URL` (live) and optional `DATABASE_URL_DEVELOPMENT`. Chosen on the login page
    (cookie `horizon_environment`, `src/environment.ts`; `GET /api/auth/environments/`
    public; `/api/auth/me/` returns `environment`; a chip on the top bar outside Live).
    `EnvironmentMiddleware` (first) swaps the thread's **"default" connection** for the
    request — so never pass `using=`/aliases: `atomic`, `select_for_update` and raw cursors
    follow. "default" is the process's own environment (`HORIZON_ENVIRONMENT`, live):
    commands run there (`HORIZON_ENVIRONMENT=development uv run python manage.py migrate`).
    In tests the other alias mirrors the test database (tests touching it:
    `django_db(transaction=True, databases=[...])`).
    **Users are one and the same in every environment**: kept in Live; the others keep a copy
    with the same ids (their records point to users) — `users/sync.py::sync_users` (roles,
    users, memberships, profiles with verticals that exist there and photo files, preferences;
    gone from Live → deleted, or inactive when records point to them). Users and Roles
    (`LiveUsersMixin`) and the preferences are read and written in Live from any environment
    and copied right after; signing in checks Live and copies before entering another
    environment; `manage.py sync_users` by hand. `activate()` nests (Live for a moment inside a
    Development request). Each user's environments: `UserProfile.environments` (new users:
    Live; the Users form's Account tab, a multiple select as Roles, at least one; nobody takes
    the current one from themselves). Signing in to one not given: 403 `{code: "environment_denied"}` (a warning on
    the login page) and a Warning notification to the administrators (kind
    `environment_denied`, ref `user:<id>` → Users searching for them).
    **Every failed sign-in** (wrong user or password) is an Error notification to the
    administrators too (kind `login_failed`: username typed, environment, address — the first
    X-Forwarded-For behind the proxy; ref `user:<id>` when the user exists), in Live.
  - **Centralized search** (`search/`): `GET /api/search/?q=&category=` — `registry.py`
    `PROVIDERS`: each category is a module's own list ViewSet (its queryset, permissions and
    `?search=`: a word finds what that grid finds) + how a record shows (uniform result: id,
    title, subtitle, meta, badge {text, color}, search — what to type in the grid —, amount,
    photo_version / icon). All: count + 5 of each; one category: up to 50; < 2 letters:
    nothing. A new searchable module = one Provider. Frontend `src/search.ts` (a category is a
    module: its icon/title from MODULES; a result opens its own page or the module's grid with
    `?search=` — `ServerCrudTable` opens already searching for it; pages searched in the
    browser by their translated names; `highlight`) and `views/SearchView.vue` (`/search?q=&
    category=`: Haze's look — count, tabs with counts, groups, View All; side menu › Pages;
    top bar's magnifier; Ctrl+K / ⌘K anywhere).
  - `config/parties.py` — shared input rules of customers, service providers and warehouses:
    `CompanyFieldsMixin` (name, trade name, tax ID: CPF/CNPJ in Brazil, unique per country —
    `tax_id_errors`), `AddressFieldsMixin` (country, email, phone, CEP/state in Brazil —
    `address_errors`) and `column_filters` (`?name=` name or keyword, `?tax_id=`, `?location=`
    city or state, `?is_active=`).
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
    `AssetClass`: name (English, unique per sub-vertical), `plural_name` (English, required;
    not sent = `catalogs/names.py::english_plural`), `translations` ({"pt-br": {name, plural},
    "es": …}, optional — empty: English; `names.localized`; folded in the form), icon (`mdi-*`; offered list in the frontend's
    `asset-classes/icons.ts`), `sub_vertical` FK with PROTECT (only sub-verticals of enabled
    verticals can be assigned; a sub-vertical/vertical with asset classes cannot be removed),
    ratings, keywords (ArrayField, lowercase, unique, max 30 × 50 chars; searchable), notes,
    enabled.
    `/api/catalogs/sub-verticals/` lists sub-verticals as picker options ("Vertical / Sub").
    `AssetModel` (`/api/catalogs/asset-models/`): manufacturer + model (unique per
    manufacturer) of an asset class, its template values as defaults (none required on the
    model), tracking unit|quantity, serial regex, kit checklist, test script, has_storage.
    Grid column filters: verticals `?name=` (name or keyword) and `?account_manager=`;
    manufacturers and asset classes `?name=` and `?remarketing_min=`
    (`catalogs.views.name_and_rating_filters`).
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
    role; must be the customer's primary or secondary), customer, `vertical` — required on
    create, one the account manager works in (their profile's verticals; 400 otherwise) — and
    optional `sub_vertical` of it (the assets its scenarios admit, by the average
    price's sub-vertical; `efmv.models.in_scope`; items outside are flagged `out_of_scope` in
    previews and refused on save; Vertical/SubVertical PROTECT; `vertical_label` in the API):
    these premises are set on creation and cannot change (400); `external_reference` (optional,
    100 chars — e.g. the opportunity's number in a CRM; not a premise: the wizard's Premises
    step, then the header's pencil, saved at once with `PATCH {external_reference}`; searched;
    under the code in the list; in the report and the disclaimer's `{external_reference}`);
    created by/at; ≥ 1
    `EfmvScenario` (official name = `title`: "<term> Months - <name>", or "<term> Months" — the
    name is optional — `efmv.models.scenario_title`, translated; unique per analysis by term +
    name case-insensitively; the tab shows it (`draft.ts::scenarioTitle`) and the list's
    `scenario_names` are titles; scenarios — and tabs — are ordered by term as a number, then
    name; tabs switch without animation; term 1–360 months, scope) with
    `EfmvScenarioItem`s (an average price's `lineage` — the **current** version always counts —,
    a quantity and a `unit_value` typed by the analyst — when not typed, the current average
    price's value counts (`value_from_price` in previews) and is stored on save; the same
    price may repeat in several rows — e.g. another value per delivery state; and an optional `efmv_value` — one unit at the end of the term, typed; negative allowed (a
    disposal cost; also as a negative %); and attached to it at most one software (SW) and one service
    (SV) — lines `EfmvScenarioItem` with `kind` hw | sw | sv and `attached_to` (a hardware line;
    services migrated from the former `service_*` fields): a name (empty: "Software" /
    "Service"), a value per unit of the hardware (≥ 0, money or `percent` of its value as typed),
    `mode` add | deduct (never worth more than the asset nor, deducted, all of it —
    `calculations.split_attachments`): added, it adds to the LO; deducted, the asset is worth
    the rest (`net_unit_value`: positioned, totalled, its eFMV % is of it); a service's eFMV is
    0, software's typed (value or % of its value; empty 0); API `service` / `software` {name,
    mode, value, line_total, weight_percent, too_high (+ efmv_value, efmv_percent)} or null.
    **Software / services of their own**: lines `kind` sw | sv without an average price —
    `description` (empty: the placeholder), quantity, `unit_value` required, eFMV (SV always 0,
    SW typed, empty 0); no positioning, curve or vertical check. HW / SW / SV shares come from
    the kinds; the automatic scope ends with "(+Service and Software)" (translated) when there
    are any. hardware eFMV null = the
    price's curve at the scenario's term, `pricing/curves.py::value_at`, returned as
    `curve_value` and followed when the term or the price changes, `efmv_from_curve`; or
    `efmv_percent` in the input — a % of the unit value, `calculations.percent_of_value`,
    resolved by the API, stored as the value; items return `efmv_percent` = eFMV / unit value). Items carry the price's `specs` for display. Each item is placed against the current average price's value
    (`pricing/positioning.py`, pure: `variation_percent` and `price_position` → below /
    slightly_below / compatible / slightly_above / above, compared at 5 places, inclusive
    limits) and flagged `expired` when that version is older than the validity; the analysis
    returns `is_outdated` (scenarios `has_expired`). Writes are nested (`scenarios` replaces them all); a
    term beyond an asset's curve (its last term) is refused per item. Figures come only from
    `efmv/calculations.py` (pure, tested): LO = Σ quantity × typed unit value; HW/SW/SV shares of
    the LO with 5 places (Average Prices are hardware; SW and SV to come); eFMV at EOL = the items' eFMV
    weighted over the LO (`efmv_total` = Σ quantity × eFMV value; `efmv_percent` = that / LO,
    %, 5 places; null without LO); each counted item's `weight_percent` = its total / LO
    (`calculations.weight_percent`; null when left out of the totals). `POST /scenario-preview/` gives the figures of a scenario
    being edited; deleted prices and items out of the curve are flagged and left out of them.
    `?search=` also finds a code. Customers: `?account_manager=<user id>` (primary or
    secondary) and `?is_active=`.
  - **Pricing settings** (`PricingSettings` singleton in `pricing/models.py`,
    `PricingSettings.current()`), `/api/pricing/settings/` (`pricing/control_panel.py`; GET
    everyone signed in, PATCH administrators): `compatible_percent` (5), `below_percent` /
    `above_percent` (10, each greater than the compatible range), `validity_months` (12, from
    the date of the price's current version) and `accept_expired` (true; false = analyses
    refuse expired prices). `report_disclaimer` ({language: text}; defaults `DEFAULT_REPORT_DISCLAIMER`, served as
    `report_disclaimer_defaults` for "Restore Default"; PATCH with some languages changes only
    those; variables {code} {customer} {account_manager} {date}). Frontend: Settings › App Settings › Pricing
    (`src/modules/pricing-settings/PricingSettingsSection.vue`; the former Control Panel —
    `/pricing/control-panel` redirects there).
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
    follows the **viewer's own** preferences (Settings → Appearance; `UserPreferences`)
    `user_name_display` (username | first_name | full_name) and `full_name_order`
    (first_last "First Last" | last_first "Last, First"), read once per serializer tree from
    the request's user.
  - **Settings are the user's own** (`UserPreferences`, Settings), except each app's App
    Settings (administrators; e.g. `PricingSettings`). `system/` only keeps the internet helpers and their messages
    (`system/messages.py::web_error_message`). Photo search (Average Prices) is part of the
    user's Internet Search Smart Tool: on (`web_search`) with a SearXNG address
    (`searxng_url`; `POST /api/auth/preferences/test-searxng/` tries one). `system/web.py`: SearXNG image search
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
  - `config/keywords.py` — keywords of every record created with a "New" form: model field
    `keywords_field()`, serializer `KeywordsField` (lowercase, single spaces, no blanks or
    duplicates, max 30 × 50 chars) and `KeywordSearchFilter` (`?search=` also finds any keyword
    containing the text; `keywords_lookup` on the view when they live elsewhere, e.g.
    `profile__keywords`). A new "New" form gets them too.
  - `config/pagination.py` — default pagination for lists (`?page=`, `?page_size=`, max 200).
  - `config/filters.py` — `NullsLastOrderingFilter` (empty values last in both directions); use it
    when a sortable column can be empty.
  - `locale/` — backend translations (`<locale>/LC_MESSAGES/django.po` + versioned `.mo`).
- `frontend/` — Vue 3 + TypeScript + Vite + Vuetify 4 (Material Design, MDI icons) + Pinia + Vue Router + vue-i18n.
  - `src/api.ts` — HTTP client (sends session cookie, X-CSRFToken and Accept-Language headers).
  - `src/stores/auth.ts` — logged-in user state.
  - `src/stores/preferences.ts` — language/theme/interface size in use; saved to the account via
    `PATCH /api/auth/preferences/`.
  - **Smart Tools** (Settings card; the name is not translated): conveniences each user turns
    on or off, `src/smartTools.ts` installed in App.vue. "Select on Focus" (preference
    `select_on_focus`, on by default; also kept in the browser for the login page): entering a
    single-line text field selects its content (not textareas, read-only or empty fields).
    "Word Dictionary" (`word_dictionary`, on): a word typed in a form becomes the shared
    dictionary's spelling when the field is left ("ltda" → "LTDA", "s/a" → "S/A"; whole words —
    never touching a letter or digit —, any case) — `src/wordDictionary.ts` (`applyDictionary`,
    pure; `appliesTo`: text fields and text areas inside a `.v-dialog form` / `form.v-form`, not
    e-mail/password/url/number/numeric/decimal inputs nor pickers nor `[data-no-dictionary]`;
    the input event is dispatched so v-model follows), installed in App.vue; the words in
    `stores/dictionary.ts`, loaded once signed in. The dictionary is shared, per environment:
    `system.DictionaryWord` (replacement + variants; a way of typing belongs to one word only),
    `/api/system/word-dictionary/` (GET everyone, write administrators; no pagination), kept in
    Settings › App Settings › Administration (`views/settings/WordDictionarySection.vue`, with a
    "Try It" field; each word's own spelling, lowercase, is a fixed chip among the ways to type
    it — `ListItemsField`'s `fixed`); starts with LTDA and S/A (sa., s.a., s.a).
    "Remove Extra Spaces" (`trim_spaces`, on): right after it, the same fields lose spaces at
    the start/end and repeated ones when left (" Teste    de  String " → "Teste de String";
    text areas keep their line breaks) — `src/tidySpaces.ts` (`tidySpaces`, pure;
    `installTidySpaces`, installed before the dictionary so it sees the tidy text; skips
    `[data-no-tidy]`).
    "Automatic Scope" (`auto_scope`, on; `scope_threshold` %, default 5): eFMV scenarios' scope
    is written from their assets — `efmv/scope.py::scope_summary` (pure): units by manufacturer
    and asset class (plural, in the user's language), groups under the threshold left out,
    manufacturers' classes together, at most 3 parts + "other assets"; services not included —
    returned as `scope_suggestion` (preview and analysis): the Scope field's placeholder (in gray;
    an empty scope means it, also in the list's expanded rows); typed text is the analyst's and
    never changed; a wand copies it into the field to edit it.
  - **Date and time formats**: preferences `date_format` (auto — by the language — | dmy | mdy
    | ymd) and `time_format` (auto | 24h | 12h), chosen in Settings (`accounts.models.DateFormat`
    / `TimeFormat`). Format dates with `useDateFormat().d(value, 'short' | 'dateTime')`
    (`src/dateFormat.ts`), never vue-i18n's `d`/`$d`.
  - **Numbers and currency** (Settings → Language and Region; `src/numberFormat.ts`):
    preferences `number_format` (auto — by the language — | dot_comma 1.234,56 | comma_dot
    1,234.56 | space_comma 1 234,56), `percent_places` (1–5, default 2: every percentage shown,
    `$n(v, 'percent' | 'percentValue')`), `currency` (the user's, ISO 4217 from
    `accounts.models.CURRENCIES`; its symbol and code shown) and `currency_display` (symbol |
    code). Every number goes through `numberLocale()`: `$n` (overridden in `i18n/index.ts`),
    `useNumberFormat().n` (never vue-i18n's `n`) and `utils/money.ts`. **Value fields** always
    show the currency (symbol or code) on the left and the value on the right, formatted when
    left: `src/components/MoneyField.vue` (the eFMV grid's cells and the terms follow the same
    look).
  - **Preferences live in the database** (`UserPreferences`), so they follow the user to any
    computer; the browser only keeps a copy for the login page. The interface's own state
    (side menu open/collapsed per window size, each grid's filter row) is `ui_state` (JSON,
    `preferences.saveUiState`), not localStorage.
  - **Settings** (`/settings`) in tabs: Language and Region, Appearance, Smart Tools and — for
    administrators only (tab hidden, `?tab=appSettings` ignored) — App Settings
    (`views/settings/AppSettingsTab.vue`: a section per app of `SUITE_APPS`, each app's
    settings its component in `APP_SETTINGS` — Pricing: `PricingSettingsSection.vue`; the others
    "no settings yet"; the same for everyone; every change saved on its own, fields when left,
    switches at once) (`?tab=`),
    laid out as Haze's settings: full width, a small caption per group (`.group-title`, with
    `.control-wide`/`.control-narrow` in main.css under `.settings-page`), cards of rows —
    `src/components/SettingRow.vue` (title and description on the left, the control on the
    right; `below` slot for wide content; `child`: a setting that depends on the one above —
    indented, no separator).
  - **Search the Internet** beside some text fields (`src/components/WebSearchButton.vue` in
    the field's `#append-inner`: disabled while empty, out of the Tab order, opens a new tab):
    Average Prices' Model (searched with its manufacturer: "Dell P2423H"); Customers' legal
    name, trade name and tax ID; Manufacturers' name. A Smart Tool (`web_search`, on by
    default; off: the button is not shown).
    A page cannot use the browser's default search engine, so it is the preference
    `web_search_engine` (`accounts.models.WebSearchEngine`, Google by default; Settings →
    Smart Tools; addresses in `src/webSearch.ts`).
  - **Interface size** (`src/uiScale.ts`, applied in App.vue): CSS `zoom` on the page (Vuetify
    sizes spacing/fields in px, so only scaling fonts would not do). Preference `ui_scale`
    (`accounts.models.UiScale`): auto (default; by the window's width: ≤1366 px 0.88 → 1920 px
    1 → ≥2560 px 1.1) | small 0.88 | normal 1 | large 1.1; chosen in Settings. The zoom is also
    in `--ui-zoom`: heights tied to the window divide by it (`calc(100dvh / var(--ui-zoom, 1))`),
    or they shrink with the zoom.
  - **Logo** (the sun rising over the horizon; name "Horizon", slogan "One Step Ahead" — the
    brand's, the same in every language: `app.slogan`): `components/HorizonMark.vue` (the mark,
    fixed brand colors: orange sun, emerald horizon #00926F) and
    `HorizonLogo.vue` (mark + name + slogan in capitals, the theme's font; login page).
    **Browser icon**: `public/favicon.svg` — the mark in white on emerald (#00926F), simplified
    for small sizes —, with `favicon.ico` and `apple-touch-icon.png` made from it (cairosvg); the
    side menu's brand is this icon drawn by `components/BrandIcon.vue` in the theme's `brand`
    color (every theme version has one; German Powerhouse: #FF2063) + "Horizon" written plainly;
    the tab's icon follows it too (`src/favicon.ts::applyFavicon`, watched in App.vue: the link
    elements point to an SVG data URL in the current version's `brand`; the files stay the
    default until the theme is known).
  - `src/i18n/` — vue-i18n; `locales/en.ts` is the reference, others are typed with `Messages`.
  - `src/layouts/MainLayout.vue` — the frame of authenticated pages (a clean dashboard look):
    dark side menu (288 px; theme colors `sidebar`, `on-sidebar`, `on-sidebar-strong`, `sidebar-active` — the open page's icon —, `sidebar-highlight` — its background —, `brand` — the Horizon icon;
    the brand fixed on top and Settings fixed at the bottom, the menu between them scrolls
    without scrollbars) with the Horizon brand, Home, a section named after the current app with its modules, a
    section "Pages" (in every app: Search, Notifications with the unread count), a section "Apps" with
    the other apps, Settings at the bottom; open from 1440 px, collapsed to
    icons below (they expand on hover); the top bar's button opens/collapses it and the choice
    is remembered with the account (preferences' `ui_state.sideMenu.wide|narrow`). Phones: a drawer.
    Light top bar: that button, the path (`AppBreadcrumbs.vue`); then Search, Documentation and
    Notifications (the user's alerts), the app launcher and the signed-in user (photo or
    initials + name; their menu: name, e-mail and roles — `/api/auth/me/` `email`, `role_refs` —,
    Dark Mode (a switch) and Language (`LanguageSelector.vue item`: the current one, the
    languages beside it; on the login page it is a globe + code button), Profile and Help &
    Support coming soon, Settings, Sign out).
    Settings also has language, mode, color theme and interface size.
    Module pages use `<v-container fluid class="module-page">` (full width, 24 px margin;
    `src/styles/main.css`, which also sets the shared look: cards 16 px corners + soft shadow
    `--v-card-shadow`, buttons/fields 10 px corners, page titles `h1` 24 px semibold, normal
    letter spacing; fields the browser auto-fills keep the theme's look — no yellow; an icon button with a
    badge shows it whole — buttons clip, so one with a badge does not). On screens ≥ 960 px the column titles of every grid in a page
    (`.v-data-table` in `.v-main`) stick under the top bar while the rows scroll — so grids must not
    get their own vertical scroll (no `height`/`fixed-header` on page grids; dialogs may).
  - **Suite of apps** (like Microsoft 365), the suite being "Horizon": `src/apps.ts`
    (`SUITE_APPS`): "Pricing" (`/pricing/…`; menu: eFMV Analyses first — the app opens it —, Average Prices), "Asset Management", "Remarketing", "Services and Partnerships"
    (`/partners/…`; a skeleton: modules Services, Partners, Incentive Programs, Discounts and
    Fees, each `components/UnderConstruction.vue` — purpose and what is planned, texts under
    its `textKey`, here `partners.<page>`; backend app `partners/` without models yet),
    "Remarketing" (`/remarketing/…`, `mdi-storefront-outline`; a skeleton the same way:
    Offers, Sales, Buyers, Sales Channels — `remarketing.<page>`; backend app `remarketing/`)
    and
    "Administração" (`/admin/…`, two side menu sections: Management — Users and Roles,
    administrators only — and Catalogs — Customers, Service Providers, Verticals, Asset
    Classes, Manufacturers, shared by every app). Asset Management (`/asset-management/…`,
    `mdi-archive-cog-outline` — not a forklift: those are assets we lease (MHE); formerly the Remarketing app — `SuiteApp.formerPath`: its addresses under
    `/remarketing/` redirect, `moduleRoutes`; app id `assets`): section
    Inventory — Appointments (calendar `v-calendar` + list), Receiving (lots; lot page
    `/asset-management/inventory/receiving/:id`), Inspection (queue; report page
    `/asset-management/inventory/inspection/:id` — `InspectionWizard.vue` for drafts, `ReportSheet.vue`
    printable), Movement, Assets, Accessories, Locations, Containers, Labels
    (`src/modules/inventory/`), section Inventory Catalogs — Grades, Penalty Table, Erasure Tools — and
    Warehouses (`/asset-management/inventory/<page>`). Scan screens are for barcode guns (keyboard
    wedge + Enter; focused field, color + sound — `inventory/beep.ts`); codes checked in the
    browser by `src/utils/inventoryCodes.ts`; labels are Code 128 SVG (`src/utils/code128.ts`,
    no library) printed one per 50 × 30 mm page from a hidden frame (`inventory/labels.ts`). App names have no "Horizon" and stay in English in
    every language; areas are translated. Every module has an `app`; `moduleRoutes()` mounts its routes under the app's
    prefix with `meta.app/module/titleKey/adminOnly` and redirects the former address without
    the prefix. Navigation: the top bar shows the path (`AppBreadcrumbs.vue`: Horizon › app › module
    (› page, from `meta.titleKey` — child routes set their own) and the app launcher
    (`AppLauncher.vue`); the side menu lists the current app's modules by section (an
    `AppModule.section` translation key, e.g. `menu.sections.management`; none: the app's name)
    and the other apps; `/` is the suite's home (welcome banner with soft waves + app cards). The user's own settings (`/settings`) open from the user menu.
  - `src/modules/` — one folder per business module; `src/modules/index.ts` (`MODULES`) feeds the
    router and the side menu (`adminOnly: true` hides it from non-administrators and the router guard refuses its
    routes). `account-managers/` is the reference module. `users/` exports two modules,
    `users` (`/admin/users`) and `roles` (`/admin/roles`; the former `?tab=roles` redirects;
    system roles show translated via `roleText.ts`; Roles is a page of cards like Haze's —
    `RolesView.vue`: name, users count, members as chips (the API's read-only `members`,
    six then "+N more"), description, keywords; edit/delete on the card, system roles locked).
  - `src/modules/catalogs/` — one module per reference table (section Catalogs of
    Administration), each a page `CatalogPage.vue` (title, subtitle, the table's `<Name>Tab.vue`)
    at `/admin/catalogs/<table>` (`/admin/catalogs` opens the first). A new small table is a new
    entry in `catalogs/index.ts` (+ MODULES); customers and service providers use the exported
    `catalog()` in their own folders (`/admin/customers` redirects).
    **Every catalog page follows Asset Classes'** (also Warehouses): `CatalogPage` +
    `ServerCrudTable` with a filter row (`src/composables/useColumnFilters.ts`: text filters
    applied after a pause; "Name or Keyword" on the name column, selects with "All"), the
    name cell with keywords/trade name below (an icon only when each record has its own, as
    asset classes), status chips
    (`EnabledChip` or `src/components/ActiveChip.vue`). Address blocks:
    `src/components/AddressFields.vue`.
  - `src/components/ServerCrudTable.vue` — generic CRUD grid (search, New, edit/delete with
    confirmation, notifications; optional `expandable` + `expanded-row` slot; column filters:
    `filters` object + `filter.<key>` slots, a row under the titles turned on/off with the
    "Filters" button — remembered per grid with `filters-storage-key`, in the account's `ui_state`; turning off
    clears them; `hide-create` hides "New"; `toolbar` slot: buttons between Filters and New; `selectable` + `v-model:selected`: a checkbox per row, ids kept across pages, no select-all); pages pass columns, texts and `item.<key>` cell slots, open
    their own form on `create`/`edit` and call the exposed `reload()` after saving. Use it for new
    simple CRUD pages (Manufacturers and Asset classes do).
  - **Battle Cards** (`src/components/BattleCards.vue`: cards as columns of one grid, a line per
    attribute so they align; picture in a small fixed frame; trophies for the `best` cells and
    their count per card; `src/utils/battle.ts`: `MAX_COMPARED` = 3, `winners` — the highest,
    no trophy for ties or a lone value). Used by Average Prices and Asset Classes (ratings and
    their average compete; the specification template comes last and does not compete).
  - **Specification template import** (Asset Classes): "Import Template" brings the fields of
    another asset class — of the same vertical (default) or of any vertical (a selector in the
    import dialog) (`asset-classes/templateImport.ts`: add the
    missing ones by name, or replace keeping the keys of same-named fields); saved with the
    template.
  - **Compare** (Average Prices): "Compare" (between Filters and New) turns on row checkboxes;
    2–3 prices (`compare.ts::MAX_COMPARED`) open `ComparePricesDialog.vue` — Battle Cards
    (one grid: a column per card, a line per attribute, aligned across cards; photo in a fixed
    small frame, model, class, original value, eFMV per term, specs last — they may differ); the trophy marks the best
    value of each attribute (highest eFMV % at a term, most stars in a rating — values from
    the API, nothing recalculated; ties and lone values never win) and each card counts its wins.
  - `src/modules/average-prices/` — the photo and documents are managed in the form's third
    tab, **Photo and Documents** (`PriceMediaTab.vue`): every change pending (`media.ts`:
    `MediaChanges`, `applyMediaChanges` after saving; Cancel discards them); they belong to
    the row, so **they never create a version**: saving with the price itself unchanged
    (`sameAsSource`) only applies them (button "Save", notice "Photo and documents saved.").
    The photo search runs before the price exists (`GET /photo-suggestions/?q=`, the form gives
    manufacturer + model + asset class); search and URL dialogs only give the image back, the
    server downloads it on save. The detail view is read-only (`PricePhoto`, `PriceDocuments`).
    Form tabs: Asset (class, manufacturer, model,
    description, keywords, specifications) and eFMV (a field per term, as the eFMV cells:
    money or "70%" of the original value — `termInput.ts::parseTermInput` —, a % becomes its
    value when the field is left, chip "% Value (x%)" below; `TermPointsInput.vue`), the
    original value in the header on the right (FormDialog `heading-end`); saving opens the tab
    with an error; grid (ServerCrudTable; edit = "New version" (`mdi-update`); "Create Copy"
    (`mdi-file-replace-outline`, also in the detail, from any version) = the form with `copy`:
    prefilled from the row — asset, specs, values, keywords and its photo (fetched and sent as
    a file) —, saved as a new price of its own (no `supersedes`; documents stay with the
    original); delete = all
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
  - `src/modules/efmv-analyses/` — list (ServerCrudTable, latest updated first — Last Update:
    `updated_at` + `updated_by_name`; deleting is only there; a row expands
    to `AnalysisScenariosPanel.vue`: each scenario's assets by kind, LO, eFMV at EOL and HW/SW/SV
    bar, loaded
    from the analysis's GET when expanded; a scenario's name opens the analysis on its tab —
    `?scenario=<id>`, used on the first load only) and, as
    child routes of a RouterView parent, `/pricing/efmv-analyses/new` — `EfmvWizardView.vue`,
    3 steps: Premises (account manager — the user by default when they have the role —,
    `CustomerPicker.vue` with that account manager's customers, `VerticalScopePicker.vue` with
    only the verticals they work in (`verticals` prop);
    beside them the account manager's card from `GET /account-manager-summary/?account_manager=`:
    photo, analyses, top 5 verticals by analyses, active customers as primary AM), Services and
    Partnerships and Alliances (coming soon); "Create Analysis" posts the premises and a first
    scenario ("36 Months") and opens it — and `/:id` (`EfmvAnalysisView.vue`): a compact header
    with the premises as labels and the creation date (saving PATCHes only `scenarios`);
    **Print** (`ReportDialog.vue`): choose the scenarios and whether each one's list of assets
    goes; `report.ts::reportHtml` makes a whole HTML document (customer, analysis, account
    manager, vertical, date; per scenario its title, scope, LO, eFMV at EOL, HW / SW / SV, its
    services and software — attached and of their own —, optionally the assets; at the end the
    Pricing settings' disclaimer, English when empty, its variables filled — `fillDisclaimer`;
    also who created it and when) in the language chosen in the dialog (the user's at first:
    texts via `t(key, values, {locale})`, scenario names via `scenarioTitle`, numbers and money
    in that language; what the API writes — asset classes, the automatic scope — stays in the
    user's); it follows the user's theme (`ReportStyle`: the light version's primary, `brand`
    as accent, text and tint, and its font — the page's @font-face rules copied into the frame,
    files served by Horizon), previewed in an iframe (`srcdoc`) and that frame printed — the
    PDF's suggested name is its `<title>`, `report.ts::reportFileName` ("<code> - <customer> -
    <vertical>"; "/" becomes " - ", characters file names refuse dropped), also the page's
    `document.title` while printing (restored on `afterprint`); made
    from the analysis as last saved; never stored — also from the list's Actions (a printer
    icon). While the project is private: **Shift + Print** prints it without the "Horizon"
    name (`ReportOptions.unbranded`; not shown on screen; through `utils/html.ts::printDocument`,
    a hidden frame — the preview keeps the name). And one
    tab per scenario — a toolbar beside the tabs adds one and duplicates/removes the
    open one — (`ScenarioPanel.vue`: name, term, scope and
    `ScenarioTotalsBar.vue` on top, in a grid lined up with the fields — name and term beside LO and eFMV at EOL (`part="main"`), the scope beside the LO's mix (`part="shares"`: a grey borderless panel with one bar, a segment per share in the list's colors, then HW / SW / SV with icon, percentage and value — the API's `hw_total`/`sw_total`/`sv_total`); assets grid below — "Add" (a menu: Hardware / Software / Service; "Attach" — Software / Service — under the selected hardware) adds an empty row whose
    Asset cell is `AveragePricePicker.vue` (options "Model (spec values)", manufacturer · asset
    class as subtitle; "New Average Price" always ends the list — `RemoteAutocomplete`'s
    `append-item` slot — and opens `AveragePriceFormDialog` with the text typed as its model
    (`initialModel`) and only the analysis's vertical / sub-vertical's asset classes
    (`scopeVertical`/`scopeSubVertical`); saved, the new price fills the row; empty rows are
    dropped when saving); spreadsheet-like grid: row
    number (assets counted by kind beside "Assets" — `AssetCounts.vue`, `draft.ts::assetCounts`:
    units by quantity: HW assets, SW, SV services —; the analysis's vertical, shown as a chip beside "Assets", filters the asset
    picker), Quantity, asset (class · specifications · price date or expired flag), Unit Value
    (the average price's value as placeholder; empty = that value; its Position chip below it
    in the same cell), eFMV (the
    curve's value at the term as placeholder; empty = that value; "25%" becomes its value when
    the cell is left; its % of the unit value below it, as a chip "% Value (50.69%)"), total (its Weight — share of the LO — below it, as a chip "Weight (50.69%)"); a click selects
    one row (asset or service; highlighted) and "Add Service" / "Remove" on the toolbar act on
    it; a right click selects the row and opens a menu with the toolbar's options (Add Row, Add
    Service, Remove); no remove column; a service is a row under its asset showing only Asset (name; empty = the
    placeholder "Service", sent as its name), Unit Value (value or %; a chip toggles
    added/deducted) and Total; deducted, the asset's Unit Value shows the
    API's `net_unit_value` (highlighted) except while it is being edited (the value typed); money cells show the currency symbol on the left
    (`utils/money.ts::currencySymbol`) and the number on the right, and share one layout
    (`.money-cell`: a value line and a chip line of fixed heights) so they line up across the row; plain fields fill the cells (focus/error shown on the cell), Tab goes through the
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
  - Asset class form pieces (`src/modules/catalogs/asset-classes/`): `IconPicker.vue`.
  - **Every "New" form has Keywords**: `src/components/KeywordsField.vue` (chips; Enter/comma
    adds; rules in `src/utils/keywords.ts`; tests type them with `typeKeywords`). Customers,
    users (on the Account tab; stored in `UserProfile`), roles, verticals, asset classes,
    manufacturers, average prices (a new version starts with the previous one's) and eFMV
    analyses (wizard's Premises step; not a premise — changed on the analysis's header, saved
    at once with `PATCH {keywords}`).
  - `src/modules/catalogs/verticals/TermsField.vue` — list of terms in months as chips with
    "Add term" (type months, Enter adds, Esc cancels).
  - Vuetify comboboxes/autocompletes with chips behave differently in jsdom and real browsers;
    when changing them, check in a real browser too. A combobox renders an
    `<input type="hidden">` before the visible one (`typeInto` skips it).
  - Settings: `src/views/SettingsView.vue` — the user's own, plus App Settings (administrators)
    (the former `/admin/system-settings` opens Settings → Smart Tools). A child setting
    (`SettingRow child`) stays shown when its parent is off, only disabled (`disabled`).
  - `src/stores/notifications.ts` — global snackbar (`notify(text, 'success' | 'error')`).
  - **Every form dialog has three parts** — `src/components/FormDialog.vue`: header (basic
    information about the form: icon, title, a subtitle such as the record being edited;
    `heading` slot to replace them, `header` slot for more fixed content such as tabs or a
    search field), body (default slot: the other controls — **the only part that scrolls**) and
    footer (`actions` slot: only the form's buttons, on the right). `heading-end`: what
    matters most, on the header's right (e.g. a price's original value). The whole dialog is one
    form (`@submit`, exposed `validate()`); never nest another `v-form` inside it.
  - `src/components/ConfirmDialog.vue` — generic confirmation dialog (a FormDialog too).
  - `src/composables/useServerTable.ts` — grid state/loading for `v-data-table-server`.
  - `src/composables/useValidationRules.ts` — translated field rules (required, email, maxLength).
  - `src/utils/countries.ts` — ISO country codes; names via `Intl.DisplayNames` in the UI language.
  - In dev, Vite proxies `/api` to `http://localhost:8000` (Host header kept). Who may reach the
    dev server comes from the root `.env` (`vite.config.ts`): `DEV_LISTEN_HOST` (localhost |
    0.0.0.0) and `ALLOWED_HOSTS` (shared with Django; `*` = any). Django always listens on
    127.0.0.1 (`runserver --insecure`, so the admin keeps its CSS with DEBUG=False). Opened to
    other machines for tests → `DEBUG=False` (debug pages show the environment). See README.
    Behind an HTTPS reverse proxy (Nginx Proxy Manager): `CSRF_TRUSTED_ORIGINS` must list the
    browser's address exactly, with the proxy's public port (else every save is a 403 shown as
    "Could not save"); machines sharing the database must share `MEDIA_ROOT` (else photos 404).
    Diagnose with the status codes in `.run/backend.log`.
- Database: PostgreSQL 17 on the homelab (`TrueNAS-1:5432`): `horizon_live` (Live) and
  `horizon_dev` (Development / Test). The test database (`test_horizon_live`) is
  created/dropped by pytest-django.

## Commands
- Dev servers (both, in background): `./dev.sh start|stop|restart|status|logs [backend|frontend]`
  — PIDs/logs in `.run/`. Stop the servers you started before finishing a task.
- Backend: `cd backend && uv run python manage.py runserver` | `uv run pytest` | `uv run ruff check . && uv run ruff format .`
- Migrations: `uv run python manage.py makemigrations && uv run python manage.py migrate`
- Frontend: `cd frontend && npm run dev` | `npm run test:unit -- --run` | `npm run lint` | `npm run type-check`

## Conventions
- **Money and percentages: always `Decimal` / `models.DecimalField`** (NUMERIC in Postgres). Never `float`.
  Precision (`config/decimals.py`): money 2 places, **percentages always calculated with 5**
  (`decimals.percent`); how many are shown is each user's `percent_places`.
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
    fails if a key is missing. Dates: `useDateFormat().d(value, 'short')` (the user's formats); numbers: `$n(value, 'decimal')`.
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
    picks the version (App.vue; light by default). User preference `color_theme` (backend
    `accounts.models.ColorTheme`). Themes, in Settings' order (`COLOR_THEMES`): "Emerald
    Slate" (default; #1C252E, #00926F, #00A883, #CBEEE0, #F9FAFB; emerald over slate, the
    dashboard look's reference palette) uses Public Sans; "German Powerhouse" (second; the
    corporate design guidelines' blues — Dark Blue #1B1E4F frame, Active Blue #2052E4 primary,
    Blue #080593, Soft Blue #B6D3FF, Light Gray #F0F0F0 background, Aubergine #9000C0 accent,
    Sage #528F6C success; CHG Red #FF2063 for the accent, the open page's icon and the Horizon
    icon — never as text; side menu items Light Gray #F0F0F0, the open page's background Soft
    Blue) uses Poppins; "Metallic Foundations" (#3D52A0,
    #7091E6, #8697C4, #ADBBDA, #EDE8F5), "Earthy and Serene" (#3E362E, #865D36, #93785B,
    #AC8968, #A69080) and "Sleek and Futuristic" (#2C3531, #116466, #D9B08C, #FFCB9A, #D1E8E2)
    use the Ubuntu font (fonts: `@fontsource/*`, imported
    in main.ts — bundled and served by Horizon itself, never from a CDN). New theme = entry in `COLOR_THEMES` (with the side menu colors) + choice in
    `ColorTheme`. Use theme colors (`primary`, `sidebar`…), never hard-coded ones.
  - UI: only open-source libraries without license keys (MIT/Apache/BSD). **Vuetify** components
  (auto-imported via `vite-plugin-vuetify`), `mdi-*` icons, themes in `src/themes.ts`.
  **Do not use PrimeVue/PrimeUI** — commercial license since v5.
