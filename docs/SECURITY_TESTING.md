# Security Test Documentation

Scope: `backend/app/tests/test_auth_security.py`, `test_auth_endpoints.py`,
`test_login_rate_limit.py`, `test_path_traversal.py` — plus a manual
security review of this pass's changes (§3) and a live walkthrough against
a running server (§3.3). For pure business-logic/unit tests, see
[UNIT_TESTING.md](UNIT_TESTING.md). For the full inventory, see
[TESTING.md](TESTING.md).

## 1. Framework & conventions

- **Framework:** Pytest, with FastAPI's `TestClient` (Starlette/httpx)
  driving real router instances. Each auth test builds its own token using
  the exact same HMAC construction the app uses
  (`app.core.security.create_access_token`'s scheme —
  `base64url(json payload) + "." + hex(HMAC-SHA256(payload_b64, secret))`),
  so a test failure means the real signing/verification code has a gap,
  not that a test's forgery routine drifted from production behavior.
- **Isolation:** every test here uses an in-memory SQLite DB seeded fresh
  per test/module — never `pixous_staging.db`, never a real `DATABASE_URL`.
- **Two coexisting DB modules:** `app.database.get_db` (used by
  `app/api/payment.py`, `app/api/projects.py`, `app/api/invoices.py`) and
  `app.core.database.get_db` (used by `app/api/dependencies.py`'s auth
  chain, and by `estimations.py`/`documents.py`/`clients.py`). Both point
  at the same physical `DATABASE_URL` outside tests, but are different
  Python function objects — a test that mounts a router without
  overriding **both** dependency functions has its auth check silently
  fall through to whatever DB is actually configured. `test_auth_endpoints.py`
  documents this explicitly (see its `client` fixture).
- **Mocking policy:** nothing in the auth path is mocked — real HMAC
  signing/verification, real bcrypt, real role checks, real DB queries.

## 2. How to run

```bash
cd backend
python -m pytest app/tests/test_auth_security.py app/tests/test_auth_endpoints.py \
  app/tests/test_login_rate_limit.py app/tests/test_path_traversal.py -v
```

Current status: **31 passed**, 0 failed.

---

## 3. This pass's findings

### 3.1 The entire payment API was unreachable — **FIXED · was HIGH (availability/integrity of a core financial feature)**

**Root cause.** `app/api/payment.py` is a fully-implemented payment
lifecycle — manual payment entry, an initiate/processing/success/failure
gateway flow, and admin correction — with row-level locking
(`with_for_update()`), an atomic per-financial-year voucher number
generator, and overpayment guards on every mutating path. The frontend
(`frontend/src/components/RecordPaymentModal.tsx`) calls it via
`recordManualPayment`/`recordPayment`/`listInvoicePayments`
(`frontend/src/api/client.ts`). **None of it was reachable**: `payment` was
never imported into `backend/main.py`'s `from app.api import (...)` block,
and `payment.router` was never passed to `app.include_router(...)`. Every
`/api/payments/...` request 404'd — the "Record Payment" button in the UI
was silently broken end-to-end.

This was found by cross-referencing every `app/api/*.py` router file
against `main.py`'s `include_router` calls (`alert.py`/`quotation.py`/
`report.py` are similarly orphaned singular-named duplicates of
`alerts.py`/`quotations.py`/`reports.py`, but — unlike `payment.py` — the
frontend never calls their paths, so they're genuinely dead code rather
than a live bug; left as-is, flagged for a future cleanup pass).

**Fix (`backend/main.py`):**
```python
from app.api import (..., payment)
...
app.include_router(payment.router, prefix="/api/payments", tags=["Payments"])
```
The `/api/payments` prefix was chosen to exactly match what
`frontend/src/api/client.ts` already calls
(`` `${BASE}/payments/${projectId}/invoices/${invoiceId}/payments` ``,
where `BASE = '/api'`) — no frontend change was needed.

