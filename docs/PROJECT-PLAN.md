# Project plan

The single planning document for this project. Phases are numbered in the
order they should be built. Supersedes the previous per-phase files.

Last reviewed: 2026-11-07 · 342 automated tests passing across monorepo (`331` frontend + `7` agents fleet + `4` ingress caddy).

- [1. Status](#1-status)
- [2. Unified Architecture & Renumbering](#2-unified-architecture--renumbering)
- [3. Risk register](#3-risk-register)
- [4. Phase 4 — AI Foundation (Substrate)](#4-phase-4--ai-foundation)
- [5. Phase 5 — Core Platform Foundations & Backend Switching](#5-phase-5--core-platform-foundations--backend-switching)
- [6. Phase 6 — Clinical Intelligence, Patient Safety & Immediate Security](#6-phase-6--clinical-intelligence-patient-safety--immediate-security)
- [7. Phase 7 — SlainteFHIR Micro-EHR, Real-Time Push & Write-Back](#7-phase-7--slaintefhir-micro-ehr-real-time-push--write-back)
- [8. Phase 8 — Enterprise AI, MCP Tool Orchestration & Clinical Assistance](#8-phase-8--enterprise-ai-mcp-tool-orchestration--clinical-assistance)
- [9. Phase 9 — Enterprise Security, Cryptographic Storage & Regulatory Governance](#9-phase-9--enterprise-security-cryptographic-storage--regulatory-governance)
- [10. Phase 10 — Patient Portal & Secure Subject Access](#10-phase-10--patient-portal--secure-subject-access)
- [11. Phase 11 — Multi-Vertical Domain Specialization & 11-Agent Fleet](#11-phase-11--multi-vertical-domain-specialization)
- [12. Phase 12 — Turnkey Appliance Packaging & Commercial Launch (`SlaintePages`)](#12-phase-12--turnkey-appliance-packaging--commercial-launch)
- [13. Phase 12.5 — Monorepo Consolidation & Agentic Plumbing (Option A)](#125-phase-125--monorepo-consolidation--agentic-plumbing-option-a)
- [14. Phase 12.6 — Single Unified Architecture & 16-Agent Fleet Expansion](#126-phase-126--single-unified-architecture--16-agent-fleet-expansion)
- [15. Phase 12.7 — Manual Human Review & UI/UX Audit across Dashboard & Public Site](#127-phase-127--manual-human-review--uiux-audit-across-dashboard--public-site)
- [16. Phase 12.8 — Agent Interaction with UI Specification](#128-phase-128--agent-interaction-with-ui-specification)
- [17. Phase 12.9 — Public Site Expansion & Enterprise Visuals](#129-phase-129--public-site-expansion--enterprise-visuals)
- [18. Phase 13 — Production Hardening, Multi-Tenant PostgreSQL 16 RLS Migration with Free-Tier Cloud Strategy & Pilot Launch](#13-phase-13--production-hardening-multi-tenant-postgresql-16-rls-migration-with-free-tier-cloud-strategy--pilot-launch-active-next-phase)
- [19. Reference & Enterprise AI Strategy](#15-reference--enterprise-ai-strategy)
- [20. Gaps and innovations](#16-gaps-and-innovations)
- [21. Open decisions](#17-open-decisions)

---

## 1. Status

| Phases | Scope | State |
|---|---|---|
| 1–3 | Hardening, auth, audit log, FHIR client, charts | **Done**, merged |
| 4 | AI foundation (substrate, prompts, context, `ai_exchange`) | **Done**, merged |
| 5 | Foundations, bedside intake modal, multi-backend switcher | **Done**, merged |
| 6 | Clinical intelligence, NEWS2, sign-off, allergy gate, core security | **Done**, merged |
| 7 | SlainteFHIR micro-EHR (8082), Slainte-Auditor red-team verifier, GMS dedup | **Done**, merged |
| 8 | AI Model Selector (`/settings/ai`), `.env` key integration, Bedside AI Briefing | **Done**, merged |
| 11 + 9 Lite | Sidebar "Agents" Hub (11 Agents + Settings + Embedded Copilots), GDPR/CVE/Audit Agents, & "Sign in as..." 8 Specialty Verticals | **Done**, merged |
| 11.5 | 11-Agent Enterprise Pack & 7 Killer Features (SMART-on-FHIR v2 + OIDC SSO, `Agent 10` Ambient Voice Scribe, HL7v2 + HSE PCRS, Granular Clinical RBAC + Break-the-Glass, SIEM + Compliance Certificate, `Agent 11` HIPE Revenue Coding + Postgres RLS, 3-Tier `SlainteRx-Guard`) | **Done**, verified live |
| 12 | `SlaintePages` Public Startup & Product Platform (`SlainteTech AI Security Labs`, Next.js 15 + MUI v6 + SSG static site, 33 static pages, 1,200 verified links) | **Done**, verified live |
| 12.5 | Monorepo Consolidation & Agentic Plumbing (Option A: Root `agents/` package, domain blueprints, Next.js site import, Caddy 2 ingress TLS reverse proxy) | **Done**, merged & verified live |
| 13 | Production Hardening, Multi-Tenant Postgres RLS Cutover & Live Pilot Launch | **Active Next Priority** |
| 10 | Standalone Mobile/Laptop Patient App (Shared `SlainteFHIR` Backend) | **Deferred (Post-Funding)** |

The dashboard (`SlainteDash`) operates as the primary clinical interface of the
unified **Slainte-Engine Appliance**, backed by `SlainteScan` (FastMCP 8081),
`SlainteFHIR` (Micro-EHR 8082), `Slainte-Auditor` (Autonomous Red-Team FHIR Verifier),
`SlainteEngine` (Autonomous Ingestion 3000), and `Slainte-Ingress` (Caddy 2 Automated TLS Reverse Proxy :80/:443).

## 2. Unified Architecture & Renumbering

Phases are aligned with the master `slainte-engine/roadmap.md` specification:

1. **Appliance Monorepo Realignment:** The dashboard is no longer a standalone viewer
   querying public HAPI; it is the clinical interface for a multi-container clinical appliance.
2. **Deterministic Clinical Tools First:** FastMCP calculations (NEWS2, allergy contraindications,
   MTS triage) must be validated deterministically before connecting unconstrained LLMs.
3. **Dual-Track AI Strategy (Local Sovereign + Enterprise Cloud):** Local-first on-premise
   inference (Ollama/Qwen) by default, with first-class enterprise cloud options
   (Azure OpenAI Ireland, OpenAI Enterprise, Google Cloud Vertex AI) for hospital trusts with
   existing BAAs.

| New Phase | Target Milestone | Status |
|---|---|---|
| **1–4** | Core Platform Foundations, Charts, AI Substrate | **Completed** |
| **5** | Bedside Intake Modal, MTS Queue, Settings Backend Switcher | **Completed** |
| **6** | Clinical Intelligence, NEWS2, Provenance Sign-Off, Core Security | **Completed** |
| **7** | SlainteFHIR Micro-EHR (Port 8082), Slainte-Auditor Red-Team Verifier, GMS Dedup | **Completed** |
| **8** | Unified AI Model Selector (`/settings/ai`), `.env` Key Integration, Bedside Briefing | **Completed** |
| **9 Lite + 11** | Sidebar "Agents" Hub (11 Agents + Settings + Embedded Copilots) & "Sign in as..." 8 Specialty Verticals | **Completed** |
| **11.5** | 11-Agent Enterprise Pack & 7 Killer Features (`SlainteScribe-Voice`, `SlainteRev-Coding`, SMART v2, HL7v2, Clinical RBAC, SIEM, 3-Tier Rx-Guard) | **Completed** |
| **12** | `SlaintePages` Public Startup & Product Platform (`SlainteTech AI Security Labs`, Next.js 15 + MUI v6 + SSG static site, 33 static pages, 1,200 verified links) | **Completed** |
| **12.5** | Monorepo Consolidation & Agentic Plumbing (Option A: Root `agents/` Package, Domain Blueprints, Next.js Site Import, Caddy 2 Ingress TLS) | **Completed** |
| **13** | Production Hardening, Multi-Tenant Postgres RLS Cutover & Live Pilot Launch | **Active Next** |
| **10** | Standalone Mobile/Laptop Patient App (Shared `SlainteFHIR` Backend) | **Deferred (Post-Funding)** |

## 3. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Unencrypted SQLite stores on appliance disk | High | High | Transparent AES-256 via SQLCipher in Phase 9 |
| R2 | **Patient portal leaks another patient's record** | Medium | **Severe** | Resource-scoped authorization, not role-based. See [Phase 10](#10-phase-10--patient-portal--secure-subject-access) |
| R3 | CSP silently breaks charts or SSE connections | High | Medium | Verify with browser subagent tests, asserting chart rendering and SSE stream reception |
| R4 | Enterprise LLM hallucinating medical advice | Medium | **Severe** | Zero-hallucination FastMCP tool bridge. Scoring & allergy checks executed deterministically, not by model weights |
| R5 | Real PHI transmitted without signed BAA | Low | **Severe** | `AI_ALLOW_REAL_PHI` code gate enforces BAA / synthetic-only constraint |
| R6 | Write conflicts between simultaneous clinicians | Medium | High | `If-Match` with optimistic concurrency (treat 409 & 412 as conflict) |
| R7 | Background polling degrades mobile tablet battery | High | Medium | Event-driven Server-Sent Events (`hx-ext="sse"`) replaces polling loops |
| R8 | Scope sprawl across 12 phases | High | Medium | Thin vertical slices; single-command turnkey appliance deployment (`./run.sh`) |
| R9 | Model pricing or rate-limit cliff on long records | Low | Low | Byte-identical prompt caching and strict `AI_CONTEXT_TOKEN_CEILING` curation |

---

## 4. Phase 4 — AI foundation

**Status: done.** Nothing in the app sends patient data to a model yet — this
phase built the substrate that Phase 9's buttons will sit on.

**Why:** the provider layer existed but nothing consumed it. Building context
assembly, prompting, the de-identification pass and the exchange trail *before*
any user-facing feature means the safety properties are structural rather than
retrofitted onto a shipped button.

### Tasks

- [x] `ai/context.py` — `build_patient_context(fhir, patient_id)` via
      `GET /Patient/{id}/$everything`, falling back to `fhir.get_many()`
- [x] Tag every fact with its source `[ResourceType/id]` so citations are checkable
- [x] **Send the whole record by default.** Measured: a dense record is ~19K
      tokens against a 1,050,000 window. Curate only above a ceiling well under
      `AI_INPUT_TOKEN_CLIFF` (272K), never truncating allergies, and state in
      the prompt what was omitted
- [x] `build_section_context(fhir, patient_id, section)` for the narrow buttons
- [x] `ai/prompts.py` — versioned system prompts; context block **byte-identical**
      across turns so prompt caching hits (cached input is 10x cheaper)
- [x] De-identification pass, config-gated: strips name, address, contact.
      On by default the moment `FHIR_SERVER_URL` is not a demo server
- [x] `ai_exchange` table, append-only triggers like `audit_log`:

```sql
CREATE TABLE ai_exchange (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,              -- username
    patient_ref TEXT NOT NULL,        -- pseudonymised
    feature TEXT NOT NULL,            -- 'chat' | 'summary' | 'section'
    model TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,        -- sha256 of assembled prompt
    prompt_version TEXT,              -- added: which wording produced this
    deidentified INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER,
    output_tokens INTEGER,
    response TEXT NOT NULL            -- full text, for later review
);
```

- [x] Tests with a `FakeProvider`; no network in CI

### What was built

| File | Contents |
|---|---|
| `ai/context.py` | `fetch_record` → `RecordFetch`; `build_patient_context`, `build_section_context` → `PatientContext`; curation, de-identification, `estimate_tokens` |
| `ai/prompts.py` | `PROMPT_VERSION`, shared safety rules + three features, `build_messages`, `cacheable_prefix`, `prompt_hash` |
| `db.py` | `ai_exchange` table with append-only triggers, `write_ai_exchange`, `read_ai_exchange` |
| `config.py` | `is_demo_fhir_host`, `deidentify_enabled`, `AI_DEIDENTIFY`, `AI_CONTEXT_TOKEN_CEILING` |

Tests: `test_ai_context.py`, `test_ai_prompts.py`, `test_ai_exchange.py` — 83
new, 286 total, offline. Verified against live HAPI: `$everything` resolves, a
real record renders, and two live fetches produce byte-identical text.

### Decisions taken while building

1. **Curation measures the rendered block, not the clinical lines.** Budgeting
   lines alone ignored section headings and the notes block, overshooting the
   ceiling by ~40% at small ceilings — an error pointing the unsafe way, since
   the ceiling exists to stay clear of the repricing cliff. It now renders,
   measures, and trims the measured overshoot, up to four passes.
2. **An unreadable section is never rendered as empty.** The fallback path
   marks failed reads `unavailable` and the block lists them under *Sections
   that could NOT be read*, with an instruction not to infer absence. This is
   the codebase's failure-vs-empty rule applied where it matters most: a
   clinician seeing a blank panel knows something may be missing; a model told
   a section is empty will state the patient has no allergies.
3. **`AI_DEIDENTIFY` is minimisation, not anonymisation.** Resource id tags stay
   so citations resolve, which means anyone with server access can re-identify.
   Documented as such in SECURITY.md rather than implied to be Safe Harbor.
   `AI_ALLOW_REAL_PHI` remains the control that decides anything.
4. **Free-text `note` elements are not rendered at all** — the one place a
   clinician's prose can name a third party, with no reliable way to strip it.
5. **Sort ties break on resource id.** Without it, two same-dated resources can
   swap places between calls, silently costing a prompt-cache hit every turn.
6. **`openai` pinned to `==2.53.0`** — it was the one unpinned dependency.

### Notes

`ai_exchange` is the record that lets someone investigate a bad answer after
the fact — non-negotiable before this touches a real patient. Cost is not a
constraint: ~$0.002/call, ~$2 per thousand. Reasoning effort, not context size,
is the cost lever (reasoning tokens bill at the output rate); default `low`.

**Carried into [Phase 9](#9-phase-9--ai-clinical-features):** routes must call
`context_options(app.config)` rather than re-deriving the de-identification
rule; every response must be written to `ai_exchange` before it reaches the
screen; and `PatientContext.complete` should be surfaced in the UI so a
clinician can see when an answer was formed from a partial record.

---

## 5. Phase 5 — Core Platform Foundations & Backend Switching

**Status: Done (Merged & Shipped).**

**Why:** The dashboard must be able to operate seamlessly both as a local standalone
appliance viewer and against live regional hospital FHIR endpoints without requiring
recompilation or container restarts.

### Tasks Completed
- [x] **Collapsible Manchester Triage System (MTS) Queue:** Grouped triage categories
      (Cat 1 Immediate down to Cat 5 Non-Urgent) with automatic category pill rendering.
- [x] **Bedside Intake Modal:** Multimodal clinical intake supporting CSV, PDF, and clinical
      document ingestion with live parsing into HL7 FHIR R4 resources.
- [x] **Scaled Clinical Cohorts:** 18-patient and 8-case synthetic Irish clinical cohorts
      seeded with Irish GMS identifiers (`urn:oid:1.3.6.1.4.1.54392.5.2690.42.80`), LOINC vitals,
      and SNOMED CT chief complaints.
- [x] **Top-Right Settings Dropdown Menu:** Unified header dropdown next to Logout, replacing
      the single "AI Settings" button, providing access to Data Settings, AI Settings, App Settings,
      Security & Audit, and User Profile.
- [x] **In-App Dynamic Backend Switcher (`/settings/data`):**
      - Instant switching between `SlainteFHIR Micro-EHR (8082)`, `Local Filesystem Store`,
        `Public HAPI Demo`, and `Custom URL`.
      - Live connection telemetry card with real-time HTMX health probe and latency counter.
      - Backed by `DynamicFhirProxy` in `app.py` for zero-container-restart switching.
- [x] **Remote Triage Parity:** Implemented `get_triage_queue()` on `FhirClient` so remote
      servers like SlainteFHIR render identical MTS queues and vital summaries.

---

## 6. Phase 6 — Clinical Intelligence, Patient Safety & Immediate Security

**Status: Completed.**

**Why:** While MTS establishes intake urgency, clinical safety requires tracking physiological
deterioration over time (NEWS2), guaranteeing clinician accountability (electronic sign-off
with standard FHIR `Provenance`), and preventing medication catastrophes before any prescription
is recorded. Concurrently, immediate security defects identified in `SECURITY.md` (per-worker
rate limits, `LOG_HASH_SALT` enforcement, CSP/SRI) must be remediated.

### Completed Tasks
- [x] **6.1 NEWS2 / MEWS Early Warning Scoring:**
  - Implemented RCP NEWS2 score calculation tool in FastMCP (`calculate_news2_score`) on `slainte-scan-mcp:8081`.
  - Dynamic NEWS2 score pill badge with color coding (Low, Low-Medium, Medium, High Risk) in the Live Triage Queue.
  - 24-hour vital deterioration trajectory SVG sparkline with telemetry gradient area fill, threshold guidelines (≥7 High, ≥5 Med), and parameter breakdown grid (RR, SpO2, O2, SBP, HR, CVPU, Temp).
- [x] **6.2 Clinician Electronic Sign-Off & FHIR Provenance:**
  - "Validate & Sign" action modal on the patient card capturing Practitioner ID, GMC/IMC registration number, clinical role, and legal verification.
  - Generates immutable HL7 FHIR `Provenance` resource with target references, ISO-8601 recorded timestamp, practitioner OID (`2.16.840.1.113883.2.17.1.5`), and SHA-256 cryptographic state hash of the clinical bundle.
  - Supported and indexed across both `LocalFhirStore` and `SlainteFHIR` micro-EHR.
- [x] **6.3 Deterministic Drug-Allergy Safety Gate:**
  - FastMCP tool `check_drug_allergy_contraindications` pre-loaded with cross-reactivity matrices (Penicillins ➔ Amoxicillin/Cephalosporins; NSAIDs ➔ Aspirin/Ibuprofen; Sulfa drugs).
  - Live HTMX validation trigger (`/fhir/validate-safety`) on medication and allergy fields in the intake modal with critical CDS interception banner.
- [x] **SPA Shell Direct Navigation & Layout Polish:**
  - Fixed direct browser URL navigation across `/fhir/Patient/<id>`, `/fhir/Triage`, `/fhir/Patients`, etc., auto-wrapping in `index.html` SPA shell.
  - Resolved inactive `.htmx-indicator` spacing (hidden with `display: none !important;`) eliminating 80px white gaps above clinical tables.
- [x] **6.4 Core Security Remediation:**
  - Fixed per-worker rate limiting: eliminated `memory://` drift under multi-worker gunicorn by backing Flask-Limiter with centralized `SqliteStorage` (`rate_limit_storage.py`).
  - Required `LOG_HASH_SALT` outside debug/testing mode to prevent pseudonymised ID correlation drift across workers (`validate_salt`).
  - Added Subresource Integrity (SRI) `sha384-` hashes to all static CDN assets (Bootstrap 5.3.0, HTMX 2.0.4, Chart.js 4.5.1, FontAwesome 6.6.0).
  - Implemented Content Security Policy (CSP) headers protecting against XSS while permitting Chart.js canvas rendering, Google Fonts, and HTMX SSE streams.
  - Implemented progressive account lockout: 15-minute lockout after 5 consecutive failed authentications with persistent database counters and audit logs.

---

## 7. Phase 7 — Rust Core Service (SlainteCore / SlainteFHIR), Real-Time Push & Write-Back

**Status: Active Architecture Evolution & Implementation.**

**Why:** Disk file juggling (`bundle_*.json`) is a fragile prototype. While the Python FastAPI micro-EHR prototype verified standard R4 endpoints, transaction bundles, and CapabilityStatements, scaling to real-time hospital appliances requires replacing the Python FastAPI service with a dedicated **Rust** core server (`SlainteCore` / `SlainteFHIR`).

### Why Rust for the FHIR Server Fits This Architecture

Pairing Python on the edges (SlainteDash for HTMX triage, SlainteScan for FastMCP extraction, and SlainteEngine for containerized orchestration) with a dedicated Rust FHIR & Search server is a battle-tested systems pattern.

```
+-------------------------------------------------------------------+
|                           Slainte Stack                           |
+-------------------------------------------------------------------+
|  Python Front-Ends & Agents:                                      |
|    - SlainteDash   (Flask/HTMX UI - Sub-50ms triage bay)          |
|    - SlainteScan   (FastMCP SSE / Pydantic deterministic OCR)     |
|    - SlainteEngine (Container dropzone / orchestration loop)      |
+----------------------------------+--------------------------------+
                                   | Internal HTTP / IPC (Port 8082)
                                   v
+-------------------------------------------------------------------+
|  Rust Core Service: SlainteCore / SlainteFHIR                     |
|    - Axum HTTP Server (JSON FHIR R4 Bundle Validation)            |
|    - Serde + Tantivy (Embedded full-text & semantic index)        |
|    - Embedded RocksDB / SQLite (Zero-allocation local storage)     |
+-------------------------------------------------------------------+
```

#### 1. Zero Garbage Collection for Massive FHIR Payloads
FHIR R4 Bundles are deeply nested JSON documents packed with arrays of resources (`Patient`, `Encounter`, `Observation`, `Condition`, `MedicationRequest`). In Python, de-serializing an 8MB multi-patient hospital transfer bundle spikes memory allocations and triggers GIL/GC pauses. In Rust, `serde_json` parses payloads with zero-copy deserialization directly into typed structs in single-digit milliseconds.

#### 2. Embedded Native Indexing (The XERJ Pattern)
Instead of running a separate heavy Java JVM container (like Elasticsearch) or wrestling with complex Postgres JSONB queries across large clinical corpora, you can embed an engine like **Tantivy** (a pure-Rust Lucene alternative) directly inside the Axum binary:
- Patient demographics, free-text clinical notes, and SNOMED CT medication tags get indexed in-memory as they are committed.
- Sub-millisecond fuzzy search and exact token retrieval are exposed natively without external infrastructure dependencies.

#### 3. Air-Gapped Single Static Binary
One of the biggest selling points of SlainteEngine is 100% on-premise, zero-trust deployment with no cloud exfiltration. A Rust FHIR server compiles to a single, statically linked binary (`musl` target) running inside a minimal scratch or distroless container image (under 30MB), requiring virtually zero host dependencies.

### Workspace & Project Structure
To maintain clean separation while sharing typed schemas and search indexes, a Rust workspace is built alongside the existing Python repositories:

```plaintext
slainte-fhir-service/
├── Cargo.toml                     # Workspace root
├── crates/
│   ├── fhir-models/               # Strongly-typed FHIR R4 structs & Pydantic parity
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── patient.rs
│   │       ├── bundle.rs
│   │       └── observation.rs
│   ├── fhir-index/                # Embedded Tantivy / search layer (XERJ-style retrieval)
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── schema.rs          # Tokenizers for SNOMED, NHS/PPS IDs, patient text
│   │       └── searcher.rs
│   └── fhir-server/               # Axum HTTP API & Ingestion endpoints
│       ├── Cargo.toml
│       └── src/
│           ├── main.rs
│           └── routes/
│               ├── ingest.rs      # Accepts raw JSON bundles from SlainteScan
│               └── search.rs      # Instant patient / medication / encounter queries
```

### Minimal Prototype (Axum + Serde)

```toml
# Cargo.toml
[workspace]
members = [
    "crates/fhir-models",
    "crates/fhir-index",
    "crates/fhir-server",
]
resolver = "2"
```

```rust
// crates/fhir-server/src/main.rs
use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::Json,
    routing::{get, post},
    Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::net::TcpListener;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FhirBundle {
    pub resource_type: String, // "Bundle"
    pub id: Option<String>,
    pub entry: Vec<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
pub struct SearchParams {
    pub q: String,
}

struct AppState {
    // Shared embedded Tantivy search index & storage pool
}

#[tokio::main]
async fn main() {
    let state = Arc::new(AppState {});

    let app = Router::new()
        .route("/health", get(|| async { "OK" }))
        .route("/fhir/Bundle", post(ingest_bundle))
        .route("/fhir/search", get(search_clinical_records))
        .with_state(state);

    let listener = TcpListener::bind("0.0.0.0:8082").await.unwrap();
    println!("SlainteFHIR Rust server listening on http://0.0.0.0:8082");
    axum::serve(listener, app).await.unwrap();
}

async fn ingest_bundle(
    State(_state): State<Arc<AppState>>,
    Json(payload): Json<FhirBundle>,
) -> (StatusCode, Json<serde_json::Value>) {
    if payload.resource_type != "Bundle" {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"error": "Expected resourceType 'Bundle'"})),
        );
    }

    // Ingest into embedded index and local store deterministically
    (
        StatusCode::CREATED,
        Json(serde_json::json!({
            "status": "ingested",
            "entries_count": payload.entry.len()
        })),
    )
}

async fn search_clinical_records(
    State(_state): State<Arc<AppState>>,
    Query(params): Query<SearchParams>,
) -> (StatusCode, Json<serde_json::Value>) {
    // Instant lookup across patient names, NHS/GMS numbers, SNOMED concepts
    (
        StatusCode::OK,
        Json(serde_json::json!({
            "query": params.q,
            "hits": []
        })),
    )
}
```

### How This Plugs Back into Your Stack
- **SlainteScan (Python / FastMCP):** Strips PHI, runs deterministic validation gates, and pushes completed FHIR R4 bundles directly over `http://localhost:8082/fhir/Bundle`.
- **SlainteCore (Rust):** Deserializes the bundle in microseconds, writes to an append-only WAL/SQLite store, and updates the Tantivy search index.
- **SlainteDash (HTMX / Flask):** When a triage nurse searches by patient name, PPS/NHS ID, or presenting complaint, HTMX fires a background search to the Rust API (`/fhir/search?q=...`), returning pre-rendered search rows in under 5 milliseconds.

### 7.2 Shared SQLite WAL Datastore (`fhir_store.db`)
- High-concurrency SQLite database running in **WAL mode** with `busy_timeout = 5000`.
- SQLite `JSON1` extension: FHIR resources stored as structured JSON with indexed generated
  columns for `patient_id`, `gms_number`, `mts_category`, `news2_score`, and `created_at`.
- Enables sub-millisecond query performance over 100,000+ patient records with concurrent reads
  and writes.

### 7.3 Real-Time Event Bus & HTMX Server-Sent Events (`hx-ext="sse"`)
- Zero-polling push architecture: Flask and SlainteFHIR expose `/events/stream`.
- Publishes real-time events: `patient-triaged`, `vital-alert`, `telemetry-updated`.
- Dashboard elements declare `hx-ext="sse" sse-connect="/events/stream" sse-swap="patient-triaged"`,
  updating the live triage queue instantly with zero battery drain on clinical tablets.

### 7.4 Bi-Directional Write-Back & Optimistic Concurrency
- Extend `FhirClient` with write support: `post(resource_type, body)` and `put(resource_type, id, body, if_match=None)`.
- Reuses existing timeout, retry, and pseudonymised logging pathways.
- Version-conflict handling: treats both **HTTP 409 and 412** as optimistic concurrency conflicts.
- Append-only `resource_edit_log` recording actor, resource type, ID, action, and before/after JSON.

---

## 8. Phase 8 — Enterprise AI, MCP Tool Orchestration & Clinical Assistance

**Status: Planned (Next Priority).**

**Why:** The AI substrate built in Phase 4 (`ai/context.py`, `ai/prompts.py`, `ai_exchange` table)
has proven that patient records can be serialized deterministically with `[ResourceType/id]`
source citations. Phase 8 connects this engine to both local sovereign models and enterprise
cloud providers, bridges LLMs directly to FastMCP tools, and surfaces interactive clinical
assistance directly in the UI.

### 8.1 The Dual-Track AI Strategy: Sovereign Local vs. Enterprise Cloud

Healthcare systems operate under strict regulatory and commercial constraints. In Ireland and
the EU, hospitals (HSE, NHS Trusts, private clinic groups) fall into two categories:
1. **Sovereign Local-First (Default):** Air-gapped on-premise inference using Ollama
   (`qwen2.5-coder:32b`, `llama3.3:70b`) or vLLM running on local hospital hardware. Zero bytes
   of clinical context ever leave the hospital perimeter.
2. **Enterprise Cloud AI Option:** Many health authorities have enterprise tenant agreements
   with cloud hyperscalers:
   - **Microsoft Azure OpenAI Service:** Hosted in Dublin (`westeurope`), with signed EU Data
     Boundary BAAs and GDPR Data Protection Impact Assessments (DPIAs).
   - **Google Cloud Vertex AI (MedLM / Gemini 1.5 Pro):** Running under Irish healthcare
     innovation partnerships.
   - **OpenAI Enterprise API:** With contractual Zero Data Retention (ZDR) guarantees.
   - **Anthropic Claude 3.5 Sonnet:** Via AWS Bedrock or GCP Vertex in EU regions.

**Implementation in SlainteDash:**
- The `/settings/ai` configuration view allows administrators to select their active provider:
  - `Local Ollama (host.docker.internal:11434)`
  - `OpenAI Enterprise (api.openai.com)`
  - `Microsoft Azure OpenAI (custom endpoint + deployment name)`
  - `Google Cloud Vertex AI`
- The `AI_ALLOW_REAL_PHI` compliance gate strictly blocks any real patient record from leaving
  the appliance unless an enterprise BAA is cryptographically certified in configuration.

### 8.2 Driving FastMCP Tools via OpenAI / Enterprise Tool Calling

Unconstrained LLMs hallucinate clinical calculations. Slainte-Engine resolves this by using
the LLM strictly as a conversational orchestrator while delegating all clinical logic to
**SlainteScan (FastMCP)**:

```
[Clinician Prompt / Question]
          │
          ▼
   ┌──────────────┐
   │ Enterprise   │ (Receives patient context + FastMCP Tool Schemas)
   │ LLM (OpenAI) │
   └──────┬───────┘
          │ Tool Call: calculate_news2_score(vitals) OR check_drug_allergy(...)
          ▼
   ┌──────────────┐
   │ SlainteScan  │ ➔ Executes 100% Deterministic Clinical Code on Port 8081
   │ FastMCP Tool │
   └──────┬───────┘
          │ Deterministic Result: {score: 18, risk: "High", alert: "Penicillin Anaphylaxis"}
          ▼
   ┌──────────────┐
   │ Grounded     │ ➔ Synthesizes response with [ResourceType/id] citations
   │ Verification │    and zero mathematical or pharmacological hallucinations.
   └──────────────┘
```

- **MCP Tool Bridge:** Exposes `slainte-scan-mcp` tools (`calculate_news2_score`,
  `check_drug_allergy_contraindications`, `ingest_handwritten_note`) as standard OpenAI tool/function
  definitions.
- When a clinician asks "What is this patient's deterioration trajectory and can we start Co-Amoxiclav?",
  OpenAI does not guess: it executes the MCP tools, incorporates the deterministic output,
  and explains the findings with exact source citations.

### 8.3 Completing the Dashboard Clinical AI Features
- **Bedside Patient Briefing (`POST /ai/summarise/<patient_id>`):**
  - Clinical card button triggering a structured summary in under 200 words.
  - Leads with immediate management alerts (allergies, acute vitals, active problems).
  - Streams directly into a sliding drawer via HTMX SSE (`hx-ext="sse"`).
- **Allergy & Medication Cross-Check (`POST /ai/crosscheck/<patient_id>`):**
  - Dedicated safety check comparing current `MedicationRequest` against `AllergyIntolerance`.
  - Backed by FastMCP deterministic cross-reactivity tables.
- **Docked Multi-Turn Clinical Chat (`POST /ai/chat/<patient_id>`):**
  - Global collapsible dock on the right of the dashboard.
  - Multi-turn conversation maintaining byte-identical prefix caching for optimal token cost.
- **Section Explainers:**
  - Targeted buttons on Lab Results ("Interpret Abnormal Panels") and Vital Trends ("Assess Trajectory").
- **Audit & Governance:**
  - Every AI interaction logged to `ai_exchange` with prompt hash, version, token usage, and response text.
  - New administrative interface at `/admin/ai_exchanges` for clinical safety audits.

---

## 9. Phase 9 Lite — Governance, Privacy & Vulnerability Agents (Folded into Phase 11 Agent Fleet)

**Status: Completed (Merged & Live in `/agents` and `/settings/security`).**

**Why:** Rather than introducing fragile C-level SQLCipher or external OIDC dependencies before commercial funding, governance and security verification are delivered as three dedicated autonomous agents inside the `/agents` Command Center:

### Completed Tasks
- [x] **Agent 03 — Software Supply-Chain & App Vulnerability Agent (`SlainteShield-CVE`):** Audits pinned dependencies (`requirements.txt`), verifies active HTTP security headers (`Content-Security-Policy`, `SRI sha384-`, `SameSite`, `HttpOnly`), and inspects multi-worker `SqliteStorage` rate-limiting posture.
- [x] **Agent 04 — GDPR & Clinical Data Privacy Agent (`SlainteGov-GDPR`):** Enforces EU GDPR Art. 9 & Irish HIQA data minimisation: audits `AI_DEIDENTIFY` PII stripping, checks the `AI_ALLOW_REAL_PHI` BAA/DPIA gate, and verifies salted SHA-256 subject pseudonymisation (`LOG_HASH_SALT`).
- [x] **Agent 05 — Immutable Clinical & AI Audit Trail Agent (`SlainteGov-Audit` — Closes Gaps `G1` & `G10`):** Verifies SQLite append-only triggers on `audit_log` & `ai_exchange`, provides the in-app `ai_exchange` & `audit_log` reader in `/settings/security`, checks `Provenance` SHA-256 bundle signatures across all 7 verticals, and provides a one-click signed JSON audit snapshot export (`/agents/audit/snapshot`).

---

## 10. Phase 10 — Standalone Patient Self-Service Mobile/Laptop App

**Status: Deferred (Separate Future Project Sharing the `SlainteFHIR` Backend).**

**Why:** Packaging a consumer-facing responsive mobile/laptop application is a standalone product track that will consume the `SlainteFHIR` (`:8082`) backend API once funded.

---

## 11. Phase 11 — The 11-Agent Command Center (`/agents`) & "Sign in as..." 8 Multi-Vertical Workspaces

**Status: Completed (Merged & Live).**

**Why:** Unifies the entire stack around **SlainteTech AI Security Labs'** core differentiator: **11 specialized Security, Governance, and Clinical Agents** managed from a sidebar **"Agents"** Command Center (`/agents`) with per-agent settings, while keeping clinical copilots embedded directly on patient and intake screens and adapting the interface to **8 "Sign in as..." verticals**.

### 11.1 How the 11 Autonomous Agents Work (OpenHands + FastMCP + Deterministic Engines)
1. **OpenHands SDK + Hybrid Adversarial Agents (`Agents 01, 02 & 06`):**
   - **Agent 01 (`SlainteShield-BOLA`) & Agent 02 (`SlainteShield-FHIR`):** Run inside `slainte-auditor` (`auditor_runner.py`). They combine deterministic RFC 1918 guardrails, `CompartmentDefinition/Patient` pruning, and live Victim/Attacker HTTP BOLA probing (`SharedAuditMemory` $\mathcal{M}$) with live LLM synthesis (`Ollama` on `:11434` or `OpenAI` via `.env`) and OASIS SARIF v2.1.0 reporting.
   - **Agent 06 (`SlainteEngine-Ingest`):** Runs in the `slainte-openhands` container (`openhands/agent_runner.py`), polling `/workspace/data/raw` and invoking FastMCP tools on `slainte-mcp:8081` to transform messy CSVs, PDFs, and notes into GMS-deduplicated FHIR R4 bundles.
2. **Deterministic Security, GDPR & Audit Agents (`Agents 03, 04 & 05` in `agents_hub.py`):**
   - Execute 100% deterministic code inspections against `requirements.txt`, `base.html`/`index.html` SRI hashes, `sqlite_master` append-only triggers, `ai_exchange` records, and `Provenance` SHA-256 signatures.
3. **Embedded Bedside Clinical Copilots (`Agents 07, 08 & 09`):**
   - **Agent 07 (`SlainteScribe-Brief`):** Embedded on every Patient Details page (`POST /ai/summarise/<id>`), calling the configured local Ollama or OpenAI model with `[ResourceType/id]` citations and logging to `ai_exchange`.
   - **Agent 08 (`SlainteRx-Guard`) & Agent 09 (`SlainteDx-Triage`):** Embedded on Patient Details (`POST /ai/crosscheck/<id>`), the Intake Modal, and the Live Triage Queue, executing 100% deterministic FastMCP rules (`check_drug_allergy_contraindications`, `calculate_mts_category`, `calculate_news2_score`).
4. **Enterprise Clinical & Financial Intelligence Agents (`Agents 10 & 11`):**
   - **Agent 10 (`SlainteScribe-Voice`):** Ambient clinical dictation listening post, converting clinician spoken dialogue into structured SOAP and FHIR DocumentReference notes.
   - **Agent 11 (`SlainteRev-Coding`):** Automated HIPE / ICD-10-AM / DRG clinical reimbursement coder, cross-referencing discharge summaries with encounter diagnoses and HSE PCRS rules.

### 11.2 "Sign in as..." 8 Specialty Verticals & Mobile Responsive Dock
- [x] **Vertical 1: Emergency Department (`SlainteED`):** MTS Cat 1–5 live triage queue, 24h NEWS2 sparklines, acute intake dropzone.
- [x] **Vertical 2: General Practice (`SlainteGP`):** SOAP clinical notes, HSE Chronic Disease Management (CDM) tracking, repeat prescribing safety gate.
- [x] **Vertical 3: Dental Surgery (`SlainteDent`):** Pre-op allergy/anticoagulant clearance gate, interactive 32-tooth FDI Odontogram & 6-sextant BPE summary, dental referral ingestion.
- [x] **Vertical 4: Community & Hospital Pharmacy (`SlaintePharm`):** Prescription dispensing queue, deterministic Beta-Lactam/NSAID cross-reactivity gate, Irish GMS reimbursement validation.
- [x] **Vertical 5: Pre-Hospital Ambulance / EMS (`SlainteEMS`):** High-contrast field ePCR intake, rapid ambulance MTS/NEWS2 scoring, hospital ETA pre-alert handoff.
- [x] **Vertical 6: Elite Sports Club (`SlainteSport`):** Squad readiness & physiological load telemetry, concussion return-to-play `Provenance` clearance, BOLA-verified athlete privacy.
- [x] **Vertical 7: Astronaut Health Monitoring (`SlainteAstro`):** 100% air-gapped deep-space bio-telemetry running local 3B Ollama models + deterministic FastMCP diagnostics.
- [x] **Vertical 8: Psychiatry & Mental Health (`SlaintePsych`):** Mental State Examination (MSE), PHQ-9 & GAD-7 psychometric rating scale scoring, and acute suicide risk stratification.

---

## 12. Phase 12 — `SlaintePages` Public Startup & Product Platform (`SlainteTech AI Security Labs`)

**Status: Completed & Verified Live (Port 3001 & `slainte-engine/public-site/`).**

- [x] **Next.js 15 App Router & Material-UI (MUI v6) Architecture**: Built modern SSG (Static Site Generator) public platform with TypeScript, responsive theme, and zero build-step export.
- [x] **Static Compilation Pipeline (`next.config.mjs`)**: Configured static bundle export emitting zero-dependency HTML/CSS/JS directly into `website/public-site/` ready for automated Caddy ingress (`/site*`).
- [x] **Core Company & Regulatory Pages (All 100% WCAG 2.2 AA Compliant)**:
  - [x] **Homepage (`/`)**: Platform hero, live architecture layer diagram, compliance ticker, interactive vertical showcase, and real-world clinical workflow photography.
  - [x] **Company & Leadership (`/about`)**: Sovereign clinical mission, engineering philosophy, and governance principles.
  - [x] **Contact & Pilot Inquiries (`/contact`)**: Interactive inquiry form with hospital tier selection and clinical role routing.
  - [x] **Security, NIS2 & AI Act Governance (`/security-compliance`)**: Detailed EU NIS2 Article 21 and EU AI Act conformity assessment breakdown.
  - [x] **Enterprise Pricing & Appliance Tiers (`/pricing`)**: Transparent appliance subscription, SMART sidecar licensing, and sovereign air-gap tiers.
  - [x] **Institutional Investors & Commercial Model (`/investors`)**: ROI brief, TAM analysis, and clinical governance moat.
  - [x] **Platform Documentation & Architecture (`/docs`, `/platform`)**: FastMCP safety kernel specifications, SMART-on-FHIR v2 specs, and FHIR R4 schema bindings.
  - [x] **Machine-Readable AI Manifest (`/public/llms.txt`)**: Structured knowledge summary for generative AI crawlers and LLM indexing.
- [x] **Dedicated Canonical Landing Pages for Autonomous Agents (`/health-tech-agents/*`)**:
  - [x] Generated canonical SEO landing pages sharing reusable `AgentCanonicalTemplate.tsx` with bespoke FastMCP schematics, deterministic capability triplets, cross-vertical use case breaks, and HL7 FHIR R4 technical spec tables.
- [x] **8 Dedicated Specialty Vertical Pages (`/verticals/*`)**:
  - [x] Built dedicated landing pages for Emergency (`emergency-departments`), General Practice (`general-practice`), Psychiatry (`psychiatry`), Dentistry (`dentistry`), Pharmacy (`pharmacy`), EMS (`ambulance-ems`), Sports Medicine (`sports-medicine`), and Astronaut Health (`astronaut-health`), each with verified color palettes, SVG graphics, and mobile/tablet callouts.
- [x] **Verified Link Integrity**: Verified over 1,200 internal routes with zero broken links, zero 404 errors, and full SEO metadata / JSON-LD schemas.

---

## 12.5. Phase 12.5 — Monorepo Consolidation & Agentic Plumbing (Option A)

**Status: Completed, Merged & 100% Verified Live.**

**Why:** Having fragmented separate repositories (`Patient-Dashboard-htmx-python-fhir`, `slainte-auditor`, `SlaintePages`, `OCR2FHIR`) created severe maintenance overhead, brittle container bind-mount hacks (`./slainte-auditor:/workspace/slainte-auditor`), cross-repo path drift, and high LLM token consumption due to a monolithic 4,043-line `app.py`. Consolidating into **Option A: The Unified Monorepo** inside `slainte-engine` creates a single source of truth, unlocks atomic version control, and establishes a clean modular architecture.

### What Was Delivered (All 3 Steps Completed & Verified)

1. **Step 1: Root `agents/` Python Package & Fleet Re-alignment (`commit cbe2bf5`):**
   - Built root `agents/` package:
     - `agents/base.py`: Core `BaseAgent` abstract class and `AgentExecutionResult` dataclass.
     - `agents/registry.py`: Central 11-agent metadata registry, `get_agent_instance()`, `get_all_agents_with_settings()`, and settings persistence.
     - `agents/governance/`: Dedicated modules for Governance Fleet (`01-BOLA`, `02-FHIR`, `03-CVE`, `04-GDPR`, `05-AUDIT`).
     - `agents/clinical/`: Dedicated modules for Clinical Fleet (`06-INGEST`, `07-BRIEF`, `08-RXGUARD`, `09-TRIAGE`, `10-SCRIBE`, `11-CODING`).
   - Linked `frontend/agents_hub.py` as a 100% backward-compatible proxy bridge re-exporting directly from `agents`.
   - Copied Next.js 15 source code into `slainte-engine/website/`.
   - Verified 338/338 passing tests; tested all 11 agents and 8 vertical cockpits live.

2. **Step 2: Modularize `frontend/app.py` into Domain Blueprints (`commit 7c14ecd`):**
   - Deconstructed monolithic 4,043-line `frontend/app.py` down to **512 clean lines**.
   - Created `frontend/blueprints/`:
     - `auth.py`: Authentication, registration, progressive lockout (15-min lockout after 5 attempts), and SIEM security alerts.
     - `patients.py`: Patient roster, search/filter, clinical detail views, vital trajectory sparklines, clinical writes, and bedside AI copilots.
     - `verticals.py`: 8 specialty cockpits (`emergency`, `general_practice`, `psychiatry`, `dental`, `pharmacy`, `ems`, `sports_medicine`, `aerospace_medicine`) and custom clinical write handlers.
     - `agents.py`: Master 11-agent hub view, individual agent dashboards (`GET /agents/<id>` and `POST /agents/<id>/run`), per-agent model settings, signed audit snapshot, and SARIF export.
     - `intake.py`: Manchester Triage Queue, dropzone telemetry, manual intake modal, and multimodal file upload (PDF/PNG/CSV).
     - `settings.py`: AI model selector (`/settings/ai`), multi-backend data switcher (`/settings/data`), app/security settings, and user administration (`/admin/users`).
     - `common.py`: Shared pseudonymized audit helper, search parsers, `VITAL_SIGN_CODES`, and bundle utilities.
     - `__init__.py`: `register_all_blueprints(app, csrf, limiter)`, global context processors, health probes (`/health`, `/health/ready`), and error handlers.
   - Retained explicit route endpoints (`endpoint='login'`, `endpoint='index'`) ensuring zero template or `url_for()` regressions.

3. **Step 3: Automated Ingress TLS & Single Entrypoint (`commit b18ddac`):**
   - Added `deploy/Caddyfile` with automated TLS (internal / Let's Encrypt), HSTS, and reverse proxying:
     - `/` -> `slainte-dashboard:8000` (HTMX + Flask) with WebSocket and SSE streaming upgrade.
     - `/fhir/r4*` -> `slainte-fhir:8082` (FHIR R4 Server).
     - `/mcp*` -> `slainte-mcp:8081` (SSE streaming flush).
     - `/site*` -> `/srv/website/public-site` (Static marketing, investor, and industry vertical pages).
   - Added `slainte-ingress` service to `docker-compose.yml` exposing ports `:80` and `:443`.
   - Integrated compiled static website export in `website/public-site/`.
   - Added automated test suite `tests/test_ingress_caddy.py` validating Caddy syntax and compose integration.
   - Verified 342/342 passing tests and verified all 11 agents and 8 vertical cockpits live.

---

## 12.6. Phase 12.6 — Single Unified Architecture & 16-Agent Fleet Expansion

**Status: Completed & 100% Passing (344/344 Tests).**

**Why:** Having fragmented execution runtimes (OpenHands container shell loops, separate `slainte-auditor` containers, and in-process Flask copilots) introduced unnecessary orchestration friction. Unifying all agents under a single `BaseAgent` abstraction with a typed `AgentExecutionResult` and a centralized CLI/runner eliminates bespoke container dependencies and allows any agent to run synchronously from the UI, as a background job, or programmatically via CLI.

### What Was Delivered:

1. **Unified Single-Architecture Engine (`agents/runner.py` & `agents/cli.py`):**
   - Consolidated agent execution into `run_agent(agent_id, context) -> AgentExecutionResult`.
   - Added operator CLI (`python -m agents [list|run|health|audit]`) supporting unified agent inspection and execution.
2. **Five New Agents Added to Registry & Catalog:**
   - **Agent 12: Clinic Onboarding & Migration Agent (`SlainteGov-Onboard`):** Introspects raw practice dumps, maps clinical variables to LOINC/SNOMED-CT via MCP, and compiles verified Irish Core FHIR R4 Bundles.
   - **Agent 13: Discharge & Transfer Coordinator (`SlainteCare-Transfer`):** Assesses physiological stability (NEWS2 <= 2), reconciles discharge medications against allergies, and drafts transfer summaries.
   - **Agent 14: Emergency Pre-Alert Agent (`SlainteEMS-Alert`):** Evaluates pre-hospital vitals to calculate Manchester Triage urgency and dispatch pre-arrival alerts with ETA to receiving Emergency Departments.
   - **Agent 15: Chronic Disease Surveillance Agent (`SlainteCare-CDM`):** Continuously audits diabetic and hypertensive panels for overdue surveillance markers (HbA1c > 12m, SBP >= 150 mmHg) for proactive GP intervention.
   - **Agent 16: EU NIS2 Directive & Continuous Compliance Auditor (`SlainteGov-NIS2`):** Continuously audits hospital operational controls against EU Directive 2022/2555 Article 21 technical safeguards.
3. **Automated Verification:**
   - 344/344 tests passing across the entire monorepo (`tests/test_agents_fleet.py` + `frontend/tests/`).

---

## 12.7. Phase 12.7 — Manual Human Review & UI/UX Audit across Dashboard & Public Site (Iteration 2)

**Status: Completed & Documented with 11 Verified Pixel-Perfect Live Patient Screenshots.**

**Why:** Elevating the user experience from an experimental prototype to a pristine, hospital-grade enterprise application requires rigorous heuristic review: eliminating visual clutter, ensuring consistent spacing and padding with native Bootstrap rhythm, implementing tactile button micro-interactions, guaranteeing smooth HTMX loading states, providing 100% data availability for all clinical records, and verifying full WCAG 2.2 AA accessibility.

### Heuristic Review & Quality Findings:

1. **Live Clinical Data Loading & Offline High-Availability Fallback:**
   - Patched `DynamicFhirProxy` in `frontend/app.py` with an automatic 200ms socket probe on port 8082. When running standalone without the container network, it automatically falls back to `LocalFhirStore` targeting `data/fhir_store/`.
   - Verified that all 34 synthetic patient bundles (`P0988`, `P101` Mary Walsh, `P102` Patrick Byrne, etc.) render immediately with real vitals, active medications, allergies, condition problem lists, and NEWS2 acuity scores.
2. **Classic Enterprise Bootstrap Aesthetic (2016 Medical Workstation Standard):**
   - Replaced playful rounded fonts (`Nunito`) with crisp native operating system UI fonts (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`).
   - Standardized cards and panels to a clean 4px border radius, 1px `#CBD5E1` clinical borders, `#F8FAFC` headers, and zero floaty glassmorphism or neon vibe-coding accents.
   - Standardized table cell padding, high-contrast `#0F172A` body typography, and flush alignment within cards.
3. **Button Micro-Interactions & Tactile Feedback:**
   - Upgraded `.btn` styles in `static/styles.css` with smooth cubic-bezier micro-transitions:
     - Hover state: `transform: translateY(-1px); box-shadow: 0 2px 4px rgba(15, 23, 42, 0.12);`
     - Active click state: `transform: translateY(0); box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.15);`
     - Accessible focus ring: `outline: 2px solid var(--tropical-primary); outline-offset: 1px;`
4. **Consistent Asynchronous HTMX Loading Feedback:**
   - Hardened `.htmx-indicator` and `.btn.htmx-request` styling to ensure immediate visual feedback on asynchronous operations (form submissions, agent runs, patient swaps). Buttons dim slightly (`opacity: 0.75; pointer-events: none;`) with inline spinners activated.
5. **De-Cluttering & Elimination of "Vibe-Coding" Jargon:**
   - Cleaned the top header bar: removed duplicate titles, unnecessary pill tags, and deprecated buttons.
   - Replaced colloquial or experimental terminology with crisp clinical nomenclature ("Vertical Workspace", "Irish Core FHIR R4", "Operational Status").
6. **WCAG 2.2 AA Accessibility & Bedside Contrast:**
   - Verified 4.5:1 text contrast for body typography (`#0F172A` on `#F1F5F9` / `#FFFFFF`) and 3:1 contrast for interactive controls and borders.
   - High-contrast clinical priority mode (`body.high-contrast-mode`) verified for bright sunlight and dimmed night-shift wards.
   - Coarse-pointer touch targets (`min-block-size: 44px`) verified for mobile tablet and ambulance ePCR use.
7. **Pixel-Perfect UI Screen Captures (With Live Clinical Cohort Data):**
   - Captured 11 high-resolution screenshots saved to `data/audit_reports/ui_screenshots/`:
     - `01_dashboard_login.png`: Login screen with rate-limiting notice and clinical security footer.
     - `02_patients_roster.png`: Clinical Patients table loaded with 15 active patients per page (`P0988`, `P101` Mary Walsh, `P102` Patrick Byrne), GMS numbers, and NEWS2 risk badges.
     - `03_patient_details_p101.png`: Patient Details chart for Mary Walsh (P101) with clinical banner, vitals panel, active medications, allergies, and problem list.
     - `04_agents_hub.png`: Master 16-agent directory with squad filters and fleet execution bar.
     - `05_agent_16_nis2.png`: Agent 16 dedicated Article 21 compliance and SIEM telemetry dashboard.
     - `06_agent_08_rxguard.png`: Agent 08 3-Tier pharmacology and renal safety dashboard evaluating real patient medications.
     - `07_triage_board.png`: Acute Manchester Triage board with patients populated across priority accordions.
     - `08_public_site_homepage.png`: Public marketing homepage with healthcare photography and agent fleet overview.
     - `09_public_site_agents_directory.png`: Public 16-agent solution directory.
     - `10_public_site_agent_nis2_landing.png`: Public canonical SEO landing page for Agent 16.
     - `11_public_site_vertical_emergency.png`: Public Emergency Department vertical landing page.
8. **Modernization Path for HTMX 4 & Bootstrap 6:**
   - Detailed comprehensive technical evaluation in `stopgap.md` Section 8 outlining breaking changes, DOM morphing (Idiomorph), strict CSP nonces without inline handlers, CSS `@layer`, container queries, and native HTML5 `<dialog>`.

---

## 12.8. Phase 12.8 — Agent Interaction with UI Specification

**Status: Fully Specified & Implemented.**

Every autonomous agent in the 16-agent fleet is cleanly integrated into the clinical and administrative user interface:

### 16-Agent UI Interaction Matrix:

| Agent # & ID | Name & Squad | User Interaction / Invocation Mechanism | Information Displayed to User | Presentation Format in UI |
|---|---|---|---|---|
| **01** `bola_redteam` | BOLA & Role-Boundary Red-Team (*SlainteShield*) | Click "Run Adversarial Probes" button on `/agents/bola_redteam` or run full fleet cycle from Agents Hub. | CompartmentDefinition surface pruning stats, active patient isolation checks, reflection vectors. | Interactive BOLA telemetry table, memory step log ($\mathcal{M}$), and status badge (PASS / FAIL). |
| **02** `fhir_conformance` | FHIR R4 Integrity & Terminology (*SlainteShield*) | Select patient bundle from dropdown on `/agents/fhir_conformance` or click "Download SARIF". | SNOMED-CT / LOINC / UCUM mapping checks, missing Irish GMS OID alerts, bundle validation outcomes. | Single-bundle resource inspector table with green/amber status pills and downloadable SARIF v2.1.0 report. |
| **03** `cve_vulnerability` | Supply-Chain & CVE Containment (*SlainteShield*) | Click "Audit Supply Chain" on `/agents/cve_vulnerability` or visit Security Settings (`/settings/security`). | Exact dependency version pins (`requirements.txt`), SRI sha384- asset verification, rate-limit storage health. | Three KPI metric cards, pinned package inventory table, and CSP header checklist. |
| **04** `gdpr_privacy` | GDPR Art. 9 & Clinical Privacy Gate (*SlainteGov*) | Select patient on `/agents/gdpr_privacy` to generate live de-identification preview, or toggle BAA gate in `/settings/ai`. | Side-by-side comparison of raw FHIR PHI vs. stripped pseudonymized LLM context, salted SHA-256 audit digest. | Side-by-side dual JSON sandbox viewer with redaction diff highlights and GDPR Article 9 gate badges. |
| **05** `immutable_audit` | GovAudit & Provenance Ledger (*SlainteGov*) | Click "Test Append-Only Trigger" on `/agents/immutable_audit` or click "Download Signed Snapshot". | Cryptographic SHA-256 integrity signatures, database tamper rejection proof, recent clinical audit events. | Tamper-proof verification card, live `audit_log` event stream, and downloadable signed JSON snapshot. |
| **06** `multimodal_ingest` | Multimodal Clinical Ingestion (*SlainteCare*) | Drag & drop file (PDF/PNG/CSV/HL7v2) into Intake Modal or dropzone on `/agents/multimodal_ingest`. | Extraction progress, OCR text fragments, mapped LOINC/SNOMED variables, generated FHIR R4 Bundle. | 5-stage pipeline progress indicator, raw dropzone file browser, and harmonized bundle preview drawer. |
| **07** `patient_summariser` | Cited Patient Summariser (*SlainteScribe-Brief*) | Click "Generate AI Bedside Briefing" on Patient Details (`POST /ai/summarise/<id>`) or interactive patient selector. | 3-bullet clinical handover summary with exact `[ResourceType/id]` bracketed citations and vital trends. | Prominent clinical briefing card at the top of the patient chart with copy button and audit trail tag. |
| **08** `medication_safety` | 3-Tier Rx-Guard Pharmacology (*SlainteCare*) | Triggered automatically when prescribing (`+ Prescribe`), dispensing in pharmacy, or running candidate drug tester. | Tier 1 Drug-Allergy cross-reactions, Tier 2 ISMP high-alert interactions, Tier 3 renal eGFR dosing contraindications. | Pre-flight modal blocker with severity banners, required override justification prompt, and cohort sweep table. |
| **09** `acuity_triage` | Dx-Triage & NEWS2 Acuity (*SlainteCare*) | Triggered automatically on recording vitals, submitting fast triage form, or adjusting physiological sliders. | Calculated Manchester Triage System Category (1–5), target time to clinician, RCP NEWS2 deterioration score. | Color-coded MTS priority badges (Red/Amber/Yellow/Green/Blue), 24h NEWS2 SVG sparkline, and triage accordion placement. |
| **10** `ambient_scribe` | Ambient Clinical Voice Scribe (*SlainteCare*) | Click "Start Ambient Scribe" on Patient Details or GP Workspace; speak via microphone or select Irish preset. | Structured SOAP clinical note, candidate diagnoses with ICD-10/SNOMED codes, draft medication orders. | Interactive 3-column draft review panel with "1-Click Approve & Commit to FHIR R4" persistence button. |
| **11** `clinical_coding` | HIPE / ICD-10-AM Revenue Coding (*SlainteGov*) | Click "Run Coding Sweep" on `/agents/clinical_coding` or inspect individual patient chart comorbidity panel. | Uncoded secondary comorbidities inferred from objective lab/vital evidence, estimated HIPE DRG uplift (€). | Cohort uplift KPI card (+€), patient gap breakdown with LOINC citations, and "Apply Dual Codes" button. |
| **12** `clinic_onboarding` | Clinic Onboarding & Migration (*SlainteGov*) | Select legacy practice dump (CSV/HL7/PDF) on `/agents/clinic_onboarding` and click "Run Migration Audit". | Introspected schema attributes, mapped SNOMED/LOINC codes, zero-defect validation gate status. | Interactive migration audit panel with mapping status table and 1-click Irish Core FHIR bundle compiler. |
| **13** `discharge_transfer` | Discharge & Transfer Coordinator (*SlainteCare*) | Select inpatient on `/agents/discharge_transfer` or click "Evaluate Discharge" from patient chart toolbar. | Physiological stability verification (NEWS2 <= 2), 3-Tier medication reconciliation against allergies, transfer summary. | Discharge readiness disposition card (CLEARED / HOLD) with structured handover note preview. |
| **14** `ems_prealert` | Emergency EMS Pre-Alert (*SlainteCare*) | Enter pre-hospital field vitals on ambulance tablet console or `/agents/ems_prealert` and click "Beam Pre-Alert". | Manchester Triage urgency, estimated hospital arrival time (ETA), trauma resuscitation bay pre-alert status. | High-contrast emergency dispatch card with real-time ETA countdown and encrypted hospital queue relay. |
| **15** `chronic_surveillance` | Chronic Disease Surveillance (*SlainteCare*) | Click "Run Panel Surveillance Sweep" on `/agents/chronic_surveillance` or view GP Vertical care gaps. | Overdue chronic disease markers (HbA1c > 12m, eGFR decline, SBP >= 150 mmHg) across practice cohorts. | Panel surveillance KPI cards, prioritized care gap watchlist, and 1-click "Open Chart" GP recall actions. |
| **16** `nis2_compliance` | EU NIS2 Directive Auditor (*SlainteGov*) | Click "Run NIS2 Audit Sweep" on `/agents/nis2_compliance` or click "Print Attestation Certificate". | Continuous verification of EU Directive 2022/2555 Article 21 technical cybersecurity safeguards and SIEM dispatch. | 5/5 Article 21 control compliance checklist, active SIEM webhook indicator, and printable attestation certificate. |

### Clean Agent Navigation Bar & Dropdown Design:
- **Top Bar Quick-Jump Menu**: Neatly grouped under three distinct semantic squads:
  1. *SlainteShield — Security & Adversarial* (Agents 01, 02, 03)
  2. *SlainteGov — Privacy, Compliance & Onboarding* (Agents 04, 05, 11, 12, 16)
  3. *SlainteCare — Bedside, Triage & Surveillance* (Agents 06, 07, 08, 09, 10, 13, 14, 15)
  - Dedicated direct link to the **Printable NIS2 / EU AI Act Attestation Certificate**.
- **Agent Sub-Nav Ribbon**: Responsive, horizontally scrollable ribbon on all agent pages allowing 1-click lateral navigation across all 16 agents with active indicator and monospace numbering.

---

## 12.9. Phase 12.9 — Public Site Expansion & Enterprise Visuals

**Status: Completed & Exported to `website/public-site/`.**

- [x] **Full 16-Agent Expansion in Next.js Static Platform**:
  - Expanded `website/src/data/agentsData.ts` to include complete technical records, capabilities, and vertical scenarios for all 16 agents.
  - Generated 38 static pages (covering all 16 `/health-tech-agents/*` canonical SEO routes and 8 `/verticals/*` routes) with zero build errors.
- [x] **Enterprise Healthcare Photography & Real-World Visuals**:
  - Downloaded and optimized high-resolution healthcare photography matching tier-1 health-tech standards:
    - `hero-clinicians.jpg`: Multi-disciplinary medical team during inpatient rounds.
    - `bedside-doctor.jpg`: Point-of-care digital health consultation with tablet electronic health record.
    - `emergency-team.jpg`: Acute trauma resuscitation team in hospital emergency department.
    - `telehealth-nurse.jpg`: Community nurse conducting chronic disease management surveillance.
    - `security-soc.jpg`: Hospital cybersecurity operations center monitoring real-time NIS2 and SIEM telemetry.
  - Integrated visual cards into `website/src/app/page.tsx` and exported to `website/public-site/images/`.

---

## 13. Phase 13 — Production Hardening, Multi-Tenant PostgreSQL 16 RLS Migration with Free-Tier Cloud Strategy & Pilot Launch (Active Next Phase)

**Status: Active Next Priority.**

**Why:** While initial local development leveraged SQLite WAL mode, production multi-tenant hospital deployments require PostgreSQL 16 with native Row-Level Security (`FORCE ROW LEVEL SECURITY`). However, committing to expensive managed cloud databases prematurely (e.g. Google Cloud SQL at \$50–\$150+/month) is unnecessary when robust, startup-friendly free tiers exist that natively support PostgreSQL 16 and RLS for pilot validation.

### Startup-Friendly PostgreSQL 16 Hosting Evaluation:

1. **Neon Serverless Postgres (Recommended for Staging & Instant Agent Branching):**
   - **Cost**: **100% Free** (Free Developer Tier).
   - **Capabilities**: Native PostgreSQL 16, Row-Level Security (`FORCE ROW LEVEL SECURITY`), 0.5 GB storage, autoscaling compute up to 2 vCPU, built-in connection pooling (PgBouncer), instant git-like database branching for CI test runs.
   - **Best for**: Immediate zero-cost testing of `deploy/postgres_rls_schema.sql` and continuous agentic test runs.
2. **Supabase (Managed PostgreSQL 15/16 + Built-In Auth & Dashboard):**
   - **Cost**: **100% Free** (Free Tier).
   - **Capabilities**: Dedicated PostgreSQL instance, 500 MB database, full RLS policy enforcement, web SQL editor, automated backups, and instant REST/GraphQL APIs.
   - **Best for**: Rapid pilot onboarding and visual schema inspection.
3. **AWS RDS Free Tier:**
   - **Cost**: **Free for 12 Months**.
   - **Capabilities**: 750 hours/month of `db.t4g.micro` or `db.t3.micro`, 20 GB SSD storage, automated point-in-time backups, VPC peering.
   - **Best for**: Standard AWS cloud infrastructure pipelines.
4. **IBM Cloud Databases for PostgreSQL & Startup Program:**
   - **Cost**: Free startup credits (\$1,000 to \$120,000 via Startup with IBM / IBM Partner Plus).
   - **Capabilities**: Enterprise multi-AZ PostgreSQL cluster, HIPAA-ready, ISO 27001 and SOC 2 certified, serverless Code Engine container runtime with 100,000 free vCPU-seconds/month.
   - **Best for**: Formal hospital trust pilots requiring enterprise BAA and high-availability SLAs.

### Phase 13 Implementation Steps:

- [x] **Step 1: External FHIR Sandbox Live Integration Testing (Done & Verified Live)**:
  - Connected dynamic FHIR proxy (`/settings/data`) to external testbeds (HAPI FHIR R4 public demo).
  - Verified bidirectional write-back, provenance signing, and remote validation under simulated network latency.
- [ ] **Step 2: Multi-Tenant PostgreSQL 16 RLS Migration Cutover**:
  - Connect `deploy/postgres_rls_schema.sql` to selected free-tier PostgreSQL instance (Neon, Supabase, AWS Free Tier, or IBM Cloud credits — *Decision: To be decided before cutover*).
  - Priority pilot vertical lead: **SlainteED & SlainteEMS** (Acute Emergency Department and Ambulance Triage queue with real-time pre-alerts).
  - Execute schema migration: `tenants`, `clinical_users`, `patients`, `fhir_resources` (`JSONB` + GIN indexing), `audit_ledger`, and `rls_policies`.
  - Validate `FORCE ROW LEVEL SECURITY` ensuring tenant isolation cannot be breached even by application SQL injection.
  - Run multi-worker gunicorn concurrency benchmarks under synthetic cohort loads.
- [ ] **Step 3: Production Custom Domain & Automated TLS Ingress**:
  - Purchase commercial production domain (Target: `slaintetech.com` or `slainte.io`).
  - Point DNS `A`/`AAAA` records to Caddy reverse proxy host.
  - Caddy automatically provisions production Let's Encrypt / ZeroSSL TLS certificates with automatic renewal.

**Why:** Showcases **SlainteTech AI Security Labs**, the **9-Agent Autonomous Fleet (`/agents/*`)**, the **Deterministic FastMCP Guardrails (`/platform/mcp-guardrails`)**, and all **7 Specialty Vertical Cockpits (`/verticals/*`)** in a Next.js App Router + Netlify + Docker web platform with built-in SEO and GEO (`public/llms.txt` + JSON-LD).

### Audiences

1. **A hiring manager or technical lead** skimming for 60 seconds — wants to
   know what it is, that it's real, and that the judgement is sound
2. **A developer** who might read the code — wants architecture and decisions
3. **A clinician** — wants to see the screens and understand honestly what it
   is and isn't

### Honesty constraints — non-negotiable

A page about a patient dashboard that overstates itself damages credibility
with exactly the audience it targets.

- State plainly it is a **demonstration** against **synthetic** data
- **No** invented users, testimonials, certifications or metrics. Real,
  checkable numbers only
- **No** medical-device or clinical-validation language
- Link SECURITY.md including its gap list — identified gaps read as competence
- Domain and branding make a project look more official, which *raises* the
  duty to be clear about what it is

### Content

Hero (one sentence, real screenshot) · the problem (FHIR tools are either
enterprise-heavy or toys; this sits between) · live screens · architecture
(Flask + HTMX, no build step, fragments over the wire, concurrent fetches,
append-only audit) · **engineering decisions** — the section a technical reader
stops for:

- An unreachable backend must never render as "no allergies recorded" — a
  failure and an empty result are clinically different
- Blood pressure arrives in two shapes from real servers; both handled,
  unpairable readings dropped rather than guessed
- The audit log is append-only by database trigger, not convention
- AI is gated in code on the data source being synthetic

Then the phase journey, and links.

### Brand

Credibility here comes from restraint. One accent colour used sparingly,
generous whitespace, a deliberate typeface pairing, tabular figures for clinical
numbers, real screenshots, no stock photography. The current `--tropical-*`
palette in `static/styles.css` reads as a tutorial theme and should be replaced.
**Apply the identity to the app, not just the page** — a polished landing page
in front of an unstyled app is worse than neither.

### Specialty personas — dentist, GP, psychiatrist

Same app and layout, different cohort and panel emphasis, implemented as a
**specialty profile**: config selecting which panels lead, which terminology
subset the picker uses, which demo cohort loads. Demonstrates a platform rather
than one hard-coded screen, and exercises real FHIR design — specialty
differences genuinely live in `Condition.category`, `Procedure.bodySite` and
terminology bindings. **One excellent persona at launch beats three thin ones.**

### Tasks

- [ ] Landing page — hand-written static HTML/CSS, self-contained, no CDN
- [ ] Screenshots at a consistent viewport against synthetic data
- [ ] Architecture diagram; Open Graph tags (most of how a link gets seen)
- [ ] Accessibility pass — semantic headings, real alt text, keyboard nav,
      contrast. Note the invisible panel headings fixed in Phase 4 were a
      contrast failure that shipped
- [ ] Link page → live demo with visible credentials
- [ ] Rate limits sized for a public demo, assuming abuse

---

## 13. Reference

### 13.1 Verified platform facts

**FHIR server** (`https://hapi.fhir.org/baseR4`, checked 2026-08-08):

| Capability | Result |
|---|---|
| `GET /Patient/{id}/$everything` | Works — Patient + Encounter + Observations in one call |
| `POST Condition` | 201 with ETag `W/"1"` |
| `PUT` with `If-Match` | 200, version increments |
| `PUT` with stale `If-Match` | **409**, not the spec's 412 — handle both |
| `DELETE Condition` | 200 |

**Clinical data profile:** 2,951 Conditions (ICD-10-CM 39%, SNOMED 34%,
ICD-10 11%); `clinicalStatus` on 68%, `onsetDateTime` 44%, `recordedDate` 21% —
every field is optional in practice. Encounter linkage is weak (18% of
Conditions, 1% of MedicationRequests) so **do not build anything requiring an
encounter**. 1,418 MedicationRequests, `dosageInstruction` on 82%, RxNorm
dominant. 605 Practitioners.

**Model** (`gpt-6.1` / Enterprise Frontier, updated 2026-10-18):

| Property | Value |
|---|---|
| Architecture | Dense multimodal reasoning with strict structured JSON schema output |
| Context / max output | 2,000,000 / 128,000 tokens |
| Pricing | $0.10/M input · $0.01/M cached input · $0.60/M output (Cheaper & higher density than 5.x) |
| Repricing cliff | Eliminated — linear token pricing across long multi-resource FHIR contexts |
| Endpoints | `v1/chat/completions` and `v1/responses`; streaming SSE supported |
| Reasoning | `none`/`low`/`medium`/`high`; default `low` for fast clinical bedside intake |
| Tool Calling | Native FastMCP tool calling integration (`calculate_news2_score`, `check_drug_allergy`) |

Measured context: a dense patient record is ~19,300 tokens (~$0.0019); a
curated subset ~3,800 tokens (~$0.00038). Roughly **<$0.80 per thousand calls**
with prompt caching. Configurable via `AI_MODEL=gpt-6.1` in environment or Settings.

### 13.2 Conventions

Defensive FHIR parsing (every function returns None/fallback rather than
raising); failure and empty are distinct at the type level (`FhirResult`); audit
on every patient access with pseudonymised identifiers; tests alongside code,
offline and stubbed; no unpinned dependencies; controls hidden rather than
rendered-then-403'd.

---

## 14. Gaps and innovations

| # | Gap | Why it matters |
|---|---|---|
| G1 | No backup/restore plan | An audit log you cannot restore is not an audit log. Folded into Phase 6 |
| G2 | No data-retention policy | `audit_log` and `ai_exchange` grow unbounded — cost and compliance |
| G3 | No error tracking | Logs exist; nothing aggregates or alerts. Cheap in Phase 6 |
| G4 | No accessibility audit | A clinical tool carries a stronger obligation, and UK/EU public sector has legal requirements |
| G5 | No performance budget | Every panel is a live FHIR round trip. A slow demo reads as broken |
| G6 | No ADR log | Decisions live in commit messages and this file |
| G7 | **Terminology source unplanned** | Phase 8 needs ICD-10/SNOMED search. Bundled subset, `$expand` on the server, or external service — **decide before Phase 8** |
| G8 | No degraded mode | If the FHIR server is down the app is a shell. A public demo needs graceful degradation |
| G9 | Single points of failure in the demo | Consider a read-through cache so a HAPI outage doesn't blank it |
| G10 | **`ai_exchange` has no reader in the app** | The trail is written but only reachable via SQLite. `/admin/audit` has no AI equivalent, so an investigation needs shell access to the box. Small admin page — fold into Phase 9 |
| G11 | Token counts are estimated, not reported | `estimate_tokens` is a character heuristic; the provider returns real usage. Phase 9 should store the reported counts and keep the estimate only for the pre-flight ceiling check |

### Innovations worth taking

- **Lead with the clinical safety net.** The allergy-vs-medication cross-check
  is the one item with genuine clinical value rather than convenience.
- **Make the audit log a visible feature.** "Every access recorded, immutably"
  is a differentiator here. Giving patients their own access log is cheap and
  unusually trust-building.
- **Structured outputs** for anything parsed, rather than free text — removes a
  class of parsing bug.

### The smart toilet / fridge idea

Honestly, that is **a different product** — consumer IoT and nutrition
tracking, against a clinician-facing record viewer. Forcing them together
weakens both.

The right relationship is that the consumer app becomes a **client** of this
one through the patient portal, writing `Observation` resources (weight, diet
adherence) into the patient's record that the clinician then sees. Clean
boundary, and a genuinely compelling story — patient-generated data flowing into
the clinical record — without entangling the codebases. Prerequisite: Phase 10
plus a patient-scoped write API. Keep in view as a possible Phase 13.

---

## 15. Open decisions

1. **Terminology source** for Phase 8's code pickers (G7) — blocks Phase 8
2. **Single-practice or multi-tenant** — decide before appointments/billing
3. **Landing page hosting** — GitHub Pages (stays up if the app is down) vs
   served by the app (one deployment, one domain)
4. **Memorystore or a Postgres-backed rate limiter** — cost against correctness
5. **Retention windows** for `audit_log` and `ai_exchange` (G2) — now live
   rather than hypothetical: the table exists and is append-only, so a
   retention policy has to be a scheduled job, not a `DELETE`
6. **How many demo personas at launch** — one strong or three thin
7. **Prescriber identity** — map users to `Practitioner`, or display-only string
8. **CDN or vendored assets** — vendoring simplifies CSP considerably
9. **Domain name** — must not imply a real clinical service
10. **Retention of `ai_exchange.response`** — indefinite audit value vs storage
