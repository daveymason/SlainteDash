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
  - [x] Unified `/settings/ai` Model Selector (`POST /settings/ai/select`) supporting Local Sovereign Ollama models (`k9/lime:latest`, `k9/lime-lite:latest`, `k9/Doggo:3b`, `k9/chihuahua:latest`, `recordstore:latest`, `gemma3:1b`) and Cloud Frontier model (`openai/gpt-6.1-luna`) backed by `OPENAI_API_KEY` in `.env`.
  - [x] Added **Generate AI Bedside Briefing** (`POST /ai/summarise/<patient_id>`) on the Patient Details view grounded in deterministic NEWS2 and drug-allergy checks and logged to `ai_exchange`.

---

## Active Final Phases (Execution Order) 🚀

### Step 1: Phase 11 + Phase 9 Lite (Unified) — The 11-Agent Command Center & 8 "Sign in as..." Clinical Verticals ✅ COMPLETED
*(Executed first so the Security, GDPR, Vulnerability, and Audit agents inspect all 8 vertical role boundaries.)*

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
- [x] **"Sign in as..." 8 Role-Based Clinical Verticals, Vertical-Adaptive `Patients` Roster & Responsive Mobile/Tablet Medical UI**:
  - [x] **De-duplicated Header & Vertical-Aware Sidebar**: Removed duplicate logos/badges and legacy status buttons from the header; removed `Pipeline Status` from the sidebar; restricted `Live Triage` in the sidebar exclusively to acute verticals (`SlainteED` & `SlainteEMS`); eliminated `"Cockpit"` terminology in favor of `"Vertical"` across the entire UI.
  - [x] **Vertical-Adaptive `Patients` Roster (`/fhir/Patients`) & 8th Vertical `SlaintePsych` (`psychiatry`)**: Switching verticals dynamically adapts the `Patients` roster title, KPIs, and clinical table columns across all 8 verticals (`SlainteED`, `SlainteGP`, `SlaintePsych` Psychiatry MSE + LOINC `44261-6` PHQ-9 / `70274-6` GAD-7, `SlainteDent`, `SlaintePharm`, `SlainteEMS`, `SlainteSport`, `SlainteAstro`).
  - [x] **Responsive Mobile, Tablet & Minimalist Clinical UI System (`static/styles.css` + `static/htmx-setup.js`)**: Off-canvas touch navigation drawer (`< 992px`), sticky mobile bottom quick-dock (`Triage`, `Patients`, `Vertical`, `Agents`, `Menu`), `44px` coarse-pointer touch targets for Care-at-Home Nurses and Ambulance tablet crews, and WCAG 2.2 AA contrast.

### Step 1.5: Production Clinical Write Workflows, Specialty Vertical Workspaces & Workstation UI Cleanup (Buckets A, B & C) ✅ COMPLETED
- [x] **Bucket A — Clinical Write Workflows on Individual Patient Records (End-to-End FHIR R4 Persistence)**:
  - [x] **A1. Prescribe Medication (`POST /fhir/Medications/<patient_id>/add` & `/status`)**: Inline `+ Prescribe` workflow on Patient Details with **live Agent 08 (`SlainteRx-Guard`) pre-flight contraindication interception** (blocks unsafe Beta-Lactam/NSAID/Sulfa orders unless clinician documents override reason), plus `Stop / Resume` status toggle on `MedicationRequest`s.
  - [x] **A2. Record Vital Signs (`POST /fhir/VitalSigns/<patient_id>/add` & `GET /fhir/News2Card/<patient_id>`)**: Inline `+ Record Vitals` workflow (`SBP`, `DBP`, `HR`, `SpO2`, `RR`, `Temp`, `Pain`) writing LOINC/UCUM `Observation`s to `SlainteFHIR` and refreshing both the Vital Signs trend charts and the 24-hour **NEWS2** deterioration score (`HX-Trigger: vitalsUpdated`).
  - [x] **A3. Add / Update Condition & Record Allergy (`POST /fhir/Conditions/<patient_id>/add`, `POST /fhir/Conditions/<patient_id>/status`, `POST /fhir/Allergies/<patient_id>/add`)**: SNOMED-CT clinical diagnosis & allergen pickers on Patient Details with ability to resolve/reopen conditions and record high/low criticality allergies.
  - [x] **A4. Clinical Consultation & Handover Notes (`GET/POST /fhir/Notes/<patient_id>`)**: Structured clinical note composer (`SOAP Consultation`, `ED Handover`, `Dental Operative Note`, `Pharmacist Intervention`, `Flight Surgeon / Sports Clearance`) persisted as HL7 FHIR R4 `DocumentReference` resources with practitioner attribution and audit logging.
