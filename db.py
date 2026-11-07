"""SQLite-backed user store and audit log.

The app previously had no user store at all -- `User.get()` fabricated a user
from whatever ID it was handed, so proving control of any wallet granted access
to every patient record. This module gives identity somewhere to live and makes
access reviewable after the fact. Authentication has since moved from wallet
signatures to username/password, but the store and its pending/active/disabled
approval model are unchanged -- only the identity column and how it's proven
are different.

The audit log is append-only, enforced by triggers rather than convention: even
a bug or a direct sqlite3 session cannot rewrite history.
"""
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone, timedelta

from flask import current_app, g
from werkzeug.security import generate_password_hash

logger = logging.getLogger(__name__)

ROLE_ADMIN = 'admin'
ROLE_CLINICIAN = 'clinician'
ROLE_VIEWER = 'viewer'
ROLES = (ROLE_ADMIN, ROLE_CLINICIAN, ROLE_VIEWER)

# Phase 11.5: Granular Clinical Separation-of-Duties Specialty Roles
CLINICAL_ROLE_GENERAL = 'general_clinician'
CLINICAL_ROLE_PRESCRIBER = 'prescriber'
CLINICAL_ROLE_PHARMACIST = 'pharmacist'
CLINICAL_ROLE_TRIAGE_NURSE = 'triage_nurse'
CLINICAL_ROLE_AUDITOR = 'auditor'
CLINICAL_ROLE_ADMIN = 'admin'
CLINICAL_ROLES = (
    CLINICAL_ROLE_GENERAL,
    CLINICAL_ROLE_PRESCRIBER,
    CLINICAL_ROLE_PHARMACIST,
    CLINICAL_ROLE_TRIAGE_NURSE,
    CLINICAL_ROLE_AUDITOR,
    CLINICAL_ROLE_ADMIN,
)

CLINICAL_ROLE_LABELS = {
    CLINICAL_ROLE_GENERAL: 'General Clinician (Full Chart)',
    CLINICAL_ROLE_PRESCRIBER: 'Physician / Prescriber (IMC)',
    CLINICAL_ROLE_PHARMACIST: 'Supervising Pharmacist (PSI)',
    CLINICAL_ROLE_TRIAGE_NURSE: 'ED / EMS Triage Nurse (NMBI)',
    CLINICAL_ROLE_AUDITOR: 'Compliance / HIQA Auditor (Read-Only)',
    CLINICAL_ROLE_ADMIN: 'Medical Director / Platform Admin',
}

