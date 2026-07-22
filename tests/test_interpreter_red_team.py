from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ast_nodes import (
    AssignmentExpression,
    Block,
    ExpressionStatement,
    FunctionDeclaration,
    Identifier,
    LetStatement,
    Literal,
    Program,
    SourceLocation,
)
from interpreter import (
    DiskCaps,
    DiskReadCaps,
    Interpreter,
    KsError,
    KoscheiRuntimeError,
    NetCaps,
    ProcessCaps,
)


class _QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class _SecretHandler(_QuietHandler):
    def do_GET(self) -> None:
        body = b"CROSS_ORIGIN_SECRET"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _RedirectHandler(_QuietHandler):
    target = ""

    def do_GET(self) -> None:
        self.send_response(302)
        self.send_header("Location", self.target)
        self.end_headers()


def _start_server(handler: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _run_cli(source: str, timeout: float = 3.0) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="koschei-red-team-") as directory:
        source_path = Path(directory) / "attack.ks"
        source_path.write_text(source, encoding="utf-8")
        return subprocess.run(
            [sys.executable, "koschei.py", "run", str(source_path)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )


class InterpreterRedTeamTests(unittest.TestCase):
    def test_disk_parent_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            allowed = Path(root) / "allowed"
            allowed.mkdir()
            outside = Path(root) / "secret.txt"
            outside.write_text("secret", encoding="utf-8")
            result = DiskReadCaps(str(allowed)).read(str(allowed / ".." / "secret.txt"))
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", str(result))

    def test_disk_prefix_collision_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            allowed = Path(root) / "app"
            collision = Path(root) / "app_evil"
            allowed.mkdir()
            collision.mkdir()
            secret = collision / "secret.txt"
            secret.write_text("secret", encoding="utf-8")
            result = DiskReadCaps(str(allowed)).read(str(secret))
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", str(result))

    def test_disk_file_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            allowed = Path(root) / "allowed"
            allowed.mkdir()
            outside = Path(root) / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            link = allowed / "link.txt"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink desteklenmiyor")
            result = DiskReadCaps(str(allowed)).read(str(link))
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", str(result))

    def test_disk_directory_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            allowed = Path(root) / "allowed"
            outside = Path(root) / "outside"
            allowed.mkdir()
            outside.mkdir()
            secret = outside / "secret.txt"
            secret.write_text("secret", encoding="utf-8")
            link = allowed / "jump"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink desteklenmiyor")
            result = DiskReadCaps(str(allowed)).read(str(link / "secret.txt"))
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", str(result))

    def test_disk_read_only_write_checks_scope_before_permission(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            allowed = Path(root) / "allowed"
            allowed.mkdir()
            outside = Path(root) / "outside.txt"
            result = DiskReadCaps(str(allowed)).write(str(outside), "owned")
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", str(result))

    def test_disk_write_symlink_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            allowed = Path(root) / "allowed"
            allowed.mkdir()
            outside = Path(root) / "outside.txt"
            outside.write_text("safe", encoding="utf-8")
            link = allowed / "write-target.txt"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink desteklenmiyor")
            result = DiskCaps(str(allowed)).write(str(link), "owned")
            contents = outside.read_text(encoding="utf-8")
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", str(result))
        self.assertEqual(contents, "safe")

    def test_net_userinfo_origin_confusion_is_rejected(self) -> None:
        result = NetCaps("https://api.example.com").get(
            "https://api.example.com@evil.example/steal"
        )
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", str(result))

    def test_net_subdomain_origin_confusion_is_rejected(self) -> None:
        result = NetCaps("https://api.example.com").get(
            "https://api.example.com.evil.example/steal"
        )
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", str(result))

    def test_net_scheme_and_port_confusion_is_rejected(self) -> None:
        cap = NetCaps("https://api.example.com")
        for url in (
            "http://api.example.com/steal",
            "https://api.example.com:444/steal",
        ):
            with self.subTest(url=url):
                result = cap.get(url)
                self.assertIsInstance(result, KsError)
                self.assertIn("KS3402", str(result))

    def test_cross_origin_redirect_cannot_escape_net_capability(self) -> None:
        secret_server, secret_thread = _start_server(_SecretHandler)
        secret_origin = f"http://127.0.0.1:{secret_server.server_port}"
        _RedirectHandler.target = secret_origin + "/secret"
        redirect_server, redirect_thread = _start_server(_RedirectHandler)
        redirect_origin = f"http://127.0.0.1:{redirect_server.server_port}"
        try:
            result = NetCaps(redirect_origin).get(redirect_origin + "/redirect")
        finally:
            redirect_server.shutdown()
            secret_server.shutdown()
            redirect_server.server_close()
            secret_server.server_close()
            redirect_thread.join(timeout=2)
            secret_thread.join(timeout=2)
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", str(result))

    def test_process_capability_never_executes(self) -> None:
        marker = Path(tempfile.gettempdir()) / "koschei-process-red-team-marker"
        try:
            marker.unlink(missing_ok=True)
            result = ProcessCaps(f"touch {marker}").run()
            self.assertIsInstance(result, KsError)
            self.assertIn("v0.1'de kapalı", str(result))
            self.assertFalse(marker.exists())
        finally:
            marker.unlink(missing_ok=True)

    def test_runtime_rewiden_guard_survives_semantic_bypass(self) -> None:
        interpreter = Interpreter(Program(()))
        with tempfile.TemporaryDirectory() as root:
            capability = DiskReadCaps(root)
            with self.assertRaisesRegex(KoscheiRuntimeError, "KS3403"):
                interpreter._member(capability, "allow", SourceLocation(1, 1))

    def test_immutable_guard_survives_semantic_bypass(self) -> None:
        location = SourceLocation(1, 1)
        program = Program(
            (
                FunctionDeclaration(
                    "main",
                    (),
                    None,
                    Block(
                        (
                            LetStatement("value", False, Literal(1, location), location),
                            ExpressionStatement(
                                AssignmentExpression(
                                    Identifier("value", location),
                                    Literal(2, location),
                                    location,
                                ),
                                location,
                            ),
                        )
                    ),
                    location,
                ),
            )
        )
        with self.assertRaisesRegex(KoscheiRuntimeError, "KS3201"):
            Interpreter(program).execute_main()

    def test_undefined_name_guard_survives_semantic_bypass(self) -> None:
        location = SourceLocation(1, 1)
        program = Program(
            (
                FunctionDeclaration(
                    "main",
                    (),
                    None,
                    Block((ExpressionStatement(Identifier("missing", location), location),)),
                    location,
                ),
            )
        )
        with self.assertRaisesRegex(KoscheiRuntimeError, "KS3101"):
            Interpreter(program).execute_main()

    def test_dunder_member_access_is_denied(self) -> None:
        interpreter = Interpreter(Program(()))
        with self.assertRaisesRegex(KoscheiRuntimeError, "KS3101"):
            interpreter._member("hello", "__class__", SourceLocation(1, 1))

    def test_recursive_crash_is_reported_as_koschei_runtime_error(self) -> None:
        completed = _run_cli(
            "fn recurse() { recurse() } fn main() { recurse() }",
            timeout=3,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("KOSCHEI RUNTIME ERROR:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_infinite_loop_is_stopped_by_runtime_budget(self) -> None:
        try:
            completed = _run_cli("fn main() { while true { } }", timeout=1)
        except subprocess.TimeoutExpired:
            self.fail("Sonsuz döngü runtime bütçesi olmadan çalışmaya devam etti.")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("KOSCHEI RUNTIME ERROR:", completed.stderr)

    def test_division_error_cannot_be_swallowed_by_println(self) -> None:
        completed = _run_cli("fn main() { println(1 / 0) }")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("Sıfıra bölme", completed.stderr)
        self.assertEqual(completed.stdout, "")

    def test_unhandled_error_bound_to_let_cannot_disappear(self) -> None:
        completed = _run_cli("fn main() { let failure = 1 / 0 }")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("Sıfıra bölme", completed.stderr)


if __name__ == "__main__":
    unittest.main()
