"""Fixture helpers for crosstalk tests."""

import json
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE identities (identity_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE states (state_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE transitions (
    transition_id TEXT PRIMARY KEY, from_state_id TEXT NOT NULL, to_state_id TEXT NOT NULL,
    authority_grant_id TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE receipts (
    receipt_seq INTEGER PRIMARY KEY AUTOINCREMENT, receipt_id TEXT NOT NULL UNIQUE,
    operation_id TEXT NOT NULL, transition_id TEXT, outcome TEXT NOT NULL,
    created_at TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE evidence (evidence_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE receipt_evidence (receipt_id TEXT NOT NULL, evidence_id TEXT NOT NULL, PRIMARY KEY (receipt_id, evidence_id));
"""


def make_database(path: Path) -> Path:
    with sqlite3.connect(str(path)) as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT INTO identities VALUES (?, ?, ?)",
            ("identity:hermes", "2026-01-01T00:00:00Z", json.dumps({"name": "Hermes"})),
        )
        states = [
            ("state:genesis", "2026-01-01T00:00:00Z", {}),
            ("state:one", "2026-01-01T00:01:00Z", {"stream": "demo", "step": 1}),
            ("state:two", "2026-01-01T00:02:00Z", {"stream": "demo", "step": 2}),
            ("state:other", "2026-01-01T00:03:00Z", {"stream": "other"}),
        ]
        connection.executemany(
            "INSERT INTO states VALUES (?, ?, ?)",
            [(key, created, json.dumps(payload)) for key, created, payload in states],
        )
        transitions = [
            ("transition:one", "state:genesis", "state:one", "grant:one", "2026-01-01T00:01:00Z"),
            ("transition:two", "state:one", "state:two", "grant:one", "2026-01-01T00:02:00Z"),
            ("transition:other", "state:genesis", "state:other", "grant:one", "2026-01-01T00:03:00Z"),
        ]
        connection.executemany(
            "INSERT INTO transitions VALUES (?, ?, ?, ?, ?, ?)",
            [row + (json.dumps({"requester_identity_id": "identity:hermes"}),) for row in transitions],
        )
        connection.executemany(
            "INSERT INTO receipts (receipt_id, operation_id, transition_id, outcome, created_at, payload) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("receipt:one", "operation:one", "transition:one", "ACCEPTED", "2026-01-01T00:01:00Z", "{}"),
                ("receipt:two", "operation:two", "transition:two", "ACCEPTED", "2026-01-01T00:02:00Z", "{}"),
                ("receipt:other", "operation:other", "transition:other", "ACCEPTED", "2026-01-01T00:03:00Z", "{}"),
            ],
        )
        connection.execute(
            "INSERT INTO evidence VALUES (?, ?, ?)",
            ("evidence:one", "2026-01-01T00:00:30Z", json.dumps({"commit": "abc123"})),
        )
        connection.execute(
            "INSERT INTO receipt_evidence VALUES (?, ?)",
            ("receipt:two", "evidence:one"),
        )
    return path
