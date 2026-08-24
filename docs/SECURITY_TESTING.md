# Security Test Documentation

Scope: `tests/test_security_auth.py`, `tests/test_security_files.py`,
`tests/test_security_html_sanitize.py`,
`tests/test_security_estimation_invoice_authz.py`,
`tests/test_security_input_validation.py`, `tests/test_security_qa_api_key.py`.

This document covers **security-focused tests** — authentication,
authorization, injection, and file/network-boundary tests — plus the
findings this pass fixed directly and why. For pure unit tests of
individual modules, see `UNIT_TESTING.md`. For end-to-end/feature coverage,
see `TESTING.md`.

## 1. Framework & conventions

- **Framework:** Pytest, with FastAPI's `TestClient` (Starlette/httpx) driving the real ASGI app.
- **Isolation:** `tests/conftest.py` points `DATABASE_URL` at a throwaway temp SQLite file *before* any project module is imported; the `fresh_database` fixture drops/recreates every table before each test. No test touches `pixous.db` / production data.
- **Mocking policy:** only external network calls (`requests.get` in `download_url`) are mocked. Authentication, JWT signing/verification, password hashing, role checks, and the database all run for real. A finding is never "proven" against a mock of the thing being tested.
- **Test-naming convention for this suite specifically:** a test whose name describes an attack succeeding (e.g. `..._can_rewrite_...`, `..._is_accepted_by_...`) documents a live, unfixed gap at the time it was written. Once a gap is fixed, the test is rewritten to describe the *rejection* (e.g. `..._cannot_rewrite_...`, `..._is_rejected_by_...`) and becomes a regression lock rather than a documented gap. Every finding below states which state each of its tests is currently in.
- **Sensitive-value handling:** `test_catchall_route_leaks_live_dotenv_secrets` deliberately never prints or logs the response body, even on assertion failure — only the *presence* of a leaked secret is asserted, so a regression can't itself leak real credentials into CI logs.

## 2. How to run

```bash
# All security tests
python -m pytest tests/test_security_*.py -v

# One file
python -m pytest tests/test_security_estimation_invoice_authz.py -v

# One test
python -m pytest tests/test_security_auth.py::test_login_locks_out_after_repeated_failures -v
```

Current status: **72 passed**, 0 failed.

---

## 3. Findings fixed in this pass

Three findings were fixed directly in `api.py`/`config.py` rather than
left as documented-but-open gaps, sized to this app's current
single-admin (CEO) usage model — the smallest secure change that closes
each gap now, without building a multi-tenant RBAC system the product
doesn't need yet.

### 3.1 JWT accepted usernames that don't correspond to a real account — **FIXED · was CRITICAL**

**Root cause.** `verify_token` used to check only the HMAC signature and
expiry of a bearer token — never that the embedded username corresponded
to an actual account. Anyone who knew `JWT_SECRET` (the hardcoded fallback
that used to ship in `config.py`, or any leaked value) could mint a valid
token for a username that was never created, and pass every protected
route with an identity that has no account to disable or audit
afterward.

**Fix (`api.py`):**
- `decode_token(token)` replaces the old boolean-only internals of `verify_token`, returning the decoded `{"user": ..., "exp": ...}` payload (or `None`) so callers can inspect *who* the token claims to be, not just whether the signature checks out.
- `is_valid_username(username, db)` returns `True` only if a `User` row exists for that username, or the username is the bootstrap `config.ADMIN_USERNAME` — the same carve-out `login_endpoint` already trusts before any `User` row exists.
- `auth_middleware` now calls both, for every Bearer-token request, and returns `401` ("Account no longer exists or is inactive.") before the request ever reaches a route handler.
- `get_current_username` performs the same check again independently — defense in depth; it must not rely solely on the middleware having already run.

**Known limitation:** this checks *existence*, not an *active/disabled*
flag — `db.py`'s `User` model has no such column today. If you need to
revoke an account without deleting it later, that's a schema addition
(`is_active: Boolean`) this pass deliberately didn't make, since existence
alone closes the immediate gap.

**Tests (all in `test_security_auth.py` unless noted):**

