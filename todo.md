# Slainte-Engine & SlainteDash — Master Todo & Roadmap Checklist

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
- [x] **Phase 6 — Clinical Intelligence & Patient Safety**:
  - [x] Royal College of Physicians **NEWS2** early warning score calculation (`calculate_news2_score` in FastMCP) with 24-hour vital trajectory SVG sparklines.
  - [x] **Clinician Electronic Sign-Off** (`Provenance` resource generation with practitioner IMC/GMC registration and SHA-256 bundle integrity hash).
  - [x] **Deterministic Drug-Allergy Safety Gate** (`check_drug_allergy_contraindications` in FastMCP + `/fhir/validate-safety` HTMX interception).
- [x] **Phase 6.4 — Core Security Hardening**:
  - [x] Centralized SQLite-backed rate limiting (`rate_limit_storage.py`) eliminating multi-worker memory drift.
  - [x] Progressive account lockout (15-minute lockout after 5 consecutive failed logins).
  - [x] Mandatory `LOG_HASH_SALT` validation outside debug/test mode.
  - [x] Content Security Policy (CSP) headers and Subresource Integrity (SRI `sha384-`) hashes across CDN assets.
- [x] **Phase 7 — SlainteFHIR R4 Micro-EHR (`slainte-fhir:8082`) & Slainte-Auditor Red-Team Verifier**:
  - [x] Dedicated HL7 FHIR R4 server (`slainte-fhir`) exposing `/fhir/r4/metadata`, `CompartmentDefinition/Patient`, `$validate`, `Provenance`, `AuditEvent`, and `Subscription`.
  - [x] **Slainte-Auditor Autonomous Red-Team FHIR Verifier**: 4-stage verification pipeline (RFC 1918 sandbox guardrail + compartment pruning, SNOMED/LOINC/UCUM/Irish GMS OID deterministic audit, Dual-Phase Reflection BOLA probing with `SharedAuditMemory` $\mathcal{M}$, and OASIS SARIF v2.1.0 report generation).
  - [x] Interactive **Slainte-Auditor UI** in `SlainteDash` with 5 KPI telemetry cards, model selector (`openai/gpt-6.1-luna`, `openai/gpt-4o`, `openai/gpt-4o-mini`, `k9/lime:latest`, `k9/lime-lite:latest`, `k9/Doggo:3b`, `k9/chihuahua:latest`, `recordstore:latest`, `gemma3:1b`), Live LLM Agent Synthesis, and execution console logs.

---

## Upcoming Product Roadmap 🚀

### 1. Modernized Navigation & "Sign in as..." Role-Based Vertical Dashboards (Phase 11)
- [ ] **"Sign in as..." Role & Specialty Persona Picker on Login**: Allow users to select or sign into a tailored clinical vertical workspace backed by the same unified FHIR R4 engine:
  - [ ] **Emergency Room (ED / Acute Triage)**: Manchester Triage System (MTS Cat 1–5), NEWS2 deterioration tracking, acute intake dropzone.
  - [ ] **General Practice (GP)**: SOAP clinical notes (*Subjective, Objective, Assessment, Plan*), HSE Chronic Disease Management (CDM) forms, repeat prescribing, and referrals.
  - [ ] **Dentist (Dental Surgery & Periodontics)**: Interactive 32-tooth SVG Odontogram (FDI 11–48), 6-sextant BPE periodontal scoring, and radiography ingestion.
  - [ ] **Pharmacy (Clinical Dispensing & Safety)**: Prescription dispensing queue, deterministic drug-allergy/drug-drug interaction checks, and Irish GMS reimbursement coding.
  - [ ] **Ambulance Driver / Paramedic (Pre-Hospital ePCR)**: High-contrast tablet/mobile field intake, rapid vital sign capture, ETA hospital pre-alert, and one-tap ED handoff.
  - [ ] **Elite Sports Group (Sports Medicine & Athlete Performance)**: Squad readiness overview, concussion return-to-play protocols (SCAT6), MSK injury body map, and physiological load telemetry.
- [ ] **Navigation Overhaul**: Modernize the sidebar and top navigation bar to dynamically adapt links, quick actions, and KPI widgets to the active vertical dashboard.

### 2. Patient Self-Service App — Mobile & Laptop (Phase 10)
- [ ] **Cross-Device Patient Portal (Phone & Laptop Responsive Web App)**: Dedicated patient-facing experience enabling individuals to access and manage their own health data anywhere.
- [ ] **Cryptographic Resource-Scoped Authorization**: Bind each authenticated patient session strictly to their own `Patient/{id}` compartment (`CompartmentDefinition/Patient`), verified continuously by `Slainte-Auditor` BOLA checks.
- [ ] **Self-Service Patient Capabilities**:
  - [ ] View and manage personal demographics, active conditions, prescribed medications, allergies, and immunization/vital history.
  - [ ] Upload patient-generated health documents or wearable/home vital observations (`Observation`).
  - [ ] **"Who Viewed My Record" Transparency Log**: Real-time patient-facing audit trail powered by the immutable `audit_log` table.

### 3. Enterprise AI Bedside Assistant & Cryptographic Storage (Phases 8–9)
- [ ] **Bedside AI Actions**: Wire `POST /ai/summarise/<patient_id>`, `POST /ai/crosscheck/<patient_id>`, and docked multi-turn clinical chat (`POST /ai/chat/<patient_id>`) to FastMCP deterministic tools.
- [ ] **AI Governance Viewer**: Admin screen at `/admin/ai_exchanges` inspecting the append-only `ai_exchange` table.
- [ ] **Encryption at Rest & SSO**: SQLCipher AES-256 database encryption and SMART on FHIR / OIDC enterprise authentication.
