# Test Suite Documentation — Overview

This is the top-level index for the automated test suite. It reflects the
**current** codebase layout (`backend/app/`, `frontend/src/`) — the previous
versions of this document and its two companions described an older,
flat `tests/`/`api.py`/`db.py` layout that no longer exists in this repo and
have been rewritten from scratch as of **2026-08-28**.

- **[UNIT_TESTING.md](UNIT_TESTING.md)** — pure business-logic and
  component-level tests: PDF/invoice math, billing classification, payment
  lifecycle, N+1 regression coverage, and the frontend's Vitest suite.
- **[SECURITY_TESTING.md](SECURITY_TESTING.md)** — authentication,
  authorization, and injection/traversal-focused tests, plus a manual
  security review of this pass's changes and its findings.

## 1. What changed in this pass (2026-08-28)

A full walkthrough of the app surfaced and fixed three real defects, closed
a test-tooling gap, and replaced the stale docs above:

| # | Finding | File(s) | Fix |
|---|---|---|---|
| 1 | **The entire payment API was unreachable in production.** `app/api/payment.py` implements a complete, correctly-locked payment lifecycle (manual entry, initiate/processing/success/failure, correction, overpayment guards) and the frontend (`RecordPaymentModal.tsx`) calls it — but its router was never passed to `app.include_router(...)` in `main.py`. Every `/api/payments/...` call 404'd. | `backend/main.py` | Added `payment` to the router import list and `app.include_router(payment.router, prefix="/api/payments", ...)`. Verified live against a running server (see §3 of `SECURITY_TESTING.md`). |
| 2 | **Payment audit log always attributed actions to `"system"`,** never the authenticated user, because none of `payment.py`'s 6 route handlers passed `user_id=user.id` through to the service layer (every other mutating endpoint in the codebase does). | `backend/app/api/payment.py` | Each handler now passes `user_id=user.id`. Verified both by `test_payment.py` and live, against a real running server. |
| 3 | Frontend had **zero test infrastructure** — no test runner, no config, no `.test.` files anywhere. | `frontend/` | Added Vitest + React Testing Library (devDependencies only; not shipped in `vite build` output) and 3 test files covering the payment client and the recently-fixed `NewInvoiceV2` page. |
| 4 | This document and its two companions described a codebase that no longer exists (`tests/test_security_auth.py`, `api.py`, `db.py`, claimed counts of 132/72/42 passed). | `docs/*.md` | Rewritten against the actual current test files and counts. |

Two pre-existing changes on this branch (not introduced by this pass, but
covered by new regression tests written during it):

- `app/models/audit.py` / `app/models/user.py`: `AuditLog.user_id` FK to
  `users.id` removed, so synthetic actors (`"bootstrap-admin"`, `"system"`)
  can be recorded without a foreign-key violation. Covered by
  `test_audit_log.py`.
- `app/api/projects.py`'s `get_billing_preview`: an N+1 query (two extra
  `SELECT`s per candidate task) replaced with one batched query and an
  in-memory set. Covered by the new `test_billing_preview.py`.

## 2. Framework & conventions

- **Backend:** Pytest, with FastAPI's `TestClient` (Starlette/httpx)
  driving real router instances — never the module under test mocked.
  Each test file builds its own isolated **in-memory SQLite** database
  (`sqlite:///:memory:` via `StaticPool`) and tears it down implicitly at
  process exit; nothing touches `pixous_staging.db` or a real `DATABASE_URL`.
