"""Multi-Vertical Clinical Cockpit Registry (Phase 11).

Powers "Sign in as..." role-based specialty cockpits across 7 healthcare & aerospace domains:
1. ed       — SlainteED (Emergency Department & Acute Triage)
2. gp       — SlainteGP (General Practice & Primary Care CDM)
3. dentist  — SlainteDent (Dental Surgery & Periodontics)
4. pharmacy — SlaintePharm (Clinical Dispensing & Pharmacotherapy Gate)
5. ems      — SlainteEMS (Pre-Hospital Ambulance & Paramedic ePCR)
6. sports   — SlainteSport (Elite Sports Club & Athlete Medicine)
7. astro    — SlainteAstro (Astronaut & Deep-Space Bio-Telemetry)
"""

VERTICALS_CATALOG = {
    'ed': {
        'key': 'ed',
        'brand': 'SlainteED',
        'title': 'Emergency Department & Acute Triage',
        'role_label': 'ED Consultant / Triage Nurse',
        'icon': 'fas fa-ambulance',
        'badge_color': 'danger',
        'accent_hex': '#ef4444',
        'default_view': 'triage',
        'tagline': 'Manchester Triage System (MTS Cat 1–5), 24h RCP NEWS2 Deterioration Tracking & Rapid Bedside Intake.',
        'active_agents': ['acuity_triage', 'multimodal_ingest', 'patient_summariser', 'medication_safety', 'bola_redteam', 'immutable_audit'],
        'kpis': [
            {'label': 'Triage Protocol', 'value': 'MTS Cat 1–5', 'sub': '0m Immediate to 240m Non-Urgent', 'icon': 'fas fa-procedures'},
            {'label': 'Deterioration Gate', 'value': 'RCP NEWS2', 'sub': '24h Continuous Vital Sparklines', 'icon': 'fas fa-heartbeat'},
            {'label': 'Safety Interceptor', 'value': 'Rx-Guard Active', 'sub': 'Beta-Lactam / NSAID Cross-Check', 'icon': 'fas fa-shield-virus'},
        ],
        'specialty_panel_title': 'ED Resuscitation & Acute Bay Status',
        'specialty_highlights': [
            'Cat 1 Immediate & Cat 2 Very Urgent bays monitored with real-time NEWS2 >= 7 sepsis escalation.',
            'Multimodal CSV/PDF/Handwritten triage note dropzone wired to FastMCP deterministic scoring.',
            'Cryptographic SHA-256 Provenance sign-off enforced for acute consultant handovers.',
        ],
    },
    'gp': {
        'key': 'gp',
        'brand': 'SlainteGP',
        'title': 'General Practice & Primary Care (CDM)',
        'role_label': 'General Practitioner (GP)',
        'icon': 'fas fa-user-md',
        'badge_color': 'primary',
        'accent_hex': '#0ea5e9',
        'default_view': 'patients',
        'tagline': 'SOAP Clinical Consultations, Irish HSE Chronic Disease Management (CDM) & Safe Repeat Prescribing.',
        'active_agents': ['patient_summariser', 'medication_safety', 'multimodal_ingest', 'gdpr_privacy', 'fhir_conformance'],
        'kpis': [
            {'label': 'Identifier Standard', 'value': 'Irish GMS OID', 'sub': 'urn:oid:1.3.6.1.4.1.54392.5.2690.42.80', 'icon': 'fas fa-id-card'},
            {'label': 'CDM Pathways', 'value': 'T2DM / COPD / HTN', 'sub': 'Longitudinal Vital & Lab Trends', 'icon': 'fas fa-notes-medical'},
            {'label': 'Prescribing Gate', 'value': 'Repeat Rx Safe', 'sub': 'FastMCP Allergy Cross-Reactivity', 'icon': 'fas fa-prescription-bottle-alt'},
        ],
        'specialty_panel_title': 'GP Consultation & HSE Chronic Disease Management (CDM)',
        'specialty_highlights': [
            'Structured SOAP (Subjective, Objective, Assessment, Plan) bedside summarisation via SlainteScribe-Brief.',
            'Automatic GMS number deduplication across hospital discharge letters and primary care referrals.',
            'EU GDPR Art. 9 PII minimisation enforced by SlainteGov-GDPR on all external referral summaries.',
        ],
    },
    'dentist': {
        'key': 'dentist',
        'brand': 'SlainteDent',
        'title': 'Dental Surgery & Periodontal Suite',
        'role_label': 'Dental Surgeon',
        'icon': 'fas fa-tooth',
        'badge_color': 'info',
        'accent_hex': '#06b6d4',
        'default_view': 'insights',
        'tagline': '32-Tooth FDI Odontogram Charting, 6-Sextant BPE Periodontal Matrix & Pre-Operative Medical Clearance.',
        'active_agents': ['medication_safety', 'multimodal_ingest', 'patient_summariser', 'gdpr_privacy'],
        'kpis': [
            {'label': 'Odontogram Standard', 'value': 'FDI 11–48', 'sub': '32-Tooth Adult / Pediatric Charting', 'icon': 'fas fa-tooth'},
            {'label': 'Periodontal Index', 'value': '6-Sextant BPE', 'sub': 'Basic Periodontal Examination', 'icon': 'fas fa-teeth-open'},
            {'label': 'Pre-Op Clearance', 'value': 'Allergy & Anticoag', 'sub': 'Amoxicillin / NSAID / Latex Gate', 'icon': 'fas fa-allergies'},
        ],
        'specialty_panel_title': 'FDI 32-Tooth Odontogram & Pre-Op Antibiotic Prophylaxis Gate',
        'specialty_highlights': [
            'Instant pre-extraction & endodontic screening for Penicillin/Amoxicillin anaphylaxis and NSAID asthma.',
            'FDI Two-Digit Quadrants (11–18, 21–28, 31–38, 41–48) & 6-Sextant BPE periodontal scoring mapped to SNOMED-CT.',
            'Automated dental referral & radiograph note ingestion via SlainteEngine-Ingest.',
        ],
    },
    'pharmacy': {
        'key': 'pharmacy',
        'brand': 'SlaintePharm',
        'title': 'Clinical Dispensing & Pharmacy Safety',
        'role_label': 'Supervising Pharmacist',
        'icon': 'fas fa-pills',
        'badge_color': 'success',
        'accent_hex': '#10b981',
        'default_view': 'patients',
        'tagline': 'MedicationRequest Dispensing Queue, Deterministic Beta-Lactam/NSAID Interception & GMS Reimbursement.',
        'active_agents': ['medication_safety', 'fhir_conformance', 'immutable_audit', 'gdpr_privacy'],
        'kpis': [
            {'label': 'Safety Engine', 'value': 'SlainteRx-Guard', 'sub': '100% Deterministic FastMCP Matrix', 'icon': 'fas fa-capsules'},
            {'label': 'Reimbursement OID', 'value': 'HSE PCRS / GMS', 'sub': 'Verified GMS Identifier Binding', 'icon': 'fas fa-file-invoice'},
            {'label': 'Dispense Audit', 'value': 'SHA-256 Signed', 'sub': 'PSI / HIQA Provenance Compliance', 'icon': 'fas fa-signature'},
        ],
        'specialty_panel_title': 'Pharmacotherapy Contraindication & GMS Dispensing Verification',
        'specialty_highlights': [
            'Deterministic cross-reactivity interception across Penicillins, Cephalosporins, Carbapenems, NSAIDs, and Sulfonamides.',
            'Strict UCUM dosage unit verification (mg, mL, ug/min) audited by SlainteShield-FHIR.',
            'Cryptographic pharmacist Provenance sign-off recorded in the immutable audit ledger.',
        ],
    },
    'ems': {
        'key': 'ems',
        'brand': 'SlainteEMS',
        'title': 'Pre-Hospital Ambulance & Paramedic ePCR',
        'role_label': 'Advanced Paramedic / EMS Crew',
        'icon': 'fas fa-truck-medical',
        'badge_color': 'warning',
        'accent_hex': '#f59e0b',
        'default_view': 'triage',
        'tagline': 'High-Contrast Field ePCR Intake, Instant Ambulance MTS/NEWS2 Acuity Scoring & Zero-Latency ED Handoff.',
        'active_agents': ['acuity_triage', 'multimodal_ingest', 'patient_summariser', 'immutable_audit'],
        'kpis': [
            {'label': 'Field Acuity', 'value': 'Sub-Second MTS', 'sub': 'Instant Cat 1–5 Pre-Alert', 'icon': 'fas fa-bolt'},
            {'label': 'Field OCR', 'value': 'Handwritten ePCR', 'sub': 'Multimodal Ambulance Note Ingest', 'icon': 'fas fa-camera'},
            {'label': 'ED Handoff', 'value': 'FHIR R4 Push', 'sub': 'Direct to SlainteFHIR :8082', 'icon': 'fas fa-satellite-dish'},
        ],
        'specialty_panel_title': 'Pre-Hospital ePCR Telemetry & Receiving ED Pre-Alert',
        'specialty_highlights': [
            'Rapid roadside vital sign entry (SpO2, RR, HR, SBP, Temp, Pain) computing MTS Category & NEWS2 in <10ms.',
            'Handwritten paramedic slate & ECG sheet OCR extraction into structured LOINC Observations.',
            'One-tap handover briefing generated by SlainteScribe-Brief for the receiving resuscitation team.',
        ],
    },
    'sports': {
        'key': 'sports',
        'brand': 'SlainteSport',
        'title': 'Elite Sports Club & Athlete Performance Medicine',
        'role_label': 'Head of Sports Medicine',
        'icon': 'fas fa-running',
        'badge_color': 'success',
        'accent_hex': '#22c55e',
        'default_view': 'insights',
        'tagline': 'Squad Readiness Telemetry, SCAT6 Concussion Return-to-Play Sign-Off & BOLA-Verified Athlete Privacy.',
        'active_agents': ['acuity_triage', 'medication_safety', 'bola_redteam', 'gdpr_privacy'],
        'kpis': [
            {'label': 'Squad Telemetry', 'value': 'HRV / SpO2 / Load', 'sub': '24h Physiological Recovery Curves', 'icon': 'fas fa-chart-line'},
            {'label': 'Clearance Protocol', 'value': 'SCAT6 + Provenance', 'sub': 'Cryptographic Return-to-Play Sign-Off', 'icon': 'fas fa-user-check'},
            {'label': 'Athlete Privacy', 'value': 'BOLA Verified', 'sub': 'Compartment Isolation (SlainteShield)', 'icon': 'fas fa-lock'},
        ],
        'specialty_panel_title': 'First-Team Squad Readiness, TUE Screening & Return-to-Play Clearance',
        'specialty_highlights': [
            'Continuous physiological load & recovery tracking using LOINC vital sign sparklines.',
            'Medication & Therapeutic Use Exemption (TUE) allergy cross-checking via SlainteRx-Guard.',
            'Strict CompartmentDefinition/Patient isolation audited by SlainteShield-BOLA to prevent roster medical leaks.',
        ],
    },
    'astro': {
        'key': 'astro',
        'brand': 'SlainteAstro',
        'title': 'Astronaut & Deep-Space Bio-Telemetry',
        'role_label': 'Flight Surgeon / Crew Medical Officer',
        'icon': 'fas fa-user-astronaut',
        'badge_color': 'dark',
        'accent_hex': '#6366f1',
        'default_view': 'agents',
        'tagline': '100% Air-Gapped Deep-Space Medical Autonomy: Local 3B Models + Deterministic FastMCP Diagnostics.',
        'active_agents': [
            'bola_redteam', 'fhir_conformance', 'cve_vulnerability',
            'gdpr_privacy', 'immutable_audit', 'multimodal_ingest',
            'patient_summariser', 'medication_safety', 'acuity_triage',
        ],
        'kpis': [
            {'label': 'Earth Uplink Needed', 'value': '0 Bytes (Air-Gap)', 'sub': 'Local 3B Ollama Sovereign Inference', 'icon': 'fas fa-satellite'},
            {'label': 'Crew Bio-Loop', 'value': 'EVA / Radiation / SpO2', 'sub': 'Autonomous NEWS2 Hypoxia Drift Gate', 'icon': 'fas fa-lungs'},
            {'label': 'Active Agent Fleet', 'value': 'All 9 Agents Live', 'sub': 'On-Board Autonomous Medical Officer', 'icon': 'fas fa-robot'},
        ],
        'specialty_panel_title': 'Orbital & Deep-Space Autonomous Medical Telemetry Bay',
        'specialty_highlights': [
            'Zero Earth-cloud dependency: runs k9/lime:latest & k9/Doggo:3b locally alongside SlainteFHIR :8082.',
            'Continuous crew hypoxia, barotrauma, and cardiovascular deconditioning monitoring via deterministic FastMCP rules.',
            'Immutable SHA-256 Provenance flight surgeon log verified continuously by all 9 onboard agents.',
        ],
    },
}


def get_vertical_list():
    return list(VERTICALS_CATALOG.values())


def get_active_vertical(session_obj, db_module=None):
    key = None
    try:
        key = session_obj.get('active_vertical')
    except Exception:
        key = None
    if not key and db_module is not None:
        try:
            key = db_module.get_system_setting('default_vertical', 'ed')
        except Exception:
            key = 'ed'
    if key not in VERTICALS_CATALOG:
        key = 'ed'
    return VERTICALS_CATALOG[key]
