"""Extract stream-scoped lineage from an EASTER v0.1 SQLite database."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


class KernelSchemaError(ValueError):
    """The database does not expose the EASTER tables crosstalk requires."""


@dataclass(frozen=True)
class Lineage:
    """A stream's records, preserving all branches in chronological order."""

    stream: str
    states: Sequence[Mapping[str, Any]]
    transitions: Sequence[Mapping[str, Any]]
    receipts: Sequence[Mapping[str, Any]]
    evidence: Sequence[Mapping[str, Any]]
    identities: Sequence[Mapping[str, Any]]


class KernelReader:
    """Read an EASTER kernel database without mutating it."""

    REQUIRED_TABLES = {
        "states",
        "transitions",
        "receipts",
        "receipt_evidence",
        "evidence",
        "identities",
    }

    def __init__(self, database: Path) -> None:
        self.database = Path(database)

    def read_stream(self, stream: str) -> Lineage:
        if not stream:
            raise ValueError("stream must not be empty")
        if not self.database.is_file():
            raise FileNotFoundError(str(self.database))

        uri = "file:{}?mode=ro".format(self.database.resolve().as_posix())
        with sqlite3.connect(uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            self._validate_schema(connection)
            all_states = self._rows(connection, "states", "created_at, state_id")
            state_by_id = {row["state_id"]: row for row in all_states}
            tagged_ids = {
                row["state_id"]
                for row in all_states
                if self._payload_stream(row["payload"]) == stream
            }
            if not tagged_ids:
                raise LookupError("stream not found: {}".format(stream))

            all_transitions = self._rows(
                connection, "transitions", "created_at, transition_id"
            )
            selected = [
                row
                for row in all_transitions
                if row["to_state_id"] in tagged_ids
                or (
                    row["from_state_id"] in tagged_ids
                    and row["to_state_id"] in tagged_ids
                )
            ]
            state_ids = set(tagged_ids)
            for transition in selected:
                state_ids.add(transition["from_state_id"])
                state_ids.add(transition["to_state_id"])

            states = [row for row in all_states if row["state_id"] in state_ids]
            transition_ids = [row["transition_id"] for row in selected]
            receipts = self._receipts(connection, transition_ids)
            receipt_ids = [row["receipt_id"] for row in receipts]
            evidence = self._evidence(connection, receipt_ids)
            identity_ids = {
                value
                for row in selected
                for value in (
                    row["payload"].get("requester_identity_id"),
                    row["payload"].get("identity_id"),
                )
                if isinstance(value, str)
            }
            identities = self._identities(connection, identity_ids)

        return Lineage(
            stream=stream,
            states=states,
            transitions=selected,
            receipts=receipts,
            evidence=evidence,
            identities=identities,
        )

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing = sorted(self.REQUIRED_TABLES - tables)
        if missing:
            raise KernelSchemaError(
                "missing required EASTER tables: {}".format(", ".join(missing))
            )

    @staticmethod
    def _payload_stream(payload: Mapping[str, Any]) -> Optional[str]:
        value = payload.get("stream", payload.get("stream_id"))
        return value if isinstance(value, str) else None

    def _rows(
        self, connection: sqlite3.Connection, table: str, ordering: str
    ) -> List[Dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM {} ORDER BY {}".format(table, ordering)
        ).fetchall()
        return [self._decode_row(row) for row in rows]

    def _receipts(
        self, connection: sqlite3.Connection, transition_ids: Sequence[str]
    ) -> List[Dict[str, Any]]:
        if not transition_ids:
            return []
        placeholders = ",".join("?" for _ in transition_ids)
        rows = connection.execute(
            "SELECT * FROM receipts WHERE transition_id IN ({}) "
            "ORDER BY receipt_seq".format(placeholders),
            tuple(transition_ids),
        ).fetchall()
        return [self._decode_row(row) for row in rows]

    def _evidence(
        self, connection: sqlite3.Connection, receipt_ids: Sequence[str]
    ) -> List[Dict[str, Any]]:
        if not receipt_ids:
            return []
        placeholders = ",".join("?" for _ in receipt_ids)
        rows = connection.execute(
            "SELECT e.*, re.receipt_id FROM receipt_evidence re "
            "JOIN evidence e ON e.evidence_id = re.evidence_id "
            "WHERE re.receipt_id IN ({}) "
            "ORDER BY e.created_at, e.evidence_id, re.receipt_id".format(
                placeholders
            ),
            tuple(receipt_ids),
        ).fetchall()
        return [self._decode_row(row) for row in rows]

    def _identities(
        self, connection: sqlite3.Connection, identity_ids: set
    ) -> List[Dict[str, Any]]:
        if not identity_ids:
            return []
        ordered = sorted(identity_ids)
        placeholders = ",".join("?" for _ in ordered)
        rows = connection.execute(
            "SELECT * FROM identities WHERE identity_id IN ({}) "
            "ORDER BY created_at, identity_id".format(placeholders),
            tuple(ordered),
        ).fetchall()
        return [self._decode_row(row) for row in rows]

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        if "payload" in result:
            try:
                result["payload"] = json.loads(result["payload"])
            except (TypeError, json.JSONDecodeError) as error:
                identifier = next(
                    (value for key, value in result.items() if key.endswith("_id")),
                    "unknown record",
                )
                raise KernelSchemaError(
                    "invalid JSON payload for {}".format(identifier)
                ) from error
        return result
