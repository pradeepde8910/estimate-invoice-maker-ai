# Test Suite Documentation — Overview

This is the top-level index for the automated test suite under `tests/`.
It covers the **end-to-end/feature tests** directly and links out to the
two dedicated documents for the other test categories:

- **[UNIT_TESTING.md](UNIT_TESTING.md)** — pure/deterministic module-level tests (`test_unit_*.py`).
- **[SECURITY_TESTING.md](SECURITY_TESTING.md)** — authentication, authorization, injection, and file/network-boundary tests (`test_security_*.py`), plus the findings this project's audits fixed and why.

## 1. Framework & conventions

- **Framework:** Pytest, with FastAPI's `TestClient` (Starlette/httpx) driving the real ASGI app end-to-end.
- **Pattern:** Arrange–Act–Assert. Test names state the condition and the expected behavior (`test_<subject>_<condition>_<expected_outcome>`).
- **Isolation:** `tests/conftest.py` points `DATABASE_URL` at a throwaway temp SQLite file *before* any project module is imported, and the `fresh_database` fixture drops/recreates every table before each test. No test touches `pixous.db` / production data.
- **Mocking policy:** Only external network calls (LLM providers via the LangGraph pipeline, `requests.get` in `download_url`) and non-deterministic time (`time.time()` in the rate limiter) are mocked. Everything else — the FastAPI app, the real SQLite DB, Pydantic validators, `bcrypt`, `invoice_builder`, `pdf_builder`, `organization.py` — runs for real. The system under test is never mocked.

## 2. How to run

```bash
# Full suite (unit + security + E2E + feature)
python -m pytest tests/ -q

# Just this document's scope (E2E + feature)
python -m pytest tests/test_e2e_*.py tests/test_features.py -q

# One file
python -m pytest tests/test_e2e_job_pipeline.py -q

# With coverage
python -m pytest tests/ --cov=. --cov-report=term-missing
```

Current status (full suite): **132 passed**, 0 failed (last run: 2026-08-13).
Breakdown: 42 unit (`UNIT_TESTING.md`) + 72 security (`SECURITY_TESTING.md`) + 18 E2E/feature (this document).

No `.env` secrets or API keys are required to run the suite — the pipeline's
LLM calls are mocked in the E2E job test, and `conftest.py` isolates the DB.
`JWT_SECRET` must still be set in the environment (loaded via `config.py`);
if you have a working local `.env` this is already satisfied.

## 3. E2E and feature test coverage (this document's scope)

### `tests/test_e2e_job_pipeline.py`

Full AI-pipeline job lifecycle over HTTP. `agents.graph.build_pipeline()`
drives real calls to Mistral/Groq/Gemini — the one thing this file mocks
(see §5) — everything downstream of it runs for real.

| Test | Scenario |
|---|---|
| `test_full_job_lifecycle_from_text_submission_to_document_retrieval` | Create job (text input) → blocking `/wait` → poll `/api/jobs/{id}` → fetch quotation/BRD documents → unknown doc type → shows up correctly in `/api/documents`, `/api/documents/{base_name}/data`, and `/api/clients`, all backed by real DB rows `_run_job` wrote |
| `test_job_with_no_input_is_rejected_before_starting_a_pipeline_run` | `POST /api/jobs` with no file/url/text → `400`, no pipeline ever starts |
| `test_failed_pipeline_run_surfaces_error_and_never_appears_complete` | A pipeline stage that reports `..._failed` surfaces the real error message; the job never appears `complete`; its documents 404 |
| `test_fetching_document_for_incomplete_job_returns_404` | A job still `running` → document fetch is `404`, not a stale/partial result |
| `test_get_job_for_unknown_id_returns_404` | Unknown job id → `404` |
| `test_job_endpoints_require_authentication` | No auth header on job creation or polling → `401` |

### `tests/test_e2e_estimation_invoice_lifecycle.py`

Manual (non-AI) estimation path, run against the real SQLite test DB, real
`invoice_builder`/`pdf_builder` — nothing mocked (no network call exists
in this path).

| Test | Scenario |
|---|---|
| `test_full_manual_estimation_to_paid_invoice_lifecycle` | Create manual estimation → fetch data → generate invoice → fetch invoice → mark Paid (Finance role) → download invoice PDF (`%PDF` magic bytes) → shows up in `/api/documents` → aggregated correctly in `/api/analytics` |
| `test_patch_estimation_applies_optimistic_lock_and_writes_audit_log` | A correct `version` patch succeeds, bumps `version`, and writes an `AuditLog` row; a stale `version` patch afterward → `409` |
| `test_delete_estimation_soft_deletes_and_hides_from_listing` | Delete → `is_deleted`/`deleted_at` set, row hidden from `/api/documents`; deleting again → `404` |
| `test_generating_invoice_for_unknown_estimation_returns_404` | Unknown `base_name` → `404` |
| `test_invoice_status_rejects_value_outside_allowed_set` | A status string outside the fixed `INVOICE_STATUSES` set → `400` |

