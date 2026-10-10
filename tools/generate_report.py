from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Flowable, KeepTogether,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "relieftrail-funding-workspace-report.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
INK = colors.HexColor("#25372d")
GREEN = colors.HexColor("#167653")
PALE = colors.HexColor("#edf5ef")
LINE = colors.HexColor("#dce5dd")
MUTED = colors.HexColor("#708078")


class ERDiagram(Flowable):
    def __init__(self):
        super().__init__()
        self.width = 480
        self.height = 205

    def draw(self):
        c = self.canv
        nodes = {
            "ORGANIZATIONS": (8, 145, 112, 42),
            "USERS": (185, 145, 88, 42),
            "MEMBERSHIPS": (332, 145, 118, 42),
            "RESPONSES": (8, 77, 112, 42),
            "FUNDING_RECORDS": (185, 77, 130, 42),
            "FUNDING_SOURCES": (360, 77, 112, 42),
            "IMPORT_BATCHES": (8, 8, 112, 42),
            "RECONCILIATION_ISSUES": (185, 8, 150, 42),
            "AUDIT_EVENTS": (360, 8, 112, 42),
        }
        links = [
            ("ORGANIZATIONS", "RESPONSES", "1 : many"),
            ("ORGANIZATIONS", "MEMBERSHIPS", "1 : many"),
            ("USERS", "MEMBERSHIPS", "1 : many"),
            ("RESPONSES", "FUNDING_RECORDS", "1 : many"),
            ("FUNDING_SOURCES", "FUNDING_RECORDS", "1 : many"),
            ("IMPORT_BATCHES", "FUNDING_RECORDS", "0..1 : many"),
            ("RESPONSES", "RECONCILIATION_ISSUES", "1 : many"),
            ("ORGANIZATIONS", "AUDIT_EVENTS", "1 : many"),
        ]
        for a, b, label in links:
            x1, y1, w1, h1 = nodes[a]
            x2, y2, w2, h2 = nodes[b]
            p1 = (x1 + w1 / 2, y1 + h1 / 2)
            p2 = (x2 + w2 / 2, y2 + h2 / 2)
            c.setStrokeColor(colors.HexColor("#9bb5a2"))
            c.setLineWidth(0.8)
            c.line(*p1, *p2)
        for name, (x, y, w, h) in nodes.items():
            c.setFillColor(PALE)
            c.setStrokeColor(LINE)
            c.roundRect(x, y, w, h, 5, fill=1, stroke=1)
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 7.1)
            c.drawCentredString(x + w / 2, y + h / 2 - 2.5, name)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7)
        c.drawString(8, -3, "Each line represents a foreign-key relationship; membership connects users to organizations.")


class InterfacePreview(Flowable):
    def __init__(self):
        super().__init__()
        self.width = 480
        self.height = 245

    def draw(self):
        c = self.canv
        c.setFillColor(colors.HexColor("#f5f7f4"))
        c.roundRect(0, 0, 480, 230, 8, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.roundRect(8, 8, 95, 214, 6, fill=1, stroke=0)
        c.setFillColor(GREEN)
        c.roundRect(17, 196, 14, 14, 4, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(37, 201, "relieftrail")
        c.setFont("Helvetica", 6.2)
        c.setFillColor(MUTED)
        c.drawString(37, 192, "FUNDING WORKSPACE")
        for i, label in enumerate(["Overview", "Responses", "Awards & budgets", "Reports", "Funding records"]):
            y = 170 - i * 19
            if i == 0:
                c.setFillColor(PALE)
                c.roundRect(14, y - 4, 82, 15, 4, fill=1, stroke=0)
            c.setFillColor(GREEN if i == 0 else MUTED)
            c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 6.7)
            c.drawString(21, y, label)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(117, 202, "Funding operations")
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.5)
        c.drawString(117, 191, "Fictional organization workspace - sample data")
        cards = [(117, 147, "ACTIVE RESPONSES", "2"), (205, 147, "CONTRIBUTIONS", "$30.4k"), (293, 147, "DISBURSEMENTS", "$6.0k"), (381, 147, "OPEN REVIEWS", "3")]
        for x, y, label, value in cards:
            c.setFillColor(colors.white)
            c.roundRect(x, y, 80, 34, 4, fill=1, stroke=0)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 5.4)
            c.drawString(x + 6, y + 22, label)
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(x + 6, y + 8, value)
        c.setFillColor(colors.white)
        c.roundRect(117, 61, 224, 75, 5, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(126, 123, "Reported funding over time")
        c.setStrokeColor(LINE)
        for y in [78, 94, 110]:
            c.line(128, y, 328, y)
        c.setStrokeColor(GREEN)
        c.setLineWidth(2)
        c.line(135, 82, 170, 92)
        c.line(170, 92, 205, 87)
        c.line(205, 87, 240, 107)
        c.line(240, 107, 275, 101)
        c.line(275, 101, 316, 117)
        c.setFillColor(colors.white)
        c.roundRect(350, 61, 122, 75, 5, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(359, 123, "Needs review")
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6)
        c.drawString(359, 107, "Missing source reference")
        c.drawString(359, 93, "Possible duplicate")
        c.drawString(359, 79, "Amount mismatch")
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Oblique", 6.2)
        c.drawString(8, -10, "Illustrative interface preview based on the frontend; not a live deployment or verified database screenshot.")


class Report(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=A4, rightMargin=17*mm, leftMargin=17*mm, topMargin=18*mm, bottomMargin=17*mm, title="ReliefTrail ResponseHub - Project Report", author="ReliefTrail portfolio project")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates(PageTemplate(id="main", frames=frame, onPage=self.decorate))

    def decorate(self, canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setStrokeColor(LINE)
        canvas.line(17*mm, 13*mm, w-17*mm, 13*mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(17*mm, 8*mm, "ReliefTrail ResponseHub | Fictional portfolio demo")
        canvas.drawRightString(w-17*mm, 8*mm, f"{doc.page}")
        canvas.restoreState()


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=25, leading=30, textColor=INK, alignment=TA_LEFT, spaceAfter=10))
styles.add(ParagraphStyle(name="Kicker", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=GREEN, spaceAfter=8))
styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=INK, spaceBefore=5, spaceAfter=8))
styles.add(ParagraphStyle(name="Sub", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=GREEN, spaceBefore=8, spaceAfter=4))
styles.add(ParagraphStyle(name="Body2", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.5, leading=12, textColor=INK, spaceAfter=6))
styles.add(ParagraphStyle(name="Small2", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.2, leading=9.5, textColor=INK))