- [x] **Bucket B — Interactive Specialty Workspaces for All 8 Clinical Verticals (`/?view=insights` / `/fhir/Dashboard` + `/fhir/VerticalWorkspace`)**:
  - [x] **B1. `SlainteDent` (Dentist)**: Interactive **32-Tooth FDI Odontogram (11–48)** with clickable per-tooth status (`Sound`, `Carious`, `Restored`, `Endodontic`, `Crown`, `Extraction Planned`, `Missing`) + **6-Sextant BPE Periodontal Scorer (0–4*)** + Pre-Op Antibiotic/Anticoagulant clearance check persisted to FHIR R4 (`POST /fhir/Vertical/dentist/save`).
  - [x] **B2. `SlaintePharm` (Pharmacy)**: Live **Clinical Prescription Dispensing Queue** aggregating active `MedicationRequest`s across the cohort with automatic `SlainteRx-Guard` contraindication flags, Irish GMS verification, and 1-click **Dispense Verified** / **Hold Rx** / **Re-Queue** actions (`POST /fhir/Vertical/pharmacy/dispense`).
  - [x] **B3. `SlainteGP` (General Practice & Community Nursing)**: Interactive **GP SOAP Consultation & Chronic Disease Management (CDM) Workspace** with patient selector, HbA1c/BP/eGFR target review, SOAP note filing (`POST /fhir/Vertical/gp/soap`), and 1-click 28-day Repeat Prescription renewal (`POST /fhir/Vertical/gp/renew`).
  - [x] **B4. `SlainteEMS` & `SlainteED` (Ambulance / Acute Resuscitation)**: High-contrast **Rapid Field ePCR Pre-Alert Console** directly on the vertical workspace for 10-second ambulance vital entry, instant deterministic MTS Cat 1–5 + NEWS2 calculation, and 1-click receiving ED FHIR R4 `Bundle` push (`POST /fhir/Vertical/ems/epcr`).
  - [x] **B5. `SlainteSport` (Elite Sports) & `SlainteAstro` (Astronaut Health)**: Interactive **Squad Readiness / Crew Bio-Telemetry Clearance Board** displaying live HR, SpO2, BP, Temp, NEWS2 drift, and 1-click cryptographic **Return-to-Play (`SCAT6`) / EVA Medical Clearance (`Provenance`)** sign-off (`POST /fhir/Vertical/clearance/<patient_id>`).
  - [x] **B6. `SlaintePsych` (Psychiatry & Community Mental Health)**: Interactive **Mental State Examination (MSE) & LOINC Rating Scale Workspace** persisting `PHQ-9` (`44261-6`) & `GAD-7` (`70274-6`) `Observation`s, structured MSE `DocumentReference`s, and 3-Tier `SlainteRx-Guard` psychotropic/renal screening (`POST /fhir/Vertical/psychiatry/assess`).
