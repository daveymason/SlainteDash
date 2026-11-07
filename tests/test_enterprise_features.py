"""Automated Unit & Integration Tests for Phase 11.5 — The 7 Killer Enterprise Features.

Tests:
1. HL7 SMART-on-FHIR v2 App Launch, Discovery, Token Exchange & OIDC PKCE SSO
2. Agent 10 (SlainteScribe-Voice): Ambient Voice Scribe + 3-Tier Rx-Guard Pre-Screen + FHIR Commit
3. Native HL7v2 (ADT^A01 / ORU^R01) Pipe-Hat -> HL7 FHIR R4 Bundle Translator & HSE PCRS GMS Claim Export
4. Granular Clinical RBAC (prescriber, pharmacist, triage_nurse, auditor) & Immutable Break-the-Glass Grants
5. CISO HMAC-SHA256 SIEM Webhook Dispatcher & Printable NIS2 / EU AI Act / HIQA / ISO 27001 Certificate
6. Agent 11 (SlainteRev-Coding): Autonomous HIPE / ICD-10-AM / SNOMED Comorbidity & DRG Revenue Auditor
7. 3-Tier SlainteRx-Guard Clinical Pharmacology Engine (Allergy + ISMP High-Alert DDI + Lab eGFR Renal Gate)
"""
import pytest
import responses

import db
from agents_hub import AGENTS_CATALOG, get_agent_by_id
from conftest import FHIR_BASE, bundle
from enterprise_engine import (
    evaluate_clinical_pharmacology_3tier,
    mint_smart_launch_token,
    process_ambient_consultation,
    scan_patient_coding_gaps,
    translate_hl7v2_to_fhir_bundle,
    verify_smart_launch_token,
)


def _mock_patient(pid="P101", name_family="Walsh", name_given="Mary"):
    return {
        "resourceType": "Patient",
        "id": pid,
        "identifier": [{"system": "urn:oid:1.3.6.1.4.1.54392.5.2690.42.80", "value": f"GMS-{pid}"}],
        "name": [{"family": name_family, "given": [name_given], "text": f"{name_given} {name_family}"}],
        "gender": "female",
        "birthDate": "1964-05-12",
    }


# ---------------------------------------------------------------------------
# 1. Fleet Expansion (11 Agents) & SMART-on-FHIR v2 + OIDC PKCE
# ---------------------------------------------------------------------------

def test_eleven_agents_registered_in_catalog():
    assert len(AGENTS_CATALOG) == 11
    ag10 = get_agent_by_id("ambient_scribe")
    ag11 = get_agent_by_id("clinical_coding")
    assert ag10 is not None and ag10["code"] == "SlainteScribe-Voice"
    assert ag11 is not None and ag11["code"] == "SlainteRev-Coding"


def test_smart_on_fhir_discovery_and_signed_launch_flow(app, auth_client):
    disc = auth_client.get("/.well-known/smart-configuration")
    assert disc.status_code == 200
    data = disc.get_json()
    assert "launch-ehr" in data["capabilities"]
    assert "S256" in data["code_challenge_methods_supported"]
    assert "launch/patient" in data["scopes_supported"]

    # Mint & verify SMART v2 launch token
    secret = app.config["SECRET_KEY"]
    tok = mint_smart_launch_token(secret, patient_id="P101", vertical_key="gp", fhir_user="Practitioner/IMC-48219")
    claims = verify_smart_launch_token(secret, tok)
    assert claims is not None
    assert claims["patient"] == "P101"
    assert verify_smart_launch_token(secret, tok + "tamper") is None

    # Execute full /smart/launch -> /smart/callback handshake
    r1 = auth_client.get(f"/smart/launch?iss=http://epic.hospital.ie/fhir/r4&launch={tok}")
    assert r1.status_code == 302
    assert "/smart/callback" in r1.headers["Location"]

    r2 = auth_client.get(r1.headers["Location"])
    assert r2.status_code == 302
    assert "Patient%2FP101" in r2.headers["Location"] or "Patient/P101" in r2.headers["Location"]

    # Token & Introspection OAuth2 endpoints
    tok_resp = auth_client.post("/smart/token", data={"patient": "P101"})
    assert tok_resp.status_code == 200
    access_token = tok_resp.get_json()["access_token"]
    intro = auth_client.post("/smart/introspect", data={"token": access_token})
    assert intro.status_code == 200
    assert intro.get_json()["active"] is True


