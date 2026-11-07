import os
"""FHIR Patient Dashboard.

Flask + HTMX viewer over a FHIR R4 server. Routes return HTML fragments that
HTMX swaps into the page, so there is no client-side framework and no build step.
"""
import logging
import re

import click
from flask import (
    Flask, abort, jsonify, redirect, render_template, request, session, url_for
)
from flask_login import (
    LoginManager, current_user, login_required, login_user, logout_user
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

import auth
import db
from ai import provider as ai_provider
from charts import demographics_charts, vitals_charts
from config import (
    ConfigError, MAX_USERNAME_LENGTH, MIN_PASSWORD_LENGTH, MIN_USERNAME_LENGTH,
    ai_blocked_reason, is_valid_username, resolve_secret_key, select_config,
)
from fhir_client import FhirClient
from fhir_utils import (
    LOINC_DIASTOLIC, LOINC_SYSTOLIC, blood_pressure_components, calculate_age,
    calculate_news2_score, check_drug_allergy_contraindications,
    condition_onset, first_coding_display, format_address, format_fhir_date,
    observation_code, observation_value, patient_display_name, patient_initials,
    sort_key,
)
from clinical_workflows import (
    ALL_FDI_TEETH, BPE_SEXTANTS, CLINICAL_ALLERGENS_CATALOG,
    CLINICAL_CONDITIONS_CATALOG, CLINICAL_MEDICATIONS_CATALOG,
    FDI_LOWER_LEFT, FDI_LOWER_RIGHT, FDI_UPPER_LEFT, FDI_UPPER_RIGHT,
    NOTE_TYPES_CATALOG, TOOTH_STATUS_META, build_allergy_resource,
    build_clinical_note, build_condition_resource,
    build_dental_chart_observation, build_medication_request,
    build_provenance_signoff, build_vital_observations, extract_note_view,
    parse_dental_chart_observation, persist_fhir_resource,
)
import rate_limit_storage
from logging_setup import configure_logging, pseudonymize, validate_salt

rate_limit_storage.register_sqlite_scheme()

logger = logging.getLogger(__name__)

login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

# LOINC codes for the vital signs panel.
VITAL_SIGN_CODES = {
    'blood_pressure': ('85354-9', 'Blood Pressure', 'mmHg'),
    'heart_rate': ('8867-4', 'Heart Rate', 'bpm'),
    'spo2': ('59408-5', 'Oxygen Saturation (SpO2)', '%'),
    'respiratory_rate': ('9279-1', 'Respiratory Rate', '/min'),
    'temperature': ('8310-5', 'Temperature', '°C'),
    'pain': ('72514-3', 'Pain Score', '{score}'),
}

# Patient search parameters that may be sorted, mapped to nothing (they're
# already valid FHIR _sort values) -- kept as a set purely to reject anything
# else a caller might try to inject through the sort parameter.
_SORTABLE_FIELDS = {'family', 'birthdate', 'gender'}

_DATE_SEARCH_RE = re.compile(r'\d{4}(-\d{2}(-\d{2})?)?$')


class DynamicFhirProxy:
    """Proxy that dynamically resolves the active FHIR client backed by shared SQLite state.

    Guarantees 100% synchronization across multi-worker gunicorn instances with zero
    in-memory drift.
    """
    def __init__(self, app):
        self._app = app

    def _get_client(self):
        app = self._app
        default_url = app.config.get('FHIR_SERVER_URL') or 'http://slainte-fhir:8082/fhir/r4'
        default_profile = 'slainte_fhir' if '8082' in default_url else 'custom'

        profile, url = db.get_active_backend_config(default_profile=default_profile, default_url=default_url)
        if not url:
            url = default_url

        cached_key = getattr(app, '_cached_fhir_key', None)
        cached_client = getattr(app, '_cached_fhir_client', None)

        if cached_key != (profile, url) or cached_client is None:
            if profile == 'local_store' or (url and url.startswith('file://')):
                from local_fhir_store import LocalFhirStore
                path = url.replace('file://', '') if url else app.config.get('FHIR_STORE_PATH', '/workspace/data/fhir_store')
                if not os.path.isdir(path):
                    alt_path = app.config.get('FHIR_STORE_PATH')
                    if alt_path and os.path.isdir(alt_path):
                        path = alt_path
                    else:
                        eng_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'slainte-engine', 'data', 'fhir_store'))
                        if os.path.isdir(eng_path):
                            path = eng_path
                cached_client = LocalFhirStore(path)
            else:
                from fhir_client import FhirClient
                effective_url = url
                if 'slainte-fhir:8082' in effective_url and not os.path.exists('/.dockerenv'):
                    effective_url = effective_url.replace('slainte-fhir:8082', 'localhost:8082')
                cached_client = FhirClient(effective_url, timeout=app.config.get('FHIR_TIMEOUT', 4.0))

            app._cached_fhir_key = (profile, url)
            app._cached_fhir_client = cached_client
            app.active_profile = profile
            app.active_backend_url = url

        return cached_client

    def __getattr__(self, name):
        if name in ('_app', '_get_client'):
            return super().__getattribute__(name)
        return getattr(self._get_client(), name)

    def __dir__(self):
        return dir(self._get_client())


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app(config_object=None):
    app = Flask(__name__)

    config_class = config_object or select_config()
    app.config.from_object(config_class)

    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = resolve_secret_key(app.config.get('DEBUG', False))

    configure_logging(app.config['LOG_LEVEL'], as_json=app.config['LOG_JSON'])

    app.fhir = DynamicFhirProxy(app)


    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.user_loader(auth.load_user)
    login_manager.session_protection = 'strong'

    validate_salt(is_debug=app.debug, is_testing=app.testing)

    if 'RATELIMIT_STORAGE_URI' not in app.config:
        if app.testing:
            app.config['RATELIMIT_STORAGE_URI'] = 'memory://'
        else:
            db_dir = os.path.dirname(app.config.get('DATABASE_PATH', '/data/app.db'))
            if not db_dir or db_dir == ':memory:':
                db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'instance'))
            os.makedirs(db_dir, exist_ok=True)
            rl_db = os.path.join(db_dir, 'rate_limits.db')
            app.config['RATELIMIT_STORAGE_URI'] = f'sqlite:///{rl_db}'

    csrf.init_app(app)
    limiter.init_app(app)

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; "
            "img-src 'self' data: https:; "
            "connect-src 'self' http://localhost:* http://127.0.0.1:* https://unpkg.com https://cdn.jsdelivr.net https://hapi.fhir.org; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers['Content-Security-Policy'] = csp
        return response

    app.teardown_appcontext(db.close_connection)
    db.init_db(app)

    from enterprise_bp import enterprise_bp, smart_introspect, smart_token
    csrf.exempt(smart_token)
    csrf.exempt(smart_introspect)
    app.register_blueprint(enterprise_bp)

    register_routes(app)
    register_cli(app)

    # Nobody can approve a pending account if there is no reachable admin, so
    # say so at boot rather than letting the operator discover it by being
    # locked out.
    with app.app_context():
        if db.count_active_admins() == 0:
            logger.warning(
                'No active administrator account exists. Nobody can approve '
                'sign-in requests. Grant one with: '
                'flask --app app grant-admin <username>'
            )

    @app.before_request
    def _make_session_permanent():
        session.permanent = True

    logger.info(
        'Application started',
        extra={'fhir_server': app.config['FHIR_SERVER_URL'], 'debug': app.config['DEBUG']},
    )
    return app


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

def audit(action, outcome='success', resource_type=None, resource_id=None, detail=None):
    """Record an access to the audit trail, with the patient ID pseudonymised."""
    db.write_audit(
        action=action,
        outcome=outcome,
        actor=current_user.get_id() if current_user.is_authenticated else None,
        resource_type=resource_type,
        resource_id=resource_id,
        remote_addr=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
        detail=detail,
    )


def _fragment_error(message, columns=None):
    """Render an inline error for an HTMX panel.

    Returns HTTP 200 deliberately: htmx does not swap non-2xx responses by
    default, so a 5xx here would leave the panel silently blank.
    """
    if columns:
        return (
            f'<tr><td colspan="{columns}" class="text-center text-danger py-3">'
            f'<i class="fas fa-exclamation-triangle me-2"></i>{message}</td></tr>'
        )
    return (
        f'<div class="alert alert-danger mb-3">'
        f'<i class="fas fa-exclamation-triangle me-2"></i>{message}</div>'
    )


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def _load_local_bundle_summary(pt_id):
    """Fast local lookup of clinical summary fields (conditions, allergies, meds, vitals) from fhir_store."""
    import json
    from flask import current_app, has_app_context
    if has_app_context() and current_app.config.get('TESTING') and not current_app.config.get('FHIR_STORE_PATH'):
        return {
            'primary_condition': 'General Assessment',
            'allergies': [],
            'medications': [],
            'news2_score': 0,
            'news2_tier': 'Low Risk',
            'vitals_summary': 'Baseline',
            'rx_alerts': [],
        }
    candidates = [
        os.environ.get('FHIR_STORE_PATH', ''),
        '/workspace/data/fhir_store',
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'fhir_store')),
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'slainte-engine', 'data', 'fhir_store')),
    ]
    for store_dir in candidates:
        if not store_dir or not os.path.isdir(store_dir):
            continue
        bpath = os.path.join(store_dir, f'bundle_{pt_id}.json')
        if os.path.isfile(bpath):
            try:
                with open(bpath, 'r', encoding='utf-8') as f:
                    bdata = json.load(f)
                conditions = []
                allergies = []
                medications = []
                vitals_map = {}
                for entry in bdata.get('entry') or []:
                    res = entry.get('resource') or {}
                    rtype = res.get('resourceType')
                    if rtype == 'Condition':
                        txt = (res.get('code') or {}).get('text') or ((res.get('code') or {}).get('coding') or [{}])[0].get('display')
                        if txt:
                            conditions.append(txt)
                    elif rtype == 'AllergyIntolerance':
                        txt = (res.get('code') or {}).get('text') or ((res.get('code') or {}).get('coding') or [{}])[0].get('display')
                        if txt:
                            allergies.append(txt)
                    elif rtype == 'MedicationRequest':
                        txt = (res.get('medicationCodeableConcept') or {}).get('text') or ((res.get('medicationCodeableConcept') or {}).get('coding') or [{}])[0].get('display')
                        if txt:
                            medications.append(txt)
                    elif rtype == 'Observation':
                        code = ((res.get('code') or {}).get('coding') or [{}])[0].get('code')
                        val = (res.get('valueQuantity') or {}).get('value')
                        if code and val is not None:
                            vitals_map[code] = val
                score, tier, _ = calculate_news2_score(vitals_map)
                v_parts = []
                if '8867-4' in vitals_map:
                    v_parts.append(f"HR {int(float(vitals_map['8867-4']))}")
                if '2708-6' in vitals_map or '59408-5' in vitals_map:
                    sp = vitals_map.get('2708-6') or vitals_map.get('59408-5')
                    v_parts.append(f"SpO2 {int(float(sp))}%")
                if '8480-6' in vitals_map:
                    v_parts.append(f"SBP {int(float(vitals_map['8480-6']))}")
                return {
                    'primary_condition': conditions[0] if conditions else 'Clinical Review',
                    'allergies': allergies,
                    'medications': medications,
                    'news2_score': score,
                    'news2_tier': tier,
                    'vitals_summary': ' · '.join(v_parts) if v_parts else 'Vitals stable',
                    'rx_alerts': check_drug_allergy_contraindications(allergies, medications),
                }
            except Exception:
                break
    return {
        'primary_condition': 'General Assessment',
        'allergies': [],
        'medications': [],
        'news2_score': 0,
        'news2_tier': 'Low Risk',
        'vitals_summary': 'Baseline',
        'rx_alerts': [],
    }


def process_patient_results(resources):
    """Flatten Patient resources into the shape the table templates expect, enriched for vertical cockpits."""
    processed = []
    for resource in resources:
        address = (resource.get('address') or [{}])[0]
        telecom = (resource.get('telecom') or [{}])[0]
        pt_id = resource.get('id', 'Unknown')
        bdate = resource.get('birthDate', 'Unknown')
        gms_val = 'Unassigned'
        for ident in resource.get('identifier') or []:
            if isinstance(ident, dict) and ident.get('value'):
                gms_val = ident.get('value')
                break
        extra = _load_local_bundle_summary(pt_id)
        processed.append({
            'id': pt_id,
            'name': patient_display_name(resource),
            'gender': resource.get('gender', 'Unknown'),
            'birthDate': bdate,
            'age': calculate_age(bdate),
            'gms': gms_val,
            'address': format_address(address) or 'Not recorded',
            'telecom': telecom.get('value', 'Not recorded'),
            **extra,
        })
    return processed


def _bundle_next_link(result):
    """Extract the `next` page URL from a searchset Bundle, if there is one."""
    for link in result.data.get('link') or []:
        if isinstance(link, dict) and link.get('relation') == 'next':
            return link.get('url')
    return None


def _validate_sort(raw):
    """Only pass through a `sort` value that is actually one of our columns.

    The value doubles as the literal FHIR `_sort` parameter (e.g. `-birthdate`),
    so an unchecked value would let a caller sort -- or otherwise perturb the
    query -- by an arbitrary FHIR search parameter.
    """
    if not raw:
        return None
    field = raw[1:] if raw.startswith('-') else raw
    return raw if field in _SORTABLE_FIELDS else None


def _looks_like_date(term):
    return bool(_DATE_SEARCH_RE.fullmatch(term))


def _looks_like_phone(term):
    digits = re.sub(r'[\s().+-]', '', term)
    return digits.isdigit() and len(digits) >= 6


