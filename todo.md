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

- [x] **Sidebar "Agents" Hub (`/agents`), 9 Dedicated Agent Dashboards (`/agents/<agent_id>`) & Per-Agent Settings**:
  - [x] Replaced the single `"Slainte-Auditor"` sidebar link with **"Agents"** (`/agents`), displaying all **9 Autonomous Agents** with a **Configure** drawer AND a dedicated **Operational Dashboard Page (`/agents/<agent_id>` / `/?view=agent_<agent_id>`)** accessible from every agent card, the Agent Sub-Nav bar, and the top-bar `Agents ▾` dropdown:
    1. **Agent 01 — BOLA & Role-Boundary Red-Team (`/agents/bola_redteam` — `SlainteShield-BOLA`)**: Dedicated page with live BOLA probe runner, `CompartmentDefinition/Patient` pruning metrics, Victim vs. Attacker `SharedAuditMemory` ($\mathcal{M}$) table, and OWASP API1:2023 findings.
    2. **Agent 02 — FHIR R4 Integrity & Terminology (`/agents/fhir_conformance` — `SlainteShield-FHIR`)**: Dedicated page with interactive single-patient FHIR R4 bundle inspector, Irish GMS OID verifier, SNOMED/LOINC/UCUM drift table, and OASIS SARIF v2.1.0 export.
    3. **Agent 03 — Supply-Chain & App Vulnerability (`/agents/cve_vulnerability` — `SlainteShield-CVE`)**: Dedicated page auditing pinned dependencies (`requirements.txt`), verified CDN `SRI sha384-` hashes, `CSP`/`HttpOnly`/`SameSite` headers, and `SqliteStorage` rate-limiting.
    4. **Agent 04 — GDPR Art. 9 & Clinical Privacy Gate (`/agents/gdpr_privacy` — `SlainteGov-GDPR`)**: Dedicated page with EU GDPR Art. 5/9/15/28/32 compliance matrix and an interactive **Live Patient PII De-Identification Sandbox** showing raw FHIR fields vs. stripped LLM context.
    5. **Agent 05 — Immutable Clinical & AI Audit Ledger (`/agents/immutable_audit` — `SlainteGov-Audit`)**: Dedicated page with live SQLite savepoint tamper-rejection test (`BEFORE UPDATE/DELETE` triggers), `Provenance` SHA-256 signature table, live `audit_log` & `ai_exchange` readers, and signed JSON snapshot export (`/agents/audit/snapshot`).
    6. **Agent 06 — Multimodal Clinical Ingestion Pipeline (`/agents/multimodal_ingest` — `SlainteEngine-Ingest`)**: Dedicated page (replacing the old standalone sidebar `Pipeline Status` tab) with `/data/raw` dropzone inspector, 5-stage FastMCP harmonization telemetry, and indexed FHIR R4 bundle browser.
    7. **Agent 07 — Cited Patient Summariser (`/agents/patient_summariser` — `SlainteScribe-Brief`)**: Dedicated page with interactive patient selector & live `[ResourceType/id]`-cited 3-bullet handover generator, plus embedded on every Patient Details page (`POST /ai/summarise/<patient_id>`).
    8. **Agent 08 — Pharmacotherapy & Allergy Safety Gate (`/agents/medication_safety` — `SlainteRx-Guard`)**: Dedicated page with interactive patient + candidate drug cross-reactivity tester and cohort-wide contraindication sweep, plus embedded on Patient Details (`POST /ai/crosscheck/<patient_id>`).
    9. **Agent 09 — Acuity Triage & NEWS2 Deterioration (`/agents/acuity_triage` — `SlainteDx-Triage`)**: Dedicated page with interactive MTS Cat 1–5 & RCP NEWS2 physiological calculator and high-acuity patient watchlist, plus embedded in the ED/EMS Triage Queue.
