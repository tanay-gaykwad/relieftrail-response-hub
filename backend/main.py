"""ReliefTrail Funding Workspace API. Demo credentials and sample data are fictional."""
import base64
import csv
import hashlib
import hmac
import io
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response as FastAPIResponse, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from psycopg.types.json import Jsonb

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://relieftrail:local_demo_only@localhost:5432/relieftrail")
APP_ENV = os.getenv("APP_ENV", "local").lower()
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "")
if APP_ENV == "production" and (len(APP_SECRET_KEY) < 32 or "change-before" in APP_SECRET_KEY.lower()):
    raise RuntimeError("Production requires APP_SECRET_KEY to be a unique secret of at least 32 characters.")
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "admin@relieftrail.test").strip().lower()
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo-change-me")
SESSION_COOKIE = "__Host-relieftrail_session" if APP_ENV == "production" else "relieftrail_session"
COOKIE_SECURE = APP_ENV == "production"
pool = ConnectionPool(DATABASE_URL, kwargs={"row_factory": dict_row}, open=False)
password_hasher = PasswordHasher()


@asynccontextmanager
async def lifespan(_app):
    pool.open(wait=True)
    try:
        ensure_demo_user()
        yield
    finally:
        pool.close()


app = FastAPI(title="ReliefTrail ResponseHub", version="0.3.0", description="Organization-scoped relief awards, budgets, reporting, and reconciliation API.", docs_url=None if APP_ENV == "production" else "/docs", redoc_url=None if APP_ENV == "production" else "/redoc", lifespan=lifespan)
allowed_origins = [value.strip() for value in os.getenv("FRONTEND_ORIGINS", os.getenv("FRONTEND_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173")).split(",") if value.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token"])


def password_digest(password: str) -> str:
    return password_hasher.hash(password)


def password_matches(password: str, encoded: str) -> bool:
    if encoded.startswith("$argon2id$"):
        try:
            return password_hasher.verify(encoded,password)
        except (VerifyMismatchError,InvalidHashError,VerificationError):
            return False
    try:
        algorithm, rounds_text, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_text)
        if rounds < 100_000 or rounds > 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256",password.encode(),base64.urlsafe_b64decode(salt + "=" * (-len(salt) % 4)),rounds)
        return hmac.compare_digest(base64.urlsafe_b64encode(actual).decode(), expected)
    except (ValueError, TypeError):
        return False


DUMMY_PASSWORD_HASH = password_digest(secrets.token_urlsafe(32))


def rows(sql, params=()):
    with pool.connection() as conn:
        return conn.execute(sql, params).fetchall()


def ensure_demo_user():
    if APP_ENV != "demo":
        return
    demo_accounts = [
        (DEMO_EMAIL, "Jamie Davis", DEMO_PASSWORD, "org_admin"),
        ("editor@relieftrail.test", "Taylor Editor", "editor-demo", "editor"),
        ("reviewer@relieftrail.test", "Riley Reviewer", "reviewer-demo", "reviewer"),
        ("viewer@relieftrail.test", "Casey Viewer", "viewer-demo", "viewer"),
    ]
    with pool.connection() as conn:
        for email, full_name, password, role in demo_accounts:
            user = conn.execute("""INSERT INTO users(email,full_name,password_hash)
                VALUES (%s,%s,%s) ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash,is_active=true RETURNING id""",
                (email,full_name,password_digest(password))).fetchone()
            conn.execute("""INSERT INTO organization_memberships(user_id,organization_id,role)
                VALUES (%s,1,%s) ON CONFLICT(user_id,organization_id) DO UPDATE SET role=excluded.role""", (user["id"],role))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if COOKIE_SECURE:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method in {"POST", "PATCH", "DELETE"}:
        cookie_token = request.cookies.get("rt_csrf")
        header_token = request.headers.get("X-CSRF-Token")
        if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
            return JSONResponse(status_code=403, content={"detail": "Security token missing or expired. Refresh the page and try again."})
    return await call_next(request)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class ResponseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_id: int = Field(gt=0)
    code: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9-]+$")
    title: str = Field(min_length=3, max_length=160)
    location: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=10, max_length=1000)
    start_date: date | None = None

    @field_validator("code", "title", "location", "summary", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class ResponseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=160)
    location: str | None = Field(default=None, min_length=2, max_length=120)
    summary: str | None = Field(default=None, min_length=10, max_length=1000)
    status: Literal["draft", "in_review", "approved", "closed"] | None = None
    start_date: date | None = None

    @field_validator("title", "location", "summary", mode="before")
    @classmethod
    def trim_update_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("title", "location", "summary", "status")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be cleared.")
        return value


class AwardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_id: int = Field(gt=0)
    response_id: int = Field(gt=0)
    funder_name: str = Field(min_length=2, max_length=160)
    funder_kind: Literal["foundation","government","institutional_donor","corporate","other"] = "foundation"
    award_code: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9-]+$")
    title: str = Field(min_length=3, max_length=160)
    total_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Literal["USD"] = "USD"
    start_date: date
    end_date: date
    restricted_purpose: str = Field(min_length=5, max_length=1000)
    allocation_category: str = Field(min_length=2, max_length=80)
    budget_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    first_report_due: date

    @field_validator("funder_name", "award_code", "title", "restricted_purpose", "allocation_category", mode="before")
    @classmethod
    def trim_award_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("award_code")
    @classmethod
    def normalize_award_code(cls, value):
        return value.upper()


class DisbursementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allocation_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    recorded_on: date
    reference: str = Field(min_length=3, max_length=120)
    source_reference: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class MilestoneUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["submitted","accepted","needs_revision"]
    summary: str | None = Field(default=None, min_length=20, max_length=3000)


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["org_admin","editor","reviewer","viewer"]


def current_user(request: Request):
    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    token_hash = hashlib.sha256(session_token.encode()).hexdigest()
    found = rows("""SELECT u.id,u.email,u.full_name,u.is_active,m.organization_id,m.role
        FROM user_sessions s JOIN users u ON u.id=s.user_id
        LEFT JOIN organization_memberships m ON m.user_id=u.id
        WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at>now()
        ORDER BY m.organization_id""", (token_hash,))
    if not found or not found[0]["is_active"]:
        raise HTTPException(status_code=401, detail="Your session expired or this account is unavailable.")
    user = {"id": found[0]["id"], "email": found[0]["email"], "full_name": found[0]["full_name"],
            "session_hash": token_hash,
            "memberships": {row["organization_id"]: row["role"] for row in found if row["organization_id"] is not None}}
    return user


def check_csrf(request: Request):
    cookie_token = request.cookies.get("rt_csrf")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="Security token missing or expired. Refresh the page and try again.")


def throttle_key(email: str, client_host: str) -> str:
    return hmac.new(APP_SECRET_KEY.encode(), f"{email}\0{client_host}".encode(), hashlib.sha256).hexdigest()


def record_login_failure(key_hash: str) -> dict:
    with pool.connection() as conn:
        return conn.execute("""INSERT INTO login_throttles(key_hash,attempts,window_started_at)
            VALUES (%s,1,now())
            ON CONFLICT(key_hash) DO UPDATE SET
              attempts=CASE WHEN login_throttles.window_started_at < now()-interval '15 minutes' THEN 1 ELSE login_throttles.attempts+1 END,
              window_started_at=CASE WHEN login_throttles.window_started_at < now()-interval '15 minutes' THEN now() ELSE login_throttles.window_started_at END,
              blocked_until=CASE WHEN login_throttles.window_started_at < now()-interval '15 minutes' THEN NULL
                                 WHEN login_throttles.attempts+1 >= 10 THEN now()+interval '15 minutes' ELSE login_throttles.blocked_until END
            RETURNING attempts,blocked_until""", (key_hash,)).fetchone()


def require_org(user: dict, organization_id: int, roles: tuple[str, ...] = ()):
    role = user["memberships"].get(organization_id)
    if not role:
        raise HTTPException(status_code=404, detail="Organization not found.")
    if roles and role not in roles:
        raise HTTPException(status_code=403, detail="Your organization role does not allow this action.")
    return role


def audit(conn, user: dict, organization_id: int, action: str, entity_type: str, entity_id: int, details: dict | None = None):
    conn.execute("""INSERT INTO audit_events(organization_id,action,entity_type,entity_id,actor_label,details)
        VALUES (%s,%s,%s,%s,%s,%s)""", (organization_id, action, entity_type, entity_id, user["full_name"], Jsonb(details or {})))


