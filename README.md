## Price Comparison API – Backend Handover Guide

This document explains the backend architecture, how to run and operate the system, and how the main modules interact. It is designed for a backend developer to fully understand and work on the codebase within a week.

### Tech stack
- **Framework**: FastAPI
- **DB/ORM**: PostgreSQL, SQLAlchemy ORM, Alembic for migrations
- **Admin UI**: SQLAdmin
- **Background jobs**: Celery (Redis broker)
- **HTTP client**: requests

### High-level architecture
- `app/main.py` boots the FastAPI app, configures CORS, mounts routers, exposes health checks, and registers SQLAdmin views bound to the DB engine.
- `app/db/` contains the SQLAlchemy models and session/engine management. All API endpoints and services use sessions from here.
- `app/api/endpoints/` exposes REST endpoints for products, prices, inventory, users, shopping lists, favorites, sale alerts, notifications, search, data collection, and catalog (categories/subcategories).
- `app/services/` contains scraping, data ingestion, scheduler/verification utilities, and other domain services.
- `app/schemas/` defines Pydantic schemas used in request/response contracts.
- `alembic/` manages schema migrations.
- `celery_worker.py` defines Celery app and tasks for asynchronous processing (e.g., notifications).


## Local development setup

### Prerequisites
- Python 3.12
- PostgreSQL (local or remote)
- Redis (for Celery; optional if you don’t run background tasks)

### 1) Create and activate a virtualenv
```bash
python -m venv venv
# Windows
  venv\Scripts\activate
# macOS/Linux
  source venv/bin/activate
  ```

### 2) Install dependencies
```bash
pip install -r requirements.txt
```

### 3) Configure environment
Create a `.env` file in the project root (same folder as `requirements.txt`). At minimum set:
```env
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/shopdb
# Optional/Recommended
# CORS_ALLOWED_ORIGINS=https://your-frontend.example
# SECRET_KEY=replace-with-strong-key
# API_UPLOAD_KEY=replace-with-strong-key
```

Notes:
- The DB engine appends `sslmode=require` automatically if missing (see `app/db/session.py`). For local PostgreSQL, this is fine; for managed Postgres, it enforces TLS.
- There is also a fallback in `app/config.py`, but `app/db/session.py` requires `DATABASE_URL` to be present. Prefer the latter.

### 4) Create schema and run migrations
```bash
alembic upgrade head
```

