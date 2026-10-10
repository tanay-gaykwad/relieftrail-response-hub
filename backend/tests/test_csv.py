import asyncio
import io
from contextlib import contextmanager

import pytest
from starlette.datastructures import UploadFile

from backend import main
from backend.main import parse_funding_csv


def test_csv_parser_normalizes_valid_row():
    parsed = parse_funding_csv(
        b"response_code,record_type,amount,currency,recorded_on,reference,source_reference,description\n"
        b"flood-26-01,contribution,125.50,usd,2026-10-01,Partner-1,source-1,Grant payment\n"
    )
    assert len(parsed) == 1
    assert parsed[0][1:8] == ("FLOOD-26-01", "contribution", parsed[0][3], "USD", parsed[0][5], "Partner-1", "source-1")
    assert str(parsed[0][3]) == "125.50"


@pytest.mark.parametrize("row", [
    "FLOOD-26-01,contribution,0,USD,2026-10-01,Partner-1,source-1,",
    "FLOOD-26-01,refund,5,USD,2026-10-01,Partner-1,source-1,",
    "FLOOD-26-01,contribution,1.001,USD,2026-10-01,Partner-1,source-1,",
    "FLOOD-26-01,contribution,5,EUR,2026-10-01,Partner-1,source-1,",
    "FLOOD-26-01,contribution,5,USD,not-a-date,Partner-1,source-1,",
])
def test_csv_parser_rejects_invalid_rows(row):
    payload = ("response_code,record_type,amount,currency,recorded_on,reference,source_reference,description\n" + row + "\n").encode()
    with pytest.raises(ValueError):
        parse_funding_csv(payload)


def test_csv_parser_rejects_missing_columns_and_non_utf8():
    with pytest.raises(ValueError, match="needs"):
        parse_funding_csv(b"response_code,amount\nFLOOD-26-01,10\n")
    with pytest.raises(ValueError, match="UTF-8"):
        parse_funding_csv(b"\xff\xfe")


def test_csv_parser_caps_row_count():
    header = "response_code,record_type,amount,currency,recorded_on,reference,source_reference\n"
    row = "FLOOD-26-01,contribution,1,USD,2026-10-01,Partner-1,source-1\n"
    with pytest.raises(ValueError, match="1,000"):
        parse_funding_csv((header + row * 1002).encode())


def test_csv_import_skips_duplicates_and_records_one_batch(monkeypatch):
    class Result:
        def __init__(self, rows=()):
            self.rows = list(rows)

        def fetchall(self):
            return self.rows

        def fetchone(self):
            return self.rows[0] if self.rows else None

    class ImportDatabase:
        def __init__(self):
            self.opens = 0
            self.inserted = set()
            self.insert_calls = 0

        @contextmanager
        def connection(self):
            self.opens += 1
            database = self

            class Connection:
                def execute(self, sql, params=()):
                    if "SELECT id,code,organization_id FROM responses" in sql:
                        return Result([{"id": 3, "code": "FLOOD-26-01", "organization_id": 1}])
                    if "INSERT INTO import_batches" in sql:
                        return Result([{"id": 12}])
                    if "SELECT id FROM funding_sources" in sql:
                        return Result([{"id": 2}])
                    if "INSERT INTO funding_records" in sql:
                        database.insert_calls += 1
                        source_ref = params[9]
                        if source_ref in database.inserted:
                            return Result()
                        database.inserted.add(source_ref)
                        return Result([{"id": 100 + database.insert_calls}])
                    return Result()

            yield Connection()

    fake_db = ImportDatabase()
    monkeypatch.setattr(main, "pool", fake_db)
    payload = b"response_code,record_type,amount,currency,recorded_on,reference,source_reference\nFLOOD-26-01,contribution,5,USD,2026-10-01,Ref-1,source-1\nFLOOD-26-01,contribution,5,USD,2026-10-01,Ref-2,source-1\n"
    upload = UploadFile(filename="records.csv", file=io.BytesIO(payload))
    user = {"id": 4, "full_name": "Editor", "memberships": {1: "editor"}}

    result = asyncio.run(main.import_csv(upload, user))

    assert result["rows_imported"] == 1
    assert result["rows_skipped"] == 1
    assert fake_db.insert_calls == 2
    assert fake_db.opens == 1
