"""Phase 6.4 Core Security Remediation Tests.

Tests:
1. Progressive account lockout after 5 consecutive failed authentications.
2. Centralized rate limiting via SQLite storage.
3. LOG_HASH_SALT enforcement in production vs test/debug bypass.
4. Content Security Policy (CSP) and defense-in-depth security headers.
5. Subresource Integrity (SRI) hashes on external CDN resources.
"""
import os
import sqlite3
import pytest
from datetime import datetime, timezone, timedelta

import auth
import db
import rate_limit_storage
from logging_setup import validate_salt
from conftest import TEST_PASSWORD


class TestProgressiveLockout:
    """Account is temporarily locked out after 5 consecutive failed logins."""

    def test_progressive_lockout_after_five_failed_attempts(self, client, active_user):
        # 1-4 failed attempts: return 401
        for i in range(1, 5):
            res = client.post('/login', data={'username': active_user, 'password': 'wrong-password'})
            assert res.status_code == 401
            assert 'incorrect username or password' in res.get_data(as_text=True).lower()
            with client.application.app_context():
                user = db.get_user(active_user)
                assert user['failed_login_attempts'] == i
                assert user['locked_until'] is None

        # 5th failed attempt: triggers lockout, returns 403
        res5 = client.post('/login', data={'username': active_user, 'password': 'wrong-password'})
        assert res5.status_code == 403
        assert 'temporarily locked' in res5.get_data(as_text=True).lower()

        with client.application.app_context():
            user = db.get_user(active_user)
            assert user['failed_login_attempts'] == 5
            assert user['locked_until'] is not None

        # Even with the CORRECT password, locked user is rejected
        res_locked = client.post('/login', data={'username': active_user, 'password': TEST_PASSWORD})
        assert res_locked.status_code == 403
        assert 'temporarily locked' in res_locked.get_data(as_text=True).lower()

    def test_lockout_expires_and_successful_login_resets_counter(self, client, active_user):
        # Lock the account by setting locked_until in the past
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        with client.application.app_context():
            conn = db.get_connection()
            conn.execute(
                'UPDATE users SET failed_login_attempts = 5, locked_until = ? WHERE username = ?',
                (past_time, active_user),
            )
            conn.commit()

            # is_account_locked should now return False and auto-reset
            locked, until = db.is_account_locked(active_user)
            assert locked is False

        # User logs in with correct password
        res = client.post('/login', data={'username': active_user, 'password': TEST_PASSWORD}, follow_redirects=True)
        assert res.status_code == 200

        with client.application.app_context():
            user = db.get_user(active_user)
            assert user['failed_login_attempts'] == 0
            assert user['locked_until'] is None


class TestRateLimiterStorage:
    """Centralized rate limiting using SqliteStorage."""

    def test_sqlite_storage_increments_and_resets(self, tmp_path):
        db_file = str(tmp_path / "ratelimits.db")
        storage = rate_limit_storage.SqliteStorage(f"sqlite:///{db_file}")

        key = "test_client_key"
        count1 = storage.incr(key, expiry=60)
        assert count1 == 1

        count2 = storage.incr(key, expiry=60)
        assert count2 == 2

        assert storage.get(key) == 2
        storage.clear(key)
        assert storage.get(key) == 0


class TestLogHashSaltEnforcement:
    """LOG_HASH_SALT is required outside debug/testing mode."""

    def test_validate_salt_passes_in_testing_or_debug(self):
        # Should not raise
        validate_salt(is_debug=True, is_testing=False)
        validate_salt(is_debug=False, is_testing=True)

    def test_validate_salt_fails_in_production_when_empty(self, monkeypatch):
        monkeypatch.delenv('LOG_HASH_SALT', raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            validate_salt(is_debug=False, is_testing=False)
        assert 'LOG_HASH_SALT environment variable is required' in str(exc_info.value)

    def test_validate_salt_passes_in_production_when_set(self, monkeypatch):
        monkeypatch.setenv('LOG_HASH_SALT', 'super-secret-salt-2026')
        validate_salt(is_debug=False, is_testing=False)


class TestSecurityHeadersAndSRI:
    """CSP and defense-in-depth headers and SRI attributes."""

    def test_security_headers_present_on_response(self, client):
        res = client.get('/login')
        assert res.status_code == 200

        headers = res.headers
        assert headers.get('X-Content-Type-Options') == 'nosniff'
        assert headers.get('X-Frame-Options') == 'DENY'
        assert headers.get('X-XSS-Protection') == '1; mode=block'

        csp = headers.get('Content-Security-Policy', '')
        assert "default-src 'self'" in csp
        assert "script-src" in csp
        assert "connect-src" in csp
        assert "https://cdn.jsdelivr.net" in csp
        assert "https://unpkg.com" in csp

    def test_sri_hashes_in_templates(self, client):
        # Check login page
        res = client.get('/login')
        html = res.get_data(as_text=True)
        assert 'integrity="sha384-' in html
        assert 'crossorigin="anonymous"' in html
