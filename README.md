# Pixous Technologies — Estimation & Invoicing Platform

An AI-assisted platform that takes a client requirements document and carries it all the way through to a billable client: automated document parsing, LLM-driven cost estimation, quotation generation, and full project/invoice/payment tracking — behind a FastAPI backend and a React dashboard.

## Overview

A LangGraph-orchestrated agent pipeline reads a requirements document (PDF, DOCX, plain text, or URL), extracts structured requirements with an LLM, estimates cost against a configurable rate card, verifies current market pricing via web search, and produces a validated quotation. From there, the platform tracks the resulting project, its milestones and commercial components, and generates GST-compliant invoices and payments against it — all backed by a Postgres (or local SQLite) database and exposed through a REST API with a dedicated frontend.

## Architecture

**Document → estimation pipeline** (`backend/app/agents/`, LangGraph state machine):

```
Ingestion → OCR → Analysis → BRD/SRS → Estimation → Web Search → Validator → Quotation
  Agent      Agent    Agent      Agent       Agent        Agent       Agent       Agent

PDF/DOCX/   Mistral   Groq LLM   Groq LLM   Groq LLM +   Gemini +   Deterministic  Markdown
Text/URL    OCR       extracts   drafts     rate card    Google     15-check       + JSON
detection  (PDF only) reqs       docs       computes     Search     health audit   output
                                             cost                    (see below)
```

**Application layer** (`backend/app/`, FastAPI + SQLAlchemy):

```
┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Estimation  │────▸│     Projects      │────▸│     Invoicing     │────▸│   Payments   │
│  (from the   │     │  milestones,      │     │  GST-compliant,   │     │  & reports   │
│  pipeline    │     │  commercial       │     │  PDF/Excel/CSV    │     │              │
│  above)      │     │  components       │     │  export           │     │              │
└──────────────┘     └───────────────────┘     └──────────────────┘     └──────────────┘
        ▲                                                                        │
        │            Master data: clients · billing classifications (HSN/SAC)   │
        │            · resource & capability catalog · rate cards · org         │
        └────────────────────────── branding/settings ─────────────────────────-┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI + Uvicorn/Gunicorn |
| Database | PostgreSQL (production) / SQLite (local dev) via SQLAlchemy + Alembic |
| AI orchestration | LangGraph + LangChain |
| OCR | Mistral OCR (`mistral-ocr-latest`) |
| Analysis / estimation LLM | Groq (`llama-3.3-70b-versatile`), key-rotated |
| Market research | Gemini (`gemini-2.5-flash`) + Google Search, key-rotated |
| Document generation | WeasyPrint (PDF), openpyxl (Excel), Playwright, markdown |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Frontend data viz | Recharts, Mermaid, `react-markdown` |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- A PostgreSQL database (optional for local dev — SQLite works out of the box)

### 1. Configure environment
```bash
cp .env.example .env
```
Fill in `MISTRAL_API_KEY`, `GROQ_API_KEYS`, `GEMINI_API_KEYS`, `JWT_SECRET`, and admin credentials. Leave `DATABASE_URL` as the SQLite default for local dev, or point it at Postgres — see [Database](#database) below.

### 2. Run the backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```
The API starts on `http://localhost:8000` and creates/migrates its schema automatically on boot.

### 3. Run the frontend
```bash
cd frontend
npm install
npm run dev
```
The dashboard starts on Vite's default dev port and talks to the backend API.

## Core Features

