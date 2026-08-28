# Unit & Business-Logic Test Documentation

Scope: `backend/app/tests/test_pdf_service.py`, `test_billing_type_service.py`,
`test_invoice_dates.py`, `test_detached_session_regression.py`,
`test_payment.py`, `test_billing_preview.py`, `test_audit_log.py`, plus the
frontend's Vitest suite under `frontend/src/`.

This document covers tests that exercise business/domain logic directly —
PDF/invoice math, billing classification, payment state transitions, N+1
query-shape regressions, and frontend component behavior. For
authentication/authorization/injection-focused tests, see
[SECURITY_TESTING.md](SECURITY_TESTING.md). For the full inventory and
how-to-run instructions, see [TESTING.md](TESTING.md).

## 1. Framework & conventions

- **Backend:** Pytest. Each test file that needs a database builds its own
  isolated `sqlite:///:memory:` engine (via `StaticPool` so the same
  in-memory DB is visible across connections within one test), rather than
  sharing any file-backed database. `test_payment.py` and
  `test_billing_preview.py` additionally drive the real FastAPI router via
  `TestClient` and override only `get_db`/`get_current_user` — the router,
  service layer, and SQLAlchemy models all run unmocked.
- **Frontend:** Vitest + `@testing-library/react` + `@testing-library/user-event`,
  jsdom environment. API calls are stubbed via `vi.spyOn` on the
  `api/client.ts` module (for page/component tests) or via a global `fetch`
  mock installed in `vitest.setup.ts` (for `client.ts` itself — see the
  comment there on why the mock must exist *before* `client.ts` is
  imported).