- [x] **Bucket C — Broken Controls Fix & Medical Workstation UI Cleanup**:
  - [x] **C1. Redesign `patient_details.html` Clinical Chart Header & Panel Toolbars**: Replaced legacy `--tropical-*` styles, oversized `150px` circle avatar, and redundant `"View ..."` buttons with a compact clinical patient banner (`clinical-monogram`, GMS ID, Provenance status badge) and clean header action buttons (`+ Prescribe`, `+ Record Vitals`, `+ Add Diagnosis`, `+ Record Allergy`, `+ File Note`, `Refresh`).
  - [x] **C2. Remove Double Card Borders in Clinical Fragments**: Cleaned up `medications.html`, `allergies.html`, `conditions.html`, `lab_results.html`, and `vital_signs.html` so tables sit flush inside their parent cards while preserving all clinical safety empty/error states.
  - [x] **C3. Wire Up Real Global Display Preferences (`settings_app.html` + `htmx-setup.js` + `styles.css`)**: Made `Clinical Font Size (100%/115%/130%)`, `High-Contrast Clinical Priority Mode`, and `Triage Queue Refresh Rate (5s/15s/30s/manual)` genuinely persist and apply across every page load and HTMX swap.
  - [x] **C4. Fix Dead `Pipeline Status` Button in `triage.html` & Unify Admin/Settings UI**: Replaced the deprecated `/pipeline/status` button on `Live Triage` with `+ Patient Intake` and `Agent 06: Ingestion`, included `intake_modal.html` in `base.html`, and aligned `/admin/users`, `/admin/audit`, and `/settings/*` headers/cards with the clinical workstation theme.

### Step 1.6 (Phase 11.5): The 7 Killer Enterprise Features & 11-Agent Platform Pack ✅ COMPLETED
*(Implemented and verified live before Phase 12 `SlaintePages` so the public website launches showcasing the complete hospital-grade 11-Agent Enterprise Platform.)*

- [x] **Killer Feature 1 — HL7 SMART-on-FHIR v2 App Launch & Enterprise OIDC SSO (`Entra ID / Okta / Keycloak`)**:
  - [x] Expose `GET /.well-known/smart-configuration` and `GET /fhir/r4/.well-known/smart-configuration` on `SlainteFHIR (:8082)` + `/.well-known/smart-configuration` & `/smart/.well-known/smart-configuration` on `SlainteDash`.
  - [x] Implement HMAC-SHA256 signed SMART EHR Launch (`/smart/launch`, `/smart/authorize`, `/smart/token`, `/smart/introspect`, `/smart/callback`, `POST /smart/simulate`), OIDC PKCE SSO (`/auth/oidc/login`, `/auth/oidc/callback`), and the dedicated **SMART-on-FHIR & Hospital SSO Hub (`/settings/smart`)** with 1-click Epic/Cerner Patient Context Launch Simulator.
- [x] **Killer Feature 2 — `Agent 10: SlainteScribe-Voice` (Ambient Clinical Voice Scribe & Pre-Screened FHIR Order Drafting)**:
  - [x] Register **Agent 10 (`ambient_scribe` — `SlainteScribe-Voice`)** with dedicated `/agents/ambient_scribe` operational dashboard + inline **Ambient Voice Scribe** consultation panel on `patient_details.html` and `SlainteGP`.
  - [x] Support browser Web Speech API live dictation, audio upload (Whisper when configured), and Irish consultation presets -> structured **SOAP `DocumentReference` + SNOMED/ICD-10 `Condition` candidates + Draft `MedicationRequest`s** pre-screened through 3-Tier `SlainteRx-Guard`, with **1-Click Approve & Commit to FHIR R4** (`POST /enterprise/scribe/process` & `POST /enterprise/scribe/commit/<patient_id>`).
- [x] **Killer Feature 3 — Native HL7v2 (`ADT^A01`, `ORU^R01`, `RDE^O11`) Pipe-Hat Translator & HSE PCRS GMS Claim Export**:
  - [x] Deterministic Python **HL7v2 (`MSH|PID|PV1|AL1|DG1|OBR|OBX|RXE`) -> HL7 FHIR R4 `Bundle` Translator** (`POST /enterprise/hl7v2/ingest`) embedded in **Agent 06 (`SlainteEngine-Ingest`)** with realistic Irish hospital PAS/LIS sample streams.
  - [x] **HSE PCRS (Primary Care Reimbursement Service) GMS Monthly Claim Export** (`GET /enterprise/pcrs/export`) accessible from `SlaintePharm` and `SlainteGP`.
