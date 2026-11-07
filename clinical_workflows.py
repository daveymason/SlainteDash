"""Clinical Write Workflows & Specialty Cockpit Builders (Buckets A & B).

Provides deterministic HL7 FHIR R4 resource builders, curated SNOMED-CT / LOINC /
UCUM clinical catalogs, FDI 32-tooth odontogram & 6-sextant BPE builders, and
dual-store persistence helpers for Slainte-Engine.
"""
import base64
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


CLINICAL_CONDITIONS_CATALOG: List[Tuple[str, str]] = [
    ("29857009", "Acute chest pain / suspected ACS"),
    ("57054005", "Acute ST-Elevation Myocardial Infarction (STEMI)"),
    ("195967001", "Acute exacerbation of asthma"),
    ("13645005", "Chronic obstructive pulmonary disease (COPD)"),
    ("44054006", "Type 2 diabetes mellitus"),
    ("38341003", "Essential hypertension"),
    ("431855005", "Chronic kidney disease stage 3A"),
    ("74400008", "Acute appendicitis"),
    ("91302008", "Sepsis / systemic inflammatory response"),
    ("195662009", "Acute bacterial pharyngitis"),
    ("44465007", "Sprain of ankle"),
    ("396275006", "Osteoarthritis of knee"),
    ("109570007", "Irreversible pulpitis (Dental)"),
    ("328383001", "Symptomatic apical periodontitis (Dental)"),
    ("110030002", "Concussion / mild traumatic brain injury (SCAT6)"),
    ("386661006", "Acute febrile illness / pyrexia"),
    ("267036007", "Acute dyspnea / hypoxia drift"),
]

CLINICAL_MEDICATIONS_CATALOG: List[Tuple[str, str, str]] = [
    ("372687004", "Amoxicillin 500mg / Clavulanate 125mg Oral Tablet", "1 tablet orally TDS for 7 days"),
    ("372687004", "Amoxicillin 500mg Oral Capsule", "500mg orally TDS for 5 days"),
    ("387467008", "Clarithromycin 500mg Oral Tablet", "500mg orally BD for 7 days"),
    ("372840008", "Metronidazole 400mg Oral Tablet", "400mg orally TDS for 5 days"),
    ("372756006", "Cefuroxime 1.5g IV Infusion", "1.5g IV q8h"),
    ("387458008", "Aspirin 300mg Dispersible Tablet", "300mg orally stat"),
    ("387207008", "Ibuprofen 400mg Oral Tablet", "400mg orally TDS with food"),
    ("387517004", "Paracetamol 1g Oral Tablet", "1g orally QDS PRN (max 4g/24h)"),
    ("372826007", "Ticagrelor 90mg Oral Tablet", "90mg orally BD"),
    ("373444002", "Atorvastatin 80mg Oral Tablet", "80mg orally ON"),
    ("386872004", "Ramipril 5mg Oral Capsule", "5mg orally OD"),
    ("372567009", "Metformin 500mg Modified-Release Tablet", "500mg orally BD with meals"),
    ("372912004", "Empagliflozin 10mg Oral Tablet", "10mg orally OD"),
    ("372897005", "Salbutamol 100mcg CFC-Free Inhaler", "2 puffs inhaled QDS PRN wheeze"),
    ("387137007", "Omeprazole 20mg Gastro-Resistant Capsule", "20mg orally OD"),
    ("387253001", "Prednisolone 40mg Oral Dose", "40mg orally OD for 5 days"),
]

CLINICAL_ALLERGENS_CATALOG: List[Tuple[str, str]] = [
    ("764146007", "Penicillin"),
    ("372687004", "Amoxicillin / Beta-Lactams"),
    ("387458008", "Aspirin / NSAIDs"),
    ("372735009", "Sulfonamide Antibiotics"),
    ("111088007", "Natural Rubber Latex"),
    ("387494007", "Codeine / Opioids"),
    ("373270004", "Iodinated Contrast Media"),
    ("387420009", "ACE Inhibitors (Lisinopril / Ramipril)"),
]

