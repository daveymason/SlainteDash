"""Tests for Phase 11 & 11.6 (11-Agent Hub, 8 Clinical Verticals incl. SlaintePsych, Mobile Drawer & CI Isolation)."""
import json
import responses

from agents_hub import (
    AGENTS_CATALOG,
    build_signed_audit_snapshot,
    run_cve_vulnerability_scan,
    run_gdpr_privacy_scan,
    run_immutable_audit_scan,
    verify_sqlite_immutability_live,
)
from conftest import FHIR_BASE, bundle
from verticals import VERTICALS_CATALOG, get_vertical_list
import db


def test_eleven_agents_catalog_complete():
    assert len(AGENTS_CATALOG) == 11
    codes = [a['code'] for a in AGENTS_CATALOG]
    for expected in (
        'SlainteShield-BOLA', 'SlainteShield-FHIR', 'SlainteShield-CVE',
        'SlainteGov-GDPR', 'SlainteGov-Audit', 'SlainteEngine-Ingest',
        'SlainteScribe-Brief', 'SlainteRx-Guard', 'SlainteDx-Triage',
        'SlainteScribe-Voice', 'SlainteRev-Coding',
    ):
        assert expected in codes


def test_eight_verticals_catalog_complete():
    verticals = get_vertical_list()
    assert len(verticals) == 8
    for key in ('ed', 'gp', 'psychiatry', 'dentist', 'pharmacy', 'ems', 'sports', 'astro'):
        assert key in VERTICALS_CATALOG
        assert VERTICALS_CATALOG[key]['brand'].startswith('Slainte')
        assert len(VERTICALS_CATALOG[key]['kpis']) == 3


def test_agents_hub_view_and_per_agent_settings(admin_client, app):
    res = admin_client.get('/fhir/Auditor', headers={'HX-Request': 'true'})
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert 'Autonomous Clinical &amp; Security Agents' in body
    assert 'SlainteShield-CVE' in body
    assert 'SlainteGov-GDPR' in body
    assert 'SlainteGov-Audit' in body
    assert 'SlainteRx-Guard' in body
    assert 'Vertical Active' in body
    assert 'Cockpit Active' not in body

    save_res = admin_client.post('/agents/gdpr_privacy/settings', data={
        'enabled': 'on',
        'assigned_model': 'ollama/k9/Doggo:3b',
        'guardrail': 'Local Sovereign Air-Gap Only',
    })
    assert save_res.status_code == 200
    assert 'SlainteGov-GDPR' in save_res.get_data(as_text=True)
    assert 'ollama/k9/Doggo:3b' in save_res.get_data(as_text=True)


@responses.activate
def test_all_eleven_dedicated_agent_dashboards_and_execution(admin_client):
    responses.add(responses.GET, f'{FHIR_BASE}/Patient', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/Observation', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/Condition', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/MedicationRequest', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/AllergyIntolerance', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/Provenance', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/Patient/P101', json={
        'resourceType': 'Patient', 'id': 'P101', 'name': [{'given': ['Aoife'], 'family': 'Murphy'}],
    }, status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/Patient/patient-case-7', json={
        'resourceType': 'Patient', 'id': 'patient-case-7', 'name': [{'given': ['Cian'], 'family': 'OBrien'}],
    }, status=200)

    for agent in AGENTS_CATALOG:
        aid = agent['id']
        get_res = admin_client.get(f'/fhir/Agent/{aid}', headers={'HX-Request': 'true'})
        assert get_res.status_code == 200
        html = get_res.get_data(as_text=True)
        assert agent['code'] in html
        assert agent['name'].replace('&', '&amp;') in html or agent['name'] in html

        run_res = admin_client.post(f'/fhir/Agent/{aid}/run', data={}, headers={'HX-Request': 'true'})
        assert run_res.status_code == 200
        run_html = run_res.get_data(as_text=True)
        assert agent['code'] in run_html


def test_phase9_lite_cve_gdpr_audit_and_snapshot(admin_client, app):
    with app.app_context():
        cve = run_cve_vulnerability_scan(app.root_path, app.config)
        assert cve['total_packages'] > 0
        assert cve['sri_assets_verified'] >= 4

        gdpr = run_gdpr_privacy_scan(app.config, db)
        assert gdpr['all_passed'] is True

        audit_scan = run_immutable_audit_scan(db)
        assert audit_scan['triggers_ok'] is True

        tamper = verify_sqlite_immutability_live(db)
        assert tamper['blocked'] is True

        snap = build_signed_audit_snapshot(db, 'test-secret')
        assert snap['schema'] == 'slaintetech.audit.snapshot.v1'
        assert len(snap['sha256_integrity_signature']) == 64

    snap_resp = admin_client.get('/agents/audit/snapshot')
    assert snap_resp.status_code == 200
    assert snap_resp.get_json()['schema'] == 'slaintetech.audit.snapshot.v1'

    sec_resp = admin_client.get('/settings/security')
    assert sec_resp.status_code == 200
    sec_html = sec_resp.get_data(as_text=True)
    assert 'Immutable AI Exchange Audit Ledger' in sec_html
    assert 'Download Signed Audit Snapshot' in sec_html