### 5) Run the API
```bash
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for interactive API docs. Health check is at `/health`.

### 6) Optional: Run background worker
```bash
redis-server # ensure Redis is running
celery -A celery_worker.celery_app worker --loglevel=info
```


## Runtime configuration

- CORS is currently permissive (`*`) in `app/main.py`. For production, set it to your actual frontend origin.
- SQLAdmin is initialized over the same `engine`. To use SQLAdmin UI, mount its routes via `Admin(app, engine)` already in `main.py`.
- JWT secret and API keys in code are placeholders. Replace them via environment variables and inject accordingly.


## Application entrypoint and routing

### `app/main.py`
- Initializes FastAPI and CORS.
- Includes routers for:
  - `products` at `/products`
  - `prices` at `/prices`
  - `inventory` at `/inventory`
  - `users` at `/users`
  - `shopping_lists` at `/shopping-lists`
  - `favorites` at `/favorites`
  - `sale_alerts` at `/sale-alerts`
  - `notifications` at `/notifications`
  - `search` at `/search`
  - `data_collection_router` at `/data-collection`
  - `catalog_router` at `/catalog`
- Registers SQLAdmin `ModelView` classes for all primary models for quick data inspection.
- Exposes `/` root and `/health` (executes `SELECT 1`).


## Database layer

### Engine and sessions
- `app/db/session.py` creates the SQLAlchemy engine from `DATABASE_URL`. It forces `sslmode=require` if not present and provides `SessionLocal` and a `get_db()` dependency for request-scoped sessions.
- `app/db/base.py` also defines a `get_db()` helper bound to the same `SessionLocal`.

### Models
Defined in `app/db/models.py` using SQLAlchemy ORM. Key entities:
- **User** ↔ 1:N `Session`, 1:1 `Preference`, 1:N `SearchHistory`, 1:N `ShoppingList`, 1:N `Favorite`, 1:N `SaleAlert`, 1:N `Notification`.
- **Product**: `api_product_id`, `name`, `brand`, `bar_code`, `image_url`, `subcategory_id`. Relationships to smart matches, inventory, prices, price history, shopping list items, favorites, sale alerts, notifications.
- **Store**: name, location, coordinates, chain, `api_source`, `is_active`. 1:N relationships to inventory, prices, price history, notifications.
- **Inventory**: per store/product quantity, `last_restocked`, `updated_at`.
- **Price**: per store/product current price, sale fields, `updated_at`.
- **PriceHistory**: immutable price events.
- **ShoppingList** and **ShoppingListItem**: user-managed lists and items.
- **Favorite**: user-product favorites with `notify_on_sale` flag.
- **SaleAlert**: user-product sale alert preferences.
- **Notification**: sent messages to users, optionally tied to store.
- **Category** and **Subcategory**: normalized product taxonomy. `Product.subcategory_id` references `Subcategory.id` which references `Category.id`.

Migrations live in `alembic/versions/`. Run `alembic upgrade head` after changes.


## Authentication and security

### JWT auth helpers
`app/utils/auth.py` provides helpers:
- Password hashing via `passlib`.
- `create_access_token` with HS256 and expiration.
- `oauth2_scheme` and `get_current_user` dependency for protected routes.

Important notes:
- Replace hardcoded `SECRET_KEY` with a secure value from env and update imports/usage accordingly.
- `get_current_user` queries `User.id` but model uses `user_id` as primary key. Fix this if you extend auth-protected endpoints.

### API upload key
`app/api/endpoints/data_collection.py` uses a static header key check `X-API-Key`. Replace `API_KEY` with a secure secret, ideally loaded from env.


## Endpoints overview

Only the key implemented endpoints are summarized here. Use `/docs` for full schemas.

### Products – `app/api/endpoints/products.py`
- `POST /products/` create or update a product. Prefers `api_product_id` match; otherwise matches on `(name, brand, bar_code)`. Accepts fields including `subcategory_id` and `image_url`.
- `GET /products/` list products with pagination.
- `GET /products/{product_id}` fetch by ID. Protected by `get_current_user`.
- `DELETE /products/{product_id}` delete by ID. Protected by `get_current_user`.

### Search – `app/api/endpoints/search.py`
- `GET /search/?q=...` case-insensitive search by product name.

### Catalog – `app/api/endpoints/catalog.py`
- Legacy `GET /catalog/` returns a list of products (acts like a pass-through list endpoint).
- `GET /catalog/categories` returns distinct `Product.type` values. Note: current `Product` model does not define `type`. This is legacy; prefer v2 endpoints.
- Category v2:
  - `GET /catalog/categories/v2` list categories
  - `GET /catalog/categories/v2/{id}` get one
  - `POST /catalog/categories/v2` create
  - `PUT /catalog/categories/v2/{id}` update
  - `DELETE /catalog/categories/v2/{id}` delete
- Subcategories:
  - `GET /catalog/subcategories` list all
  - `GET /catalog/subcategories/{id}` get one
  - `GET /catalog/categories/{category_id}/subcategories` list by category
  - `POST /catalog/subcategories` create
  - `PUT /catalog/subcategories/{id}` update
  - `DELETE /catalog/subcategories/{id}` delete

### Data ingestion – `app/api/endpoints/data_collection.py`
- `POST /data-collection/upload` accepts a JSON array of `ProductData` items and ingests via `process_scraped_data`. Requires header `X-API-Key` matching backend’s configured key.


## Services

### Scraper – `app/services/scraper.py`
- Pulls categories and subcategories from Agrohub APIs and paginates through product groups.
- For each product item:
  - Upserts `Product` by `api_product_id` and sets `subcategory_id`.
  - Upserts `Price` for the active `Store` (creates `Store` named "Agrohub" if missing) and sets `price`, `sale_price`, flags, and `updated_at`.
  - Commits in batches after parsing groups.
- Includes defensive logging and type checks since source payloads may vary.

Entry point: `run_scrape()` which orchestrates category → subcategory → paginated products, with simple pacing via `time.sleep` when `hasNextPage` is true.

### Scheduler/verification
- `app/services/updated_scraper_scheduler.py` and `app/services/verify_scraper_with_scheduler.py` run periodic data verification using `schedule` to:
  - Check presence of target store (example: "Spar")
  - Inspect recent products and price updates within a time window
  - Sanity-check categories
- They are designed as standalone scripts. For production, prefer a proper scheduler (e.g., cron, Celery beat, or a platform timer) instead of long-running processes.

### Data collection processor – `app/services/data_collection.py`
`process_scraped_data(data)` performs upserts in a transactional scope:
- Upsert `Product` by `(name, brand, size)`
- Upsert `Store` by `(name, location)`
- Upsert `Inventory` by `(store_id, product_id)` and update `quantity`, `last_restocked`, `updated_at`
- Upsert `Price` by `(store_id, product_id)` and update monetary fields

Notes:
- The current `Product` model does not include `type`, `size`, `upc`, `keywords`. These are referenced here for backward compatibility with older schemas. If you plan to use these fields, add them to the model and create a migration, or adjust the ingestion logic to only use current fields.


## Background processing

- `celery_worker.py` defines a Celery app with Redis broker and a sample `notify_user(email, message)` task. Extend this for real emails/push notifications.
- Run a worker locally with the command shown above. Ensure any producer (API/service) calls `notify_user.delay(...)` rather than the function directly for async execution.


## Admin interface (SQLAdmin)

- Defined in `app/main.py` via `Admin(app, engine)` with multiple `ModelView` classes. This provides an admin UI for CRUD and inspection.
- To secure it, place it behind auth and restrict CORS in production.


## Testing

- Tests are in `tests/`. Run with:
```bash
pytest -q
```
Ensure your test DB and env vars are configured appropriately before running tests.


## Database migrations

- Use Alembic for schema changes:
```bash
alembic revision -m "your message"
alembic upgrade head
```
- Review existing migrations in `alembic/versions/` to understand the evolution of categories/subcategories and uniqueness constraints.


## Deployment notes

- The repository includes `render.yaml` for Render deployment. Ensure `DATABASE_URL` is set in the environment. The engine will enforce `sslmode=require` by default.
- Expose the ASGI app `app.main:app` using a production server (e.g., `uvicorn` with workers or `gunicorn` + `uvicorn.workers.UvicornWorker`).
- Lock down CORS and secrets (`SECRET_KEY`, API keys).


## Operational tips and pitfalls

- **Model vs schema drift**: Some endpoints/services reference fields not present in the current models (`Product.type`, `size`, `upc`, `keywords`). Before using those paths, either add the fields via migration or refactor to use the current taxonomy (`Category`/`Subcategory`).
- **Auth**: `get_current_user` expects `User.id` which does not exist; change to `User.user_id` when enabling protected endpoints.
- **Hardcoded secrets**: Replace the static JWT `SECRET_KEY` and data-collection `API_KEY` with env vars.
- **CORS**: Replace `*` with concrete frontend origins in production.
- **Scraper headers**: The included bearer token and endpoints in `scraper.py` are for development/testing. Replace with a secure mechanism and rotate tokens.
- **Long-running scripts**: The scheduler scripts are basic. For production, use managed cron, Celery beat, or cloud-native schedulers.


## Quick reference

- Start API: `uvicorn app.main:app --reload`
- Run migrations: `alembic upgrade head`
- Run worker: `celery -A celery_worker.celery_app worker --loglevel=info`
- Admin UI: configured via SQLAdmin in `app/main.py`
- Docs: `http://localhost:8000/docs`


