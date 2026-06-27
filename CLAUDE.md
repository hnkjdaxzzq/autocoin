# CLAUDE.md

## Project Overview

Autocoin (autocoin-t) is a personal finance/accounting web application — a **monolithic SPA + REST API** built with FastAPI (Python) and vanilla JavaScript frontend.

- **Backend:** Python 3.9+, FastAPI, SQLAlchemy 2.0 ORM, SQLite (WAL mode)
- **Frontend:** Vanilla JS SPA (no framework), Chart.js for charts, CSS custom properties for dark mode
- **Deployment:** Docker + docker-compose, single process serving both API and static files on port 8000

## Project Structure

```
autocoin-t/
├── main.py                          # Entry point: uvicorn startup
├── autocoin/                        # Python backend package (~2000 lines)
│   ├── app.py                       # FastAPI app factory (middleware, exception handlers, routers, static files)
│   ├── config.py                    # Pydantic Settings with AUTOCOIN_ env prefix
│   ├── auth.py                      # JWT auth (python-jose) + bcrypt password hashing
│   ├── database.py                  # SQLAlchemy engine, session factory, init_db (WAL mode + FK enforcement)
│   ├── models/                      # 4 ORM models: User, Transaction, ClassificationRule, ImportBatch
│   ├── repository/                  # Repository pattern: DataRepository ABC → SQLiteRepository
│   ├── routers/                     # 5 route modules under /api/v1 (auth, transactions, imports, rules, statistics)
│   ├── schemas/                     # Pydantic request/response models
│   ├── parsers/                     # Bill parser strategy pattern (Alipay CSV GBK, WeChat XLSX)
│   └── services/                    # ImportService, ImageRecognizer (multi-LLM fallback), StatsService
├── frontend/                        # Vanilla JS SPA (~2700 lines JS + ~1800 lines CSS)
│   ├── index.html                   # SPA shell with sidebar, topbar, bottom tab bar (mobile)
│   ├── css/styles.css               # Dark mode, responsive layouts, animations
│   └── js/
│       ├── api.js                   # API client with JWT token management
│       ├── app.js                   # Hash router, auth guard, dark mode toggle
│       ├── auth.js                  # Login/Register pages
│       ├── dashboard.js             # Summary cards, monthly chart, category donut
│       ├── transactions.js          # Full CRUD, filters, inline edit, batch ops, export
│       ├── import.js                # File import (drag-drop preview), image import (LLM recognition)
│       ├── rules.js                 # Classification rules CRUD, reclassify with diff dialog
│       ├── charts.js                # Chart.js wrapper (bar, line, donut)
│       └── stats.js                 # Year/month/category/daily statistics with drill-down
├── tests/                           # pytest + httpx + FastAPI TestClient (~33 test cases)
│   ├── conftest.py                  # Test DB setup/teardown
│   ├── test_parsers.py              # 9 parser tests
│   ├── test_image_recognizer.py     # 10 recognizer tests
│   └── test_api.py                  # 14+ API integration tests
├── Dockerfile                        # multi-stage build (python:3.12-slim + uv)
├── docker-compose.yml               # single service, persistent volume, port 8000
├── pyproject.toml                   # Python project config (uv package manager)
└── uv.lock                          # Dependency lock file
```

## Architecture Patterns

| Pattern | Location | Description |
|---------|----------|-------------|
| **Repository** | `autocoin/repository/` | `DataRepository` ABC with `SQLiteRepository` impl; all queries scoped by `user_id` |
| **Parser Strategy** | `autocoin/parsers/` | `BillParser` ABC, `can_parse()` auto-detection for Alipay/WeChat |
| **LLM Fallback Chain** | `autocoin/services/image_recognizer.py` | Tries providers in priority order: Zhipu → Qwen → DeepSeek → OpenAI → Gemini |
| **Classification Engine** | `autocoin/repository/sqlite.py` | Regex-based matching with priority ordering, auto-applied on transaction create |
| **App Factory** | `autocoin/app.py` | `create_app()` assembles middleware, exception handlers, routers, static mount |
| **Soft Delete** | `autocoin/models/transaction.py` | `is_deleted` flag, never hard delete |
| **Multi-User Isolation** | All repository methods | Data scoped by `user_id` from JWT, bcrypt password hashing |
| **Hash Router SPA** | `frontend/js/app.js` | Client-side routing with auth guard, no framework dependency |

