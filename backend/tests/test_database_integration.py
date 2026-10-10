import os

import psycopg
import pytest


DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="Set TEST_DATABASE_URL to a disposable PostgreSQL database.")


def test_summary_view_aggregates_seeded_funding():
    with psycopg.connect(DATABASE_URL) as conn:
        row = conn.execute("SELECT contributions,disbursements,record_count FROM response_funding_summary WHERE code='FLOOD-26-01'").fetchone()
    assert row[0] > 0
    assert row[1] == 4700
    assert row[2] == 5


def test_database_rejects_disbursement_over_budget():
    with psycopg.connect(DATABASE_URL) as conn:
        allocation = conn.execute("""SELECT al.id,al.response_id,al.budget_amount,coalesce(sum(f.amount),0)
            FROM award_allocations al LEFT JOIN funding_records f ON f.award_allocation_id=al.id AND f.record_type='disbursement'
            GROUP BY al.id ORDER BY al.id LIMIT 1""").fetchone()
        source_id = conn.execute("SELECT id FROM funding_sources WHERE source_type='manual' LIMIT 1").fetchone()[0]
        with pytest.raises(psycopg.errors.RaiseException, match="exceed the approved award budget line"):
            conn.execute("""INSERT INTO funding_records(response_id,award_allocation_id,source_id,record_type,amount,currency,recorded_on,reference,source_reference)
                VALUES (%s,%s,%s,'disbursement',%s,'USD',CURRENT_DATE,'TEST-OVER-BUDGET','TEST-OVER-BUDGET')""",
                (allocation[1], allocation[0], source_id, allocation[2] + 1))
        conn.rollback()


def test_audit_table_rejects_update():
    with psycopg.connect(DATABASE_URL) as conn:
        audit_id = conn.execute("SELECT id FROM audit_events ORDER BY id LIMIT 1").fetchone()[0]
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute("UPDATE audit_events SET actor_label='changed' WHERE id=%s", (audit_id,))
        conn.rollback()
