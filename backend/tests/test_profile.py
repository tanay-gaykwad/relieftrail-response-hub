from contextlib import contextmanager

import pytest
from fastapi import HTTPException, Response

from backend import main


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class ProfileDatabase:
    def __init__(self, password_hash):
        self.password_hash = password_hash
        self.statements = []

    def open(self, wait=False):
        pass

    def close(self):
        pass

    @contextmanager
    def connection(self):
        database = self

        class Connection:
            def execute(self, sql, params=()):
                database.statements.append((sql, params))
                if "SELECT password_hash FROM users" in sql:
                    return Result([{"password_hash": database.password_hash}])
                if "SELECT organization_id FROM organization_memberships" in sql:
                    return Result([{"organization_id": 1}])
                return Result()

        yield Connection()


def profile_user():
    return {
        "id": 7,
        "email": "member@example.test",
        "full_name": "Old Name",
        "session_hash": "old-session-hash",
        "memberships": {1: "editor"},
    }


def test_profile_name_update_is_scoped_and_audited(monkeypatch):
    database = ProfileDatabase(main.password_digest("unchanged-password"))
    monkeypatch.setattr(main, "pool", database)
    response = Response()
    result = main.update_my_profile(
        main.ProfileUpdate(full_name="  New Name  "), response, profile_user()
    )

    assert result == {
        "full_name": "New Name",
        "email": "member@example.test",
        "password_changed": False,
    }
    assert any("UPDATE users SET full_name" in sql for sql, _ in database.statements)
    assert any("INSERT INTO audit_events" in sql for sql, _ in database.statements)


def test_password_change_checks_old_password_and_rotates_sessions(monkeypatch):
    database = ProfileDatabase(main.password_digest("current passphrase"))
    monkeypatch.setattr(main, "pool", database)
    response = Response()
    result = main.update_my_profile(
        main.ProfileUpdate(
            current_password="current passphrase",
            new_password="a-new-unique-passphrase-2026",
        ),
        response,
        profile_user(),
    )

    assert result["password_changed"] is True
    assert any("UPDATE user_sessions SET revoked_at" in sql for sql, _ in database.statements)
    assert any("INSERT INTO user_sessions" in sql for sql, _ in database.statements)
    cookies = [value.decode() for key, value in response.raw_headers if key == b"set-cookie"]
    session_cookie = next(cookie for cookie in cookies if main.SESSION_COOKIE in cookie)
    assert "httponly" in session_cookie.lower()
    csrf_cookie = next(cookie for cookie in cookies if "rt_csrf=" in cookie)
    assert "csrf-test-token" not in csrf_cookie


def test_password_change_rejects_wrong_current_password_without_writing(monkeypatch):
    database = ProfileDatabase(main.password_digest("actual current passphrase"))
    monkeypatch.setattr(main, "pool", database)
    with pytest.raises(HTTPException, match="current password is incorrect") as error:
        main.update_my_profile(
            main.ProfileUpdate(
                current_password="wrong password",
                new_password="a-new-unique-passphrase-2026",
            ),
            Response(),
            profile_user(),
        )

    assert error.value.status_code == 403
    assert not any("UPDATE users SET password_hash" in sql for sql, _ in database.statements)
    assert not any("UPDATE user_sessions SET revoked_at" in sql for sql, _ in database.statements)


def test_password_change_requires_long_passphrase(monkeypatch):
    database = ProfileDatabase(main.password_digest("current passphrase"))
    monkeypatch.setattr(main, "pool", database)
    with pytest.raises(ValueError):
        main.ProfileUpdate(current_password="current passphrase", new_password="too-short")

    assert not any("UPDATE users SET password_hash" in sql for sql, _ in database.statements)

