from contextlib import contextmanager

from fastapi.testclient import TestClient

from backend import main


class MemoryDatabase:
    """Small adapter for exercising the HTTP auth boundary without a DB server."""

    def __init__(self):
        self.sessions = set()
        self.revoked = set()

    def open(self, wait=False):
        pass

    def close(self):
        pass

    @contextmanager
    def connection(self):
        class Connection:
            def __init__(inner):
                inner.db = self

            def execute(inner, sql, params=()):
                if "INSERT INTO user_sessions" in sql:
                    inner.db.sessions.add(params[1])
                elif "UPDATE user_sessions SET revoked_at" in sql:
                    inner.db.revoked.add(params[0])
                return inner

            def fetchone(inner):
                return None

        yield Connection()


def test_login_issues_httponly_session_and_logout_revokes_it(monkeypatch):
    db = MemoryDatabase()
    password_hash = main.password_digest("correct horse battery staple")
    org_membership = {"organization_id": 1, "role": "org_admin", "name": "Demo Org"}

    def fake_rows(sql, params=()):
        if "FROM login_throttles" in sql:
            return []
        if "FROM users WHERE email" in sql:
            return [{"id": 4, "email": "owner@example.test", "full_name": "Org Owner", "password_hash": password_hash, "is_active": True}]
        if "FROM user_sessions" in sql:
            token_hash = params[0]
            if token_hash in db.sessions and token_hash not in db.revoked:
                return [{"id": 4, "email": "owner@example.test", "full_name": "Org Owner", "is_active": True, "organization_id": 1, "role": "org_admin"}]
            return []
        if "FROM organization_memberships m" in sql:
            return [org_membership]
        return []

    monkeypatch.setattr(main, "rows", fake_rows)
    monkeypatch.setattr(main, "pool", db)
    with TestClient(main.app) as client:
        csrf = client.get("/api/auth/csrf")
        assert csrf.status_code == 200
        csrf_token = client.cookies["rt_csrf"]
        login = client.post("/api/auth/login", json={"email": "owner@example.test", "password": "correct horse battery staple"}, headers={"X-CSRF-Token": csrf_token})
        assert login.status_code == 200
        assert "token" not in login.json()
        session_cookie = next(cookie for cookie in login.headers.get_list("set-cookie") if main.SESSION_COOKIE in cookie)
        assert "httponly" in session_cookie.lower()
        assert client.get("/api/auth/me").status_code == 200

        logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": client.cookies["rt_csrf"]})
        assert logout.status_code == 204
        assert client.get("/api/auth/me").status_code == 401


def test_csrf_required_for_state_changing_requests():
    client = TestClient(main.app)
    response = client.post("/api/auth/login", json={"email": "x@example.test", "password": "x"})
    assert response.status_code == 403


def test_invalid_credentials_do_not_create_a_session(monkeypatch):
    password_hash = main.password_digest("right-password")

    def fake_rows(sql, params=()):
        if "FROM login_throttles" in sql:
            return []
        if "FROM users WHERE email" in sql:
            return [{"id": 12, "email": "user@example.test", "full_name": "Test User", "password_hash": password_hash, "is_active": True}]
        return []

    monkeypatch.setattr(main, "rows", fake_rows)
    monkeypatch.setattr(main, "record_login_failure", lambda _key: {"attempts": 1, "blocked_until": None})
    client = TestClient(main.app)
    csrf = client.get("/api/auth/csrf")
    response = client.post("/api/auth/login", json={"email": "user@example.test", "password": "wrong-password"}, headers={"X-CSRF-Token": client.cookies["rt_csrf"]})
    assert csrf.status_code == 200
    assert response.status_code == 401
    assert main.SESSION_COOKIE not in client.cookies


def test_viewer_cannot_create_response():
    main.app.dependency_overrides[main.current_user] = lambda: {"id": 9, "full_name": "Read Only", "memberships": {1: "viewer"}}
    try:
        client = TestClient(main.app)
        client.cookies.set("rt_csrf", "safe-token")
        response = client.post("/api/responses", headers={"X-CSRF-Token": "safe-token"}, json={
            "organization_id": 1,
            "code": "TEST-01",
            "title": "Test response",
            "location": "Test region",
            "summary": "A valid test description for a new response.",
        })
        assert response.status_code == 403
    finally:
        main.app.dependency_overrides.clear()


def test_membership_does_not_reveal_another_organization():
    main.app.dependency_overrides[main.current_user] = lambda: {"id": 9, "full_name": "Viewer", "memberships": {1: "viewer"}}
    try:
        response = TestClient(main.app).get("/api/team?organization_id=2")
        assert response.status_code == 404
    finally:
        main.app.dependency_overrides.clear()
