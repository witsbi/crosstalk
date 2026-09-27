import tempfile
import unittest
from pathlib import Path

from crosstalk.reader import KernelReader
from crosstalk.render import render_html, write_timeline

from tests.fixture import make_database


class RenderTests(unittest.TestCase):
    def test_renders_self_contained_escaped_timeline(self):
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


if __name__ == "__main__":
    unittest.main()
