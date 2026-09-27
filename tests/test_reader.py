import tempfile
import unittest
from pathlib import Path

from crosstalk.reader import KernelReader

from tests.fixture import make_database


class KernelReaderTests(unittest.TestCase):
    def test_extracts_only_the_requested_stream_and_its_links(self):
        with tempfile.TemporaryDirectory() as directory:
            lineage = KernelReader(
                make_database(Path(directory) / "kernel.db")
            ).read_stream("demo")

        self.assertEqual(
            [row["state_id"] for row in lineage.states],
            ["state:genesis", "state:one", "state:two"],
        )
        self.assertEqual(
            [row["transition_id"] for row in lineage.transitions],
            ["transition:one", "transition:two"],
        )
        self.assertEqual(len(lineage.receipts), 2)
        self.assertEqual(lineage.evidence[0]["receipt_id"], "receipt:two")
        self.assertEqual(lineage.evidence[0]["payload"]["commit"], "abc123")
        self.assertEqual(lineage.identities[0]["payload"]["name"], "Hermes")

    def test_unknown_stream_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            reader = KernelReader(make_database(Path(directory) / "kernel.db"))
            with self.assertRaisesRegex(LookupError, "stream not found"):
                reader.read_stream("missing")


if __name__ == "__main__":
    unittest.main()