- **Mocking policy:** the system under test is never mocked. `test_pdf_service.py`
  mocks only `app.utils.organization.load_profile`/`branding_url` (so a
  test doesn't depend on real branding assets on disk) and
  `app.utils.pdf_builder.html_to_pdf` itself in the escaping test (so the
  assertion is about the HTML string built, independent of whether
  Playwright/WeasyPrint are installed in the environment — see
  `TESTING.md` §5 for why that matters in practice).

## 2. How to run

```bash
cd backend
python -m pytest app/tests/test_pdf_service.py app/tests/test_billing_type_service.py \
  app/tests/test_invoice_dates.py app/tests/test_detached_session_regression.py \
  app/tests/test_payment.py app/tests/test_billing_preview.py app/tests/test_audit_log.py -v

cd ../frontend
npm test
```

Current status: **54 passed** (backend, the files above), **14 passed**
(frontend), 0 failed.

---

## 3. `test_payment.py` (11 tests) — payment lifecycle

**Context this suite exists for:** `app/api/payment.py` implements a
complete payment lifecycle (manual entry; gateway-style
initiate→processing→success/failure; correction) with row locking and
overpayment guards — but its router was never mounted in `main.py`, so
none of it was reachable over HTTP and it had zero test coverage. Both are
fixed as of this pass (see `TESTING.md` §1and `SECURITY_TESTING.md` §3).

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_payment_routes_are_mounted_on_the_real_app` | Import the real `main.app` and check its OpenAPI schema | `/api/payments/{project_id}/invoices/{invoice_id}/payments[/manual\|/{payment_id}/success]` are real registered routes — regression lock for the router-mount bug |
| `test_full_payment_marks_invoice_paid_and_attributes_audit_to_caller` | Manual payment for the exact balance due | `200`; invoice `payment_status` becomes `PAID`; the `PAYMENT_RECORDED_MANUAL` audit row's `user_id` is the caller's real id, not `"system"` |
| `test_partial_payment_marks_invoice_partially_paid` | Manual payment for less than the balance | `payment_status` becomes `PARTIALLY_PAID` |
| `test_overpayment_is_rejected` | Manual payment amount exceeds outstanding balance | `400`, invoice untouched |
| `test_payment_against_draft_invoice_is_rejected` | Invoice is `DRAFT`, not `ISSUED` | `400` — payments only apply to issued invoices |
| `test_payment_against_unknown_invoice_is_404` | Nonexistent `invoice_id` | `404` |
| `test_role_without_finance_or_admin_is_forbidden` | Caller has role `Developer` | `403` |
| `test_initiate_then_success_updates_invoice_and_attributes_audit` | Full gateway lifecycle: initiate → processing → success | Each transition returns the new status; final invoice `payment_status == PAID`; `PAYMENT_SUCCESS` audit row attributes the real caller |
| `test_success_cannot_follow_failed` | Mark a payment `FAILED`, then try to mark it `SUCCESS` | `400` — invalid state transition |
| `test_correcting_a_success_payment_recomputes_invoice_status` | Correct a `SUCCESS` payment's amount downward | Invoice `payment_status` recomputes from `PAID` to `PARTIALLY_PAID`; `PAYMENT_CORRECTION` audit row attributes the real caller |
| `test_correction_exceeding_balance_is_rejected` | Corrected amount would exceed `total_payable` | `400` |

**Why the audit-attribution assertions matter:** before this pass, every
one of `payment.py`'s 6 handlers called its service function without
`user_id=`, so every payment audit entry — who recorded a payment, who
corrected one — said `"system"` regardless of who was actually logged in.
For a financial audit trail, that's the whole point of the log; these
tests pin the fix (`user_id=user.id` on every call) so a future refactor
can't silently drop it again.

---

## 4. `test_billing_preview.py` (7 tests) — N+1 regression coverage

**Context:** `GET /api/projects/{project_id}/billing-preview`
(`app/api/projects.py`) used to run two extra `SELECT`s per candidate task
(one checking for an `ISSUED` invoice item, one for a `DRAFT` one) inside
its task loop. It was rewritten to batch-fetch every billed/draft
`(milestone_id, task_key)` pair once, into an in-memory set, and to
prebuild a classification-by-id lookup instead of querying per match.
These tests pin the *observable behavior* (which tasks are included or
excluded) so that optimization can never silently change what a project
can be billed for.

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_unbilled_tasks_are_all_returned` | A milestone with 2 unbilled tasks | Both appear in the preview |
| `test_task_already_on_issued_invoice_is_excluded` | One task already has an `ISSUED` invoice item | That task is excluded; the other unbilled task still appears |
| `test_task_already_on_draft_invoice_is_excluded` | One task already has a `DRAFT` invoice item | Same exclusion — drafts reserve a task's billing slot too, to prevent double-billing across two draft invoices |
| `test_task_on_cancelled_invoice_is_not_excluded` | The only invoice referencing a task is `CANCELLED` | Task **is** included — a cancelled invoice doesn't permanently hold a task's billing slot |
| `test_milestone_with_all_tasks_billed_is_omitted_entirely` | Every task on a milestone is already billed | The milestone itself is omitted from the response, not returned with an empty `tasks: []` |
| `test_unknown_project_is_404` | Nonexistent `project_id` | `404` |
| `test_project_without_milestones_returns_empty` | Project exists but has no `PENDING`/`PARTIALLY_BILLED` milestones | `{"milestones": []}`, no error |

---

## 5. `test_pdf_service.py` (15 tests) — invoice PDF generation

**Module under test:** `app/services/pdf_service.py` — amount-in-words
conversion, invoice-item grouping for the template, and HTML generation
from an `Invoice` ORM object.

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_amount_in_words_whole_numbers` *(parametrized)* | Several whole-rupee amounts | Correct Indian-numbering-system words (e.g. "One Lakh") |
| `test_amount_in_words_with_paise` | An amount with a paise component | Paise rendered correctly in words |
| `test_amount_in_words_accepts_decimal` | `Decimal` input (not `float`) | Same correct result — no float-rounding drift |
| `test_group_items_groups_by_milestone` | Multiple invoice items sharing a `milestone_id` | Grouped under that milestone in the template data |
| `test_group_items_component_vs_custom` | Items with a `component_id` vs. neither | Correctly bucketed as component vs. custom line items |
| `test_group_items_requirement_subgrouping` | Milestone items with different `requirement_name`s | Sub-grouped by requirement within the milestone |
| `test_group_items_empty_list` | No items | Returns an empty grouping, doesn't raise |
| `test_generate_invoice_pdf_escapes_all_user_content` | Every user/DB-sourced string field (`client_name`, `invoice_terms`, `bank_name`, item description, tax type, etc.) set to `'<script>alert(1)</script>"><img src=x onerror=alert(2)>'` | The raw payload never appears in the generated HTML (`<script>alert(1)</script>` and the `<img ... onerror=...>` tag are both absent); the escaped form (`&lt;script&gt;`) is present, proving the content came through rather than being silently dropped |
| `test_generate_invoice_pdf_raises_for_unknown_invoice` | Nonexistent invoice id | Raises `ValueError`, not an unhandled DB error |

**Design note — asserting structural safety, not string absence:** the
correct assertion for the escaping test is "no real tag/attribute is
formed" (`"<img src=x onerror=..." not in html`), not "the word `alert`
never appears anywhere" — `html.escape()` neutralizes the angle brackets
that matter for breaking out of a text node, but the escaped text still
*contains* those words as harmless literal text. A plain substring-absence
assertion would be a false requirement with no corresponding real
vulnerability.

---

## 6. `test_billing_type_service.py` (9 tests) — billing model inference

**Module under test:** the service that infers whether a project bills by
Milestone, Component, or Custom, and derives a human-readable delivery-unit
label (e.g. "Sprint", "Milestone").

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_milestone_units_take_priority` | Both milestone units and commercial components present | Milestone billing type wins |
| `test_component_only_when_no_billing_units` | Only commercial components, no milestone units | Component billing type |
| `test_custom_when_neither_units_nor_components` | Neither present | Custom billing type |
| `test_all_codes_have_descriptions` | Every defined billing-type code | Each has a non-empty human-readable description |
| `test_delivery_label_inferred_when_units_share_first_word` | Unit names like "Sprint 1", "Sprint 2" | Delivery label inferred as "Sprint" |
| `test_delivery_label_falls_back_when_units_disagree` | Unit names with no shared first word | Falls back to the generic default label |
| `test_delivery_label_falls_back_for_short_first_word` | A shared first word too short to be meaningful | Falls back to the default rather than a 1-2 character label |
| `test_delivery_label_untouched_for_non_milestone_types` | Component/Custom billing types | Label logic doesn't apply — untouched |
| `test_delivery_label_default_when_no_units` | No units at all | Default label |

---

## 7. `test_invoice_dates.py` (8 tests) — payment-terms date parsing

**Module under test:** the free-text `payment_terms` (e.g. `"Net 30"`) →
`due_date` parser.

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_invoice_date_is_always_now` | Any input | `invoice_date` is set to the current time, not user-suppliable |
| `test_net_30_parsed_correctly` | `"Net 30"` | Due date is 30 days after invoice date |
| `test_net_without_space_and_case_insensitive` | `"net30"`, `"NET 30"` | Parsed identically to `"Net 30"` |
| `test_net_with_dash` | `"Net-30"` | Parsed correctly |
| `test_none_falls_back_to_default` | `payment_terms=None` | Falls back to the default term length |
| `test_empty_string_falls_back_to_default` | `payment_terms=""` | Same fallback |
| `test_unrecognized_terms_fall_back_to_default` | An arbitrary unparseable string | Same fallback — never raises on bad input |
| `test_due_date_is_strictly_after_invoice_date` | Any valid term | `due_date > invoice_date`, always |

---

## 8. `test_detached_session_regression.py` (2 tests) — lazy-load after session close

**Context:** a real production bug — `app/api/system.py`'s
`get_analytics()` and `app/services/client_service.py`'s
`list_derived_clients()` both closed their DB session immediately after
querying `Estimation` rows, then accessed `est.client` (a lazy-loaded
relationship) afterward, raising `sqlalchemy.orm.exc.DetachedInstanceError`
the moment there was a real row to iterate. This class of bug is invisible
against an empty test database (an empty list never touches the lazy
attribute) — exactly how it slipped past testing originally.

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_analytics_does_not_raise_on_detached_client_access` | Seed one real `Estimation` with a `Client`, call `get_analytics()` after closing the session | Does not raise `DetachedInstanceError` |
| `test_list_derived_clients_does_not_raise_on_detached_client_access` | Same seeding, call `list_derived_clients()` | Does not raise |

---

## 9. `test_audit_log.py` (2 tests) — bootstrap-admin / system actors

See `SECURITY_TESTING.md` §4 for the authorization context this test file
exists alongside (the `bootstrap-admin` fallback identity). In scope here:
the pure persistence-layer proof that non-UUID actor strings can be
written and queried at all, now that `AuditLog.user_id` has no foreign key.

| Test | Scenario | Expected behavior |
|---|---|---|
| `test_audit_log_supports_bootstrap_admin_and_system_ids` | Insert `AuditLog` rows with `user_id` of `"bootstrap-admin"`, `"system"`, `None`, and an arbitrary UUID string | All 4 persist and are queryable — no FK violation |
| `test_update_estimation_client_as_bootstrap_admin` | `PATCH /api/estimations/{id}/client` authenticated as the synthetic `bootstrap-admin` user (no real `User` row exists) | `200`; an `AuditLog` row is written with `user_id == "bootstrap-admin"` |

---

## 10. Frontend — Vitest suite (14 tests)

### 10.1 `src/api/client.payments.test.ts` (3 tests)

Regression coverage for the exact bug class just fixed on the backend:
pins the literal URLs `recordPayment`/`recordManualPayment`/
`listInvoicePayments` call, so a future path/prefix mismatch between
frontend and backend shows up as a failing test here instead of a silent
404 in production.

| Test | Verifies |
|---|---|
| `recordPayment posts to /api/payments/{projectId}/invoices/{invoiceId}/payments` | Exact URL + `POST` method |
| `recordManualPayment posts to the /manual sub-path` | Exact URL, method, and JSON body shape |
| `listInvoicePayments GETs the same collection path recordPayment posts to` | Same base path, `GET` |

### 10.2 `src/pages/NewInvoiceV2.test.tsx` (7 tests)

Regression coverage for the bug fixed alongside this page's loading-state
work: `milestoneReqs` used to be built from the *project summary* response
instead of the *billing-preview* response (the two were fetched
sequentially before this pass's `Promise.all` fix), which only happened to
produce plausible-looking output because both response shapes had a
`.milestones` array.

| Test | Verifies |
|---|---|
| `shows a loading state before both API calls resolve` | Loading skeleton renders, then clears |
| `builds requirement groups from the billing-preview response, grouped and summed correctly` | Requirement grouping/sums come from `getBillingPreview`'s response, not `getProjectSummary`'s |
| `defaults every requirement to checked and totals the full billing-preview amount` | Initial "Selected: ₹—" total matches the sum of all tasks |
| `"Deselect All" on a milestone removes its requirements from the running total` | Running total drops to ₹0 |
| `"Select All" restores every requirement after a Deselect All` | Running total restored |
| `unchecking a single requirement checkbox updates the running total` | Per-requirement toggle updates the sum correctly |
| `surfaces the error message when either API call fails, instead of hanging on loading` | `Promise.all` rejection is caught; the page doesn't render a stale/partial view |

### 10.3 `src/components/RecordPaymentModal.test.tsx` (4 tests)

Client-side guard tests for the payment-amount field — the backend
(`payment_service.record_manual_payment`) rejects an amount exceeding the
balance due with a `400`; these confirm the UI disables submission before
that round trip, for a clear inline message instead of a generic API
error.

| Test | Verifies |
|---|---|
| `pre-fills the amount field with the full balance due` | Default amount = `invoice.balance_due` |
| `disables submit while no payment method is selected` | Submit button `disabled` with no method chosen |
| `rejects (disables submit for) an amount greater than the balance due` | Over-balance amount → submit disabled, inline error shown |
| `submits recordManualPayment with the entered amount when the form is valid` | Correct payload (`amount`, `payment_method`) passed through on submit |
