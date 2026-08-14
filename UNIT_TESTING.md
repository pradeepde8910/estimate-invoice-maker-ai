# Unit Test Documentation

Scope: `tests/test_unit_security_utils.py`, `tests/test_unit_invoice_builder.py`,
`tests/test_unit_api_auth_helpers.py`.

This document covers **unit tests only** — tests that exercise a single
module's pure/deterministic logic directly (no HTTP layer, no end-to-end
flow). For integration/E2E coverage over the FastAPI app, see the main
`TESTING.md`. For authentication/authorization/injection-focused tests,
see `SECURITY_TESTING.md`.

## 1. Framework & conventions

- **Framework:** Pytest.
- **Pattern:** Arrange–Act–Assert. Test names state the condition and the expected behavior: `test_<subject>_<condition>_<expected_outcome>`.
- **Mocking policy:** The system under test is never mocked. The only thing ever patched in this layer is `time.time()` (via `monkeypatch`) to make sliding-window/lockout-expiry logic in the rate limiter deterministic without real sleeps. `bcrypt`, `KeyManager`'s `asyncio.Lock`, and `invoice_builder`'s HTML generation all run for real.
- **No DB, no network:** none of these tests touch the database or the network. `test_unit_api_auth_helpers.py` uses the `db_session` fixture from `conftest.py` only for the two `is_valid_username` cases that need a real `User` row to query against — that fixture still points at the isolated temp SQLite file, never production data.

## 2. How to run

```bash
# All unit tests
python -m pytest tests/test_unit_security_utils.py tests/test_unit_invoice_builder.py tests/test_unit_api_auth_helpers.py -v

# One file
python -m pytest tests/test_unit_invoice_builder.py -v

# One test
python -m pytest tests/test_unit_security_utils.py::test_hash_password_is_salted_so_same_input_yields_different_hashes -v
```

Current status: **42 passed**, 0 failed.

---

## 3. `tests/test_unit_security_utils.py`

**Modules under test:** `utils/security.py`, `utils/rate_limiter.py`, `utils/key_manager.py`.

### 3.1 `utils/security.py` — password hashing

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_hash_password_returns_a_bcrypt_hash_distinct_from_input` | Hash a plaintext password | Result is a recognizable bcrypt hash and is never equal to the input |
| `test_hash_password_is_salted_so_same_input_yields_different_hashes` | Hash the same password twice | The two hashes differ (bcrypt salt is randomized per call) |
| `test_verify_password_accepts_correct_bcrypt_hash` | Verify the correct password against its bcrypt hash | Returns `True` |
| `test_verify_password_rejects_wrong_password_against_bcrypt_hash` | Verify an incorrect password against a bcrypt hash | Returns `False` |
| `test_verify_password_accepts_matching_legacy_plaintext` | Verify against a legacy (pre-bcrypt) plaintext row where the password matches | Returns `True` |
| `test_verify_password_rejects_mismatched_legacy_plaintext` | Verify against a legacy plaintext row where the password does not match | Returns `False` |
| `test_verify_password_rejects_when_stored_is_empty_or_none` | Stored hash is `""` or `None` | Returns `False` for both — never raises |
| `test_verify_password_handles_malformed_bcrypt_prefixed_hash_without_raising` | Stored value starts with a bcrypt prefix (`$2b$`) but isn't a well-formed hash (e.g. corrupted by a bad migration) | Returns `False` — fails closed instead of raising and 500ing the login endpoint |
| `test_is_bcrypt_hash_false_for_none_and_plain_strings` | `is_bcrypt_hash(None)`, `is_bcrypt_hash("")`, `is_bcrypt_hash("plaintext-password")` | All return `False` |
| `test_is_bcrypt_hash_true_for_all_supported_prefixes` | A well-formed hash string for each of `$2a$`/`$2b$`/`$2y$` | All return `True` |

**Why these edge cases matter:** the malformed-hash and empty/`None`-stored
cases are the two failure modes that would otherwise turn a login attempt
into an unhandled exception (a 500) instead of a clean authentication
failure (a 401) — the boundary between "wrong password" and "broken data"
must fail safely either way.

### 3.2 `utils/rate_limiter.py` — login lockout

An `autouse` fixture (`_clear_rate_limiter_state`) clears the module's
process-global `_failures`/`_locked_until` dicts before and after every
test in this section, since the rate limiter intentionally has no other
reset mechanism (it's designed to persist for the life of the process).

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_check_login_rate_limit_returns_none_when_no_failures_recorded` | Fresh (ip, username) pair | `check_login_rate_limit` returns `None` (not locked out) |
| `test_record_login_failure_below_threshold_does_not_lock_out` | `MAX_FAILED_ATTEMPTS - 1` failures recorded | Still not locked out |
| `test_record_login_failure_at_threshold_locks_out_with_correct_duration` | `MAX_FAILED_ATTEMPTS` failures recorded | Locked out; remaining seconds is `> 0` and `<= LOCKOUT_SECONDS` |
| `test_lockout_key_is_scoped_to_ip_and_username_case_insensitively` | Lock out `(ip, "Alice")`, then check `(ip, "alice")` and `(other_ip, "alice")` | Same-ip/different-case is still locked out (case-insensitive username key); different-ip is not locked out (scoped per source IP) |
| `test_record_login_success_clears_failures_and_lockout` | Lock out a pair, then record a success for it | Lockout is cleared immediately |
| `test_lockout_expires_after_lockout_window_elapses` (monkeypatch `time.time`) | Lock out at `t=0`, check at `t=LOCKOUT_SECONDS+1` | No longer locked out |
| `test_failures_outside_sliding_window_are_not_counted` (monkeypatch `time.time`) | Record `MAX_FAILED_ATTEMPTS - 1` failures at `t=0`, one more at `t=WINDOW_SECONDS+1` | Old failures have aged out of the sliding window, so the pair is still below threshold and not locked out |