NOTE_TYPES_CATALOG: List[Tuple[str, str, str]] = [
    ("11506-3", "SOAP Clinical Consultation Note", "Progress / GP Consultation"),
    ("28651-8", "Emergency Handover & Triage Note", "ED / EMS Handover"),
    ("28570-0", "Dental Operative & Periodontal Note", "Dental Procedure"),
    ("56445-0", "Pharmacist Clinical Intervention Note", "Medication Review"),
    ("34109-9", "Flight Surgeon / Sports Clearance Note", "Clearance Evaluation"),
]

# FDI Two-Digit Adult Dentition (Upper Right 18..11, Upper Left 21..28, Lower Right 48..41, Lower Left 31..38)
FDI_UPPER_RIGHT = ["18", "17", "16", "15", "14", "13", "12", "11"]
FDI_UPPER_LEFT = ["21", "22", "23", "24", "25", "26", "27", "28"]
FDI_LOWER_RIGHT = ["48", "47", "46", "45", "44", "43", "42", "41"]
FDI_LOWER_LEFT = ["31", "32", "33", "34", "35", "36", "37", "38"]
ALL_FDI_TEETH = FDI_UPPER_RIGHT + FDI_UPPER_LEFT + FDI_LOWER_RIGHT + FDI_LOWER_LEFT

TOOTH_STATUS_META: Dict[str, Dict[str, str]] = {
    "sound": {"label": "Sound", "short": "OK", "bg": "#FFFFFF", "border": "#CBD5E1", "text": "#1E293B"},
    "carious": {"label": "Caries / Pulpitis", "short": "CAR", "bg": "#FEE2E2", "border": "#DC2626", "text": "#991B1B"},
    "restored": {"label": "Restored / Filling", "short": "FIL", "bg": "#DBEAFE", "border": "#2563EB", "text": "#1E40AF"},
    "endodontic": {"label": "Root Canal (RCT)", "short": "RCT", "bg": "#FEF3C7", "border": "#D97706", "text": "#92400E"},
    "crown": {"label": "Crown / Prosthesis", "short": "CRN", "bg": "#E0E7FF", "border": "#4F46E5", "text": "#3730A3"},
    "extraction_planned": {"label": "Extraction Planned", "short": "EXT", "bg": "#FFEDD5", "border": "#EA580C", "text": "#9A3412"},
    "missing": {"label": "Missing / Extracted", "short": "MIS", "bg": "#F1F5F9", "border": "#94A3B8", "text": "#64748B"},
}

