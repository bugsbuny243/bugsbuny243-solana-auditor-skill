from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from koschei import main


class CliTests(unittest.TestCase):
    def test_check_accepts_valid_koschei_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "main.ks"
            source.write_text("fn main() { return }", encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["check", str(source)])

            self.assertEqual(exit_code, 0)
            self.assertIn("KOSCHEI CHECK: PASS", output.getvalue())

    def test_check_rejects_non_koschei_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "main.txt"
            source.write_text("fn main() { return }", encoding="utf-8")

            error = io.StringIO()
            with redirect_stderr(error):
                exit_code = main(["check", str(source)])

            self.assertEqual(exit_code, 1)
            self.assertIn(".ks", error.getvalue())


if __name__ == "__main__":
    unittest.main()