STATUS_PENDING = 'pending'
STATUS_ACTIVE = 'active'
STATUS_DISABLED = 'disabled'

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username               TEXT PRIMARY KEY,
    password_hash          TEXT NOT NULL,
    display_name           TEXT,
    role                   TEXT NOT NULL DEFAULT 'viewer',
    clinical_role          TEXT NOT NULL DEFAULT 'general_clinician',
    registration_id        TEXT DEFAULT '',
    status                 TEXT NOT NULL DEFAULT 'pending',
    created_at             TEXT NOT NULL,
    last_login_at          TEXT,
    failed_login_attempts  INTEGER NOT NULL DEFAULT 0,
    locked_until           TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at   TEXT NOT NULL,
    actor         TEXT,
    action        TEXT NOT NULL,
    resource_type TEXT,
    resource_id   TEXT,
    outcome       TEXT NOT NULL,
    remote_addr   TEXT,
    user_agent    TEXT,
    detail        TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_occurred_at ON audit_log(occurred_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor       ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_resource    ON audit_log(resource_type, resource_id);

-- The audit trail is evidence. Make it structurally impossible to edit.
CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;

-- Every exchange with a model, kept so a bad answer can be investigated after
-- the fact: which patient, which prompt, which model, what it said. Without
-- this a clinician reporting "the assistant told me the wrong thing" leaves
-- nothing to examine. Separate from audit_log because the columns are
-- different and the retention decision will be too.
CREATE TABLE IF NOT EXISTS ai_exchange (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at   TEXT NOT NULL,
    actor         TEXT NOT NULL,
    patient_ref   TEXT NOT NULL,
    feature       TEXT NOT NULL,
    model         TEXT NOT NULL,
    prompt_hash   TEXT NOT NULL,
    prompt_version TEXT,
    deidentified  INTEGER NOT NULL DEFAULT 0,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    response      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_exchange_occurred_at ON ai_exchange(occurred_at);
CREATE INDEX IF NOT EXISTS idx_ai_exchange_actor       ON ai_exchange(actor);
CREATE INDEX IF NOT EXISTS idx_ai_exchange_patient     ON ai_exchange(patient_ref);

CREATE TRIGGER IF NOT EXISTS ai_exchange_no_update
BEFORE UPDATE ON ai_exchange
BEGIN
    SELECT RAISE(ABORT, 'ai_exchange is append-only');
END;

CREATE TRIGGER IF NOT EXISTS ai_exchange_no_delete
BEFORE DELETE ON ai_exchange
BEGIN
    SELECT RAISE(ABORT, 'ai_exchange is append-only');
END;

CREATE TABLE IF NOT EXISTS system_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS break_glass_grants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at     TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    actor           TEXT NOT NULL,
    clinical_role   TEXT NOT NULL,
    patient_id      TEXT NOT NULL,
    emergency_type  TEXT NOT NULL,
    justification   TEXT NOT NULL,
    remote_addr     TEXT,
    siem_dispatched INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_break_glass_actor   ON break_glass_grants(actor, patient_id);
CREATE INDEX IF NOT EXISTS idx_break_glass_patient ON break_glass_grants(patient_id);

CREATE TRIGGER IF NOT EXISTS break_glass_no_update
BEFORE UPDATE ON break_glass_grants
BEGIN
    SELECT RAISE(ABORT, 'break_glass_grants is append-only');
END;

CREATE TRIGGER IF NOT EXISTS break_glass_no_delete
BEFORE DELETE ON break_glass_grants
BEGIN
    SELECT RAISE(ABORT, 'break_glass_grants is append-only');
END;
"""


def _utcnow():
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    """Per-request SQLite connection, created on first use."""
    if 'db' not in g:
        path = current_app.config['DATABASE_PATH']
        if path != ':memory:':
            os.makedirs(os.path.dirname(path), exist_ok=True)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('PRAGMA journal_mode = WAL')
        g.db = connection
    return g.db


def close_connection(_exception=None):
    connection = g.pop('db', None)
    if connection is not None:
        connection.close()


def _retire_wallet_era_users_table(connection):
    """Rename a users table left over from the wallet-auth era.

    That schema keyed users on wallet_address with no password_hash column.
    `CREATE TABLE IF NOT EXISTS` silently keeps it, after which every seed
    INSERT and login query crashes on the missing username column. Wallet
    identities cannot be carried into password auth (there is no password to
    migrate), so the old table is preserved under a backup name for the
    operator and a fresh one is created.
    """
    columns = {
        row['name']
        for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    if not columns or 'username' in columns:
        return
    backup_name = f"users_wallet_era_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    connection.execute(f'ALTER TABLE users RENAME TO {backup_name}')
    connection.commit()
    logger.warning(
        'Found a users table from the wallet-auth era; renamed it to %s. '
        'Accounts must be re-created (passwords cannot be derived from '
        'wallet identities).', backup_name,
    )


def init_db(app):
    """Create the schema and seed the bootstrap administrator."""
    with app.app_context():
        connection = get_connection()
        _retire_wallet_era_users_table(connection)
        connection.executescript(SCHEMA)
        connection.commit()

        # Migrate existing users table if lockout / clinical RBAC columns are missing
        user_cols = {
            row['name']
            for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if 'failed_login_attempts' not in user_cols:
            connection.execute('ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0')
        if 'locked_until' not in user_cols:
            connection.execute('ALTER TABLE users ADD COLUMN locked_until TEXT')
        if 'clinical_role' not in user_cols:
            connection.execute("ALTER TABLE users ADD COLUMN clinical_role TEXT NOT NULL DEFAULT 'general_clinician'")
        if 'registration_id' not in user_cols:
            connection.execute("ALTER TABLE users ADD COLUMN registration_id TEXT DEFAULT ''")
        connection.commit()

        # Ensure system_settings table exists
        connection.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key        TEXT PRIMARY KEY,
                value      TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        connection.commit()

        # Seed initial backend configuration if not present
        row = connection.execute("SELECT value FROM system_settings WHERE key = 'backend_url'").fetchone()
        if not row:
            initial_url = app.config.get('FHIR_SERVER_URL', 'http://slainte-fhir:8082/fhir/r4')
            initial_profile = 'slainte_fhir' if '8082' in initial_url else 'custom'
            connection.execute(
                "INSERT OR REPLACE INTO system_settings (key, value, updated_at) VALUES ('backend_profile', ?, ?)",
                (initial_profile, _utcnow())
            )
            connection.execute(
                "INSERT OR REPLACE INTO system_settings (key, value, updated_at) VALUES ('backend_url', ?, ?)",
                (initial_url, _utcnow())
            )
            connection.commit()

        username = app.config.get('INITIAL_ADMIN_USERNAME')
        password = app.config.get('INITIAL_ADMIN_PASSWORD')
        if username and password:  # already validated by config._resolve_initial_admin
            existing = get_user(username)
            if existing is None:
                connection.execute(
                    'INSERT INTO users'
                    ' (username, password_hash, display_name, role, status, created_at)'
                    ' VALUES (?, ?, ?, ?, ?, ?)',
                    (username, generate_password_hash(password), 'Initial administrator',
                     ROLE_ADMIN, STATUS_ACTIVE, _utcnow()),
                )
                connection.commit()
                logger.info('Seeded initial administrator account')
            elif existing['status'] != STATUS_ACTIVE or existing['role'] != ROLE_ADMIN:
                connection.execute(
                    'UPDATE users SET role = ?, status = ?, password_hash = ?'
                    ' WHERE username = ?',
                    (ROLE_ADMIN, STATUS_ACTIVE, generate_password_hash(password),
                     username),
                )
                connection.commit()
                logger.info(
                    'Synchronized administrator credential to configured INITIAL_ADMIN_PASSWORD.'
                )
        close_connection()


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------

def get_user(username):
    if not username:
        return None
    row = get_connection().execute(
        'SELECT * FROM users WHERE username = ?',
        (username.strip().lower(),),
    ).fetchone()
    return dict(row) if row else None


def register_pending_user(username, password_hash, display_name=None):
    """Record a first-time registration as pending approval.

    Registering is deliberately not the same as granting access -- a new row
    lands as `pending` and cannot sign in until an administrator activates it.
    """
    username = username.strip().lower()
    connection = get_connection()
    connection.execute(
        'INSERT OR IGNORE INTO users'
        ' (username, password_hash, display_name, role, status, created_at)'
        ' VALUES (?, ?, ?, ?, ?, ?)',
        (username, password_hash, display_name, ROLE_VIEWER, STATUS_PENDING, _utcnow()),
    )
    connection.commit()
    return get_user(username)


def record_login(username):
    connection = get_connection()
    connection.execute(
        'UPDATE users SET last_login_at = ?, failed_login_attempts = 0, locked_until = NULL WHERE username = ?',
        (_utcnow(), username.strip().lower()),
    )
    connection.commit()


def is_account_locked(username):
    """Check if the account is temporarily locked due to failed login attempts."""
    user = get_user(username)
    if not user:
        return False, None
    locked_until_str = user.get('locked_until')
    if not locked_until_str:
        return False, None
    try:
        locked_until_dt = datetime.fromisoformat(locked_until_str)
        if datetime.now(timezone.utc) < locked_until_dt:
            return True, locked_until_str
        else:
            # Lockout expired, clear the lock
            reset_failed_logins(username)
            return False, None
    except (ValueError, TypeError):
        return False, None


def record_failed_login(username, max_attempts=5, lockout_minutes=15):
    """Increment failed login attempts for a user. Lock if max_attempts reached.

    Returns (attempts, locked_until_iso_or_none).
    """
    user = get_user(username)
    if not user:
        return 0, None
    attempts = (user.get('failed_login_attempts') or 0) + 1
    locked_until = None
    if attempts >= max_attempts:
        locked_dt = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
        locked_until = locked_dt.isoformat()

    connection = get_connection()
    connection.execute(
        'UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE username = ?',
        (attempts, locked_until, username.strip().lower()),
    )
    connection.commit()
    return attempts, locked_until


def reset_failed_logins(username):
    """Reset failed attempts and unlock the account."""
    connection = get_connection()
    connection.execute(
        'UPDATE users SET failed_login_attempts = 0, locked_until = NULL WHERE username = ?',
        (username.strip().lower(),),
    )
    connection.commit()


def set_user_status(username, status):
    if status not in (STATUS_PENDING, STATUS_ACTIVE, STATUS_DISABLED):
        raise ValueError(f'Unknown status: {status}')
    connection = get_connection()
    connection.execute(
        'UPDATE users SET status = ? WHERE username = ?',
        (status, username.strip().lower()),
    )
    connection.commit()


def set_user_role(username, role):
    if role not in ROLES:
        raise ValueError(f'Unknown role: {role}')
    connection = get_connection()
    connection.execute(
        'UPDATE users SET role = ? WHERE username = ?',
        (role, username.strip().lower()),
    )
    connection.commit()


def set_user_clinical_role(username, clinical_role, registration_id=None):
    if clinical_role not in CLINICAL_ROLES:
        raise ValueError(f'Unknown clinical_role: {clinical_role}')
    connection = get_connection()
    if registration_id is not None:
        connection.execute(
            'UPDATE users SET clinical_role = ?, registration_id = ? WHERE username = ?',
            (clinical_role, registration_id.strip()[:64], username.strip().lower()),
        )
    else:
        connection.execute(
            'UPDATE users SET clinical_role = ? WHERE username = ?',
            (clinical_role, username.strip().lower()),
        )
    connection.commit()


def list_users():
    rows = get_connection().execute(
        'SELECT * FROM users ORDER BY created_at DESC'
    ).fetchall()
    return [dict(row) for row in rows]


def count_active_admins():
    """How many accounts can actually administer the system right now."""
    row = get_connection().execute(
        'SELECT COUNT(*) AS n FROM users WHERE role = ? AND status = ?',
        (ROLE_ADMIN, STATUS_ACTIVE),
    ).fetchone()
    return row['n'] if row else 0


def set_password(username, password_hash):
    """Reset one account's credential, leaving role and status untouched.

    Distinct from `grant_admin`, which also promotes: using that to reset a
    clinician's forgotten password would silently make them an administrator.
    Returns the updated user, or None if no such account exists.
    """
    username = username.strip().lower()
    connection = get_connection()
    cursor = connection.execute(
        'UPDATE users SET password_hash = ? WHERE username = ?',
        (password_hash, username),
    )
    connection.commit()
    return get_user(username) if cursor.rowcount else None


def grant_admin(username, password_hash):
    """Create or promote a user to an active administrator, (re)setting
    their password.

    The recovery path when nobody can sign in -- reachable from the CLI
    without hand-editing the database.
    """
    username = username.strip().lower()
    connection = get_connection()
    connection.execute(
        'INSERT INTO users (username, password_hash, display_name, role, status, created_at)'
        ' VALUES (?, ?, ?, ?, ?, ?)'
        ' ON CONFLICT(username) DO UPDATE SET'
        ' password_hash = excluded.password_hash, role = excluded.role,'
        ' status = excluded.status',
        (username, password_hash, 'Administrator', ROLE_ADMIN, STATUS_ACTIVE, _utcnow()),
    )
    connection.commit()
    return get_user(username)


# --------------------------------------------------------------------------
# Audit log
# --------------------------------------------------------------------------

def write_audit(action, outcome, actor=None, resource_type=None, resource_id=None,
                remote_addr=None, user_agent=None, detail=None):
    """Append one entry to the audit trail.

    Auditing must never take the request down with it, so a failure here is
    logged and swallowed rather than raised.
    """
    try:
        connection = get_connection()
        connection.execute(
            'INSERT INTO audit_log'
            ' (occurred_at, actor, action, resource_type, resource_id, outcome,'
            '  remote_addr, user_agent, detail)'
            ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                _utcnow(), actor, action, resource_type, resource_id, outcome,
                remote_addr, (user_agent or '')[:300],
                json.dumps(detail) if detail is not None else None,
            ),
        )
        connection.commit()
    except sqlite3.Error:
        logger.exception('Failed to write audit entry for action=%s', action)


def write_ai_exchange(actor, patient_ref, feature, model, prompt_hash, response,
                      prompt_version=None, deidentified=False,
                      input_tokens=None, output_tokens=None):
    """Append one model exchange to the review trail.

    `patient_ref` must already be pseudonymised by the caller -- this table is
    read by whoever is investigating a complaint, which is not the same
    audience as the record itself.

    Like `write_audit`, a failure here is logged rather than raised: losing the
    trail is bad, but taking a clinician's screen down because a log write
    failed is worse. Returns the new row id, or None if it could not be
    written, so a caller that wants to react has something to check.
    """
    try:
        connection = get_connection()
        cursor = connection.execute(
            'INSERT INTO ai_exchange'
            ' (occurred_at, actor, patient_ref, feature, model, prompt_hash,'
            '  prompt_version, deidentified, input_tokens, output_tokens, response)'
            ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                _utcnow(), actor, patient_ref, feature, model, prompt_hash,
                prompt_version, 1 if deidentified else 0,
                input_tokens, output_tokens, response,
            ),
        )
        connection.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        logger.exception('Failed to record AI exchange for feature=%s', feature)
        return None


def read_ai_exchange(limit=100, actor=None, patient_ref=None, feature=None):
    query = 'SELECT * FROM ai_exchange'
    clauses, params = [], []
    if actor:
        clauses.append('actor = ?')
        params.append(actor)
    if patient_ref:
        clauses.append('patient_ref = ?')
        params.append(patient_ref)
    if feature:
        clauses.append('feature = ?')
        params.append(feature)
    if clauses:
        query += ' WHERE ' + ' AND '.join(clauses)
    query += ' ORDER BY id DESC LIMIT ?'
    params.append(limit)

    rows = get_connection().execute(query, params).fetchall()
    return [dict(row) for row in rows]


def read_audit(limit=100, actor=None, resource_id=None):
    query = 'SELECT * FROM audit_log'
    clauses, params = [], []
    if actor:
        clauses.append('actor = ?')
        params.append(actor)
    if resource_id:
        clauses.append('resource_id = ?')
        params.append(resource_id)
    if clauses:
        query += ' WHERE ' + ' AND '.join(clauses)
    query += ' ORDER BY id DESC LIMIT ?'
    params.append(limit)

    rows = get_connection().execute(query, params).fetchall()
    return [dict(row) for row in rows]


read_audit_log = read_audit


# --------------------------------------------------------------------------
# Break-the-Glass Emergency Access Grants (GDPR Art. 9(2)(c) Vital Interests)
# --------------------------------------------------------------------------

def write_break_glass_grant(actor, clinical_role, patient_id, emergency_type,
                            justification, remote_addr=None, duration_minutes=60,
                            siem_dispatched=False):
    """Append an immutable 60-minute emergency access grant to break_glass_grants."""
    now_dt = datetime.now(timezone.utc)
    exp_dt = now_dt + timedelta(minutes=duration_minutes)
    connection = get_connection()
    cursor = connection.execute(
        'INSERT INTO break_glass_grants'
        ' (occurred_at, expires_at, actor, clinical_role, patient_id,'
        '  emergency_type, justification, remote_addr, siem_dispatched)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (
            now_dt.isoformat(),
            exp_dt.isoformat(),
            (actor or 'unknown').strip().lower(),
            (clinical_role or CLINICAL_ROLE_GENERAL).strip(),
            (patient_id or '').strip(),
            (emergency_type or 'Clinical Emergency').strip()[:120],
            (justification or '').strip()[:500],
            remote_addr,
            1 if siem_dispatched else 0,
        ),
    )
    connection.commit()
    return {
        'id': cursor.lastrowid,
        'occurred_at': now_dt.isoformat(),
        'expires_at': exp_dt.isoformat(),
        'actor': actor,
        'patient_id': patient_id,
        'emergency_type': emergency_type,
        'justification': justification,
    }


def get_active_break_glass_grant(actor, patient_id):
    """Return the active (non-expired) Break-the-Glass grant for actor + patient_id, if any."""
    if not actor or not patient_id:
        return None
    try:
        from flask import has_app_context
        if not has_app_context():
            return None
        now_str = _utcnow()
        row = get_connection().execute(
            'SELECT * FROM break_glass_grants'
            ' WHERE actor = ? AND patient_id = ? AND expires_at > ?'
            ' ORDER BY id DESC LIMIT 1',
            (actor.strip().lower(), patient_id.strip(), now_str),
        ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def read_break_glass_grants(limit=50, patient_id=None):
    try:
        from flask import has_app_context
        if not has_app_context():
            return []
        if patient_id:
            rows = get_connection().execute(
                'SELECT * FROM break_glass_grants WHERE patient_id = ? ORDER BY id DESC LIMIT ?',
                (patient_id.strip(), limit),
            ).fetchall()
        else:
            rows = get_connection().execute(
                'SELECT * FROM break_glass_grants ORDER BY id DESC LIMIT ?',
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# --------------------------------------------------------------------------
# System Settings & Centralized Multi-Worker Configuration
# --------------------------------------------------------------------------

def get_system_setting(key, default=None):
    """Retrieve a centralized system setting across all gunicorn workers."""
    try:
        from flask import has_app_context
        if not has_app_context():
            return default
        connection = get_connection()
        row = connection.execute(
            'SELECT value FROM system_settings WHERE key = ?', (key,)
        ).fetchone()
        return row['value'] if row else default
    except Exception as exc:
        logger.debug('Could not read system setting %s: %s', key, exc)
        return default


def set_system_setting(key, value):
    """Persist a centralized system setting across all gunicorn workers."""
    try:
        from flask import has_app_context
        if not has_app_context():
            return
        connection = get_connection()
        connection.execute(
            'INSERT INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)'
            ' ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at',
            (key, str(value), _utcnow())
        )
        connection.commit()
    except Exception as exc:
        logger.warning('Could not write system setting %s: %s', key, exc)


def get_active_backend_config(default_profile='slainte_fhir', default_url=None):
    profile = get_system_setting('backend_profile', default_profile)
    url = get_system_setting('backend_url', default_url)
    return profile, url


def set_active_backend_config(profile, url):
    set_system_setting('backend_profile', profile)
    set_system_setting('backend_url', url)