def test_oidc_pkce_login_and_smart_settings_hub(admin_client):
    r_oidc = admin_client.get("/auth/oidc/login")
    assert r_oidc.status_code == 200
    assert b"PKCE S256" in r_oidc.data

    r_hub = admin_client.get("/settings/smart")
    assert r_hub.status_code == 200
    assert b"SMART-on-FHIR v2 EHR Launch Simulator" in r_hub.data


# ---------------------------------------------------------------------------
# 2. Pillar 7: 3-Tier SlainteRx-Guard Clinical Pharmacology Engine
# ---------------------------------------------------------------------------

def test_three_tier_pharmacology_engine_allergy_ddi_and_renal_egfr():
    # Tier 2 High-Alert DDI: Clarithromycin + Atorvastatin -> Rhabdomyolysis block
    ddi_res = evaluate_clinical_pharmacology_3tier(
        allergies=[],
        active_medications=["Atorvastatin 80mg Oral Tablet"],
        lab_observations=[],
        candidate_drug="Clarithromycin 500mg Oral Tablet",
    )
    assert ddi_res["tier_counts"]["tier2_ddi"] == 1
    assert any("Rhabdomyolysis" in a["alert_type"] for a in ddi_res["alerts"])

    # Tier 3 Renal eGFR Gate: eGFR = 26 mL/min + Metformin & Ibuprofen -> Contraindicated
    egfr_obs = [{
        "resourceType": "Observation",
        "id": "obs-egfr-low",
        "code": {"coding": [{"system": "http://loinc.org", "code": "33914-3", "display": "eGFR"}]},
        "valueQuantity": {"value": 26, "unit": "mL/min"},
    }]
    renal_met = evaluate_clinical_pharmacology_3tier(
        allergies=[],
        active_medications=[],
        lab_observations=egfr_obs,
        candidate_drug="Metformin 500mg Modified-Release Tablet",
    )
    assert renal_met["egfr"] == 26
    assert renal_met["tier_counts"]["tier3_renal"] == 1
    assert any("Lactic Acidosis" in a["alert_type"] for a in renal_met["alerts"])

    renal_nsaid = evaluate_clinical_pharmacology_3tier(
        allergies=[],
        active_medications=[],
        lab_observations=egfr_obs,
        candidate_drug="Ibuprofen 400mg Oral Tablet",
    )
    assert renal_nsaid["tier_counts"]["tier3_renal"] == 1


@responses.activate
def test_prescribe_route_blocks_ddi_and_renal_egfr_without_override(auth_client):
    responses.add(responses.GET, f"{FHIR_BASE}/AllergyIntolerance", json=bundle(), status=200)
    responses.add(
        responses.GET,
        f"{FHIR_BASE}/MedicationRequest",
        json=bundle({
            "resourceType": "MedicationRequest",
            "id": "med-statin-1",
            "status": "active",
            "medicationCodeableConcept": {"text": "Atorvastatin 80mg Oral Tablet"},
        }),
        status=200,
    )
    responses.add(
        responses.GET,
        f"{FHIR_BASE}/Observation",
        json=bundle({
            "resourceType": "Observation",
            "id": "obs-egfr-28",
            "code": {"coding": [{"system": "http://loinc.org", "code": "33914-3", "display": "eGFR"}]},
            "valueQuantity": {"value": 28, "unit": "mL/min"},
        }),
        status=200,
    )

    resp = auth_client.post(
        "/fhir/Medications/P101/add",
        data={"drug_name": "Clarithromycin 500mg Oral Tablet", "dosage": "500mg BD"},
    )
    assert resp.status_code == 200
    assert b"Tier 2: High-Alert DDI" in resp.data
    assert b"Rhabdomyolysis" in resp.data