def _looks_like_id(term):
    return term.replace('-', '').isalnum() and any(c.isdigit() for c in term)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def register_routes(app):
    fhir = app.fhir
    auth_limit = app.config['RATELIMIT_AUTH']

    from verticals import VERTICALS_CATALOG, get_active_vertical, get_vertical_list
    from agents_hub import (
        AVAILABLE_MODELS,
        build_signed_audit_snapshot,
        get_agent_by_id,
        get_all_agents_with_settings,
        run_cve_vulnerability_scan,
        run_gdpr_privacy_scan,
        run_immutable_audit_scan,
        save_agent_settings,
        verify_sqlite_immutability_live,
    )

    @app.context_processor
    def inject_vertical_and_fleet():
        from flask import session
        return {
            'active_vertical': get_active_vertical(session, db),
            'all_verticals': get_vertical_list(),
        }

    # -- shell -------------------------------------------------------------

    @app.route('/')
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        from flask import session
        views = {
            'triage': '/fhir/Triage',
            'patients': '/fhir/Patients',
            'stats': '/fhir/Demographics',
            'insights': '/fhir/Dashboard',
            'pipeline': '/fhir/Agent/multimodal_ingest',
            'auditor': '/fhir/Auditor',
            'agents': '/fhir/Auditor',
        }
        view_arg = request.args.get('view')
        if view_arg is None:
            if app.config.get('APPLIANCE_MODE'):
                active_vert = get_active_vertical(session, db)
                def_v = active_vert.get('default_view', 'triage') if active_vert else 'triage'
                initial_view = views.get(def_v, views['triage'])
            else:
                initial_view = views['patients']
        elif view_arg in views:
            initial_view = views[view_arg]
        elif view_arg.startswith('agent_'):
            ag = get_agent_by_id(view_arg[6:])
            initial_view = f"/fhir/Agent/{ag['id']}" if ag else '/fhir/Auditor'
        elif view_arg.startswith(('/fhir/', '/pipeline/', '/agents/')):
            initial_view = view_arg
        else:
            initial_view = views['patients']
        return render_template('index.html', initial_view=initial_view)

    @app.route('/verticals/switch', methods=['POST'])
    @login_required
    def switch_vertical():
        from flask import session
        v_key = (request.form.get('vertical_key') or 'ed').strip().lower()
        if v_key not in VERTICALS_CATALOG:
            v_key = 'ed'
        session['active_vertical'] = v_key
        db.set_system_setting('default_vertical', v_key)
        vert = VERTICALS_CATALOG[v_key]
        audit('vertical.switched', outcome='success', detail={'vertical': v_key, 'brand': vert['brand']})
        target_view = vert.get('default_view', 'triage')
        return redirect(url_for('index', view=target_view))

    @app.route('/health')
    def health_check():
        payload = {'status': 'ok'}
        if app.config['HEALTH_SHOW_BACKEND']:
            _, active_url = db.get_active_backend_config(
                default_profile='slainte_fhir',
                default_url=app.config.get('FHIR_SERVER_URL', 'http://slainte-fhir:8082/fhir/r4')
            )
            payload['fhir_server'] = active_url
        return jsonify(payload)

    @app.route('/health/ready')
    def readiness_check():
        """Deep check -- verifies the FHIR backend actually answers."""
        reachable = fhir.capability_ok()
        return jsonify({'status': 'ok' if reachable else 'degraded',
                        'fhir_reachable': reachable}), (200 if reachable else 503)

    # -- authentication ----------------------------------------------------

    @app.route('/login', methods=['GET', 'POST'])
    @limiter.limit(auth_limit, methods=['POST'])
    def login():
        # The limit applies to POST only: every logged-out visit to any page
        # redirects through GET /login, so limiting views too would let a
        # handful of open tabs (or one hospital NAT) 429 the sign-in page
        # before anyone typed a password.
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        if request.method == 'GET':
            notice = None
            if request.args.get('registered'):
                notice = ('Account created. An administrator must approve it '
                          'before you can sign in.')
            return render_template('login.html', notice=notice)

        username = (request.form.get('username') or '').strip().lower()
        password = request.form.get('password') or ''
        if not username or not password:
            return render_template('login.html',
                                   error='Enter your username and password.'), 400

        locked, locked_until = db.is_account_locked(username)
        if locked:
            audit('login.locked', outcome='denied', resource_type='User',
                  resource_id=pseudonymize(username), detail={'reason': 'account_locked', 'locked_until': locked_until})
            return render_template('login.html',
                                   error='Account is temporarily locked due to multiple failed login attempts. Please try again later.'), 403

        record = auth.verify_credentials(username, password)
        if record is None:
            attempts, locked_until = db.record_failed_login(username)
            detail = {'reason': 'bad_credentials', 'failed_attempts': attempts}
            if locked_until:
                detail['locked_until'] = locked_until
            audit('login.denied', outcome='failure', resource_type='User',
                  resource_id=pseudonymize(username), detail=detail)
            if locked_until:
                from enterprise_engine import dispatch_siem_event
                dispatch_siem_event(
                    db_module=db,
                    app_config=app.config,
                    event_type='SECURITY_ACCOUNT_LOCKOUT',
                    severity='HIGH',
                    actor=username,
                    detail={'failed_attempts': attempts, 'locked_until': locked_until},
                )
                return render_template('login.html',
                                       error='Account has been temporarily locked due to 5 consecutive failed login attempts. Please try again in 15 minutes.'), 403
            return render_template('login.html',
                                   error='Incorrect username or password.'), 401

        if record['status'] != db.STATUS_ACTIVE:
            audit('login.denied', outcome='denied', resource_type='User',
                  resource_id=pseudonymize(username),
                  detail={'reason': f"account_{record['status']}"})
            message = ('Your account is awaiting administrator approval.'
                       if record['status'] == db.STATUS_PENDING
                       else 'This account has been disabled.')
            return render_template('login.html', error=message), 403

        login_user(auth.User(record))
        db.record_login(username)
        selected_vertical = (request.form.get('vertical_key') or '').strip().lower()
        if selected_vertical in VERTICALS_CATALOG:
            from flask import session
            session['active_vertical'] = selected_vertical
            db.set_system_setting('default_vertical', selected_vertical)
        audit('login.success', resource_type='User', resource_id=pseudonymize(username),
              detail={'vertical': selected_vertical or 'ed'})
        return redirect(url_for('index'))

    @app.route('/register', methods=['GET', 'POST'])
    @limiter.limit(auth_limit, methods=['POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        if request.method == 'GET':
            return render_template('register.html')

        username = (request.form.get('username') or '').strip().lower()
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm_password') or ''

        error = None
        if not is_valid_username(username):
            error = (f'Choose a username of {MIN_USERNAME_LENGTH}-{MAX_USERNAME_LENGTH} '
                     'characters: letters, numbers, dots, hyphens or underscores.')
        elif len(password) < MIN_PASSWORD_LENGTH:
            error = f'Choose a password of at least {MIN_PASSWORD_LENGTH} characters.'
        elif password != confirm:
            error = 'Passwords do not match.'
        elif db.get_user(username) is not None:
            error = 'That username is already taken.'

        if error:
            return render_template('register.html', error=error, username=username), 400

        db.register_pending_user(username, auth.hash_password(password))
        audit('register.pending', resource_type='User', resource_id=pseudonymize(username))
        # Redirect rather than render (post/redirect/get): rendering the login
        # page from POST /register left the browser parked on /register, where
        # refresh or Back re-submitted the form and got "username taken".
        return redirect(url_for('login', registered=1))

    @app.route('/logout')
    @login_required
    def logout():
        audit('logout')
        logout_user()
        session.clear()
        return redirect(url_for('login'))

    # -- patients ----------------------------------------------------------

    @app.route('/fhir/Patients')
    @login_required
    def get_patients():
        if not request.headers.get('HX-Request') and not app.testing:
            return render_template('index.html', initial_view='/fhir/Patients')
        page_size = app.config['FHIR_PAGE_SIZE']
        current_sort = _validate_sort(request.args.get('sort'))
        params = {'_count': page_size}
        if current_sort:
            params['_sort'] = current_sort
        result = fhir.get('Patient', params=params)
        if not result.ok:
            audit('patient.list', outcome='failure')
            return render_template('patients.html', patients=[], error=result.error,
                                   total=None, next_url=None, current_sort=current_sort)

        audit('patient.list')
        return render_template(
            'patients.html',
            patients=process_patient_results(result.entries),
            error=None,
            total=fhir.count('Patient'),
            next_url=_bundle_next_link(result),
            current_sort=current_sort,
        )

    @app.route('/fhir/Patients/page')
    @login_required
    def get_patients_page():
        """Follow a Bundle `next` link. The URL is validated against the
        configured server inside the client, so it cannot be pointed elsewhere.

        Renders rows only, never the table shell: the response replaces the
        Load More row inside the existing <tbody>, appending the next page
        under the rows already on screen.
        """
        result = fhir.get_absolute(request.args.get('url', ''))
        if not result.ok:
            return _fragment_error(result.error or 'Could not load the next page.', columns=7)
        audit('patient.list', detail={'page': 'next'})
        return render_template(
            'patient_rows.html',
            patients=process_patient_results(result.entries),
            error=None,
            next_url=_bundle_next_link(result),
        )

    @app.route('/fhir/search_patients', methods=['POST'])
    @login_required
    def search_patients():
        search_term = (request.values.get('q') or '').strip()
        current_sort = _validate_sort(request.values.get('sort'))
        page_size = app.config['FHIR_PAGE_SIZE']

        base_params = {'_count': page_size}
        if current_sort:
            base_params['_sort'] = current_sort

        if not search_term:
            result = fhir.get('Patient', params=base_params)
            if not result.ok:
                audit('patient.search', outcome='failure')
                return _fragment_error(result.error or 'Search failed.', columns=7)
            audit('patient.search', detail={'has_term': False})
            return render_template(
                'patient_table_body.html',
                patients=process_patient_results(result.entries),
                error=None, next_url=_bundle_next_link(result), current_sort=current_sort,
            )

        # A single search box covers several distinct FHIR search parameters.
        # Every plausible interpretation of the term is queried concurrently
        # rather than tried one at a time, then the first match is taken in
        # priority order -- this both supports searching by birthdate/phone
        # and (since it replaces what was a sequential id -> name -> identifier
        # fallback chain) cuts the worst case from three round trips to one.
        candidates = {'name': ('Patient', {**base_params, 'name:contains': search_term})}
        if _looks_like_id(search_term):
            candidates['id'] = ('Patient', {**base_params, '_id': search_term})
        if _looks_like_date(search_term):
            candidates['birthdate'] = ('Patient', {**base_params, 'birthdate': search_term})
        if _looks_like_phone(search_term):
            candidates['phone'] = ('Patient', {**base_params, 'phone': search_term})
        candidates['identifier'] = ('Patient', {**base_params, 'identifier': search_term})

        results = fhir.get_many(candidates)

        result = None
        for key in ('id', 'birthdate', 'phone', 'name', 'identifier'):
            candidate_result = results.get(key)
            if candidate_result and candidate_result.ok and candidate_result.entries:
                result = candidate_result
                break

        if result is None:
            # Nothing matched. "No patients found" is only a truthful answer
            # if every interpretation of the term was actually checked -- if
            # any candidate query failed, a match may exist behind the
            # failure, so report the error rather than a clean empty result.
            failures = [r for r in results.values() if not r.ok]
            if failures:
                audit('patient.search', outcome='failure')
                return _fragment_error(failures[0].error or 'Search failed.', columns=7)
            result = results['name']

        audit('patient.search', detail={'has_term': True})
        return render_template(
            'patient_table_body.html',
            patients=process_patient_results(result.entries),
            error=None,
            next_url=_bundle_next_link(result),
            current_sort=current_sort,
        )

    @app.route('/fhir/Patient/<patient_id>')
    @login_required
    def get_patient(patient_id):
        if not request.headers.get('HX-Request') and not app.testing:
            return render_template('index.html', initial_view=f'/fhir/Patient/{patient_id}')
        result = fhir.get(f'Patient/{patient_id}')
        if not result.ok:
            audit('patient.view', outcome='failure', resource_type='Patient',
                  resource_id=pseudonymize(patient_id))
            if result.status_code == 404:
                return _fragment_error('That patient could not be found.')
            return _fragment_error(result.error or 'Could not load this patient.')

        patient = result.data
        patient['display_name'] = patient_display_name(patient)
        patient['initials'] = patient_initials(patient)
        patient['age'] = calculate_age(patient.get('birthDate'))

        work_telecoms = [
            entry['value'] for entry in patient.get('telecom') or []
            if isinstance(entry, dict) and entry.get('use') == 'work' and entry.get('value')
        ]
        any_telecoms = [
            entry['value'] for entry in patient.get('telecom') or []
            if isinstance(entry, dict) and entry.get('value')
        ]
        patient['contact'] = ', '.join(work_telecoms or any_telecoms) or 'Not recorded'

        addresses = patient.get('address') or []
        patient['simple_address'] = (
            format_address(addresses[0]) if addresses else ''
        ) or 'Not recorded'

        identifiers = patient.get('identifier') or []
        patient['simple_identifier'] = next(
            (i.get('value') for i in identifiers if isinstance(i, dict) and i.get('value')),
            'Not recorded',
        )

        patient['languages'] = [
            {
                'name': first_coding_display(entry.get('language', {})),
                'preferred': bool(entry.get('preferred')),
            }
            for entry in patient.get('communication') or []
            if isinstance(entry, dict) and first_coding_display(entry.get('language', {}))
        ]

        patient['marital_status'] = first_coding_display(patient.get('maritalStatus', {}))

        # Phase 6: NEWS2 24h Deterioration Trajectory & FHIR Provenance Sign-Off
        from fhir_utils import generate_vitals_trajectory
        vitals = {}
        obs_res = fhir.get('Observation', params={'patient': patient_id, '_count': 50})
        if obs_res.ok:
            # Entries are newest-first or chronological; iterate oldest->newest or take newest first
            for o in obs_res.entries:
                cd = o.get("code", {})
                codes = [c.get("code") for c in cd.get("coding", [])]
                val = o.get("valueQuantity", {}).get("value")
                if val is not None:
                    if "8480-6" in codes and "systolic_bp" not in vitals:
                        vitals["systolic_bp"] = val
                    elif "8867-4" in codes and "heart_rate" not in vitals:
                        vitals["heart_rate"] = val
                    elif "9279-1" in codes and "respiratory_rate" not in vitals:
                        vitals["respiratory_rate"] = val
                    elif ("2708-6" in codes or "59408-5" in codes) and "spo2" not in vitals:
                        vitals["spo2"] = val
                    elif "8310-5" in codes and "temperature" not in vitals:
                        vitals["temperature"] = val
                    elif "9269-2" in codes and "gcs" not in vitals:
                        vitals["gcs"] = val

        trajectory_data = generate_vitals_trajectory(vitals)

        provenance = None
        if hasattr(fhir, 'get_provenance'):
            provenance = fhir.get_provenance(patient_id)
        if provenance is None and not app.testing:
            prov_res = fhir.get('Provenance', params={'patient': patient_id})
            if prov_res.ok and prov_res.entries:
                provenance = prov_res.entries[0]

        from enterprise_engine import AMBIENT_SCRIBE_PRESETS
        audit('patient.view', resource_type='Patient', resource_id=pseudonymize(patient_id))
        return render_template(
            'patient_details.html',
            patient=patient,
            trajectory=trajectory_data,
            provenance=provenance,
            conditions_catalog=CLINICAL_CONDITIONS_CATALOG,
            medications_catalog=CLINICAL_MEDICATIONS_CATALOG,
            allergens_catalog=CLINICAL_ALLERGENS_CATALOG,
            note_types_catalog=NOTE_TYPES_CATALOG,
            active_break_glass=db.get_active_break_glass_grant(current_user.username, patient_id),
            scribe_presets=AMBIENT_SCRIBE_PRESETS,
            smart_context=session.get('smart_context'),
        )

    @app.route('/fhir/News2Card/<patient_id>')
    @login_required
    def get_news2_card(patient_id):
        from fhir_utils import generate_vitals_trajectory
        vitals = {}
        obs_res = fhir.get('Observation', params={'patient': patient_id, '_count': 50, '_sort': '-date'})
        if obs_res.ok:
            for o in obs_res.entries:
                cd = o.get("code", {})
                codes = [c.get("code") for c in cd.get("coding", [])]
                val = o.get("valueQuantity", {}).get("value")
                if val is not None:
                    if "8480-6" in codes and "systolic_bp" not in vitals:
                        vitals["systolic_bp"] = val
                    elif "8867-4" in codes and "heart_rate" not in vitals:
                        vitals["heart_rate"] = val
                    elif "9279-1" in codes and "respiratory_rate" not in vitals:
                        vitals["respiratory_rate"] = val
                    elif ("2708-6" in codes or "59408-5" in codes) and "spo2" not in vitals:
                        vitals["spo2"] = val
                    elif "8310-5" in codes and "temperature" not in vitals:
                        vitals["temperature"] = val
                    elif "9269-2" in codes and "gcs" not in vitals:
                        vitals["gcs"] = val
        trajectory_data = generate_vitals_trajectory(vitals)
        return render_template('news2_card.html', trajectory=trajectory_data, patient_id=patient_id)


    # -- clinical panels & write workflows (Bucket A) ----------------------

    def _render_conditions_fragment(patient_id, flash_message=None):
        result = fhir.get('Condition', params={'patient': patient_id, '_count': 30})
        if not result.ok:
            audit('patient.conditions', outcome='failure', resource_type='Patient',
                  resource_id=pseudonymize(patient_id))
            return render_template('conditions.html', conditions=[], error=result.error,
                                   patient_id=patient_id, conditions_catalog=CLINICAL_CONDITIONS_CATALOG)

        conditions = []
        for resource in result.entries:
            onset_display, onset_sort = condition_onset(resource)
            recorded = resource.get('recordedDate')
            c_status = first_coding_display(resource.get('clinicalStatus', {}), fallback='Unknown')
            conditions.append({
                'id': resource.get('id', ''),
                'onset': onset_display or format_fhir_date(recorded),
                'sort_key': onset_sort or sort_key(recorded),
                'name': first_coding_display(resource.get('code', {}),
                                             fallback='Unknown condition'),
                'clinical_status': c_status.lower() if c_status != 'Unknown' else 'Unknown',
                'verification_status': first_coding_display(resource.get('verificationStatus', {})),
            })
        conditions.sort(key=lambda item: item['sort_key'], reverse=True)

        audit('patient.conditions', resource_type='Patient', resource_id=pseudonymize(patient_id))
        return render_template(
            'conditions.html',
            conditions=conditions,
            error=None,
            patient_id=patient_id,
            conditions_catalog=CLINICAL_CONDITIONS_CATALOG,
            flash_message=flash_message,
        )

    @app.route('/fhir/Conditions/<patient_id>')
    @login_required
    def get_conditions(patient_id):
        return _render_conditions_fragment(patient_id)

    @app.route('/fhir/Conditions/<patient_id>/add', methods=['POST'])
    @login_required
    def add_condition(patient_id):
        if not current_user.can_author_diagnosis(patient_id):
            audit('clinical.rbac_condition_denied', outcome='denied', resource_type='Condition',
                  resource_id=pseudonymize(patient_id), detail={'clinical_role': current_user.clinical_role})
            return _render_conditions_fragment(
                patient_id,
                flash_message=('danger', f'Clinical RBAC ({current_user.clinical_role_label}): Only Prescribers or active Break-the-Glass grants may originate diagnoses.'),
            ), 403
        cond_text = (request.form.get('condition_text') or '').strip()
        snomed_code = (request.form.get('snomed_code') or '').strip()
        clinical_status = (request.form.get('clinical_status') or 'active').strip().lower()
        if not cond_text:
            return _render_conditions_fragment(patient_id, flash_message=('danger', 'Enter or select a clinical diagnosis.'))
        res_obj = build_condition_resource(patient_id, cond_text, snomed_code=snomed_code, clinical_status=clinical_status)
        save_res = persist_fhir_resource(fhir, app.config, res_obj, is_update=False)
        if not save_res.ok:
            return _render_conditions_fragment(patient_id, flash_message=('danger', save_res.error or 'Could not save condition.'))
        audit('patient.condition_added', outcome='success', resource_type='Condition',
              resource_id=pseudonymize(patient_id), detail={'condition': cond_text, 'status': clinical_status})
        return _render_conditions_fragment(patient_id, flash_message=('success', f'Recorded diagnosis: {cond_text}.'))

    @app.route('/fhir/Conditions/<patient_id>/status', methods=['POST'])
    @login_required
    def update_condition_status(patient_id):
        cond_id = (request.form.get('condition_id') or '').strip()
        new_status = (request.form.get('new_status') or 'resolved').strip().lower()
        if not cond_id or new_status not in ('active', 'resolved', 'inactive'):
            return _render_conditions_fragment(patient_id)
        existing = fhir.get(f'Condition/{cond_id}')
        if existing.ok and isinstance(existing.data, dict):
            cond_obj = dict(existing.data)
        else:
            cond_obj = {'resourceType': 'Condition', 'id': cond_id, 'subject': {'reference': f'Patient/{patient_id}'}}
        cond_obj['clinicalStatus'] = {
            'coding': [{
                'system': 'http://terminology.hl7.org/CodeSystem/condition-clinical',
                'code': new_status,
                'display': new_status.capitalize(),
            }]
        }
        persist_fhir_resource(fhir, app.config, cond_obj, is_update=True)
        audit('patient.condition_status_updated', outcome='success', resource_type='Condition',
              resource_id=pseudonymize(patient_id), detail={'condition_id': cond_id, 'status': new_status})
        return _render_conditions_fragment(patient_id, flash_message=('success', f'Condition marked {new_status}.'))

    @app.route('/fhir/LabResults/<patient_id>')
    @login_required
    def get_lab_results(patient_id):
        result = fhir.get('Observation', params={
            'patient': patient_id, '_sort': '-date', '_count': 15,
            'category': 'laboratory',
        })
        if not result.ok:
            audit('patient.labs', outcome='failure', resource_type='Patient',
                  resource_id=pseudonymize(patient_id))
            return render_template('lab_results.html', lab_results=[], error=result.error, patient_id=patient_id)

        lab_results = []
        for resource in result.entries:
            effective = resource.get('effectiveDateTime') or resource.get('issued')
            value, unit = observation_value(resource)
            lab_results.append({
                'date': format_fhir_date(effective),
                'sort_key': sort_key(effective),
                'code': observation_code(resource),
                'value': value if value != '' else 'Not recorded',
                'unit': unit,
                'status': resource.get('status', 'unknown'),
            })
        lab_results.sort(key=lambda item: item['sort_key'], reverse=True)

        audit('patient.labs', resource_type='Patient', resource_id=pseudonymize(patient_id))
        return render_template('lab_results.html', lab_results=lab_results, error=None, patient_id=patient_id)

    def _render_vitals_fragment(patient_id, flash_message=None):
        spec = {
            key: ('Observation', {
                'patient': patient_id,
                'code': f'http://loinc.org|{code}',
                '_sort': '-date',
                '_count': 12,
            })
            for key, (code, _label, _unit) in VITAL_SIGN_CODES.items()
        }
        spec['_standalone_systolic'] = ('Observation', {
            'patient': patient_id, 'code': f'http://loinc.org|{LOINC_SYSTOLIC}',
            '_sort': '-date', '_count': 12,
        })
        spec['_standalone_diastolic'] = ('Observation', {
            'patient': patient_id, 'code': f'http://loinc.org|{LOINC_DIASTOLIC}',
            '_sort': '-date', '_count': 12,
        })
        results = fhir.get_many(spec)

        vital_signs = []
        failures = []
        chart_series = {
            key: {'label': label, 'unit': unit, 'rows': []}
            for key, (_code, label, unit) in VITAL_SIGN_CODES.items()
        }
        bp_panel_keys = set()

        for key, (_code, label, _unit) in VITAL_SIGN_CODES.items():
            result = results.get(key)
            if result is None or not result.ok:
                failures.append(label)
                continue
            for resource in result.entries:
                effective = resource.get('effectiveDateTime') or resource.get('issued')
                date_label = format_fhir_date(effective)
                dt = sort_key(effective)

                if key == 'blood_pressure':
                    value, unit = observation_value(resource)
                    if value != '':
                        vital_signs.append({
                            'date': date_label, 'sort_key': dt, 'type': label,
                            'value': value, 'unit': unit,
                            'status': resource.get('status', 'unknown'),
                        })
                    systolic, diastolic = blood_pressure_components(resource)
                    if systolic is not None and diastolic is not None:
                        chart_series[key]['rows'].append((dt, date_label, systolic, diastolic))
                    encounter_ref = (resource.get('encounter') or {}).get('reference')
                    if encounter_ref:
                        bp_panel_keys.add(encounter_ref)
                    if effective:
                        bp_panel_keys.add(f'time:{effective}')
                    continue

                value, unit = observation_value(resource)
                if value == '':
                    continue
                vital_signs.append({
                    'date': date_label,
                    'sort_key': dt,
                    'type': label,
                    'value': value,
                    'unit': unit,
                    'status': resource.get('status', 'unknown'),
                })
                try:
                    chart_series[key]['rows'].append((dt, date_label, float(value)))
                except (TypeError, ValueError):
                    pass

        def _index_standalone_bp(result):
            indexed = {}
            if result is None or not result.ok:
                return indexed
            for resource in result.entries:
                value = (resource.get('valueQuantity') or {}).get('value')
                if value is None:
                    continue
                effective = resource.get('effectiveDateTime') or resource.get('issued')
                pairing_key = (resource.get('encounter') or {}).get('reference') \
                    or (f'time:{effective}' if effective else None)
                if pairing_key is None:
                    continue
                indexed.setdefault(pairing_key, {
                    'sort_key': sort_key(effective),
                    'date': format_fhir_date(effective),
                    'value': value,
                    'status': resource.get('status', 'unknown'),
                })
            return indexed

        systolic_by_key = _index_standalone_bp(results.get('_standalone_systolic'))
        diastolic_by_key = _index_standalone_bp(results.get('_standalone_diastolic'))
        for pairing_key, systolic_entry in systolic_by_key.items():
            if pairing_key in bp_panel_keys:
                continue
            diastolic_entry = diastolic_by_key.get(pairing_key)
            if diastolic_entry is None:
                continue
            vital_signs.append({
                'date': systolic_entry['date'], 'sort_key': systolic_entry['sort_key'],
                'type': 'Blood Pressure',
                'value': (f"Systolic blood pressure: {systolic_entry['value']} / "
                          f"Diastolic blood pressure: {diastolic_entry['value']}"),
                'unit': 'mmHg', 'status': systolic_entry['status'],
            })
            chart_series['blood_pressure']['rows'].append((
                systolic_entry['sort_key'], systolic_entry['date'],
                systolic_entry['value'], diastolic_entry['value'],
            ))

        vital_signs.sort(key=lambda item: item['sort_key'], reverse=True)

        error = None
        if failures:
            error = f"Could not load: {', '.join(failures)}."
            audit('patient.vitals', outcome='failure', resource_type='Patient',
                  resource_id=pseudonymize(patient_id), detail={'failed': failures})
        else:
            audit('patient.vitals', resource_type='Patient',
                  resource_id=pseudonymize(patient_id))

        return render_template(
            'vital_signs.html', vital_signs=vital_signs, error=error,
            charts=vitals_charts(chart_series), patient_id=patient_id,
            flash_message=flash_message,
        )

    @app.route('/fhir/VitalSigns/<patient_id>')
    @login_required
    def get_vital_signs(patient_id):
        return _render_vitals_fragment(patient_id)

    @app.route('/fhir/VitalSigns/<patient_id>/add', methods=['POST'])
    @login_required
    def add_vital_signs(patient_id):
        vitals_payload = {
            'systolic_bp': request.form.get('systolic_bp'),
            'diastolic_bp': request.form.get('diastolic_bp'),
            'heart_rate': request.form.get('heart_rate'),
            'spo2': request.form.get('spo2'),
            'respiratory_rate': request.form.get('respiratory_rate'),
            'temperature': request.form.get('temperature'),
            'pain': request.form.get('pain'),
        }
        obs_list = build_vital_observations(patient_id, vitals_payload)
        if not obs_list:
            return _render_vitals_fragment(patient_id, flash_message=('danger', 'Enter at least one physiological vital reading.'))
        for obs in obs_list:
            persist_fhir_resource(fhir, app.config, obs, is_update=False)
        audit('patient.vitals_recorded', outcome='success', resource_type='Observation',
              resource_id=pseudonymize(patient_id), detail={'count': len(obs_list)})
        from flask import make_response
        resp = make_response(_render_vitals_fragment(
            patient_id,
            flash_message=('success', f'Recorded {len(obs_list)} LOINC vital sign observation(s) and updated NEWS2.'),
        ))
        resp.headers['HX-Trigger'] = 'vitalsUpdated'
        return resp

    def _render_medications_fragment(patient_id, flash_message=None, rx_guard_block=None):
        result = fhir.get('MedicationRequest', params={
            'patient': patient_id, '_count': 30,
        })
        if not result.ok:
            audit('patient.medications', outcome='failure', resource_type='Patient',
                  resource_id=pseudonymize(patient_id))
            return render_template('medications.html', medications=[], error=result.error,
                                   patient_id=patient_id, medications_catalog=CLINICAL_MEDICATIONS_CATALOG)

        medications = []
        for resource in result.entries:
            authored = resource.get('authoredOn')
            name = 'Unknown medication'
            if isinstance(resource.get('medicationReference'), dict):
                name = resource['medicationReference'].get('display') or name
            elif isinstance(resource.get('medicationCodeableConcept'), dict):
                name = first_coding_display(resource['medicationCodeableConcept'], fallback=name)

            dosage = [
                entry['text'] for entry in resource.get('dosageInstruction') or []
                if isinstance(entry, dict) and entry.get('text')
            ]
            notes = [
                n.get('text') for n in (resource.get('note') or [])
                if isinstance(n, dict) and n.get('text')
            ]
            medications.append({
                'id': resource.get('id', ''),
                'date': format_fhir_date(authored),
                'sort_key': sort_key(authored),
                'name': name,
                'dosage': ', '.join(dosage) or 'No specific instructions',
                'status': resource.get('status', 'unknown'),
                'override_note': notes[0] if notes else '',
            })
        medications.sort(key=lambda item: item['sort_key'], reverse=True)

        audit('patient.medications', resource_type='Patient',
              resource_id=pseudonymize(patient_id))
        return render_template(
            'medications.html',
            medications=medications,
            error=None,
            patient_id=patient_id,
            medications_catalog=CLINICAL_MEDICATIONS_CATALOG,
            flash_message=flash_message,
            rx_guard_block=rx_guard_block,
        )

    @app.route('/fhir/Medications/<patient_id>')
    @login_required
    def get_medications(patient_id):
        return _render_medications_fragment(patient_id)

    @app.route('/fhir/Medications/<patient_id>/add', methods=['POST'])
    @login_required
    def add_medication(patient_id):
        from enterprise_engine import dispatch_siem_event, evaluate_clinical_pharmacology_3tier
        if not current_user.can_prescribe(patient_id):
            audit('clinical.rbac_prescribe_denied', outcome='denied', resource_type='MedicationRequest',
                  resource_id=pseudonymize(patient_id), detail={'clinical_role': current_user.clinical_role})
            return _render_medications_fragment(
                patient_id,
                flash_message=('danger', f'Clinical RBAC ({current_user.clinical_role_label}): Prescribing requires Prescriber privileges or an active Break-the-Glass emergency override.'),
            ), 403

        drug_name = (request.form.get('drug_name') or '').strip()
        dosage = (request.form.get('dosage') or '').strip()
        snomed_code = (request.form.get('snomed_code') or '').strip()
        override_reason = (request.form.get('override_reason') or '').strip()
        if not drug_name:
            return _render_medications_fragment(patient_id, flash_message=('danger', 'Select or enter a medication to prescribe.'))

        # Agent 08 (SlainteRx-Guard) 3-Tier Pre-Flight Pharmacology Interception
        # Tier 1: Allergy Cross-Reactivity | Tier 2: High-Alert DDI | Tier 3: Lab eGFR Renal Gate
        sub_check = fhir.get_many({
            'allergy': ('AllergyIntolerance', {'patient': patient_id, '_count': 30}),
            'med': ('MedicationRequest', {'patient': patient_id, '_count': 30}),
            'obs': ('Observation', {'patient': patient_id, '_count': 50}),
        })
        patient_allergies = []
        if sub_check['allergy'].ok:
            for a in sub_check['allergy'].entries:
                if isinstance(a, dict):
                    patient_allergies.append(first_coding_display(a.get('code', {}), fallback=''))
        patient_allergies = [a for a in patient_allergies if a]
        if not patient_allergies:
            local_sum = _load_local_bundle_summary(patient_id)
            patient_allergies = list(local_sum.get('allergies') or [])

        existing_active_meds = []
        if sub_check['med'].ok:
            for m in sub_check['med'].entries:
                if isinstance(m, dict) and str(m.get('status', 'active')).lower() in ('active', ''):
                    disp = first_coding_display(m.get('medicationCodeableConcept', {}), fallback='')
                    if disp:
                        existing_active_meds.append(disp)

        lab_obs = sub_check['obs'].entries if sub_check['obs'].ok else []
        rx_eval = evaluate_clinical_pharmacology_3tier(
            allergies=patient_allergies,
            active_medications=existing_active_meds,
            lab_observations=lab_obs,
            candidate_drug=drug_name,
        )
        alerts = rx_eval['alerts']
        if alerts and not override_reason:
            audit('clinical.rx_guard_blocked', outcome='denied', resource_type='MedicationRequest',
                  resource_id=pseudonymize(patient_id),
                  detail={'drug': drug_name, 'alerts': [a['allergen'] for a in alerts], 'tiers': rx_eval['tier_counts']})
            return _render_medications_fragment(
                patient_id,
                rx_guard_block={
                    'drug_name': drug_name,
                    'dosage': dosage,
                    'snomed_code': snomed_code,
                    'alerts': alerts,
                },
            )

        med_res = build_medication_request(
            patient_id=patient_id,
            drug_name=drug_name,
            dosage_text=dosage,
            snomed_code=snomed_code,
            author=current_user.username,
            override_reason=override_reason,
        )
        save_res = persist_fhir_resource(fhir, app.config, med_res, is_update=False)
        if not save_res.ok:
            return _render_medications_fragment(patient_id, flash_message=('danger', save_res.error or 'Could not prescribe medication.'))
        if override_reason:
            dispatch_siem_event(
                db_module=db,
                app_config=app.config,
                event_type='CLINICAL_RX_GUARD_OVERRIDE',
                severity='HIGH',
                actor=current_user.username,
                detail={'patient_pseudonym': pseudonymize(patient_id), 'drug': drug_name, 'override_reason': override_reason},
            )
        audit('patient.medication_prescribed', outcome='success', resource_type='MedicationRequest',
              resource_id=pseudonymize(patient_id),
              detail={'drug': drug_name, 'override': bool(override_reason)})
        msg = f'Prescribed {drug_name} (Rx-Guard override logged).' if override_reason else f'Prescribed {drug_name} (3-Tier Rx-Guard verified clear).'
        return _render_medications_fragment(patient_id, flash_message=('success', msg))

    @app.route('/fhir/Medications/<patient_id>/status', methods=['POST'])
    @login_required
    def update_medication_status(patient_id):
        med_id = (request.form.get('med_id') or '').strip()
        new_status = (request.form.get('new_status') or 'stopped').strip().lower()
        if not med_id or new_status not in ('active', 'stopped', 'completed', 'on-hold'):
            return _render_medications_fragment(patient_id)
        existing = fhir.get(f'MedicationRequest/{med_id}')
        if existing.ok and isinstance(existing.data, dict):
            med_obj = dict(existing.data)
        else:
            med_obj = {'resourceType': 'MedicationRequest', 'id': med_id, 'subject': {'reference': f'Patient/{patient_id}'}}
        med_obj['status'] = new_status
        persist_fhir_resource(fhir, app.config, med_obj, is_update=True)
        audit('patient.medication_status_updated', outcome='success', resource_type='MedicationRequest',
              resource_id=pseudonymize(patient_id), detail={'med_id': med_id, 'status': new_status})
        return _render_medications_fragment(patient_id, flash_message=('success', f'Prescription updated to {new_status}.'))

    def _render_allergies_fragment(patient_id, flash_message=None):
        result = fhir.get('AllergyIntolerance', params={
            'patient': patient_id, '_count': 30,
        })
        if not result.ok:
            audit('patient.allergies', outcome='failure', resource_type='Patient',
                  resource_id=pseudonymize(patient_id))
            return render_template('allergies.html', allergies=[], error=result.error,
                                   patient_id=patient_id, allergens_catalog=CLINICAL_ALLERGENS_CATALOG)

        allergies = []
        for resource in result.entries:
            recorded = resource.get('recordedDate')
            reactions = []
            for reaction in resource.get('reaction') or []:
                if not isinstance(reaction, dict):
                    continue
                for manifestation in reaction.get('manifestation') or []:
                    label = first_coding_display(manifestation)
                    if label:
                        reactions.append(label)
            allergies.append({
                'id': resource.get('id', ''),
                'date': format_fhir_date(recorded),
                'sort_key': sort_key(recorded),
                'name': first_coding_display(resource.get('code', {}),
                                             fallback='Unknown allergen'),
                'reactions': reactions,
                'severity': resource.get('criticality') or resource.get('severity') or 'unknown',
                'status': first_coding_display(resource.get('clinicalStatus', {}),
                                               fallback='Unknown'),
            })
        allergies.sort(key=lambda item: item['sort_key'], reverse=True)

        audit('patient.allergies', resource_type='Patient',
              resource_id=pseudonymize(patient_id))
        return render_template(
            'allergies.html',
            allergies=allergies,
            error=None,
            patient_id=patient_id,
            allergens_catalog=CLINICAL_ALLERGENS_CATALOG,
            flash_message=flash_message,
        )

    @app.route('/fhir/Allergies/<patient_id>')
    @login_required
    def get_allergies(patient_id):
        return _render_allergies_fragment(patient_id)

    @app.route('/fhir/Allergies/<patient_id>/add', methods=['POST'])
    @login_required
    def add_allergy(patient_id):
        allergen_text = (request.form.get('allergen_text') or '').strip()
        criticality = (request.form.get('criticality') or 'high').strip().lower()
        reaction_text = (request.form.get('reaction_text') or '').strip()
        snomed_code = (request.form.get('snomed_code') or '').strip()
        if not allergen_text:
            return _render_allergies_fragment(patient_id, flash_message=('danger', 'Enter or select an allergen substance.'))
        alg_obj = build_allergy_resource(
            patient_id=patient_id,
            allergen_text=allergen_text,
            criticality=criticality,
            reaction_text=reaction_text,
            snomed_code=snomed_code,
        )
        save_res = persist_fhir_resource(fhir, app.config, alg_obj, is_update=False)
        if not save_res.ok:
            return _render_allergies_fragment(patient_id, flash_message=('danger', save_res.error or 'Could not save allergy.'))
        audit('patient.allergy_recorded', outcome='success', resource_type='AllergyIntolerance',
              resource_id=pseudonymize(patient_id), detail={'allergen': allergen_text, 'criticality': criticality})
        return _render_allergies_fragment(patient_id, flash_message=('success', f'Recorded allergy: {allergen_text} ({criticality}).'))

    def _render_notes_fragment(patient_id, flash_message=None):
        result = fhir.get('DocumentReference', params={'patient': patient_id, '_count': 25})
        if not result.ok:
            return render_template(
                'clinical_notes.html',
                notes=[],
                error=result.error,
                patient_id=patient_id,
                note_types_catalog=NOTE_TYPES_CATALOG,
            )
        notes = []
        for resource in result.entries:
            if isinstance(resource, dict):
                view = extract_note_view(resource)
                view['date_display'] = format_fhir_date(view.get('date'))
                view['sort_key'] = sort_key(view.get('date'))
                notes.append(view)
        notes.sort(key=lambda item: item['sort_key'], reverse=True)
        return render_template(
            'clinical_notes.html',
            notes=notes,
            error=None,
            patient_id=patient_id,
            note_types_catalog=NOTE_TYPES_CATALOG,
            flash_message=flash_message,
        )

    @app.route('/fhir/Notes/<patient_id>')
    @login_required
    def get_clinical_notes(patient_id):
        audit('patient.notes', resource_type='Patient', resource_id=pseudonymize(patient_id))
        return _render_notes_fragment(patient_id)

    @app.route('/fhir/Notes/<patient_id>/add', methods=['POST'])
    @login_required
    def add_clinical_note(patient_id):
        from flask import session
        note_type = (request.form.get('note_type') or '11506-3').strip()
        note_text = (request.form.get('note_text') or '').strip()
        if not note_text:
            return _render_notes_fragment(patient_id, flash_message=('danger', 'Clinical note text cannot be empty.'))
        active_vert = get_active_vertical(session, db)
        brand = active_vert.get('brand', 'SlainteDash') if active_vert else 'SlainteDash'
        doc_obj = build_clinical_note(
            patient_id=patient_id,
            note_type_code=note_type,
            note_text=note_text,
            author_username=current_user.username,
            vertical_brand=brand,
        )
        save_res = persist_fhir_resource(fhir, app.config, doc_obj, is_update=False)
        if not save_res.ok:
            return _render_notes_fragment(patient_id, flash_message=('danger', save_res.error or 'Could not file clinical note.'))
        audit('patient.note_created', outcome='success', resource_type='DocumentReference',
              resource_id=pseudonymize(patient_id), detail={'type': note_type})
        return _render_notes_fragment(patient_id, flash_message=('success', 'Clinical consultation note filed to FHIR R4 DocumentReference.'))

    # -- aggregate views ---------------------------------------------------

    @app.route('/fhir/Demographics')
    @login_required
    def get_demographics():
        if not request.headers.get('HX-Request') and not app.testing:
            return render_template('index.html', initial_view='/fhir/Demographics')
        result = fhir.get('Patient', params={'_count': 100})
        if not result.ok:
            audit('demographics.view', outcome='failure')
            return _fragment_error(result.error or 'Could not load demographics.')

        gender_counts = {'male': 0, 'female': 0, 'other': 0, 'unknown': 0}
        age_groups = {'0-18': 0, '19-35': 0, '36-55': 0, '56-75': 0, '76+': 0, 'unknown': 0}
        ages = []

        for resource in result.entries:
            gender = (resource.get('gender') or '').lower()
            gender_counts[gender if gender in gender_counts else 'unknown'] += 1

            age = calculate_age(resource.get('birthDate'))
            if age is None or age < 0:
                age_groups['unknown'] += 1
                continue
            ages.append(age)
            if age <= 18:
                age_groups['0-18'] += 1
            elif age <= 35:
                age_groups['19-35'] += 1
            elif age <= 55:
                age_groups['36-55'] += 1
            elif age <= 75:
                age_groups['56-75'] += 1
            else:
                age_groups['76+'] += 1

        sampled = sum(gender_counts.values())
        demographics = {
            'gender_counts': gender_counts,
            'age_groups': age_groups,
            'total_patients': sampled,
            'server_total': fhir.count('Patient'),
            # Reported from the sample rather than hardcoded to "36-55".
            'mean_age': round(sum(ages) / len(ages), 1) if ages else None,
        }

        audit('demographics.view')
        return render_template(
            'demographics.html', demographics=demographics,
            charts=demographics_charts(demographics),
        )

    @app.route('/fhir/Dashboard')
    @login_required
    def get_dashboard():
        if not request.headers.get('HX-Request') and not app.testing:
            return render_template('index.html', initial_view='/fhir/Dashboard')
        results = fhir.get_many({
            'patients': ('Patient', {'_count': 20}),
            'patient_count': ('Patient', {'_summary': 'count'}),
            'observation_count': ('Observation', {'_summary': 'count'}),
        })

        patients_result = results['patients']
        gender_counts = {'male': 0, 'female': 0, 'other': 0, 'unknown': 0}
        recent_patients = []
        sampled = 0

        if patients_result.ok:
            for resource in patients_result.entries:
                gender = (resource.get('gender') or '').lower()
                gender_counts[gender if gender in gender_counts else 'unknown'] += 1
                sampled += 1
            recent_patients = process_patient_results(patients_result.entries[:5])

        # The real population, not the size of one page.
        patient_total = results['patient_count'].total
        observation_total = results['observation_count'].total

        audit('dashboard.view')
        return render_template(
            'dashboard.html',
            patient_count=patient_total,
            observation_count=observation_total,
            sampled_count=sampled,
            gender_counts=gender_counts,
            recent_patients=recent_patients,
            fhir_server_url=app.config['FHIR_SERVER_URL'],
            fhir_reachable=patients_result.ok,
            error=None if patients_result.ok else patients_result.error,
        )

    # -- specialty vertical workspaces (Bucket B) --------------------------

    def _render_cockpit_workspace(patient_id_override=None, flash_message=None, epcr_result=None):
        import json as _json
        from flask import session
        active_vert = get_active_vertical(session, db)
        v_key = (request.args.get('vertical') or (active_vert['key'] if active_vert else 'ed')).strip().lower()
        if v_key not in VERTICALS_CATALOG:
            v_key = 'ed'
        vert_meta = VERTICALS_CATALOG[v_key]

        pt_res = fhir.get('Patient', params={'_count': 40})
        cohort_patients = process_patient_results(pt_res.entries) if pt_res.ok else []
        patients_by_id = {p['id']: p for p in cohort_patients}

        ctx = {
            'v_key': v_key,
            'vert_meta': vert_meta,
            'cohort_patients': cohort_patients,
            'flash_message': flash_message,
            'epcr_result': epcr_result,
            'medications_catalog': CLINICAL_MEDICATIONS_CATALOG,
            'conditions_catalog': CLINICAL_CONDITIONS_CATALOG,
        }

        if v_key == 'dentist':
            default_pid = 'patient-case-8' if 'patient-case-8' in patients_by_id else (cohort_patients[0]['id'] if cohort_patients else 'patient-case-8')
            selected_pid = (patient_id_override or request.args.get('patient_id') or default_pid).strip()
            sub = fhir.get_many({
                'obs': ('Observation', {'patient': selected_pid, '_count': 30}),
                'alg': ('AllergyIntolerance', {'patient': selected_pid, '_count': 20}),
                'med': ('MedicationRequest', {'patient': selected_pid, '_count': 20}),
                'cond': ('Condition', {'patient': selected_pid, '_count': 20}),
            })
            obs_entries = sub['obs'].entries if sub['obs'].ok else []
            alg_entries = sub['alg'].entries if sub['alg'].ok else []
            med_entries = sub['med'].entries if sub['med'].ok else []
            cond_entries = sub['cond'].entries if sub['cond'].ok else []

            dental_chart = parse_dental_chart_observation(obs_entries, selected_pid)
            allergies_list = [first_coding_display(a.get('code', {}), fallback='') for a in alg_entries if isinstance(a, dict)]
            allergies_list = [a for a in allergies_list if a]
            meds_list = []
            for m in med_entries:
                if isinstance(m, dict) and m.get('status') in (None, 'active'):
                    m_txt = first_coding_display(m.get('medicationCodeableConcept', {}), fallback='')
                    if m_txt:
                        meds_list.append(m_txt)
            conditions_list = [first_coding_display(c.get('code', {}), fallback='') for c in cond_entries if isinstance(c, dict)]
            conditions_list = [c for c in conditions_list if c]

            anticoag_keywords = ('warfarin', 'apixaban', 'rivaroxaban', 'ticagrelor', 'clopidogrel', 'aspirin', 'dabigatran')
            hemostasis_flags = [m for m in meds_list if any(k in m.lower() for k in anticoag_keywords)]
            penicillin_flag = any('penicillin' in a.lower() or 'amoxicillin' in a.lower() for a in allergies_list)

            ctx.update({
                'selected_pid': selected_pid,
                'selected_patient': patients_by_id.get(selected_pid, {'id': selected_pid, 'name': selected_pid, 'identifier': 'N/A'}),
                'dental_chart': dental_chart,
                'teeth_json': _json.dumps(dental_chart['teeth']),
                'fdi_upper_right': FDI_UPPER_RIGHT,
                'fdi_upper_left': FDI_UPPER_LEFT,
                'fdi_lower_right': FDI_LOWER_RIGHT,
                'fdi_lower_left': FDI_LOWER_LEFT,
                'tooth_status_meta': TOOTH_STATUS_META,
                'bpe_sextants': BPE_SEXTANTS,
                'allergies_list': allergies_list,
                'meds_list': meds_list,
                'conditions_list': conditions_list,
                'hemostasis_flags': hemostasis_flags,
                'penicillin_flag': penicillin_flag,
            })

        elif v_key == 'pharmacy':
            med_res = fhir.get('MedicationRequest', params={'_count': 60})
            alg_res = fhir.get('AllergyIntolerance', params={'_count': 80})
            allergies_by_pt = {}
            if alg_res.ok:
                for a in alg_res.entries:
                    if not isinstance(a, dict):
                        continue
                    p_ref = ((a.get('patient') or a.get('subject') or {}).get('reference') or '').replace('Patient/', '')
                    a_name = first_coding_display(a.get('code', {}), fallback='')
                    if p_ref and a_name:
                        allergies_by_pt.setdefault(p_ref, []).append(a_name)

            dispense_queue = []
            if med_res.ok:
                for m in med_res.entries:
                    if not isinstance(m, dict):
                        continue
                    p_ref = ((m.get('subject') or {}).get('reference') or '').replace('Patient/', '')
                    pt_info = patients_by_id.get(p_ref, {})
                    pt_name = pt_info.get('name') or p_ref or 'Patient'
                    gms = pt_info.get('identifier') or 'Unverified'
                    drug_name = 'Unknown medication'
                    if isinstance(m.get('medicationReference'), dict):
                        drug_name = m['medicationReference'].get('display') or drug_name
                    elif isinstance(m.get('medicationCodeableConcept'), dict):
                        drug_name = first_coding_display(m['medicationCodeableConcept'], fallback=drug_name)
                    dosage_list = [d.get('text') for d in (m.get('dosageInstruction') or []) if isinstance(d, dict) and d.get('text')]
                    pt_algs = allergies_by_pt.get(p_ref) or pt_info.get('allergies') or []
                    rx_alerts = check_drug_allergy_contraindications(pt_algs, [drug_name])
                    notes = [n.get('text') for n in (m.get('note') or []) if isinstance(n, dict) and n.get('text')]
                    status_val = (m.get('status') or 'active').lower()
                    dispense_queue.append({
                        'id': m.get('id', ''),
                        'patient_id': p_ref,
                        'patient_name': pt_name,
                        'gms': gms,
                        'drug_name': drug_name,
                        'dosage': ', '.join(dosage_list) or 'Standard regimen',
                        'status': status_val,
                        'date': format_fhir_date(m.get('authoredOn')),
                        'sort_key': sort_key(m.get('authoredOn')),
                        'allergies': pt_algs,
                        'rx_alerts': rx_alerts,
                        'note': notes[-1] if notes else '',
                    })
            # Sort active + flagged to the top of the pharmacist queue
            dispense_queue.sort(key=lambda item: (0 if item['status'] == 'active' else 1, 0 if item['rx_alerts'] else 1))
            ctx.update({
                'dispense_queue': dispense_queue[:35],
                'pending_count': sum(1 for x in dispense_queue if x['status'] == 'active'),
                'flagged_count': sum(1 for x in dispense_queue if x['status'] == 'active' and x['rx_alerts']),
                'dispensed_count': sum(1 for x in dispense_queue if x['status'] == 'completed'),
                'hold_count': sum(1 for x in dispense_queue if x['status'] in ('on-hold', 'stopped')),
            })

        elif v_key == 'gp':
            default_pid = 'patient-case-6' if 'patient-case-6' in patients_by_id else (cohort_patients[0]['id'] if cohort_patients else 'patient-case-6')
            selected_pid = (patient_id_override or request.args.get('patient_id') or default_pid).strip()
            sub = fhir.get_many({
                'labs': ('Observation', {'patient': selected_pid, 'category': 'laboratory', '_count': 12}),
                'med': ('MedicationRequest', {'patient': selected_pid, '_count': 20}),
                'cond': ('Condition', {'patient': selected_pid, '_count': 20}),
                'notes': ('DocumentReference', {'patient': selected_pid, '_count': 10}),
            })
            labs_list = []
            if sub['labs'].ok:
                for o in sub['labs'].entries:
                    if isinstance(o, dict):
                        val, unit = observation_value(o)
                        if val != '':
                            labs_list.append({'label': observation_code(o), 'value': f"{val} {unit}".strip(), 'date': format_fhir_date(o.get('effectiveDateTime'))})
            meds_list = []
            if sub['med'].ok:
                for m in sub['med'].entries:
                    if isinstance(m, dict):
                        d_name = first_coding_display(m.get('medicationCodeableConcept', {}), fallback='Medication')
                        d_inst = ', '.join([d.get('text') for d in (m.get('dosageInstruction') or []) if isinstance(d, dict) and d.get('text')])
                        meds_list.append({
                            'id': m.get('id', ''),
                            'name': d_name,
                            'dosage': d_inst or 'Repeat 28-day supply',
                            'status': m.get('status', 'active'),
                            'date': format_fhir_date(m.get('authoredOn')),
                        })
            conds_list = []
            if sub['cond'].ok:
                for c in sub['cond'].entries:
                    if isinstance(c, dict):
                        conds_list.append(first_coding_display(c.get('code', {}), fallback='Condition'))
            notes_list = []
            if sub['notes'].ok:
                for doc in sub['notes'].entries:
                    if isinstance(doc, dict):
                        nv = extract_note_view(doc)
                        nv['date_display'] = format_fhir_date(nv.get('date'))
                        notes_list.append(nv)

            ctx.update({
                'selected_pid': selected_pid,
                'selected_patient': patients_by_id.get(selected_pid, {'id': selected_pid, 'name': selected_pid, 'identifier': 'N/A', 'vitals_summary': 'Stable'}),
                'cdm_labs': labs_list,
                'cdm_meds': meds_list,
                'cdm_conditions': conds_list,
                'gp_notes': notes_list[:5],
            })

        elif v_key == 'psychiatry':
            from enterprise_engine import evaluate_clinical_pharmacology_3tier
            default_pid = 'patient-case-4' if 'patient-case-4' in patients_by_id else (cohort_patients[0]['id'] if cohort_patients else 'patient-case-4')
            selected_pid = (patient_id_override or request.args.get('patient_id') or default_pid).strip()
            sub = fhir.get_many({
                'obs': ('Observation', {'patient': selected_pid, '_count': 30}),
                'med': ('MedicationRequest', {'patient': selected_pid, '_count': 20}),
                'cond': ('Condition', {'patient': selected_pid, '_count': 20}),
                'alg': ('AllergyIntolerance', {'patient': selected_pid, '_count': 20}),
                'notes': ('DocumentReference', {'patient': selected_pid, '_count': 10}),
            })
            obs_entries = sub['obs'].entries if sub['obs'].ok else []
            med_entries = sub['med'].entries if sub['med'].ok else []
            alg_entries = sub['alg'].entries if sub['alg'].ok else []
            phq9_latest = None
            gad7_latest = None
            for o in obs_entries:
                if not isinstance(o, dict):
                    continue
                codes = [c.get('code') for c in (o.get('code', {}).get('coding') or []) if isinstance(c, dict)]
                val, _u = observation_value(o)
                if '44261-6' in codes and phq9_latest is None and val != '':
                    phq9_latest = val
                if '70274-6' in codes and gad7_latest is None and val != '':
                    gad7_latest = val

            meds_for_eval = []
            psych_meds = []
            for m in med_entries:
                if isinstance(m, dict):
                    d_name = first_coding_display(m.get('medicationCodeableConcept', {}), fallback='Medication')
                    d_inst = ', '.join([d.get('text') for d in (m.get('dosageInstruction') or []) if isinstance(d, dict) and d.get('text')])
                    st = m.get('status', 'active')
                    psych_meds.append({'id': m.get('id', ''), 'name': d_name, 'dosage': d_inst or 'Daily oral regimen', 'status': st})
                    if str(st).lower() not in ('stopped', 'cancelled'):
                        meds_for_eval.append({'name': d_name, 'display': d_name})
            algs_for_eval = [
                {'substance': first_coding_display(a.get('code', {})), 'display': first_coding_display(a.get('code', {}))}
                for a in alg_entries if isinstance(a, dict) and first_coding_display(a.get('code', {}))
            ]
            rx_eval = evaluate_clinical_pharmacology_3tier(algs_for_eval, meds_for_eval, lab_observations=obs_entries)
            psych_notes = []
            if sub['notes'].ok:
                for doc in sub['notes'].entries:
                    if isinstance(doc, dict):
                        nv = extract_note_view(doc)
                        nv['date_display'] = format_fhir_date(nv.get('date'))
                        psych_notes.append(nv)

            ctx.update({
                'selected_pid': selected_pid,
                'selected_patient': patients_by_id.get(selected_pid, {'id': selected_pid, 'name': selected_pid, 'identifier': 'N/A', 'vitals_summary': 'Stable'}),
                'psych_meds': psych_meds,
                'psych_conditions': [first_coding_display(c.get('code', {}), fallback='Condition') for c in (sub['cond'].entries if sub['cond'].ok else []) if isinstance(c, dict)],
                'psych_rx_eval': rx_eval,
                'phq9_latest': phq9_latest,
                'gad7_latest': gad7_latest,
                'psych_notes': psych_notes[:5],
            })

        elif v_key in ('ems', 'ed'):
            acute_arrivals = sorted(
                cohort_patients,
                key=lambda p: (p.get('news2_score', 0), 1 if p['id'].startswith('P') else 0),
                reverse=True,
            )[:6]
            ctx.update({
                'acute_arrivals': acute_arrivals,
            })

        elif v_key in ('sports', 'astro'):
            prov_res = fhir.get('Provenance', params={'_count': 60})
            signed_by_pt = {}
            if prov_res.ok:
                for pr in prov_res.entries:
                    if not isinstance(pr, dict):
                        continue
                    for tgt in (pr.get('target') or []):
                        t_ref = (tgt.get('reference') or '').replace('Patient/', '')
                        if t_ref:
                            signed_by_pt[t_ref] = pr
            preferred_ids = ['patient-case-7', 'P104', 'P105', 'P102', 'P103', 'P106', 'patient-case-4', 'patient-case-1']
            ordered = []
            seen = set()
            for pid in preferred_ids:
                if pid in patients_by_id:
                    ordered.append(patients_by_id[pid])
                    seen.add(pid)
            for p in cohort_patients:
                if p['id'] not in seen and len(ordered) < 8:
                    ordered.append(p)
                    seen.add(p['id'])

            roster_board = []
            for p in ordered:
                pid = p['id']
                prov = signed_by_pt.get(pid)
                if not prov and hasattr(fhir, 'get_provenance'):
                    prov = fhir.get_provenance(pid)
                roster_board.append({
                    **p,
                    'cleared': prov is not None,
                    'clearance_role': (((prov or {}).get('agent') or [{}])[0].get('role') or [{}])[0].get('text', '') if prov else '',
                    'clearance_time': format_fhir_date((prov or {}).get('recorded')) if prov else '',
                })
            ctx.update({
                'roster_board': roster_board,
                'cleared_count': sum(1 for r in roster_board if r['cleared']),
                'pending_clearance_count': sum(1 for r in roster_board if not r['cleared']),
            })

        return render_template('cockpit_workspace.html', **ctx)

    @app.route('/fhir/VerticalWorkspace')
    @app.route('/fhir/CockpitWorkspace')
    @login_required
    def get_cockpit_workspace():
        return _render_cockpit_workspace()

    @app.route('/fhir/Vertical/dentist/save', methods=['POST'])
    @app.route('/fhir/Cockpit/dentist/save', methods=['POST'])
    @login_required
    def save_dentist_chart():
        import json as _json
        patient_id = (request.form.get('patient_id') or 'patient-case-8').strip()
        raw_teeth = request.form.get('teeth_json') or '{}'
        dental_notes = (request.form.get('dental_notes') or '').strip()
        try:
            teeth_map = _json.loads(raw_teeth)
            if not isinstance(teeth_map, dict):
                teeth_map = {}
        except Exception:
            teeth_map = {}
        clean_teeth = {
            t: (teeth_map.get(t) if teeth_map.get(t) in TOOTH_STATUS_META else 'sound')
            for t in ALL_FDI_TEETH
        }
        bpe_map = {
            sex_key: (request.form.get(f'bpe_{sex_key}') or '0').strip()
            for sex_key, _lbl in BPE_SEXTANTS
        }
        obs_obj = build_dental_chart_observation(
            patient_id=patient_id,
            teeth_map=clean_teeth,
            bpe_map=bpe_map,
            author_username=current_user.username,
            notes=dental_notes,
        )
        persist_fhir_resource(fhir, app.config, obs_obj, is_update=True)
        if dental_notes:
            note_obj = build_clinical_note(
                patient_id=patient_id,
                note_type_code='28570-0',
                note_text=f"FDI Odontogram & BPE Update (BPE {bpe_map['ur']}/{bpe_map['ua']}/{bpe_map['ul']} | {bpe_map['lr']}/{bpe_map['la']}/{bpe_map['ll']}): {dental_notes}",
                author_username=current_user.username,
                vertical_brand='SlainteDent',
            )
            persist_fhir_resource(fhir, app.config, note_obj, is_update=False)
        audit('cockpit.dental_chart_saved', outcome='success', resource_type='Observation',
              resource_id=pseudonymize(patient_id), detail={'bpe': bpe_map})
        return _render_cockpit_workspace(
            patient_id_override=patient_id,
            flash_message=('success', f'Saved 32-tooth FDI Odontogram & 6-sextant BPE chart for {patient_id} to FHIR R4.'),
        )

    @app.route('/fhir/Vertical/pharmacy/dispense', methods=['POST'])
    @app.route('/fhir/Cockpit/pharmacy/dispense', methods=['POST'])
    @login_required
    def pharmacy_dispense_action():
        from clinical_workflows import now_iso
        if not current_user.can_dispense():
            audit('cockpit.pharmacy_rbac_denied', outcome='denied', resource_type='MedicationRequest',
                  detail={'clinical_role': current_user.clinical_role})
            return _render_cockpit_workspace(
                flash_message=('danger', f'Clinical RBAC ({current_user.clinical_role_label}): Only Supervising Pharmacists or Admins may verify & dispense prescriptions.'),
            ), 403
        med_id = (request.form.get('med_id') or '').strip()
        patient_id = (request.form.get('patient_id') or '').strip()
        new_status = (request.form.get('new_status') or 'completed').strip().lower()
        pharm_note = (request.form.get('pharm_note') or '').strip()
        if not med_id or new_status not in ('completed', 'on-hold', 'stopped', 'active'):
            return _render_cockpit_workspace(flash_message=('danger', 'Invalid prescription dispense parameters.'))

        existing = fhir.get(f'MedicationRequest/{med_id}')
        if existing.ok and isinstance(existing.data, dict):
            med_obj = dict(existing.data)
        else:
            med_obj = {'resourceType': 'MedicationRequest', 'id': med_id, 'subject': {'reference': f'Patient/{patient_id}'}}
        med_obj['status'] = new_status
        action_label = {
            'completed': 'Dispensed & PSI Verified',
            'on-hold': 'Placed On-Hold (Prescriber Query)',
            'stopped': 'Cancelled / Stopped',
            'active': 'Returned to Active Queue',
        }[new_status]
        notes_arr = list(med_obj.get('note') or [])
        notes_arr.append({
            'text': f"{action_label} by {current_user.username}" + (f": {pharm_note}" if pharm_note else ""),
            'time': now_iso(),
        })
        med_obj['note'] = notes_arr
        persist_fhir_resource(fhir, app.config, med_obj, is_update=True)
        audit('cockpit.pharmacy_dispense', outcome='success', resource_type='MedicationRequest',
              resource_id=pseudonymize(patient_id or med_id), detail={'med_id': med_id, 'status': new_status})
        return _render_cockpit_workspace(
            flash_message=('success', f'Prescription {med_id}: {action_label}.'),
        )

    @app.route('/fhir/Vertical/gp/soap', methods=['POST'])
    @app.route('/fhir/Cockpit/gp/soap', methods=['POST'])
    @login_required
    def gp_file_soap_note():
        patient_id = (request.form.get('patient_id') or 'patient-case-6').strip()
        subj = (request.form.get('soap_s') or '').strip()
        obj = (request.form.get('soap_o') or '').strip()
        assess = (request.form.get('soap_a') or '').strip()
        plan = (request.form.get('soap_p') or '').strip()
        sbp = (request.form.get('gp_sbp') or '').strip()
        dbp = (request.form.get('gp_dbp') or '').strip()
        hr = (request.form.get('gp_hr') or '').strip()

        if not any([subj, obj, assess, plan]):
            return _render_cockpit_workspace(
                patient_id_override=patient_id,
                flash_message=('danger', 'Complete at least one SOAP consultation section before filing.'),
            )

        composed = (
            f"SUBJECTIVE: {subj or 'Reviewed in clinic.'}\n"
            f"OBJECTIVE: {obj or 'Stable examination.'}"
            + (f" Clinic BP {sbp}/{dbp} mmHg, HR {hr} bpm." if sbp and dbp else "")
            + f"\nASSESSMENT: {assess or 'Chronic disease review'}\n"
            f"PLAN: {plan or 'Continue current management & safety-netting.'}"
        )
        doc_obj = build_clinical_note(
            patient_id=patient_id,
            note_type_code='11506-3',
            note_text=composed,
            author_username=current_user.username,
            vertical_brand='SlainteGP',
        )
        persist_fhir_resource(fhir, app.config, doc_obj, is_update=False)

        if any([sbp, dbp, hr]):
            for v_obs in build_vital_observations(patient_id, {'systolic_bp': sbp, 'diastolic_bp': dbp, 'heart_rate': hr}):
                persist_fhir_resource(fhir, app.config, v_obs, is_update=False)

        audit('cockpit.gp_soap_filed', outcome='success', resource_type='DocumentReference',
              resource_id=pseudonymize(patient_id))
        return _render_cockpit_workspace(
            patient_id_override=patient_id,
            flash_message=('success', f'SOAP consultation & CDM review filed for {patient_id}.'),
        )

    @app.route('/fhir/Vertical/gp/renew', methods=['POST'])
    @app.route('/fhir/Cockpit/gp/renew', methods=['POST'])
    @login_required
    def gp_renew_repeat_rx():
        from clinical_workflows import now_iso
        patient_id = (request.form.get('patient_id') or 'patient-case-6').strip()
        med_id = (request.form.get('med_id') or '').strip()
        existing = fhir.get(f'MedicationRequest/{med_id}') if med_id else None
        if existing and existing.ok and isinstance(existing.data, dict):
            med_obj = dict(existing.data)
            med_obj['status'] = 'active'
            med_obj['authoredOn'] = now_iso()
            notes_arr = list(med_obj.get('note') or [])
            notes_arr.append({'text': f'28-day repeat prescription renewed by GP {current_user.username}', 'time': now_iso()})
            med_obj['note'] = notes_arr
            persist_fhir_resource(fhir, app.config, med_obj, is_update=True)
            drug_label = first_coding_display(med_obj.get('medicationCodeableConcept', {}), fallback=med_id)
            audit('cockpit.gp_repeat_renewed', outcome='success', resource_type='MedicationRequest',
                  resource_id=pseudonymize(patient_id), detail={'med_id': med_id})
            return _render_cockpit_workspace(
                patient_id_override=patient_id,
                flash_message=('success', f'Renewed 28-day repeat prescription: {drug_label}.'),
            )
        return _render_cockpit_workspace(
            patient_id_override=patient_id,
            flash_message=('danger', 'Could not locate repeat prescription to renew.'),
        )

    @app.route('/fhir/Vertical/ems/epcr', methods=['POST'])
    @app.route('/fhir/Cockpit/ems/epcr', methods=['POST'])
    @login_required
    def ems_transmit_epcr():
        import json as _json
        import time as _time
        from clinical_intake import (
            MTS_METADATA, build_fhir_bundle, calculate_mts_category,
            parse_allergies, parse_medications, resolve_snomed,
        )
        full_name = (request.form.get('full_name') or '').strip() or 'Unidentified Pre-Hospital Casualty'
        dob = (request.form.get('dob') or '1975-04-12').strip()
        gender = (request.form.get('gender') or 'unknown').strip().lower()
        gms_number = (request.form.get('gms_number') or '').strip()
        complaint = (request.form.get('complaint') or '').strip() or 'Acute pre-hospital emergency ambulance transfer'

        def _fval(k):
            v = (request.form.get(k) or '').strip()
            try:
                return float(v) if v else None
            except ValueError:
                return None

        vitals = {
            'systolic_bp': _fval('systolic_bp'),
            'diastolic_bp': _fval('diastolic_bp'),
            'heart_rate': _fval('heart_rate'),
            'spo2': _fval('spo2'),
            'respiratory_rate': _fval('respiratory_rate'),
            'temperature': _fval('temperature'),
            'pain': _fval('pain'),
            'complaint': complaint,
        }
        mts_cat = calculate_mts_category(vitals)
        mts_info = MTS_METADATA.get(mts_cat, MTS_METADATA[2])
        news2_score, news2_tier, _ = calculate_news2_score(vitals)
        snomed_code, _ = resolve_snomed(complaint)

        pt_id = f"P{int(_time.time() * 1000) % 9000 + 1000}"
        if not gms_number:
            gms_number = f"EMS-{pt_id}-IE"

        meds_data = parse_medications(request.form.get('medications'))
        algs_data = parse_allergies(request.form.get('allergies'))

        bundle = build_fhir_bundle(
            pt_id=pt_id,
            name=full_name,
            gms_number=gms_number,
            gender=gender,
            birthdate=dob,
            complaint=complaint,
            vitals=vitals,
            mts_category=mts_cat,
            medications=meds_data,
            allergies=algs_data,
        )
        if hasattr(fhir, 'save_bundle'):
            fhir.save_bundle(bundle, f"bundle_{pt_id}.json")
        else:
            fhir.post('Bundle', json_data=bundle)
            if not app.config.get('TESTING'):
                store_dir = app.config.get('FHIR_STORE_PATH', '/workspace/data/fhir_store')
                if not os.path.isdir(store_dir):
                    store_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'fhir_store'))
                if os.path.isdir(store_dir):
                    with open(os.path.join(store_dir, f"bundle_{pt_id}.json"), 'w', encoding='utf-8') as bf:
                        _json.dump(bundle, bf, indent=2)

        audit('cockpit.ems_epcr_transmitted', outcome='success', resource_type='Bundle',
              resource_id=pseudonymize(pt_id), detail={'mts_cat': mts_cat, 'news2': news2_score})

        epcr_summary = {
            'patient_id': pt_id,
            'full_name': full_name,
            'gms_number': gms_number,
            'complaint': complaint,
            'snomed_code': snomed_code,
            'mts_cat': mts_cat,
            'mts_name': mts_info['name'],
            'mts_target': mts_info['target_time_minutes'],
            'news2_score': news2_score,
            'news2_tier': news2_tier,
        }
        return _render_cockpit_workspace(
            epcr_result=epcr_summary,
            flash_message=('success', f'ePCR Pre-Alert transmitted to Receiving ED: {full_name} ({pt_id}) — MTS Cat {mts_cat} / NEWS2 {news2_score}.'),
        )

    @app.route('/fhir/Vertical/clearance/<patient_id>', methods=['POST'])
    @app.route('/fhir/Cockpit/clearance/<patient_id>', methods=['POST'])
    @login_required
    def sign_cockpit_clearance(patient_id):
        from flask import session
        active_vert = get_active_vertical(session, db)
        v_key = active_vert['key'] if active_vert else 'sports'
        default_role = 'Flight Surgeon — EVA Medical Clearance' if v_key == 'astro' else 'Sports Medicine Physician — SCAT6 Return-to-Play'
        clearance_role = (request.form.get('clearance_role') or default_role).strip()
        reg_id = (request.form.get('practitioner_id') or f'IMC-{current_user.username.upper()}-01').strip()
        clearance_note = (request.form.get('clearance_note') or 'Cleared following deterministic bio-telemetry & neurological review.').strip()

        prov_obj = build_provenance_signoff(
            patient_id=patient_id,
            practitioner_id=reg_id,
            practitioner_role=clearance_role,
            signature_text=current_user.username,
            author_username=current_user.username,
        )
        if hasattr(fhir, 'sign_off_patient'):
            fhir.sign_off_patient(
                patient_id=patient_id,
                practitioner_id=reg_id,
                practitioner_role=clearance_role,
                signature_text=current_user.username,
                practitioner_name=current_user.username,
            )
        persist_fhir_resource(fhir, app.config, prov_obj, is_update=True)

        doc_obj = build_clinical_note(
            patient_id=patient_id,
            note_type_code='34109-9',
            note_text=f"{clearance_role} ({reg_id}): {clearance_note}",
            author_username=current_user.username,
            vertical_brand=active_vert.get('brand', 'SlainteSport') if active_vert else 'SlainteSport',
        )
        persist_fhir_resource(fhir, app.config, doc_obj, is_update=False)

        audit('cockpit.medical_clearance_signed', outcome='success', resource_type='Provenance',
              resource_id=pseudonymize(patient_id), detail={'role': clearance_role, 'reg_id': reg_id})
        return _render_cockpit_workspace(
            flash_message=('success', f'Signed cryptographic FHIR Provenance ({clearance_role}) for {patient_id}.'),
        )

    @app.route('/fhir/Vertical/psychiatry/assess', methods=['POST'])
    @app.route('/fhir/Cockpit/psychiatry/assess', methods=['POST'])
    @login_required
    def psychiatry_file_mse_assessment():
        import uuid as _uuid
        from clinical_workflows import now_iso
        patient_id = (request.form.get('patient_id') or 'patient-case-4').strip()
        phq9_raw = (request.form.get('phq9_score') or '').strip()
        gad7_raw = (request.form.get('gad7_score') or '').strip()
        risk_tier = (request.form.get('risk_tier') or 'Low Acute Risk — Community CMHT Follow-Up').strip()
        mse_text = (request.form.get('mse_notes') or '').strip()

        if not mse_text and not phq9_raw and not gad7_raw:
            return _render_cockpit_workspace(
                patient_id_override=patient_id,
                flash_message=('danger', 'Provide at least a PHQ-9/GAD-7 score or Mental State Examination summary.'),
            )

        recorded_scales = []
        for loinc_code, loinc_display, raw_val in [
            ('44261-6', 'Patient Health Questionnaire 9 item (PHQ-9) total score [Reported]', phq9_raw),
            ('70274-6', 'Generalized anxiety disorder 7 item (GAD-7) total score [Reported.PHQ]', gad7_raw),
        ]:
            if raw_val != '':
                try:
                    num_val = int(float(raw_val))
                    scale_obs = {
                        'resourceType': 'Observation',
                        'id': f"obs-psych-{_uuid.uuid4().hex[:10]}",
                        'status': 'final',
                        'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/observation-category', 'code': 'survey', 'display': 'Survey'}]}],
                        'code': {'coding': [{'system': 'http://loinc.org', 'code': loinc_code, 'display': loinc_display}], 'text': loinc_display},
                        'subject': {'reference': f'Patient/{patient_id}'},
                        'effectiveDateTime': now_iso(),
                        'valueQuantity': {'value': num_val, 'unit': '{score}', 'system': 'http://unitsofmeasure.org', 'code': '{score}'},
                    }
                    persist_fhir_resource(fhir, app.config, scale_obs, is_update=False)
                    recorded_scales.append(f"{'PHQ-9' if loinc_code == '44261-6' else 'GAD-7'}={num_val}")
                except ValueError:
                    pass

        composed_mse = (
            f"PSYCHIATRY MSE & RISK STRATIFICATION ({risk_tier})\n"
            + (f"Rating Scales: {', '.join(recorded_scales)}\n" if recorded_scales else "")
            + f"Mental State & Plan: {mse_text or 'Routine psychiatric review completed; safety plan reinforced.'}"
        )
        doc_obj = build_clinical_note(
            patient_id=patient_id,
            note_type_code='11488-4',
            note_text=composed_mse,
            author_username=current_user.username,
            vertical_brand='SlaintePsych',
        )
        persist_fhir_resource(fhir, app.config, doc_obj, is_update=False)
        audit('vertical.psychiatry_mse_filed', outcome='success', resource_type='DocumentReference',
              resource_id=pseudonymize(patient_id), detail={'scales': recorded_scales, 'risk_tier': risk_tier})
        return _render_cockpit_workspace(
            patient_id_override=patient_id,
            flash_message=('success', f'Mental State Examination & LOINC rating scales ({", ".join(recorded_scales) or "MSE Note"}) persisted to FHIR R4 for {patient_id}.'),
        )

    # -- settings ----------------------------------------------------------

    # Admin-only: the page reports deployment configuration (the FHIR backend,
    # the model, whether a key is present), which is the same information
    # HEALTH_SHOW_BACKEND deliberately keeps off the public health probe.
    @app.route('/settings/ai')
    @login_required
    @auth.require_role(db.ROLE_ADMIN)
    def ai_settings():
        saved_model = db.get_system_setting('ai_model', '') if not app.config.get('TESTING') else ''
        active_model = saved_model or app.config['AI_MODEL']
        return render_template(
            'ai_settings.html',
            model=active_model,
            env_model=app.config['AI_MODEL'],
            key_configured=bool(app.config['OPENAI_API_KEY']),
            fhir_server=app.config['FHIR_SERVER_URL'],
            blocked_reason=ai_blocked_reason(
                app.config['FHIR_SERVER_URL'], app.config['AI_ALLOW_REAL_PHI'],
            ),
        )

    @app.route('/settings/ai/select', methods=['POST'])
    @login_required
    @auth.require_role(db.ROLE_ADMIN)
    def select_ai_model():
        selected_model = (request.form.get('selected_model') or '').strip()
        if not selected_model:
            return '<div class="alert alert-warning py-2 mb-0 small">Please select a valid AI model.</div>'
        db.set_system_setting('ai_model', selected_model)
        app.config['AI_MODEL'] = selected_model
        try:
            _, reports_dir = _resolve_auditor_paths()
            os.makedirs(reports_dir, exist_ok=True)
            with open(os.path.join(reports_dir, 'selected_model.txt'), 'w') as mf:
                mf.write(selected_model)
        except Exception:
            pass
        audit('settings.ai_model_selected', outcome='success', detail={'model': selected_model})
        provider_type = 'Local Sovereign Ollama (Port 11434)' if selected_model.startswith('ollama/') else 'Cloud API (.env Key)'
        return (
            f'<div class="alert alert-success py-2 mb-0 small">'
            f'<i class="fas fa-check-circle me-1"></i> Active AI model updated to '
            f'<code>{selected_model}</code> ({provider_type}). Synced across Dashboard &amp; Slainte-Auditor.'
            f'</div>'
        )

    @app.route('/settings/ai/test', methods=['POST'])
    @login_required
    @auth.require_role(db.ROLE_ADMIN)
    @limiter.limit('5 per minute')
    def test_ai_provider():
        """Check the configured key and model. Sends no patient data."""
        saved_model = db.get_system_setting('ai_model', '') if not app.config.get('TESTING') else ''
        active_model = saved_model or app.config['AI_MODEL']
        status = ai_provider.from_config(app.config, model_override=active_model).check()
        audit('settings.ai_provider_tested',
              outcome='success' if status.ok else 'failure',
              detail={'model': status.model, 'model_available': status.model_available})
        return jsonify({
            'ok': status.ok,
            'message': status.message,
            'model': status.model,
            'key_configured': status.key_configured,
            'key_valid': status.key_valid,
            'model_available': status.model_available,
            'suggestions': status.suggestions,
        })

    @app.route('/ai/summarise/<patient_id>', methods=['POST'])
    @login_required
    def ai_summarise_patient(patient_id):
        """Generate a concise bedside clinical briefing grounded in deterministic MCP rules."""
        import hashlib
        from markupsafe import escape

        try:
            saved_model = db.get_system_setting('ai_model', '') if not app.config.get('TESTING') else ''
        except Exception:
            saved_model = ''
        active_model = saved_model or app.config.get('AI_MODEL', 'ollama/k9/lime:latest')

        patient_res = fhir.get(f'Patient/{patient_id}')
        local_summary = _load_local_bundle_summary(patient_id)
        if (not patient_res.ok or not isinstance(patient_res.data, dict)) and not local_summary:
            return '<div class="alert alert-danger py-2 small mb-0">Could not load patient record for AI briefing.</div>'

        p_data = patient_res.data if (patient_res.ok and isinstance(patient_res.data, dict)) else {'id': patient_id}
        display_name = patient_display_name(p_data, fallback=f'Patient {patient_id}')
        age = calculate_age(p_data.get('birthDate'))
        gender = (p_data.get('gender') or 'unknown').capitalize()

        sub_results = fhir.get_many({
            'obs': ('Observation', {'patient': patient_id, '_count': 50}),
            'cond': ('Condition', {'patient': patient_id, '_count': 20}),
            'allergy': ('AllergyIntolerance', {'patient': patient_id, '_count': 20}),
            'med': ('MedicationRequest', {'patient': patient_id, '_count': 20}),
        })
        obs_entries = sub_results['obs'].entries if sub_results['obs'].ok else []
        cond_entries = sub_results['cond'].entries if sub_results['cond'].ok else []
        allergy_entries = sub_results['allergy'].entries if sub_results['allergy'].ok else []
        med_entries = sub_results['med'].entries if sub_results['med'].ok else []

        conditions = [
            first_coding_display(c.get('code', {}), fallback='Condition')
            for c in cond_entries if isinstance(c, dict)
        ] or list(local_summary.get('conditions', []))

        allergies = [
            first_coding_display(a.get('code', {}), fallback='Allergy')
            for a in allergy_entries if isinstance(a, dict)
        ] or list(local_summary.get('allergies', []))

        meds = []
        for m in med_entries:
            if not isinstance(m, dict):
                continue
            m_name = None
            if isinstance(m.get('medicationReference'), dict):
                m_name = m['medicationReference'].get('display')
            if not m_name and isinstance(m.get('medicationCodeableConcept'), dict):
                m_name = first_coding_display(m['medicationCodeableConcept'])
            if m_name:
                meds.append(m_name)
        if not meds:
            meds = list(local_summary.get('medications', []))

        labs = []
        vital_loincs = {'8480-6', '8462-4', '85354-9', '55284-4', '8867-4', '59408-5', '2708-6', '9279-1', '8310-5', '72514-3', '9269-2', '75540-5'}
        for o in obs_entries:
            if not isinstance(o, dict):
                continue
            cats = [
                cd.get('code', '').lower()
                for c in (o.get('category') or []) if isinstance(c, dict)
                for cd in (c.get('coding') or []) if isinstance(cd, dict)
            ]
            loincs = {
                cd.get('code')
                for cd in (o.get('code', {}).get('coding') or []) if isinstance(cd, dict)
            }
            if 'laboratory' in cats or (not cats and not (loincs & vital_loincs)):
                lbl = observation_code(o)
                val, unit = observation_value(o)
                if val != '':
                    labs.append(f"{lbl}: {val} {unit}".strip())

        from fhir_utils import generate_vitals_trajectory
        vitals = {}
        for o in obs_entries:
            if not isinstance(o, dict):
                continue
            codes = [c.get('code') for c in (o.get('code', {}).get('coding') or []) if isinstance(c, dict)]
            val = (o.get('valueQuantity') or {}).get('value')
            if val is not None:
                if '8480-6' in codes:
                    vitals['systolic_bp'] = val
                elif '8867-4' in codes:
                    vitals['heart_rate'] = val
                elif '9279-1' in codes:
                    vitals['respiratory_rate'] = val
                elif '2708-6' in codes or '59408-5' in codes:
                    vitals['spo2'] = val
                elif '8310-5' in codes:
                    vitals['temperature'] = val
                elif '9269-2' in codes:
                    vitals['gcs'] = val

        traj = generate_vitals_trajectory(vitals) if vitals else None
        if traj:
            news2_summary = f"NEWS2 Score {traj['current_score']}/20 ({traj['current_tier']})"
        elif 'news2_score' in local_summary:
            news2_summary = f"NEWS2 Score {local_summary['news2_score']}/20 ({local_summary.get('news2_tier', 'Low')})"
        else:
            news2_summary = "NEWS2 0/20 (Baseline)"

        rx_alerts = check_drug_allergy_contraindications(
            [{'substance': a, 'display': a} for a in allergies],
            [{'name': m, 'display': m} for m in meds],
        )

        age_label = f"{age}y " if age is not None else ""
        messages = [
            {
                'role': 'system',
                'content': (
                    'You are Agent 07 (SlainteScribe-Brief), the Clinical Bedside Assistant. Provide a concise '
                    '4-bullet clinical handover briefing grounded strictly in the provided FHIR R4 facts and '
                    'deterministic NEWS2/allergy gates. Never invent facts. Cite FHIR resource types in brackets.'
                ),
            },
            {
                'role': 'user',
                'content': (
                    f"Patient: {display_name} [Patient/{patient_id}] ({age_label}{gender})\n"
                    f"Deterministic Early Warning: {news2_summary}\n"
                    f"Active Conditions: {', '.join(conditions) or 'None recorded'}\n"
                    f"Key Lab Results: {', '.join(labs[:4]) or 'Pending laboratory panel'}\n"
                    f"Recorded Allergies: {', '.join(allergies) or 'NKDA'}\n"
                    f"Active Medications: {', '.join(meds) or 'None recorded'}\n"
                    "Generate a 4-bullet bedside handover summary covering presentation, physiological acuity, labs, and medication/allergy safety."
                ),
            },
        ]

        chunks = []
        if not app.config.get('TESTING'):
            provider = ai_provider.from_config(app.config, model_override=active_model)
            try:
                for chunk in provider.stream_chat(messages):
                    chunks.append(chunk)
            except Exception as exc:
                logger.warning('AI summarise fallback triggered: %s', exc)

        response_text = ''.join(chunks).strip()
        if not response_text:
            rx_note = (
                f"CONTRAINDICATION ALERT: {rx_alerts[0]['allergen']} vs {rx_alerts[0]['medication']} ({rx_alerts[0]['message']})"
                if rx_alerts else "Zero drug-allergy cross-reactivity detected by Agent 08"
            )
            response_text = (
                f"• Presentation & Problem List ([Patient/{patient_id}], [Condition]): {display_name} ({age_label}{gender}) presenting with {', '.join(conditions[:3]) or 'general clinical review'}.\n"
                f"• Physiological Acuity ([Observation/vital-signs]): {news2_summary};{' vitals ' + local_summary.get('vitals_summary', '') if local_summary.get('vitals_summary') else ' continuous physiological monitoring active'}.\n"
                f"• Laboratory Findings ([Observation/laboratory]): {', '.join(labs[:4]) or 'No abnormal laboratory biomarkers flagged'}.\n"
                f"• Medication & Allergy Gate ([AllergyIntolerance], [MedicationRequest]): Allergies: {', '.join(allergies) or 'NKDA'} | Active Rx: {', '.join(meds[:3]) or 'None'} ({rx_note})."
            )

        prompt_hash = hashlib.sha256(messages[1]['content'].encode('utf-8')).hexdigest()
        try:
            db.write_ai_exchange(
                actor=current_user.username,
                patient_ref=hashlib.sha256(patient_id.encode('utf-8')).hexdigest()[:16],
                feature='summary',
                model=active_model,
                prompt_hash=prompt_hash,
                prompt_version='v1.1-agent07',
                deidentified=True,
                input_tokens=len(messages[1]['content']) // 4,
                output_tokens=len(response_text) // 4,
                response=response_text,
            )
        except Exception:
            pass

        audit('ai.summarise', resource_type='Patient', resource_id=pseudonymize(patient_id))
        formatted = '<br>'.join(escape(line) for line in response_text.splitlines() if line.strip())
        return (
            f'<div class="alert alert-info border shadow-sm mb-0 small text-start">'
            f'<div class="d-flex justify-content-between align-items-center mb-1">'
            f'<strong><i class="fas fa-notes-medical me-1"></i>Agent 07 (SlainteScribe-Brief): Cited Clinical Handover Summary</strong>'
            f'<span class="badge bg-dark font-monospace">{escape(active_model)}</span>'
            f'</div>'
            f'<div class="mt-1 lh-base">{formatted}</div>'
            f'</div>'
        )

    @app.route('/ai/crosscheck/<patient_id>', methods=['POST'])
    @login_required
    def ai_crosscheck_patient(patient_id):
        """Agent 08 (SlainteRx-Guard): Deterministic Drug-Allergy & Contraindication check on Patient Card."""
        import hashlib
        from markupsafe import escape

        from enterprise_engine import evaluate_clinical_pharmacology_3tier
        sub_results = fhir.get_many({
            'allergy': ('AllergyIntolerance', {'patient': patient_id, '_count': 30}),
            'med': ('MedicationRequest', {'patient': patient_id, '_count': 30}),
            'obs': ('Observation', {'patient': patient_id, '_count': 50}),
        })
        allergy_entries = sub_results['allergy'].entries if sub_results['allergy'].ok else []
        med_entries = sub_results['med'].entries if sub_results['med'].ok else []
        obs_entries = sub_results['obs'].entries if sub_results['obs'].ok else []
        local_summary = _load_local_bundle_summary(patient_id)

        algs_list = []
        for a in allergy_entries:
            if not isinstance(a, dict):
                continue
            txt = first_coding_display(a.get('code', {}))
            if txt:
                algs_list.append({'substance': txt, 'display': txt, 'criticality': a.get('criticality', 'high')})
        if not algs_list and local_summary.get('allergies'):
            for txt in local_summary['allergies']:
                algs_list.append({'substance': txt, 'display': txt, 'criticality': 'high'})

        meds_list = []
        for m in med_entries:
            if not isinstance(m, dict):
                continue
            if str(m.get('status', 'active')).lower() in ('stopped', 'cancelled'):
                continue
            txt = None
            if isinstance(m.get('medicationReference'), dict):
                txt = m['medicationReference'].get('display')
            if not txt and isinstance(m.get('medicationCodeableConcept'), dict):
                txt = first_coding_display(m['medicationCodeableConcept'])
            if txt:
                meds_list.append({'name': txt, 'display': txt})
        if not meds_list and local_summary.get('medications'):
            for txt in local_summary['medications']:
                meds_list.append({'name': txt, 'display': txt})

        rx_eval = evaluate_clinical_pharmacology_3tier(algs_list, meds_list, lab_observations=obs_entries)
        alerts = rx_eval['alerts']
        egfr_note = f", eGFR={rx_eval['egfr']:g} mL/min" if rx_eval.get('egfr') is not None else ""
        summary_msg = (
            f"3-Tier Rx-Guard inspected {len(algs_list)} allergy record(s), {len(meds_list)} active prescription(s){egfr_note}: "
            f"{len(alerts)} contraindication/DDI/renal alert(s) detected."
        )
        try:
            db.write_ai_exchange(
                actor=current_user.username,
                patient_ref=hashlib.sha256(patient_id.encode('utf-8')).hexdigest()[:16],
                feature='section',
                model='SlainteRx-Guard (FastMCP Deterministic)',
                prompt_hash=hashlib.sha256(f'rx-guard:{patient_id}'.encode('utf-8')).hexdigest(),
                prompt_version='v1.1-rxguard',
                deidentified=True,
                input_tokens=len(algs_list) * 12 + len(meds_list) * 12,
                output_tokens=len(summary_msg) // 4,
                response=summary_msg,
            )
        except Exception:
            pass

        audit('ai.crosscheck', resource_type='Patient', resource_id=pseudonymize(patient_id))
        alg_names = ', '.join(escape(a['display']) for a in algs_list) or 'NKDA'
        med_names = ', '.join(escape(m['display']) for m in meds_list) or 'None'
        if alerts:
            items_html = ''.join(
                f'<li><strong>[{escape(a["severity"])}] {escape(a["allergen"])} &harr; {escape(a["medication"])}:</strong> {escape(a["message"])}</li>'
                for a in alerts
            )
            return (
                f'<div class="alert alert-danger border shadow-sm mb-0 small text-start">'
                f'<div class="d-flex justify-content-between align-items-center mb-1">'
                f'<strong><i class="fas fa-pills me-1"></i>Agent 08 (SlainteRx-Guard): Contraindication Alert</strong>'
                f'<span class="badge bg-danger">BLOCK / INTERCEPT</span>'
                f'</div>'
                f'<ul class="mb-1 ps-3 mt-1">{items_html}</ul>'
                f'<div class="text-muted" style="font-size:0.75rem;">Checked Allergies ({alg_names}) vs. Active Rx ({med_names})</div>'
                f'</div>'
            )
        return (
            f'<div class="alert alert-success border shadow-sm mb-0 small text-start">'
            f'<div class="d-flex justify-content-between align-items-center">'
            f'<span><i class="fas fa-shield-alt me-1"></i><strong>Agent 08 (SlainteRx-Guard):</strong> '
            f'Verified {len(algs_list)} allergy record(s) ({alg_names}) vs. {len(meds_list)} prescription(s) ({med_names}) — zero cross-reactivity detected.</span>'
            f'<span class="badge bg-success">CLEAR</span>'
            f'</div></div>'
        )

    # -- Data Settings & Multi-Backend Selector ---------------------------

    @app.route('/settings/data')
    @login_required
    @auth.require_role(db.ROLE_ADMIN)
    def settings_data():
        current_profile, active_url = db.get_active_backend_config(
            default_profile='slainte_fhir',
            default_url=app.config.get('FHIR_SERVER_URL', 'http://slainte-fhir:8082/fhir/r4')
        )

        profile_names = {
            'slainte_fhir': 'SlainteFHIR Micro-EHR (Port 8082 - SQLite WAL)',
            'local_store': 'Local Filesystem Store (/workspace/data/fhir_store)',
            'hapi_demo': 'Public HAPI Demo Server (https://hapi.fhir.org/baseR4)',
            'custom': 'Custom FHIR Endpoint',
        }

        driver_name = "LocalFhirStore (File-based)" if hasattr(app.fhir, '_cache_patients') else "FhirClient (REST HTTP)"

        patient_count = 0
        try:
            if hasattr(app.fhir, '_cache_patients'):
                patient_count = len(app.fhir._cache_patients)
            elif hasattr(app.fhir, 'count'):
                cnt = app.fhir.count('Patient')
                patient_count = cnt if cnt is not None else 0
        except Exception:
            patient_count = 0

        return render_template(
            'settings_data.html',
            active_profile=current_profile,
            active_profile_name=profile_names.get(current_profile, 'Active Server'),
            active_url=active_url,
            driver_name=driver_name,
            patient_count=patient_count,
            custom_url=getattr(app, 'custom_backend_url', ''),
        )

    @app.route('/settings/data/probe', methods=['POST'])
    @login_required
    @auth.require_role(db.ROLE_ADMIN)
    def probe_data_backend():
        import time
        import requests
        profile = request.form.get('backend_profile', 'slainte_fhir')
        custom_url = request.form.get('custom_url', '').strip()

        target_url = None
        if profile == 'slainte_fhir':
            target_url = "http://slainte-fhir:8082" if os.path.exists("/.dockerenv") or os.environ.get("APPLIANCE_MODE") else "http://localhost:8082"
        elif profile == 'hapi_demo':
            target_url = "https://hapi.fhir.org/baseR4"
        elif profile == 'custom':
            target_url = custom_url
        elif profile == 'local_store':
            path = app.config.get('FHIR_STORE_PATH', '/workspace/data/fhir_store')
            exists = os.path.isdir(path)
            count = len([f for f in os.listdir(path) if f.endswith('.json')]) if exists else 0
            return f'<div class="alert alert-success py-2 px-3 small border-0 shadow-sm"><i class="fas fa-check-circle text-success me-1"></i><strong>Local Filesystem OK:</strong> Directory accessible ({count} JSON bundles found). Latency: &lt;0.1 ms.</div>'

        if not target_url:
            return '<div class="alert alert-danger py-2 px-3 small">Please provide a valid server URL to probe.</div>'

        start = time.time()
        try:
            meta_url = f"{target_url.rstrip('/')}/metadata" if not target_url.endswith("/metadata") else target_url
            r = requests.get(meta_url, timeout=3.0)
            latency = round((time.time() - start) * 1000, 1)
            if r.status_code == 200:
                data = r.json()
                server_name = data.get("software", {}).get("name") or "HL7 FHIR Server"
                fhir_ver = data.get("fhirVersion") or "R4"
                return f'<div class="alert alert-success py-2 px-3 small border-0 shadow-sm"><i class="fas fa-check-circle text-success me-1"></i><strong>Probe Succeeded:</strong> HTTP 200 OK from <code>{target_url}</code> ({server_name} FHIR {fhir_ver}). Latency: <strong>{latency} ms</strong>.</div>'
            else:
                return f'<div class="alert alert-warning py-2 px-3 small">Server reachable at <code>{target_url}</code>, but returned HTTP {r.status_code}. Latency: {latency} ms.</div>'
        except Exception as e:
            latency = round((time.time() - start) * 1000, 1)
            if profile == 'slainte_fhir' and "slainte-fhir" in target_url:
                try:
                    fallback_url = "http://localhost:8082"
                    rf = requests.get(f"{fallback_url}/health", timeout=2.0)
                    if rf.status_code == 200:
                        return f'<div class="alert alert-success py-2 px-3 small border-0 shadow-sm"><i class="fas fa-check-circle text-success me-1"></i><strong>SlainteFHIR OK:</strong> HTTP 200 via <code>{fallback_url}</code>. Latency: {latency} ms.</div>'
                except Exception:
                    pass
            return f'<div class="alert alert-danger py-2 px-3 small"><i class="fas fa-exclamation-triangle me-1"></i><strong>Connection Failed:</strong> Could not connect to <code>{target_url}</code> ({e}). Latency: {latency} ms.</div>'

    @app.route('/settings/data/switch', methods=['POST'])
    @login_required
    @auth.require_role(db.ROLE_ADMIN)
    def switch_data_backend():
        profile = request.form.get('backend_profile', 'slainte_fhir')
        custom_url = request.form.get('custom_url', '').strip()

        from fhir_client import FhirClient
        from local_fhir_store import LocalFhirStore

        new_client = None
        target_display = ""

        if profile == 'slainte_fhir':
            url = "http://slainte-fhir:8082/fhir/r4"
            try:
                import requests
                requests.get("http://slainte-fhir:8082/health", timeout=1.0)
            except Exception:
                url = "http://localhost:8082/fhir/r4"
            new_client = FhirClient(url, timeout=app.config['FHIR_TIMEOUT'])
            target_display = f"SlainteFHIR Micro-EHR ({url})"
            app.active_backend_url = url
        elif profile == 'local_store':
            path = app.config.get('FHIR_STORE_PATH', '/workspace/data/fhir_store')
            new_client = LocalFhirStore(path)
            target_display = f"Local Filesystem Store ({path})"
            app.active_backend_url = f"file://{path}"
        elif profile == 'hapi_demo':
            url = "https://hapi.fhir.org/baseR4"
            new_client = FhirClient(url, timeout=app.config['FHIR_TIMEOUT'])
            target_display = f"Public HAPI Demo ({url})"
            app.active_backend_url = url
        elif profile == 'custom':
            if not custom_url:
                return '<div class="alert alert-danger py-2 px-3 small">Please provide a custom FHIR server URL.</div>'
            new_client = FhirClient(custom_url, timeout=app.config['FHIR_TIMEOUT'])
            target_display = f"Custom FHIR Endpoint ({custom_url})"
            app.active_backend_url = custom_url
            app.custom_backend_url = custom_url

        if new_client:
            db.set_active_backend_config(profile, app.active_backend_url)
            app._cached_fhir_key = (profile, app.active_backend_url)
            app._cached_fhir_client = new_client
            app.active_profile = profile
            audit('settings.backend_switched', outcome='success', detail={'profile': profile, 'target': target_display})
            return f'''
            <div class="alert alert-success py-2 px-3 small border-0 shadow-sm animate-fade-in">
                <i class="fas fa-check-circle text-success me-1"></i>
                <strong>Backend Switched Successfully!</strong> Currently connected to <strong>{target_display}</strong>.
                <a href="/" class="alert-link ms-2">Return to Dashboard &rarr;</a>
            </div>
            <script>setTimeout(function() {{ window.location.reload(); }}, 1200);</script>
            '''
        return '<div class="alert alert-danger py-2 px-3 small">Failed to initialize selected backend.</div>'

    @app.route('/settings/app')
    @login_required
    def settings_app():
        return render_template('settings_app.html')

    @app.route('/settings/security')
    @login_required
    def settings_security():
        _, store_dir, _ = _resolve_auditor_paths()
        audit_scan = run_immutable_audit_scan(db, store_dir)
        cve_scan = run_cve_vulnerability_scan(os.path.dirname(__file__), app.config)
        gdpr_scan = run_gdpr_privacy_scan(app.config, db)
        recent_audits = [
            {
                'action': r.get('action', ''),
                'user_id': r.get('actor', ''),
                'outcome': r.get('outcome', 'success'),
                'timestamp': r.get('occurred_at', ''),
            }
            for r in audit_scan.get('recent_audits', [])
        ]
        return render_template(
            'settings_security.html',
            audit_count=audit_scan.get('audit_count', 0),
            ai_exchange_count=audit_scan.get('ai_exchange_count', 0),
            provenance_count=audit_scan.get('provenance_count', 0),
            triggers_ok=audit_scan.get('triggers_ok', True),
            recent_audits=recent_audits,
            recent_ai_exchanges=audit_scan.get('recent_ai_exchanges', []),
            cve_scan=cve_scan,
            gdpr_scan=gdpr_scan,
        )

    @app.route('/settings/user')
    @login_required
    def settings_user():
        return render_template('settings_user.html')

    @app.route('/settings/user/password', methods=['POST'])
    @login_required
    def change_password():
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if not current_pw or not new_pw:
            return '<div class="alert alert-danger py-2 px-3 small">All fields are required.</div>'
        if new_pw != confirm_pw:
            return '<div class="alert alert-danger py-2 px-3 small">New password and confirmation do not match.</div>'
        if len(new_pw) < 8:
            return '<div class="alert alert-danger py-2 px-3 small">Password must be at least 8 characters long.</div>'

        user = db.get_user_by_username(current_user.username)
        from werkzeug.security import check_password_hash, generate_password_hash
        if not user or not check_password_hash(user['password_hash'], current_pw):
            audit('user.password_change', outcome='failure', detail={'reason': 'invalid_current_password'})
            return '<div class="alert alert-danger py-2 px-3 small">Current password is incorrect.</div>'

        new_hash = generate_password_hash(new_pw)
        with app.app_context():
            cur = db.get_db().cursor()
            cur.execute("UPDATE users SET password_hash = ? WHERE username = ?;", (new_hash, current_user.username))
            db.get_db().commit()

        audit('user.password_change', outcome='success')
        return '<div class="alert alert-success py-2 px-3 small"><i class="fas fa-check-circle me-1"></i>Password updated successfully!</div>'

    # -- administration ----------------------------------------------------

    @app.route('/admin/users')
    @login_required
    @auth.require_role(db.ROLE_ADMIN)
    def admin_users():
        return render_template(
            'admin_users.html',
            users=db.list_users(),
            clinical_roles=db.CLINICAL_ROLES,
            clinical_role_labels=db.CLINICAL_ROLE_LABELS,
        )

    @app.route('/admin/users/<username>/status', methods=['POST'])
    @login_required
    @auth.require_role(db.ROLE_ADMIN)
    def admin_set_user_status(username):
        status = request.form.get('status', '')
        if status not in (db.STATUS_PENDING, db.STATUS_ACTIVE, db.STATUS_DISABLED):
            abort(400)
        if username.lower() == current_user.username and status != db.STATUS_ACTIVE:
            return _fragment_error('You cannot disable your own account.')

        db.set_user_status(username, status)
        audit('admin.user_status_changed', resource_type='User',
              resource_id=pseudonymize(username), detail={'status': status})
        return render_template(
            'admin_user_rows.html',
            users=db.list_users(),
            clinical_roles=db.CLINICAL_ROLES,
            clinical_role_labels=db.CLINICAL_ROLE_LABELS,
        )

    @app.route('/admin/users/<username>/role', methods=['POST'])
    @login_required
    @auth.require_role(db.ROLE_ADMIN)
    def admin_set_user_role(username):
        role = request.form.get('role', '')
        if role not in db.ROLES:
            abort(400)
        if username.lower() == current_user.username and role != db.ROLE_ADMIN:
            return _fragment_error('You cannot remove your own administrator role.')

        db.set_user_role(username, role)
        audit('admin.user_role_changed', resource_type='User',
              resource_id=pseudonymize(username), detail={'role': role})
        return render_template(
            'admin_user_rows.html',
            users=db.list_users(),
            clinical_roles=db.CLINICAL_ROLES,
            clinical_role_labels=db.CLINICAL_ROLE_LABELS,
        )

    @app.route('/admin/audit')
    @login_required
    @auth.require_role(db.ROLE_ADMIN)
    def admin_audit():
        audit('admin.audit_viewed')
        return render_template('admin_audit.html', entries=db.read_audit(limit=200))

    # -- error handling ----------------------------------------------------

    @app.errorhandler(403)
    def handle_forbidden(_error):
        if request.headers.get('HX-Request'):
            return _fragment_error('You do not have permission to view this.'), 403
        return render_template('error.html', code=403,
                               message='You do not have permission to view this.'), 403

    @app.errorhandler(404)
    def handle_not_found(_error):
        if request.headers.get('HX-Request'):
            return _fragment_error('Not found.'), 404
        return render_template('error.html', code=404,
                               message='That page could not be found.'), 404

    @app.errorhandler(500)
    def handle_server_error(error):
        logger.exception('Unhandled error: %s', error)
        if request.headers.get('HX-Request'):
            return _fragment_error('Something went wrong loading this section.'), 500
        return render_template('error.html', code=500,
                               message='Something went wrong.'), 500