**Why these edge cases matter:** the case-insensitivity and per-(ip,
username) scoping tests exist because a rate limiter scoped incorrectly
either fails to protect an account (case mismatch bypass) or accidentally
locks out unrelated legitimate users sharing an IP (see the companion
integration test in `SECURITY_TESTING.md` §`test_rate_limit_is_scoped_per_username_not_globally`). The
window/expiry tests exist because a sliding window implemented with an
unbounded list, or a lockout with no expiry, are both easy off-by-one
mistakes that only surface under time pressure.

### 3.3 `utils/key_manager.py` — API key round-robin/failover

All async tests wrap their body in a local `_run()` coroutine and drive it
with `asyncio.run(...)`, since `KeyManager` uses `asyncio.Lock` internally.

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_key_manager_requires_at_least_one_key` | Construct with `[]` | Raises `ValueError` |
| `test_key_manager_round_robins_across_keys` | 3 keys, call `get_key()` 6 times | Returns `[k1, k2, k3, k1, k2, k3]` in strict rotation |
| `test_key_manager_skips_keys_marked_failed` | Mark `k2` failed, then call `get_key()` 4 times | `k2` never returned; only `k1`/`k3` cycle |
| `test_key_manager_resets_and_recovers_when_all_keys_have_failed` | Mark every key failed, then call `get_key()` | Does not deadlock or raise — resets the failed set and returns a key; `available_count` returns to `total_count` afterward |
| `test_key_manager_available_and_total_count_reflect_failures` | Mark 1 of 3 keys failed | `total_count == 3`, `available_count == 2` |
| `test_key_manager_reset_clears_all_failed_keys` | Mark a key failed, call `reset()` | `available_count == total_count` again |

**Why these edge cases matter:** the all-keys-failed case is the one that
would silently deadlock a production LLM-key rotator (every remaining
provider request blocking forever) if the reset-on-exhaustion branch were
missing or buggy — this is the single most important case in the file.

---

## 4. `tests/test_unit_invoice_builder.py`

**Module under test:** `invoice_builder.build_invoice` — pure, deterministic
HTML generation from estimation data (no LLM, no DB, no network call of
any kind).

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_build_invoice_computes_tax_and_total_from_subtotal` | `grand_total=780000`, `tax_percentage=18.0` | `meta["subtotal"] == 780000`, `tax_amount ≈ 780000*0.18`, `total_due ≈ 780000*1.18` |
| `test_build_invoice_due_date_offsets_from_invoice_date_by_due_days` | `due_days=30`, explicit `invoice_date` | `due_date - invoice_date == timedelta(days=30)` exactly |
| `test_build_invoice_includes_bank_box_only_when_bank_name_configured` | Build once with `bank_name` set, once without | Bank box markup present only in the first case |
| `test_build_invoice_line_items_sorted_by_cost_descending` | Two role estimates, one with a higher `total_cost` | Higher-cost line item appears earlier in the rendered HTML |
| `test_build_invoice_adds_extra_rows_for_infra_license_and_contingency` | Non-zero `infrastructure_cost_monthly`, `third_party_licenses_monthly`, `contingency_amount` | All three corresponding extra line-item rows appear in the HTML |
| `test_build_invoice_escapes_malicious_client_name_to_prevent_xss` | `client_name = "<script>alert(1)</script>"` | Raw `<script>` tag never appears in the rendered HTML (`&lt;script&gt;` does); the *unescaped* raw value is still returned in `meta` for callers who need it |
| `test_build_invoice_escapes_malicious_bank_details` | `bank_name = '"><img src=x onerror=alert(1)>'` | No real `<img>` tag is formed in the output (`"<img src=x" not in html`); the escaped literal text is present instead |
| `test_build_invoice_falls_back_to_unspecified_client_when_no_name_given` | No `client_name` anywhere in the input data | `meta["client_name"] == "Unspecified Client"`, and that string appears in the HTML |
| `test_build_invoice_handles_no_line_items_without_raising` | `role_estimates = []`, `grand_total = 0` | Does not raise; `subtotal`/`total_due` are `0`; an (empty) `<tbody>` is still emitted |
| `test_build_invoice_uses_supplied_status_for_badge_and_meta` | `status="Paid"` | `meta["status"] == "Paid"`; the "Paid" status badge color (`#DCFCE7`) appears in the HTML |

