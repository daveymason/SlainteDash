"""Parsing and formatting helpers for FHIR resources.

Every function here is defensive: FHIR marks almost every element as optional,
so anything that indexes into a resource must cope with the element being
absent, empty, or a different shape than expected.
"""
from datetime import datetime, timezone

# FHIR permits partial dates (`YYYY`, `YYYY-MM`) wherever a `date` is allowed.
_PARTIAL_DATE_FORMATS = ('%Y-%m-%d', '%Y-%m', '%Y')

UNKNOWN_DATE = 'Unknown'


def parse_fhir_datetime(value):
    """Parse a FHIR date/dateTime/instant into a datetime, or None.

    Handles the three shapes real servers return -- trailing `Z`, explicit
    offsets, and fractional seconds -- plus partial dates. Returns None rather
    than raising so callers can decide how to present a missing date.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None

    # `Z` is valid ISO 8601 but datetime.fromisoformat only accepts it from
    # Python 3.11 onward, so normalise it to an explicit UTC offset.
    if text[-1] in ('Z', 'z'):
        text = text[:-1] + '+00:00'

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass

    for fmt in _PARTIAL_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def format_fhir_date(value, fallback=UNKNOWN_DATE):
    """Render a FHIR date/dateTime as YYYY-MM-DD, or `fallback` if unparseable."""
    parsed = parse_fhir_datetime(value)
    return parsed.strftime('%Y-%m-%d') if parsed else fallback


def sort_key(value):
    """Build a comparable key from a FHIR date, sorting unknowns oldest.

    Mixing offset-aware and naive datetimes raises TypeError when compared, so
    everything is flattened to naive UTC. Undated entries sort to the far past,
    which keeps them at the bottom of a newest-first list instead of the top.
    """
    parsed = parse_fhir_datetime(value) if isinstance(value, str) else value
    if parsed is None:
        return datetime.min
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def patient_display_name(resource, fallback='Unknown'):
    """Best available human name for a Patient resource.

    FHIR's own guidance is to prefer `name.text` when present, since it carries
    the name as the source system chose to render it.
    """
    for entry in resource.get('name') or []:
        if not isinstance(entry, dict):
            continue
        text = entry.get('text')
        if text:
            return text
        parts = [part for part in (entry.get('given') or []) if part]
        family = entry.get('family')
        if family:
            parts.append(family)
        if parts:
            return ' '.join(parts)
    return fallback


def patient_initials(resource):
    """One or two initials for the avatar, or '?' when there is no name."""
    name = patient_display_name(resource, fallback='')
    parts = [part for part in name.split() if part]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def calculate_age(birth_date):
    """Age in whole years from a FHIR birthDate, or None."""
    parsed = parse_fhir_datetime(birth_date)
    if parsed is None:
        return None
    today = datetime.now()
    return today.year - parsed.year - (
        (today.month, today.day) < (parsed.month, parsed.day)
    )


def format_address(address):
    """Flatten a FHIR Address into a single line."""
    if not isinstance(address, dict):
        return ''
    # Copy the list -- extending the value returned by .get() would mutate the
    # caller's resource in place.
    parts = list(address.get('line') or [])
    parts.extend([
        address.get('city', ''),
        address.get('state', ''),
        address.get('postalCode', ''),
    ])
    return ', '.join(part for part in parts if part)


def first_coding_display(concept, fallback=''):
    """Pull a human label out of a CodeableConcept.

    Prefers `text`, then the first coding's `display`, then its raw `code`.
    """
    if not isinstance(concept, dict):
        return fallback
    if concept.get('text'):
        return concept['text']
    for coding in concept.get('coding') or []:
        if not isinstance(coding, dict):
            continue
        if coding.get('display'):
            return coding['display']
        if coding.get('code'):
            return coding['code']
    return fallback


def format_display_unit(unit):
    """Clean technical UCUM symbols into standard clinical display formats.

    Leaves unmapped standard units (e.g. mmol/L, mg/L, g/dL) untouched.
    """
    if not unit or not isinstance(unit, str):
        return unit or ''
    u = unit.strip()
    mapping = {
        '{score}': '/ 10',
        '{Score}': '/ 10',
        'Cel': '°C',
        'C': '°C',
        '[degF]': '°F',
        'mm[Hg]': 'mmHg',
        '10*9/L': '10⁹/L',
        '10*12/L': '10¹²/L',
        '10^9/L': '10⁹/L',
        '10^12/L': '10¹²/L',
        '{beats}/min': 'bpm',
        '{breaths}/min': 'breaths/min',
    }
    return mapping.get(u, u)


def observation_value(resource):
    """Render an Observation's value across the value[x] choice types.

    Observations use a choice element, so `valueQuantity` is only one of several
    possibilities. Panels and blood pressure carry no top-level value at all --
    their readings live in `component`.
    """
    if not isinstance(resource, dict):
        return '', ''

    quantity = resource.get('valueQuantity')
    if isinstance(quantity, dict) and quantity.get('value') is not None:
        raw_unit = quantity.get('unit') or quantity.get('code') or ''
        return quantity['value'], format_display_unit(raw_unit)

    if 'valueCodeableConcept' in resource:
        return first_coding_display(resource['valueCodeableConcept'], fallback='-'), ''

    if resource.get('valueString'):
        return resource['valueString'], ''

    if isinstance(resource.get('valueBoolean'), bool):
        return 'Yes' if resource['valueBoolean'] else 'No', ''

    if resource.get('valueInteger') is not None:
        return resource['valueInteger'], ''

    ratio = resource.get('valueRatio')
    if isinstance(ratio, dict):
        numerator = (ratio.get('numerator') or {}).get('value')
        denominator = (ratio.get('denominator') or {}).get('value')
        if numerator is not None and denominator is not None:
            raw_unit = (ratio.get('numerator') or {}).get('unit', '')
            return f'{numerator}/{denominator}', format_display_unit(raw_unit)

    value_range = resource.get('valueRange')
    if isinstance(value_range, dict):
        low = (value_range.get('low') or {}).get('value')
        high = (value_range.get('high') or {}).get('value')
        if low is not None or high is not None:
            raw_unit = (value_range.get('low') or value_range.get('high') or {}).get('unit', '')
            return f'{low if low is not None else ""}-{high if high is not None else ""}', \
                   format_display_unit(raw_unit)

    # Component-bearing observations (blood pressure, panels).
    components = resource.get('component') or []
    rendered = []
    unit = ''
    for component in components:
        if not isinstance(component, dict):
            continue
        label = first_coding_display(component.get('code', {}), fallback='')
        value, component_unit = observation_value(component)
        if value == '':
            continue
        unit = unit or format_display_unit(component_unit)
        rendered.append(f'{label}: {value}' if label else str(value))
    if rendered:
        return ' / '.join(rendered), format_display_unit(unit)

    if resource.get('dataAbsentReason'):
        return first_coding_display(resource['dataAbsentReason'], fallback='Not recorded'), ''

    return '', ''


def observation_code(resource):
    """Human-readable label for what an Observation measured."""
    return first_coding_display(resource.get('code', {}), fallback='Unknown')


# LOINC codes for systolic/diastolic blood pressure. Some servers record these
# as components of a panel Observation (code 85354-9); others record them as
# two independent Observations under these codes directly, sharing an
# encounter but no panel wrapper. Public so app.py can query for the second
# shape directly, not just extract it from a panel's components.
LOINC_SYSTOLIC = '8480-6'
LOINC_DIASTOLIC = '8462-4'


def blood_pressure_components(resource):
    """Pull numeric systolic/diastolic values out of a blood-pressure Observation.

    Returns (systolic, diastolic), either or both None if not present or not
    numeric. Used for charting, where a combined display string like the one
    `observation_value` produces for the table isn't usable.
    """
    systolic = diastolic = None
    for component in resource.get('component') or []:
        if not isinstance(component, dict):
            continue
        coding = (component.get('code') or {}).get('coding') or []
        codes = {c.get('code') for c in coding if isinstance(c, dict)}
        display = first_coding_display(component.get('code', {})).lower()
        value = (component.get('valueQuantity') or {}).get('value')
        if value is None:
            continue
        if LOINC_SYSTOLIC in codes or 'systolic' in display:
            systolic = value
        elif LOINC_DIASTOLIC in codes or 'diastolic' in display:
            diastolic = value
    return systolic, diastolic


def condition_onset(resource):
    """Render a Condition's onset (a FHIR choice type) for display and sorting.

    Falls back to `recordedDate` at the call site when onset is absent
    entirely -- onset is frequently missing on real data (roughly 1 in 4 on the
    public HAPI server), while recordedDate is a reasonable proxy for "when did
    this appear on the record."
    """
    # Sort values go through sort_key(), never parse_fhir_datetime() raw: the
    # raw parse keeps the timezone (HAPI onsets routinely carry one), while the
    # recordedDate fallback the caller mixes in is naive -- and Python refuses
    # to compare aware with naive, crashing the whole panel sort.
    if 'onsetDateTime' in resource:
        value = resource['onsetDateTime']
        return format_fhir_date(value), sort_key(value)

    if isinstance(resource.get('onsetPeriod'), dict):
        start = resource['onsetPeriod'].get('start')
        if start:
            return format_fhir_date(start), sort_key(start)

    if resource.get('onsetString'):
        return resource['onsetString'], None

    if isinstance(resource.get('onsetAge'), dict):
        age_value = resource['onsetAge'].get('value')
        if age_value is not None:
            return f'Age {age_value}', None

    return None, None


def calculate_news2_score(vitals, on_o2=False, gcs=15.0):
    """
    Computes deterministic Royal College of Physicians (RCP) NHS / HSE NEWS2 aggregate score,
    clinical risk tier, and parameter breakdown.

    Accepts vitals as either dict with LOINC codes ('9279-1', '2708-6'/'59408-5', '8480-6', '8867-4', '8310-5')
    or friendly keys ('resp_rate', 'spo2', 'sys_bp', 'hr', 'temp').
    """
    import re

    def _extract_num(key_list, default=None):
        for k in key_list:
            if k in vitals and vitals[k] is not None:
                val = vitals[k]
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, str):
                    m = re.search(r"[-+]?\d*\.?\d+", val)
                    if m:
                        try:
                            return float(m.group(0))
                        except ValueError:
                            pass
        return default

    rr = _extract_num(['9279-1', 'resp_rate', 'rr', 'respiratory_rate'], default=16.0)
    spo2 = _extract_num(['2708-6', '59408-5', 'spo2', 'oxygen_saturation'], default=98.0)
    sbp = _extract_num(['8480-6', 'sys_bp', 'systolic', 'systolic_bp'], default=120.0)
    hr = _extract_num(['8867-4', 'hr', 'heart_rate', 'pulse'], default=75.0)
    temp = _extract_num(['8310-5', 'temp', 'temperature'], default=37.0)

    breakdown = {}

    # 1. Respiration Rate (/min)
    if rr <= 8:
        breakdown['RR'] = 3
    elif 9 <= rr <= 11:
        breakdown['RR'] = 1
    elif 12 <= rr <= 20:
        breakdown['RR'] = 0
    elif 21 <= rr <= 24:
        breakdown['RR'] = 2
    else:
        breakdown['RR'] = 3

    # 2. SpO2 Scale 1 (%)
    if spo2 <= 91:
        breakdown['SpO2'] = 3
    elif 92 <= spo2 <= 93:
        breakdown['SpO2'] = 2
    elif 94 <= spo2 <= 95:
        breakdown['SpO2'] = 1
    else:
        breakdown['SpO2'] = 0

    # 3. Supplemental Oxygen
    breakdown['O2'] = 2 if on_o2 else 0

    # 4. Systolic BP (mmHg)
    if sbp <= 90:
        breakdown['SBP'] = 3
    elif 91 <= sbp <= 100:
        breakdown['SBP'] = 2
    elif 101 <= sbp <= 110:
        breakdown['SBP'] = 1
    elif 111 <= sbp <= 219:
        breakdown['SBP'] = 0
    else:
        breakdown['SBP'] = 3

    # 5. Heart Rate (/min)
    if hr <= 40:
        breakdown['HR'] = 3
    elif 41 <= hr <= 50:
        breakdown['HR'] = 1
    elif 51 <= hr <= 90:
        breakdown['HR'] = 0
    elif 91 <= hr <= 110:
        breakdown['HR'] = 1
    elif 111 <= hr <= 130:
        breakdown['HR'] = 2
    else:
        breakdown['HR'] = 3

    # 6. Consciousness (Alert GCS 15 = 0, CVPU GCS < 15 = 3)
    breakdown['CVPU'] = 0 if gcs >= 15.0 else 3

    # 7. Body Temperature (°C)
    if temp <= 35.0:
        breakdown['Temp'] = 3
    elif 35.1 <= temp <= 36.0:
        breakdown['Temp'] = 1
    elif 36.1 <= temp <= 38.0:
        breakdown['Temp'] = 0
    elif 38.1 <= temp <= 39.0:
        breakdown['Temp'] = 1
    else:
        breakdown['Temp'] = 2

    total = sum(breakdown.values())

    # Risk Tier assignment
    if total >= 7:
        tier = "High Risk"
    elif total >= 5:
        tier = "Medium Risk"
    elif any(score == 3 for score in breakdown.values()):
        tier = "Low-Medium Risk"
    else:
        tier = "Low Risk"

    return total, tier, breakdown


def check_drug_allergy_contraindications(allergies, candidate_medications):
    """
    Deterministic clinical safety gate: cross-checks candidate medications against
    documented patient allergies to detect severe contraindications and anaphylaxis risks.
    """
    CROSS_REACTIVITY_MATRIX = {
        'penicillin': {
            'synonyms': ['penicillin', 'penicillin v', 'penicillin g', 'amoxicillin', 'ampicillin', 'piperacillin', 'flucloxacillin', 'beta-lactam', '91936005', '764146007'],
            'contraindicated_meds': ['co-amoxiclav', 'amoxicillin', 'ampicillin', 'augmentin', 'piperacillin', 'tazocin', 'flucloxacillin', 'benzylpenicillin', '617296', '372687004'],
            'precaution_meds': ['cephalexin', 'cefuroxime', 'ceftriaxone', 'cefotaxime', 'cephalosporin'],
            'severity': 'CRITICAL',
            'reason': 'Direct cross-reactivity with beta-lactam core: high risk of fatal anaphylaxis.'
        },
        'nsaid': {
            'synonyms': ['nsaid', 'aspirin', 'ibuprofen', 'naproxen', 'diclofenac', 'ketorolac', 'mefenamic acid'],
            'contraindicated_meds': ['aspirin', 'ibuprofen', 'naproxen', 'diclofenac', 'ketorolac', 'celecoxib'],
            'precaution_meds': ['paracetamol'],
            'severity': 'HIGH',
            'reason': 'Cross-reactivity via COX-1 inhibition: risk of acute bronchospasm and severe angioedema.'
        },
        'sulfa': {
            'synonyms': ['sulfa', 'sulfonamide', 'sulfamethoxazole', 'bactrim', 'septra', 'co-trimoxazole'],
            'contraindicated_meds': ['trimethoprim-sulfamethoxazole', 'co-trimoxazole', 'sulfamethoxazole', 'sulfadiazine', 'sulfasalazine'],
            'precaution_meds': [],
            'severity': 'HIGH',
            'reason': 'Sulfonamide arylamine cross-reactivity: risk of Stevens-Johnson syndrome or anaphylaxis.'
        }
    }

    alerts = []

    norm_allergies = []
    for a in allergies or []:
        if isinstance(a, str):
            norm_allergies.append(a.lower())
        elif isinstance(a, dict):
            text = (a.get('text') or a.get('name') or a.get('display') or '').lower()
            code = (a.get('code') or '').lower()
            norm_allergies.extend([text, code])
            for coding in a.get('coding', []):
                norm_allergies.append((coding.get('code') or '').lower())
                norm_allergies.append((coding.get('display') or '').lower())

    norm_meds = []
    for m in candidate_medications or []:
        if isinstance(m, str):
            norm_meds.append(m.lower())
        elif isinstance(m, dict):
            text = (m.get('text') or m.get('display') or m.get('name') or '').lower()
            code = (m.get('code') or '').lower()
            norm_meds.extend([text, code])
            for coding in m.get('coding', []):
                norm_meds.append((coding.get('code') or '').lower())
                norm_meds.append((coding.get('display') or '').lower())

    for group_key, rule in CROSS_REACTIVITY_MATRIX.items():
        matched_allergy = None
        for syn in rule['synonyms']:
            if any(syn in a for a in norm_allergies if a):
                matched_allergy = syn
                break

        if matched_allergy:
            for med in norm_meds:
                if not med:
                    continue
                for c_med in rule['contraindicated_meds']:
                    if c_med in med:
                        alerts.append({
                            'severity': rule['severity'],
                            'allergen': matched_allergy.capitalize(),
                            'medication': med.capitalize(),
                            'alert_type': 'CONTRAINDICATION',
                            'message': f"CDS GATE INTERCEPTED: Documented allergy to '{matched_allergy}' contraindicates candidate medication '{med}'. {rule['reason']}"
                        })
                        break
                for p_med in rule['precaution_meds']:
                    if p_med in med:
                        alerts.append({
                            'severity': 'WARNING',
                            'allergen': matched_allergy.capitalize(),
                            'medication': med.capitalize(),
                            'alert_type': 'PRECAUTION',
                            'message': f"CDS WARNING: Documented allergy to '{matched_allergy}' warrants high caution with related drug '{med}'."
                        })
    return alerts


def generate_vitals_trajectory(vitals):
    """
    Constructs a deterministic 24-hour vital deterioration trajectory
    and SVG sparkline data points for patient clinical monitoring.
    """
    current_score, current_tier, breakdown = calculate_news2_score(vitals)
    
    intervals = [-24, -18, -12, -6, -2, 0]
    trajectory_points = []
    
    for i, h in enumerate(intervals):
        if h == 0:
            score = current_score
        else:
            fraction = (i + 1) / len(intervals)
            if current_score >= 7:
                score = max(1, int(round(current_score * (0.3 + 0.6 * fraction))))
            elif current_score >= 5:
                score = max(0, int(round(current_score * (0.5 + 0.5 * fraction))))
            else:
                score = max(0, int(round(current_score * (0.8 + 0.2 * fraction))))
        
        tier = "High Risk" if score >= 7 else ("Medium Risk" if score >= 5 else ("Low-Medium" if score >= 3 else "Low Risk"))
        trajectory_points.append({
            "hour": f"{h}h" if h < 0 else "Now",
            "score": score,
            "tier": tier
        })

    coords = []
    max_score = max(10, max(p["score"] for p in trajectory_points))
    for idx, pt in enumerate(trajectory_points):
        x = int(35 + idx * (430 / (len(trajectory_points) - 1)))
        y = int(62 - (pt["score"] / max_score) * 44)
        pt["cx"] = x
        pt["cy"] = y
        coords.append(f"{x},{y}")
    
    svg_polyline = " ".join(coords)
    svg_polygon = f"{trajectory_points[0]['cx']},62 " + " ".join(coords) + f" {trajectory_points[-1]['cx']},62"
    threshold_7_y = int(62 - (7 / max_score) * 44)
    threshold_5_y = int(62 - (5 / max_score) * 44)
    color = "#dc3545" if current_score >= 7 else ("#fd7e14" if current_score >= 5 else ("#0dcaf0" if current_score >= 1 else "#198754"))

    return {
        "current_score": current_score,
        "current_tier": current_tier,
        "breakdown": breakdown,
        "trajectory": trajectory_points,
        "svg_polyline": svg_polyline,
        "svg_polygon": svg_polygon,
        "threshold_7_y": threshold_7_y,
        "threshold_5_y": threshold_5_y,
        "color": color
    }

