"""Tests for Phase 11 (9-Agent Hub, Dedicated Agent Pages & 7 Vertical Cockpits) and Phase 9 Lite."""
from agents_hub import (
    AGENTS_CATALOG,
    build_signed_audit_snapshot,
    run_cve_vulnerability_scan,
    run_gdpr_privacy_scan,
    run_immutable_audit_scan,
    verify_sqlite_immutability_live,
)
from verticals import VERTICALS_CATALOG, get_vertical_list
import db


def test_nine_agents_catalog_complete():
    assert len(AGENTS_CATALOG) == 9
    codes = [a['code'] for a in AGENTS_CATALOG]
    assert 'SlainteShield-BOLA' in codes
    assert 'SlainteShield-FHIR' in codes
    assert 'SlainteShield-CVE' in codes
    assert 'SlainteGov-GDPR' in codes
    assert 'SlainteGov-Audit' in codes
    assert 'SlainteEngine-Ingest' in codes
    assert 'SlainteScribe-Brief' in codes
    assert 'SlainteRx-Guard' in codes
    assert 'SlainteDx-Triage' in codes


def test_seven_verticals_catalog_complete():
    verticals = get_vertical_list()
    assert len(verticals) == 7
    for key in ('ed', 'gp', 'dentist', 'pharmacy', 'ems', 'sports', 'astro'):
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

    # Update per-agent settings for gdpr_privacy
    save_res = admin_client.post('/agents/gdpr_privacy/settings', data={
        'enabled': 'on',
        'assigned_model': 'ollama/k9/Doggo:3b',
        'guardrail': 'Local Sovereign Air-Gap Only',
    })
    assert save_res.status_code == 200
    assert 'SlainteGov-GDPR' in save_res.get_data(as_text=True)
    assert 'ollama/k9/Doggo:3b' in save_res.get_data(as_text=True)


def test_all_nine_dedicated_agent_dashboards_and_execution(admin_client):
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


def test_vertical_cockpit_switcher_sidebar_and_patients(admin_client):
    # ED shows Live Triage in sidebar
    ed_resp = admin_client.post('/verticals/switch', data={'vertical_key': 'ed'}, follow_redirects=True)
    assert ed_resp.status_code == 200
    ed_text = ed_resp.get_data(as_text=True)
    assert 'SlainteED' in ed_text
    assert 'Live Triage' in ed_text
    assert '9 Autonomous Agents Active' not in ed_text
    assert 'Pipeline Status' not in ed_text

    # GP hides Live Triage from sidebar and adapts Patients view
    gp_resp = admin_client.post('/verticals/switch', data={'vertical_key': 'gp'}, follow_redirects=True)
    assert gp_resp.status_code == 200
    gp_text = gp_resp.get_data(as_text=True)
    assert 'SlainteGP' in gp_text
    assert 'Live Triage' not in gp_text
    assert '9 Autonomous Agents Active' not in gp_text
    assert 'Pipeline Status' not in gp_text


def test_embedded_patient_summarise_and_rxguard_agents(admin_client):
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

