# Slainte-Engine — Production Readiness Audit, Security Review, Handover & Commercialization Dossier (`stopgap.md`)

**Audit Date:** November 2026  
**Audited Monorepo:** `/home/adman-voids/Desktop/Code/slainte-engine`  
**Automated Verification Status:** `318 / 318` passing `pytest` tests + live end-to-end Docker verification across `slainte-dashboard:8000`, `slainte-fhir:8082`, and `slainte-mcp:8081`.

---

## 1. Completed Milestone Verification (`todo.md` Step 1.5 Sign-Off)

All items in **Step 1.5 (Buckets A, B, and C)** have been implemented end-to-end, verified live against the containerized `SlainteFHIR` SQLite WAL server, and crossed off in [`todo.md`](file:///home/adman-voids/Desktop/Code/slainte-engine/todo.md):

1. **Bucket A — Clinical Write Workflows on Patient Charts:**
   - **ePrescribing + Live Agent 08 (`SlainteRx-Guard`) Pre-Flight Gate** (`POST /fhir/Medications/<id>/add` & `/status`): Automatically screens every new prescription against the patient's `AllergyIntolerance` list; blocks contraindicated orders (e.g., Beta-Lactams in Penicillin allergy) unless the clinician records an audited clinical override justification; supports stopping and resuming prescriptions (`PUT /fhir/r4/MedicationRequest/<id>`).
   - **Physiological Vital Signs Entry + Live NEWS2 Recalculation** (`POST /fhir/VitalSigns/<id>/add` & `GET /fhir/News2Card/<id>`): Persists LOINC/UCUM `Observation`s (`8480-6`, `8462-4`, `8867-4`, `59408-5`, `9279-1`, `8310-5`, `72514-3`) and emits `HX-Trigger: vitalsUpdated` to dynamically refresh both Vital Signs charts and the 24-hour RCP NEWS2 deterioration sparkline.
   - **Problem List & Allergy Recording** (`POST /fhir/Conditions/<id>/add`, `/status`, & `POST /fhir/Allergies/<id>/add`): SNOMED-CT diagnosis and allergen pickers with active/resolved lifecycle controls.
   - **Structured Clinical Consultation & Handover Notes** (`GET/POST /fhir/Notes/<id>`): Persists base64-encoded HL7 FHIR R4 `DocumentReference` resources (`SOAP`, `ED Handover`, `Dental Operative`, `Pharmacist Intervention`, `Flight Surgeon / Sports Clearance`).
2. **Bucket B — Interactive Specialty Workspaces Across All 7 Vertical Cockpits (`GET /fhir/CockpitWorkspace`):**
   - **`SlainteDent`:** Interactive **32-Tooth FDI Odontogram (11–48)** + **6-Sextant BPE Periodontal Scorer (`0–4*`)** + Pre-Op Antibiotic/Anticoagulant safety banner persisted to FHIR R4 (`Observation/obs-dental-chart-<id>`).
   - **`SlaintePharm`:** Cohort-wide **Clinical Prescription Dispensing Queue** with live `SlainteRx-Guard` cross-reactivity screening, Irish GMS verification, and 1-click **Dispense Verified** / **Hold Rx** / **Re-Queue** actions.
   - **`SlainteGP`:** **HSE Chronic Disease Management (CDM) & SOAP Consultation Workspace** with biomarker strip, structured `S/O/A/P` + clinic BP filing, and 1-click **28-Day Repeat Prescription** renewal.
   - **`SlainteEMS` & `SlainteED`:** **Rapid Field ePCR & Resuscitation Pre-Alert Console** computing deterministic MTS Cat 1–5 + NEWS2 acuity and pushing full FHIR R4 `Bundle`s to the receiving ED.
   - **`SlainteSport` & `SlainteAstro`:** **Squad Readiness / Crew Bio-Telemetry Clearance Board** with 1-click cryptographic **SCAT6 Return-to-Play / EVA Flight Surgeon (`Provenance`)** sign-off.
3. **Bucket C — Workstation UI Cleanup & Global Display Preferences:**
   - Redesigned `patient_details.html` (compact clinical banner, square monogram, zero redundant `"View ..."` buttons, flush single-border clinical tables).
   - Wired real browser-persisted Display Preferences (`100%/115%/130%` clinical font scaling, WCAG High-Contrast Priority Mode, and `5s/15s/30s/manual` HTMX triage polling) in `static/htmx-setup.js` and `static/styles.css`.
   - Removed deprecated `/pipeline/status` button from `triage.html` and unified `/admin/*` & `/settings/*` styling.

---

## 2. Codebase Audit & Architecture Review

### 2.1 System Architecture & Footprint
`Slainte-Engine` is packaged as a 5-container clinical interoperability and autonomous cybersecurity appliance (~`18,500` lines of Python + `34` Jinja2/HTMX templates, zero SPA build step):

| Service / Directory | Runtime & Port | Responsibility | Code Quality Assessment |
| :--- | :--- | :--- | :--- |
| `frontend/` (`SlainteDash`) | Python 3.12 + Flask 3 + Gunicorn (`:8000`) | Server-rendered HTMX clinical workstation, 7 vertical cockpits, 9 agent command dashboards, auth/RBAC, audit ledger | **Strong** clinical safety separation (errors never masquerade as empty clinical lists). **Tech debt:** `app.py` has grown to ~3,680 LOC and should be split into Flask Blueprints. |
| `slainte-fhir/` (`SlainteFHIR`) | Python 3.12 + FastAPI + `aiosqlite` WAL (`:8082`) | Sovereign HL7 FHIR R4 Micro-EHR (`Patient`, `Observation`, `Condition`, `MedicationRequest`, `AllergyIntolerance`, `DocumentReference`, `Provenance`, `$validate`) | **Clean, fast, asynchronous.** Supports `GET`, `POST`, `PUT`, compartment pruning, and `$validate`. Single-node SQLite WAL ceiling (~50 concurrent writers). |
| `slainte-scan-mcp/` (`SlainteScan`) | Python 3.12 + FastMCP SSE (`:8081`) | Deterministic clinical rules engine (RCP NEWS2, Manchester Triage Cat 1–5, SNOMED/LOINC/UCUM validation, drug-allergy cross-reactivity) | **Architectural highlight:** Prevents LLM math/clinical hallucinations. Contains 6 small dev scratch scripts (`scratch.py`, `test_fastmcp_types.py`) that should be deleted. |
| `slainte-auditor/` (`SlainteShield`) | Python 3.12 Autonomous Verifier | 4-stage BOLA reflection agent (`SharedAuditMemory`), terminology conformance scanner, OASIS SARIF v2.1.0 generator | **Strong differentiation:** Dual-phase HTTP BOLA probing + RFC 1918 sandbox target guardrails. |
| `openhands/` | Sandboxed Ingestion Daemon (`:3000`) | Watches `/data/raw` dropzone for batch CSV/PDF/image arrivals and harmonizes into `/data/fhir_store` | Decoupled via filesystem dropzone; optional for core interactive clinical workflows. |

### 2.2 Concrete Code Review Findings (Technical Debt Inventory)
During this stopgap review, **two real runtime synchronization bugs were caught and fixed immediately**:
- *Fixed during audit:* Manual patient intake (`POST /fhir/intake/manual`), document upload (`POST /fhir/upload`), and clinician sign-off (`POST /fhir/patient/<id>/sign-off`) previously wrote only to local JSON files when `SlainteFHIR (:8082)` was active; they now write through to `SlainteFHIR` via `POST /Bundle` and `PUT /Provenance` as well.
- *Fixed during audit:* `run.sh` startup banner still printed the deprecated `/?view=/pipeline/status` URL; updated to `/agents` and `/fhir/r4/metadata`.

**Remaining Code Maintenance Items:**
1. **Modularize `frontend/app.py` (~3,680 LOC) into Flask Blueprints:** Split `app.py` into `blueprints/auth.py`, `blueprints/patients.py`, `blueprints/cockpits.py`, `blueprints/agents.py`, `blueprints/intake.py`, and `blueprints/settings.py`.
2. **Pin Exact Versions Across All Microservices:** `frontend/requirements.txt` uses strict `==` pins, whereas `slainte-fhir/requirements.txt` and `slainte-scan-mcp/requirements.txt` use `>=` floating bounds (`fastapi>=0.110.0`, `fastmcp>=0.1.0`). Freeze exact hashes (`pip-compile --generate-hashes`) for reproducible supply-chain builds.
3. **Remove Scratch Files in `slainte-scan-mcp/`:** Delete `scratch.py`, `test_fastmcp_types.py`, `test_genai.py`, `test_image.py`, and `test_list_tools*.py` from root of `slainte-scan-mcp/` (already excluded from Docker image via `COPY src/ ./src/`, but cluttering the repo).
4. **Workspace Consolidation:** `/home/adman-voids/Desktop/Code/SlainteDash` is a symlink to `Patient-Dashboard-htmx-python-fhir`, while `slainte-engine/frontend/` is the integrated monorepo copy. Treat `slainte-engine` as the single canonical repository going forward to eliminate manual `rsync` drift.

---

## 3. Security, Privacy (GDPR Art. 9) & Clinical Safety Audit

### 3.1 Verified Security Controls Currently Active
| Domain | Control Implemented | Evidence / Location | Status |
| :--- | :--- | :--- | :--- |
| **Authentication** | `scrypt` password hashing (`werkzeug.security`), pending-account admin approval gate, 10-char minimum password policy | `frontend/auth.py`, `frontend/db.py` | **PASS** |
| **Brute-Force Defense** | Progressive account lockout (15-min lock after 5 failed attempts) + SQLite-shared `Flask-Limiter` across Gunicorn workers | `frontend/db.py`, `frontend/rate_limit_storage.py` | **PASS** |
| **CSRF & Session Security** | Global `CSRFProtect` + automatic `X-CSRFToken` header injection on mutating HTMX verbs; `HttpOnly`, `SameSite=Lax` cookies | `frontend/app.py`, `static/htmx-setup.js` | **PASS** |
| **Supply-Chain & XSS** | `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, verified `sha384-` SRI hashes on CDN assets, Jinja2 auto-escaping | `frontend/app.py`, `templates/base.html`, `templates/index.html` | **PASS** |
| **GDPR Art. 9 & AI Gate** | Salted HMAC-SHA256 subject digests (`LOG_HASH_SALT`), Safe-Harbor PII stripping (`ai/context.py`), hard block (`AI_ALLOW_REAL_PHI=false`) on non-demo FHIR hosts | `frontend/logging_setup.py`, `frontend/ai/context.py`, `frontend/config.py` | **PASS** |
| **Audit Immutability** | Append-only SQLite `audit_log` & `ai_exchange` tables enforced by `BEFORE UPDATE` and `BEFORE DELETE` `RAISE(ABORT)` triggers | `frontend/db.py` | **PASS** |
| **Red-Team Containment** | `Slainte-Auditor` refuses to send BOLA probes to public IPs (enforces RFC 1918 / loopback sandbox check) | `slainte-auditor/src/redteam_bola_agent.py` | **PASS** |

### 3.2 Open Security Findings to Close Before Live Hospital PHI Production
| Severity | Finding | Remediation Required Before Live Patient Deployment |
| :--- | :--- | :--- |
| **HIGH** | **No TLS Termination Container in Default `docker-compose.yml` (`HTTP :8000`)** | Place **Caddy** or **Nginx** in `docker-compose.yml` terminating TLS 1.3 (`:443`), add `Strict-Transport-Security`, and set `SESSION_COOKIE_SECURE=true`. |
| **HIGH** | **Fallback Default Credentials & Static Fallback Salts in `docker-compose.yml` / `run.sh`** | `docker-compose.yml` falls back to `ClinicalAdmin2026!`, `slainte-engine-production-key-99021`, and `slainte-secure-audit-salt-2026-prod` if `.env` is unset. Update `run.sh` to generate `openssl rand -hex 32` secrets on initial setup and require admin password change on first login. |
| **MEDIUM** | **Unauthenticated Internal Microservice Ports (`:8081` & `:8082`) Bound to `0.0.0.0`** | In `docker-compose.yml`, `ports: - "8082:8082"` and `"8081:8081"` expose `SlainteFHIR` and `SlainteScan` on the host network without bearer auth. Change to `127.0.0.1:8082:8082` (or remove host port mapping entirely in production) and add an internal `X-Slainte-Service-Key` middleware. |
| **MEDIUM** | **Coarse Role-Based Access Control (`admin` vs `user`)** | Vertical cockpits adapt the UI per clinical persona, but any authenticated `user` can invoke write endpoints (`/fhir/Medications/<id>/add`, `/fhir/Cockpit/pharmacy/dispense`). Enforce server-side clinical role claims (`prescriber`, `pharmacist`, `nurse`, `auditor`) in `db.py` / `@require_clinical_permission`. |
| **LOW** | **CSP Allows `'unsafe-inline'` for Scripts/Styles** | Move inline `<script>` helpers in `settings_app.html` and `cockpit_workspace.html` into `static/` JS files and switch CSP to per-request cryptographic nonces. |

---

## 4. Operator Runbook ("Everything Needed to Run & Maintain Slainte-Engine")

### 4.1 Infrastructure Prerequisites
- **Operating System:** Ubuntu 22.04 / 24.04 LTS, Debian 12, RHEL 9, macOS, or Windows WSL2.
- **Container Engine:** Docker Engine `>= 24.0` + Docker Compose v2 (`docker compose`).
- **Compute Sizing:**
  - *Cloud-AI / Deterministic Mode:* 4 vCPU, 8 GB RAM, 40 GB SSD.
  - *100% Air-Gapped Sovereign Local LLM Mode (with Ollama):* 8+ vCPU, 32 GB RAM, NVIDIA GPU with 16–24 GB VRAM (running `ollama serve` on host port `11434`).

### 4.2 Production `.env` Reference
Create `/home/adman-voids/Desktop/Code/slainte-engine/.env` before starting:
```ini
# Core Security (MUST generate unique values per deployment: openssl rand -hex 32)
FLASK_ENV=production
SECRET_KEY=<64-hex-char-random-secret>
LOG_HASH_SALT=<64-hex-char-random-audit-salt>
SESSION_COOKIE_SECURE=true

# Bootstrap Administrator
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=<strong-unique-passphrase-min-14-chars>

# FHIR R4 Backend Routing
APPLIANCE_MODE=true
FHIR_SERVER_URL=http://slainte-fhir:8082/fhir/r4
TARGET_FHIR_URL=http://slainte-fhir:8082

# Sovereign Local AI (Ollama) or Cloud Frontier AI
AI_MODEL=ollama/k9/lime:latest
LLM_BASE_URL=http://host.docker.internal:11434
OPENAI_API_KEY=
GEMINI_API_KEY=
AI_ALLOW_REAL_PHI=false
```

### 4.3 Standard Day-1 & Day-2 Operations
- **Boot Full Appliance:** `./run.sh start` (or `docker compose up -d --build`)
- **Verify Service Health:** `./run.sh status`
  - Workstation UI: `http://localhost:8000`
  - Readiness Probe (verifies FHIR connectivity): `curl -f http://localhost:8000/health/ready`
  - SlainteFHIR CapabilityStatement: `curl -f http://localhost:8082/fhir/r4/metadata`
- **Account Recovery / Admin Provisioning (Zero Downtime):**
  - Grant or unlock admin: `docker exec -it slainte-dashboard flask --app app grant-admin <username>`
  - Reset clinician password: `docker exec -it slainte-dashboard flask --app app reset-password <username>`
  - List accounts: `docker exec -it slainte-dashboard flask --app app list-users`
- **Run Automated Test Suite (`318` Tests):**
  - `cd frontend && pytest -q`
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

## 5. Buyer / M&A Handover & Real-World Hospital Implementation Playbook

### 5.1 M&A Technical Due Diligence & Handover Package ("Suppose Someone Bought This Tomorrow")
When handing `Slainte-Engine` over to an acquirer, strategic health-tech buyer, or enterprise licensee, deliver a clean **5-Part Acquisition Data Room**:

1. **Consolidated Source Repository Transfer:**
   - Transfer ownership of two clean Git repositories:
     1. **`slainte-engine`** (Core clinical platform, `SlainteFHIR`, `SlainteScan` FastMCP, `Slainte-Auditor` 9-agent engine, Docker orchestration, and `318` automated tests).
     2. **`SlaintePages`** (Phase 12 Next.js marketing, documentation, and technical buyer portal).
   - Archive/retire standalone legacy repos (`OCR2FHIR`, `Patient-Dashboard-htmx-python-fhir`) once verified that 100% of commit value lives in `slainte-engine`.
2. **Intellectual Property & Open-Source License Clearance (SBOM):**
   - Generate a CycloneDX SBOM (`syft` / `pip-audit`). Core Python stack (`Flask`, `FastAPI`, `Pydantic`, `aiosqlite`, `Bootstrap`, `HTMX`, `Chart.js`) is 100% permissive (`MIT` / `BSD-3` / `Apache-2.0`).
   - *Important M&A Note:* Keep `openhands/` optional/pluggable via a clean adapter interface so buyers with strict corporate policies on external agent runtimes can run the pure `Slainte-Engine` Python stack (`slainte-dashboard` + `slainte-fhir` + `slainte-mcp` + `slainte-auditor`) with 100% proprietary first-party IP!
3. **Synthetic Data Attestation:**
   - Provide written attestation that all 34 bundled patient records (`P101`–`P9662`, `patient-case-1`–`8`) are 100% synthetic — zero real patient PHI has ever been committed to Git history.
4. **Architecture & Cryptographic Custody Handover:**
   - Rotate all `.env` keys, Docker Hub / GHCR container registry tokens, domain DNS records, and hand over the `Operator Runbook` (Section 4 above).
5. **90-Day Knowledge Transfer & Pilot Playbook:**
   - Walkthrough of adding a new vertical cockpit (`frontend/verticals.py` + `templates/cockpit_workspace.html`) and registering a new autonomous agent (`frontend/agents_catalog.py` + `slainte-scan-mcp/src/`).

### 5.2 How to Actually Implement This in a Real Hospital, GP Group, or Clinic
Hospitals and clinics **do not rip-and-replace** their core PAS/EHR on Day 1. You deploy `Slainte-Engine` in one of two proven clinical topologies:

#### Mode 1: "Sidecar AI Governance & Specialty Cockpit Overlay" (For Hospitals Already Running Epic, Cerner/Oracle, MEDITECH, or HSE PAS)
1. **Network Placement:** Deploy `Slainte-Engine` on a dedicated Ubuntu VM (or Kubernetes namespace) inside the hospital's internal clinical VLAN behind an Nginx/Caddy TLS 1.3 ingress, paired with an on-premise Ollama GPU server so **zero PHI leaves the hospital perimeter**.
2. **EHR Integration (`FHIR_SERVER_URL` + Mirth Connect):**
   - If the hospital exposes an HL7 FHIR R4 endpoint (Epic FHIR / Cerner Ignite / Azure Health Data Services), point `/settings/data` (`FHIR_SERVER_URL`) at the hospital's FHIR R4 endpoint with OAuth2 client credentials.
   - If the hospital still emits legacy **HL7v2 (`ADT^A01` admissions, `ORU^R01` lab results)** over MLLP, place open-source **Mirth Connect (NextGen Connect)** in front of `slainte-fhir:8082/fhir/r4/Bundle` to translate HL7v2 messages into FHIR R4 Bundles in real time.
3. **Clinician Workflow:** Clinicians sign in via hospital Active Directory / Entra ID SSO, or launch `SlainteDash` directly from a button inside Epic/Cerner via **SMART-on-FHIR patient context launch**.

#### Mode 2: "Turnkey Sovereign Micro-EHR + Agentic Workstation" (For Private Clinics, Dental Practices, Sports Clubs, Ambulance Services, & Remote/Aerospace Medicine)
1. **Turnkey Appliance:** Deploy the full 5-container `Slainte-Engine` stack (`SlainteFHIR` acts as the primary clinical system of record, backed up nightly to encrypted PostgreSQL / S3 Object Lock).
2. **Immediate Day-1 Value:** Smaller clinics (`SlainteDent`, `SlainteSport`, private urgent care, expedition/aerospace medicine) get a modern FHIR R4 record store, 32-tooth odontogram / ePCR / clearance sign-off, multimodal PDF/letter ingestion, and built-in GDPR/audit governance in a single box.

#### Regulatory & Clinical Governance Path (EU / Ireland / UK)
- **Sell Immediately (Zero MDR Delay):** Position **Agents 01–06** (`SlainteShield-BOLA`, `SlainteShield-FHIR`, `SlainteShield-CVE`, `SlainteGov-GDPR`, `SlainteGov-Audit`, `SlainteEngine-Ingest`) as **Healthcare Cybersecurity, Interoperability & Compliance Infrastructure** — cybersecurity and data-pipeline software is *not* a medical device under EU MDR (2017/745), allowing immediate commercial contracts with hospital CISOs and IT directors!
- **Clinical Decision Support Governance:** Keep **Agents 07–09** (`SlainteScribe-Brief`, `SlainteRx-Guard`, `SlainteDx-Triage`) strictly **deterministic, transparent, cited, and clinician-in-the-loop** (displaying exact RCP NEWS2 / MTS / SNOMED rule logic for human clinician sign-off), aligned with **NHS DCB0129 / DCB0160** Clinical Risk Management standards while preparing **EU MDR Class IIa** technical documentation for commercial clinical CDS modules.

---

## 6. Pre-Phase-12 Checklist (What Should Be Done Before Starting `SlaintePages`)

Before opening `/home/adman-voids/Desktop/Code/SlaintePages` (Phase 12 separate marketing/product repo), here is the exact prioritized shortlist:

1. **Quick Hardening Pass (~20 mins, Recommended Before Phase 12):**
   - [ ] Pin exact `==` versions in `slainte-fhir/requirements.txt` and `slainte-scan-mcp/requirements.txt` and remove the 6 scratch `test_*.py` files in `slainte-scan-mcp/`.
   - [ ] Update `docker-compose.yml` to bind internal ports `8081` and `8082` to `127.0.0.1` (`127.0.0.1:8082:8082`) so they aren't exposed to external LAN interfaces, and update `run.sh` to auto-generate random `SECRET_KEY` and `LOG_HASH_SALT` values when creating `.env`.
2. **Product Visual Assets for `SlaintePages`:**
   - [ ] Capture crisp screenshots of (a) the 9-Agent Command Hub (`/agents`), (b) Agent 01 BOLA Red-Team Dashboard, (c) Agent 08 `SlainteRx-Guard` blocking an unsafe prescription live on a patient chart, (d) `SlainteDent` 32-Tooth FDI Odontogram, and (e) `SlaintePharm` Dispensing Queue so `SlaintePages` displays authentic, high-trust product visuals rather than generic mockups.
3. **Commit & Push Step 1.5 + `stopgap.md` to GitHub:**
   - [ ] Ensure `slainte-engine` (and `SlainteDash` mirror) have a clean Git tree tagged `v0.9.0-pre-pages` before starting Phase 12.

---

## 7. Commercialization Gap Analysis ("What Killer Features Are Missing to Sell This?")

Right now, `Slainte-Engine` is an **exceptionally strong technical prototype & pilot appliance** — far ahead of typical AI wrappers because it combines a real FHIR R4 server, 7 specialty cockpits, clinical writes, deterministic FastMCP safety gates, and 9 security/clinical agents.

To turn this from a ** compelling pilot demo** into a **€100k–€500k ACV enterprise healthcare product** that hospitals, clinic chains, or acquirers buy on sight, here are the **7 Killer Features** currently missing:

### 1. SMART-on-FHIR Launch + Hospital SSO (`OIDC / SAML 2.0 / Entra ID + MFA`) — *Deal-Breaker #1 for Hospitals*
- **Why buyers demand it:** No hospital doctor or nurse will log into a separate username/password screen. Supporting **HL7 SMART-on-FHIR App Launch** (`iss` + `launch` OAuth2 handshake) lets `SlainteDash` or any of the 9 agents open *directly inside Epic, Cerner, or MEDITECH* with the active patient and practitioner automatically authenticated via Microsoft Entra ID / Okta + Smartcard MFA.

### 2. Ambient Clinical Voice Scribe (`Agent 10 — SlainteScribe-Voice`) — *Fastest Revenue Wedge for Clinics & GPs*
- **Why buyers pay immediately:** GPs, dentists, and ED doctors spend 2+ hours/night typing notes. Adding a browser WebRTC microphone button that streams audio to an **on-premise Whisper / MedASR model**, drafts the structured SOAP `DocumentReference` + SNOMED `Condition`s + `MedicationRequest`s, and immediately runs Agent 08 (`SlainteRx-Guard`) before 1-click sign-off saves 6–10 minutes *per patient*. Clinics happily pay €150–€300/clinician/month for this alone.

### 3. Irish / EU National Spine Connectors (`Healthlink / Healthmail / HSE PCRS GMS Claims & HL7v2 MLLP`)
- **Why buyers pay in Ireland/UK/EU:**
  - For **`SlainteGP` & `SlaintePharm`**: Automated **HSE PCRS (Primary Care Reimbursement Service)** GMS claim validation and **Healthmail** secure electronic prescription transfer.
  - For **`SlainteED`**: Built-in **HL7v2 MLLP listener** (`ADT^A01`, `ORU^R01`) so hospital lab analysers and legacy PAS systems stream into `SlainteFHIR` with zero third-party middleware.

### 4. Granular Clinical RBAC + "Break-the-Glass" Emergency Access Workflow
- **Why CISOs & DPOs love it:** Enforce cryptographic role permissions (`Prescriber` IMC#, `Pharmacist` PSI#, `Triage Nurse` NMBI#, `DPO Auditor`) and restrict clinicians to their assigned care team (`CompartmentDefinition`) *unless* they click **"Break the Glass (Emergency Override)"** — which grants 60-minute emergency chart access while firing an instant real-time alert to Agent 04 (`SlainteGov-GDPR`) and Agent 05 (`SlainteGov-Audit`).

### 5. Autonomous Scheduled Red-Teaming, SIEM Webhooks & One-Click CISO Compliance PDF (`NIS2 / HIQA / ISO 27001`)
- **Why it unlocks standalone `Slainte-Shield` sales:** Allow `Slainte-Auditor` (Agents 01–05) to run on a nightly cron against *any* hospital's external/staging FHIR API, push critical BOLA/CVE/GDPR alerts to **Microsoft Sentinel / Splunk / Slack / PagerDuty**, and export a **board-ready signed PDF Compliance Certificate** mapped to **EU NIS2**, **EU AI Act Art. 9–15**, and **HIQA**. Security budgets approve this in weeks rather than months!

### 6. PostgreSQL Multi-Tenant Engine + Automated Clinical Coding / HIPE / DRG Revenue Recovery Agent (`Agent 11`)
- **Why Hospital CFOs fund it:**
  - Migrate from SQLite to **PostgreSQL 16 (`JSONB` + Row-Level Security)** for multi-clinic SaaS scale.
  - Add an **Autonomous Clinical Coding & HIPE/DRG Audit Agent** that cross-checks clinical notes + lab results (e.g., elevated Creatinine / Troponin / Lactate) against coded `Condition`s to catch unbilled comorbidities — generating measurable 5x–10x ROI for private hospitals.

### 7. Full British National Formulary (BNF) / dm+d / DrugBank Interaction Matrix
- **Why it upgrades `SlainteRx-Guard` to clinical-grade ePrescribing:** Expand `check_drug_allergy_contraindications` from high-risk class rules into a licensed **drug-drug interaction (QT prolongation, CYP450), renal dose-adjustment (eGFR-gated), and pregnancy/pediatric weight-based dosing engine**.
