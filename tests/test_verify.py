import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crosstalk.reader import KernelReader, Lineage
from crosstalk.verify import VerificationResult, verify

from tests.fixture import SCHEMA, make_database


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.executescript(SCHEMA)
    return connection


def _insert_state(connection, state_id, created_at, payload):
    connection.execute(
        "INSERT INTO states VALUES (?, ?, ?)",
        (state_id, created_at, json.dumps(payload)),
    )


def _insert_transition(connection, transition_id, from_id, to_id, created_at, payload):
    connection.execute(
        "INSERT INTO transitions VALUES (?, ?, ?, ?, ?, ?)",
        (transition_id, from_id, to_id, "grant:one", created_at, json.dumps(payload)),
    )


def _insert_receipt(connection, receipt_id, transition_id, outcome, created_at):
    connection.execute(
        "INSERT INTO receipts (receipt_id, operation_id, transition_id, outcome, "
        "created_at, payload) VALUES (?, ?, ?, ?, ?, ?)",
        (receipt_id, "operation:" + receipt_id, transition_id, outcome, created_at, "{}"),
    )


class VerifyValidChainTests(unittest.TestCase):
    def test_valid_chain_reports_no_problems(self):
        with tempfile.TemporaryDirectory() as directory:
            lineage = KernelReader(
                make_database(Path(directory) / "kernel.db")
            ).read_stream("demo")

        result = verify(lineage)

        self.assertIsInstance(result, VerificationResult)
        self.assertTrue(result.valid)
        self.assertEqual(result.problems, ())


class VerifyStructuralProblemsTests(unittest.TestCase):
    def test_missing_source_state_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kernel.db"
            with _connect(path) as connection:
                _insert_state(connection, "state:tagged", "2026-01-01T00:00:00Z", {"stream": "s"})
                _insert_transition(
                    connection, "transition:one", "state:missing", "state:tagged",
                    "2026-01-01T00:00:01Z", {},
                )
                _insert_receipt(connection, "receipt:one", "transition:one", "ACCEPTED", "2026-01-01T00:00:01Z")
            lineage = KernelReader(path).read_stream("s")

        result = verify(lineage)

        self.assertFalse(result.valid)
        self.assertTrue(
            any("source state state:missing is not included" in problem for problem in result.problems)
        )

    def test_orphan_tagged_state_without_incoming_transition_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kernel.db"
            with _connect(path) as connection:
                _insert_state(connection, "state:orphan", "2026-01-01T00:00:00Z", {"stream": "s"})
            lineage = KernelReader(path).read_stream("s")

        result = verify(lineage)

        self.assertFalse(result.valid)
        self.assertTrue(
            any("state:orphan: has 0 incoming transitions" in problem for problem in result.problems)
        )

    def test_duplicate_incoming_transitions_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kernel.db"
            with _connect(path) as connection:
                _insert_state(connection, "state:genesis", "2026-01-01T00:00:00Z", {})
                _insert_state(connection, "state:target", "2026-01-01T00:00:01Z", {"stream": "s"})
                _insert_transition(
                    connection, "transition:one", "state:genesis", "state:target",
                    "2026-01-01T00:00:02Z", {},
                )
                _insert_transition(
                    connection, "transition:two", "state:genesis", "state:target",
                    "2026-01-01T00:00:03Z", {},
                )
                _insert_receipt(connection, "receipt:one", "transition:one", "ACCEPTED", "2026-01-01T00:00:02Z")
                _insert_receipt(connection, "receipt:two", "transition:two", "ACCEPTED", "2026-01-01T00:00:03Z")
            lineage = KernelReader(path).read_stream("s")

        result = verify(lineage)

        self.assertFalse(result.valid)
        self.assertTrue(
            any("state:target: has 2 incoming transitions" in problem for problem in result.problems)
        )