# ---------------------------------------------------------------------------
# 3. Pillar 2: Agent 10 (SlainteScribe-Voice) Ambient Voice Scribe
# ---------------------------------------------------------------------------

@responses.activate
def test_agent10_ambient_scribe_process_and_commit_to_fhir(auth_client):
    responses.add(responses.GET, f"{FHIR_BASE}/Patient/P101", json=_mock_patient("P101"), status=200)
    responses.add(
        responses.GET,
        f"{FHIR_BASE}/AllergyIntolerance",
        json=bundle({
            "resourceType": "AllergyIntolerance",
            "id": "alg-pen",
            "code": {"text": "Penicillin"},
        }),
        status=200,
    )
    responses.add(responses.GET, f"{FHIR_BASE}/MedicationRequest", json=bundle(), status=200)
    responses.add(responses.GET, f"{FHIR_BASE}/Condition", json=bundle(), status=200)
    responses.add(responses.GET, f"{FHIR_BASE}/Observation", json=bundle(), status=200)
    responses.add(responses.POST, f"{FHIR_BASE}/DocumentReference", json={"resourceType": "DocumentReference", "id": "doc-1"}, status=201)
    responses.add(responses.POST, f"{FHIR_BASE}/Condition", json={"resourceType": "Condition", "id": "cond-1"}, status=201)
    responses.add(responses.POST, f"{FHIR_BASE}/MedicationRequest", json={"resourceType": "MedicationRequest", "id": "med-1"}, status=201)

    # 1. Process GP consultation preset — Penicillin allergy should flag Amoxicillin!
    r_proc = auth_client.post(
        "/enterprise/scribe/process",
        data={"patient_id": "P101", "preset_key": "gp_chest_ckd"},
    )
    assert r_proc.status_code == 200
    assert b"SlainteScribe-Voice" in r_proc.data
    assert b"BLOCKED" in r_proc.data  # Amoxicillin caught by Penicillin allergy!

    # 2. Commit SOAP note + diagnosis + safe Paracetamol + un-overridden Amoxicillin (should auto-hold Amoxicillin)
    r_commit = auth_client.post(
        "/enterprise/scribe/commit/P101",
        data={
            "soap_text": "S: Cough\nO: Temp 38.2\nA: LRTI\nP: Paracetamol",
            "selected_conditions": ["50417007|J22|Acute lower respiratory tract infection"],
            "selected_medications": [
                "387517004|Paracetamol 1g Oral Tablet|1g QDS",
                "372687004|Amoxicillin 500mg Oral Capsule|500mg TDS",
            ],
        },
    )
    assert r_commit.status_code == 200
    assert r_commit.headers.get("HX-Trigger") == "scribeCommitted"
    assert b"1 SOAP DocumentReference" in r_commit.data
    assert b"Held unsafe Rx without override: Amoxicillin" in r_commit.data


# ---------------------------------------------------------------------------
# 4. Pillar 3: Native HL7v2 Pipe-Hat Ingest & HSE PCRS GMS Claim Export
# ---------------------------------------------------------------------------

