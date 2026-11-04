# SlainteTech AI Security Labs — Master Todo & Roadmap Checklist

## Completed Milestones ✅

- [x] **Ensure the sidebar works properly (URL updating)**: Added `hx-push-url="/?view={{ key }}"` and full browser history `popstate` synchronization.
- [x] **Collapsible MTS Triage Queue Minimisation**: Implemented 5 category accordions (Cat 1–3 open, Cat 4–5 collapsed by default) with "Expand All", "Focus Urgent (Collapse Cat 4–5)", and session storage preference persistence.
- [x] **Add more patients**: Expanded test cohort to 34 diverse clinical emergency records covering all 5 Manchester Triage System categories (`P001`–`P9660`).
- [x] **Allow adding patients (Manual entry + File Upload)**: Built in-dashboard intake modal with Fast Triage Form (deterministic MTS scoring & sub-second FHIR R4 generation) and Batch CSV Dropzone synced with the OpenHands autonomous daemon.
- [x] **GMS Number Deduplication**: Prevented duplicate patient cards across CSV re-ingestion and manual intake (`find_patient_id_by_gms` in `LocalFhirStore` and `app.py`).
- [x] **Architectural Stopgap & Justification**: Documented monorepo vs. multi-repo trade-offs in `stopgap.md`.
- [x] **Create unified project packaging**: Packaged turnkey appliance orchestration into a single executive control script (`./run.sh`), `Makefile`, and `docker-compose.yml` supporting `start`, `stop`, `status`, `test`, `ingest`, and `logs`.
- [x] **Fix sidebar single-click navigation**: Resolved pointer-event trapping on SVG icons and eliminated View Transition API interaction locks (`hx-swap="innerHTML"`) with full `popstate` history synchronization.
- [x] **Add PDF and Image to Patient Intake & Relocate from Header**: Removed the intake button from the top navbar, added the dedicated `(Add Patient / Ingest)` button to the Patients page header, and added multimodal PDF and Image (PNG/JPG) ingestion with FastMCP zero-hallucination validation gates.
- [x] **Phase 5 — Multi-Backend Switcher (`/settings/data`)**: Dynamic zero-restart switching between `SlainteFHIR Micro-EHR (8082)`, `Local Filesystem Store`, `Public HAPI Demo`, and `Custom URL` via `DynamicFhirProxy`.
- [x] **Phase 6 — Clinical Intelligence, Patient Safety & Core Security**:
  - [x] Royal College of Physicians **NEWS2** early warning score calculation (`calculate_news2_score` in FastMCP) with 24-hour vital trajectory SVG sparklines.
  - [x] **Clinician Electronic Sign-Off** (`Provenance` resource generation with practitioner IMC/GMC registration and SHA-256 bundle integrity hash).
  - [x] **Deterministic Drug-Allergy Safety Gate** (`check_drug_allergy_contraindications` in FastMCP + `/fhir/validate-safety` HTMX interception).
  - [x] Centralized SQLite-backed rate limiting (`rate_limit_storage.py`), progressive account lockout (15-min after 5 failed logins), `LOG_HASH_SALT` enforcement, CSP headers, and SRI `sha384-` hashes.
- [x] **Phase 7 — SlainteFHIR R4 Micro-EHR (`slainte-fhir:8082`) & Slainte-Auditor Red-Team Verifier**:
  - [x] Dedicated HL7 FHIR R4 server (`slainte-fhir`) exposing `/fhir/r4/metadata`, `CompartmentDefinition/Patient`, `$validate`, `Provenance`, `AuditEvent`, and `Subscription`.
  - [x] **Slainte-Auditor Autonomous Red-Team FHIR Verifier**: 4-stage verification pipeline (RFC 1918 sandbox guardrail + compartment pruning, SNOMED/LOINC/UCUM/Irish GMS OID deterministic audit, Dual-Phase Reflection BOLA probing with `SharedAuditMemory` $\mathcal{M}$, and OASIS SARIF v2.1.0 report generation).
- [x] **Phase 8 — Unified AI Model Selector (`/settings/ai`), `.env` Key Integration & Bedside AI Briefing**:
  - [x] Unified `/settings/ai` Model Selector (`POST /settings/ai/select`) supporting Local Sovereign Ollama models (`k9/lime:latest`, `k9/lime-lite:latest`, `k9/Doggo:3b`, `k9/chihuahua:latest`, `recordstore:latest`, `gemma3:1b`) and Cloud Frontier models (`openai/gpt-6.1-luna`, `openai/gpt-4o`, `openai/gpt-4o-mini`) backed by `OPENAI_API_KEY` in `.env`.
  - [x] Added **Generate AI Bedside Briefing** (`POST /ai/summarise/<patient_id>`) on the Patient Details view grounded in deterministic NEWS2 and drug-allergy checks and logged to `ai_exchange`.

---

## Active Final Phases (Execution Order) 🚀

### Step 1: Phase 11 + Phase 9 Lite (Unified) — The 9-Agent Command Center & 7 "Sign in as..." Vertical Cockpits ✅ COMPLETED
*(Executed first so the Security, GDPR, Vulnerability, and Audit agents inspect all 7 vertical role boundaries.)*