def parse_funding_csv(content: bytes) -> list[tuple]:
    """Validate an entire CSV payload before opening a database transaction."""
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
        required = {"response_code", "record_type", "amount", "currency", "recorded_on", "reference", "source_reference"}
        if not required.issubset({name.strip().lower() for name in (reader.fieldnames or []) if name}):
            raise ValueError("CSV needs response_code, record_type, amount, currency, recorded_on, reference, and source_reference columns.")
        if len(reader.fieldnames or []) > 30:
            raise ValueError("The CSV has too many columns.")
        parsed = []
        for line_number, raw in enumerate(reader, start=2):
            if line_number > 1002:
                raise ValueError("A file can contain at most 1,000 data rows.")
            row = {(key or "").strip().lower(): (value or "").strip() for key, value in raw.items()}
            if not any(row.values()):
                continue
            try:
                code, kind = row["response_code"].upper(), row["record_type"].lower()
                amount = Decimal(row["amount"])
                currency, date_value = row["currency"].upper(), date.fromisoformat(row["recorded_on"])
                reference, source_reference = row["reference"], row["source_reference"]
            except (KeyError, ValueError, InvalidOperation, ArithmeticError) as exc:
                raise ValueError(f"Row {line_number}: required values or date/amount format are invalid.") from exc
            if kind not in ("contribution", "disbursement") or not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2 or amount.adjusted() > 15:
                raise ValueError(f"Row {line_number}: type must be contribution/disbursement and amount must be positive with at most two decimal places.")
            if currency != "USD" or len(reference) < 3 or len(reference) > 120 or not source_reference or len(source_reference) > 120:
                raise ValueError(f"Row {line_number}: currency, reference, or source_reference is invalid.")
            if len(row.get("description") or "") > 1000:
                raise ValueError(f"Row {line_number}: description must be 1,000 characters or fewer.")
            parsed.append((line_number, code, kind, amount, currency, date_value, reference, source_reference, row.get("description") or None))
        if not parsed:
            raise ValueError("The CSV contains no funding rows.")
        return parsed
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("CSV must be a valid UTF-8 CSV file.") from exc


@app.get("/api/health")
def health():
    rows("SELECT 1")
    return {"status": "ok", "database": "connected", "mode": os.getenv("APP_ENV", "local")}


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: FastAPIResponse):
    check_csrf(request)
    email = payload.email.strip().lower()
    key_hash = throttle_key(email, request.client.host if request.client else "unknown")
    throttle = rows("SELECT blocked_until FROM login_throttles WHERE key_hash=%s", (key_hash,))
    if throttle and throttle[0]["blocked_until"] and throttle[0]["blocked_until"] > datetime.now(timezone.utc):
        raise HTTPException(status_code=429, detail="Too many sign-in attempts. Wait 15 minutes and try again.", headers={"Retry-After": "900"})
    found = rows("SELECT id,email,full_name,password_hash,is_active FROM users WHERE email=%s", (email,))
    encoded = found[0]["password_hash"] if found else DUMMY_PASSWORD_HASH
    valid = password_matches(payload.password, encoded)
    if not found or not found[0]["is_active"] or not valid:
        failure = record_login_failure(key_hash)
        if failure["blocked_until"] and failure["blocked_until"] > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many sign-in attempts. Wait 15 minutes and try again.", headers={"Retry-After": "900"})
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    user = found[0]
    if not user["password_hash"].startswith("$argon2id$") or password_hasher.check_needs_rehash(user["password_hash"]):
        with pool.connection() as conn:
            conn.execute("UPDATE users SET password_hash=%s WHERE id=%s", (password_digest(payload.password),user["id"]))
    with pool.connection() as conn:
        conn.execute("DELETE FROM login_throttles WHERE key_hash=%s", (key_hash,))
    memberships = rows("""SELECT m.organization_id,m.role,o.name FROM organization_memberships m
        JOIN organizations o ON o.id=m.organization_id WHERE m.user_id=%s ORDER BY o.name""", (user["id"],))
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    with pool.connection() as conn:
        conn.execute("INSERT INTO user_sessions(user_id,token_hash,expires_at) VALUES (%s,%s,%s)", (user["id"],session_hash,expires_at))
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(SESSION_COOKIE, session_token, max_age=8*60*60, httponly=True, secure=COOKIE_SECURE, samesite="strict", path="/")
    response.set_cookie("rt_csrf", csrf_token, max_age=8*60*60, httponly=False, secure=COOKIE_SECURE, samesite="strict", path="/")
    return {"user": {"full_name": user["full_name"], "email": user["email"]}, "organizations": memberships}


@app.get("/api/auth/csrf")
def issue_csrf(response: FastAPIResponse):
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie("rt_csrf", csrf_token, httponly=False, secure=COOKIE_SECURE, samesite="strict", path="/")
    return {"ok": True}


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: FastAPIResponse, user: dict = Depends(current_user)):
    check_csrf(request)
    with pool.connection() as conn:
        conn.execute("UPDATE user_sessions SET revoked_at=now() WHERE token_hash=%s AND revoked_at IS NULL", (user["session_hash"],))
    logout_response = FastAPIResponse(status_code=204)
    logout_response.delete_cookie(SESSION_COOKIE, path="/", secure=COOKIE_SECURE, httponly=True, samesite="strict")
    logout_response.delete_cookie("rt_csrf", path="/", secure=COOKIE_SECURE, samesite="strict")
    return logout_response


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    organizations = rows("""SELECT o.id,o.name,o.kind,m.role FROM organization_memberships m
        JOIN organizations o ON o.id=m.organization_id WHERE m.user_id=%s ORDER BY o.name""", (user["id"],))
    return {"full_name": user["full_name"], "email": user["email"], "organizations": organizations}


