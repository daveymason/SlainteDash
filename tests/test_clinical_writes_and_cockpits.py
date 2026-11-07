"""Tests for Step 1.5: Clinical Write Workflows (Bucket A), Interactive
Specialty Cockpits (Bucket B), and Workstation UI Cleanup (Bucket C).
"""
import json
import responses

from conftest import FHIR_BASE, bundle


class TestBucketAClinicalWrites:
    @responses.activate
    def test_rx_guard_blocks_contraindicated_medication_without_override(self, auth_client):
        """Agent 08 (SlainteRx-Guard) must intercept Amoxicillin when Penicillin allergy exists."""
        responses.add(
            responses.GET, f'{FHIR_BASE}/AllergyIntolerance',
            json=bundle({
                'resourceType': 'AllergyIntolerance',
                'id': 'alg-1',
                'criticality': 'high',
                'code': {'coding': [{'system': 'http://snomed.info/sct', 'code': '764146007', 'display': 'Penicillin'}]},
            }),
            status=200,
        )
        responses.add(
            responses.GET, f'{FHIR_BASE}/MedicationRequest',
            json=bundle(),
            status=200,
        )

        resp = auth_client.post('/fhir/Medications/p1/add', data={
            'drug_name': 'Amoxicillin 500mg Oral Capsule',
            'dosage': '500mg TDS',
        })
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'SlainteRx-Guard' in body
        assert 'CONTRAINDICATION' in body
        assert 'Confirm Override' in body
        # Crucially, POST /MedicationRequest was NOT called
        post_calls = [c for c in responses.calls if c.request.method == 'POST']
        assert len(post_calls) == 0

    @responses.activate
    def test_rx_guard_allows_documented_clinical_override(self, auth_client):
        responses.add(
            responses.GET, f'{FHIR_BASE}/AllergyIntolerance',
            json=bundle({
                'resourceType': 'AllergyIntolerance',
                'id': 'alg-1',
                'code': {'coding': [{'display': 'Penicillin'}]},
            }),
            status=200,
        )
        created_meds = []

        def _post_med(req):
            payload = json.loads(req.body)
            created_meds.append(payload)
            return (201, {}, json.dumps(payload))

        responses.add_callback(responses.POST, f'{FHIR_BASE}/MedicationRequest', callback=_post_med)
        responses.add(
            responses.GET, f'{FHIR_BASE}/MedicationRequest',
            json=bundle({
                'resourceType': 'MedicationRequest',
                'id': 'med-new',
                'status': 'active',
                'authoredOn': '2026-11-07T01:00:00Z',
                'medicationCodeableConcept': {'text': 'Amoxicillin 500mg Oral Capsule'},
                'dosageInstruction': [{'text': '500mg TDS'}],
                'note': [{'text': 'Rx-Guard Clinical Override: ICU desensitization'}],
            }),
            status=200,
        )

        resp = auth_client.post('/fhir/Medications/p1/add', data={
            'drug_name': 'Amoxicillin 500mg Oral Capsule',
            'dosage': '500mg TDS',
            'override_reason': 'ICU desensitization protocol',
        })
        assert resp.status_code == 200
        assert len(created_meds) == 1
        assert 'ICU desensitization protocol' in created_meds[0]['note'][0]['text']
        assert 'override logged' in resp.get_data(as_text=True).lower()

    @responses.activate
    def test_stop_medication_status_updates_resource(self, auth_client):
        responses.add(
            responses.GET, f'{FHIR_BASE}/MedicationRequest/med-1',
            json={'resourceType': 'MedicationRequest', 'id': 'med-1', 'status': 'active'},
            status=200,
        )
        updated = []

        def _put_med(req):
            payload = json.loads(req.body)
            updated.append(payload)
            return (200, {}, json.dumps(payload))

        responses.add_callback(responses.PUT, f'{FHIR_BASE}/MedicationRequest/med-1', callback=_put_med)
        responses.add(responses.GET, f'{FHIR_BASE}/MedicationRequest', json=bundle(), status=200)

        resp = auth_client.post('/fhir/Medications/p1/status', data={
            'med_id': 'med-1',
            'new_status': 'stopped',
        })
        assert resp.status_code == 200
        assert len(updated) == 1
        assert updated[0]['status'] == 'stopped'

    @responses.activate
    def test_record_vital_signs_persists_loinc_observations_and_triggers_news2(self, auth_client):
        posted_obs = []

        def _post_obs(req):
            payload = json.loads(req.body)
            posted_obs.append(payload)
            return (201, {}, json.dumps(payload))

        responses.add_callback(responses.POST, f'{FHIR_BASE}/Observation', callback=_post_obs)
        responses.add(responses.GET, f'{FHIR_BASE}/Observation', json=bundle(), status=200)

        resp = auth_client.post('/fhir/VitalSigns/p1/add', data={
            'systolic_bp': '128',
            'diastolic_bp': '82',
            'heart_rate': '78',
            'spo2': '98',
            'respiratory_rate': '16',
            'temperature': '36.9',
        })
        assert resp.status_code == 200
        assert resp.headers.get('HX-Trigger') == 'vitalsUpdated'
        assert len(posted_obs) == 6
        loinc_codes = {o['code']['coding'][0]['code'] for o in posted_obs}
        assert {'8480-6', '8462-4', '8867-4', '59408-5', '9279-1', '8310-5'} == loinc_codes

    @responses.activate
    def test_add_condition_and_allergy_and_clinical_note(self, auth_client):
        created = []

        def _capture_post(req):
            payload = json.loads(req.body)
            created.append(payload)
            return (201, {}, json.dumps(payload))

        for rt in ('Condition', 'AllergyIntolerance', 'DocumentReference'):
            responses.add_callback(responses.POST, f'{FHIR_BASE}/{rt}', callback=_capture_post)

        responses.add(responses.GET, f'{FHIR_BASE}/Condition', json=bundle(), status=200)
        responses.add(responses.GET, f'{FHIR_BASE}/AllergyIntolerance', json=bundle(), status=200)

        r_cond = auth_client.post('/fhir/Conditions/p1/add', data={
            'condition_text': 'Essential hypertension',
            'clinical_status': 'active',
        })
        assert r_cond.status_code == 200

        r_alg = auth_client.post('/fhir/Allergies/p1/add', data={
            'allergen_text': 'Penicillin',
            'criticality': 'high',
            'reaction_text': 'Anaphylaxis',
        })
        assert r_alg.status_code == 200

        # Return the created DocumentReference on GET so we verify base64 decoding too
        def _get_docs(_req):
            docs = [x for x in created if x['resourceType'] == 'DocumentReference']
            return (200, {}, json.dumps(bundle(*docs)))

        responses.add_callback(responses.GET, f'{FHIR_BASE}/DocumentReference', callback=_get_docs)

        r_note = auth_client.post('/fhir/Notes/p1/add', data={
            'note_type': '11506-3',
            'note_text': 'S: Chest pain resolved. O: BP 124/78. P: Discharge home.',
        })
        assert r_note.status_code == 200
        assert 'Chest pain resolved' in r_note.get_data(as_text=True)
        assert {c['resourceType'] for c in created} == {'Condition', 'AllergyIntolerance', 'DocumentReference'}


