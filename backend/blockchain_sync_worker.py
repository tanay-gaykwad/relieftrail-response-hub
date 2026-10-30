"""Local/testnet EVM event indexer for the ReliefTrail ResponseHub demo.

Reads events from the configured contract and stores exact raw token units.
It never moves funds or attributes unmatched events to an organization.
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from typing import Any

import psycopg
from psycopg.rows import dict_row
from web3 import Web3

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
ABI = [
    {
        "anonymous": False, "type": "event", "name": "DonationReceived",
        "inputs": [
            {"indexed": True, "name": "donor", "type": "address"},
            {"indexed": False, "name": "responseCode", "type": "string"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "newBalance", "type": "uint256"},
        ],
    },
    {
        "anonymous": False, "type": "event", "name": "ReliefPaid",
        "inputs": [
            {"indexed": True, "name": "recipient", "type": "address"},
            {"indexed": False, "name": "responseCode", "type": "string"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "purpose", "type": "string"},
            {"indexed": False, "name": "evidenceHash", "type": "bytes32"},
        ],
    },
]


def config() -> dict[str, Any]:
    required = ("EVM_RPC_URL", "EVM_CONTRACT_ADDRESS", "DATABASE_URL", "EVM_START_BLOCK")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")
    start_block = int(os.environ["EVM_START_BLOCK"])
    confirmations = int(os.getenv("EVM_CONFIRMATIONS", "0"))
    expected_chain_id = int(os.getenv("EVM_CHAIN_ID", "31337"))
    if start_block < 0 or confirmations < 0 or expected_chain_id <= 0:
        raise ValueError("EVM_START_BLOCK and EVM_CONFIRMATIONS must be non-negative; EVM_CHAIN_ID must be positive.")
    address = Web3.to_checksum_address(os.environ["EVM_CONTRACT_ADDRESS"])
    return {
        "rpc": os.environ["EVM_RPC_URL"],
        "address": address,
        "database_url": os.environ["DATABASE_URL"],
        "start_block": start_block,
        # Zero is appropriate for the local Hardhat demo, which has no reorgs.
        # Set a positive value when indexing a testnet or other live chain.
        "confirmations": confirmations,
        "poll_seconds": max(1, int(os.getenv("EVM_POLL_SECONDS", "5"))),
        "batch_size": min(2000, max(1, int(os.getenv("EVM_BATCH_SIZE", "200")))),
        "expected_chain_id": expected_chain_id,
    }


def store_batch(conn, chain_id: int, address: str, start: int, end: int, events: list[dict]) -> None:
    """Persist each event and advance the cursor in one transaction."""
    with conn.transaction():
        with conn.cursor() as cur:
            for event in events:
                args = event["args"]
                code = args["responseCode"]
                response = cur.execute("SELECT id FROM responses WHERE code=%s", (code,)).fetchone()
                response_id = response["id"] if response else None
                if event["name"] == "DonationReceived":
                    actor = args["donor"]
                    recipient = None
                    purpose = None
                    evidence = None
                    event_type = "donation"
                else:
                    actor = event["actor_address"]
                    recipient = args["recipient"]
                    purpose = args["purpose"]
                    evidence = Web3.to_hex(args["evidenceHash"])
                    event_type = "payout"
                cur.execute(
                    """INSERT INTO blockchain_events
                       (chain_id,contract_address,transaction_hash,log_index,block_number,block_hash,
                        response_id,response_code,event_type,actor_address,recipient_address,amount_raw,
                        asset_address,asset_decimals,purpose,evidence_hash,confirmation_status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,18,%s,%s,%s)
                       ON CONFLICT (chain_id,contract_address,transaction_hash,log_index) DO NOTHING""",
                    (chain_id,address,Web3.to_hex(event["transactionHash"]),event["logIndex"],event["blockNumber"],
                     Web3.to_hex(event["blockHash"]),response_id,code,event_type,actor,recipient,
                     str(args["amount"]),ZERO_ADDRESS,purpose,evidence,
                     "confirmed" if response_id is not None else "unmatched"),
                )
            cur.execute(
                """INSERT INTO blockchain_sync_state(chain_id,contract_address,last_synced_block)
                   VALUES (%s,%s,%s)
                   ON CONFLICT (chain_id,contract_address) DO UPDATE
                   SET last_synced_block=GREATEST(blockchain_sync_state.last_synced_block,EXCLUDED.last_synced_block),
                       updated_at=now()""",
                (chain_id,address,end),
            )


def scan_once(w3: Web3, contract: Any, conn, settings: dict) -> int:
    chain_id = w3.eth.chain_id
    if chain_id != settings["expected_chain_id"]:
        raise RuntimeError(f"Connected chain {chain_id}, expected {settings['expected_chain_id']}")
    address = settings["address"]
    with conn.cursor() as cur:
        row = cur.execute(
            "SELECT last_synced_block FROM blockchain_sync_state WHERE chain_id=%s AND contract_address=%s",
            (chain_id,address),
        ).fetchone()
    start = row["last_synced_block"] + 1 if row else settings["start_block"]
    safe_head = w3.eth.block_number - settings["confirmations"]
    if safe_head < start:
        return 0
    end = min(start + settings["batch_size"] - 1, safe_head)
    events = []
    for name in ("DonationReceived", "ReliefPaid"):
        decoder = getattr(contract.events, name)()
        logs = decoder.get_logs(from_block=start, to_block=end)
        for log in logs:
            actor = log["args"]["donor"] if name == "DonationReceived" else w3.eth.get_transaction(log["transactionHash"])["from"]
            events.append({"name": name, "args": log["args"], "actor_address": actor, **log})
    events.sort(key=lambda item: (item["blockNumber"], item["logIndex"]))
    store_batch(conn, chain_id, address, start, end, events)
    logging.info("Scanned blocks %s-%s; indexed %s events", start, end, len(events))
    return len(events)


def main() -> None:
    parser = argparse.ArgumentParser(description="Index events from the configured ReliefTrail contract.")
    parser.add_argument("--once", action="store_true", help="scan one confirmed block batch and exit (useful for local verification)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = config()
    w3 = Web3(Web3.HTTPProvider(settings["rpc"], request_kwargs={"timeout": 20}))
    if not w3.is_connected():
        raise RuntimeError("Could not connect to the configured EVM RPC endpoint.")
    if w3.eth.chain_id != settings["expected_chain_id"]:
        raise RuntimeError(f"Connected chain {w3.eth.chain_id}, expected {settings['expected_chain_id']}")
    contract = w3.eth.contract(address=settings["address"], abi=ABI)
    logging.info("Indexer connected to chain %s and contract %s", w3.eth.chain_id, settings["address"])
    with psycopg.connect(settings["database_url"], row_factory=dict_row) as conn:
        if args.once:
            count = scan_once(w3, contract, conn, settings)
            logging.info("One-shot scan complete; indexed %s events.", count)
            return
        while True:
            try:
                scan_once(w3, contract, conn, settings)
                time.sleep(settings["poll_seconds"])
            except KeyboardInterrupt:
                raise
            except Exception:
                logging.exception("Indexer batch failed; cursor was not advanced")
                time.sleep(settings["poll_seconds"] * 2)


if __name__ == "__main__":
    main()