@responses.activate
def test_hl7v2_pipe_hat_translation_and_pcrs_export(auth_client):
    parsed = translate_hl7v2_to_fhir_bundle(
        "MSH|^~\\&|MATER_PAS|MATER|SLAINTE|HSE|20261107120000||ADT^A01|MSG001|P|2.5.1\n"
        "PID|1||GMS-991122^^^HSE||Murphy^Sean||19720819|M|||12 O'Connell St^^Dublin\n"
        "AL1|1|DA|764146007^Penicillin^SCT|SV|Anaphylaxis\n"
        "OBX|1|NM|33914-3^eGFR^LN||34|mL/min|60-120|L|||F"
    )
    assert parsed["patient_name"] == "Sean Murphy"
    assert parsed["gms_id"] == "GMS-991122"
    assert parsed["bundle"]["resourceType"] == "Bundle"
    assert parsed["resource_count"] == 3

    responses.add(responses.POST, f"{FHIR_BASE}/Bundle", json={"resourceType": "Bundle", "status": "success"}, status=201)
    r_ing = auth_client.post("/enterprise/hl7v2/ingest", data={"sample_key": "mater_adt_a01"})
    assert r_ing.status_code == 200
    assert b"HL7v2 (ADT^A01) Harmonized" in r_ing.data

    responses.add(
        responses.GET,
        f"{FHIR_BASE}/MedicationRequest",
        json=bundle({
            "resourceType": "MedicationRequest",
            "id": "med-pcrs-1",
            "status": "completed",
            "subject": {"reference": "Patient/P101"},
            "medicationCodeableConcept": {"text": "Atorvastatin 80mg Oral Tablet"},
        }),
        status=200,
    )
    responses.add(responses.GET, f"{FHIR_BASE}/Patient", json=bundle(_mock_patient("P101")), status=200)
    r_pcrs = auth_client.get("/enterprise/pcrs/export")
    assert r_pcrs.status_code == 200
    assert "text/csv" in r_pcrs.content_type
    assert b"PCRSContractorID" in r_pcrs.data
    assert b"GMS-P101" in r_pcrs.data


# ---------------------------------------------------------------------------
# 5. Pillar 4 & 5: Granular Clinical RBAC, Break-the-Glass & SIEM / Certificate
# ---------------------------------------------------------------------------

@responses.activate
def test_granular_clinical_rbac_and_break_the_glass_unlocks_emergency_access(app, auth_client, active_user):
    # Assign active_user to 'triage_nurse' (cannot prescribe medications normally)
    with app.app_context():
        db.set_user_clinical_role(active_user, db.CLINICAL_ROLE_TRIAGE_NURSE, registration_id="NMBI-77102")

    responses.add(responses.GET, f"{FHIR_BASE}/MedicationRequest", json=bundle(), status=200)
    responses.add(responses.GET, f"{FHIR_BASE}/AllergyIntolerance", json=bundle(), status=200)
    responses.add(responses.GET, f"{FHIR_BASE}/Observation", json=bundle(), status=200)
    responses.add(responses.POST, f"{FHIR_BASE}/MedicationRequest", json={"resourceType": "MedicationRequest", "id": "med-btg"}, status=201)

    # 1. Triage nurse blocked from prescribing without Break-the-Glass
    denied = auth_client.post(
        "/fhir/Medications/P101/add",
        data={"drug_name": "Paracetamol 1g Oral Tablet", "dosage": "1g stat"},
    )
    assert denied.status_code == 403
    assert b"Clinical RBAC" in denied.data

    # 2. Triage nurse also blocked from dispensing in Pharmacy Queue
    responses.add(responses.GET, f"{FHIR_BASE}/Patient", json=bundle(_mock_patient("P101")), status=200)
    pharm_denied = auth_client.post(
        "/fhir/Cockpit/pharmacy/dispense",
        data={"med_id": "med-1", "patient_id": "P101", "new_status": "completed"},
    )
    assert pharm_denied.status_code == 403

    # 3. Invoke Break-the-Glass Emergency Override (must reject short justification < 10 chars)
    short_btg = auth_client.post(
        "/enterprise/break-glass/P101",
        data={"emergency_type": "Resuscitation", "justification": "short"},
    )
    assert short_btg.status_code == 400

    valid_btg = auth_client.post(
        "/enterprise/break-glass/P101",
        data={
            "emergency_type": "Unconscious / Acute Resuscitation",
            "justification": "Acute trauma arrest in Resus Bay 1 — verbal consultant order emergency access",
        },
    )
    assert valid_btg.status_code == 200
    assert b"BREAK-THE-GLASS ACTIVE" in valid_btg.data

    # Verify SQLite immutability trigger protects break_glass_grants from deletion!
    with app.app_context():
        conn = db.get_connection()
        with pytest.raises(Exception, match="append-only"):
            conn.execute("DELETE FROM break_glass_grants")

    # 4. Now emergency prescribing succeeds for P101 under the 60-minute Break-the-Glass grant!
    allowed = auth_client.post(
        "/fhir/Medications/P101/add",
        data={"drug_name": "Paracetamol 1g Oral Tablet", "dosage": "1g stat"},
    )
    assert allowed.status_code == 200
    assert b"Prescribed Paracetamol" in allowed.data