@app.get("/api/organizations")
def organizations(user: dict = Depends(current_user)):
    return rows("""SELECT o.id,o.name,o.kind,m.role FROM organizations o
        JOIN organization_memberships m ON m.organization_id=o.id WHERE m.user_id=%s ORDER BY o.name""", (user["id"],))


@app.get("/api/team")
def team(organization_id: int, user: dict = Depends(current_user)):
    require_org(user, organization_id, ("org_admin",))
    return rows("""SELECT u.id,u.full_name,u.email,u.is_active,m.role,m.created_at AS joined_at
        FROM organization_memberships m JOIN users u ON u.id=m.user_id
        WHERE m.organization_id=%s ORDER BY u.full_name""", (organization_id,))


@app.patch("/api/team/{member_id}")
def update_team_role(member_id: int, organization_id: int, payload: RoleUpdate, user: dict = Depends(current_user)):
    require_org(user, organization_id, ("org_admin",))
    with pool.connection() as conn:
        conn.execute("SELECT id FROM organizations WHERE id=%s FOR UPDATE", (organization_id,))
        member = conn.execute("SELECT role FROM organization_memberships WHERE organization_id=%s AND user_id=%s FOR UPDATE", (organization_id,member_id)).fetchone()
        if not member:
            raise HTTPException(status_code=404, detail="Team member not found in this organization.")
        admin_count = conn.execute("SELECT count(*) AS total FROM organization_memberships WHERE organization_id=%s AND role='org_admin'", (organization_id,)).fetchone()["total"]
        if member["role"] == "org_admin" and payload.role != "org_admin" and admin_count <= 1:
            raise HTTPException(status_code=409, detail="An organization must keep at least one administrator.")
        conn.execute("UPDATE organization_memberships SET role=%s WHERE organization_id=%s AND user_id=%s", (payload.role,organization_id,member_id))
        audit(conn,user,organization_id,"role_changed","organization_member",member_id,{"from":member["role"],"to":payload.role})
    return {"user_id":member_id,"organization_id":organization_id,"role":payload.role}


@app.get("/api/awards")
def awards(user: dict = Depends(current_user)):
    return rows("""SELECT a.id,a.organization_id,a.award_code,a.title,f.name AS funder_name,a.total_amount,a.currency,
        a.start_date,a.end_date,a.restricted_purpose,a.status,
        coalesce((SELECT sum(al.budget_amount) FROM award_allocations al WHERE al.award_id=a.id),0) AS allocated_amount,
        coalesce((SELECT json_agg(json_build_object('id',al.id,'category',al.category,'budget_amount',al.budget_amount,'response_id',al.response_id,'response_code',r.code,'response_title',r.title) ORDER BY al.id)
                  FROM award_allocations al JOIN responses r ON r.id=al.response_id WHERE al.award_id=a.id),'[]'::json) AS allocations,
        coalesce((SELECT sum(fr.amount) FROM funding_records fr JOIN award_allocations al ON al.id=fr.award_allocation_id
                  WHERE al.award_id=a.id AND fr.record_type='disbursement'),0) AS disbursed_amount,
        (SELECT count(*) FROM reporting_milestones rm WHERE rm.award_id=a.id AND rm.status IN ('upcoming','needs_revision')) AS reports_due
        FROM funding_awards a JOIN funders f ON f.id=a.funder_id
        JOIN organization_memberships m ON m.organization_id=a.organization_id AND m.user_id=%s
        ORDER BY a.start_date DESC,a.id DESC""", (user["id"],))