- [x] **"Sign in as..." 7 Role-Based Vertical Cockpits, Cockpit-Adaptive `Patients` Roster & Minimalist Medical UI**:
  - [x] **De-duplicated Header & Cockpit-Aware Sidebar**: Removed duplicate logos/badges and the `"9 Autonomous Agents Active"` button from the header; removed `Pipeline Status` from the sidebar; restricted `Live Triage` in the sidebar exclusively to acute cockpits (`SlainteED` & `SlainteEMS`).
  - [x] **Cockpit-Adaptive `Patients` Roster (`/fhir/Patients`)**: Switching cockpits dynamically adapts the `Patients` roster title, KPIs, and clinical table columns (`CDM Diagnosis & Rx` for `SlainteGP`, `Pre-Op Clearance & Meds` for `SlainteDent`, `Active Regimen & Rx-Guard` for `SlaintePharm`, `Physiological Load & Vitals` for `SlainteSport`, `Crew Bio-Telemetry` for `SlainteAstro`, and `Clinical Summary & Acuity` for `SlainteED`/`SlainteEMS`).
  - [x] **Minimalist Clinical UI System (`static/styles.css`)**: High-contrast, zero-motion-noise medical interface with semantic severity pills (`PASS` / `WARN` / `FAIL`) and proper `64px` sidebar/header alignment.

### Step 1.5: Production Clinical Write Workflows, Specialty Vertical Workspaces & Workstation UI Cleanup (Buckets A, B & C) ✅ COMPLETED
- [x] **Bucket A — Clinical Write Workflows on Individual Patient Records (End-to-End FHIR R4 Persistence)**:
  - [x] **A1. Prescribe Medication (`POST /fhir/Medications/<patient_id>/add` & `/status`)**: Inline `+ Prescribe` workflow on Patient Details with **live Agent 08 (`SlainteRx-Guard`) pre-flight contraindication interception** (blocks unsafe Beta-Lactam/NSAID/Sulfa orders unless clinician documents override reason), plus `Stop / Resume` status toggle on `MedicationRequest`s.
  - [x] **A2. Record Vital Signs (`POST /fhir/VitalSigns/<patient_id>/add` & `GET /fhir/News2Card/<patient_id>`)**: Inline `+ Record Vitals` workflow (`SBP`, `DBP`, `HR`, `SpO2`, `RR`, `Temp`, `Pain`) writing LOINC/UCUM `Observation`s to `SlainteFHIR` and refreshing both the Vital Signs trend charts and the 24-hour **NEWS2** deterioration score (`HX-Trigger: vitalsUpdated`).
  - [x] **A3. Add / Update Condition & Record Allergy (`POST /fhir/Conditions/<patient_id>/add`, `POST /fhir/Conditions/<patient_id>/status`, `POST /fhir/Allergies/<patient_id>/add`)**: SNOMED-CT clinical diagnosis & allergen pickers on Patient Details with ability to resolve/reopen conditions and record high/low criticality allergies.
  - [x] **A4. Clinical Consultation & Handover Notes (`GET/POST /fhir/Notes/<patient_id>`)**: Structured clinical note composer (`SOAP Consultation`, `ED Handover`, `Dental Operative Note`, `Pharmacist Intervention`, `Flight Surgeon / Sports Clearance`) persisted as HL7 FHIR R4 `DocumentReference` resources with practitioner attribution and audit logging.