@responses.activate
def test_vertical_switcher_sidebar_responsive_drawer_and_no_cockpit_wording(admin_client, client):
    responses.add(responses.GET, f'{FHIR_BASE}/Patient', json=bundle(), status=200)
    login_html = client.get('/login').get_data(as_text=True)
    assert 'Cockpit' not in login_html
    assert 'SlaintePsych' in login_html

    ed_resp = admin_client.post('/verticals/switch', data={'vertical_key': 'ed'}, follow_redirects=True)
    assert ed_resp.status_code == 200
    ed_text = ed_resp.get_data(as_text=True)
    assert 'SlainteED' in ed_text
    assert 'Live Triage' in ed_text
    assert 'Vertical Overview' in ed_text
    assert 'Cockpit Overview' not in ed_text
    assert 'mobileMenuBtn' in ed_text
    assert 'mobile-bottom-dock' in ed_text

    gp_resp = admin_client.post('/verticals/switch', data={'vertical_key': 'gp'}, follow_redirects=True)
    assert gp_resp.status_code == 200
    gp_text = gp_resp.get_data(as_text=True)
    assert 'SlainteGP' in gp_text
    assert 'Live Triage' not in gp_text


@responses.activate
def test_psychiatry_vertical_mse_and_loinc_scales(admin_client):
    responses.add(responses.GET, f'{FHIR_BASE}/Patient', json=bundle({
        'resourceType': 'Patient', 'id': 'patient-case-4',
        'name': [{'given': ['Niamh'], 'family': 'Kavanagh'}],
    }), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/Observation', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/MedicationRequest', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/Condition', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/AllergyIntolerance', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/DocumentReference', json=bundle(), status=200)

    posted_obs = []
    posted_docs = []
    responses.add_callback(
        responses.POST, f'{FHIR_BASE}/Observation',
        callback=lambda req: (posted_obs.append(json.loads(req.body)) or (201, {}, req.body)),
    )
    responses.add_callback(
        responses.POST, f'{FHIR_BASE}/DocumentReference',
        callback=lambda req: (posted_docs.append(json.loads(req.body)) or (201, {}, req.body)),
    )

    admin_client.post('/verticals/switch', data={'vertical_key': 'psychiatry'})
    ws_resp = admin_client.get('/fhir/VerticalWorkspace?vertical=psychiatry')
    assert ws_resp.status_code == 200
    assert 'Psychiatry Mental State Examination' in ws_resp.get_data(as_text=True)

    post_resp = admin_client.post('/fhir/Vertical/psychiatry/assess', data={
        'patient_id': 'patient-case-4',
        'phq9_score': '16',
        'gad7_score': '12',
        'risk_tier': 'Moderate Risk — Crisis Home Treatment Team',
        'mse_notes': 'Calm, cooperative, euthymic speech, low mood, denies suicidal ideation, crisis safety plan agreed.',
    })
    assert post_resp.status_code == 200
    assert 'PHQ-9=16' in post_resp.get_data(as_text=True)
    assert len(posted_obs) == 2
    assert len(posted_docs) == 1


@responses.activate
def test_embedded_patient_summarise_and_rxguard_agents(admin_client):
    responses.add(responses.GET, f'{FHIR_BASE}/Patient/P101', json={
        'resourceType': 'Patient',
        'id': 'P101',
        'name': [{'given': ['Aoife'], 'family': 'Murphy'}],
        'gender': 'female',
        'birthDate': '1978-06-14',
    }, status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/Observation', json=bundle(), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/Condition', json=bundle({
        'resourceType': 'Condition', 'id': 'c1', 'code': {'text': 'Community-acquired pneumonia'},
    }), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/AllergyIntolerance', json=bundle({
        'resourceType': 'AllergyIntolerance',
        'id': 'alg-pen',
        'criticality': 'high',
        'code': {'text': 'Penicillin'},
    }), status=200)
    responses.add(responses.GET, f'{FHIR_BASE}/MedicationRequest', json=bundle({
        'resourceType': 'MedicationRequest',
        'id': 'med-amox',
        'status': 'active',
        'medicationCodeableConcept': {'text': 'Amoxicillin 500mg Oral Capsule'},
    }), status=200)

    sum_resp = admin_client.post('/ai/summarise/P101')
    assert sum_resp.status_code == 200
    sum_html = sum_resp.get_data(as_text=True)
    assert 'Agent 07 (SlainteScribe-Brief)' in sum_html
    assert 'Patient/P101' in sum_html

    rx_resp = admin_client.post('/ai/crosscheck/patient-case-7')
    assert rx_resp.status_code == 200
    rx_html = rx_resp.get_data(as_text=True)
    assert 'Agent 08 (SlainteRx-Guard)' in rx_html
    assert 'BLOCK / INTERCEPT' in rx_html
    assert 'Penicillin' in rx_html
