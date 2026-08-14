# Software Requirements Specification (SRS)
## Pixous Estimation & Invoicing Platform — Version 1.0

**Document status:** Baseline for shipped V1 functionality
**Prepared for:** Pixous Technologies Pvt Ltd
**Date:** 2026-08-14

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements for Version 1 of the Pixous Estimation & Invoicing Platform. It describes the system **as built**, so that it can serve as (a) a reference for QA sign-off, (b) an onboarding reference for new engineers, and (c) a baseline against which V2 scope can be planned.

### 1.2 Product Overview
The platform is an internal tool for Pixous Technologies that automates two related workflows for a software services business:

1. **Estimation Maker** — ingests a client's requirement document (PDF, DOCX, plain text, or a URL), uses an AI pipeline to analyze scope and generate a cost/timeline estimate, and produces client-ready Quotation, Business Requirements Document (BRD), and Software Requirements Specification (SRS) documents.
2. **Invoice Maker** — generates a branded, GST-compliant tax invoice either from a completed estimation or from manually entered line items, tracks its payment status, and exports it as a PDF.

The system is single-tenant (one company profile), India-specific (GST/INR throughout), and intended for internal staff use only — there is no public-facing or client-facing account access in V1.

### 1.3 Intended Audience
Engineering team, QA, and Pixous management evaluating the tool for internal rollout.

### 1.4 Scope of Version 1
V1 covers: authenticated internal users, AI-assisted estimation generation, manual (non-AI) estimation and invoicing, document editing and PDF export, company branding/letterhead, a fixed developer rate card, and a basic analytics dashboard. Any authenticated internal user has equal access to all of the above in V1 — there is no role-based access control (see §2.2 and §7). Multi-currency, client self-service portals, payment gateway integration, and horizontal scaling of the job pipeline are explicitly **out of scope** for V1 (see §7).

---

## 2. Overall Description

### 2.1 System Architecture
- **Backend:** Python / FastAPI, serving both the REST API and the built frontend as a single deployable unit.
- **Frontend:** React 18 + TypeScript (Vite), React Router, Tailwind CSS.
- **Database:** SQLAlchemy ORM; SQLite for local/dev, PostgreSQL in production.
- **AI pipeline:** LangGraph-orchestrated multi-agent workflow using Mistral (OCR), Groq (LLM analysis/estimation/document generation), and Google Gemini (web-grounded market pricing research).
- **Document export:** WeasyPrint / Playwright (headless Chromium) for Markdown/HTML → PDF conversion.

### 2.2 User Roles
In V1, all internal user accounts have equal, undifferentiated access — any authenticated user can create, edit, and delete estimations and invoices, manage organization/branding, and update the rate card. There is no role-based access control (RBAC) in V1; it is a candidate for future development if the business later needs to separate duties (e.g. restricting financial edits to a Finance function, or organization/branding changes to an Admin function) — see §7.

There is no self-service sign-up; accounts are provisioned by an operator via a CLI script.

### 2.3 Operating Environment
Single company/tenant deployment. Currency fixed to INR; tax model fixed to Indian GST. Designed to run as one backend process (see §6.3 for the scaling constraint this implies).

---

## 3. Functional Requirements

### 3.1 Authentication & Session Management
- FR-1.1: Users shall log in with a username and password; the system returns a signed, time-limited session token (24-hour expiry).
- FR-1.2: The system shall lock out an IP+username pair for 15 minutes after 5 failed login attempts within a 15-minute window.
- FR-1.3: The system shall reject expired or tampered tokens on every authenticated request.
- FR-1.4: An unauthenticated endpoint shall expose company branding (logo/name) so the login screen can display it pre-authentication.
- FR-1.5: A machine-to-machine API key (`X-API-Key`) mode shall be supported for automated testing tools, resolving to a designated internal identity with the same permissions as a logged-in user.
- FR-1.6: Passwords shall be stored hashed (bcrypt); any legacy plaintext password shall be transparently upgraded to a hash on next successful login.

### 3.2 Authorization
- FR-2.1: Any authenticated internal user shall be able to perform any action in the system (create/edit/delete estimations and invoices, manage organization/branding, update the rate card) — V1 has no role-based access control.
- FR-2.2: Estimation and invoice mutations shall be recorded in an audit log (actor, action, before/after values, timestamp), regardless of the acting user's account.

### 3.3 Document Ingestion (Estimation Maker)
- FR-3.1: The system shall accept a requirement source as an uploaded file (PDF, DOCX), a URL, or pasted plain text.
- FR-3.2: PDF sources shall be routed through OCR to extract text and structure; DOCX sources shall be parsed directly.
- FR-3.3: URL ingestion shall reject non-HTTP(S) schemes and any address resolving to a private, loopback, link-local, or otherwise reserved IP range, shall not follow redirects, and shall cap downloaded content at 50MB (SSRF hardening).

