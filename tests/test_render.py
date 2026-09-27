import tempfile
import unittest
from pathlib import Path

from crosstalk.reader import KernelReader, Lineage
from crosstalk.render import render_html, write_timeline

from tests.fixture import make_database


class RenderTests(unittest.TestCase):
    def test_renders_fixture_timeline_and_writes_same_document(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lineage = KernelReader(make_database(root / "kernel.db")).read_stream("demo")
            document = render_html(lineage)
            output = root / "timeline.html"
            write_timeline(lineage, output)

            self.assertIn("<!doctype html>", document)
            self.assertIn("transition:two", document)
            self.assertIn("Hermes (identity:hermes)", document)
            self.assertIn("evidence:one", document)
            self.assertNotIn("transition:other", document)
            self.assertEqual(output.read_text(encoding="utf-8"), document)

    def test_escapes_all_record_content(self):
        lineage = Lineage(
            stream="demo <script>&",
            states=[
                {
                    "state_id": "state:<to>",
                    "payload": {"message": "<b>state & payload</b>"},
                }
            ],
            transitions=[
                {
                    "transition_id": "transition:<unsafe>",
                    "from_state_id": "state:<from>",
                    "to_state_id": "state:<to>",
                    "created_at": "2026-01-01T00:00:00Z<script>",
                    "payload": {
                        "requester_identity_id": "identity:<agent>",
                        "message": "<script>alert('transition')</script>",
                    },
                }
            ],
            receipts=[
                {
                    "receipt_id": "receipt:<unsafe>",
                    "transition_id": "transition:<unsafe>",
                    "outcome": "ACCEPTED<script>",
                    "payload": {"message": "<i>receipt</i>"},
                }
            ],
            evidence=[
                {
                    "evidence_id": "evidence:<unsafe>",
                    "receipt_id": "receipt:<unsafe>",
                    "payload": {"message": "<em>evidence</em>"},
                }
            ],
            identities=[
                {
                    "identity_id": "identity:<agent>",
                    "payload": {"name": "Agent <admin> & team"},
                }
            ],
        )

        document = render_html(lineage)

        self.assertNotIn("<script>", document)
        self.assertNotIn("<b>", document)
        self.assertNotIn("<i>", document)
        self.assertNotIn("<em>", document)
        self.assertIn("demo &lt;script&gt;&amp;", document)
        self.assertIn("transition:&lt;unsafe&gt;", document)
        self.assertIn("Agent &lt;admin&gt; &amp; team", document)
        self.assertIn("&lt;script&gt;alert", document)
        self.assertIn("evidence:&lt;unsafe&gt;", document)

    def test_associates_receipts_and_evidence_with_their_transition(self):
        lineage = Lineage(
            stream="demo",
            states=[
                {"state_id": "state:one", "payload": {"step": 1}},
                {"state_id": "state:two", "payload": {"step": 2}},
            ],
            transitions=[
                {
                    "transition_id": "transition:one",
                    "from_state_id": "state:genesis",
                    "to_state_id": "state:one",
                    "created_at": "2026-01-01T00:01:00Z",
                    "payload": {},
                },
                {
                    "transition_id": "transition:two",
                    "from_state_id": "state:one",
                    "to_state_id": "state:two",
                    "created_at": "2026-01-01T00:02:00Z",
                    "payload": {},
                },
            ],
            receipts=[
                {
                    "receipt_id": "receipt:one",
                    "transition_id": "transition:one",
                    "outcome": "ACCEPTED",
                    "payload": {"marker": "receipt-one"},
                },
                {
                    "receipt_id": "receipt:two",
                    "transition_id": "transition:two",
                    "outcome": "REJECTED",
                    "payload": {"marker": "receipt-two"},
                },
            ],
            evidence=[
                {
                    "evidence_id": "evidence:two",
                    "receipt_id": "receipt:two",
                    "payload": {"marker": "evidence-two"},
                }
            ],
            identities=[],
        )

        document = render_html(lineage)
        first_card, second_card = document.split('<article class="event">')[1:]

        self.assertIn("receipt:one", first_card)
        self.assertNotIn("receipt:two", first_card)
        self.assertIn("<h3>Evidence</h3><ul><li>None</li></ul>", first_card)
        self.assertIn("receipt:two", second_card)
        self.assertIn("evidence:two", second_card)
        self.assertIn("REJECTED", second_card)

    def test_renders_missing_receipt_state_and_actor_fallbacks(self):
        lineage = Lineage(
            stream="demo",
            states=[],
            transitions=[
                {
                    "transition_id": "transition:missing",
                    "from_state_id": "state:one",
                    "to_state_id": "state:missing",
                    "created_at": "2026-01-01T00:00:00Z",
                    "payload": {},
                },
                {
                    "transition_id": "transition:unlabelled",
                    "from_state_id": "state:missing",
                    "to_state_id": "state:also-missing",
                    "created_at": "2026-01-01T00:01:00Z",
                    "payload": {"identity_id": "identity:unlabelled"},
                },
            ],
            receipts=[],
            evidence=[],
            identities=[],
        )

        document = render_html(lineage)

        self.assertEqual(document.count("<strong>Receipt:</strong> missing"), 2)
        self.assertEqual(document.count("<h3>State</h3><pre>{}</pre>"), 2)
        self.assertIn("unknown agent", document)
        self.assertIn("identity:unlabelled", document)

    def test_renders_empty_timeline_with_summary_counts(self):
        lineage = Lineage(
            stream="empty",
            states=[],
            transitions=[],
            receipts=[],
            evidence=[],
            identities=[],
        )

        document = render_html(lineage)

        self.assertIn("0 states · 0 transitions · 0 receipts", document)
        self.assertIn("<main><p>No transitions.</p></main>", document)
        self.assertNotIn('<article class="event">', document)

    def test_write_timeline_uses_utf8(self):
        lineage = Lineage(
            stream="handoff café 🚀",
            states=[],
            transitions=[],
            receipts=[],
            evidence=[],
            identities=[],
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "timeline.html"

            write_timeline(lineage, output)

            self.assertEqual(output.read_bytes(), render_html(lineage).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