@app.post("/api/awards", status_code=201)
def create_award(payload: AwardCreate, user: dict = Depends(current_user)):
    require_org(user,payload.organization_id,("org_admin","editor"))
    if payload.budget_amount > payload.total_amount:
        raise HTTPException(status_code=422, detail="The response budget cannot exceed the award total.")
    if payload.end_date < payload.start_date or payload.first_report_due < payload.start_date:
        raise HTTPException(status_code=422, detail="Award end date and report deadline must follow its start date.")
    with pool.connection() as conn:
        response = conn.execute("""SELECT id,status FROM responses WHERE id=%s AND organization_id=%s FOR UPDATE""", (payload.response_id,payload.organization_id)).fetchone()
        if not response:
            raise HTTPException(status_code=404, detail="Response not found in this organization.")
        if response["status"] != "approved":
            raise HTTPException(status_code=409, detail="Approve the response before assigning a grant budget.")
        funder = conn.execute("""INSERT INTO funders(organization_id,name,kind) VALUES (%s,%s,%s)
            ON CONFLICT(organization_id,name) DO UPDATE SET kind=excluded.kind RETURNING id""", (payload.organization_id,payload.funder_name,payload.funder_kind)).fetchone()
        try:
            award = conn.execute("""INSERT INTO funding_awards(organization_id,funder_id,award_code,title,total_amount,currency,start_date,end_date,restricted_purpose,status,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',%s) RETURNING id""", (payload.organization_id,funder["id"],payload.award_code,payload.title,payload.total_amount,payload.currency,payload.start_date,payload.end_date,payload.restricted_purpose,user["id"])).fetchone()
            conn.execute("""INSERT INTO award_allocations(organization_id,award_id,response_id,category,budget_amount)
                VALUES (%s,%s,%s,%s,%s)""", (payload.organization_id,award["id"],payload.response_id,payload.allocation_category,payload.budget_amount))
            conn.execute("""INSERT INTO reporting_milestones(organization_id,award_id,period_start,period_end,due_date,report_type,status)
                VALUES (%s,%s,%s,%s,%s,'financial','upcoming')""", (payload.organization_id,award["id"],payload.start_date,min(payload.first_report_due,payload.end_date),payload.first_report_due))
            audit(conn,user,payload.organization_id,"created","funding_award",award["id"],{"award_code":payload.award_code})
        except psycopg.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="That award code or reporting period already exists.")
    return {"id":award["id"],"award_code":payload.award_code,"status":"active"}


@app.get("/api/reporting-calendar")
def reporting_calendar(user: dict = Depends(current_user)):
    return rows("""SELECT rm.id,rm.award_id,rm.period_start,rm.period_end,rm.due_date,rm.report_type,rm.status,rm.summary,rm.submitted_at,
        a.award_code,a.title AS award_title,f.name AS funder_name,
        (SELECT coalesce(sum(fr.amount),0) FROM funding_records fr JOIN award_allocations al ON al.id=fr.award_allocation_id
         WHERE al.award_id=a.id AND fr.record_type='disbursement') AS disbursed_amount
        FROM reporting_milestones rm JOIN funding_awards a ON a.id=rm.award_id JOIN funders f ON f.id=a.funder_id
        JOIN organization_memberships m ON m.organization_id=rm.organization_id AND m.user_id=%s
        ORDER BY rm.due_date,rm.id""", (user["id"],))


@app.patch("/api/reporting-calendar/{milestone_id}")
def update_milestone(milestone_id: int, payload: MilestoneUpdate, user: dict = Depends(current_user)):
    if payload.status in ("submitted","needs_revision") and not payload.summary:
        raise HTTPException(status_code=422, detail="Add a report summary before submitting or requesting changes.")
    with pool.connection() as conn:
        item = conn.execute("""SELECT rm.organization_id,rm.status FROM reporting_milestones rm
            JOIN organization_memberships m ON m.organization_id=rm.organization_id AND m.user_id=%s
            WHERE rm.id=%s FOR UPDATE OF rm""", (user["id"],milestone_id)).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Reporting milestone not found.")
        if payload.status == "submitted":
            require_org(user,item["organization_id"],("org_admin","editor"))
            if item["status"] not in ("upcoming","needs_revision"):
                raise HTTPException(status_code=409, detail="Only a due or returned report can be submitted.")
            submitted_at = datetime.now(timezone.utc)
            submitted_by = user["id"]
        else:
            require_org(user,item["organization_id"],("org_admin","reviewer"))
            if item["status"] != "submitted":
                raise HTTPException(status_code=409, detail="A report must be submitted before review.")
            submitted_at = None
            submitted_by = None
        conn.execute("""UPDATE reporting_milestones SET status=%s,summary=coalesce(%s,summary),
            submitted_at=CASE WHEN %s='needs_revision' THEN NULL WHEN %s='accepted' THEN submitted_at ELSE %s END,
            submitted_by=CASE WHEN %s='needs_revision' THEN NULL WHEN %s='accepted' THEN submitted_by ELSE %s END
            WHERE id=%s""", (payload.status,payload.summary,payload.status,payload.status,submitted_at,payload.status,payload.status,submitted_by,milestone_id))
        audit(conn,user,item["organization_id"],"report_status_changed","reporting_milestone",milestone_id,{"from":item["status"],"to":payload.status})
    return {"id":milestone_id,"status":payload.status}


