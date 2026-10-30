from contextlib import contextmanager

from backend.blockchain_sync_worker import store_batch


class FakeCursor:
    def __init__(self, response=None):
        self.response = response
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=()):
        self.executions.append((sql, params))
        if "SELECT id FROM responses" in sql:
            return self
        return self

    def fetchone(self):
        return {"id": 17} if self.response else None


class FakeConnection:
    def __init__(self, response=None):
        self.fake_cursor = FakeCursor(response)
        self.transactions = 0

    @contextmanager
    def transaction(self):
        self.transactions += 1
        yield

    def cursor(self):
        return self.fake_cursor


def test_event_amount_and_deduplication_key_are_preserved():
    conn = FakeConnection(response=True)
    event = {
        "name": "DonationReceived",
        "args": {
            "donor": "0x1111111111111111111111111111111111111111",
            "responseCode": "FLOOD-26-01",
            "amount": 1234567890123456789,
        },
        "transactionHash": bytes.fromhex("22" * 32),
        "blockNumber": 42,
        "blockHash": bytes.fromhex("33" * 32),
        "logIndex": 3,
    }

    store_batch(conn, 31337, "0x4444444444444444444444444444444444444444", 40, 50, [event])

    insert = next(item for item in conn.fake_cursor.executions if "INSERT INTO blockchain_events" in item[0])
    assert insert[1][11] == "1234567890123456789"
    assert insert[1][15] == "confirmed"
    assert "UNIQUE (chain_id,contract_address,transaction_hash,log_index)" not in insert[0]
    assert "ON CONFLICT (chain_id,contract_address,transaction_hash,log_index) DO NOTHING" in insert[0]
    assert conn.transactions == 1


def test_unknown_response_stays_unmatched_without_fake_response_id():
    conn = FakeConnection(response=False)
    event = {
        "name": "ReliefPaid",
        "args": {
            "recipient": "0x1111111111111111111111111111111111111111",
            "responseCode": "UNKNOWN-01",
            "amount": 100,
            "purpose": "sample payout",
            "evidenceHash": bytes.fromhex("55" * 32),
        },
        "actor_address": "0x6666666666666666666666666666666666666666",
        "transactionHash": bytes.fromhex("22" * 32),
        "blockNumber": 42,
        "blockHash": bytes.fromhex("33" * 32),
        "logIndex": 4,
    }

    store_batch(conn, 31337, "0x4444444444444444444444444444444444444444", 40, 50, [event])

    insert = next(item for item in conn.fake_cursor.executions if "INSERT INTO blockchain_events" in item[0])
    assert insert[1][6] is None
    assert insert[1][7] == "UNKNOWN-01"
    assert insert[1][15] == "unmatched"
    assert insert[1][9] == "0x6666666666666666666666666666666666666666"
    assert conn.transactions == 1