**Design note — asserting structural safety, not string absence:** for
attacker-controlled strings rendered into HTML (the two XSS tests above),
the correct assertion is "no real tag/attribute is formed"
(`"<img src=x" not in html`), not "the substring `onerror=alert(1)` never
appears anywhere." `html.escape()` neutralizes the angle brackets and
quotes that actually matter for breaking out of a text node; the escaped
text naturally still *contains* those words as harmless text. Asserting
plain substring absence here would be a false requirement that doesn't
correspond to any real vulnerability.

---

## 5. `tests/test_unit_api_auth_helpers.py`

**Module under test:** `api.py`'s token/identity primitives —
`decode_token`, `verify_token`, `is_valid_username` — tested directly and
independently of the HTTP/middleware layer that calls them.

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_decode_token_returns_payload_for_a_validly_signed_unexpired_token` | A token forged the same way `api.create_token` builds one | Returns the decoded `{"user": ..., "exp": ...}` payload |
| `test_decode_token_returns_none_for_tampered_signature` | Last 4 characters of a valid token's signature replaced | Returns `None` |
| `test_decode_token_returns_none_for_expired_token` | Token with `exp` in the past | Returns `None` |
| `test_decode_token_returns_none_for_malformed_token_shape` | Not base64/JSON at all, empty string, or too many `.`-separated parts | Returns `None` for all three — never raises |
| `test_verify_token_is_a_thin_boolean_wrapper_over_decode_token` | Valid token vs. the same token with a tampered signature | `True` then `False` — confirms `verify_token` is exactly `decode_token(token) is not None` |
| `test_is_valid_username_true_for_existing_user_row` | A real `User` row exists for the username | Returns `True` |
| `test_is_valid_username_true_for_bootstrap_admin_even_without_user_row` | Username equals `config.ADMIN_USERNAME`, no matching `User` row | Returns `True` (the same bootstrap carve-out `login_endpoint` trusts) |
| `test_is_valid_username_false_for_unknown_username` | Username matches neither a `User` row nor `ADMIN_USERNAME` | Returns `False` |
| `test_is_valid_username_false_for_empty_or_none` | `""` and `None` | Both return `False` |

**Why this file exists separately from the security suite:** these are
the exact primitives `auth_middleware` and `get_current_username` rely on
to close the JWT-forgery gap described in `SECURITY_TESTING.md` §2. Unit
tests here isolate their logic from the HTTP layer so a future change to
the middleware's plumbing can't accidentally leave a hole in
`decode_token`/`is_valid_username` unnoticed just because the higher-level
HTTP test happened to still pass for an unrelated reason.