### 3.4 AI-Assisted Analysis & Estimation
- FR-4.1: The system shall extract a structured project analysis from ingested text: client name, project name/description/type, technology stack, a granular list of requirements (each with category, priority, complexity, estimated hours, required role, dependencies), assumptions, risks, and explicit out-of-scope items.
- FR-4.2: The system shall produce a cost and timeline estimate that maps requirement effort to roles and hours, priced against the current developer rate card.
- FR-4.3: The system shall research current market pricing (infrastructure, licensing, third-party services) via web-grounded search and incorporate it into the estimate in INR.
- FR-4.4: The system shall optionally generate a full BRD (business goals, stakeholders, scope) and/or SRS (technical architecture, data schema, API surface, functional flows, non-functional requirements, and an entity-relationship diagram) alongside the Quotation, at the user's discretion per job.
- FR-4.5: The system shall assemble a client-facing Quotation document deterministically from the analysis, estimation, and market-research outputs (no LLM call at this stage, to guarantee consistent totals).

### 3.5 Job Lifecycle
- FR-5.1: Submitting a source shall start an asynchronous job and return a job identifier immediately.
- FR-5.2: The system shall expose job progress (current pipeline stage, log, and final result) via a polling endpoint.
- FR-5.3: The system shall additionally expose a synchronous long-poll endpoint (bounded timeout) for load-testing tools that require a single blocking call.
- FR-5.4: A running job shall be cancellable by the user who owns the session.
- FR-5.5: On successful completion, the system shall persist the client, estimation, and generated documents (Quotation/BRD/SRS) to the database.

### 3.6 Estimation Management
- FR-6.1: Users shall be able to list all estimations, grouped by client, with status, totals, and linked invoice metadata.
- FR-6.2: Users shall be able to view the full underlying pipeline data for an estimation.
- FR-6.3: Users shall be able to create a **manual estimation** (client name, project name, and a list of line items with description/quantity/rate) without invoking the AI pipeline, for cases where no requirement document exists.
- FR-6.4: Any authenticated user shall be able to edit an estimation's project name, timeline, and grand total; concurrent edits shall be protected by optimistic locking (a version conflict shall be rejected rather than silently overwritten).
- FR-6.5: Any authenticated user shall be able to delete an estimation; deletion shall be a soft delete (recoverable/auditable), not a physical row removal.
- FR-6.6: Estimation status shall progress through Draft → Processing → Completed/Failed → Approved/Sent → Archived.

### 3.7 Document Editing & Export
- FR-7.1: Users shall be able to view and edit the Markdown content of a Quotation, BRD, or SRS document; each edit shall be preserved as a new version rather than overwriting history.
- FR-7.2: Users shall be able to download any Quotation/BRD/SRS/Invoice as a PDF, matching the on-screen rendering (including diagrams where the export format supports it).
- FR-7.3: Any invoice HTML content submitted for edit shall be sanitized to remove executable script content before storage.

### 3.8 Invoice Management (Invoice Maker)
- FR-8.1: Users shall be able to generate an invoice from a completed estimation, specifying tax percentage and payment due period.
- FR-8.2: Users shall be able to create an invoice directly from manually entered line items, independent of any estimation.
- FR-8.3: Each invoice shall compute subtotal, GST amount, discount, and grand total, and shall carry a unique sequential invoice number.
- FR-8.4: Any authenticated user shall be able to update invoice status (Draft, Sent, Paid, Partially Paid, Overdue, Cancelled); marking an invoice Paid shall auto-stamp the payment date.
- FR-8.5: Any authenticated user shall be able to directly patch invoice financial fields (amounts, status, payment date); such changes shall be audit-logged.
- FR-8.6: Any authenticated user shall be able to hard-delete an invoice; if no invoices remain for its parent estimation, the estimation's status shall revert accordingly.
- FR-8.7: Users shall be able to list invoice history and view/download any invoice as branded PDF.

### 3.9 Organization Profile & Branding
- FR-9.1: The system shall maintain a single company profile: name, tagline, address, contact details, GSTIN, registration number, certifications, bank account details, and authorized signatory.
- FR-9.2: Any authenticated user shall be able to update the company profile, with server-side validation of email, phone, and GSTIN formats.
- FR-9.3: Any authenticated user shall be able to upload/replace/remove branding assets (logo, signature, seal), limited to 5MB, with the server verifying that uploaded image content genuinely matches its declared file type.
- FR-9.4: Any authenticated user shall be able to retroactively re-apply the current branding to all previously generated invoices and documents in one action.
- FR-9.5: Branding assets shall be durably stored (backed up in the database) so they survive a redeploy of the application filesystem.

### 3.10 Rate Card
- FR-10.1: The system shall maintain a fixed list of developer roles and their hourly billing rates, used by every estimation.
- FR-10.2: Any authenticated user shall be able to add, update, or deactivate a role's rate; rate changes shall be versioned (old rates retained with an end date, not deleted) so historical estimations remain traceable to the rate in effect at the time.

### 3.11 Analytics
- FR-11.1: The system shall present an aggregate dashboard: total estimations/invoices, counts for the current day/month, revenue paid vs. pending, invoice status breakdown, and recent activity.

### 3.12 Clients
- FR-12.1: The system shall derive a client list from estimation history and allow browsing estimations grouped by client.

---

## 4. Non-Functional Requirements