**Verified live**, not just via `TestClient`: a throwaway backend instance
was started against an isolated SQLite file (never the real
`DATABASE_URL`), and a full flow was driven over real HTTP — login →
create client → create project → create+issue a standalone invoice →
`POST /api/payments/{project_id}/invoices/{invoice_id}/payments/manual` →
confirmed `200`, invoice `payment_status` flipped to `PAID`, `balance_due`
became `0`. Before the fix this returned `404` at every step past login.

**Tests:** `test_payment.py::TestRouterIsRegistered` (see
`UNIT_TESTING.md` §3) — imports the real `main.app` and asserts the
payment paths exist in its OpenAPI schema, as a permanent regression lock.

### 3.2 Payment audit trail always said `"system"`, never the real actor — **FIXED · was MEDIUM (accountability/non-repudiation gap on financial actions)**

**Root cause.** `record_manual_payment`, `initiate_payment`,
`transition_payment_processing`, `record_payment_success`,
`record_payment_failure`, and `correct_erroneous_payment` (all in
`app/services/payment_service.py`) accept a `user_id: str = "system"`
parameter and write it into the `AuditLog` row for that action. Every
route handler in `app/api/payment.py` already resolves the authenticated
caller via `user=Depends(require_roles("Admin", "Finance"))` — but none of
the 6 handlers passed `user_id=user.id` through to the service call, so
every payment ever recorded, initiated, corrected, or failed had its audit
entry attributed to the literal string `"system"`, regardless of which
Admin or Finance user actually performed it. This is inconsistent with
every other mutating endpoint in the codebase (`estimations.py`'s
`patch_estimation`/`delete_estimation` correctly pass `user_id=user.id`).

**Fix (`backend/app/api/payment.py`):** each of the 6 handlers now passes
`user_id=user.id`.

**Verified live** (same walkthrough as §3.1): after recording a payment
authenticated as the bootstrap admin, the resulting `AuditLog` row's
`user_id` was queried directly from the database and confirmed to be
`"bootstrap-admin"` (the real caller identity resolved from the token),
not `"system"`.

**Tests:** every test in `test_payment.py` that triggers an audit-logged
action asserts `logs[0].user_id == "admin-1"` (the test's authenticated
principal) rather than asserting only on HTTP status — see
`UNIT_TESTING.md` §3.

### 3.3 Manual security review of this pass's diff — no findings

A structured review (input validation, authn/authz, crypto/secrets,
injection/RCE, data exposure) was run against every file changed on this
branch. Full result:

> **No HIGH or MEDIUM confidence findings.**

Two candidates were investigated and ruled out as *not* deviations from
the app's existing (admittedly coarse) authorization model, rather than
new vulnerabilities:

- **Unvalidated `project_id` path segment on payment routes.** `POST
  /api/payments/{project_id}/invoices/{invoice_id}/payments/manual` never
  checks that `project_id` actually matches the invoice's real
  `project_id` — the handler only uses `invoice_id`. This is pre-existing
  code (the comment `# Note: In a real app we would query the invoice and
  verify project_id == invoice.project_id` was already there), and every
  sibling endpoint in `projects.py`/`invoices.py`/`project_summary.py`
  grants any Admin/Finance-role user global, unscoped access to every
  project — there is no per-project ACL anywhere in this app to bypass.
  Not exploitable as an authorization bypass; at most a decorative/unused
  URL segment. Documented here rather than silently dropped, in case a
  future multi-tenant redesign needs to know this parameter isn't
  currently load-bearing.
- **`AuditLog.user_id` foreign key removed.** Checked whether this lets a
  caller forge an arbitrary `user_id` to frame a different real user in
  the audit trail. Every call site sets `user_id=user.id` from the
  already-authenticated principal (never from request body/query input),
  so there is no attacker-controlled path into this field. Not
  exploitable.

### 3.4 Live-server smoke checks (beyond the payment flow)

Run against the same throwaway backend instance as §3.1:

