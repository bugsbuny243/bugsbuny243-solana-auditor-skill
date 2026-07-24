from __future__ import annotations

import io
import pathlib
import re
import unittest
from contextlib import redirect_stderr, redirect_stdout

from koschei.diagnostics import CATALOG, known_codes, lookup
from koschei.cli import main

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CODE_IN_SOURCE = re.compile(r'"(KS\d{4})"')


class DiagnosticsCatalogTests(unittest.TestCase):
    def test_every_code_used_in_compiler_has_an_explanation(self) -> None:
        used: set[str] = set()
        for name in ("semantic.py", "interpreter.py", "codegen_go.py", "modules.py"):
            path = REPO_ROOT / "koschei" / name
            # Henüz eklenmemiş bir kaynak dosya testi çökertmemeli; var olan
            # her dosyanın kodları eksiksiz açıklanmış olmalıdır.
            if not path.is_file():
                continue
            used.update(CODE_IN_SOURCE.findall(path.read_text(encoding="utf-8")))

        missing = sorted(used - set(CATALOG))
        self.assertEqual(missing, [], f"Katalogda eksik hata kodları: {missing}")

    def test_catalog_entries_are_complete(self) -> None:
        for code, diagnostic in CATALOG.items():
            self.assertEqual(diagnostic.code, code)
            for field in (
                diagnostic.title,
                diagnostic.summary,
                diagnostic.why,
                diagnostic.fix,
                diagnostic.example,
            ):
                self.assertTrue(field.strip(), f"{code} için boş alan var")

    def test_lookup_accepts_bare_code_and_full_error_text(self) -> None:
        self.assertIsNotNone(lookup("KS2403"))
        self.assertIsNotNone(lookup("ks2403"))
        found = lookup("KS3402: Disk kapsamı dışında erişim reddedildi: /etc/passwd")
        self.assertIsNotNone(found)
        self.assertEqual(found.code, "KS3402")

    def test_lookup_returns_none_for_unknown_code(self) -> None:
        self.assertIsNone(lookup("KS9999"))
        self.assertIsNone(lookup("merhaba"))

    def test_known_codes_is_sorted_and_non_empty(self) -> None:
        codes = known_codes()
        self.assertTrue(codes)
        self.assertEqual(codes, sorted(codes))


class ExplainCommandTests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        output = io.StringIO()
        error = io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            exit_code = main(argv)
        return exit_code, output.getvalue(), error.getvalue()

    def test_explain_prints_all_sections(self) -> None:
        code, output, _ = self.run_cli(["explain", "KS1401"])
        self.assertEqual(code, 0)
        for section in ("NE OLDU", "NEDEN", "NASIL DÜZELTİLİR", "ÖRNEK"):
            self.assertIn(section, output)

    def test_explain_accepts_full_error_message(self) -> None:
        code, output, _ = self.run_cli(
            ["explain", "KS2402 [satır 3, sütun 21]: kök yetki"]
        )
        self.assertEqual(code, 0)
        self.assertIn("KS2402", output)

    def test_explain_rejects_unknown_code(self) -> None:
        code, output, error = self.run_cli(["explain", "KS9999"])
        self.assertEqual(code, 1)
        self.assertEqual(output, "")
        self.assertIn("bilinen bir hata kodu değil", error)

    def test_failed_check_suggests_explain(self) -> None:
        source = REPO_ROOT / "tests" / "_tmp_rewiden.ks"
        source.write_text(
            'fn main(caps: SystemCaps) {\n'
            '    let ro = caps.disk.allow_read_only("/tmp")\n'
            '    let w = ro.allow("/")\n'
            '}\n',
            encoding="utf-8",
        )
        try:
            code, _, error = self.run_cli(["check", str(source)])
        finally:
            source.unlink(missing_ok=True)

        self.assertEqual(code, 1)
        self.assertIn("KS2403", error)
        self.assertIn("explain KS2403", error)


if __name__ == "__main__":
    unittest.main()