- **Frontend:** Vitest + `@testing-library/react`, jsdom environment
  (`frontend/vite.config.ts`'s `test` block, `frontend/vitest.setup.ts`).
  `fetch` is mocked at the global level in `vitest.setup.ts` **before**
  `api/client.ts` is ever imported — see the comment there; `client.ts`
  captures `window.fetch` into a module-level const at import time, so a
  mock installed later would never be seen.
- **Pattern:** Arrange–Act–Assert; test names state the condition and the
  expected outcome.

## 3. How to run

```bash
# Backend — full suite
cd backend
python -m pytest app/tests -q

# Backend — one file
python -m pytest app/tests/test_payment.py -q

# Backend — one test
python -m pytest app/tests/test_payment.py::TestManualPayment::test_overpayment_is_rejected -q

# Frontend — full suite
cd frontend
npm test

# Frontend build/type-check (not a test, but part of this pass's verification)
npm run build
```

**Current status (last run 2026-08-28):**
- Backend: **85 passed**, 0 failed (`python -m pytest app/tests -q`).
- Frontend: **14 passed**, 0 failed (`npm test`), plus a clean `tsc -b` and
  `vite build`.

No `.env` secrets are required to run either suite — every backend test
builds its own in-memory DB, and `MISTRAL_API_KEY`/`GROQ_API_KEY`/etc. are
never touched (the LLM-driven estimation pipeline under `app/agents/` has
no dedicated test coverage at all — see §5).

`JWT_SECRET` must be set in the environment for the backend suite to import
(`app/config.py` fails closed / raises `RuntimeError` at import time if it
isn't) — a working local `.env` already satisfies this.

## 4. Full backend test inventory

| File | Tests | Primary scope | Documented in |
|---|---|---|---|
| `test_pdf_service.py` | 15 | Invoice PDF generation: amount-in-words, item grouping, HTML-escaping of user content | `UNIT_TESTING.md` |
| `test_auth_security.py` | 12 | HMAC token primitive (`decode_access_token`) in isolation | `SECURITY_TESTING.md` |
| `test_billing_type_service.py` | 9 | Billing-model inference (milestone vs. component vs. custom) | `UNIT_TESTING.md` |
| `test_invoice_dates.py` | 8 | Payment-terms string parsing → due date | `UNIT_TESTING.md` |
| `test_payment.py` | 11 | Payment lifecycle end-to-end (this pass's router-mount fix) | `UNIT_TESTING.md` |
| `test_auth_endpoints.py` | 7 | Role/token enforcement over real invoice routes | `SECURITY_TESTING.md` |
| `test_billing_preview.py` | 7 | Billing-preview N+1 fix regression (this pass) | `UNIT_TESTING.md` |
| `test_path_traversal.py` | 7 | `_safe_output_path` traversal guard | `SECURITY_TESTING.md` |
| `test_login_rate_limit.py` | 5 | Login lockout scoping and reset | `SECURITY_TESTING.md` |
| `test_detached_session_regression.py` | 2 | Lazy-relationship access after session close | `UNIT_TESTING.md` |
| `test_audit_log.py` | 2 | Bootstrap-admin / system actor audit rows (this pass's context) | `UNIT_TESTING.md` |
| **Total** | **85** | | |

## 5. Known gaps / not covered by any test document

- **`app/agents/*.py`** (ingestion, OCR, analysis, estimation, web search,
  BRD/SRS/quotation generation — the actual LLM pipeline) has **no**
  automated test coverage of any kind. It requires live Mistral/Groq/Gemini
  credentials to exercise and was out of scope for this pass; a full
  click-through of the AI estimation intake flow could not be performed in
  this environment (only `MISTRAL_API_KEY` was configured locally, not
  `GROQ_API_KEY`/Gemini).
- **PDF generation is broken in the local Windows dev environment** —
  not a code bug, but worth recording here since it blocked live testing of
  `GET /api/invoices/{id}/pdf`: `app/utils/pdf_builder.py` tries Playwright
  (headless Chromium) first, falling back to WeasyPrint after a 25s
  timeout. In this environment, Playwright's browser binary was never
  downloaded (`playwright install` was never run) **and** WeasyPrint's
  fallback needs the GTK3 runtime, which isn't installed on Windows by
  default — so both backends fail and the request 500s after a ~25s hang.
  See `SECURITY_TESTING.md` §5 for the exact tracebacks captured. Fix:
  run `playwright install chromium` after `pip install -r requirements.txt`
  on any Windows dev machine, or install the
  [GTK3 runtime for Windows](https://weasyprint.readthedocs.io/en/stable/first_steps.html#windows)
  as a fallback path. Neither is needed on the Linux-based deployment
  target if that image's Dockerfile/build step already runs
  `playwright install --with-deps chromium` — verify this is the case
  before relying on it in production.
- **`/{full_path:path}` SPA catch-all masks unmatched API routes as 200
  HTML instead of 404 JSON** (`main.py`) — discovered while walking through
  the API live: hitting a mistyped or wrong-shaped API path (e.g. missing a
  required path segment) returns the frontend's `index.html` with a `200`,
  not a `404`. Not a security issue (no auth bypass — the SPA route itself
  requires no auth, same as any static asset), but a debuggability
  footgun: a frontend bug that constructs a slightly-wrong API URL fails
  as a confusing "Unexpected token '<'" JSON-parse error in the browser
  console instead of a clear 404. Not fixed in this pass (would require
  auditing every legitimate SPA deep-link route to avoid false 404s);
  flagged for awareness.
- Load/performance testing is out of scope for both test documents —
  correctness and security only. The frontend's own production build does
  emit a bundle-size warning (`chunk-KEIR6QF5...js` 662KB,
  `index-Cx4Q8KjH.js` 1.9MB gzip 556KB, driven by `mermaid`/`cytoscape`/
  `katex`) — a real bottleneck for initial page load, not touched by this
  pass's changes and not a regression, but worth a future code-splitting
  pass (dynamic `import()` for the diagram/markdown editor routes).