## Contact and ownership

All critical modules are documented above. With this guide and `/docs`, a backend developer should be able to extend endpoints, adjust the schema, and operate the scraper and ingestion flows safely.


## Source-of-truth configuration

Create and maintain `.env` from `.env.example`. Variables the app expects:

```ini
# Database
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/shopdb

# Redis / Celery
REDIS_URL=redis://localhost:6379/0

# Auth
SECRET_KEY=replace-with-strong-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Data ingestion
API_UPLOAD_KEY=replace-with-strong-key

# HTTP / CORS
CORS_ALLOWED_ORIGINS=http://localhost:5173

# Environment
ENV=local

# Scraper
UPSTREAM_BASE_URL=https://api.agrohub.ge
UPSTREAM_AUTH_BEARER=replace-with-rotated-token
UPSTREAM_RATE_LIMIT_PER_SEC=5
```

### Config matrix (ownership placeholders)

| Variable | Local | Staging | Prod | Owner |
|---|---|---|---|---|
| DATABASE_URL | local Postgres | managed Postgres (TLS) | managed Postgres (TLS) | Platform |
| REDIS_URL | local Redis | managed Redis | managed Redis | Platform |
| SECRET_KEY | dev-secret | secret manager | secret manager | Security |
| ACCESS_TOKEN_EXPIRE_MINUTES | 30 | 30 | 15 | Backend |
| API_UPLOAD_KEY | dev-key | secret manager | secret manager | Backend |
| CORS_ALLOWED_ORIGINS | http://localhost:5173 | https://staging-frontend | https://prod-frontend | Backend |
| ENV | local | staging | prod | Backend |
| UPSTREAM_AUTH_BEARER | dev token | rotated token | rotated token | Backend |