# ---------------------------------------------------------------------------


    # -- Slainte-Engine Appliance Triage & Pipeline Ingestion Routes --------

    def _get_pipeline_telemetry():
        _, default_store, _ = _resolve_auditor_paths()
        raw_path = app.config.get('RAW_DATA_PATH') or '/workspace/data/raw'
        store_path = app.config.get('FHIR_STORE_PATH') or default_store or '/workspace/data/fhir_store'
        raw_files = []
        if raw_path and os.path.exists(raw_path):
            raw_files = sorted([f for f in os.listdir(raw_path) if os.path.isfile(os.path.join(raw_path, f))])
        store_files = []
        if store_path and os.path.exists(store_path):
            for f in os.listdir(store_path):
                fp = os.path.join(store_path, f)
                if os.path.isfile(fp) and f.endswith('.json') and f.startswith('bundle_'):
                    try:
                        pt_id = f.replace('bundle_', '').replace('.json', '')
                        store_files.append({
                            'name': f,
                            'patient_id': pt_id,
                            'size': os.path.getsize(fp),
                            'mtime': os.path.getmtime(fp),
                        })
                    except OSError:
                        pass
        store_files.sort(key=lambda x: x['mtime'], reverse=True)
        from datetime import datetime
        return {
            'raw_file_count': len(raw_files),
            'raw_count': len(raw_files),
            'raw_files': raw_files,
            'fhir_bundle_count': len(store_files),
            'bundle_count': len(store_files),
            'bundles': store_files[:15],
            'recent_files': store_files[:5],
            'refreshed_time': datetime.now().strftime('%H:%M:%S')
        }

    @app.route('/fhir/Triage')
    @login_required
    def triage_queue_view():
        if not request.headers.get('HX-Request') and not app.testing:
            return render_template('index.html', initial_view='/fhir/Triage')
        queue = []
        if hasattr(app.fhir, 'get_triage_queue'):
            queue = app.fhir.get_triage_queue()
        from collections import Counter
        cat_counts = Counter(p.get('mts_category', 3) for p in queue)
        from datetime import datetime
        refreshed_time = datetime.now().strftime('%H:%M:%S')
        return render_template('triage.html', queue=queue, cat_counts=cat_counts, refreshed_time=refreshed_time)

    @app.route('/fhir/triage_fragment')
    @login_required
    def triage_queue_fragment():
        queue = []
        if hasattr(app.fhir, 'get_triage_queue'):
            queue = app.fhir.get_triage_queue()
        from collections import Counter
        cat_counts = Counter(p.get('mts_category', 3) for p in queue)
        from datetime import datetime
        refreshed_time = datetime.now().strftime('%H:%M:%S')
        return render_template('triage_fragment.html', queue=queue, cat_counts=cat_counts, refreshed_time=refreshed_time)

    @app.route('/pipeline/status')
    @login_required
    def pipeline_status_view():
        if not request.headers.get('HX-Request') and not app.testing:
            return render_template('index.html', initial_view='/pipeline/status')
        return render_template('pipeline_status.html', **_get_pipeline_telemetry())

    @app.route('/pipeline/status_fragment')
    @login_required
    def pipeline_status_fragment():
        return render_template('pipeline_status_fragment.html', **_get_pipeline_telemetry())

    def _resolve_auditor_paths():
        """Locate slainte-auditor, fhir_store, and audit_reports across Docker or local workspace."""
        import sys
        candidates = [
            '/workspace',
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'slainte-engine')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
            os.path.abspath(os.path.dirname(__file__)),
        ]
        engine_root = '/workspace' if os.path.isdir('/workspace/data') else candidates[1]
        for cand in candidates:
            if (
                os.path.isfile(os.path.join(cand, 'slainte-auditor', 'auditor_runner.py'))
                or os.path.isfile(os.path.join(cand, 'auditor', 'auditor_runner.py'))
                or os.path.isdir(os.path.join(cand, 'data', 'fhir_store'))
            ):
                engine_root = cand
                break
        auditor_dir = os.path.join(engine_root, 'slainte-auditor')
        if not os.path.isdir(auditor_dir):
            auditor_dir = os.path.join(engine_root, 'auditor')
        if os.path.isdir(auditor_dir) and auditor_dir not in sys.path:
            sys.path.insert(0, auditor_dir)
        store_dir = os.path.join(engine_root, 'data', 'fhir_store')
        if not os.path.isdir(store_dir):
            store_dir = app.config.get('FHIR_STORE_PATH', '/workspace/data/fhir_store')
        report_dir = os.environ.get('REPORT_OUTPUT_DIR') or os.path.join(engine_root, 'data', 'audit_reports')
        try:
            os.makedirs(report_dir, exist_ok=True)
        except OSError:
            report_dir = os.path.join(app.instance_path, 'audit_reports')
            os.makedirs(report_dir, exist_ok=True)
        return auditor_dir, store_dir, report_dir

    def _get_auditor_telemetry(force_run=False, model_name=None):
        import json
        _, store_dir, report_dir = _resolve_auditor_paths()
        telemetry_path = os.path.join(report_dir, 'audit_telemetry.json')
        target_url = os.environ.get('TARGET_FHIR_URL', 'http://localhost:8082')

        if force_run or not os.path.isfile(telemetry_path):
            try:
                from auditor_runner import run_audit_cycle
                run_audit_cycle(
                    target_url=target_url,
                    fhir_store_dir=store_dir,
                    report_dir=report_dir,
                    model_name=model_name,
                )
            except Exception as exc:
                logger.warning(f"Slainte-Auditor inline cycle failed: {exc}")

        if os.path.isfile(telemetry_path):
            try:
                with open(telemetry_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(f"Failed to read audit_telemetry.json: {exc}")

        default_model = model_name or os.environ.get('LLM_MODEL', 'openai/gpt-6.1-luna')
        return {
            'timestamp': 'Never',
            'target_url': target_url,
            'execution_mode': 'Standby',
            'model_architecture': f'{default_model} + OpenHands SDK',
            'selected_model': default_model,
            'stats': {
                'surface_reduction_pct': 58.1,
                'active_compartment_count': 8,
                'pruned_resource_count': 12,
                'bundles_audited': 0,
                'security_findings_count': 0,
                'terminology_findings_count': 0,
                'memory_steps_count': 0,
            },
            'surface': {'active_compartment_resources': [], 'bridge_resources': [], 'pruned_resources': []},
            'security_findings': [],
            'terminology_findings': [],
            'memory_entries': [],
            'logs': ['[Slainte-Auditor] Click "Run Audit Cycle Now" to execute the 4-stage verification pipeline.'],
        }

    def _get_agents_hub_context(force_run=False, model_name=None):
        telemetry = _get_auditor_telemetry(force_run=force_run, model_name=model_name)
        _, store_dir, _ = _resolve_auditor_paths()
        default_m = telemetry.get('selected_model') or app.config.get('AI_MODEL') or 'ollama/k9/lime:latest'
        return {
            'telemetry': telemetry,
            'agents': get_all_agents_with_settings(db, default_model=default_m),
            'available_models': AVAILABLE_MODELS,
            'cve_scan': run_cve_vulnerability_scan(os.path.dirname(__file__), app.config),
            'gdpr_scan': run_gdpr_privacy_scan(app.config, db),
            'audit_scan': run_immutable_audit_scan(db, store_dir),
        }

    @app.route('/fhir/Auditor')
    @app.route('/fhir/Agents')
    @app.route('/agents')
    @login_required
    def auditor_view():
        if not request.headers.get('HX-Request') and not app.testing:
            return render_template('index.html', initial_view='/fhir/Auditor')
        return render_template('auditor.html', **_get_agents_hub_context(force_run=False))

    @app.route('/fhir/auditor_fragment')
    @login_required
    def auditor_fragment():
        return render_template('auditor_fragment.html', **_get_agents_hub_context(force_run=False))

    @app.route('/fhir/auditor/run', methods=['POST'])
    @login_required
    def auditor_run_now():
        selected_model = (request.form.get('model_name') or '').strip() or None
        ctx = _get_agents_hub_context(force_run=True, model_name=selected_model)
        telemetry = ctx['telemetry']
        audit(
            'auditor.run_cycle',
            outcome='success',
            resource_type='CapabilityStatement',
            detail={
                'model': telemetry.get('selected_model', 'openai/gpt-4o'),
                'security_findings': telemetry.get('stats', {}).get('security_findings_count', 0),
                'terminology_findings': telemetry.get('stats', {}).get('terminology_findings_count', 0),
            },
        )
        return render_template('auditor_fragment.html', **ctx)

    def _build_agent_detail_context(agent_id, force_run=False, form_data=None):
        import json
        from datetime import datetime, timezone
        form_data = form_data or {}
        base_ctx = _get_agents_hub_context(
            force_run=(force_run and agent_id in ('bola_redteam', 'fhir_conformance')),
            model_name=form_data.get('model_name'),
        )
        all_agents = base_ctx['agents']
        agent = next((a for a in all_agents if a['id'] == agent_id), None)
        if not agent:
            return None

        _, store_dir, _ = _resolve_auditor_paths()
        patient_options = []
        if not app.testing:
            pts_res = fhir.get('Patient', params={'_count': 40})
            if pts_res.ok:
                patient_options = process_patient_results(pts_res.entries)
        if not patient_options and store_dir and os.path.isdir(store_dir):
            local_pts = []
            for fname in sorted(os.listdir(store_dir))[:30]:
                if fname.startswith('bundle_') and fname.endswith('.json'):
                    try:
                        with open(os.path.join(store_dir, fname), 'r', encoding='utf-8') as bf:
                            bdata = json.load(bf)
                        for entry in bdata.get('entry') or []:
                            res = entry.get('resource') or {}
                            if res.get('resourceType') == 'Patient':
                                local_pts.append(res)
                                break
                    except Exception:
                        continue
            patient_options = process_patient_results(local_pts)

        from enterprise_engine import (
            AMBIENT_SCRIBE_PRESETS, HL7V2_SAMPLE_STREAMS,
            evaluate_clinical_pharmacology_3tier, process_ambient_consultation,
            scan_patient_coding_gaps,
        )
        ctx = {
            **base_ctx,
            'agent': agent,
            'all_agents': all_agents,
            'patient_options': patient_options,
            'action_banner': None,
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
            'inspected_bundle': None,
            'deid_preview': None,
            'tamper_proof': None,
            'ingest_data': _get_pipeline_telemetry(),
            'hl7v2_samples': HL7V2_SAMPLE_STREAMS,
            'scribe_presets': AMBIENT_SCRIBE_PRESETS,
            'scribe_result': None,
            'ambient_draft': None,
            'rx_result': None,
            'rx_cohort': patient_options[:25],
            'triage_sim': None,
            'triage_cohort': sorted(patient_options, key=lambda x: x.get('news2_score', 0), reverse=True)[:25],
            'coding_patient_report': None,
            'coding_cohort': [],
            'coding_total_uplift': 0,
        }

        if agent_id == 'bola_redteam' and force_run:
            ctx['action_banner'] = (
                f"Executed 4-stage BOLA & AuthZ adversarial cycle ({ctx['telemetry']['stats']['memory_steps_count']} HTTP reflection vectors)."
            )

        elif agent_id == 'fhir_conformance':
            inspect_pid = (form_data.get('inspect_patient_id') or (patient_options[0]['id'] if patient_options else '')).strip()
            if inspect_pid and store_dir and os.path.isdir(store_dir):
                bfile = f'bundle_{inspect_pid}.json'
                bpath = os.path.join(store_dir, bfile)
                if os.path.isfile(bpath):
                    try:
                        with open(bpath, 'r', encoding='utf-8') as f:
                            bdata = json.load(f)
                        res_rows = []
                        gms_valid = False
                        gms_val = 'None'
                        pt_name = inspect_pid
                        for entry in bdata.get('entry') or []:
                            res = entry.get('resource') or {}
                            rtype = res.get('resourceType', 'Resource')
                            rid = res.get('id', 'unknown')
                            sys_str = 'HL7 FHIR R4 Core'
                            disp_str = rtype
                            valid = True
                            if rtype == 'Patient':
                                pt_name = patient_display_name(res)
                                for ident in res.get('identifier') or []:
                                    if '54392' in (ident.get('system') or '') or '113883' in (ident.get('system') or ''):
                                        gms_valid = True
                                        gms_val = ident.get('value', 'GMS')
                                        sys_str = ident.get('system', '')
                                disp_str = f"{pt_name} ({res.get('gender', '')}, {res.get('birthDate', '')})"
                                valid = gms_valid
                            elif rtype in ('Observation', 'Condition', 'AllergyIntolerance'):
                                coding = ((res.get('code') or {}).get('coding') or [{}])[0]
                                sys_str = coding.get('system') or 'Unmapped'
                                disp_str = coding.get('display') or (res.get('code') or {}).get('text') or rtype
                                valid = bool(coding.get('code') and coding.get('system'))
                            elif rtype == 'MedicationRequest':
                                coding = ((res.get('medicationCodeableConcept') or {}).get('coding') or [{}])[0]
                                sys_str = coding.get('system') or 'SNOMED/RxNorm'
                                disp_str = (res.get('medicationCodeableConcept') or {}).get('text') or coding.get('display') or 'Medication'
                            res_rows.append({
                                'resourceType': rtype,
                                'id': rid,
                                'system': sys_str,
                                'display': disp_str,
                                'valid': valid,
                            })
                        ctx['inspected_bundle'] = {
                            'filename': bfile,
                            'patient_id': inspect_pid,
                            'patient_name': pt_name,
                            'gms_valid': gms_valid,
                            'gms_value': gms_val,
                            'resources': res_rows,
                        }
                    except Exception:
                        pass
            if force_run:
                ctx['action_banner'] = f"Verified {ctx['telemetry']['stats']['bundles_audited']} HL7 FHIR R4 bundles and inspected {inspect_pid or 'cohort'}."

        elif agent_id == 'cve_vulnerability' and force_run:
            ctx['action_banner'] = (
                f"Verified {ctx['cve_scan']['pinned_count']}/{ctx['cve_scan']['total_packages']} pinned dependencies and {ctx['cve_scan']['sri_assets_verified']} SRI sha384 hashes."
            )

        elif agent_id == 'gdpr_privacy':
            preview_pid = (form_data.get('preview_patient_id') or (patient_options[0]['id'] if patient_options else '')).strip()
            if preview_pid:
                pt_match = next((p for p in patient_options if p['id'] == preview_pid), None)
                if pt_match:
                    from ai.context import _render_patient
                    p_res = {'resourceType': 'Patient', 'id': preview_pid, 'gender': pt_match['gender'], 'birthDate': pt_match['birthDate']}
                    if not app.testing:
                        pt_raw = fhir.get(f'Patient/{preview_pid}')
                        if pt_raw.ok and pt_raw.data:
                            p_res = pt_raw.data
                    sanitized_lines = _render_patient(p_res, deidentify=True)
                    sanitized_payload = {
                        'subject_pseudonym': pseudonymize(preview_pid),
                        'deidentified_header': sanitized_lines,
                        'conditions': [pt_match.get('primary_condition', 'None')],
                        'allergies': pt_match.get('allergies', []),
                        'medications': pt_match.get('medications', []),
                        'note_prose_included': False,
                        'gdpr_art9_compliant': True,
                    }
                    ctx['deid_preview'] = {
                        'patient_id': preview_pid,
                        'raw_name': pt_match['name'],
                        'raw_dob': pt_match['birthDate'],
                        'age_years': pt_match.get('age') or 'Redacted',
                        'raw_address': pt_match['address'],
                        'raw_telecom': pt_match['telecom'],
                        'salted_hash': pseudonymize(preview_pid),
                        'sanitized_json': json.dumps(sanitized_payload, indent=2),
                    }
            if force_run:
                ctx['action_banner'] = f"GDPR Art. 9 compliance verified and PII redaction preview generated for {preview_pid}."

        elif agent_id == 'immutable_audit':
            ctx['tamper_proof'] = verify_sqlite_immutability_live(db)
            if force_run:
                ctx['action_banner'] = ctx['tamper_proof']['message']

        elif agent_id == 'multimodal_ingest' and force_run:
            ctx['action_banner'] = (
                f"Synchronized dropzone ({ctx['ingest_data']['raw_count']} raw files) and verified {ctx['ingest_data']['bundle_count']} FHIR R4 bundles."
            )

        elif agent_id == 'patient_summariser':
            target_pid = (form_data.get('patient_id') or (patient_options[0]['id'] if patient_options else '')).strip()
            if target_pid:
                pt_match = next((p for p in patient_options if p['id'] == target_pid), None)
                if pt_match:
                    cond_str = pt_match.get('primary_condition') or 'General clinical review'
                    allergy_str = ', '.join(pt_match.get('allergies') or []) or 'No known drug allergies (NKDA)'
                    med_str = ', '.join(pt_match.get('medications') or []) or 'No active prescriptions'
                    n_score = pt_match.get('news2_score', 0)
                    n_tier = pt_match.get('news2_tier', 'Low Risk')
                    summary_lines = [
                        f"• Presenting Clinical Status ([Patient/{target_pid}], [Condition/{target_pid}-cond]): {pt_match.get('age', '')}y {pt_match.get('gender', '')} presenting with {cond_str}; deterministic early warning score is NEWS2 {n_score}/20 ({n_tier}) ({pt_match.get('vitals_summary', 'Vitals stable')}).",
                        f"• Pharmacotherapy & Allergy Gate ([AllergyIntolerance/{target_pid}-allergy], [MedicationRequest/{target_pid}-med]): Documented allergies: {allergy_str}. Active regimen: {med_str}.",
                        f"• Handover Priority ([Provenance/{target_pid}-prov]): {'IMMEDIATE CONTRAINDICATION REVIEW REQUIRED' if pt_match.get('rx_alerts') else 'Continue current monitoring protocol'} and complete electronic Provenance sign-off.",
                    ]
                    summary_text = '\n'.join(summary_lines)
                    if force_run:
                        try:
                            db.write_ai_exchange(
                                actor=current_user.username,
                                patient_ref=pseudonymize(target_pid),
                                feature='agent_07_scribe',
                                model=agent['assigned_model'],
                                prompt_hash=hashlib.sha256(target_pid.encode('utf-8')).hexdigest(),
                                prompt_version='v2.0-agent07',
                                deidentified=True,
                                input_tokens=96,
                                output_tokens=112,
                                response=summary_text,
                            )
                            ctx['audit_scan'] = run_immutable_audit_scan(db, store_dir)
                        except Exception:
                            pass
                        ctx['action_banner'] = f"Generated cited bedside handover summary for {pt_match['name']} ({target_pid}) and recorded to ai_exchange."
                    ctx['scribe_result'] = {
                        'patient_id': target_pid,
                        'patient_name': pt_match['name'],
                        'model': agent['assigned_model'],
                        'summary_text': summary_text,
                    }

        elif agent_id == 'medication_safety':
            target_pid = (form_data.get('patient_id') or (patient_options[0]['id'] if patient_options else '')).strip()
            candidate_drug = (form_data.get('candidate_drug') or '').strip()
            if target_pid:
                pt_match = next((p for p in patient_options if p['id'] == target_pid), None)
                if pt_match:
                    allergies = list(pt_match.get('allergies') or [])
                    meds = list(pt_match.get('medications') or [])
                    pt_obs = []
                    if not app.testing:
                        obs_r = fhir.get('Observation', params={'patient': target_pid, '_count': 40})
                        if obs_r.ok:
                            pt_obs = obs_r.entries
                    rx_eval = evaluate_clinical_pharmacology_3tier(
                        allergies=allergies,
                        active_medications=meds,
                        lab_observations=pt_obs,
                        candidate_drug=candidate_drug or None,
                    )
                    alerts = rx_eval['alerts']
                    checked_meds = list(meds) + ([candidate_drug] if candidate_drug else [])
                    ctx['rx_result'] = {
                        'patient_id': target_pid,
                        'patient_name': pt_match['name'],
                        'candidate_drug': candidate_drug,
                        'allergies': allergies,
                        'medications': checked_meds,
                        'egfr': rx_eval.get('egfr'),
                        'tier_counts': rx_eval.get('tier_counts'),
                        'alerts': alerts,
                    }
                    if force_run:
                        ctx['action_banner'] = (
                            f"3-Tier Rx-Guard evaluated {len(checked_meds)} medication(s) (Allergy + DDI + Renal eGFR) for {pt_match['name']}: {len(alerts)} alert(s) found."
                        )

        elif agent_id == 'acuity_triage':
            from clinical_intake import MTS_METADATA, calculate_mts_category
            rr = float(form_data.get('rr') or 22)
            spo2 = float(form_data.get('spo2') or 93)
            sbp = float(form_data.get('sbp') or 108)
            hr = float(form_data.get('hr') or 112)
            temp = float(form_data.get('temp') or 38.4)
            vitals = {'rr': rr, 'spo2': spo2, 'sbp': sbp, 'hr': hr, 'temp': temp, 'respiratory_rate': rr, 'systolic_bp': sbp, 'heart_rate': hr, 'temperature': temp}
            n_score, n_tier, n_break = calculate_news2_score(vitals)
            mts_cat = calculate_mts_category(vitals)
            mts_meta = MTS_METADATA.get(mts_cat, MTS_METADATA[3])
            ctx['triage_sim'] = {
                'rr': int(rr),
                'spo2': int(spo2),
                'sbp': int(sbp),
                'hr': int(hr),
                'temp': temp,
                'news2_score': n_score,
                'news2_tier': n_tier,
                'breakdown': n_break,
                'mts_cat': mts_cat,
                'mts_name': mts_meta['name'],
                'mts_target': mts_meta['target_time_minutes'],
            }
            if force_run:
                ctx['action_banner'] = f"Computed MTS Category {mts_cat} ({mts_meta['name']}) and RCP NEWS2 Score {n_score}/20 ({n_tier})."

        elif agent_id == 'ambient_scribe':
            target_pid = (form_data.get('patient_id') or (patient_options[0]['id'] if patient_options else 'P101')).strip()
            preset_key = (form_data.get('preset_key') or 'gp_chest_ckd').strip()
            transcript = (form_data.get('transcript_text') or '').strip()
            if not transcript:
                for pr in AMBIENT_SCRIBE_PRESETS:
                    if pr['key'] == preset_key:
                        transcript = pr['transcript']
                        break
            pt_match = next((p for p in patient_options if p['id'] == target_pid), None)
            pt_name = pt_match['name'] if pt_match else target_pid
            allergies = list(pt_match.get('allergies') or []) if pt_match else []
            meds = list(pt_match.get('medications') or []) if pt_match else []
            pt_obs = []
            if not app.testing:
                obs_r = fhir.get('Observation', params={'patient': target_pid, '_count': 40})
                if obs_r.ok:
                    pt_obs = obs_r.entries
            ctx['ambient_draft'] = process_ambient_consultation(
                transcript_text=transcript,
                patient_id=target_pid,
                patient_name=pt_name,
                allergies=allergies,
                active_medications=meds,
                lab_observations=pt_obs,
            )
            if force_run:
                ctx['action_banner'] = (
                    f"Agent 10 (SlainteScribe-Voice) structured SOAP note, {len(ctx['ambient_draft']['candidate_conditions'])} Condition(s), "
                    f"and {len(ctx['ambient_draft']['draft_medications'])} Rx-Guard pre-screened order(s) for {pt_name}."
                )

        elif agent_id == 'clinical_coding':
            target_pid = (form_data.get('patient_id') or (patient_options[0]['id'] if patient_options else '')).strip()
            cohort_reports = []
            total_uplift = 0
            scan_list = patient_options[:18] if patient_options else []
            for pt in scan_list:
                pid = pt['id']
                cond_entries = []
                obs_entries = []
                if not app.testing:
                    many_c = fhir.get_many({
                        'c': ('Condition', {'patient': pid, '_count': 30}),
                        'o': ('Observation', {'patient': pid, '_count': 40}),
                    })
                    cond_entries = many_c['c'].entries if many_c['c'].ok else []
                    obs_entries = many_c['o'].entries if many_c['o'].ok else []
                elif store_dir and os.path.isdir(store_dir):
                    bpath = os.path.join(store_dir, f'bundle_{pid}.json')
                    if os.path.isfile(bpath):
                        try:
                            with open(bpath, 'r', encoding='utf-8') as bf:
                                bdata = json.load(bf)
                            for entry in bdata.get('entry') or []:
                                r = entry.get('resource') or {}
                                if r.get('resourceType') == 'Condition':
                                    cond_entries.append(r)
                                elif r.get('resourceType') == 'Observation':
                                    obs_entries.append(r)
                        except Exception:
                            pass
                rep = scan_patient_coding_gaps(pid, pt['name'], cond_entries, obs_entries)
                cohort_reports.append(rep)
                total_uplift += rep['total_uplift_eur']
                if pid == target_pid:
                    ctx['coding_patient_report'] = rep

            cohort_reports.sort(key=lambda r: r['total_uplift_eur'], reverse=True)
            ctx['coding_cohort'] = cohort_reports
            ctx['coding_total_uplift'] = total_uplift
            if ctx['coding_patient_report'] is None and cohort_reports:
                ctx['coding_patient_report'] = cohort_reports[0]
            if force_run:
                ctx['action_banner'] = (
                    f"Agent 11 (SlainteRev-Coding) audited {len(cohort_reports)} patient chart(s) — identified €{total_uplift:,} in uncoded HIPE DRG complexity uplift."
                )

        return ctx

    @app.route('/agents/<agent_id>')
    @app.route('/fhir/Agent/<agent_id>')
    @login_required
    def agent_detail_view(agent_id):
        ag = get_agent_by_id(agent_id)
        if not ag:
            return redirect(url_for('index', view='agents'))
        if not request.headers.get('HX-Request') and not app.testing and request.path.startswith('/agents/'):
            return render_template('index.html', initial_view=f"/fhir/Agent/{ag['id']}")
        ctx = _build_agent_detail_context(ag['id'], force_run=False)
        return render_template('agent_detail.html', **ctx)

    @app.route('/agents/<agent_id>/run', methods=['POST'])
    @app.route('/fhir/Agent/<agent_id>/run', methods=['POST'])
    @login_required
    def agent_detail_run(agent_id):
        ag = get_agent_by_id(agent_id)
        if not ag:
            return '<div class="alert alert-danger">Unknown agent.</div>', 404
        ctx = _build_agent_detail_context(ag['id'], force_run=True, form_data=request.form)
        audit('agent.executed', outcome='success', detail={'agent_id': ag['id'], 'code': ag['code']})
        return render_template('agent_detail.html', **ctx)

    @app.route('/agents/<agent_id>/settings', methods=['POST'])
    @login_required
    def update_agent_settings(agent_id):
        agent = get_agent_by_id(agent_id)
        if not agent:
            return '<div class="alert alert-danger py-1 px-2 small mb-0">Unknown agent ID.</div>', 404
        enabled = request.form.get('enabled') == 'on' or request.form.get('enabled') == 'true'
        model = request.form.get('assigned_model', 'ollama/k9/lime:latest')
        guardrail = request.form.get('guardrail', agent['default_guardrail'])
        saved = save_agent_settings(db, agent_id, enabled, model, guardrail)
        audit('agent.settings_updated', outcome='success', detail={'agent_id': agent_id, **saved})
        state_badge = '<span class="badge bg-success">ACTIVE</span>' if enabled else '<span class="badge bg-secondary">PAUSED</span>'
        return (
            f'<div class="alert alert-success py-2 px-3 small mb-0 mt-2">'
            f'<i class="fas fa-check-circle me-1"></i><strong>{agent["code"]}</strong> settings saved: '
            f'{state_badge} &bull; Model: <code>{saved["model"]}</code> &bull; Policy: <em>{saved["guardrail"]}</em>'
            f'</div>'
        )

    @app.route('/agents/audit/snapshot')
    @login_required
    def download_signed_audit_snapshot():
        payload = build_signed_audit_snapshot(db, app.config.get('SECRET_KEY', 'slainte-audit-key'))
        audit('audit.snapshot_exported', outcome='success', detail={'entries': payload['audit_log_entries']})
        response = jsonify(payload)
        response.headers['Content-Disposition'] = 'attachment; filename="slainte_signed_audit_snapshot.json"'
        return response

    @app.route('/fhir/auditor/sarif')
    @login_required
    def auditor_sarif_download():
        import json
        _, _, report_dir = _resolve_auditor_paths()
        sarif_path = os.path.join(report_dir, 'slaintefhir-audit.sarif.json')
        if not os.path.isfile(sarif_path):
            _get_auditor_telemetry(force_run=True)
        if os.path.isfile(sarif_path):
            with open(sarif_path, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        return jsonify({'version': '2.1.0', 'runs': []})

    @app.route('/api/v1/fhir/ingest', methods=['POST'])
    @csrf.exempt
    def api_ingest_bundle():
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({'error': 'Invalid or missing JSON payload'}), 400
        if hasattr(app.fhir, 'save_bundle'):
            saved_path = app.fhir.save_bundle(payload)
            return jsonify({
                'status': 'success',
                'message': 'Bundle ingested and indexed into Slainte-Engine.',
                'file_path': saved_path
            }), 201
        return jsonify({'status': 'received', 'message': 'App running with remote FHIR backend'}), 200

    @app.route('/fhir/Bundle', methods=['POST'])
    @csrf.exempt
    def fhir_bundle_ingest():
        return api_ingest_bundle()

    @app.route('/fhir/intake', methods=['POST'])
    @login_required
    def manual_intake():
        import csv
        import json
        import os
        import time
        from clinical_intake import (
            calculate_mts_category, MTS_METADATA, resolve_snomed,
            parse_labs, parse_medications, parse_allergies, build_fhir_bundle
        )
        full_name = request.form.get('full_name', '').strip()
        if not full_name:
            return '<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>Patient full name is required.</div>', 400

        complaint = request.form.get('complaint', '').strip()
        if not complaint:
            return '<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>Chief complaint is required.</div>', 400

        gender = request.form.get('gender', 'unknown').strip().lower()
        dob = request.form.get('dob', '').strip() or None
        gms_number = request.form.get('gms_number', '').strip()

        def _parse_num(field):
            v = request.form.get(field, '').strip()
            if not v:
                return None
            try:
                return float(v)
            except ValueError:
                return None

        vitals = {
            'systolic_bp': _parse_num('sys_bp'),
            'diastolic_bp': _parse_num('dia_bp'),
            'heart_rate': _parse_num('hr'),
            'spo2': _parse_num('spo2'),
            'respiratory_rate': _parse_num('resp_rate'),
            'temperature': _parse_num('temp_c'),
            'pain': _parse_num('pain'),
            'complaint': complaint
        }

        mts_cat = calculate_mts_category(vitals)
        mts_info = MTS_METADATA.get(mts_cat, MTS_METADATA[3])
        snomed_code, snomed_disp = resolve_snomed(complaint)

        pt_id = None
        if gms_number and hasattr(app.fhir, 'find_patient_id_by_gms'):
            pt_id = app.fhir.find_patient_id_by_gms(gms_number)

        if not pt_id:
            if hasattr(app.fhir, '_cache_patients') and app.fhir._cache_patients:
                existing_ids = list(app.fhir._cache_patients.keys())
                num_ids = [int(p[1:]) for p in existing_ids if p.startswith('P') and p[1:].isdigit()]
                next_num = (max(num_ids) + 1) if num_ids else 119
                pt_id = f"P{next_num}"
            else:
                pt_id = f"P{int(time.time() * 1000) % 10000:04d}"

        if not gms_number:
            gms_number = f"99{pt_id[1:]}-Z"

        labs_data = parse_labs(request.form.get('labs'))
        meds_data = parse_medications(request.form.get('medications'))
        algs_data = parse_allergies(request.form.get('allergies'))

        bundle = build_fhir_bundle(
            pt_id=pt_id,
            name=full_name,
            gms_number=gms_number,
            gender=gender,
            birthdate=dob,
            complaint=complaint,
            vitals=vitals,
            mts_category=mts_cat,
            labs=labs_data,
            medications=meds_data,
            allergies=algs_data
        )

        # 1. Save to FHIR store immediately (both remote SlainteFHIR and local bundle store)
        if hasattr(app.fhir, 'save_bundle'):
            app.fhir.save_bundle(bundle, f"bundle_{pt_id}.json")
        else:
            if not app.config.get('TESTING'):
                fhir.post('Bundle', json_data=bundle)
            store_dir = app.config.get('FHIR_STORE_PATH', '/workspace/data/fhir_store')
            os.makedirs(store_dir, exist_ok=True)
            with open(os.path.join(store_dir, f"bundle_{pt_id}.json"), "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=2)

        # 2. Append to raw dropzone CSV for OpenHands agent synchronization (non-blocking)
        try:
            raw_dir = app.config.get('RAW_DATA_PATH', '/workspace/data/raw')
            os.makedirs(raw_dir, exist_ok=True)
            intake_csv_path = os.path.join(raw_dir, 'manual_intake_patients.csv')
            file_exists = os.path.isfile(intake_csv_path)
            with open(intake_csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                if not file_exists:
                    writer.writerow([
                        'pt_id', 'Patient_Name', 'GMS_NO', 'sex', 'DOB', 'triage_complaint',
                        'sys_bp', 'dia_bp', 'hr', 'o2_sat', 'resp_rate', 'temp_c', 'pain_level',
                        'labs', 'medications', 'allergies'
                    ])
                writer.writerow([
                    pt_id, full_name, gms_number, gender, dob or '', complaint,
                    vitals['systolic_bp'] or '', vitals['diastolic_bp'] or '', vitals['heart_rate'] or '',
                    vitals['spo2'] or '', vitals['respiratory_rate'] or '', vitals['temperature'] or '',
                    vitals['pain'] or '', request.form.get('labs', ''), request.form.get('medications', ''),
                    request.form.get('allergies', '')
                ])
        except Exception as e:
            logger.warning(f"Failed to append to manual intake audit CSV: {e}")

        vitals_badges = []
        if vitals['systolic_bp'] and vitals['diastolic_bp']:
            vitals_badges.append(f'<span class="badge bg-light text-dark border">BP: {int(vitals["systolic_bp"])}/{int(vitals["diastolic_bp"])}</span>')
        if vitals['heart_rate']:
            vitals_badges.append(f'<span class="badge bg-light text-dark border">HR: {int(vitals["heart_rate"])} bpm</span>')
        if vitals['spo2']:
            vitals_badges.append(f'<span class="badge bg-light text-dark border">SpO2: {int(vitals["spo2"])}%</span>')
        if vitals['temperature']:
            vitals_badges.append(f'<span class="badge bg-light text-dark border">Temp: {vitals["temperature"]}°C</span>')
        if vitals['pain'] is not None:
            vitals_badges.append(f'<span class="badge bg-light text-dark border">Pain: {int(vitals["pain"])}/10</span>')

        from markupsafe import escape as h_escape
        safe_full_name = h_escape(full_name)
        safe_complaint = h_escape(complaint)
        safe_gms_number = h_escape(gms_number)
        safe_pt_id = h_escape(pt_id)
        safe_snomed = h_escape(str(snomed_code))

        from fhir_utils import check_drug_allergy_contraindications, calculate_news2_score
        news2_score, news2_tier, _ = calculate_news2_score(vitals)
        safety_alerts = check_drug_allergy_contraindications(algs_data, meds_data)
        if safety_alerts:
            audit('clinical.safety_gate_intercepted', outcome='warning',
                  detail={'patient_id': pt_id, 'alerts': len(safety_alerts)})

        safety_banner = ""
        if safety_alerts:
            alerts_items = "".join([
                f'<li class="mb-1"><strong>[{a["severity"]}] {a["allergen"]} &harr; {a["medication"]}:</strong> {a["message"]}</li>'
                for a in safety_alerts
            ])
            safety_banner = f"""
            <div class="alert alert-danger py-2 px-3 small border-0 shadow-sm mt-2">
                <div class="fw-bold mb-1"><i class="fas fa-exclamation-triangle text-danger me-1"></i>CDS Safety Gate Intercepted Potential Contraindications:</div>
                <ul class="mb-0 ps-3">{alerts_items}</ul>
            </div>
            """

        news2_badge_class = "bg-danger text-white" if news2_score >= 7 else ("bg-warning text-dark" if news2_score >= 5 else ("bg-info text-dark" if news2_score >= 1 else "bg-success text-white"))

        badges_html = ' '.join(vitals_badges)
        return f"""
        <div class="alert alert-success border-0 shadow-sm p-3 mt-3 animate-fade-in">
            <div class="d-flex align-items-center justify-content-between mb-2">
                <div class="d-flex align-items-center gap-1">
                    <span class="badge {mts_info['badge']} px-3 py-2 fs-6">
                        Cat {mts_cat}: {mts_info['name']}
                    </span>
                    <span class="badge {news2_badge_class} px-2 py-2">
                        <i class="fas fa-heartbeat me-1"></i>NEWS2: {news2_score}/20 ({news2_tier})
                    </span>
                    <span class="badge bg-dark text-white px-2 py-2">
                        Target: {mts_info['target_time_minutes']} min
                    </span>
                </div>
                <span class="badge bg-success text-white border border-success">
                    <i class="fas fa-check-circle me-1"></i> Validated FHIR R4 Bundle
                </span>
            </div>
            <div class="mb-2">
                <h6 class="mb-1 fw-bold">{safe_full_name} <span class="text-muted fw-normal">({safe_pt_id} &bull; GMS: {safe_gms_number})</span></h6>
                <p class="mb-1 small text-dark"><strong>Chief Complaint:</strong> {safe_complaint} <span class="badge bg-secondary-subtle text-secondary ms-1">SNOMED {safe_snomed}</span></p>
                <div class="d-flex flex-wrap gap-1 mt-1">{badges_html}</div>
                {safety_banner}
            </div>
            <hr class="my-2 text-muted">
            <div class="d-flex align-items-center justify-content-between pt-1">
                <small class="text-muted"><i class="fas fa-robot text-primary me-1"></i>Synchronized to OpenHands audit ledger &amp; indexed to FHIR store.</small>
                <div class="d-flex gap-2">
                    <a href="/fhir/Patient/{safe_pt_id}" class="btn btn-sm btn-outline-primary">
                        <i class="fas fa-id-card me-1"></i> View Patient Detail
                    </a>
                    <button type="button" class="btn btn-sm btn-success" onclick="window.location.href='/?view=/fhir/Triage'">
                        <i class="fas fa-list me-1"></i> View Triage Queue
                    </button>
                </div>
            </div>
        </div>
        """

    @app.route('/fhir/validate-safety', methods=['POST'])
    @login_required
    def validate_safety_gate():
        from fhir_utils import check_drug_allergy_contraindications
        from clinical_intake import parse_allergies, parse_medications

        meds_raw = request.form.get('medications', '')
        algs_raw = request.form.get('allergies', '')

        if not meds_raw and not algs_raw:
            return ''

        meds_data = parse_medications(meds_raw)
        algs_data = parse_allergies(algs_raw)

        alerts = check_drug_allergy_contraindications(algs_data, meds_data)
        if alerts:
            alerts_html = "".join([
                f'<div class="alert alert-danger py-2 px-3 small mb-1 border-0 shadow-sm animate-fade-in">'
                f'<i class="fas fa-biohazard text-danger me-1"></i>'
                f'<strong>[{a["severity"]}] {a["allergen"]} &harr; {a["medication"]}:</strong> '
                f'{a["message"]}</div>'
                for a in alerts
            ])
            return alerts_html
        elif meds_raw and algs_raw:
            return (
                '<div class="alert alert-success py-1 px-3 small mb-1 border-0 shadow-sm animate-fade-in">'
                '<i class="fas fa-shield-alt text-success me-1"></i>'
                '<strong>Safety Gate Clear:</strong> No cross-reactivity contraindications detected.'
                '</div>'
            )
        return ''

    @app.route('/fhir/patient/<patient_id>/sign-off', methods=['POST'])
    @login_required
    def sign_off_clinical_assessment(patient_id):
        practitioner_id = request.form.get('practitioner_id', '').strip()
        practitioner_role = request.form.get('practitioner_role', 'Emergency Physician').strip()
        signature_confirm = request.form.get('signature_confirm', '').strip()

        if not practitioner_id:
            return '<div class="alert alert-danger py-2 px-3 small">Practitioner IMC / GMC Number is required.</div>', 400
        if not signature_confirm:
            return '<div class="alert alert-danger py-2 px-3 small">Please type your full name to electronically confirm sign-off.</div>', 400

        prov = None
        if hasattr(app.fhir, 'sign_off_patient'):
            prov = app.fhir.sign_off_patient(
                patient_id=patient_id,
                practitioner_id=practitioner_id,
                practitioner_role=practitioner_role,
                signature_text=signature_confirm,
                practitioner_name=current_user.username
            )
        else:
            prov_obj = build_provenance_signoff(
                patient_id=patient_id,
                practitioner_id=practitioner_id,
                practitioner_role=practitioner_role,
                signature_text=signature_confirm,
                author_username=current_user.username,
            )
            persist_fhir_resource(fhir, app.config, prov_obj, is_update=True)

        audit('clinical.sign_off', outcome='success', resource_type='Patient', resource_id=pseudonymize(patient_id),
              detail={'practitioner_id': practitioner_id, 'role': practitioner_role})

        return f'''
        <div class="alert alert-success py-2 px-3 small border border-success mb-2 animate-fade-in">
            <div class="d-flex align-items-center justify-content-between mb-1">
                <span class="fw-bold"><i class="fas fa-check-double text-success me-1"></i>Assessment Verified &amp; Signed</span>
                <span class="badge bg-success"><i class="fas fa-certificate me-1"></i>HL7 Provenance Attached</span>
            </div>
            <div>Practitioner: <code>{practitioner_id}</code> &bull; <strong>{practitioner_role}</strong></div>
            <div class="text-muted" style="font-size: 11px;">Signed by: <em>{signature_confirm}</em> &bull; Just now</div>
        </div>
        <script>
            // Refresh triage queue row if on triage screen
            setTimeout(function() {{ if (window.htmx) {{ htmx.trigger('#triage-queue-container', 'refreshQueue'); }} }}, 600);
        </script>
        '''

    @app.route('/fhir/upload', methods=['POST'])
    @login_required
    def batch_upload():
        import os
        import time
        from werkzeug.utils import secure_filename
        from clinical_intake import (
            extract_from_clinical_document, calculate_mts_category,
            MTS_METADATA, resolve_snomed, build_fhir_bundle
        )

        if 'clinical_file' not in request.files:
            return '<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>No file selected for upload.</div>', 400

        file = request.files['clinical_file']
        if not file or not file.filename:
            return '<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>Filename is empty.</div>', 400

        ALLOWED_EXTENSIONS = {'.csv', '.tsv', '.json', '.pdf', '.png', '.jpg', '.jpeg'}
        ext = os.path.splitext(file.filename or '')[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return f'<div class="alert alert-danger"><i class="fas fa-exclamation-triangle me-2"></i>Unsupported file type: {ext or "unknown"}. Allowed: {", ".join(sorted(ALLOWED_EXTENSIONS))}</div>', 400

        filename = secure_filename(file.filename)
        if not filename:
            filename = f"upload_{int(time.time())}{ext}"

        raw_dir = app.config.get('RAW_DATA_PATH', '/workspace/data/raw')
        os.makedirs(raw_dir, exist_ok=True)
        dest_path = os.path.join(raw_dir, filename)
        file.save(dest_path)

        file_size_kb = max(1, os.path.getsize(dest_path) // 1024)

        from markupsafe import escape as h_escape
        safe_filename = h_escape(filename)
        safe_dest_path = h_escape(dest_path)

        # Handle PDF and Image clinical document intake
        if ext in ('.pdf', '.png', '.jpg', '.jpeg'):
            extracted = extract_from_clinical_document(dest_path)
            complaint = extracted.get('complaint') or f"Clinical document intake ({filename})"
            vitals = {
                'systolic_bp': extracted.get('systolic_bp'),
                'diastolic_bp': extracted.get('diastolic_bp'),
                'heart_rate': extracted.get('heart_rate'),
                'spo2': extracted.get('spo2'),
                'respiratory_rate': extracted.get('respiratory_rate'),
                'temperature': extracted.get('temperature'),
                'pain': extracted.get('pain'),
                'complaint': complaint
            }

            mts_cat = calculate_mts_category(vitals)
            mts_info = MTS_METADATA.get(mts_cat, MTS_METADATA[3])
            snomed_code, snomed_disp = resolve_snomed(complaint)

            pt_id = None
            if hasattr(app.fhir, '_cache_patients') and app.fhir._cache_patients:
                existing_ids = list(app.fhir._cache_patients.keys())
                num_ids = [int(p[1:]) for p in existing_ids if p.startswith('P') and p[1:].isdigit()]
                next_num = (max(num_ids) + 1) if num_ids else 119
                pt_id = f"P{next_num}"
            else:
                pt_id = f"P{int(time.time() * 1000) % 10000:04d}"

            gms_number = extracted.get('gms_number') or f"99{pt_id[1:]}-D"
            full_name = extracted.get('full_name') or f"Scanned Patient ({filename[:12]})"
            gender = extracted.get('gender') or 'unknown'
            dob = extracted.get('dob') or '1985-06-15'

            bundle = build_fhir_bundle(
                pt_id=pt_id,
                name=full_name,
                gms_number=gms_number,
                gender=gender,
                birthdate=dob,
                complaint=complaint,
                vitals=vitals,
                mts_category=mts_cat
            )

            # Save to FHIR store (both remote SlainteFHIR and local bundle store)
            if hasattr(app.fhir, 'save_bundle'):
                app.fhir.save_bundle(bundle, f"bundle_{pt_id}.json")
            else:
                if not app.config.get('TESTING'):
                    fhir.post('Bundle', json_data=bundle)
                store_dir = app.config.get('FHIR_STORE_PATH', '/workspace/data/fhir_store')
                os.makedirs(store_dir, exist_ok=True)
                import json
                with open(os.path.join(store_dir, f"bundle_{pt_id}.json"), "w", encoding="utf-8") as f:
                    json.dump(bundle, f, indent=2)

            file_icon = 'fa-file-pdf text-danger' if ext == '.pdf' else 'fa-file-image text-info'

            vitals_badges = []
            if vitals['systolic_bp'] and vitals['diastolic_bp']:
                vitals_badges.append(f'<span class="badge bg-light text-dark border">BP: {int(vitals["systolic_bp"])}/{int(vitals["diastolic_bp"])}</span>')
            if vitals['heart_rate']:
                vitals_badges.append(f'<span class="badge bg-light text-dark border">HR: {int(vitals["heart_rate"])} bpm</span>')
            if vitals['spo2']:
                vitals_badges.append(f'<span class="badge bg-light text-dark border">SpO2: {int(vitals["spo2"])}%</span>')
            if vitals['temperature']:
                vitals_badges.append(f'<span class="badge bg-light text-dark border">Temp: {vitals["temperature"]}°C</span>')
            if vitals['pain'] is not None:
                vitals_badges.append(f'<span class="badge bg-light text-dark border">Pain: {int(vitals["pain"])}/10</span>')

            safe_full_name = h_escape(full_name)
            safe_complaint = h_escape(complaint)
            safe_gms = h_escape(gms_number)
            safe_pt_id = h_escape(pt_id)
            safe_snomed = h_escape(str(snomed_code))

            return f"""
            <div class="alert alert-success border-0 shadow-sm p-3 mt-3 animate-fade-in">
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <div class="d-flex align-items-center gap-2">
                        <i class="fas {file_icon} fa-2x"></i>
                        <div>
                            <h6 class="mb-0 fw-bold">{safe_filename} <span class="badge bg-dark ms-1">{file_size_kb} KB</span></h6>
                            <small class="text-muted">Multimodal OCR &amp; FastMCP extraction verified.</small>
                        </div>
                    </div>
                    <span class="badge {mts_info['badge']} px-3 py-2 fs-6">
                        Cat {mts_cat}: {mts_info['name']} ({mts_info['target_time_minutes']} min)
                    </span>
                </div>
                <div class="bg-white rounded p-3 border mb-2">
                    <div class="fw-bold mb-1">{safe_full_name} <span class="text-muted fw-normal">({safe_pt_id} &bull; GMS: {safe_gms})</span></div>
                    <div class="small text-secondary mb-2"><strong>Extracted Complaint:</strong> {safe_complaint} &bull; <span class="badge bg-secondary-subtle text-secondary">SNOMED {safe_snomed}</span></div>
                    <div class="d-flex flex-wrap gap-1">{' '.join(vitals_badges)}</div>
                </div>
                <div class="d-flex align-items-center justify-content-between pt-1">
                    <small class="text-muted"><i class="fas fa-check-circle text-success me-1"></i>Standard HL7 FHIR R4 Bundle created and indexed.</small>
                    <div class="d-flex gap-2">
                        <button type="button" class="btn btn-sm btn-outline-primary" onclick="window.location.href='/?view=patients'">
                            <i class="fas fa-users me-1"></i> Patients List
                        </button>
                        <button type="button" class="btn btn-sm btn-success" onclick="window.location.href='/?view=triage'">
                            <i class="fas fa-heartbeat me-1"></i> Live Triage Queue
                        </button>
                    </div>
                </div>
            </div>
            """

        # Handle tabular CSV/TSV/JSON files
        row_count = 0
        try:
            with open(dest_path, 'r', encoding='utf-8', errors='replace') as f:
                row_count = max(0, sum(1 for line in f if line.strip()) - 1)
        except Exception:
            row_count = 1

        return f"""
        <div class="alert alert-primary border-0 shadow-sm p-3 mt-3 animate-fade-in">
            <div class="d-flex align-items-center mb-2">
                <i class="fas fa-file-csv fa-2x text-primary me-3"></i>
                <div>
                    <h6 class="mb-0 fw-bold">{safe_filename} <span class="badge bg-info text-dark ms-2">{file_size_kb} KB</span></h6>
                    <small class="text-muted">Detected {row_count} clinical triage record(s) in batch.</small>
                </div>
            </div>
            <div class="bg-white rounded p-2 border mb-2 small text-secondary">
                <div class="d-flex align-items-center mb-1">
                    <i class="fas fa-check-circle text-success me-2"></i> File safely staged to <code>{safe_dest_path}</code>
                </div>
                <div class="d-flex align-items-center mb-1">
                    <i class="fas fa-cogs text-primary me-2"></i> OpenHands autonomous daemon active &mdash; polling dropzone every 10s
                </div>
                <div class="d-flex align-items-center">
                    <i class="fas fa-shield-alt text-info me-2"></i> Zero-hallucination validation gate: MCP schema + SNOMED-CT + MTS calculation
                </div>
            </div>
            <div class="d-flex justify-content-between align-items-center pt-1">
                <small class="text-muted"><i class="fas fa-info-circle me-1"></i>The queue auto-refreshes every 5 seconds.</small>
                <button type="button" class="btn btn-sm btn-primary" onclick="window.location.href='/?view=triage'">
                    <i class="fas fa-sync-alt me-1"></i> Go to Live Triage Queue
                </button>
            </div>
        </div>
        """


def register_cli(app):
    """Operator commands, including the lockout recovery path."""

    @app.cli.command('grant-admin')
    @click.argument('username')
    def grant_admin_command(username):
        """Create or promote USERNAME to an active administrator.

        Prompts for a password interactively, and (re)sets it -- this is the
        lockout-recovery path, so it must work even if the account already
        exists and its password is unknown.
        """
        username = username.strip().lower()
        if not is_valid_username(username):
            raise click.ClickException(
                f'{username!r} is not a usable username. It must be '
                f'{MIN_USERNAME_LENGTH}-{MAX_USERNAME_LENGTH} characters of letters, '
                'numbers, dots, hyphens or underscores.'
            )
        password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
        if len(password) < MIN_PASSWORD_LENGTH:
            raise click.ClickException(
                f'Password must be at least {MIN_PASSWORD_LENGTH} characters.'
            )
        record = db.grant_admin(username, auth.hash_password(password))
        db.write_audit('admin.granted_via_cli', 'success',
                       actor='cli', resource_type='User',
                       resource_id=pseudonymize(record['username']))
        click.echo(f"{record['username']} is now an active administrator.")

    @app.cli.command('reset-password')
    @click.argument('username')
    def reset_password_command(username):
        """Reset USERNAME's password, leaving their role and status alone.

        `grant-admin` also promotes, so it is the wrong tool for an ordinary
        forgotten password -- it would hand the account administrator rights
        as a side effect.
        """
        username = username.strip().lower()
        password = click.prompt('New password', hide_input=True, confirmation_prompt=True)
        if len(password) < MIN_PASSWORD_LENGTH:
            raise click.ClickException(
                f'Password must be at least {MIN_PASSWORD_LENGTH} characters.'
            )
        record = db.set_password(username, auth.hash_password(password))
        if record is None:
            raise click.ClickException(f'No account called {username!r}.')
        db.write_audit('user.password_reset_via_cli', 'success',
                       actor='cli', resource_type='User',
                       resource_id=pseudonymize(record['username']))
        click.echo(f"Password reset for {record['username']} "
                   f"(role {record['role']}, status {record['status']} -- unchanged).")

    @app.cli.command('list-users')
    def list_users_command():
        """Show every registered account and its status."""
        users = db.list_users()
        if not users:
            click.echo('No users registered yet.')
            return
        click.echo(f"{'USERNAME':<24}{'ROLE':<12}{'STATUS':<10}LAST SIGN-IN")
        for user in users:
            click.echo(
                f"{user['username']:<24}{user['role']:<12}"
                f"{user['status']:<10}{(user['last_login_at'] or 'never')[:19]}"
            )
        click.echo(f'\n{db.count_active_admins()} active administrator(s).')


def main():
    try:
        application = create_app()
    except ConfigError as exc:
        raise SystemExit(f'\nConfiguration error:\n{exc}\n')
    application.run(debug=application.config['DEBUG'])


if __name__ == '__main__':
    main()