def para(text, style="Body2"):
    return Paragraph(text, styles[style])


def bullet(text):
    return para("- " + text)


story = [
    Spacer(1, 15*mm),
    para("DATABASE MANAGEMENT SYSTEMS | MINI PROJECT", "Kicker"),
    para("ReliefTrail ResponseHub", "CoverTitle"),
    para("An organization-scoped response and grant workspace linking approved work, restricted awards, budget lines, reported spending, donor deadlines, and human review.", "Body2"),
    Spacer(1, 7*mm),
    InterfacePreview(),
    Spacer(1, 8*mm),
    para("Project stage", "Sub"),
    para("Portfolio demo: React + TypeScript frontend, FastAPI backend, and PostgreSQL schema with fictional sample records. This report uses an illustrative interface preview rather than a screenshot from a live database-backed deployment.", "Body2"),
    para("Safety note", "Sub"),
    para("All data and demo credentials are fictional. The app does not accept donations, move money, or verify aid delivery. This project is not approved for real organizational data or production use.", "Body2"),
    PageBreak(),
    para("1. Introduction", "Section"),
    para("ReliefTrail ResponseHub is a database-backed portfolio application for a fictional nonprofit team. It links response records to awards and restricted allocations, lets staff record reported spending, tracks reporting milestones, and supports human review and audit history.", "Body2"),
    para("2. Problem statement", "Section"),
    para("Funding details may arrive in separate spreadsheets and records. This makes it harder to see which response a line belongs to, spot missing references, and explain what a reviewer changed. The project demonstrates a small internal workflow that links the records and preserves the source context. It is a learning scenario, not a verified statement about a particular organization's operational pain.", "Body2"),
    para("3. Objectives", "Section"),
    bullet("Design normalized relational entities with primary keys, foreign keys, constraints, indexes, and organization membership."),
    bullet("Build a friendly interface for response create/read/update/delete, CSV import/export, review flags, and activity history."),
    bullet("Use SQL joins, aggregates, a reporting view, transaction-backed writes, and a trigger."),
    bullet("Demonstrate authentication and role-aware organization access checks in a controlled fictional demo."),
    bullet("Test session/CSRF behavior, role denial, CSV validation/import handling, and PostgreSQL integrity rules."),
    para("4. Technologies", "Section"),
    Table([[para("Layer", "Small2"), para("Technology", "Small2"), para("Purpose", "Small2")],
           [para("Frontend", "Small2"), para("React, TypeScript, Vite", "Small2"), para("Responsive workspace interface", "Small2")],
           [para("Backend", "Small2"), para("Python, FastAPI, Pydantic", "Small2"), para("JSON API, validation, authorization", "Small2")],
           [para("Database", "Small2"), para("PostgreSQL 16", "Small2"), para("Relational storage, views, trigger, transactions", "Small2")],
           [para("Local run", "Small2"), para("Docker Compose, pnpm", "Small2"), para("Repeatable demo setup", "Small2")]],
          colWidths=[28*mm, 54*mm, 93*mm], style=TableStyle([("BACKGROUND",(0,0),(-1,0),PALE),("TEXTCOLOR",(0,0),(-1,0),GREEN),("GRID",(0,0),(-1,-1),.35,LINE),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)])),
    PageBreak(),
    para("5. ER diagram and database schema", "Section"),
    para("The design separates organization, identity, response, funding, review, and audit facts. Foreign keys show how those facts connect.", "Body2"),
    ERDiagram(),
    Spacer(1, 7*mm),
    Table([[para("Table", "Small2"), para("Key columns and purpose", "Small2")],
           [para("organizations", "Small2"), para("id PK; organization name and type", "Small2")],
           [para("users / organization_memberships", "Small2"), para("user_id + organization_id composite PK; role-based membership", "Small2")],
           [para("responses", "Small2"), para("id PK; organization_id FK; unique response code; status, dates, summary", "Small2")],
           [para("funders / funding_awards", "Small2"), para("Organization-scoped donor identity, award ceiling, dates, restrictions", "Small2")],
           [para("award_allocations / reporting_milestones", "Small2"), para("Response budget line and due/submitted/accepted/returned report state", "Small2")],
           [para("user_sessions / login_throttles", "Small2"), para("One-way session verifier/revocation; keyed failed-login throttle state", "Small2")],
           [para("funding_sources / import_batches", "Small2"), para("Source identity and organization-scoped CSV import summaries", "Small2")],
           [para("funding_records", "Small2"), para("response_id/source_id/import_batch_id FKs; type, amount, currency, date, references", "Small2")],
           [para("reconciliation_issues", "Small2"), para("Response FK and optional funding-record FK; issue state", "Small2")],
           [para("audit_events", "Small2"), para("Organization-scoped action and actor history; append-only trigger", "Small2")]],
          colWidths=[55*mm, 120*mm], style=TableStyle([("BACKGROUND",(0,0),(-1,0),PALE),("GRID",(0,0),(-1,-1),.35,LINE),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)])),
    para("Normalization", "Sub"),
    para("Related facts are stored once and connected with keys: response rows refer to organizations; funding rows refer to responses and sources. The reporting view calculates totals from funding rows instead of copying totals into response rows. This reduces duplicate data and update anomalies, following a practical third-normal-form style.", "Body2"),
    PageBreak(),
    para("6. SQL queries and implemented features", "Section"),
    bullet("Parameterized SELECT queries join responses, organizations, funding sources, and review issues."),
    bullet("Aggregate queries calculate contribution, disbursement, response, and issue summaries within the user's organization memberships."),
    bullet("The response_funding_summary view derives response totals from funding records."),
    bullet("Foreign keys, uniqueness rules, and CHECK constraints protect allowed statuses, roles, currency, positive amounts, and response codes."),
    bullet("CSV validation completes before database writes; accepted rows and the import batch/audit row commit in one transaction. Duplicate source references are skipped."),
    bullet("An append-only PostgreSQL trigger rejects UPDATE and DELETE on audit_events."),
    bullet("Argon2id password hashes, opaque revocable HttpOnly cookie sessions, CSRF checks, login throttling, and exact CORS origins protect the demo sign-in boundary."),
    bullet("The API reloads active-account and organization membership state and checks roles server-side. Review responses, awards, team roles, reports, and flags by organization scope."),
    bullet("Award creation groups award, allocation, reporting milestone, and audit event in one transaction. PostgreSQL triggers enforce award and disbursement ceilings."),
    bullet("Only unused draft responses can be deleted; a funding or review history blocks deletion. The database trigger rejects changes to audit events."),
    para("Example relationship query", "Sub"),
    Table([[para("SELECT r.code, o.name AS organization, f.record_type, f.amount, s.name AS source<br/>FROM funding_records f<br/>JOIN responses r ON r.id = f.response_id<br/>JOIN organizations o ON o.id = r.organization_id<br/>JOIN funding_sources s ON s.id = f.source_id;", "Small2")]], colWidths=[175*mm], style=TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#f5f7f4")),("BOX",(0,0),(-1,-1),.5,LINE),("LEFTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)])),
    para("7. Interface preview", "Section"),
    para("The preview summarizes the dashboard style and is illustrative. The frontend also includes dedicated response, awards/budgets, reporting calendar, funding, review queue, team access, and activity screens. It is not proof of a deployed service.", "Body2"),
    InterfacePreview(),
    PageBreak(),
    para("8. Conclusion", "Section"),
    para("This project demonstrates an end-to-end database application: a typed frontend calls an API, the API validates requests and enforces tenant roles, and PostgreSQL protects linked grant records with constraints, a reporting view, triggers, and transactional writes. It is production-minded portfolio work, not certified or suitable for real operations.", "Body2"),
    para("9. Future scope", "Section"),
    bullet("Add invited-account onboarding, recovery, MFA, independent authorization review, and production operations controls."),
    bullet("Add schema migration tooling, monitoring, tested backups, an incident process, and independent security review."),
    bullet("Improve reconciliation rules, spreadsheet column mapping, and correction workflow."),
    bullet("Explore human-reviewed AI suggestions for mapping columns or drafting reports with source-row citations."),
    bullet("Explore connecting the separate contract prototype as a read-only event source after validating provenance and integrity; the projects are not currently integrated."),
    bullet("Interview NGO grants and finance staff before making adoption or commercial claims."),
    para("Repository and setup", "Sub"),
    para("The repository includes source code, SQL schema and sample data, query examples, security and architecture docs, setup instructions, a CI workflow, and backend tests. Local API docs are available at /docs in demo mode. Local checks currently pass 14 tests; three PostgreSQL integration checks require a disposable database and are skipped when it is unavailable.", "Body2"),
]

Report(OUTPUT).build(story)
print(OUTPUT)