- [x] **Killer Feature 4 — Granular Clinical RBAC (`prescriber`, `pharmacist`, `triage_nurse`, `auditor`, `admin`) & Immutable "Break-the-Glass" Emergency Access**:
  - [x] Add `clinical_role` & `registration_id` (`IMC/PSI/NMBI`) to `users` (manageable in `/admin/users`) enforcing clinical separation of duties across prescribing, pharmacy dispensing, and diagnosis authoring.
  - [x] Add append-only `break_glass_grants` SQLite table with kernel immutability triggers (`BEFORE UPDATE/DELETE`), **Break-the-Glass Emergency Override** modal (`POST /enterprise/break-glass/<patient_id>`) granting 60-minute audited emergency access, and live telemetry on **Agent 04 (`SlainteGov-GDPR`)** & **Agent 05 (`SlainteGov-Audit`)**.
- [x] **Killer Feature 5 — CISO SIEM Webhook Dispatcher & Printable `NIS2 / EU AI Act / HIQA / ISO 27001` Compliance Attestation Certificate**:
  - [x] HMAC-SHA256 signed (`X-Slainte-Signature`) SIEM security webhook dispatcher (`SIEM_WEBHOOK_URL` for Sentinel / Splunk / PagerDuty) triggered on account lockouts, Break-the-Glass overrides, high-risk Rx overrides, and `/enterprise/siem/test`.
  - [x] Print-optimized (`@media print`) **Executive Cybersecurity, GDPR & EU AI Act Compliance Attestation Certificate (`GET /agents/compliance-certificate`)** dynamically computed from live Agent 01–05 telemetry + SHA-256 verification digest.
- [x] **Killer Feature 6 — `Agent 11: SlainteRev-Coding` (Autonomous HIPE / ICD-10-AM / SNOMED Clinical Coding & Revenue Audit) + PostgreSQL Multi-Tenant RLS Schema**:
  - [x] Register **Agent 11 (`clinical_coding` — `SlainteRev-Coding`)** with dedicated `/agents/clinical_coding` dashboard + inline Patient Chart coding scanner checking labs/vitals (`eGFR < 60`, `HbA1c >= 48`, `Troponin > 50`, `Lactate >= 2.0`, `SpO2 <= 91%`, `SBP >= 160`) against active `Condition`s to catch uncoded comorbidities, show estimated Irish HIPE DRG uplift (`€`), and apply dual-coded SNOMED + ICD-10-AM `Condition`s in 1 click (`POST /enterprise/coding/apply/<patient_id>`).
  - [x] Create `deploy/postgres_rls_schema.sql` providing the production PostgreSQL 16 `JSONB` + GIN + Row-Level Security (`FORCE ROW LEVEL SECURITY`) multi-tenant hospital schema.
- [x] **Killer Feature 7 — 3-Tier `SlainteRx-Guard` Clinical Pharmacology Engine (Allergy + High-Alert DDI + Lab `eGFR` Renal Dosing Gate)**:
  - [x] Upgrade `SlainteRx-Guard` (`POST /fhir/Medications/<id>/add`, `POST /ai/crosscheck/<id>`, `SlaintePharm` Dispensing Queue, `Agent 10`, and `/agents/medication_safety`) to screen **Tier 1** Drug-Allergy cross-reactivity, **Tier 2** ISMP High-Alert Drug-Drug Interactions (`Clarithromycin+Statin`, `NSAID+Anticoagulant`, `ACEi+Spironolactone`, `Warfarin+Metronidazole`, `Opioid+Benzodiazepine`, `ACEi+NSAID`), and **Tier 3** FHIR Lab `eGFR` & Potassium Renal Contraindications (`Metformin` at `eGFR < 45`/`< 30`, `NSAID` at `eGFR < 60`, hyperkalaemia gate).