class TestBucketBSpecialtyCockpits:
    @responses.activate
    def test_dentist_odontogram_renders_and_saves(self, auth_client):
        responses.add(responses.GET, f'{FHIR_BASE}/Patient', json=bundle({
            'resourceType': 'Patient', 'id': 'patient-case-8',
            'name': [{'given': ['Declan'], 'family': 'Fitzgerald'}],
        }), status=200)
        responses.add(responses.GET, f'{FHIR_BASE}/Observation', json=bundle(), status=200)
        responses.add(responses.GET, f'{FHIR_BASE}/AllergyIntolerance', json=bundle({
            'resourceType': 'AllergyIntolerance', 'id': 'alg-pen',
            'code': {'coding': [{'display': 'Penicillin'}]},
        }), status=200)
        responses.add(responses.GET, f'{FHIR_BASE}/MedicationRequest', json=bundle(), status=200)
        responses.add(responses.GET, f'{FHIR_BASE}/Condition', json=bundle(), status=200)

        view = auth_client.get('/fhir/CockpitWorkspace?vertical=dentist')
        assert view.status_code == 200
        html = view.get_data(as_text=True)
        assert 'Odontogram' in html
        assert 'data-tooth="46"' in html
        assert 'AVOID Amoxicillin' in html

        saved_obs = []

        def _put_dental(req):
            payload = json.loads(req.body)
            saved_obs.append(payload)
            return (200, {}, json.dumps(payload))

        responses.add_callback(
            responses.PUT,
            f'{FHIR_BASE}/Observation/obs-dental-chart-patient-case-8',
            callback=_put_dental,
        )
        responses.add(responses.POST, f'{FHIR_BASE}/DocumentReference', json={'resourceType': 'DocumentReference'}, status=201)

        with auth_client.session_transaction() as sess:
            sess['active_vertical'] = 'dentist'

        save_resp = auth_client.post('/fhir/Cockpit/dentist/save', data={
            'patient_id': 'patient-case-8',
            'teeth_json': json.dumps({'46': 'endodontic', '18': 'missing'}),
            'bpe_ur': '2', 'bpe_ua': '1', 'bpe_ul': '2',
            'bpe_lr': '3', 'bpe_la': '1', 'bpe_ll': '2',
            'dental_notes': 'Completed pulpectomy #46',
        })
        assert save_resp.status_code == 200
        assert len(saved_obs) == 1
        parsed = json.loads(saved_obs[0]['valueString'])
        assert parsed['teeth']['46'] == 'endodontic'
        assert parsed['bpe']['lr'] == '3'

    @responses.activate
    def test_pharmacy_dispense_queue_and_action(self, auth_client):
        responses.add(responses.GET, f'{FHIR_BASE}/Patient', json=bundle({
            'resourceType': 'Patient', 'id': 'p1',
            'name': [{'given': ['Mary'], 'family': 'Walsh'}],
            'identifier': [{'value': '99281-A'}],
        }), status=200)
        responses.add(responses.GET, f'{FHIR_BASE}/MedicationRequest', json=bundle({
            'resourceType': 'MedicationRequest', 'id': 'rx-101', 'status': 'active',
            'subject': {'reference': 'Patient/p1'},
            'medicationCodeableConcept': {'text': 'Atorvastatin 80mg Oral Tablet'},
            'dosageInstruction': [{'text': '80mg ON'}],
        }), status=200)
        responses.add(responses.GET, f'{FHIR_BASE}/AllergyIntolerance', json=bundle(), status=200)
        responses.add(responses.GET, f'{FHIR_BASE}/MedicationRequest/rx-101', json={
            'resourceType': 'MedicationRequest', 'id': 'rx-101', 'status': 'active',
            'subject': {'reference': 'Patient/p1'},
        }, status=200)

        updated = []
        responses.add_callback(
            responses.PUT, f'{FHIR_BASE}/MedicationRequest/rx-101',
            callback=lambda req: (updated.append(json.loads(req.body)) or (200, {}, req.body)),
        )

        with auth_client.session_transaction() as sess:
            sess['active_vertical'] = 'pharmacy'

        q_resp = auth_client.get('/fhir/CockpitWorkspace?vertical=pharmacy')
        assert q_resp.status_code == 200
        assert 'Atorvastatin 80mg' in q_resp.get_data(as_text=True)

        d_resp = auth_client.post('/fhir/Cockpit/pharmacy/dispense', data={
            'med_id': 'rx-101', 'patient_id': 'p1', 'new_status': 'completed',
        })
        assert d_resp.status_code == 200
        assert updated and updated[0]['status'] == 'completed'

    @responses.activate
    def test_ems_epcr_transmits_bundle_and_scores_mts(self, auth_client):
        responses.add(responses.GET, f'{FHIR_BASE}/Patient', json=bundle(), status=200)
        bundles_posted = []
        responses.add_callback(
            responses.POST, f'{FHIR_BASE}/Bundle',
            callback=lambda req: (bundles_posted.append(json.loads(req.body)) or (201, {}, req.body)),
        )

        with auth_client.session_transaction() as sess:
            sess['active_vertical'] = 'ems'

        resp = auth_client.post('/fhir/Cockpit/ems/epcr', data={
            'full_name': 'Seamus OToole',
            'dob': '1962-03-11',
            'gender': 'male',
            'complaint': 'Acute central chest pain and severe hypoxia',
            'systolic_bp': '84',
            'diastolic_bp': '52',
            'heart_rate': '135',
            'spo2': '87',
            'respiratory_rate': '30',
            'temperature': '37.9',
        })
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'MTS Cat 1' in body
        assert 'Seamus OToole' in body
        assert len(bundles_posted) == 1

    @responses.activate
    def test_sports_clearance_signs_provenance(self, auth_client):
        responses.add(responses.GET, f'{FHIR_BASE}/Patient', json=bundle({
            'resourceType': 'Patient', 'id': 'patient-case-7',
            'name': [{'given': ['Cian'], 'family': 'OBrien'}],
        }), status=200)
        responses.add(responses.GET, f'{FHIR_BASE}/Provenance', json=bundle(), status=200)
        signed_prov = []
        responses.add_callback(
            responses.PUT, f'{FHIR_BASE}/Provenance/prov-patient-case-7',
            callback=lambda req: (signed_prov.append(json.loads(req.body)) or (200, {}, req.body)),
        )
        responses.add(responses.POST, f'{FHIR_BASE}/DocumentReference', json={'resourceType': 'DocumentReference'}, status=201)

        with auth_client.session_transaction() as sess:
            sess['active_vertical'] = 'sports'

        resp = auth_client.post('/fhir/Cockpit/clearance/patient-case-7')
        assert resp.status_code == 200
        assert len(signed_prov) == 1
        assert signed_prov[0]['resourceType'] == 'Provenance'