- [x] **Sidebar "Agents" Hub (`/agents`) & Per-Agent Settings Modal**:
  - [x] Replaced the single `"Slainte-Auditor"` sidebar link with **"Agents"** (`/agents`), displaying all **9 Autonomous Agents** across 3 squads with live status, bound FastMCP tools, execution triggers, and a **Settings / Configure** drawer for every agent:
    1. **Agent 01 — BOLA & Role-Boundary Red-Team Agent (`SlainteShield-BOLA`)**: Cross-patient (`CompartmentDefinition/Patient`) and cross-vertical BOLA probing via Dual-Phase Reflection ($\mathcal{M}$).
    2. **Agent 02 — FHIR R4 Conformance & Terminology Agent (`SlainteShield-FHIR`)**: SNOMED-CT, LOINC, UCUM, Irish GMS OID & `$validate` verification + OASIS SARIF v2.1.0 export.
    3. **Agent 03 — Software Supply-Chain & App Vulnerability Agent (`SlainteShield-CVE`)**: Audits pinned dependencies (`requirements.txt`), active `CSP` & `SRI sha384-` headers, session flags (`HttpOnly`, `SameSite`), and `SqliteStorage` rate-limiter posture.
    4. **Agent 04 — GDPR & Clinical Data Privacy Agent (`SlainteGov-GDPR`)**: Enforces EU GDPR Art. 9 & Irish HIQA data minimisation (`AI_DEIDENTIFY`, `AI_ALLOW_REAL_PHI` BAA gate, and salted SHA-256 subject pseudonymisation `LOG_HASH_SALT`).
    5. **Agent 05 — Immutable Clinical & AI Audit Trail Agent (`SlainteGov-Audit` — Phase 9 Lite `G1` & `G10`)**: Verifies SQLite append-only triggers on `audit_log` & `ai_exchange`, provides the live `ai_exchange` & `audit_log` reader in `/settings/security`, validates `Provenance` SHA-256 signatures, and exports one-click signed audit snapshots (`/agents/audit/snapshot`).
    6. **Agent 06 — Multimodal Clinical Ingestion Agent (`SlainteEngine-Ingest`)**: Manages `/data/raw` & bedside CSV/PDF/OCR ingestion into deduplicated FHIR R4 bundles.
    7. **Agent 07 — Patient Summariser & Handover Agent (`SlainteScribe-Brief`)**: Configurable in `/agents` AND **embedded directly on every Patient Details page** (`POST /ai/summarise/<patient_id>`).
    8. **Agent 08 — Medication & Allergy Safety Agent (`SlainteRx-Guard`)**: Configurable in `/agents` AND **embedded directly in the Intake Modal, Patient Details (`POST /ai/crosscheck/<patient_id>`), and Pharmacy Cockpit** (`check_drug_allergy_contraindications`).
    9. **Agent 09 — Acuity Triage & Deterioration Agent (`SlainteDx-Triage`)**: Configurable in `/agents` AND **embedded directly in the Live Triage Queue & Patient 24h NEWS2 Sparkline card**.
- [x] **"Sign in as..." 7 Role-Based Vertical Cockpits & Modernized Navigation**:
  - [x] Added role/vertical selector on `/login` (`Sign in as...`) and a live **Vertical Cockpit Switcher** (`POST /verticals/switch`) in the top header bar:
    - [x] **1. Emergency Department (`SlainteED`)**: Collapsible MTS Cat 1–5 queue, 24h NEWS2 sparklines, acute intake.
    - [x] **2. General Practice (`SlainteGP`)**: SOAP consultation notes, HSE Chronic Disease Management (CDM) tracking, repeat prescribing safety gate.
    - [x] **3. Dentistry (`SlainteDent`)**: Pre-op allergy/anticoagulant clearance gate, 32-tooth FDI Odontogram & 6-sextant BPE summary, dental referral ingestion.
    - [x] **4. Pharmacy (`SlaintePharm`)**: Active `MedicationRequest` dispensing queue, deterministic Beta-Lactam/NSAID cross-reactivity gate, GMS validation.
    - [x] **5. Ambulance / EMS (`SlainteEMS`)**: High-contrast pre-hospital ePCR field intake, rapid ambulance MTS/NEWS2 scoring, hospital ETA handoff.
    - [x] **6. Elite Sports Club (`SlainteSport`)**: Squad readiness & physiological load telemetry, concussion return-to-play `Provenance` sign-off, athlete BOLA privacy.
    - [x] **7. Astronaut Health Monitoring (`SlainteAstro`)**: 100% air-gapped deep-space bio-telemetry running local 3B models + deterministic FastMCP diagnostics.

### Step 2: Phase 12 — `SlaintePages` Public Startup & Product Website (`SlainteTech AI Security Labs`)
- [ ] Build the Next.js App Router + Netlify + Docker marketing and product platform in `/home/adman-voids/Desktop/Code/SlaintePages` matching `SlainteDash` styling, featuring `/agents/*` (all 9 agents), `/verticals/*` (all 7 vertical cockpits), `/platform/mcp-guardrails`, and SEO + GEO (`public/llms.txt` + JSON-LD).

### Future Standalone Project (Deferred Post-Funding)
- [ ] **Phase 10 (Standalone Mobile/Laptop Patient App)**: Dedicated patient-facing mobile & web client sharing the `SlainteFHIR` backend.