## Database Models (SQLite, 4 tables)

- **users** — id, username (unique), password_hash, created_at
- **transactions** — id, user_id (FK), source, source_order_id, transaction_time, transaction_type, category, counterparty, counterparty_account, product, direction (income/expense/neutral), amount, payment_method, status, remark, import_batch_id (FK), is_deleted (soft delete), timestamps. Unique constraint: (user_id, source, source_order_id)
- **classification_rules** — id, user_id (FK), name, priority, is_active, match_counterparty (regex), match_product (regex), match_payment_method (regex), match_transaction_type (regex), category, remark, timestamps
- **import_batches** — id (UUID PK), user_id (FK), filename, source, imported_at, total_rows, imported_rows, duplicate_rows, error_rows, status

## API Routes (all under `/api/v1`, JWT Bearer auth)

| Module | Key Endpoints | Description |
|--------|--------------|-------------|
| `/auth` | `POST /register`, `/login`, `GET /me` | Registration (auto-login), login, current user |
| `/transactions` | `GET/POST /`, `PUT/DELETE /{id}`, `POST /batch/delete`, `POST /batch/update`, `GET /export/csv`, `GET /export/excel`, `GET /categories` | Full CRUD, batch ops, export with filters, sort, pagination, search |
| `/imports` | `POST /`, `/preview`, `/confirm`, `/image/recognize`, `/image/check-duplicates`, `/image/confirm`, `/image/quota` | File import pipeline (preview→confirm), image recognition with LLM fallback |
| `/rules` | `GET/POST /`, `PUT/DELETE /{id}`, `POST /reclassify` | Classification rules CRUD, reclassify all transactions with diff |
| `/statistics` | `GET /summary`, `/monthly`, `/category`, `/daily` | Summary, monthly trends, category breakdown, daily stats |

## Key Implementation Details

### Image Recognition Pipeline
Upload images → try LLM providers in order (Zhipu GLM-4V → Qwen VL → DeepSeek VL2 → OpenAI GPT-4o → Gemini) → parse JSON response → check duplicates (time+amount+counterparty) → user preview → confirm insert. Daily limit default: 10.

### Classification Rules
Regex patterns matched against transaction fields (counterparty, product, payment_method, transaction_type). Higher priority rules applied first. Applied automatically on transaction creation, manual creation, and file import. `/reclassify` re-applies all rules to existing transactions and returns a diff.

### File Import Pipeline
Upload bill file → auto-detect parser (Alipay CSV / WeChat XLSX) → preview (show duplicates, anomalies, summary per file in a card UI) → user confirms per file → bulk insert with dedup.

### Frontend Architecture
- Hash-based routing: `#/login`, `#/dashboard`, `#/transactions`, `#/import`, `#/rules`, `#/stats`
- JWT stored in localStorage, attached to all API requests
- Dark mode via `data-theme="dark"` with system preference detection
- Mobile responsive: bottom tab bar on small screens, sidebar on desktop
- Cache busting with `?v=N` query param on script/style tags
- No build tooling — all vanilla JS with Chart.js loaded from CDN

## Running the Project

```bash
# Local development
uvicorn main:app --reload

# Docker deployment
docker-compose up -d

# Run tests
pytest tests/ -v
```

## Configuration

All config via environment variables with `AUTOCOIN_` prefix:
- `AUTOCOIN_DATABASE_URL` — SQLite path (default: `sqlite:///./autocoin.db`)
- `AUTOCOIN_JWT_SECRET` — JWT signing key
- `AUTOCOIN_CORS_ORIGINS` — comma-separated allowed origins
- `AUTOCOIN_LLM_PROVIDER_ORDER` — comma-separated provider priority list
- Provider-specific keys: `AUTOCOIN_OPENAI_API_KEY`, `AUTOCOIN_GEMINI_API_KEY`, etc.
- `AUTOCOIN_IMAGE_IMPORT_DAILY_LIMIT` — daily image recognition cap (default: 10)