- [x] **Bucket B — Interactive Specialty Workspaces for All 7 Vertical Cockpits (`/?view=insights` / `/fhir/Dashboard` + `/fhir/CockpitWorkspace`)**:
  - [x] **B1. `SlainteDent` (Dentist)**: Interactive **32-Tooth FDI Odontogram (11–48)** with clickable per-tooth status (`Sound`, `Carious`, `Restored`, `Endodontic`, `Crown`, `Extraction Planned`, `Missing`) + **6-Sextant BPE Periodontal Scorer (0–4*)** + Pre-Op Antibiotic/Anticoagulant clearance check persisted to FHIR R4 (`POST /fhir/Cockpit/dentist/save`).
  - [x] **B2. `SlaintePharm` (Pharmacy)**: Live **Clinical Prescription Dispensing Queue** aggregating active `MedicationRequest`s across the cohort with automatic `SlainteRx-Guard` contraindication flags, Irish GMS verification, and 1-click **Dispense Verified** / **Hold Rx** / **Re-Queue** actions (`POST /fhir/Cockpit/pharmacy/dispense`).
  - [x] **B3. `SlainteGP` (General Practice)**: Interactive **GP SOAP Consultation & Chronic Disease Management (CDM) Workspace** with patient selector, HbA1c/BP/eGFR target review, SOAP note filing (`POST /fhir/Cockpit/gp/soap`), and 1-click 28-day Repeat Prescription renewal (`POST /fhir/Cockpit/gp/renew`).
  - [x] **B4. `SlainteEMS` & `SlainteED` (Ambulance / Acute Resuscitation)**: High-contrast **Rapid Field ePCR Pre-Alert Console** directly on the cockpit for 10-second ambulance vital entry, instant deterministic MTS Cat 1–5 + NEWS2 calculation, and 1-click receiving ED FHIR R4 `Bundle` push (`POST /fhir/Cockpit/ems/epcr`).
  - [x] **B5. `SlainteSport` (Elite Sports) & `SlainteAstro` (Astronaut Health)**: Interactive **Squad Readiness / Crew Bio-Telemetry Clearance Board** displaying live HR, SpO2, BP, Temp, NEWS2 drift, and 1-click cryptographic **Return-to-Play (`SCAT6`) / EVA Medical Clearance (`Provenance`)** sign-off (`POST /fhir/Cockpit/clearance/<patient_id>`).
- [x] **Bucket C — Broken Controls Fix & Medical Workstation UI Cleanup**:
  - [x] **C1. Redesign `patient_details.html` Clinical Chart Header & Panel Toolbars**: Replaced legacy `--tropical-*` styles, oversized `150px` circle avatar, and redundant `"View ..."` buttons with a compact clinical patient banner (`clinical-monogram`, GMS ID, Provenance status badge) and clean header action buttons (`+ Prescribe`, `+ Record Vitals`, `+ Add Diagnosis`, `+ Record Allergy`, `+ File Note`, `Refresh`).
  - [x] **C2. Remove Double Card Borders in Clinical Fragments**: Cleaned up `medications.html`, `allergies.html`, `conditions.html`, `lab_results.html`, and `vital_signs.html` so tables sit flush inside their parent cards while preserving all clinical safety empty/error states.
  - [x] **C3. Wire Up Real Global Display Preferences (`settings_app.html` + `htmx-setup.js` + `styles.css`)**: Made `Clinical Font Size (100%/115%/130%)`, `High-Contrast Clinical Priority Mode`, and `Triage Queue Refresh Rate (5s/15s/30s/manual)` genuinely persist and apply across every page load and HTMX swap.
  - [x] **C4. Fix Dead `Pipeline Status` Button in `triage.html` & Unify Admin/Settings UI**: Replaced the deprecated `/pipeline/status` button on `Live Triage` with `+ Patient Intake` and `Agent 06: Ingestion`, included `intake_modal.html` in `base.html`, and aligned `/admin/users`, `/admin/audit`, and `/settings/*` headers/cards with the clinical workstation theme.

### Step 2: Phase 12 — `SlaintePages` Public Startup & Product Website (`SlainteTech AI Security Labs`)
- [ ] Build the Next.js App Router + Netlify + Docker marketing and product platform in `/home/adman-voids/Desktop/Code/SlaintePages` matching `SlainteDash` styling, featuring `/agents/*` (all 9 agents), `/verticals/*` (all 7 vertical cockpits), `/platform/mcp-guardrails`, and SEO + GEO (`public/llms.txt` + JSON-LD).

### Future Standalone Project (Deferred Post-Funding)
- [ ] **Phase 10 (Standalone Mobile/Laptop Patient App)**: Dedicated patient-facing mobile & web client sharing the `SlainteFHIR` backend.
