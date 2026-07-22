from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from interpreter import DiskReadCaps, KsError, run
from parser import parse


class InterpreterTests(unittest.TestCase):
    def run_source(self, source: str) -> tuple[int, str, str]:
        output = io.StringIO()
        error = io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            exit_code = run(parse(source), [])
        return exit_code, output.getvalue(), error.getvalue()

    def test_println_and_string_interpolation(self) -> None:
        code, output, error = self.run_source(
            'fn main() { let name = "Koschei" println("Merhaba {name}") }'
        )
        self.assertEqual(code, 0)
        self.assertEqual(output, "Merhaba Koschei\n")
        self.assertEqual(error, "")

    def test_arithmetic_and_while_countdown(self) -> None:
        code, output, _ = self.run_source(
            "fn main() { let mut count = 3 while count > 0 { "
            "println(count) count = count - 1 } }"
        )
        self.assertEqual(code, 0)
        self.assertEqual(output, "3\n2\n1\n")

    def test_or_default_uses_fallback(self) -> None:
        code, output, _ = self.run_source(
            'fn main() { let port = "x".to_int() or 8080 println(port) }'
        )
        self.assertEqual(code, 0)
        self.assertEqual(output, "8080\n")

    def test_or_return_propagates_error_to_caller(self) -> None:
        source = (
            'fn parse_value(raw: String) -> Int or Error { '
            'return raw.to_int() or return '
            '} '
            'fn main() { '
            'let result = parse_value("x") or "taşındı" '
            'println(result) '
            '}'
        )
        code, output, _ = self.run_source(source)
        self.assertEqual(code, 0)
        self.assertEqual(output, "taşındı\n")

    def test_or_block_runs_and_returns_last_expression(self) -> None:
        source = (
            'fn main() { '
            'let value = "x".to_int() or { println("blok çalıştı") 7 } '
            'println(value) '
            '}'
        )
        code, output, _ = self.run_source(source)
        self.assertEqual(code, 0)
        self.assertEqual(output, "blok çalıştı\n7\n")

    def test_disk_read_scope_and_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "allowed"
            root.mkdir()
            inside = root / "inside.txt"
            outside = Path(directory) / "outside.txt"
            inside.write_text("güvenli", encoding="utf-8")
            outside.write_text("gizli", encoding="utf-8")
            escaped = root / ".." / "outside.txt"
            source = (
                'fn main(caps: SystemCaps) { '
                f'let disk = caps.disk.allow_read_only("{root}") '
                f'let content = disk.read("{inside}") or "hata" '
                'println(content) '
                f'let blocked = disk.read("{outside}") or "dışarı engellendi" '
                'println(blocked) '
                f'let parent = disk.read("{escaped}") or "kaçış engellendi" '
                'println(parent) '
                '}'
            )
            code, output, _ = self.run_source(source)
        self.assertEqual(code, 0)
        self.assertEqual(
            output,
            "güvenli\ndışarı engellendi\nkaçış engellendi\n",
        )

    def test_disk_scope_error_contains_ks3402_and_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            allowed = Path(directory) / "allowed"
            allowed.mkdir()
            outside = Path(directory) / "outside.txt"
            outside.write_text("gizli", encoding="utf-8")
            caps = DiskReadCaps(str(allowed))
            outside_result = caps.read(str(outside))
            self.assertIsInstance(outside_result, KsError)
            self.assertIn("KS3402", outside_result.message)

            link = allowed / "escape.txt"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink oluşturulamıyor")
            link_result = caps.read(str(link))
            self.assertIsInstance(link_result, KsError)
            self.assertIn("KS3402", link_result.message)

    def test_disk_read_caps_write_returns_ks3404_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = DiskReadCaps(directory).write(
                str(Path(directory) / "x.txt"), "data"
            )
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3404", result.message)

    def test_disk_read_caps_outside_write_returns_ks3402(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            allowed = Path(directory) / "allowed"
            allowed.mkdir()
            result = DiskReadCaps(str(allowed)).write(
                str(Path(directory) / "outside.txt"), "data"
            )
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", result.message)

    def test_division_by_zero_can_be_handled(self) -> None:
        code, output, _ = self.run_source(
            "fn main() { let result = 1 / 0 or 0 println(result) }"
        )
        self.assertEqual(code, 0)
        self.assertEqual(output, "0\n")

    def test_env_allow_and_get(self) -> None:
        name = "KOSCHEI_INTERPRETER_TEST"
        previous = os.environ.get(name)
        os.environ[name] = "hazır"
        try:
            code, output, _ = self.run_source(
                'fn main(caps: SystemCaps) { '
                f'let env = caps.env.allow("{name}") '
                'let value = env.get() or "yok" '
                'println(value) '
                '}'
            )
        finally:
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous
        self.assertEqual(code, 0)
        self.assertEqual(output, "hazır\n")

    def test_rejected_network_origin_does_not_make_http_request(self) -> None:
        source = (
            'fn main(caps: SystemCaps) { '
            'let net = caps.net.allow("https://api.example.com") '
            'let result = net.get("https://evil.example.com/data") or "engellendi" '
            'println(result) '
            '}'
        )
        code, output, _ = self.run_source(source)
        self.assertEqual(code, 0)
        self.assertEqual(output, "engellendi\n")

    def test_unhandled_error_returns_exit_code_one(self) -> None:
        code, output, error = self.run_source(
            'fn main() { "x".to_int() }'
        )
        self.assertEqual(code, 1)
        self.assertEqual(output, "")
        self.assertIn("KOSCHEI RUNTIME ERROR", error)


if __name__ == "__main__":
    unittest.main()
