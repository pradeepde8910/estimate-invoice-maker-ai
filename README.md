# 📄 Pixous Technologies — Estimation & Invoicing

**Automated document analysis → cost estimation → quotation & invoice generation**

An agentic AI pipeline built with **LangGraph** that reads requirement documents (PDF, DOCX, text, or URL), analyzes them using LLMs, researches current market rates via web search, and generates a structured cost quotation.

## 🏗️ Architecture

```
┌─────────────┐    ┌───────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐
│  Ingestion  │───▸│  OCR      │───▸│  Analysis   │───▸│  Estimation  │───▸│  Web Search  │───▸│  Quotation  │
│  Agent      │    │  Agent    │    │  Agent      │    │  Agent       │    │  Agent       │    │  Agent      │
│             │    │           │    │             │    │              │    │              │    │             │
│ PDF/DOCX/   │    │ Mistral   │    │ Groq LLM   │    │ Groq LLM +  │    │ Gemini +     │    │ Markdown    │
│ Text/URL    │    │ OCR       │    │ Extracts    │    │ Rate Card   │    │ Google Search│    │ + JSON      │
│ detection   │    │ (PDF only)│    │ requirements│    │ calculates  │    │ verifies     │    │ output      │
└─────────────┘    └───────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └─────────────┘
```

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| OCR | Mistral OCR (`mistral-ocr-latest`) | Extract text from PDFs |
| LLM | Groq (`llama-3.3-70b-versatile`) | Analyze requirements, estimate costs |
| Web Search | Gemini (`gemini-2.5-flash`) + Google Search | Current market rates |
| Orchestration | LangGraph | Agentic state graph workflow |
| Data Models | Pydantic | Structured data validation |
| CLI | Rich | Beautiful terminal output |

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### 3. Run the Pipeline
```bash
# With a PDF file
python main.py --file requirements.pdf

# With a DOCX file
python main.py --file project_spec.docx

# With a URL
python main.py --url https://example.com/requirements.pdf

# With text input
python main.py --text "Build an e-commerce platform with user authentication..."

# Interactive mode (paste text directly)
python main.py
```

## 📋 Output

The pipeline generates two files in the `output/` directory:

1. **`<project>_quotation.md`** — Structured quotation with:
   - Executive summary
   - Requirements breakdown by category
   - Team composition
   - Cost breakdown by role and category
   - Infrastructure & third-party costs (from web research)
   - Project timeline and phases
   - Grand total with contingency

2. **`<project>_data.json`** — Complete structured data for programmatic use

## 🗂️ Project Structure

```
documentparser/
├── main.py                        # CLI entry point
├── config.py                      # Configuration & rate card
├── requirements.txt               # Python dependencies
├── .env                           # API keys (not committed)
├── agents/
│   ├── state.py                   # LangGraph shared state
│   ├── graph.py                   # Workflow definition
│   ├── ingestion_agent.py         # Input detection & file handling
│   ├── ocr_agent.py              # Mistral OCR processing
│   ├── analysis_agent.py         # Requirement extraction (Groq)
│   ├── estimation_agent.py       # Cost calculation (Groq + rate card)
│   ├── web_search_agent.py       # Market rate research (Gemini)
│   └── quotation_agent.py        # MD quotation generation
├── models/
│   └── schemas.py                 # Pydantic data models
├── utils/
│   ├── key_manager.py            # API key rotation
│   └── file_handler.py           # File I/O utilities
└── output/                        # Generated quotations
```

## 💰 Developer Rate Card

Predefined in `config.py` (customizable):

| Role | Rate ($/hr) |
|------|-------------|
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

## 🔑 API Key Rotation

The pipeline supports multiple API keys for Groq and Gemini (comma-separated in `.env`). Keys are rotated automatically using round-robin, with automatic failover when a key hits rate limits.

## 🚢 Deployment (for DevOps)

The app talks to the database purely through `DATABASE_URL` (via SQLAlchemy in `db.py`), so moving from local SQLite to a managed database is a config change, not a code change.

**What to hand off:** the codebase only — never the local `pixous.db` file. Production gets its own empty database; the schema is defined in `db.py` and created automatically.

1. **Provision a PostgreSQL database** and set:
   ```
   DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
   ```
   (see `.env.example` for the full list of required env vars — `JWT_SECRET`, `ADMIN_USERNAME`/`ADMIN_PASSWORD`, and the LLM API keys must also be set to real production values, not the repo defaults).
2. `pip install -r requirements.txt` — this includes `psycopg2-binary`, the Postgres driver.
3. Create the schema by either:
   - Starting the API (`uvicorn api:app`) — it calls `init_db()` on startup, which creates any missing tables and is safe to run every deploy, **or**
   - Running `python scripts/init_prod_db.py` explicitly as a pre-deploy step (e.g. a CI/CD migration job). Both are non-destructive and idempotent.
4. **Never run `scripts/reset_db.py` in production** — it's a local dev convenience that drops and recreates all tables, permanently deleting data. It's excluded from the production entry points on purpose.

There's currently no migration framework (e.g. Alembic) — schema changes are additive via `create_all` only. If you expect to evolve the schema after go-live (adding/altering columns on existing tables), add Alembic before the first production deploy so future changes can be applied without a destructive reset.