| Check | Result |
|---|---|
| `POST /api/payments/.../manual` on an already-`PAID` invoice | `400 Cannot record payment: Invoice is already PAID.` — overpayment guard holds against a live server, not just `TestClient` |
| `GET /api/payments/.../payments` with no `Authorization` header | `401 Unauthorized. Please log in.` |
| Client creation with a malformed Indian mobile number | `422`, server-side `PHONE_RE` validation rejects it independent of frontend validation |
| Invoice line item with no matching billing classification and none supplied explicitly | `400 Could not confidently auto-match an HSN/SAC classification...` — the app refuses to guess a GST rate/HSN code rather than silently invoicing with a wrong one |

---

## 4. `test_auth_endpoints.py` (7 tests) — role/token enforcement over real routes

Mounts the real `invoices` router in isolation and drives it with a
genuine `TestClient`, seeding two real `User` rows (`finance_alice` /
Finance, `dev_bob` / Developer) so role checks resolve against actual
database rows, not mocks.

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_get_invoice_without_token_is_rejected` | No `Authorization` header | `401` |
| `test_get_invoice_with_garbage_token_is_rejected` | Header present, not a valid token shape | `401` |
| `test_get_invoice_with_token_forged_under_wrong_secret_is_rejected` | Well-formed token, signed with a secret the app doesn't use | `401` |
| `test_get_invoice_with_expired_token_is_rejected` | Valid signature, `exp` in the past | `401` |
| `test_developer_role_forbidden_from_finance_only_route` | Valid token for `dev_bob` (role `Developer`) on a route requiring `Admin`/`Finance` | `403` |
| `test_finance_role_allowed_gets_404_not_500_for_missing_invoice` | Valid token for `finance_alice`, unknown invoice id | `404`, not an unhandled `500` — confirms the role gate is passed *before* the not-found check runs, and that a missing resource doesn't leak an internal error |
| `test_unknown_username_in_valid_token_is_rejected` | Correctly signed, unexpired token for a username with no matching `User` row and not equal to the bootstrap admin username | `401` — a validly-signed token alone is not sufficient; the claimed identity must resolve to a real account or the bootstrap carve-out |

## 5. `test_auth_security.py` (12 tests) — HMAC token primitive

Tests `app.core.security.decode_access_token` in complete isolation (no
DB, no running server, no dependency on the real `JWT_SECRET` — each test
monkeypatches `config.JWT_SECRET` to a test-local value).

| Test | Verifies |
|---|---|
| `test_valid_token_decodes` | A correctly-signed, unexpired token decodes to its payload |
| `test_tampered_signature_rejected` | Flipping the signature to `'0' * 64` → `None` |
| `test_token_signed_with_wrong_secret_rejected` | A token forged with a different (attacker-guessed) secret → `None` |
| `test_expired_token_rejected` | `exp` in the past → `None` |
| `test_token_missing_exp_treated_as_expired` | No `exp` field at all → `None` (fails closed, doesn't default-trust) |
| `test_malformed_tokens_rejected` *(parametrized: not-a-token, too many dots, empty string, no dot)* | All → `None`, none raise |
| `test_payload_tampering_changes_signature_mismatch` | Editing the payload (e.g. `"user": "alice"` → `"admin"`) without the secret invalidates the signature | 
| `test_none_algorithm_style_bypass_rejected` | The classic JWT `alg=none` bypass doesn't apply to this HMAC-only scheme, but an empty or missing signature segment is still explicitly rejected |
| `test_jwt_secret_fails_closed_when_unset` | With `JWT_SECRET` unset and `.env` re-import prevented, importing `app.config` raises `RuntimeError` rather than falling back to a hardcoded default — this is the fix for a previously-hardcoded `"supersecretkey"`-style fallback found in an earlier security review |

## 6. `test_login_rate_limit.py` (5 tests) — login lockout

| Test | Verifies |
|---|---|
| `test_correct_login_succeeds` | Baseline positive control |
| `test_wrong_password_rejected_but_not_locked_out_immediately` | One failure alone doesn't trigger `429` |
| `test_repeated_failures_trigger_lockout` | `MAX_FAILED_ATTEMPTS` wrong-password attempts, then even the **correct** password → `429` — a brute-forcer can't slip through by eventually guessing right inside the flood |
| `test_lockout_is_scoped_to_ip_and_username_pair` | Locking out `(ip, "bob")` doesn't lock out `(ip, "alice")` — no shared-IP collateral lockout |
| `test_successful_login_clears_prior_failure_count` | A successful login resets the failure counter, so the count doesn't silently carry over and trigger a lockout on unrelated future failures |

## 7. `test_path_traversal.py` (7 tests) — output-path traversal guard

**Context:** `app.api.documents._safe_output_path` is the fix for a
path-traversal vulnerability found in an earlier security review —
`base_name` path parameters on `/api/documents/{base_name}/...` endpoints
used to be joined into a filesystem path with a raw f-string and never
validated, so a `base_name` like `"../../../etc/passwd"` could escape
`OUTPUT_DIR`.

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_normal_filename_resolves_inside_output_dir` | An ordinary filename | Resolves inside `OUTPUT_DIR`, as expected |
| `test_path_traversal_sequences_rejected` *(parametrized: `../../../etc/passwd`, `..\..\..\windows\win.ini`, 6-level `../` chain to `/etc/shadow`)* | Classic traversal sequences, both Unix and Windows separator styles | `HTTPException(400)` |
| `test_url_encoded_traversal_is_decoded_before_reaching_this_function` | `..%2f..%2f..%2fetc%2fpasswd_data.json` | Resolves harmlessly inside `OUTPUT_DIR` — documents that Starlette already URL-decodes path params *before* this function ever sees them, so `%2f` arrives as a literal 3-character string here, not a real path separator; the real decoding boundary is upstream, not in this function |
| `test_absolute_path_injection_rejected` | `/etc/passwd` as the "filename" | `HTTPException(400)` — an absolute path would otherwise make `out_dir / filename` discard `out_dir` entirely, since `pathlib`'s `/` operator honors an absolute right-hand side |
| `test_legitimate_looking_but_escaping_name_rejected` | `normal_name/../../../secrets_data.json` | `HTTPException` — a traversal sequence *embedded* inside an otherwise normal-looking name is still caught |