### Step 2: Phase 12 — `SlaintePages` Public Startup & Product Website (`SlainteTech AI Security Labs`) ✅ COMPLETED
- [x] **Phase 12A & 12B — Next.js 15 + Material UI (`@mui/material` v6) Static Public Platform (`SlaintePages` & `public-site/`)**:
  - [x] Built **11 SEO-rich `/health-tech-agents/<agent-real-name>/` pages** sharing a single reusable canonical MUI template (`AgentCanonicalTemplate.tsx`), each featuring a bespoke FastMCP architecture SVG, 3-column deterministic capabilities, a **full-width Vertical Use Case Page Break** linked directly to its matching Vertical page, an HL7 FHIR R4 technical spec table, and a **bottom 3-column solution grid of the other 10 agents**.
  - [x] Built **8 visually distinct `/verticals/<domain>/` pages** (`emergency-departments`, `general-practice`, `psychiatry`, `dentistry`, `pharmacy`, `ambulance-ems`, `sports-medicine`, `astronaut-health`), each with its own WCAG 2.2 AA verified color palette, custom SVG illustration (`VerticalUniqueGraphic`), mobile/tablet Care-at-Home & Ambulance readiness callout, and executive ROI brief.
  - [x] Built complete startup sitemap (`/`, `/platform/`, `/health-tech-agents/`, `/verticals/`, `/security-compliance/`, `/pricing/`, `/investors/`, `/docs/`, `/about/`, `/contact/`, `/llms.txt`) passing WCAG 2.2 AA contrast, heading hierarchy, zero `"cockpit"` wording, and 100% link integrity.