| Test | Verifies |
|---|---|
| `test_token_forged_for_nonexistent_user_is_rejected_by_middleware` | A forged token for a username with no matching `User` row now gets `401`, not `200` (**regression lock** — previously named `..._is_accepted_by_middleware` and asserted the opposite) |
| `test_token_for_real_user_is_still_accepted_by_middleware` | Positive control: a token for an account that *does* exist is still accepted |
| `test_token_with_no_matching_user_row_cannot_rewrite_bank_details` | The same forged-token scenario against a mutating endpoint (`PUT /api/organization`) now `401`s before role is even evaluated |
| `test_token_with_wrong_signature_is_rejected` | Tampering the signature of a validly-shaped token still fails (confirms the HMAC check itself, independent of the identity check, was never the weak point) |
| `test_expired_token_is_rejected` | A token with `exp` in the past is rejected |
| `test_protected_routes_reject_missing_auth_header` | No `Authorization` header at all → `401` |
| `test_decode_token_*`, `test_is_valid_username_*` (`test_unit_api_auth_helpers.py`) | Direct unit coverage of the two new primitives — see `UNIT_TESTING.md` §5 |

### 3.2 Missing RBAC on `PATCH /api/estimations/{id}` and `PATCH /api/invoices/{id}` — **FIXED · was HIGH**