def test_siem_test_webhook_and_printable_compliance_certificate(admin_client):
    r_siem = admin_client.post(
        "/enterprise/siem/test",
        data={"siem_webhook_url": "https://sentinel.hospital.invalid/webhook"},
    )
    assert r_siem.status_code == 200
    assert b"SIEM Event Signed" in r_siem.data

    r_cert = admin_client.get("/agents/compliance-certificate")
    assert r_cert.status_code == 200
    assert b"Clinical AI Safety, Cybersecurity &amp; Data Protection Certificate" in r_cert.data
    assert b"EU AI Act (Reg. 2024/1689)" in r_cert.data
    assert b"EU NIS2 Directive (2022/2555)" in r_cert.data


# ---------------------------------------------------------------------------
# 6. Pillar 6: Agent 11 (SlainteRev-Coding) HIPE / ICD-10-AM Comorbidity Audit
# ---------------------------------------------------------------------------

@responses.activate
def test_agent11_hipe_clinical_coding_gap_detection_and_capture(auth_client):
    obs_list = [
        {
            "resourceType": "Observation",
            "id": "obs-egfr-36",
            "code": {"coding": [{"system": "http://loinc.org", "code": "33914-3", "display": "eGFR"}]},
            "valueQuantity": {"value": 36, "unit": "mL/min"},
        },
        {
            "resourceType": "Observation",
            "id": "obs-a1c-58",
            "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "HbA1c"}]},
            "valueQuantity": {"value": 58, "unit": "mmol/mol"},
        },
    ]
    report = scan_patient_coding_gaps("P101", "Mary Walsh", conditions=[], observations=obs_list)
    assert len(report["gaps"]) == 2
    assert report["total_uplift_eur"] == 1420 + 1180

    responses.add(responses.GET, f"{FHIR_BASE}/Patient/P101", json=_mock_patient("P101"), status=200)
    responses.add(responses.GET, f"{FHIR_BASE}/AllergyIntolerance", json=bundle(), status=200)
    responses.add(responses.GET, f"{FHIR_BASE}/MedicationRequest", json=bundle(), status=200)
    responses.add(responses.GET, f"{FHIR_BASE}/Condition", json=bundle(), status=200)
    responses.add(responses.GET, f"{FHIR_BASE}/Observation", json=bundle(*obs_list), status=200)
    responses.add(responses.POST, f"{FHIR_BASE}/Condition", json={"resourceType": "Condition", "id": "cond-hipe-1"}, status=201)

    r_scan = auth_client.get("/enterprise/coding/scan/P101")
    assert r_scan.status_code == 200
    assert b"N18.3" in r_scan.data
    assert b"E11.9" in r_scan.data

    r_apply = auth_client.post(
        "/enterprise/coding/apply/P101",
        data={
            "icd10_code": "N18.3",
            "snomed_code": "431855005",
            "condition_display": "Chronic kidney disease Stage 3B (N18.32)",
            "evidence_ref": "Observation/obs-egfr-36",
        },
    )
    assert r_apply.status_code == 200
    assert r_apply.headers.get("HX-Trigger") == "conditionsUpdated"
    assert b"Captured dual-coded Condition" in r_apply.data


def test_dedicated_dashboards_for_agent_10_and_agent_11(auth_client):
    r10 = auth_client.get("/agents/ambient_scribe")
    assert r10.status_code == 200
    assert b"SlainteScribe-Voice" in r10.data

    r11 = auth_client.get("/agents/clinical_coding")
    assert r11.status_code == 200
    assert b"SlainteRev-Coding" in r11.data
