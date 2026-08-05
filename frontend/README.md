# Pixous Technologies — Frontend

React + Vite + TypeScript + Tailwind app for Pixous Technologies' internal Estimation & Invoicing tool (client-organized estimations, cost breakdown charts, rate card, invoice generation).

It is a real client for the pipeline in `../api.py` — uploads run the actual LangGraph pipeline (Mistral OCR → Groq → Gemini) and results are live, not mocked.

## Run

**1. Backend** (from the `documentparser/` project root, with `.env` configured):

```bash
venv/Scripts/python.exe -m uvicorn api:app --reload --port 8010
```

**2. Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api/*` to `http://127.0.0.1:8010` (see `vite.config.ts`) — change the port there if your backend runs elsewhere.

## Pages

- **Dashboard** (`/`) — live analysis stepper, estimated summary, cost breakdown donuts, rate card, quick actions
- **New Analysis** (`/new-analysis`) — upload a file, paste a URL, or type requirements to kick off a job
- **My Documents** (`/documents`) — every previously generated BRD/SRS/quotation
- **Rate Card** (`/rate-card`) — edit hourly rates used by the estimation agent
- **Settings** (`/settings`) — API key/service status
- **Document viewer** (`/document/:jobId/:type`, `/document/base/:baseName/:type`) — rendered Markdown with download