class VerifyReceiptProblemsTests(unittest.TestCase):
    def test_missing_accepted_receipt_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kernel.db"
            with _connect(path) as connection:
                _insert_state(connection, "state:genesis", "2026-01-01T00:00:00Z", {})
                _insert_state(connection, "state:target", "2026-01-01T00:00:01Z", {"stream": "s"})
                _insert_transition(
                    connection, "transition:one", "state:genesis", "state:target",
                    "2026-01-01T00:00:02Z", {},
                )
                _insert_receipt(connection, "receipt:one", "transition:one", "REJECTED", "2026-01-01T00:00:02Z")
            lineage = KernelReader(path).read_stream("s")

        result = verify(lineage)

        self.assertFalse(result.valid)
        self.assertTrue(
            any("transition:one: has 0 ACCEPTED receipts" in problem for problem in result.problems)
        )

    def test_duplicate_accepted_receipts_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kernel.db"
            with _connect(path) as connection:
                _insert_state(connection, "state:genesis", "2026-01-01T00:00:00Z", {})
                _insert_state(connection, "state:target", "2026-01-01T00:00:01Z", {"stream": "s"})
                _insert_transition(
                    connection, "transition:one", "state:genesis", "state:target",
                    "2026-01-01T00:00:02Z", {},
                )
                _insert_receipt(connection, "receipt:one", "transition:one", "ACCEPTED", "2026-01-01T00:00:02Z")
                _insert_receipt(connection, "receipt:two", "transition:one", "ACCEPTED", "2026-01-01T00:00:03Z")
            lineage = KernelReader(path).read_stream("s")

        result = verify(lineage)

        self.assertFalse(result.valid)
        self.assertTrue(
            any("transition:one: has 2 ACCEPTED receipts" in problem for problem in result.problems)
        )


class VerifySyntheticLinkProblemsTests(unittest.TestCase):
    """These two link checks can never occur in a Lineage produced by
    KernelReader, since its own queries only select receipts/evidence whose
    foreign keys already resolve within the extracted set. verify() must
    still check them independently of that guarantee, so they are exercised
    directly against a constructed Lineage rather than a fixture database."""

    def test_receipt_naming_absent_transition_is_reported(self):
        lineage = Lineage(
            stream="s",
            states=[{"state_id": "state:one", "payload": {"stream": "s"}}],
            transitions=[],
            receipts=[
                {
                    "receipt_id": "receipt:one",
                    "transition_id": "transition:absent",
                    "outcome": "ACCEPTED",
                }
            ],
            evidence=[],
            identities=[],
        )

        result = verify(lineage)

        self.assertFalse(result.valid)
        self.assertTrue(
            any(
                "receipt:one: names transition transition:absent" in problem
                for problem in result.problems
            )
        )

    def test_evidence_linking_to_absent_receipt_is_reported(self):
        lineage = Lineage(
            stream="s",
            states=[],
            transitions=[],
            receipts=[],
            evidence=[{"evidence_id": "evidence:one", "receipt_id": "receipt:absent"}],
            identities=[],
        )

        result = verify(lineage)

        self.assertFalse(result.valid)
        self.assertTrue(
            any(
                "evidence:one: linked receipt receipt:absent" in problem
                for problem in result.problems
            )
        )


class VerifyCollectsAllProblemsTests(unittest.TestCase):
    def test_does_not_stop_at_the_first_problem(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kernel.db"
            with _connect(path) as connection:
                _insert_state(connection, "state:genesis", "2026-01-01T00:00:00Z", {})
                _insert_state(connection, "state:target", "2026-01-01T00:00:01Z", {"stream": "s"})
                _insert_state(connection, "state:orphan", "2026-01-01T00:00:02Z", {"stream": "s"})
                _insert_transition(
                    connection, "transition:one", "state:genesis", "state:target",
                    "2026-01-01T00:00:03Z", {},
                )
                _insert_receipt(connection, "receipt:one", "transition:one", "REJECTED", "2026-01-01T00:00:03Z")
            lineage = KernelReader(path).read_stream("s")

        result = verify(lineage)

        self.assertFalse(result.valid)
        self.assertGreaterEqual(len(result.problems), 2)
        self.assertTrue(any("transition:one: has 0 ACCEPTED receipts" in p for p in result.problems))
        self.assertTrue(any("state:orphan: has 0 incoming transitions" in p for p in result.problems))


if __name__ == "__main__":
    unittest.main()