@app.post("/api/disbursements", status_code=201)
def record_disbursement(payload: DisbursementCreate, user: dict = Depends(current_user)):
    with pool.connection() as conn:
        allocation = conn.execute("""SELECT al.id,al.organization_id,al.response_id,al.budget_amount,a.status AS award_status,
            a.start_date,a.end_date,r.status AS response_status
            FROM award_allocations al JOIN funding_awards a ON a.id=al.award_id JOIN responses r ON r.id=al.response_id
            JOIN organization_memberships m ON m.organization_id=al.organization_id AND m.user_id=%s
            WHERE al.id=%s FOR UPDATE OF al""", (user["id"],payload.allocation_id)).fetchone()
        if not allocation:
            raise HTTPException(status_code=404, detail="Award budget line not found.")
        require_org(user,allocation["organization_id"],("org_admin","editor"))
        if allocation["award_status"] != "active" or allocation["response_status"] != "approved":
            raise HTTPException(status_code=409, detail="Only active awards assigned to approved responses can be spent.")
        if not allocation["start_date"] <= payload.recorded_on <= allocation["end_date"]:
            raise HTTPException(status_code=422, detail="Disbursement date must be within the award period.")
        spent = conn.execute("""SELECT coalesce(sum(amount),0) AS total FROM funding_records
            WHERE award_allocation_id=%s AND record_type='disbursement'""", (payload.allocation_id,)).fetchone()["total"]
        if spent + payload.amount > allocation["budget_amount"]:
            raise HTTPException(status_code=409, detail="This disbursement would exceed its approved budget line.")
        source = conn.execute("SELECT id FROM funding_sources WHERE source_type='manual' ORDER BY id LIMIT 1").fetchone()
        if not source:
            raise HTTPException(status_code=500, detail="Manual funding source is not configured.")
        try:
            record = conn.execute("""INSERT INTO funding_records(response_id,award_allocation_id,source_id,record_type,amount,currency,recorded_on,reference,description,source_reference)
                VALUES (%s,%s,%s,'disbursement',%s,'USD',%s,%s,%s,%s) RETURNING id""", (allocation["response_id"],payload.allocation_id,source["id"],payload.amount,payload.recorded_on,payload.reference,payload.description,payload.source_reference)).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="That source reference has already been recorded.")
        audit(conn,user,allocation["organization_id"],"disbursed","funding_record",record["id"],{"amount":str(payload.amount),"reference":payload.reference})
    return {"id":record["id"],"status":"recorded"}


@app.get("/api/dashboard")
def dashboard(user: dict = Depends(current_user)):
    org_ids = list(user["memberships"])
    summary = rows("""SELECT count(DISTINCT r.id) FILTER (WHERE r.status='approved') AS active_responses,
        count(DISTINCT r.id) AS response_count,
        coalesce(sum(f.amount) FILTER (WHERE f.record_type='contribution'),0) AS contributed,
        coalesce(sum(f.amount) FILTER (WHERE f.record_type='disbursement'),0) AS disbursed,
        (SELECT count(*) FROM reconciliation_issues i JOIN responses ir ON ir.id=i.response_id WHERE i.status='open' AND ir.organization_id=ANY(%s)) AS open_issues
        FROM responses r LEFT JOIN funding_records f ON f.response_id=r.id WHERE r.organization_id=ANY(%s)""", (org_ids, org_ids))[0]
    monthly = rows("""WITH months AS (
          SELECT generate_series(date_trunc('month',CURRENT_DATE)-interval '5 months',date_trunc('month',CURRENT_DATE),interval '1 month') AS month_start
        ), scoped_records AS (
          SELECT f.* FROM funding_records f JOIN responses r ON r.id=f.response_id WHERE r.organization_id=ANY(%s)
        ) SELECT to_char(m.month_start,'Mon') AS month,
          coalesce(sum(f.amount) FILTER (WHERE f.record_type='contribution'),0) AS contributions,
          coalesce(sum(f.amount) FILTER (WHERE f.record_type='disbursement'),0) AS disbursements
        FROM months m LEFT JOIN scoped_records f ON date_trunc('month',f.recorded_on)=m.month_start
        GROUP BY m.month_start ORDER BY m.month_start""", (org_ids,))
    recent = rows("""SELECT f.id,f.record_type,f.amount,f.currency,f.recorded_on,f.reference,
        r.code AS response_code,r.title AS response_title,s.name AS source_name
        FROM funding_records f JOIN responses r ON r.id=f.response_id JOIN funding_sources s ON s.id=f.source_id
        WHERE r.organization_id=ANY(%s) ORDER BY f.recorded_on DESC,f.id DESC LIMIT 6""", (org_ids,))
    return {"summary": summary, "monthly": monthly, "recent_records": recent}