### Step 3: Phase 12.5 — Monorepo Consolidation & Agentic Plumbing (Option A) ✅ COMPLETED
*(Detailed technical roadmap: [Monorepo Consolidation Plan](file:///home/adman-voids/.gemini/antigravity/brain/d2792fde-88d2-4d0b-833f-7c997c4a9b3f/monorepo_consolidation_plan.md))*

- [x] **1. Unified `agents/` Package & Fleet Re-alignment**:
  - [x] Created `slainte-engine/agents/` with `base.py` (`BaseAgent` abstract class) and `registry.py` (master 11-agent metadata catalog).
  - [x] Consolidated **Governance Fleet (01–05)** into `agents/governance/` (`bola_redteam.py`, `fhir_conformance.py`, `cve_vulnerability.py`, `gdpr_privacy.py`, `immutable_audit.py`).
  - [x] Consolidated **Clinical Fleet (06–11)** into `agents/clinical/` (`multimodal_ingest.py`, `patient_summariser.py`, `medication_safety.py`, `acuity_triage.py`, `ambient_scribe.py`, `clinical_coding.py`).
  - [x] Backward-compatible proxy bridge in `frontend/agents_hub.py`.
- [x] **2. Modularize `frontend/app.py` (~4,040 LOC) into Flask Blueprints**:
  - [x] Split monolithic route handlers into `frontend/blueprints/` (`auth.py`, `patients.py`, `verticals.py`, `agents.py`, `intake.py`, `settings.py`, `common.py`, `__init__.py`). Reduced `app.py` from 4,040 LOC to 512 LOC.
  - [x] Eliminated `sys.path.insert()` dynamic import hacks; verified 100% route backwards compatibility without changing templates.
- [x] **3. Bring `SlaintePages` Next.js Source into Monorepo (`slainte-engine/website/`)**:
  - [x] Migrated `SlaintePages` Next.js 15 source into `slainte-engine/website/` and copied compiled static export to `slainte-engine/website/public-site/`.
- [x] **4. Unified Ingress TLS & Single Entrypoint (Caddy 2 Container)**:
  - [x] Added `deploy/Caddyfile` with automated internal/production TLS, HSTS, reverse proxying `/` to `slainte-dashboard:8000`, `/fhir/r4*` to `slainte-fhir:8082`, `/mcp*` to `slainte-mcp:8081` (with SSE streaming flush), and `/site*` to `/srv/website/public-site`.
  - [x] Integrated `slainte-ingress` service in `docker-compose.yml` with ports `80` and `443`.
  - [x] Added automated validation test suite `tests/test_ingress_caddy.py` (342/342 passing tests across repo).

### Step 3.5: Unified Single-Architecture Simplification & Agent Fleet Expansion (12–16) ✅ COMPLETED
*(Consolidated multi-tier execution fragmentation into 1 standard `BaseAgent` architecture + built 5 requested agents, pending human review)*

- [x] **Unified Single Agent Architecture (`BaseAgent` + `agents/runner.py` + `agents/cli.py`)**:
  - [x] Retired multi-tier runtime fragmentation (separate OpenHands container shell loops and bespoke auditor scripts) in favor of the canonical `BaseAgent` Python architecture.
  - [x] Built `agents/runner.py`: Standard execution engine handling synchronous copilot invocations, background daemon loops, and batch sweeps through one typed interface (`AgentExecutionResult`).
  - [x] Built `agents/cli.py` & `agents/__main__.py`: Unified CLI (`python -m agents [list|run|health|audit]`) allowing operators and CI/CD pipelines to run any agent directly.
- [x] **New Agents Expansion (Agents 12–16) — Built & Verified**:
  - [x] **Agent 12 — Clinic Onboarding & Migration Agent (`SlainteGov-Onboard` — `/agents/clinic_onboarding`)**: Introspects raw practice dumps (CSV/HL7v2/PDF), maps unstandardized codes to LOINC/SNOMED-CT via MCP, and compiles verified Irish Core FHIR R4 Bundles.
  - [x] **Agent 13 — Discharge & Transfer Coordinator (`SlainteCare-Transfer` — `/agents/discharge_transfer`)**: Assesses physiological stability (NEWS2 <= 2), performs discharge medication reconciliation against documented allergies, and drafts structured primary care transfer summaries.
  - [x] **Agent 14 — Emergency Pre-Alert Agent (`SlainteEMS-Alert` — `/agents/ems_prealert`)**: Evaluates ambulance vital signs and complaints to determine Manchester Triage urgency (Cat 1–2) and dispatch real-time pre-arrival alerts with ETA to receiving Emergency Departments.
  - [x] **Agent 15 — Chronic Disease Surveillance Agent (`SlainteCare-CDM` — `/agents/chronic_surveillance`)**: Continuously audits diabetic, hypertensive, and CKD patient cohorts to surface overdue surveillance markers (HbA1c > 12m, eGFR drop, uncontrolled SBP >= 150 mmHg) for proactive GP intervention.
  - [x] **Agent 16 — EU NIS2 Directive & Continuous Compliance Auditor (`SlainteGov-NIS2` — `/agents/nis2_compliance`)**: Continuously audits hospital operational controls against EU Directive 2022/2555 (NIS2) Article 21, verifying SIEM dispatch readiness, supply-chain pin integrity, and cryptographic Provenance sign-offs.
  - [x] Enriched `AGENTS_CATALOG` in `agents/registry.py` from 11 to 16 agents; added concrete class dispatch in `get_agent_instance()`.
  - [x] Expanded test suite in `tests/test_agents_fleet.py` (344/344 passing tests across monorepo).

### Step 3.7: Phase 12.7 — Manual Human Review & UI/UX Audit across Dashboard & Public Site (Iteration 2) ✅ COMPLETED
- [x] **Live Patient Cohort Rendering & Offline Fallback**:
  - [x] Patched `DynamicFhirProxy` in `frontend/app.py` with 200ms socket probe on port 8082, automatically falling back to `LocalFhirStore` targeting `data/fhir_store/` in standalone workstation mode.
  - [x] Verified full cohort rendering (34 synthetic patients: Mary Walsh P101, Patrick Byrne P102, Declan Foley P113, etc.) with real vitals, active medications, allergies, problem list, and NEWS2 acuity scores.
- [x] **Classic Enterprise Bootstrap Aesthetic (2016 Medical Workstation Standard)**:
  - [x] Replaced playful rounded fonts (`Nunito`) with crisp native operating system UI fonts (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`).
  - [x] Standardized cards/panels to solid 4px border radius, 1px `#CBD5E1` clinical borders, `#F8FAFC` headers, and zero floaty glassmorphism or neon vibe-coding accents.
  - [x] Standardized padding (`p-3`, `p-4`), table line-heights, and crisp `#0F172A` high-contrast typography.
- [x] **Tactile Micro-Feedback & Interactive Hover States**:
  - [x] Enhanced `.btn` styles in `static/styles.css` with subtle micro-elevation (`translateY(-1px)`, `box-shadow: 0 2px 4px rgba(15, 23, 42, 0.12)`), inset click feedback, and 2px focus rings.
- [x] **Consistent Asynchronous Loading States & Spinners**:
  - [x] Implemented global `.htmx-indicator` rules and button loading states (`button.htmx-request { pointer-events: none; opacity: 0.75; }`) ensuring seamless, visible feedback during asynchronous searches and agent executions.
- [x] **Pixel-Perfect Screen Captures (With Live Clinical Data)**:
  - [x] Captured 11 high-resolution screenshots saved to `data/audit_reports/ui_screenshots/` with all clinical data fully loaded: Workstation Login, Patients Roster (15 active patients per page), Patient Details Chart (Mary Walsh P101), 16-Agent Fleet Hub, Agent 16 NIS2 Dashboard, Agent 08 Rx-Guard Gate, Acute Manchester Triage Board, and Public Next.js 15 pages.
- [x] **HTMX 4 & Bootstrap 6 Modernization Evaluation**:
  - [x] Detailed comprehensive technical evaluation in `stopgap.md` Section 8 outlining breaking changes, DOM morphing (Idiomorph), strict CSP nonces, CSS `@layer`, container queries, and native HTML5 `<dialog>`.

### Step 3.8: Phase 12.8 — Agent Interaction with UI Specification ✅ COMPLETED
- [x] **16-Agent UI Interaction Matrix**: Documented full interaction lifecycle (invocation trigger, computed output, and presentation format in UI) for all 16 agents in `PROJECT-PLAN.md`.
- [x] **Clean Agent Navigation Bar & Dropdown**:
  - [x] Updated `frontend/templates/header.html` dropdown to include all 16 agents neatly categorized into 3 semantic squads: *SlainteShield Security*, *SlainteGov Governance*, and *SlainteCare Bedside*.
  - [x] Built responsive, horizontally scrollable `agent-subnav` ribbon for 1-click lateral navigation across all 16 agent operational dashboards.
  - [x] Implemented dedicated interactive dashboard panels in `frontend/templates/agent_detail.html` for Agents 12, 13, 14, 15, and 16.

### Step 3.9: Phase 12.9 — Public Site Expansion & Enterprise Visuals ✅ COMPLETED
- [x] **16-Agent Expansion on Public Marketing Platform**: Expanded `website/src/data/agentsData.ts` to include all 16 agents; generated 38 static pages with zero build errors.
- [x] **Authentic Enterprise Healthcare Photography**: Downloaded, optimized, and integrated high-resolution clinical photography into `website/src/app/page.tsx` and `website/public-site/images/` showcasing multi-disciplinary rounds, bedside EHR consultation, trauma resuscitation, community care surveillance, and hospital cybersecurity SOC operations.

### Step 4: Phase 13 — Production Hardening, Multi-Tenant PostgreSQL 16 RLS Migration (Startup Free-Tier Strategy) & Pilot Launch 🚀
- [x] **External FHIR Sandbox Live Integration Testing**: Connected dynamic FHIR client (`/settings/data`) to external testbeds (HAPI FHIR R4 public demo, synthetic cohort intake, bidirectional write-back, and provenance signing). Verified live.
- [ ] **Multi-Tenant PostgreSQL 16 RLS Migration (Startup Free-Tier / Multi-Cloud Strategy)**:
  - [ ] Database host selection: Kept flexible between **Neon Serverless Postgres** (0.5 GB, native RLS, instant branching), **Supabase** (500 MB free PostgreSQL 16), **AWS RDS Free Tier**, or **IBM Cloud Startup Credits** (*Decision: To be finalized before cutover*).
  - [ ] Initial live pilot vertical lead: **SlainteED & SlainteEMS** (Acute Emergency Department and Ambulance Triage queue with real-time pre-alerts).
  - [ ] Connect selected free-tier PostgreSQL instance and execute `deploy/postgres_rls_schema.sql` (`FORCE ROW LEVEL SECURITY` across hospital trust boundaries, clinical roles, and patients).
  - [ ] Run high-concurrency benchmarks under multi-worker gunicorn.
- [ ] **Production Domain & Automated Public Ingress TLS**:
  - [ ] Purchase commercial domain (Target: `slaintetech.com` or `slainte.io`).
  - [ ] Point DNS A/AAAA records to Caddy ingress host for automated Let's Encrypt / ZeroSSL TLS certificates with automatic renewal.

### Future Standalone Project (Deferred Post-Funding)
- [ ] **Phase 10 (Standalone Mobile/Laptop Patient App)**: Dedicated patient-facing mobile & web client sharing the `SlainteFHIR` backend.