BPE_SEXTANTS = [
    ("ur", "UR (17–14)"),
    ("ua", "UA (13–23)"),
    ("ul", "UL (24–27)"),
    ("lr", "LR (47–44)"),
    ("la", "LA (43–33)"),
    ("ll", "LL (34–37)"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def lookup_condition_code(text: str) -> str:
    t_low = text.strip().lower()
    for code, disp in CLINICAL_CONDITIONS_CATALOG:
        if disp.lower() == t_low or t_low in disp.lower():
            return code
    return "404684003"  # Clinical finding (SNOMED-CT)


def lookup_medication_code(text: str) -> str:
    t_low = text.strip().lower()
    for code, disp, _dose in CLINICAL_MEDICATIONS_CATALOG:
        if disp.lower() == t_low or t_low in disp.lower():
            return code
    return "108774000"  # Pharmaceutical product


def lookup_allergen_code(text: str) -> str:
    t_low = text.strip().lower()
    for code, disp in CLINICAL_ALLERGENS_CATALOG:
        if disp.lower() == t_low or t_low in disp.lower():
            return code
    return "419199007"  # Allergy to substance


def build_medication_request(
    patient_id: str,
    drug_name: str,
    dosage_text: str,
    snomed_code: str = "",
    author: str = "Clinician",
    override_reason: str = "",
) -> Dict[str, Any]:
    code = snomed_code or lookup_medication_code(drug_name)
    ts = now_iso()
    med_id = f"med-{patient_id}-{int(time.time() * 1000)}"
    res: Dict[str, Any] = {
        "resourceType": "MedicationRequest",
        "id": med_id,
        "status": "active",
        "intent": "order",
        "authoredOn": ts,
        "requester": {"display": author},
        "medicationCodeableConcept": {
            "coding": [{"system": "http://snomed.info/sct", "code": code, "display": drug_name}],
            "text": drug_name,
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "dosageInstruction": [{"text": dosage_text or "As directed by prescriber"}],
    }
    if override_reason:
        res["note"] = [{"text": f"Rx-Guard Clinical Override by {author}: {override_reason}", "time": ts}]
    return res


def build_vital_observations(patient_id: str, vitals: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build standard HL7 FHIR R4 vital-signs Observations sharing an exact timestamp."""
    ts = now_iso()
    enc_ref = f"Encounter/enc-vitals-{int(time.time())}"
    specs = [
        ("systolic_bp", "8480-6", "Systolic Blood Pressure", "mmHg", "mm[Hg]"),
        ("diastolic_bp", "8462-4", "Diastolic Blood Pressure", "mmHg", "mm[Hg]"),
        ("heart_rate", "8867-4", "Heart Rate", "bpm", "/min"),
        ("spo2", "59408-5", "Oxygen Saturation (SpO2)", "%", "%"),
        ("respiratory_rate", "9279-1", "Respiratory Rate", "/min", "/min"),
        ("temperature", "8310-5", "Body Temperature", "Cel", "Cel"),
        ("pain", "72514-3", "Pain Score", "{score}", "{score}"),
    ]
    created: List[Dict[str, Any]] = []
    ms = int(time.time() * 1000)
    for field_key, loinc, display, unit, ucum in specs:
        raw_val = vitals.get(field_key)
        if raw_val in (None, ""):
            continue
        try:
            num_val = float(raw_val)
        except (TypeError, ValueError):
            continue
        obs = {
            "resourceType": "Observation",
            "id": f"obs-{field_key}-{patient_id}-{ms}",
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "vital-signs",
                    "display": "Vital Signs",
                }],
                "text": "Vital Signs",
            }],
            "code": {
                "coding": [{"system": "http://loinc.org", "code": loinc, "display": display}],
                "text": display,
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": enc_ref},
            "effectiveDateTime": ts,
            "valueQuantity": {
                "value": num_val,
                "unit": unit,
                "system": "http://unitsofmeasure.org",
                "code": ucum,
            },
        }
        created.append(obs)
    return created


def build_condition_resource(
    patient_id: str,
    condition_text: str,
    snomed_code: str = "",
    clinical_status: str = "active",
) -> Dict[str, Any]:
    code = snomed_code or lookup_condition_code(condition_text)
    ts = now_iso()
    status_clean = clinical_status if clinical_status in ("active", "resolved", "inactive") else "active"
    return {
        "resourceType": "Condition",
        "id": f"cond-{patient_id}-{int(time.time() * 1000)}",
        "clinicalStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code": status_clean,
                "display": status_clean.capitalize(),
            }]
        },
        "verificationStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code": "confirmed",
                "display": "Confirmed",
            }]
        },
        "code": {
            "coding": [{"system": "http://snomed.info/sct", "code": code, "display": condition_text}],
            "text": condition_text,
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "recordedDate": ts,
        "onsetDateTime": ts,
    }


def build_allergy_resource(
    patient_id: str,
    allergen_text: str,
    criticality: str = "high",
    reaction_text: str = "",
    snomed_code: str = "",
) -> Dict[str, Any]:
    code = snomed_code or lookup_allergen_code(allergen_text)
    ts = now_iso()
    crit_clean = criticality if criticality in ("high", "low", "unable-to-assess") else "high"
    res: Dict[str, Any] = {
        "resourceType": "AllergyIntolerance",
        "id": f"alg-{patient_id}-{int(time.time() * 1000)}",
        "clinicalStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                "code": "active",
                "display": "Active",
            }]
        },
        "verificationStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                "code": "confirmed",
                "display": "Confirmed",
            }]
        },
        "criticality": crit_clean,
        "code": {
            "coding": [{"system": "http://snomed.info/sct", "code": code, "display": allergen_text}],
            "text": allergen_text,
        },
        "patient": {"reference": f"Patient/{patient_id}"},
        "recordedDate": ts,
    }
    if reaction_text.strip():
        res["reaction"] = [{
            "manifestation": [{
                "coding": [{"system": "http://snomed.info/sct", "code": "418363000", "display": reaction_text.strip()}],
                "text": reaction_text.strip(),
            }]
        }]
    return res


def build_clinical_note(
    patient_id: str,
    note_type_code: str,
    note_text: str,
    author_username: str,
    vertical_brand: str = "SlainteDash",
) -> Dict[str, Any]:
    ts = now_iso()
    type_display = "Clinical Consultation Note"
    for code, disp, _cat in NOTE_TYPES_CATALOG:
        if code == note_type_code:
            type_display = disp
            break
    encoded = base64.b64encode(note_text.encode("utf-8")).decode("ascii")
    return {
        "resourceType": "DocumentReference",
        "id": f"doc-{patient_id}-{int(time.time() * 1000)}",
        "status": "current",
        "type": {
            "coding": [{"system": "http://loinc.org", "code": note_type_code or "11506-3", "display": type_display}],
            "text": type_display,
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "date": ts,
        "author": [{"display": f"{author_username} ({vertical_brand})"}],
        "description": type_display,
        "content": [{
            "attachment": {
                "contentType": "text/plain; charset=utf-8",
                "data": encoded,
                "title": type_display,
                "creation": ts,
            }
        }],
    }


def extract_note_view(doc: Dict[str, Any]) -> Dict[str, str]:
    raw_b64 = (
        ((doc.get("content") or [{}])[0].get("attachment") or {}).get("data") or ""
    )
    decoded = ""
    if raw_b64:
        try:
            decoded = base64.b64decode(raw_b64).decode("utf-8", errors="replace")
        except Exception:
            decoded = ""
    if not decoded:
        decoded = doc.get("description") or ""
    authors = doc.get("author") or []
    author_disp = authors[0].get("display", "Clinician") if authors and isinstance(authors[0], dict) else "Clinician"
    title = (doc.get("type") or {}).get("text") or doc.get("description") or "Clinical Note"
    return {
        "id": doc.get("id", ""),
        "date": doc.get("date", ""),
        "title": title,
        "author": author_disp,
        "body": decoded,
    }


def build_dental_chart_observation(
    patient_id: str,
    teeth_map: Dict[str, str],
    bpe_map: Dict[str, str],
    author_username: str,
    notes: str = "",
) -> Dict[str, Any]:
    ts = now_iso()
    payload_json = json.dumps({
        "teeth": teeth_map,
        "bpe": bpe_map,
        "author": author_username,
        "notes": notes,
    })
    return {
        "resourceType": "Observation",
        "id": f"obs-dental-chart-{patient_id}",
        "status": "final",
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "exam",
                "display": "Exam",
            }],
            "text": "Dental & Periodontal Examination",
        }],
        "code": {
            "coding": [{"system": "http://snomed.info/sct", "code": "275983008", "display": "FDI Odontogram & BPE Chart"}],
            "text": "FDI 32-Tooth Odontogram & 6-Sextant BPE Periodontal Assessment",
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": ts,
        "performer": [{"display": author_username}],
        "valueString": payload_json,
    }


def parse_dental_chart_observation(obs_entries: List[Dict[str, Any]], patient_id: str = "") -> Dict[str, Any]:
    default_teeth = {t: "sound" for t in ALL_FDI_TEETH}
    if patient_id == "patient-case-8":
        default_teeth["46"] = "carious"
        default_teeth["36"] = "restored"
        default_teeth["16"] = "restored"
        default_teeth["26"] = "crown"
    default_bpe = {"ur": "1", "ua": "0", "ul": "1", "lr": "3", "la": "1", "ll": "2"}
    result = {
        "teeth": default_teeth,
        "bpe": default_bpe,
        "author": "Dental Suite Baseline",
        "updated": "Baseline Chart",
        "notes": "",
    }
    for obs in reversed(obs_entries):
        if not isinstance(obs, dict):
            continue
        if obs.get("id") == f"obs-dental-chart-{patient_id}" or "Odontogram" in str((obs.get("code") or {}).get("text", "")):
            raw = obs.get("valueString")
            if raw:
                try:
                    parsed = json.loads(raw)
                    merged_teeth = dict(default_teeth)
                    for k, v in (parsed.get("teeth") or {}).items():
                        if k in merged_teeth and v in TOOTH_STATUS_META:
                            merged_teeth[k] = v
                    merged_bpe = dict(default_bpe)
                    for k, v in (parsed.get("bpe") or {}).items():
                        if k in merged_bpe:
                            merged_bpe[k] = str(v)
                    result["teeth"] = merged_teeth
                    result["bpe"] = merged_bpe
                    result["author"] = parsed.get("author") or "Dental Surgeon"
                    result["notes"] = parsed.get("notes") or ""
                    result["updated"] = (obs.get("effectiveDateTime") or "")[:19].replace("T", " ")
                    break
                except Exception:
                    continue
    return result


def build_provenance_signoff(
    patient_id: str,
    practitioner_id: str,
    practitioner_role: str,
    signature_text: str,
    author_username: str,
) -> Dict[str, Any]:
    import hashlib
    ts = now_iso()
    sig_payload = f"{patient_id}:{practitioner_id}:{practitioner_role}:{signature_text}:{ts}".encode("utf-8")
    digest = hashlib.sha256(sig_payload).hexdigest()
    sig_b64 = base64.b64encode(digest.encode("ascii")).decode("ascii")
    return {
        "resourceType": "Provenance",
        "id": f"prov-{patient_id}",
        "target": [{"reference": f"Patient/{patient_id}"}],
        "recorded": ts,
        "agent": [{
            "role": [{"text": practitioner_role}],
            "who": {
                "identifier": {"system": "urn:oid:2.16.840.1.113883.2.1.3.2.4.16.2", "value": practitioner_id},
                "display": f"{signature_text} ({author_username})",
            },
        }],
        "signature": [{
            "type": [{
                "system": "urn:iso-astm:E1762-95:2013",
                "code": "1.2.840.10065.1.12.1.1",
                "display": "Author's Signature",
            }],
            "when": ts,
            "who": {"display": signature_text},
            "sigFormat": "application/signature+sha256",
            "data": sig_b64,
        }],
    }


def persist_fhir_resource(fhir_client: Any, app_config: Dict[str, Any], resource: Dict[str, Any], is_update: bool = False):
    """Write an HL7 FHIR R4 resource to the active FHIR backend AND sync local bundle store."""
    rt = resource.get("resourceType", "")
    rid = resource.get("id", "")
    if is_update and rid:
        res = fhir_client.put(f"{rt}/{rid}", json_data=resource)
    else:
        res = fhir_client.post(rt, json_data=resource)

    # Mirror to local bundle directory when not running against unit-test mock URL
    server_url = str(app_config.get("FHIR_SERVER_URL", ""))
    if "example.invalid" not in server_url and not app_config.get("TESTING"):
        try:
            from local_fhir_store import LocalFhirStore
            store_dir = app_config.get("FHIR_STORE_PATH", "/workspace/data/fhir_store")
            if not os.path.isdir(store_dir):
                store_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "fhir_store"))
            if os.path.isdir(store_dir):
                lfs = LocalFhirStore(store_dir)
                lfs._upsert_local_resource(res.data if (res.ok and isinstance(res.data, dict) and res.data.get("resourceType")) else resource)
        except Exception:
            pass
    return res
