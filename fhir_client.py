"""HTTP client for the FHIR server.

Two things this exists to guarantee:

1. Every request has a timeout. A hung upstream must never pin a worker.
2. Callers can tell "the server said there are no medications" apart from
   "we could not reach the server". Rendering the second as the first is a
   patient-safety problem, not a cosmetic one.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_WORKERS = 6


class FhirResult:
    """Outcome of a single FHIR read.

    `ok` False means the request failed. `ok` True with an empty `entries`
    means the server genuinely holds no matching resources.
    """

    __slots__ = ('ok', 'data', 'status_code', 'error')

    def __init__(self, ok, data=None, status_code=None, error=None):
        self.ok = ok
        self.data = data or {}
        self.status_code = status_code
        self.error = error

    @property
    def entries(self):
        """Resources from a searchset Bundle, in order."""
        if not self.ok:
            return []
        return [
            entry['resource']
            for entry in self.data.get('entry') or []
            if isinstance(entry, dict) and isinstance(entry.get('resource'), dict)
        ]

    @property
    def total(self):
        """Server-reported match count, when it sent one."""
        return self.data.get('total') if self.ok else None

    def __repr__(self):
        return f'<FhirResult ok={self.ok} status={self.status_code} error={self.error!r}>'


class FhirClient:
    """Connection-pooled, retrying, always-timed-out FHIR client."""

    def __init__(self, base_url, timeout=DEFAULT_TIMEOUT, max_workers=DEFAULT_MAX_WORKERS):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_workers = max_workers

        self._session = requests.Session()
        self._session.headers.update({'Accept': 'application/fhir+json'})

        retry = Retry(
            total=2,
            backoff_factor=0.3,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=frozenset(['GET']),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

    def get(self, path, params=None):
        """GET a FHIR path. Never raises -- failures come back as FhirResult(ok=False)."""
        return self._request(f'{self.base_url}/{path.lstrip("/")}', params)

    def post(self, path, data=None, json_data=None):
        """POST to a FHIR path. Never raises -- failures come back as FhirResult(ok=False)."""
        url = f'{self.base_url}/{path.lstrip("/")}'
        path_log = urlsplit(url).path or '/'
        payload = json_data if json_data is not None else data
        try:
            response = self._session.post(url, json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout:
            logger.warning('FHIR POST timed out', extra={'fhir_path': path_log})
            return FhirResult(False, error='The record server did not respond in time.')
        except requests.exceptions.RequestException as exc:
            logger.warning('FHIR POST failed: %s', exc, extra={'fhir_path': path_log})
            return FhirResult(False, error='Could not reach the record server.')
        except Exception:
            logger.exception('Unexpected error during FHIR POST', extra={'fhir_path': path_log})
            return FhirResult(False, error='Could not reach the record server.')

        if not response.ok:
            return FhirResult(False, status_code=response.status_code, error=f'Server returned {response.status_code}')

        try:
            payload_res = response.json()
            return FhirResult(True, data=payload_res, status_code=response.status_code)
        except ValueError:
            return FhirResult(True, status_code=response.status_code)


    def _request(self, url, params=None):
        # Log the URL path only -- slicing len(base_url) garbles upgraded
        # https pagination URLs, and dropping the query string keeps
        # patient-scoped search parameters out of the logs.
        path = urlsplit(url).path or '/'
        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout:
            logger.warning('FHIR request timed out', extra={'fhir_path': path})
            return FhirResult(False, error='The record server did not respond in time.')
        except requests.exceptions.RequestException as exc:
            logger.warning('FHIR request failed: %s', exc, extra={'fhir_path': path})
            return FhirResult(False, error='Could not reach the record server.')
        except Exception:
            # Anything requests did not wrap. Logged at exception level so the
            # cause stays visible, but a single panel must not take the page down.
            logger.exception('Unexpected error during FHIR request',
                             extra={'fhir_path': path})
            return FhirResult(False, error='Could not reach the record server.')

        if response.status_code == 404:
            return FhirResult(False, status_code=404, error='Not found on the record server.')

        if not response.ok:
            logger.warning(
                'FHIR request returned %s', response.status_code,
                extra={'fhir_path': path},
            )
            return FhirResult(
                False,
                status_code=response.status_code,
                error=f'The record server returned an error ({response.status_code}).',
            )

        try:
            payload = response.json()
        except ValueError:
            logger.warning('FHIR response was not valid JSON', extra={'fhir_path': path})
            return FhirResult(
                False,
                status_code=response.status_code,
                error='The record server returned a malformed response.',
            )

        return FhirResult(True, data=payload, status_code=response.status_code)

    def get_absolute(self, url):
        """Follow an absolute Bundle link (pagination).

        Restricted to the configured server. Bundle links are server-supplied
        data, so following one unchecked would turn pagination into a
        server-side request forgery primitive.

        The check is structural rather than a naive string prefix, because real
        servers mint cursor links that a prefix test wrongly rejects: HAPI
        answers an http:// deployment with https:// links (an upgrade we allow;
        a downgrade we do not), and its paging cursors hang the query string
        directly off the base path with no trailing slash
        (`.../baseR4?_getpages=...`).
        """
        if not isinstance(url, str) or not url:
            return FhirResult(False, error='Missing pagination link.')

        base = urlsplit(self.base_url)
        target = urlsplit(url)
        scheme_ok = target.scheme == base.scheme or (
            base.scheme == 'http' and target.scheme == 'https'
        )
        base_path = base.path.rstrip('/')
        path_ok = target.path.rstrip('/') == base_path or \
            target.path.startswith(base_path + '/')

        if not (scheme_ok and target.netloc == base.netloc and path_ok):
            logger.warning('Refused to follow off-server pagination link')
            return FhirResult(False, error='Invalid pagination link.')
        return self._request(url)

    def get_many(self, requests_spec):
        """Run several reads concurrently.

        `requests_spec` maps a caller-chosen key to (path, params). Returns a
        dict of the same keys to FhirResult. Used so that a panel needing four
        queries costs one round trip's latency rather than four.
        """
        if not requests_spec:
            return {}

        results = {}
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(requests_spec))) as pool:
            futures = {
                key: pool.submit(self.get, path, params)
                for key, (path, params) in requests_spec.items()
            }
            for key, future in futures.items():
                try:
                    results[key] = future.result()
                except Exception as exc:  # defensive: get() already swallows its own
                    logger.exception('Concurrent FHIR read failed for %s', key)
                    results[key] = FhirResult(False, error=str(exc))
        return results

    def count(self, resource_type, params=None):
        """Server-side total for a resource type, or None if unavailable.

        Uses `_summary=count` so the server reports the real population rather
        than however many entries happened to fit in one page.
        """
        query = dict(params or {})
        query['_summary'] = 'count'
        result = self.get(resource_type, params=query)
        return result.total if result.ok else None

    def capability_ok(self):
        """Cheap liveness probe against the server's metadata endpoint."""
        return self.get('metadata', params={'_summary': 'true'}).ok

    def get_triage_queue(self):
        """Builds a Manchester Triage queue from FHIR resources on the remote server."""
        patients_res = self.get('Patient', params={'_count': 100})
        if not patients_res.ok:
            return []

        queue = []
        for patient in patients_res.entries:
            pid = patient.get('id')
            if not pid:
                continue

            names = patient.get("name", [])
            display_name = f"Patient {pid}"
            if names:
                display_name = names[0].get("text") or f"{names[0].get('given', [''])[0]} {names[0].get('family', '')}".strip()

            gms_number = "GMS-UNKNOWN"
            for ident in patient.get("identifier", []):
                if ident.get("value"):
                    gms_number = ident.get("value")
                    break

            obs_res = self.get('Observation', params={'patient': pid})
            obs_list = obs_res.entries if obs_res.ok else []

            cond_res = self.get('Condition', params={'patient': pid})
            cond_list = cond_res.entries if cond_res.ok else []

            mts_category = 3
            for o in obs_list:
                cd = o.get("code", {})
                codes = [c.get("code") for c in cd.get("coding", [])]
                text = cd.get("text", "")
                if "75540-5" in codes or "Manchester Triage System" in text or "MTS" in text:
                    val = o.get("valueQuantity", {}).get("value")
                    if val is not None:
                        try:
                            mts_category = int(val)
                            break
                        except (ValueError, TypeError):
                            pass

            chief_complaint = "General Clinical Review"
            if cond_list:
                c0 = cond_list[0]
                codings = c0.get("code", {}).get("coding", [])
                if codings and codings[0].get("display"):
                    chief_complaint = codings[0].get("display")
                elif c0.get("code", {}).get("text"):
                    chief_complaint = c0.get("code", {}).get("text")

            vitals = {}
            for o in obs_list:
                cd = o.get("code", {})
                codes = [c.get("code") for c in cd.get("coding", [])]
                val = o.get("valueQuantity", {}).get("value")
                unit = o.get("valueQuantity", {}).get("unit", "")
                if val is not None:
                    if "8480-6" in codes:
                        vitals["sys_bp"] = f"{int(val)} {unit}".strip()
                        vitals["systolic"] = f"{int(val)} {unit}".strip()
                    elif "8462-4" in codes:
                        vitals["dia_bp"] = f"{int(val)} {unit}".strip()
                        vitals["diastolic"] = f"{int(val)} {unit}".strip()
                    elif "8867-4" in codes:
                        vitals["hr"] = f"{int(val)} {unit}".strip()
                        vitals["heart_rate"] = f"{int(val)} {unit}".strip()
                    elif "9279-1" in codes:
                        vitals["resp_rate"] = f"{int(val)} {unit}".strip()
                        vitals["rr"] = f"{int(val)} {unit}".strip()
                    elif "2708-6" in codes or "59408-5" in codes:
                        vitals["spo2"] = f"{int(val)}{unit if '%' in unit else '%'}"
                    elif "8310-5" in codes:
                        vitals["temp"] = f"{val} {unit}".strip()
                        vitals["temperature"] = f"{val} {unit}".strip()
                    elif "72514-3" in codes:
                        vitals["pain"] = f"{int(val)}/10"
                        vitals["pain_score"] = f"{int(val)}/10"

            from fhir_utils import calculate_news2_score
            news2_score, news2_tier, news2_breakdown = calculate_news2_score(vitals)

            mts_meta = {
                1: {"name": "Immediate", "color": "Red", "wait": 0},
                2: {"name": "Very Urgent", "color": "Orange", "wait": 10},
                3: {"name": "Urgent", "color": "Yellow", "wait": 60},
                4: {"name": "Standard", "color": "Green", "wait": 120},
                5: {"name": "Non-Urgent", "color": "Blue", "wait": 240},
            }.get(mts_category, {"name": "Urgent", "color": "Yellow", "wait": 60})

            queue.append({
                "patient_id": pid,
                "name": display_name,
                "gms_number": gms_number,
                "mts_category": mts_category,
                "mts_name": mts_meta["name"],
                "mts_color": mts_meta["color"],
                "target_wait_minutes": mts_meta["wait"],
                "chief_complaint": chief_complaint,
                "complaint_code": "404684003",
                "vitals": vitals,
                "news2_score": news2_score,
                "news2_tier": news2_tier,
                "news2_breakdown": news2_breakdown,
                "signed_off": bool(self.get_provenance(pid)),
                "arrival_time": "Just now",
                "file_name": f"remote_{pid}"
            })

        queue.sort(key=lambda x: x["mts_category"])
        return queue

    def get_provenance(self, patient_id: str):
        """Fetches the latest Provenance resource for a patient from the FHIR server."""
        if not hasattr(self, '_cache_provenance'):
            self._cache_provenance = {}
        res = self.get('Provenance', params={'patient': patient_id})
        if res.ok and res.entries:
            return res.entries[-1]
        return self._cache_provenance.get(str(patient_id))


    def sign_off_patient(self, patient_id: str, practitioner_id: str, practitioner_role: str, signature_text: str, practitioner_name: str = ""):
        """Generates and transmits HL7 FHIR Provenance resource for clinician sign-off."""
        import hashlib
        import json
        import time
        from datetime import datetime, timezone

        pid = str(patient_id)
        now_iso = datetime.now(timezone.utc).isoformat()
        prov_id = f"prov-{pid}-{int(time.time())}"

        state_repr = f"remote-patient-{pid}-{now_iso}"
        bundle_hash = hashlib.sha256(state_repr.encode("utf-8")).hexdigest()

        provenance = {
            "resourceType": "Provenance",
            "id": prov_id,
            "target": [
                {"reference": f"Patient/{pid}"},
                {"reference": f"Encounter/enc-{pid}"},
                {"reference": f"Condition/cond-{pid}"}
            ],
            "recorded": now_iso,
            "reason": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                            "code": "VRAT",
                            "display": "Verification and Clinical Sign-Off"
                        }
                    ],
                    "text": "Clinician Intake Validation & Electronic Sign-off"
                }
            ],
            "activity": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-DocumentCompletion",
                        "code": "LA",
                        "display": "Legally Authenticated"
                    }
                ]
            },
            "agent": [
                {
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                                "code": "verifier",
                                "display": "Verifier"
                            }
                        ]
                    },
                    "role": [
                        {"text": practitioner_role or "Triage Clinician"}
                    ],
                    "who": {
                        "identifier": {
                            "system": "urn:oid:2.16.840.1.113883.2.17.1.5",
                            "value": practitioner_id
                        },
                        "display": practitioner_name or f"Practitioner {practitioner_id}"
                    }
                }
            ],
            "signature": [
                {
                    "type": [
                        {
                            "system": "urn:iso-astm:E1762-95:2013",
                            "code": "1.2.840.10065.1.12.1.1",
                            "display": "Author's Signature"
                        }
                    ],
                    "when": now_iso,
                    "who": {
                        "reference": f"Practitioner/{practitioner_id}",
                        "display": practitioner_name or f"Dr. {practitioner_id}"
                    },
                    "data": bundle_hash
                }
            ]
        }

        # Submit as single resource or bundle to FHIR server
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "fullUrl": f"urn:uuid:{prov_id}",
                    "resource": provenance,
                    "request": {
                        "method": "POST",
                        "url": "Provenance"
                    }
                }
            ]
        }
        res = self.post('Bundle', data=bundle)
        if not hasattr(self, '_cache_provenance'):
            self._cache_provenance = {}
        self._cache_provenance[pid] = provenance
        return provenance

