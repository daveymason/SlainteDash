import pytest
from fhir_utils import calculate_news2_score, check_drug_allergy_contraindications, generate_vitals_trajectory
from local_fhir_store import LocalFhirStore

def test_news2_trajectory_generation():
    vitals = {
        'systolic_bp': 85,
        'heart_rate': 135,
        'respiratory_rate': 28,
        'spo2': 90,
        'temperature': 39.2,
        'gcs': 12
    }
    traj = generate_vitals_trajectory(vitals)
    assert traj['current_score'] >= 7
    assert traj['current_tier'] == 'High Risk'
    assert len(traj['trajectory']) == 6
    assert 'svg_polyline' in traj
    assert traj['color'] == '#dc3545'

def test_drug_allergy_contraindication_interception():
    allergies = [{'text': 'Penicillin V anaphylaxis', 'code': '91936005'}]
    meds = ['Augmentin 625mg', 'Paracetamol 1g']
    alerts = check_drug_allergy_contraindications(allergies, meds)
    assert len(alerts) >= 1
    assert alerts[0]['severity'] == 'CRITICAL'
    assert alerts[0]['allergen'] == 'Penicillin'

def test_provenance_sign_off_lifecycle(tmp_path):
    store = LocalFhirStore(str(tmp_path))
    # Seed patient
    patient_bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "P500",
                    "name": [{"text": "Patrick O'Sullivan"}]
                }
            }
        ]
    }
    store.save_bundle(patient_bundle, "bundle_P500.json")
    
    # Verify initially not signed off
    assert store.get_provenance("P500") is None
    
    # Clinician signs off
    prov = store.sign_off_patient(
        patient_id="P500",
        practitioner_id="IMC-99881",
        practitioner_role="Consultant in Emergency Medicine",
        signature_text="Dr. Fiona Gallagher",
        practitioner_name="admin"
    )
    
    assert prov["resourceType"] == "Provenance"
    assert prov["recorded"] is not None
    assert prov["agent"][0]["who"]["identifier"]["value"] == "IMC-99881"
    assert prov["agent"][0]["role"][0]["text"] == "Consultant in Emergency Medicine"
    assert len(prov["signature"][0]["data"]) == 64  # SHA-256 hash
    
    # Verify retrieval
    stored_prov = store.get_provenance("P500")
    assert stored_prov is not None
    assert stored_prov["id"] == prov["id"]

def test_safety_gate_route(admin_client):
    res = admin_client.post('/fhir/validate-safety', data={
        'medications': 'Amoxicillin 500mg TDS',
        'allergies': 'Penicillin severe allergy'
    })
    assert res.status_code == 200
    assert b'CDS GATE INTERCEPTED' in res.data
    assert b'CRITICAL' in res.data

def test_sign_off_route(admin_client):
    res = admin_client.post('/fhir/patient/P001/sign-off', data={
        'practitioner_id': 'IMC-77210',
        'practitioner_role': 'Emergency Physician',
        'signature_confirm': 'Dr. Niall Horan'
    })
    assert res.status_code == 200
    assert b'Assessment Verified &amp; Signed' in res.data
    assert b'IMC-77210' in res.data

