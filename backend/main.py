"""ReliefTrail Funding Workspace API. Demo credentials and sample data are fictional."""
import base64
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

import psycopg
from fastapi import Depends, FastAPI, File, HTTPException, Response as FastAPIResponse, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from psycopg.types.json import Jsonb

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://relieftrail:local_demo_only@localhost:5432/relieftrail")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "local-demo-only-change-before-deployment")
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "admin@relieftrail.test").strip().lower()
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo-change-me")
pool = ConnectionPool(DATABASE_URL, kwargs={"row_factory": dict_row}, open=False)
app = FastAPI(title="ReliefTrail Funding Workspace", version="0.2.0", description="Organization-scoped demo API for relief funding reconciliation.")
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")], allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])
bearer = HTTPBearer(auto_error=False)


def password_digest(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def password_matches(password: str, encoded: str) -> bool:
    try:
        _, rounds, salt, expected = encoded.split("$", 3)
        actual = password_digest(password, base64.urlsafe_b64decode(salt + "=" * (-len(salt) % 4))).split("$", 3)[3]
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_encode(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signing = f"{header}.{body}".encode()
    signature = base64.urlsafe_b64encode(hmac.new(APP_SECRET_KEY.encode(), signing, hashlib.sha256).digest()).decode().rstrip("=")
    return f"{header}.{body}.{signature}"


def token_decode(token: str) -> dict:
    try:
        header, body, signature = token.split(".")
        signing = f"{header}.{body}".encode()
        expected = base64.urlsafe_b64encode(hmac.new(APP_SECRET_KEY.encode(), signing, hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload["exp"]) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired token")
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please sign in again.") from exc


def rows(sql, params=()):
    with pool.connection() as conn:
        return conn.execute(sql, params).fetchall()


def ensure_demo_user():
    if os.getenv("APP_ENV", "local") != "demo":
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
                VALUES (%s,%s,%s) ON CONFLICT(email) DO UPDATE SET is_active=users.is_active RETURNING id""",
                (email,full_name,password_digest(password))).fetchone()
            conn.execute("""INSERT INTO organization_memberships(user_id,organization_id,role)
                VALUES (%s,1,%s) ON CONFLICT(user_id,organization_id) DO UPDATE SET role=excluded.role""", (user["id"],role))


@app.on_event("startup")
def open_pool():
    pool.open(wait=True)
    ensure_demo_user()


@app.on_event("shutdown")
def close_pool():
    pool.close()


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
    title: str = Field(default=None, min_length=3, max_length=160)
    location: str = Field(default=None, min_length=2, max_length=120)
    summary: str = Field(default=None, min_length=10, max_length=1000)
    status: Literal["draft", "in_review", "approved", "closed"] = None
    start_date: date | None = None

    @field_validator("title", "location", "summary", mode="before")
    @classmethod
    def trim_update_text(cls, value):
        return value.strip() if isinstance(value, str) else value


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    payload = token_decode(credentials.credentials)
    found = rows("""SELECT u.id,u.email,u.full_name,u.is_active,m.organization_id,m.role
        FROM users u JOIN organization_memberships m ON m.user_id=u.id WHERE u.id=%s ORDER BY m.organization_id""", (payload.get("sub"),))
    if not found or not found[0]["is_active"]:
        raise HTTPException(status_code=401, detail="This account is unavailable.")
    user = {"id": found[0]["id"], "email": found[0]["email"], "full_name": found[0]["full_name"],
            "memberships": {row["organization_id"]: row["role"] for row in found}}
    return user


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


@app.get("/api/health")
def health():
    rows("SELECT 1")
    return {"status": "ok", "database": "connected", "mode": os.getenv("APP_ENV", "local")}


@app.post("/api/auth/login")
def login(payload: LoginRequest):
    found = rows("SELECT id,email,full_name,password_hash,is_active FROM users WHERE email=%s", (payload.email.strip().lower(),))
    if not found or not found[0]["is_active"] or not password_matches(payload.password, found[0]["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    user = found[0]
    memberships = rows("""SELECT m.organization_id,m.role,o.name FROM organization_memberships m
        JOIN organizations o ON o.id=m.organization_id WHERE m.user_id=%s ORDER BY o.name""", (user["id"],))
    token = token_encode({"sub": user["id"], "exp": int((datetime.now(timezone.utc) + timedelta(hours=8)).timestamp())})
    return {"access_token": token, "token_type": "bearer", "user": {"full_name": user["full_name"], "email": user["email"]},
            "organizations": memberships}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    organizations = rows("""SELECT o.id,o.name,o.kind,m.role FROM organization_memberships m
        JOIN organizations o ON o.id=m.organization_id WHERE m.user_id=%s ORDER BY o.name""", (user["id"],))
    return {"full_name": user["full_name"], "email": user["email"], "organizations": organizations}


@app.get("/api/organizations")
def organizations(user: dict = Depends(current_user)):
    return rows("""SELECT o.id,o.name,o.kind,m.role FROM organizations o
        JOIN organization_memberships m ON m.organization_id=o.id WHERE m.user_id=%s ORDER BY o.name""", (user["id"],))


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
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
        required = {"response_code","record_type","amount","currency","recorded_on","reference","source_reference"}
        if not required.issubset({name.strip().lower() for name in (reader.fieldnames or []) if name}):
            raise HTTPException(status_code=422, detail="CSV needs response_code, record_type, amount, currency, recorded_on, reference, and source_reference columns.")
        if len(reader.fieldnames or []) > 30:
            raise HTTPException(status_code=422, detail="The CSV has too many columns.")
        parsed = []
        for line_number, raw in enumerate(reader, start=2):
            if line_number > 1002:
                raise HTTPException(status_code=422, detail="A file can contain at most 1,000 data rows.")
            row = {(key or "").strip().lower(): (value or "").strip() for key,value in raw.items()}
            if not any(row.values()):
                continue
            code,kind = row["response_code"].upper(),row["record_type"].lower()
            amount = Decimal(row["amount"])
            currency,date_value = row["currency"].upper(),date.fromisoformat(row["recorded_on"])
            reference,source_reference = row["reference"],row["source_reference"]
            if kind not in ("contribution","disbursement") or not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2 or amount.adjusted() > 15:
                raise ValueError(f"Row {line_number}: type must be contribution/disbursement and amount must be positive with at most two decimal places.")
            if currency != "USD" or len(reference) < 3 or len(reference) > 120 or not source_reference or len(source_reference) > 120:
                raise ValueError(f"Row {line_number}: currency, reference, or source_reference is invalid.")
            if len(row.get("description") or "") > 1000:
                raise ValueError(f"Row {line_number}: description must be 1,000 characters or fewer.")
            parsed.append((line_number,code,kind,amount,currency,date_value,reference,source_reference,row.get("description") or None))
        if not parsed:
            raise HTTPException(status_code=422, detail="The CSV contains no funding rows.")
    except HTTPException:
        raise
    except (UnicodeDecodeError,csv.Error,KeyError,ValueError,InvalidOperation,ArithmeticError) as exc:
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
            if inserted: imported += 1
            else: skipped += 1
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