@app.get("/api/responses")
def list_responses(user: dict = Depends(current_user)):
    return rows("""SELECT r.id,r.code,r.title,r.location,r.summary,r.status,r.start_date,o.name AS organization_name,
        coalesce((SELECT sum(f.amount) FROM funding_records f WHERE f.response_id=r.id AND f.record_type='contribution'),0) AS contributed,
        coalesce((SELECT sum(f.amount) FROM funding_records f WHERE f.response_id=r.id AND f.record_type='disbursement'),0) AS disbursed,
        (SELECT count(*) FROM reconciliation_issues i WHERE i.response_id=r.id AND i.status='open') AS open_issues
        FROM responses r JOIN organizations o ON o.id=r.organization_id
        JOIN organization_memberships m ON m.organization_id=o.id AND m.user_id=%s ORDER BY r.created_at DESC""", (user["id"],))


@app.post("/api/responses", status_code=201)
def create_response(payload: ResponseCreate, user: dict = Depends(current_user)):
    require_org(user, payload.organization_id, ("org_admin", "editor"))
    try:
        with pool.connection() as conn:
            item = conn.execute("""INSERT INTO responses(organization_id,code,title,location,summary,status,start_date)
                VALUES (%s,%s,%s,%s,%s,'draft',%s) RETURNING id,code,title,location,summary,status,start_date""",
                (payload.organization_id,payload.code.upper(),payload.title,payload.location,payload.summary,payload.start_date)).fetchone()
            audit(conn,user,payload.organization_id,"created","response",item["id"],{"code":item["code"]})
        return item
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="That response code is already in use.")
    except psycopg.errors.ForeignKeyViolation:
        raise HTTPException(status_code=400, detail="Choose an existing organization.")


@app.patch("/api/responses/{response_id}")
def update_response(response_id: int, payload: ResponseUpdate, user: dict = Depends(current_user)):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    with pool.connection() as conn:
        current = conn.execute("""SELECT r.organization_id,r.status FROM responses r
            JOIN organization_memberships m ON m.organization_id=r.organization_id AND m.user_id=%s
            WHERE r.id=%s FOR UPDATE""", (user["id"],response_id)).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Response not found.")
        role = require_org(user,current["organization_id"],("org_admin","editor"))
        if updates.get("status") in ("approved","closed") and role != "org_admin":
            raise HTTPException(status_code=403, detail="Only an organization administrator can approve or close a response.")
        fields = list(updates)
        assignments = ",".join(f"{field}=%s" for field in fields)
        values = [updates[field] for field in fields]
        item = conn.execute(f"UPDATE responses SET {assignments},updated_at=now() WHERE id=%s RETURNING id,code,title,location,summary,status,start_date", (*values,response_id)).fetchone()
        audit(conn,user,current["organization_id"],"updated","response",response_id,{"fields":fields})
    return item


@app.delete("/api/responses/{response_id}", status_code=204)
def delete_response(response_id: int, user: dict = Depends(current_user)):
    with pool.connection() as conn:
        item = conn.execute("""SELECT r.organization_id,r.status FROM responses r
            JOIN organization_memberships m ON m.organization_id=r.organization_id AND m.user_id=%s
            WHERE r.id=%s FOR UPDATE""", (user["id"],response_id)).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Response not found.")
        require_org(user,item["organization_id"],("org_admin","editor"))
        if item["status"] != "draft":
            raise HTTPException(status_code=409, detail="Only a draft response can be deleted.")
        has_history = conn.execute("""SELECT EXISTS(SELECT 1 FROM funding_records WHERE response_id=%s)
            OR EXISTS(SELECT 1 FROM reconciliation_issues WHERE response_id=%s) AS used""", (response_id,response_id)).fetchone()["used"]
        if has_history:
            raise HTTPException(status_code=409, detail="This draft has funding or review history and cannot be deleted.")
        audit(conn,user,item["organization_id"],"deleted","response",response_id)
        conn.execute("DELETE FROM responses WHERE id=%s", (response_id,))
    return FastAPIResponse(status_code=204)


@app.get("/api/funding-records")
def funding_records(record_type: Literal["contribution", "disbursement"] | None = None, user: dict = Depends(current_user)):
    condition = "AND f.record_type=%s" if record_type else ""
    params = (list(user["memberships"]), record_type) if record_type else (list(user["memberships"]),)
    return rows(f"""SELECT f.id,f.record_type,f.amount,f.currency,f.recorded_on,f.reference,f.description,f.source_reference,
        r.code AS response_code,r.title AS response_title,s.name AS source_name,
        count(i.id) FILTER (WHERE i.status='open') AS open_issues
        FROM funding_records f JOIN responses r ON r.id=f.response_id JOIN funding_sources s ON s.id=f.source_id
        LEFT JOIN reconciliation_issues i ON i.funding_record_id=f.id WHERE r.organization_id=ANY(%s) {condition}
        GROUP BY f.id,r.code,r.title,s.name ORDER BY f.recorded_on DESC,f.id DESC""", params)