## Data model and constraints

- Natural/upsert keys:
  - Product: prefer `api_product_id`; fallback historically `(name, brand, bar_code)`
  - Store: `(name, location)`
  - Price: `(store_id, product_id)`
  - Inventory: `(store_id, product_id)`
- Uniqueness/indexes to maintain performance:
  - `prices(store_id, product_id)` composite index
  - `inventory(store_id, product_id)` composite index
  - `products(api_product_id)` unique + index
  - Consider search index for `lower(products.name)` if LIKE queries scale
- Cascade:
  - `Subcategory` backref cascades delete-orphan to `Product` relationship in code; review before enabling destructive deletes in prod.
- Drift to address:
  - Some services reference `Product.type`, `size`, `upc`, `keywords`. Decide: add columns + migrate, or remove legacy references.


## Auth story

- Token creation: HS256 JWT with `exp`, default lifetime `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Client flow: obtain token via login route (to be implemented), then pass `Authorization: Bearer <token>`.
- Protect SQLAdmin and any admin routes behind auth and network rules.
- Fix in code: `User.id` vs `User.user_id` in `get_current_user`.

One-line fix:

```diff
- user = db.query(User).filter(User.id == int(user_id)).first()
+ user = db.query(User).filter(User.user_id == int(user_id)).first()
```

Add a migration if you introduce auth tables/columns.

Example cURL (after you implement token route):

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/products/1
```


## API contracts (top endpoints)

- POST `/products/` upsert example:
```json
{
  "api_product_id": 12345,
  "name": "Milk 2% 1L",
  "brand": "BrandX",
  "bar_code": "0123456789",
  "image_url": "https://.../milk.jpg",
  "subcategory_id": 10
}
```
Conflicts: 409 if you later add uniqueness that this violates.

- GET `/search?q=milk` returns array of products; substring, case-insensitive.

- POST `/data-collection/upload` requires `X-API-Key: $API_UPLOAD_KEY` and body is an array of ProductData. Edge cases: missing prices, out-of-stock quantities, partial records allowed.

Pagination: `skip` and `limit` on list endpoints; defaults in code are `(0, 100)`.


## Scraper and ingestion specifics

- Upstream:
  - Base: `https://api.agrohub.ge` (categories, subcategories, grouped products)
  - Auth: bearer token in headers; rotate regularly and keep out of code.
  - Rate limits: add simple pacing; exponential backoff on 429/5xx recommended.
- Matching rules:
  - Prefer `api_product_id`. If absent, fallback is fragile—avoid unless necessary.
- Reconciliation:
  - On price change, consider writing `PriceHistory` records at each update tick (extend `parse_and_save_products`).
- Sample payload for ingestion (use with `/data-collection/upload`):
```json
[
  {
    "name": "Milk 2% 1L",
    "brand": "BrandX",
    "size": "1L",
    "price": 3.49,
    "store_name": "Agrohub",
    "store_location": "Store #1",
    "quantity": 12
  }
]
```


## Background jobs and scheduling

- Celery: use `REDIS_URL` for broker; set concurrency and acks/retry policy in Celery config when you extend beyond demo.
- Scheduling: replace ad-hoc `schedule` loops with cron or Celery beat. Example cadence: scrape nightly, verify hourly.


## Observability and operations

- Logging: standardize JSON logs in production; include request IDs; redact secrets.
- Health checks: `/health` validates DB connectivity; add Redis ping when using Celery.
- Metrics to track: items ingested, scrape duration, task failures, API latency, DB errors.
- Errors: 400 for validation, 404 for not found, 409 for conflicts, 500 for unexpected.
- Backups: set Postgres automated backups; document restore and migration rollback steps.


## Testing and data seeding

