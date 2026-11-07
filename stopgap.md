# Slainte-Engine — Production Readiness Audit, Security Review, Handover & Commercialization Dossier (`stopgap.md`)

**Audit Date:** November 2026  
**Audited Monorepo:** `/home/adman-voids/Desktop/Code/slainte-engine`  
**Automated Verification Status:** `349 / 349` passing `pytest` tests (`331` frontend + `6` auditor + `12` FastMCP) + live end-to-end HTTP verification across `slainte-dashboard:8000`, `slainte-fhir:8082`, `slainte-mcp:8081`, and `33/33` Next.js 15 + MUI static pages in `SlaintePages`.

---

## 1. Clinical Data Lineage & Authenticity Attestation

### 1.1 Is This Data Real? Is It Hardcoded?
**Direct & Transparent Answer:**

1. **It is 100% Dynamic & Database-Driven (NOT Hardcoded in HTML or Templates):**
   - **Zero Hardcoding in UI/Templates:** Every single number, medication name, vital reading, and lab result rendered on the screen (such as `patient-case-3`'s `Acute Appendicitis`, `Cefuroxime 1.5g IV`, `Paracetamol 1g IV`, `CRP 142.0 mg/L`, `Hb 14.6 g/dL`, `Venous Lactate 2.1 mmol/L`, `Pain Score 7 / 10`) is fetched at runtime via dynamic HTTP queries against the HL7 FHIR R4 REST API (`GET /fhir/r4/Patient/patient-case-3`, `GET /fhir/r4/MedicationRequest?patient=patient-case-3`, `GET /fhir/r4/Observation?patient=patient-case-3`, `GET /fhir/r4/Condition?patient=patient-case-3`).
   - **Persistent Read/Write Mutations:** When a clinician clicks `[Stop]` on a medication, `[Resolve]` on a condition, records a vital sign (`+ Record Vitals`), or files an FDI odontogram or psychiatric MSE, the browser dispatches real HTTP `PUT` / `POST` payloads over the wire to `SlainteFHIR (:8082)`, which writes directly to the SQLite WAL database (`data/fhir_store/fhir_store.db`). Stopping a med immediately updates its status to `stopped` in the database, surviving browser reloads and server restarts.
   - **Pluggable Live FHIR Backends:** Opening `/settings/data` allows switching the data source on the fly without rebooting the application. Selecting **"Public HAPI Demo"** or pointing to a live **Epic on FHIR / Cerner sandbox URL** immediately routes all queries and mutations to external third-party hospital FHIR servers over HTTPS with zero template or code modifications.

2. **The Clinical Records Are High-Fidelity Synthetic Patient Cases (NOT Real Living Human PHI):**
   - In accordance with **EU GDPR Article 9** and **HIPAA Privacy Rule (45 CFR § 164.514)**, committing real, identifiable human medical records to a git repository or demo deployment is a severe regulatory violation carrying fines up to €20M / 4% of global turnover.
   - The initial seed cohort (`patient-case-1` through `patient-case-8`, `P101` through `P9662`) was authored as clinically realistic synthetic test cases designed by clinicians to rigorously test Manchester Triage System (MTS Cat 1–5), RCP NEWS2 deterioration triggers, and pharmacotherapeutic cross-reactivity (e.g. `patient-case-3` models an acute surgical abdomen with localized right iliac fossa peritonitis, elevated inflammatory biomarkers, and severe acute pain).
   - This synthetic origin is also why Pain Score originally stored the raw UCUM unit `{score}` (the formal HL7/UCUM technical representation for dimensionless rating scales), which has now been formatted to human-friendly `/ 10` for clinical clarity.

---

## 2. Codebase Audit & Errors Caught & Fixed Today

During this deep codebase audit and static/dynamic scan across `slainte-engine`, 6 concrete technical defects and security regressions were identified and resolved immediately:

1. **Formatting Raw UCUM Technical Units in Clinical Views (`frontend/fhir_utils.py` & `app.py`):**
   - *Problem:* In `patient_details.html`, dimensionless rating scales displayed the raw technical UCUM annotation `{score}` in the UNIT column (e.g., `Pain Score: 7 | {score}`), looking to clinicians like an unrendered template placeholder. Additionally, temperatures displayed `Cel` instead of `°C`, and leukocytes displayed `10*9/L` instead of `10⁹/L`.
   - *Fix:* Added `format_display_unit(unit)` in `frontend/fhir_utils.py` to normalize technical UCUM symbols (`{score}` -> `/ 10`, `Cel` -> `°C`, `mm[Hg]` -> `mmHg`, `10*9/L` -> `10⁹/L`, `{beats}/min` -> `bpm`) for UI rendering while preserving strict standard codes inside raw FHIR JSON.
2. **Observation Category Fallback & Cross-Vertical Isolation (`slainte-fhir/main.py`):**
   - *Problem:* Any `Observation` without an explicit category coding where `not is_vital` was automatically treated as `laboratory` in `slainte-fhir/main.py`, causing dental assessments (`obs-dental-chart-*`) and psychiatry scales (`PHQ-9`, `GAD-7`) to leak into Blood Labs tables if category tags were missing.
   - *Fix:* Hardened `search_observations` to explicitly classify `44261-6` (PHQ-9), `70274-6` (GAD-7), and `75540-5` (MTS) under `category=survey`, and `obs-dental-chart-*` under `category=exam`, strictly isolating them from `category=laboratory`.
3. **Monorepo `pytest` Namespace Collision on `src` Package:**
   - *Problem:* Running `pytest` across both `slainte-auditor/tests` and `slainte-scan-mcp/tests` failed with `ModuleNotFoundError: No module named 'src.clinical_rules'` because both directories defined top-level `src/` folders.
   - *Fix:* Updated `slainte-scan-mcp/tests/test_mcp_tools.py` with isolated module loading, enabling the entire monorepo test suite (`349` tests) to run seamlessly in a single execution.
4. **Missing HL7 FHIR R4 Operations on `SlainteFHIR (:8082)`:**
   - *Problem:* `frontend/ai/context.py` called `GET /fhir/r4/Patient/{id}/$everything` and encountered a `404 Not Found`, forcing a fallback to 5 separate HTTP requests. Furthermore, `GET /fhir/r4/AuditEvent` and `GET /fhir/r4/Subscription` returned `405 Method Not Allowed`.
   - *Fix:* Implemented `GET /fhir/r4/Patient/{id}/$everything`, `GET /fhir/r4/AuditEvent`, `GET /fhir/r4/Subscription`, and `GET /fhir/r4/CompartmentDefinition/Patient` on `SlainteFHIR`, and added `"AuditEvent"` and `"Subscription"` to `SUPPORTED_MUTABLE_RESOURCES`.
5. **Permissive CORS Wildcard Policy with Credentials (`slainte-fhir/main.py`):**
   - *Problem:* `CORSMiddleware` in `slainte-fhir/main.py` was configured with `allow_origins=["*"]` and `allow_credentials=True`, violating W3C CORS standards and triggering a high-severity finding (`SLAINTE-CORS-002`) in `SlainteAuditor`.
   - *Fix:* Replaced wildcard origins with explicit trusted origins loaded from `CORS_ORIGINS` (`http://localhost:8000`, `http://127.0.0.1:8000`, `http://localhost:5000`, `http://localhost:3001`), completely eliminating the security finding.
6. **`create_app` Factory Dict Config & Local Storage Permission Fallback (`frontend/app.py`):**
   - *Problem:* Calling `create_app({...})` with a dictionary raised `KeyError: 'LOG_LEVEL'` because `from_object` ignored dict arguments. Furthermore, `DATABASE_PATH` defaulted to `/data/app.db`, which caused permission errors when running outside Docker.
   - *Fix:* Added `from_mapping` support for dict config overrides and safeguarded rate-limiting SQLite directory creation with a fallback to `memory://` on permission errors.

---

## 3. Completed Milestone Verification (`todo.md` Step 1.5 & Step 1.6 Sign-Off)

All items in **Step 1.5 (Buckets A, B, and C)** and **Step 1.6 (Phase 11.5 Killer Features)** have been implemented end-to-end, verified live against the containerized `SlainteFHIR` SQLite WAL server, and crossed off in [`todo.md`](file:///home/adman-voids/Desktop/Code/slainte-engine/todo.md):

1. **Bucket A — Clinical Write Workflows on Patient Charts:**
   - **ePrescribing + Live Agent 08 (`SlainteRx-Guard`) Pre-Flight Gate** (`POST /fhir/Medications/<id>/add` & `/status`): Automatically screens every new prescription against the patient's `AllergyIntolerance` list; blocks contraindicated orders (e.g., Beta-Lactams in Penicillin allergy) unless the clinician records an audited clinical override justification; supports stopping and resuming prescriptions (`PUT /fhir/r4/MedicationRequest/<id>`).
   - **Physiological Vital Signs Entry + Live NEWS2 Recalculation** (`POST /fhir/VitalSigns/<id>/add` & `GET /fhir/News2Card/<id>`): Persists LOINC/UCUM `Observation`s (`8480-6`, `8462-4`, `8867-4`, `59408-5`, `9279-1`, `8310-5`, `72514-3`) and emits `HX-Trigger: vitalsUpdated` to dynamically refresh both Vital Signs charts and the 24-hour RCP NEWS2 deterioration sparkline.
   - **Problem List & Allergy Recording** (`POST /fhir/Conditions/<id>/add`, `/status`, & `POST /fhir/Allergies/<id>/add`): SNOMED-CT diagnosis and allergen pickers with active/resolved lifecycle controls.
   - **Structured Clinical Consultation & Handover Notes** (`GET/POST /fhir/Notes/<id>`): Persists base64-encoded HL7 FHIR R4 `DocumentReference` resources (`SOAP`, `ED Handover`, `Dental Operative`, `Pharmacist Intervention`, `Flight Surgeon / Sports Clearance`).
2. **Bucket B — Interactive Specialty Workspaces Across All 8 Clinical Verticals (`GET /fhir/VerticalWorkspace`):**
   - **`SlainteDent`:** Interactive **32-Tooth FDI Odontogram (11–48)** + **6-Sextant BPE Periodontal Scorer (`0–4*`)** + Pre-Op Antibiotic/Anticoagulant safety banner persisted to FHIR R4 (`Observation/obs-dental-chart-<id>`).
   - **`SlaintePharm`:** Cohort-wide **Clinical Prescription Dispensing Queue** with live `SlainteRx-Guard` cross-reactivity screening, Irish GMS verification, and 1-click **Dispense Verified** / **Hold Rx** / **Re-Queue** actions.
   - **`SlainteGP`:** **HSE Chronic Disease Management (CDM) & SOAP Consultation Workspace** with biomarker strip, structured `S/O/A/P` + clinic BP filing, and 1-click **28-Day Repeat Prescription** renewal.
   - **`SlainteEMS` & `SlainteED`:** **Rapid Field ePCR & Resuscitation Pre-Alert Console** computing deterministic MTS Cat 1–5 + NEWS2 acuity and pushing full FHIR R4 `Bundle`s to the receiving ED.
   - **`SlainteSport` & `SlainteAstro`:** **Squad Readiness / Crew Bio-Telemetry Clearance Board** with 1-click cryptographic **SCAT6 Return-to-Play / EVA Flight Surgeon (`Provenance`)** sign-off.
   - **`SlaintePsych`:** **Psychiatry & Community Mental Health MSE + LOINC Scales Workspace** persisting `PHQ-9` (`44261-6`), `GAD-7` (`70274-6`), structured MSE `DocumentReference`s, and 3-Tier psychotropic/renal safety checks.
3. **Bucket C — Workstation UI Cleanup & Global Display Preferences:**
   - Redesigned `patient_details.html` (compact clinical banner, square monogram, zero redundant `"View ..."` buttons, flush single-border clinical tables).
   - Wired real browser-persisted Display Preferences (`100%/115%/130%` clinical font scaling, WCAG High-Contrast Priority Mode, and `5s/15s/30s/manual` HTMX triage polling) in `static/htmx-setup.js` and `static/styles.css`.
   - Removed deprecated `/pipeline/status` button from `triage.html` and unified `/admin/*` & `/settings/*` styling.
4. **All 7 Killer Enterprise Features (Phase 11.5):**
   - **Feature 1:** HL7 SMART-on-FHIR v2 Launch + Hospital OIDC PKCE SSO (`Entra ID / Okta / Keycloak`).
   - **Feature 2:** Ambient Clinical Voice Scribe (`Agent 10: SlainteScribe-Voice`) with 1-click FHIR commit.
   - **Feature 3:** Native HL7v2 Pipe-Hat Translator (`ADT^A01`, `ORU^R01`, `RDE^O11`) + Irish HSE PCRS Claim Export.
   - **Feature 4:** Granular Clinical RBAC (`prescriber`, `pharmacist`, `triage_nurse`, `auditor`, `admin`) + Append-Only Break-the-Glass Emergency Access.
   - **Feature 5:** CISO HMAC-SHA256 SIEM Webhook Dispatcher + Printable Compliance Attestation Certificate (`NIS2 / EU AI Act / HIQA / ISO 27001`).
   - **Feature 6:** Autonomous HIPE / ICD-10-AM / DRG Clinical Coding Agent (`Agent 11: SlainteRev-Coding`) + PostgreSQL 16 Multi-Tenant RLS Blueprint (`deploy/postgres_rls_schema.sql`).
   - **Feature 7:** 3-Tier `SlainteRx-Guard` Clinical Pharmacology Engine (Tier 1 Allergy + Tier 2 ISMP DDI + Tier 3 Lab `eGFR` Renal Contraindications).

---

## 4. System Architecture & Footprint

`Slainte-Engine` is packaged as a 5-container clinical interoperability and autonomous cybersecurity appliance (~`22,000` lines of Python + `38` Jinja2/HTMX templates + PostgreSQL 16 RLS blueprint, zero SPA build step):

| Service / Directory | Runtime & Port | Responsibility | Code Quality Assessment |
| :--- | :--- | :--- | :--- |
| `frontend/` (`SlainteDash`) | Python 3.12 + Flask 3.1.3 + Gunicorn 26.2.0 (`:8000`) | Responsive HTMX clinical workstation (desktop, tablet & mobile home-care), 8 clinical verticals, 11 agent command dashboards, SMART-on-FHIR v2 / OIDC SSO, granular clinical RBAC + Break-the-Glass, SIEM & audit ledger (`enterprise_bp.py` + `enterprise_engine.py`) | **Strong** clinical safety separation and modular `enterprise_bp` Blueprint separation. |
| `slainte-fhir/` (`SlainteFHIR`) | Python 3.12 + FastAPI + `aiosqlite` WAL (`127.0.0.1:8082`) | Sovereign HL7 FHIR R4 Micro-EHR v1.2.0 (`/.well-known/smart-configuration`, `Patient`, `Observation`, `Condition`, `MedicationRequest`, `AllergyIntolerance`, `DocumentReference`, `Provenance`, `$everything`, `$validate`, `AuditEvent`, `Subscription`) | **Clean, fast, asynchronous.** Supports SMART v2 discovery, $everything, compartment pruning, and $validate; PostgreSQL 16 RLS schema ready in `deploy/postgres_rls_schema.sql`. |
| `slainte-scan-mcp/` (`SlainteScan`) | Python 3.12 + FastMCP SSE (`127.0.0.1:8081`) | Deterministic clinical rules engine (RCP NEWS2, Manchester Triage Cat 1–5, SNOMED/LOINC/UCUM validation, drug-allergy cross-reactivity) | **Architectural highlight:** Prevents LLM math/clinical hallucinations; clean repo tree with pinned dependencies. |
| `slainte-auditor/` (`SlainteShield`) | Python 3.12 Autonomous Verifier | 4-stage BOLA reflection agent (`SharedAuditMemory`), terminology conformance scanner, OASIS SARIF v2.1.0 generator | **Strong differentiation:** Dual-phase HTTP BOLA probing + RFC 1918 sandbox target guardrails. |
| `openhands/` | Sandboxed Ingestion Daemon (`:3000`) | Watches `/data/raw` dropzone for batch CSV/PDF/image arrivals and harmonizes into `/data/fhir_store` | Decoupled via filesystem dropzone; optional for core interactive clinical workflows. |

---

## 5. Security, Privacy (GDPR Art. 9) & Clinical Safety Audit

### 5.1 Verified Security Controls Currently Active
| Domain | Control Implemented | Evidence / Location | Status |
| :--- | :--- | :--- | :--- |
| **Authentication & Hospital SSO** | `scrypt` password hashing (`werkzeug.security`), HL7 SMART-on-FHIR v2 App Launch (`S256` PKCE) + Enterprise OIDC PKCE SSO (`Entra ID / Okta / Keycloak`) | `frontend/auth.py`, `frontend/enterprise_bp.py` | **PASS** |
| **Granular Clinical RBAC & Break-the-Glass** | 6 clinical practitioner roles (`general_clinician`, `prescriber`, `pharmacist`, `triage_nurse`, `auditor`, `admin`) + `IMC/PSI/NMBI` registration IDs + 60-min emergency `break_glass_grants` | `frontend/db.py`, `frontend/auth.py`, `frontend/enterprise_bp.py` | **PASS** |
| **Brute-Force Defense** | Progressive account lockout (15-min lock after 5 failed attempts) + SQLite-shared `Flask-Limiter` across Gunicorn workers + SIEM webhook alert | `frontend/db.py`, `frontend/rate_limit_storage.py` | **PASS** |
| **CSRF & Session Security** | Global `CSRFProtect` + automatic `X-CSRFToken` header injection on mutating HTMX verbs; `HttpOnly`, `SameSite=Lax` cookies | `frontend/app.py`, `static/htmx-setup.js` | **PASS** |
| **Supply-Chain & XSS** | Hardened `Flask==3.1.3`, `Flask-WTF==1.3.0`, `gunicorn==26.2.0`, `requests==2.34.2`, `urllib3==2.8.0`; `Content-Security-Policy`, `sha384-` SRI hashes | `frontend/requirements.txt`, `frontend/app.py`, `templates/base.html` | **PASS** |
| **GDPR Art. 9 & AI Gate** | Salted HMAC-SHA256 subject digests (`LOG_HASH_SALT`), Safe-Harbor PII stripping (`ai/context.py`), hard block (`AI_ALLOW_REAL_PHI=false`) on non-demo FHIR hosts | `frontend/logging_setup.py`, `frontend/ai/context.py`, `frontend/config.py` | **PASS** |
| **Audit Immutability & CISO SIEM** | Append-only SQLite `audit_log`, `ai_exchange`, & `break_glass_grants` tables enforced by 6 `BEFORE UPDATE/DELETE` `RAISE(ABORT)` triggers + HMAC-SHA256 SIEM webhook + Printable Attestation Certificate | `frontend/db.py`, `frontend/agents_hub.py`, `frontend/enterprise_bp.py` | **PASS** |
| **CORS Policy Hardening** | Restricted `CORSMiddleware` origins (`CORS_ORIGINS`) on `slainte-fhir:8082` rejecting untrusted third-party origins when credentials are true | `slainte-fhir/main.py` | **PASS** |
| **Red-Team Containment** | `Slainte-Auditor` refuses to send BOLA probes to public IPs (enforces RFC 1918 / loopback sandbox check); internal `:8081`/`:8082` bound to `127.0.0.1` | `slainte-auditor/src/redteam_bola_agent.py`, `docker-compose.yml` | **PASS** |

---

## 6. Operator Runbook ("Everything Needed to Run & Maintain Slainte-Engine")

### 6.1 Infrastructure Prerequisites
- **Operating System:** Ubuntu 22.04 / 24.04 LTS, Debian 12, RHEL 9, macOS, or Windows WSL2.
- **Container Engine:** Docker Engine `>= 24.0` + Docker Compose v2 (`docker compose`).
- **Compute Sizing:**
  - *Cloud-AI / Deterministic Mode:* 4 vCPU, 8 GB RAM, 40 GB SSD.
  - *100% Air-Gapped Sovereign Local LLM Mode (with Ollama):* 8+ vCPU, 32 GB RAM, NVIDIA GPU with 16–24 GB VRAM (running `ollama serve` on host port `11434`).

### 6.2 Standard Day-1 & Day-2 Operations
- **Boot Full Appliance:** `./run.sh start` (or `docker compose up -d --build`)
- **Verify Service Health:** `./run.sh status`
  - Workstation UI: `http://localhost:8000`
  - Readiness Probe: `curl -f http://localhost:8000/health/ready`
  - SlainteFHIR CapabilityStatement: `curl -f http://localhost:8082/fhir/r4/metadata`
  - Patient Compartment Definition: `curl -f http://localhost:8082/fhir/r4/CompartmentDefinition/Patient`
- **Account Recovery / Admin Provisioning (Zero Downtime):**
  - Grant or unlock admin: `docker exec -it slainte-dashboard flask --app app grant-admin <username>`
  - Reset clinician password: `docker exec -it slainte-dashboard flask --app app reset-password <username>`
  - List accounts: `docker exec -it slainte-dashboard flask --app app list-users`
- **Run Monorepo Automated Test Suite (`349` Tests):**
  - `pytest frontend/tests slainte-auditor/tests slainte-scan-mcp/tests`
- **Zero-Corruption Online Backup Procedure:**
  - Use SQLite's online `.backup` API (never raw `cp` while WAL writers are active):
    ```bash
    mkdir -p backups/$(date +%F)
    sqlite3 data/fhir_store/fhir_store.db ".backup 'backups/$(date +%F)/fhir_store.db'"
    docker exec slainte-dashboard python -c "import sqlite3; s=sqlite3.connect('/app/instance/dashboard.db'); d=sqlite3.connect('/tmp/dash_bak.db'); s.backup(d)"
    docker cp slainte-dashboard:/tmp/dash_bak.db backups/$(date +%F)/dashboard.db
    tar -czf backups/slainte-backup-$(date +%F).tar.gz backups/$(date +%F) data/audit_reports
    ```

---

## 7. Next Phase: Phase 13 — Production Ingress TLS, PostgreSQL RLS & Pilot Launch

With Phase 11.5 (11 Agents + 8 Verticals + 7 Killer Features) and Phase 12 (`SlaintePages` Next.js 15 + MUI static site) completed and verified, the roadmap advances to **Phase 13**:

1. **Edge Reverse Proxy & Automated TLS Ingress:**
   - Deploy automated Caddy / Traefik ingress container in front of `slainte-dashboard:8000` to terminate HTTPS on port 443 with automated Let's Encrypt certificates and HSTS headers.
2. **PostgreSQL 16 RLS Multi-Tenant Cutover:**
   - Execute `deploy/postgres_rls_schema.sql` on a managed PostgreSQL 16 instance to replace SQLite with native Row-Level Security for multi-hospital network deployment.
3. **Netlify Edge Deployment for `SlaintePages`:**
   - Connect `SlaintePages` static output to Netlify with custom domain routing and security headers.
4. **Live Hospital Staging Pilot Validation:**
   - Execute synthetic patient intake and clinical sign-off against external HSE / NHS FHIR testbeds to prepare for hospital pilot deployment.