@app.post("/api/imports/csv", status_code=201)
async def import_csv(file: UploadFile = File(...), user: dict = Depends(current_user)):
    """Validate the full file in memory, then write it as one database transaction."""
    safe_name = (file.filename or "funding.csv").replace("\\", "/").split("/")[-1][:120]
    if not safe_name.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Choose a CSV file.")
    content = await file.read(2_097_153)
    if len(content) > 2_097_152:
        raise HTTPException(status_code=413, detail="CSV files must be 2 MB or smaller.")
    try:
        parsed = parse_funding_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"CSV could not be validated: {exc}")

    imported = skipped = 0
    with pool.connection() as conn:
        codes = list({entry[1] for entry in parsed})
        responses = conn.execute("SELECT id,code,organization_id FROM responses WHERE code=ANY(%s)", (codes,)).fetchall()
        by_code = {row["code"]: row for row in responses}
        unknown = [code for code in codes if code not in by_code]
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown response code: {unknown[0]}.")
        org_ids = {row["organization_id"] for row in responses}
        if len(org_ids) != 1:
            raise HTTPException(status_code=422, detail="One CSV upload must contain records for only one organization.")
        organization_id = next(iter(org_ids))
        require_org(user, organization_id, ("org_admin","editor"))
        batch = conn.execute("""INSERT INTO import_batches(organization_id,source_name,file_name,rows_received,rows_imported,rows_skipped,status)
            VALUES (%s,'CSV upload',%s,%s,0,0,'completed') RETURNING id""", (organization_id,safe_name,len(parsed))).fetchone()
        source = conn.execute("SELECT id FROM funding_sources WHERE source_type='csv_import' ORDER BY id LIMIT 1").fetchone()
        for line,code,kind,amount,currency,recorded_on,reference,source_reference,description in parsed:
            inserted = conn.execute("""INSERT INTO funding_records(response_id,source_id,import_batch_id,record_type,amount,currency,recorded_on,reference,description,source_reference)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(response_id,source_id,source_reference) DO NOTHING RETURNING id""",
                (by_code[code]["id"],source["id"],batch["id"],kind,amount,currency,recorded_on,reference,description,source_reference)).fetchone()
            if inserted:
                imported += 1
            else:
                skipped += 1
        status = "completed_with_skips" if skipped else "completed"
        conn.execute("UPDATE import_batches SET rows_imported=%s,rows_skipped=%s,status=%s WHERE id=%s", (imported,skipped,status,batch["id"]))
        audit(conn,user,organization_id,"imported","funding_batch",batch["id"],{"file":safe_name,"created":imported,"skipped":skipped})
    return {"batch_id":batch["id"],"rows_received":len(parsed),"rows_imported":imported,"rows_skipped":skipped,"status":status}


@app.get("/api/imports")
def import_history(user: dict = Depends(current_user)):
    return rows("SELECT id,source_name,file_name,rows_received,rows_imported,rows_skipped,status,created_at FROM import_batches WHERE organization_id=ANY(%s) ORDER BY created_at DESC LIMIT 30", (list(user["memberships"]),))


@app.get("/api/issues")
def issues(user: dict = Depends(current_user)):
    return rows("""SELECT i.id,i.issue_type,i.description,i.status,i.created_at,r.code AS response_code,
        f.reference,f.amount,f.currency FROM reconciliation_issues i JOIN responses r ON r.id=i.response_id
        LEFT JOIN funding_records f ON f.id=i.funding_record_id JOIN organization_memberships m ON m.organization_id=r.organization_id AND m.user_id=%s
        ORDER BY i.created_at DESC""", (user["id"],))


@app.patch("/api/issues/{issue_id}/resolve")
def resolve_issue(issue_id: int, user: dict = Depends(current_user)):
    with pool.connection() as conn:
        item = conn.execute("""UPDATE reconciliation_issues i SET status='resolved',resolved_at=now()
            FROM responses r WHERE i.id=%s AND i.response_id=r.id AND i.status='open'
            AND r.organization_id=ANY(%s) RETURNING i.id,i.response_id,r.organization_id""",
            (issue_id,list(user["memberships"]))).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Open issue not found.")
        require_org(user,item["organization_id"],("org_admin","editor","reviewer"))
        audit(conn,user,item["organization_id"],"resolved","reconciliation_issue",item["id"])
    return {"id": item["id"], "status": "resolved"}


@app.get("/api/audit")
def audit_history(user: dict = Depends(current_user)):
    return rows("SELECT id,action,entity_type,entity_id,actor_label,details,created_at FROM audit_events WHERE organization_id=ANY(%s) ORDER BY created_at DESC LIMIT 30", (list(user["memberships"]),))