- **Document-to-quotation pipeline** — upload a requirements document or paste text/a URL; get back a structured, itemized quotation with team composition, cost breakdown, timeline, and researched infrastructure/licensing costs.
- **Automated quotation health checks** — before a quotation is generated, 15 deterministic checks verify requirement coverage, cost arithmetic (unit/category/grand-total reconciliation), team billing consistency, and cross-unit scope overlap (with an entity/phase-aware filter so parallel rollouts across regions or phases aren't flagged as accidental duplicates).
- **Project & milestone tracking** — projects, milestones, and commercial components derived from an accepted estimation.
- **Invoicing** — GST-compliant invoices (tax, TDS, HSN/SAC classification) generated from project milestones or as standalone invoices, exportable to PDF, Excel, and CSV.
- **Payments & reporting** — payment recording against invoices and configurable reports.
- **Master data management** — clients, billing classifications, a resource & capability catalog, rate cards, and organization branding/settings, all editable from the admin UI.
- **Auth** — JWT-based auth with role checks; a QA-only static API key mode for automated testing (never enabled in production).

## API Surface

All routes are served from `backend/main.py`. Prefixed (`/api/...`) routers are the current V2 surface; unprefixed routers are the original document-pipeline endpoints, retained as-is:

| Prefix | Router | Purpose |
|---|---|---|
| `/api/auth` | `auth` | Login, JWT issuance |
| `/api/reports` | `reports` | Payment/financial reports |
| `/api/alerts` | `alerts` | System alerts |
| `/api/master` | `master` | Clients & general master data |
| `/api/master/billing-classifications` | `billing_classification` | HSN/SAC catalog |
| `/api/master/resource-catalog` | `resource_catalog` | Resource & capability catalog |
| `/api/quotations` | `quotations` | Quotation retrieval |
| `/api/invoices` | `invoices` | Invoice CRUD, generation, export |
| `/api/projects` | `projects`, `project_summary` | Project tracking & summaries |
| — | `jobs`, `estimations`, `documents`, `organization`, `rate_cards`, `system`, `clients` | Document pipeline, estimation history, org settings, rate cards |

## Project Structure

```
documentparser/
├── .env.example                   # Documented environment variables
├── docs/                          # Requirements, testing & security test docs
├── backend/
│   ├── main.py                    # FastAPI entry point (uvicorn main:app)
│   ├── requirements.txt
│   ├── alembic/                   # DB migrations (targets DATABASE_URL)
│   ├── conftest.py, tests/        # Pytest suite
│   └── app/
│       ├── agents/                # LangGraph document → quotation pipeline
│       ├── api/                   # FastAPI routers
│       ├── models/                # SQLAlchemy models
│       ├── services/               # Business logic (invoicing, billing, tax, exports…)
│       ├── exporters/             # PDF/Excel/CSV generation
│       ├── core/                  # DB session, security, key rotation, rate limiting
│       └── config.py              # Environment & rate card configuration
└── frontend/
    ├── package.json               # npm run dev / build / preview
    └── src/
        ├── pages/                 # Dashboards: Projects, Estimations, Invoices,
        │                          #  Rate Card, Organization Settings, Export Center,
        │                          #  admin/BillingClassifications, admin/ResourceCatalog
        ├── components/
        └── api/client.ts          # Backend API client
```

## Database

The app resolves its database purely from `DATABASE_URL` (`app/config.py`, `app/database.py`, and `app/core/database.py` all agree on the same resolution order), so moving between SQLite and Postgres is a config change, not a code change.

- **Local dev:** leave `DATABASE_URL` unset or `sqlite:///pixous.db` — no setup required.
- **Production:** provision PostgreSQL and set
  ```
  DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
  ```
- Schema is created automatically on boot via `init_db()`, and is also tracked by Alembic (`backend/alembic/`, `script_location = alembic`) — `alembic upgrade head` / `alembic stamp head` operate against whatever `DATABASE_URL` currently points to.
- Never commit real database credentials — `.env` is gitignored; rotate any credential that's ever been pasted somewhere unencrypted.

## Developer Rate Card

Default hourly rates live in `backend/app/config.py` and are also editable per-organization from the Rate Card admin page.

| Role | Rate ($/hr) |
|---|---|
| Junior Developer | $25 |
| Mid-Level Developer | $45 |
| Senior Developer | $75 |
| Tech Lead / Architect | $95 |
| UI/UX Designer | $55 |
| QA Engineer | $40 |
| DevOps Engineer | $65 |
| Project Manager | $60 |
| Business Analyst | $50 |
| Data Engineer | $70 |
| ML Engineer | $85 |
| Security Specialist | $80 |

## API Key Rotation

`GROQ_API_KEYS` and `GEMINI_API_KEYS` accept comma-separated keys. The key manager (`app/core/key_manager.py`) rotates them round-robin with automatic failover when a key hits its rate limit.

## Testing

```bash
cd backend
python -m pytest
```

## Deployment Notes

1. Provision PostgreSQL and set `DATABASE_URL`, along with real (non-default) values for `JWT_SECRET`, `ADMIN_USERNAME`/`ADMIN_PASSWORD`, and the LLM API keys — see `.env.example` for the full list.
2. `pip install -r backend/requirements.txt` — includes `psycopg2-binary` (Postgres driver) and `gunicorn`.
3. Starting the API (`uvicorn main:app` / a Gunicorn worker) calls `init_db()` on startup, which creates any missing tables and is safe to run on every deploy.
4. Build the frontend for production with `npm run build` (in `frontend/`) and serve the resulting static assets from your web server or CDN of choice.
5. Leave `QA_TEST_API_KEY` unset in production — it exists purely for automated staging/QA authentication.