---

## 8. Known gaps / not covered by this document

- **No `is_active`/disabled flag on `User`.** (`app/models/user.py`) A
  compromised or ex-employee account can only be deleted outright, not
  deactivated-and-auditable-later. Pre-existing; not touched this pass.
- **No server-side token revocation.** The HMAC token scheme has a fixed
  24h TTL and no blocklist — a leaked, unexpired token for a still-active
  account remains valid until it naturally expires. Pre-existing.
- **`QA_TEST_API_KEY` / `X-API-Key` bootstrap path.** `app/api/dependencies.py`'s
  `get_current_user` resolves an `X-API-Key` header to `config.QA_TEST_USERNAME`,
  falling back to a synthetic bootstrap Admin user if no matching row
  exists and the configured QA username equals `ADMIN_USERNAME`. Confirm
  `QA_TEST_API_KEY` is unset (or QA/staging-only) in any environment this
  code runs in outside local dev — it is not exercised by any test in this
  document.
- **`.env.example` ships illustrative weak values** (`JWT_SECRET=pixous-super-secret-key-12345`,
  `ADMIN_PASSWORD=admin123`). These are documentation placeholders, not
  the real `.env` (not read as part of this review), but worth an explicit
  reminder here: rotate both to strong, unique values before any shared
  staging/production deployment, and confirm `.env` itself is
  git-ignored (`.gitignore` was not modified by this pass; verify
  separately that it already excludes `.env`).
- **PDF generation environment gap** (Playwright browser binary not
  installed, WeasyPrint fallback missing GTK3 on Windows) — not a security
  finding, but recorded in `TESTING.md` §5 since it was discovered during
  this pass's live walkthrough and blocked testing `GET
  /api/invoices/{id}/pdf` end-to-end.
- **`/{full_path:path}` SPA catch-all returns `200` HTML for any unmatched
  path**, including malformed/mistyped API-shaped paths — not an auth
  bypass (the SPA itself requires no auth) but recorded in `TESTING.md` §5
  as a debuggability footgun worth fixing separately.