### `tests/test_features.py` *(pre-existing)*

| Test | Scenario |
|---|---|
| `test_delete_branding_asset_clears_path` | Deleting a branding asset clears its DB path reference and removes the file |
| `test_delete_branding_asset_requires_admin` | Non-Admin role → `403` |
| `test_delete_branding_asset_rejects_unknown_slot` | An unrecognized slot name → `400` |
| `test_cancel_job_marks_status_cancelled` | Cancelling a running job flips its status and is reflected on the next poll |
| `test_cancel_job_rejects_already_finished_job` | Cancelling a `complete` job → `400` |
| `test_cancel_job_requires_auth` | No auth header → `401` |
| `test_get_job_returns_created_at` | Job responses include `created_at` |

## 4. Notable design decisions

- **Mocking the LangGraph pipeline, not the app.** `test_e2e_job_pipeline.py` monkeypatches `api.build_pipeline` to return a fake compiled-graph stand-in whose `astream()` yields the same incremental-state-dict shape the real graph emits (`current_stage` progressing through the same values `STEP_INDEX` expects). Every other layer — job bookkeeping, `_summarize`, letterhead application, DB persistence, document/analytics endpoints — runs unmocked against the real pipeline-completion code path in `api._run_job`.
- **Async background jobs are exercised for real, not stubbed.** `POST /api/jobs` calls `asyncio.create_task(_run_job(...))`; the E2E test relies on `TestClient`'s persistent background event-loop thread (the same one production `uvicorn`/`asyncio.create_task` semantics assume) rather than injecting into `api.JOBS` directly, so the polling/`wait` endpoints are tested against genuine concurrent execution.
- **Global mutable state is snapshotted and restored where any test touches it** (e.g. `config.DEVELOPER_RATES` in the rate-card tests — see `SECURITY_TESTING.md` §4.4) so no test's side effects leak into another's expectations.

## 5. QA Postman collection (manual/exploratory testing)

`postman/Pixous_QA_Collection.postman_collection.json` and its companion
`postman/Pixous_QA.postman_environment.json` are a separate artifact from
the automated pytest suite above — a real Postman v2.1 collection (not the
OpenAPI export in `pixous_api_postman.json`) for manual/exploratory QA
against a running server, using only synthetic/fictional data (no real
client names, financial details, or personal information anywhere in it).

**Setup:** import both files into Postman, select the environment, fill in
`admin_password` (and `qa_api_key` if you've set `QA_TEST_API_KEY`), then
run **Auth → Login (Admin)** first — it captures the JWT into `jwt_token`,
which every other request (except the QA API Key folder) sends
automatically via Bearer auth. **Estimations (Manual) → Create Manual
Estimation** and **Jobs (AI Pipeline) → Create Job (Text)** each capture an
ID (`base_name` / `job_id`) that later requests in their folder depend on.

**Folders:** Auth · QA API Key (alternate auth) · Estimations (Manual) ·
Invoices · Jobs (AI Pipeline) · Organization & Rate Card · Documents &
Analytics.

Unlike the automated E2E test (`test_e2e_job_pipeline.py`), the **Jobs (AI
Pipeline)** folder is *not* mocked — it calls whatever Mistral/Groq/Gemini
credentials are configured in the server's `.env` and can take 1–3 minutes
per job. Everything else runs against real endpoints with no network
dependency beyond the running Pixous server itself.

## 6. Known gaps / not covered by any of the three test documents

- `agents/*.py` (ingestion, OCR, analysis, estimation, web search, BRD, SRS, quotation node logic) are exercised only indirectly through the mocked-pipeline E2E test — their internal LLM-prompt/parsing logic has no dedicated unit tests.
- `pdf_builder.py`'s Markdown→PDF rendering (WeasyPrint) is exercised transitively via the invoice-PDF E2E assertion (`content[:4] == b"%PDF"`) but has no dedicated unit tests for its Markdown-to-CSS mapping.
- Load/performance testing (the app itself already ships a `/wait` endpoint aimed at JMeter-style blocking polls) is out of scope for all three documents — this suite is functional/security correctness only.
- See `SECURITY_TESTING.md` §6 for security-specific known gaps (no account-disable flag, no server-side token revocation, per-process rate limiting).