class TestBucketCWorkstationCleanup:
    @responses.activate
    def test_patient_details_removes_redundant_buttons_and_giant_avatar(self, auth_client):
        responses.add(
            responses.GET, f'{FHIR_BASE}/Patient/p1',
            json={'resourceType': 'Patient', 'id': 'p1', 'name': [{'given': ['Ada'], 'family': 'Lovelace'}]},
            status=200,
        )
        responses.add(responses.GET, f'{FHIR_BASE}/Observation', json=bundle(), status=200)
        body = auth_client.get('/fhir/Patient/p1').get_data(as_text=True)
        assert 'View Lab Results' not in body
        assert 'View Vital Signs' not in body
        assert 'View Medications' not in body
        assert 'View Allergies' not in body
        assert 'width: 150px' not in body
        assert 'clinical-monogram' in body

    def test_triage_removes_dead_pipeline_status_button(self, auth_client):
        import os
        tpl_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'triage.html')
        with open(tpl_path, 'r', encoding='utf-8') as f:
            triage_tpl = f.read()
        assert '/pipeline/status' not in triage_tpl
        assert '#patientIntakeModal' in triage_tpl
        assert 'agent_multimodal_ingest' in triage_tpl

    def test_htmx_setup_wires_global_display_preferences(self):
        import os
        js_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'htmx-setup.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()
        assert 'applyDisplayPreferences' in js
        assert 'slainte_font_size' in js
        assert 'high-contrast-mode' in js
        assert 'slainte_refresh_rate' in js
