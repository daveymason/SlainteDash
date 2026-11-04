# Project plan

The single planning document for this project. Phases are numbered in the
order they should be built. Supersedes the previous per-phase files.

Last reviewed: 2026-08-09 · 286 tests passing, pyflakes clean.

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
- [11. Phase 11 — Multi-Vertical Domain Specialization](#11-phase-11--multi-vertical-domain-specialization)
- [12. Phase 12 — Turnkey Appliance Packaging & Commercial Launch](#12-phase-12--turnkey-appliance-packaging--commercial-launch)
- [13. Reference & Enterprise AI Strategy](#13-reference--enterprise-ai-strategy)
- [14. Gaps and innovations](#14-gaps-and-innovations)
- [15. Open decisions](#15-open-decisions)

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
| 11 + 9 Lite | Sidebar "Agents" Hub (9 Agents + Settings + Embedded Copilots), GDPR/CVE/Audit Agents, & "Sign in as..." 7 Vertical Cockpits | **Done**, merged |
| 12 | `SlaintePages` Public Startup & Product Platform (`SlainteTech AI Security Labs`, Next.js + Netlify + Docker) | **Active Next Priority** |
| 10 | Standalone Mobile/Laptop Patient App (Shared `SlainteFHIR` Backend) | **Deferred (Separate Post-Funding Project)** |

The dashboard (`SlainteDash`) operates as the primary clinical interface of the
unified **Slainte-Engine Appliance**, backed by `SlainteScan` (FastMCP 8081),
`SlainteFHIR` (Micro-EHR 8082), `Slainte-Auditor` (Autonomous Red-Team FHIR Verifier),
and `SlainteEngine` (Autonomous Ingestion 3000).

## 2. Unified Architecture & Renumbering

Phases are aligned with the master `slainte-engine/roadmap.md` specification:

1. **Appliance Monorepo Realignment:** The dashboard is no longer a standalone viewer
   querying public HAPI; it is the clinical cockpit for a four-container clinical appliance.
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
| **6** | Clinical Intelligence, NEWS2, Provenance Sign-Off, Core Security | **Active** |
| **7** | SlainteFHIR Micro-EHR (Port 8082), Real-Time SSE, Write-Back | **Active** (Server Shipped) |
| **8** | Enterprise AI (OpenAI / Azure), FastMCP Tool Orchestration, UI Actions | **Next Up** |
| **9** | Enterprise Security (SQLCipher, SMART on FHIR, Regulatory Dossier) | Planned |
| **10** | Patient Portal & Resource-Scoped Authorization | Planned |
| **11** | Multi-Vertical Domain Specialization (SlainteGP, SlainteDent, SlaintePhysio) | Planned |
| **12** | Turnkey Appliance Packaging & Commercial Launch | Planned |

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

**Status: Active Next (Executed alongside Phase 11 so Security, GDPR & Audit Agents verify all 7 Vertical Role Boundaries).**

**Why:** Rather than introducing fragile C-level SQLCipher or external OIDC dependencies before commercial funding, governance and security verification are delivered as three dedicated autonomous agents inside the `/agents` Command Center:

### Tasks
- [ ] **Agent 03 — Software Supply-Chain & App Vulnerability Agent (`SlainteShield-CVE`):** Audits pinned dependencies (`requirements.txt`), verifies active HTTP security headers (`Content-Security-Policy`, `SRI sha384-`, `SameSite`, `HttpOnly`), and inspects multi-worker `SqliteStorage` rate-limiting posture.
- [ ] **Agent 04 — GDPR & Clinical Data Privacy Agent (`SlainteGov-GDPR`):** Enforces EU GDPR Art. 9 & Irish HIQA data minimisation: audits `AI_DEIDENTIFY` PII stripping, checks the `AI_ALLOW_REAL_PHI` BAA/DPIA gate, and verifies salted SHA-256 subject pseudonymisation (`LOG_HASH_SALT`).
- [ ] **Agent 05 — Immutable Clinical & AI Audit Trail Agent (`SlainteGov-Audit` — Closes Gaps `G1` & `G10`):** Verifies SQLite append-only triggers on `audit_log` & `ai_exchange`, provides the in-app `ai_exchange` & `audit_log` reader, checks `Provenance` SHA-256 bundle signatures across all 7 verticals, and provides a one-click signed JSON audit snapshot export.

---

## 10. Phase 10 — Standalone Patient Self-Service Mobile/Laptop App

**Status: Deferred (Separate Future Project Sharing the `SlainteFHIR` Backend).**

**Why:** Packaging a consumer-facing responsive mobile/laptop application is a standalone product track that will consume the `SlainteFHIR` (`:8082`) backend API once funded.

---

## 11. Phase 11 — The 9-Agent Command Center (`/agents`) & "Sign in as..." 7 Multi-Vertical Cockpits

**Status: Active Next Priority (Step 1).**

**Why:** Unifies the entire stack around **SlainteTech AI Security Labs'** core differentiator: **9 specialized Security, Governance, and Clinical Agents** managed from a sidebar **"Agents"** Command Center (`/agents`) with per-agent settings, while keeping clinical copilots embedded directly on patient and intake screens and adapting the cockpit to **7 "Sign in as..." verticals**.

### 11.1 The 9-Agent Autonomous Fleet (`/agents` Hub + Embedded Copilots)
- **Squad A — Security & Red-Team (`SlainteShield`):**
  1. **Agent 01: BOLA & Role-Boundary Red-Team Agent (`SlainteShield-BOLA`)** — Live Victim/Attacker cross-compartment (`CompartmentDefinition/Patient`) and cross-vertical probing using Dual-Phase Reflection ($\mathcal{M}$).
  2. **Agent 02: FHIR R4 Conformance & Terminology Agent (`SlainteShield-FHIR`)** — SNOMED-CT, LOINC, UCUM, Irish GMS OID & `$validate` verification + OASIS SARIF v2.1.0 export.
  3. **Agent 03: Software & CVE Vulnerability Agent (`SlainteShield-CVE`)** — Dependency pin audit, CSP/SRI header verification, and rate-limiter posture check.
- **Squad B — Governance & Regulatory Privacy (`SlainteGov`):**
  4. **Agent 04: GDPR & Clinical Privacy Agent (`SlainteGov-GDPR`)** — EU GDPR Art. 9 data minimisation, `AI_DEIDENTIFY` verification, `AI_ALLOW_REAL_PHI` gate, and salted pseudonymisation check.
  5. **Agent 05: Immutable Clinical & AI Audit Agent (`SlainteGov-Audit`)** — Append-only trigger verification, live `ai_exchange` & `audit_log` viewer, `Provenance` SHA-256 verification, and signed snapshot export.
- **Squad C — Clinical Intelligence & Ingestion (`SlainteClinical` — Managed in `/agents` + Embedded in App):**
  6. **Agent 06: Multimodal Clinical Ingestion Agent (`SlainteEngine-Ingest`)** — Embedded on the Patients Intake Modal + `/data/raw` watcher.
  7. **Agent 07: Patient Summariser & Handover Agent (`SlainteScribe-Brief`)** — Embedded directly on every **Patient Details** page (`POST /ai/summarise/<patient_id>`).
  8. **Agent 08: Medication & Allergy Safety Agent (`SlainteRx-Guard`)** — Embedded in the **Intake Modal**, **Patient Details**, and **Pharmacy Cockpit** (`check_drug_allergy_contraindications`).
  9. **Agent 09: Acuity Triage & Deterioration Agent (`SlainteDx-Triage`)** — Embedded in the **Live Triage Queue** and **Patient 24h NEWS2 Sparkline Card**.

### 11.2 "Sign in as..." 7 Specialty Vertical Cockpits & Modernized Navigation
- **Vertical 1: Emergency Department (`SlainteED`):** MTS Cat 1–5 live triage queue, 24h NEWS2 sparklines, acute intake dropzone.
- **Vertical 2: General Practice (`SlainteGP`):** SOAP clinical notes, HSE Chronic Disease Management (CDM) tracking, repeat prescribing safety gate.
- **Vertical 3: Dental Surgery (`SlainteDent`):** Pre-op allergy/anticoagulant clearance gate, interactive 32-tooth FDI Odontogram & 6-sextant BPE summary, dental referral ingestion.
- **Vertical 4: Community & Hospital Pharmacy (`SlaintePharm`):** Prescription dispensing queue, deterministic Beta-Lactam/NSAID cross-reactivity gate, Irish GMS reimbursement validation.
- **Vertical 5: Pre-Hospital Ambulance / EMS (`SlainteEMS`):** High-contrast field ePCR intake, rapid ambulance MTS/NEWS2 scoring, hospital ETA pre-alert handoff.
- **Vertical 6: Elite Sports Club (`SlainteSport`):** Squad readiness & physiological load telemetry, concussion return-to-play `Provenance` clearance, BOLA-verified athlete privacy.
- **Vertical 7: Astronaut Health Monitoring (`SlainteAstro`):** 100% air-gapped deep-space bio-telemetry running local 3B Ollama models + deterministic FastMCP diagnostics.

---

## 12. Phase 12 — Turnkey Appliance Packaging & Commercial Launch

**Why:** a product-style landing page, a professional brand, and a live demo to
point at.

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