- Use a throwaway DB for tests (override `DATABASE_URL`).
- Seed minimal fixtures: 1 store, a few products, prices, and inventory to exercise search and listing.
- Add contract tests around ingestion upserts and idempotency.


## Security hardening checklist

- Exact CORS origins in production.
- Secrets only from environment/secret manager; remove hardcoded keys/tokens from repo.
- Put SQLAdmin behind auth and IP allowlists.
- Add basic rate limiting for public endpoints.


## Developer ergonomics

- Makefile tasks (see `Makefile`):
  - `make dev` run API
  - `make migrate` upgrade head
  - `make worker` start Celery
  - `make test` run tests
  - `make fmt` format code
- Docker Compose (see `docker-compose.yml`) boots Postgres, Redis, API, Worker for day-1 onboarding.


Userflow: https://mermaid.live/edit#pako:eNp1Vd1O4zgUfhUro11ugG2SFkq1mlVoKTBToG0KA2PmwiQnqUUadx2nTIci7bPso-2T7LGdlFaiubBy7M_nfOfXr04kYnA6TpKJl2jKpCKT3mNO8AvobQGS3PGCq4KEXMEPcnDwmZy-9rksEMdnQDTkrzd74VQfrx6gWJEuDUolDroSmAISRJEoc_VjE3YtVqRHB4LF5OwnLxTPUzKUIuEZVDi7do3NMzqGv0tAqwMRMcVFToYgZ7wo8LfC9wyyb3Ua6kMJCUjIIygqzJnFbBrom61z62wITEZTKDSVuIzUn0_yj89wmB6SPSFTlvOIzHj2TNzB3hbLc6PkgobLQsFM30abBeqxCivshUFd0iGTBdQmSA8U41lhTP33z78Y6V-wFibL-btwKlkeb9m9NBq_0B5T7Imh0oEQz-W8wnwxp19pn-cxuWIqmlZR1nbrkHw1oAHtTiF6JqESEshlvoAc_5YVZmAwV_QcFOmWEkOqUA1HH8nvJGTZOr5XBnhNuyyLykzn3irsYYbZRh7sem3QNxRP5xlbkjEUZbYmdmNOh68mMUGkk15Xml2HppCCOCZKkAFaWJERDadiPtdu6o2C9LEAS1mXlL0RohdBBhLxY2rcsOIONFsA6bOFkNgBKxLS-v9j-DW8VElfkfNNtiPjzsilRiEyvkJf-TwDy7RSMnItzNsI4UQolpGu0P7MdZHqkNZ4z-J9zE0OUsPHotRxL9MU-wWDtlbt23BvkhqbrTGSwphMmEyhSmx1Z2zpjD16JXKOdu0p6U5Znq6zObYkxj6qwUq7Foon3LZpQV6mkFe3elLM13c-YBOardClp1jFMyafySV2U3UhtFRCj57l7AnDNio5FmzNB4u3Vh1aOqFvvNLluU2phn3AYGI6CWOdZWAqjtiOtpPvlt7O4_eirjpgwRkJhpe12omB3tGJZGt6F5jh926yiG_0DiRPdNWz7EDpYRoscBCwJ55xtdxqlFvb5la42xS-bQp2vafhTM_xdcOf5SnPq-H9QG_zGKTuxhgnDQ4zJtcTwQyaPe83M-P2yKIge_gqHCRM2Z2K073R9J1eoI5M93ZipixWDnrMUjATrNgCBwEO8EikOZ7YMUbumORb-bDrg51ZVvi-KQTBpmTXQi2RQUDw2cg6n8BNWgnsRyITsvOpYb5N3E2Fi9pwFJ3sxk0qXJIkPjR24-5rnA-tpLUbN6r5tZMWtPfJTuD43XAb3N0KwxoXQROibZyz76SSx05HyRL2nRk-k0yLzqvW8OioKczg0engb4wt9ug85m94Z87y70LM6mtSlOnU6SQsK1AqTdn3OEslm613MedYSl39tDsd12_7vlHjdF6dn07Hd48PvWbzqOk3Gp7v-kf7ztLpeLh51Dj2XNfFTc9rve07v4zdxuGJ77caXtM_Pm66J-3j9tv_kyCgqw


Description( in Georgian): https://docs.google.com/document/d/1t2MHQPHhnr_qEiJuViu88WJcxQU1Og-tqZGjTWz336U/edit?usp=sharing