**Root cause.** `patch_estimation` and `patch_invoice` resolved the
caller's identity (`get_current_username`) but never called
`require_role(...)`, unlike every other mutating endpoint in `api.py`
(`delete_estimation`, `delete_invoice`, `update_organization`,
`upload_organization_asset`, `update_rate_card`, and the dedicated
`PUT /invoice/status` endpoint all did). Any authenticated account,
regardless of role, could rewrite an estimation's
`grand_total`/`timeline_weeks`/`project_name`, or an invoice's
`subtotal`/`gst_amount`/`discount`/`total`/**`status`**.
`PATCH /api/invoices/{id}` with `{"status": "Paid"}` achieved the exact
same effect as `PUT /api/estimations/{base_name}/invoice/status`, which
*did* correctly restrict that action to `Admin`/`Finance` — the two
endpoints disagreed on who could mark an invoice Paid.

**Fix (`api.py`):** both handlers now start with
`require_role(request, db, {"Admin"})`, matching the file's existing
convention and the current reality that only the CEO's Admin account
performs these edits. If Finance is later given day-to-day ownership of
invoice edits, widen `patch_invoice`'s allowed-role set to
`{"Admin", "Finance"}` to match the status endpoint — left narrower for
now rather than guessed at.

**Tests (`test_security_estimation_invoice_authz.py`):**

| Test | Verifies |
|---|---|
| `test_developer_role_cannot_rewrite_estimation_grand_total_via_patch` | Developer role → `403` (**regression lock**) |
| `test_finance_role_cannot_rewrite_estimation_grand_total_via_patch` | Finance role → `403` (estimation edits are Admin-only, not Admin/Finance) |
| `test_admin_role_can_still_rewrite_estimation_grand_total_via_patch` | Positive control: Admin → `200`, field actually updated |
| `test_token_for_nonexistent_user_cannot_rewrite_estimation_financials` | Forged token for a nonexistent user → `401` (caught even earlier, by §3.1's middleware check) |
| `test_patch_estimation_requires_some_valid_auth_token` | No auth header → `401` |
| `test_patch_estimation_unknown_id_returns_404_not_500` | Admin, unknown `id` → clean `404`, no stack trace in the response |
| `test_developer_role_cannot_mark_invoice_paid_via_patch` | Developer role blocked on *both* `PUT /invoice/status` (`403`) and the generic `PATCH /api/invoices/{id}` (`403`) — confirms the two endpoints now agree; also confirms the invoice's stored status is genuinely unchanged after both attempts |
| `test_admin_role_can_still_patch_invoice_fields` | Positive control: Admin → `200`, status actually updated |
| `test_patch_invoice_requires_some_valid_auth_token` | No auth header → `401` |
| `test_delete_invoice_still_correctly_requires_admin_role` | Positive control: `delete_invoice` already required Admin before this fix and still does — confirms `patch_estimation`/`patch_invoice` are now consistent with it rather than exceptions |

### 3.3 QA `X-API-Key` bypassed authorization entirely — **FIXED · was MEDIUM**

**Root cause.** The QA static-API-key branch in `auth_middleware` used to
`return await call_next(request)` immediately on a valid key, skipping
identity resolution entirely. Any `require_role(...)` check downstream
calls `get_current_username`, which requires an `Authorization: Bearer`
header — a QA request authenticated only via `X-API-Key` has none. In
practice this meant QA traffic either broke unexpectedly against
role-gated endpoints, or (had `get_current_username` ever been changed to
fail open instead of raising) could have bypassed authorization
altogether rather than just authentication.

**Fix (`config.py`, `api.py`):**
- `config.QA_TEST_USERNAME` added (defaults to `ADMIN_USERNAME`).
- On a valid `X-API-Key`, `auth_middleware` sets `request.state.qa_authenticated_username = config.QA_TEST_USERNAME` and continues — it no longer short-circuits past identity resolution.
- `get_current_username` checks that state first and returns it directly, so `get_current_role`/`require_role` resolve a real role for QA traffic exactly as they would for a Bearer-token login.
- `QA_TEST_API_KEY` remains empty by default — any `X-API-Key` header is rejected with `401` ("QA mode disabled") when it's unset, and `.env.example` documents it as QA/staging-only; leave it blank in production.

**Tests (`test_security_qa_api_key.py`):**

| Test | Verifies |
|---|---|
| `test_qa_api_key_disabled_by_default_rejects_any_header_value` | `QA_TEST_API_KEY` unset → *any* `X-API-Key` value still `401`s |
| `test_qa_api_key_wrong_value_is_rejected` | Configured key, wrong value sent → `401` |
| `test_qa_api_key_correct_value_grants_access` | Configured key, correct value sent → `200` |
| `test_qa_api_key_resolves_to_configured_username_not_a_bypass` | `QA_TEST_USERNAME` pointed at a real Developer-role account → an Admin-only endpoint (`PUT /api/rate-card`) still `403`s — the key is not a bypass |
| `test_qa_api_key_with_admin_configured_username_passes_admin_gate` | Positive control: `QA_TEST_USERNAME` pointed at an Admin-role account → the same Admin-only endpoint succeeds |
| `test_qa_api_key_defaults_to_bootstrap_admin_username_with_no_user_row` | Default `QA_TEST_USERNAME` (`== ADMIN_USERNAME`) works out of the box with no `User` row provisioned |
| `test_qa_api_key_takes_precedence_over_a_missing_bearer_token` | A request with only `X-API-Key` (no `Authorization` header at all) is still correctly authenticated, not treated as anonymous |

---

## 4. Confirmed-fixed items from the original audit (regression-locked, unchanged this pass)

These were already covered before this test pass and remain green — listed
here for completeness so this document is the full picture of the app's
security test coverage, not just what changed most recently.

### 4.1 `test_security_auth.py`

| Test | Verifies |
|---|---|
| `test_login_succeeds_with_correct_password_and_stores_bcrypt_hash` | Correct login succeeds; the stored `password_hash` is a real bcrypt hash, never the raw password |
| `test_login_rejects_wrong_password` | Wrong password → `401` |
| `test_legacy_plaintext_row_still_logs_in_and_is_upgraded_to_bcrypt` | A pre-hashing legacy row (raw plaintext in `password_hash`) still logs in on the correct password, and is transparently rehashed to bcrypt on that first successful login |
| `test_stored_password_is_never_plaintext_after_creation` | `password_hash` for a freshly created user is bcrypt, never plaintext |
| `test_bootstrap_admin_login_uses_whatever_is_actually_configured` | The one-time bootstrap admin login works using whatever `ADMIN_PASSWORD` is actually configured in this environment (skips if unset — the secure default) |
| `test_wrong_password_rejected_on_empty_user_table` | Wrong password against the bootstrap path (empty `User` table) still `401`s |
| `test_bootstrap_path_disabled_when_admin_password_unset` | `ADMIN_PASSWORD=""` fully disables the bootstrap login path |
| `test_login_locks_out_after_repeated_failures` | 8 rapid failed attempts → first 5 return `401`, the rest return `429` |
| `test_rate_limit_is_scoped_per_username_not_globally` | A lockout on one username doesn't lock out a different legitimate user from the same client IP |
| `test_successful_login_resets_the_failure_counter` | A successful login resets the failure count, so the next few wrong attempts don't immediately re-trigger the lockout |
| `test_developer_role_cannot_rewrite_bank_details` | Developer role → `403` on `PUT /api/organization` |
| `test_admin_role_can_rewrite_bank_details` | Admin role → `200`, bank details actually updated |
| `test_developer_role_cannot_delete_estimations` | Developer role → `403` on `DELETE /api/estimations/{id}` |
| `test_finance_role_can_update_invoice_status_but_developer_cannot` | Finance role passes the invoice-status role gate; Developer role is blocked |
| `test_cors_never_allows_credentials_regardless_of_origin` | `allow_credentials` is never `true` in a CORS preflight response, regardless of the `Origin` sent — auth here is a Bearer header, never a cookie, so credentialed cross-site requests have nothing to ride along |
| `test_deleting_nonexistent_estimation_does_not_leak_stack_trace` | A 404/500 error response never contains `"Traceback"` or a raw `sqlalchemy` internal string |

### 4.2 `test_security_files.py`

| Test | Verifies |
|---|---|
| `test_catchall_path_join_escapes_frontend_dist_for_dotdot_input` | Reproduces, in isolation, why an unguarded `FRONTEND_DIST / full_path` join is unsafe for `../../config.py`-style input |
| `test_catchall_route_does_not_serve_files_outside_frontend_dist` | The actual SPA catch-all route rejects both literal `../` and percent-encoded (`..%2f`) traversal attempts, for both `config.py` and `.env` targets |
| `test_catchall_route_leaks_live_dotenv_secrets` | Regression lock for the specific historical exploit: the encoded-traversal payload must never return the live `.env` file's contents (asserts *absence* only — never logs the body, see §1) |
| `test_branding_upload_requires_no_authentication` *(name reflects the route, not a vulnerability)* | `POST /api/organization/{slot}` with no auth header → `401` (the middleware gate itself; what an authenticated upload accepts is covered separately below) |
| `test_save_branding_file_rejects_html_extension` | An upload named `signature.html` containing a `<script>` payload is rejected, never written to disk |
| `test_save_branding_file_rejects_content_mismatched_extension` | A file named `logo.png` whose real bytes are HTML (extension/content-type spoofing) is rejected — Pillow verifies the actual format |
| `test_save_branding_file_accepts_a_real_png` | Positive control: a genuine PNG upload still succeeds |
| `test_save_branding_file_never_deletes_existing_asset_on_invalid_upload` | A rejected upload never deletes the pre-existing valid asset for that slot — validation happens before any file is touched |
| `test_branding_static_mount_requires_no_authentication` | `/branding/*` static files are servable with no `Authorization` header, by design (needed for the pre-login logo) — documents this is intentional, not a gap, given the upload-side validation above |
| `test_download_url_blocks_internal_and_link_local_targets` | Cloud metadata (`169.254.169.254`), loopback, RFC1918 private ranges, and the `file://` scheme are all rejected by `_assert_safe_url` before `requests.get` is ever called (verified via a spy that fails the test if reached) |
| `test_download_url_allows_public_looking_host` | Positive control: a hostname resolving to a public IP is still allowed through |
| `test_download_url_does_not_follow_redirects` | A 302 response is never followed (`allow_redirects=False` is enforced) — closes the classic "public host redirects to an internal address" allow-list bypass |

### 4.3 `test_security_html_sanitize.py`

| Test | Verifies |
|---|---|
| `test_strips_script_tags` | `<script>` content is removed entirely, surrounding content preserved |
| `test_strips_event_handler_attributes` | `onerror`/`onclick` attributes are stripped; unrelated attributes (`src`) survive |
| `test_neutralizes_javascript_uri` | `href="javascript:..."` URIs are neutralized |
| `test_strips_iframe_object_embed` | `<iframe>`/`<object>` tags are removed |
| `test_preserves_legitimate_invoice_markup_and_styles` | Full invoice document structure, `<style>` blocks, and inline `style` attributes survive sanitization unmangled |
| `test_invoice_save_endpoint_strips_injected_script` | End-to-end: a `<script>` payload submitted through `PUT /api/documents/{base_name}/invoice` is stripped before being stored in the DB |

### 4.4 `test_security_input_validation.py`

| Test | Verifies |
|---|---|
| `test_organization_update_rejects_malformed_email` | `email` failing `EMAIL_RE` → `422` |
| `test_organization_update_rejects_phone_with_wrong_digit_count` | `phone` not exactly 10 digits → `422` |
| `test_organization_update_rejects_non_numeric_phone` | Non-numeric `phone` → `422` |
| `test_organization_update_rejects_malformed_gstin` | `gstin` failing `GSTIN_RE` → `422` |
| `test_organization_update_accepts_valid_gstin_and_normalizes_case` | Valid lowercase GSTIN accepted and upper-cased on save |
| `test_organization_update_html_in_name_field_is_stored_but_never_executed` | `name` field accepts arbitrary text including `<script>` — documents that *this* field's safety comes from render-time escaping (see `UNIT_TESTING.md` §4), not input rejection |
| `test_organization_update_rejects_oversized_address_field` | `address` beyond its `max_length` → `422` |
| `test_organization_update_requires_admin_and_rejects_sql_metacharacters_safely` | A classic SQL-injection-shaped string (`Robert'); DROP TABLE ...;--`) is stored verbatim via the parameterized ORM call, never interpreted; the table remains queryable afterward |
| `test_patch_estimation_rejects_negative_grand_total` | Negative `grand_total` in a patch payload → `422` |
| `test_patch_estimation_rejects_negative_timeline_weeks` | Negative `timeline_weeks` → `422` |
| `test_patch_estimation_rejects_missing_required_version_field` | Omitting the required optimistic-lock `version` field → `422` |
| `test_invoice_patch_rejects_negative_subtotal` | Negative `subtotal` on an invoice patch → `422` |
| `test_rate_card_update_requires_admin_role` | Developer role → `403` on `PUT /api/rate-card` |
| `test_rate_card_update_persists_new_custom_role_for_admin` | Admin can add a new custom rate-card role; test snapshots/restores the process-global `config.DEVELOPER_RATES` dict so it can't leak into other tests |
| `test_get_rate_card_is_readable_without_admin_role` | Reading the rate card has no role restriction (only writing does) |

---

## 5. Notable design decisions in the security suite

- **Forged tokens use the real signing path.** Every "attacker" token in this suite is built with the exact same HMAC construction `api.create_token` uses (see `_forge_token`/`auth_helper.forge_token`), so a test failure means the real signing/verification code has a gap — not that the test's forgery routine drifted from production behavior.
- **Regression tests over "documented gap" tests, once fixed.** A test that once proved a vulnerability existed is rewritten in place (not just deleted and replaced) once the fix lands, so `git log` on the test file shows the exploit → fix → lock progression rather than losing that history.
- **Global mutable state is snapshotted and restored.** `update_rate_card` mutates the process-global `config.DEVELOPER_RATES` dict in place; `test_rate_card_update_persists_new_custom_role_for_admin` snapshots it beforehand and restores it in a `finally` block so it can't bleed into other tests' expectations of the default rate card.
- **Sized to actual usage, not maximal RBAC.** The Admin-only fix in §3.2 is deliberately narrower than "Admin or Finance" even though the dedicated status endpoint allows Finance — because no Finance-role workflow for editing estimations/invoices directly exists yet in this product. Widening it later is a one-line change with a clear trigger (a real Finance user needing it), not a guess made now.

## 6. Known gaps / not covered by this suite

- No `is_active`/disabled flag exists on `User` yet (see §3.1) — a compromised or ex-employee account can only be removed, not deactivated-and-audited-later.
- Session/token revocation: there's no server-side token blocklist — a leaked, unexpired JWT for a real, still-active account remains valid until it naturally expires (24h). This is a separate concern from the "does the account exist" check fixed in §3.1.
- Rate limiting is per-process (`utils/rate_limiter.py`'s own module docstring already documents this); behind multiple workers the effective limit is `MAX_FAILED_ATTEMPTS * worker_count`. Not exercised by any test here since it requires a multi-process setup this suite doesn't run.