### 4.1 Security
- NFR-1.1: All API endpoints except login, token validation, and public branding shall require authentication.
- NFR-1.2: Session tokens shall be cryptographically signed and shall be rejected if the embedded identity does not correspond to a real, currently valid account.
- NFR-1.3: All destructive or financially significant mutations (estimation edit/delete, invoice edit/delete, organization/rate-card changes) shall be captured in an audit trail, though in V1 they are not further restricted by role — any authenticated user may perform them.
- NFR-1.4: User-supplied HTML (invoice content) shall never be persisted or rendered with executable script content.
- NFR-1.5: Outbound URL ingestion shall be hardened against SSRF (see FR-3.3).
- NFR-1.6: Uploaded images shall be validated against spoofed file extensions.

### 4.2 Reliability & Data Integrity
- NFR-2.1: Concurrent edits to the same estimation shall not silently overwrite one another (optimistic locking).
- NFR-2.2: Deleted estimations shall be recoverable in principle (soft delete) rather than immediately and irreversibly purged.
- NFR-2.3: Document edits (Quotation/BRD/SRS) shall retain version history.

### 4.3 Usability
- NFR-3.1: Long-running estimation jobs shall show step-by-step progress so a user can track pipeline stage (ingestion → OCR → analysis → estimation → web research → BRD → SRS → quotation).
- NFR-3.2: A user shall be able to navigate away from an in-progress job and return to see its current state.

### 4.4 Performance & Scalability (documented constraints, not guaranteed SLAs in V1)
- NFR-4.1: Job state is held in-process (in-memory), not in a persistent queue; this is an accepted V1 limitation (see §7).
- NFR-4.2: Login rate-limiting is tracked per process; multi-process deployment proportionally raises the effective attempt ceiling (accepted V1 limitation).

### 4.5 Compliance / Localization
- NFR-5.1: All monetary values shall be presented in INR with GST-compliant invoice fields (GSTIN, tax breakdown).

---

## 5. External Interfaces

### 5.1 API
A REST API under `/api`, consumed by the bundled React frontend and by internal QA tooling (Postman/JMeter) via the `X-API-Key` mechanism. Endpoint groups: Auth, Jobs, Estimations/Documents, Invoices, Organization, Rate Card, Analytics, Config/Health.

### 5.2 Third-Party AI Services
- **Mistral** — OCR of PDF requirement documents.
- **Groq** — LLM analysis, estimation, and BRD/SRS text generation.
- **Google Gemini** — web-grounded market pricing research.

The system shall support multiple API keys per provider with automatic rotation/failover on rate-limit errors.

### 5.3 User Interface
A single-page React application with two primary workspaces reachable from a landing page: **Estimation Maker** and **Invoice Maker**, each with its own dashboard, creation flow, history list, detail view, and shared organization settings page.

---

## 6. Data Requirements

Core persisted entities: `User`, `OrganizationProfile`, `RateCard`, `Client`, `Estimation`, `Document` (versioned Quotation/BRD/SRS content), `Invoice`, `AuditLog`, `BrandingAsset`. Estimation, Invoice, and Document numbers are generated as year-scoped sequential identifiers (e.g. `EST-2026-000123`, `INV-2026-000045`).

---

## 7. Known V1 Limitations / Explicit Non-Goals

These are documented so they are not mistaken for defects during QA, and so they can be scoped deliberately for V2:

1. **No role-based access control (RBAC).** Any authenticated user has full access to every action in the system, including organization/branding, rate card, and estimation/invoice edits and deletes. This is a candidate for future development — e.g. an Admin/Finance/PM/Developer role split — if the business later needs separation of duties; it is not required for V1.
3. **No horizontal scaling of the AI pipeline.** Job state lives in an in-process dictionary; it does not survive a server restart and is not shared across multiple worker processes.
4. **No account deactivation flag.** A user account can be deleted but not temporarily disabled.
5. **No server-side token revocation.** A leaked session token remains valid until its 24-hour natural expiry.
6. **No self-service client portal.** All access is internal-staff-only; clients receive documents as exported PDFs, not through an account.
7. **No payment gateway integration.** Invoice "Paid" status is recorded manually, not verified against a payment processor.
8. **Single currency (INR) and single tax regime (Indian GST).** No multi-currency or multi-region support.
9. **No formal schema migration framework.** Schema changes are additive (`ALTER TABLE ADD COLUMN`) rather than managed by a tool such as Alembic; this is flagged in the codebase as a pre-scale-up gap.
10. **`Attachment` data model exists but has no wired endpoints** — treated as reserved for a future release, not a V1 feature.
11. **Two diagnostic/debug endpoints remain in the API surface** (an organization-profile debug dump and a PDF smoke-test route) and should be removed or explicitly access-controlled before external exposure.

---

## 8. Glossary

| Term | Meaning |
|---|---|
| BRD | Business Requirements Document |
| SRS | Software Requirements Specification (the generated client document, distinct from this file) |
| GST | Goods and Services Tax (India) |
| GSTIN | GST Identification Number |
| OCR | Optical Character Recognition |
| SSRF | Server-Side Request Forgery |
| Optimistic locking | Concurrency control via a version counter, rejecting stale writes instead of blocking readers |
