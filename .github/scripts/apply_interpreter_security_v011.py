from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent, indent


ALLOWED_FILES = {
    "docs/language-core.md",
    "interpreter.py",
    "semantic.py",
    "tests/test_interpreter.py",
    "tests/test_semantic.py",
}


def run_command(*arguments: str) -> None:
    print(f"\n$ {' '.join(arguments)}", flush=True)
    subprocess.run(arguments, check=True)


def add_test_method(text: str, method: str) -> str:
    marker = '\n\nif __name__ == "__main__":\n'
    if marker not in text:
        raise RuntimeError("unittest dosyası son işareti bulunamadı")
    rendered = "\n\n" + indent(dedent(method).strip("\n"), "    ")
    return text.replace(marker, rendered + marker, 1)


def apply_ks3105() -> None:
    print("\n=== BULGU 3 / KS3105: çağrı derinliği sınırı ===", flush=True)
    path = Path("interpreter.py")
    text = path.read_text(encoding="utf-8")

    anchor = "from semantic import check as semantic_check\n\n\n"
    if anchor not in text:
        raise RuntimeError("semantic import işareti bulunamadı")
    text = text.replace(
        anchor,
        "from semantic import check as semantic_check\n\n\nMAX_CALL_DEPTH = 512\n\n\n",
        1,
    )

    interpreter_start = text.index("class Interpreter:\n")
    init_line = "        self.environment = _Environment()\n"
    init_position = text.index(init_line, interpreter_start)
    text = (
        text[:init_position]
        + init_line
        + "        self._depth = 0\n"
        + text[init_position + len(init_line) :]
    )

    start = text.index("    def _call_function(\n", interpreter_start)
    end = text.index("\n    def _execute_block", start)
    method = indent(
        dedent(
            '''
            def _call_function(
                self, function: FunctionDeclaration, arguments: list[Any]
            ) -> Any:
                self._depth += 1
                try:
                    if self._depth > MAX_CALL_DEPTH:
                        raise KoscheiRuntimeError(
                            "KS3105",
                            "Çağrı derinliği sınırı aşıldı (512); sonsuz özyineleme olabilir.",
                            function.location,
                        )
                    if len(arguments) != len(function.parameters):
                        raise KoscheiRuntimeError(
                            "KS3101",
                            f"'{function.name}' için {len(function.parameters)} argüman bekleniyor, "
                            f"{len(arguments)} verildi.",
                            function.location,
                        )
                    previous = self.environment
                    self.environment = _Environment()
                    try:
                        for parameter, value in zip(function.parameters, arguments):
                            self.environment.define(parameter.name, value, False)
                        try:
                            return self._execute_block(function.body, create_scope=False)
                        except _ReturnSignal as signal:
                            return signal.value
                    finally:
                        self.environment = previous
                except RecursionError:
                    raise KoscheiRuntimeError(
                        "KS3105",
                        "Çağrı derinliği sınırı aşıldı (512); sonsuz özyineleme olabilir.",
                        function.location,
                    ) from None
                finally:
                    self._depth -= 1
            '''
        ).strip("\n"),
        "    ",
    )
    text = text[:start] + method + text[end:]
    path.write_text(text, encoding="utf-8")

    test_path = Path("tests/test_interpreter.py")
    tests = test_path.read_text(encoding="utf-8")
    old_import = "from interpreter import DiskReadCaps, KsError, run\n"
    if old_import not in tests:
        raise RuntimeError("interpreter test import işareti bulunamadı")
    tests = tests.replace(
        old_import,
        "from interpreter import (\n"
        "    DiskReadCaps,\n"
        "    Interpreter,\n"
        "    KoscheiRuntimeError,\n"
        "    KsError,\n"
        "    run,\n"
        ")\n",
        1,
    )
    tests = add_test_method(
        tests,
        '''
        def test_recursion_limit_raises_ks3105_without_python_error(self) -> None:
            program = parse(
                "fn boom(n: Int) -> Int { return boom(n + 1) } "
                "fn main() { boom(0) }"
            )
            with self.assertRaisesRegex(KoscheiRuntimeError, "KS3105"):
                Interpreter(program, []).execute_main()
        ''',
    )
    test_path.write_text(tests, encoding="utf-8")


def apply_ks1401() -> None:
    print("\n=== BULGU 2 / KS1401: ele alınmayan hata değeri ===", flush=True)
    path = Path("interpreter.py")
    text = path.read_text(encoding="utf-8")
    old_block = dedent(
        '''
                    for statement in block.statements:
                        result = self._execute_statement(statement)
                        if isinstance(result, KsError):
                            return result
                    return result
        '''
    ).strip("\n")
    new_block = dedent(
        '''
                    for statement in block.statements:
                        result = self._execute_statement(statement)
                    return result
        '''
    ).strip("\n")
    if old_block not in text:
        raise RuntimeError("_execute_block hata çıkışı işareti bulunamadı")
    text = text.replace(old_block, new_block, 1)
    path.write_text(text, encoding="utf-8")

    semantic_path = Path("semantic.py")
    semantic = semantic_path.read_text(encoding="utf-8")
    code_row = "    KS1301  Tip uyuşmazlığı\n"
    if code_row not in semantic:
        raise RuntimeError("semantic hata kodu işareti bulunamadı")
    semantic = semantic.replace(
        code_row,
        code_row + "    KS1401  Ele alınmayan hata değeri\n",
        1,
    )

    old_statement = dedent(
        '''
                if isinstance(statement, ExpressionStatement):
                    self._check_expression(statement.expression)
                    return
        '''
    ).strip("\n")
    new_statement = dedent(
        '''
                if isinstance(statement, ExpressionStatement):
                    self._check_expression(statement.expression)
                    if self._is_unhandled_error_call(statement.expression):
                        raise SemanticError(
                            "KS1401",
                            "Hata dönebilen çağrının sonucu ele alınmalıdır "
                            "('let ... = ...', 'or return', 'or varsayılan' veya "
                            "'or { ... }' kullanın).",
                            statement.location,
                        )
                    return
        '''
    ).strip("\n")
    if old_statement not in semantic:
        raise RuntimeError("ExpressionStatement semantic işareti bulunamadı")
    semantic = semantic.replace(old_statement, new_statement, 1)

    helpers = indent(
        dedent(
            '''
            def _is_unhandled_error_call(self, expression: Expression) -> bool:
                if not isinstance(expression, CallExpression):
                    return False
                if isinstance(expression.callee, Identifier):
                    return expression.callee.name == "Error"
                if isinstance(expression.callee, MemberExpression):
                    receiver_type = self._infer_expression_type(expression.callee.object)
                    return (
                        receiver_type in NARROWED_METHODS
                        and expression.callee.member in NARROWED_METHODS[receiver_type]
                    )
                return False

            def _infer_expression_type(self, expression: Expression) -> str | None:
                if isinstance(expression, Identifier):
                    symbol = self._resolve(expression.name)
                    if symbol is not None:
                        return symbol.type_name
                    if expression.name in self.functions:
                        function = self.functions[expression.name]
                        return str(function.return_type) if function.return_type else "Void"
                    return None
                if isinstance(expression, MemberExpression):
                    object_type = self._infer_expression_type(expression.object)
                    if object_type == "SystemCaps":
                        return CAPABILITY_MEMBERS.get(expression.member)
                    return object_type
                if isinstance(expression, CallExpression):
                    if isinstance(expression.callee, MemberExpression):
                        receiver_type = self._infer_expression_type(
                            expression.callee.object
                        )
                        if receiver_type in ROOT_METHODS:
                            return ROOT_METHODS[receiver_type].get(
                                expression.callee.member
                            )
                        return None
                    return self._infer_expression_type(expression.callee)
                return None

            '''
        ).strip("\n"),
        "    ",
    ) + "\n\n"
    marker = "    def _check_binary(self, expression: BinaryExpression) -> str | None:\n"
    if marker not in semantic:
        raise RuntimeError("_check_binary işareti bulunamadı")
    semantic = semantic.replace(marker, helpers + marker, 1)
    semantic_path.write_text(semantic, encoding="utf-8")

    test_path = Path("tests/test_semantic.py")
    tests = test_path.read_text(encoding="utf-8")
    tests = add_test_method(
        tests,
        '''
        def test_unhandled_capability_error_is_rejected(self) -> None:
            program = parse(
                'fn main(caps: SystemCaps) { '
                'let ro = caps.disk.allow_read_only("/tmp/safe") '
                'ro.read("/etc/passwd") '
                '}'
            )
            with self.assertRaisesRegex(SemanticError, "KS1401"):
                check(program)

        def test_handled_capability_errors_are_accepted(self) -> None:
            program = parse(
                'fn main(caps: SystemCaps) { '
                'let ro = caps.disk.allow_read_only("/tmp/safe") '
                'let value = ro.read("/tmp/safe/a") or "" '
                'ro.read("/tmp/safe/b") or return '
                '}'
            )
            report = check(program)
            self.assertEqual(report.functions, 1)
        ''',
    )
    test_path.write_text(tests, encoding="utf-8")

    docs_path = Path("docs/language-core.md")
    docs = docs_path.read_text(encoding="utf-8")
    row = '| KS1301 | Tip uyuşmazlığı (`"abc" + 5`, Bool olmayan `if` koşulu vb.) |\n'
    if row not in docs:
        raise RuntimeError("doküman KS1301 satırı bulunamadı")
    docs = docs.replace(row, row + "| KS1401 | Ele alınmayan hata değeri |\n", 1)
    docs_path.write_text(docs, encoding="utf-8")


def apply_redirect_guard() -> None:
    print("\n=== BULGU 1 / KS3402: redirect origin koruması ===", flush=True)
    path = Path("interpreter.py")
    text = path.read_text(encoding="utf-8")
    old_import = "from urllib.parse import urlsplit\n"
    if old_import not in text:
        raise RuntimeError("urlsplit import işareti bulunamadı")
    text = text.replace(old_import, "from urllib.parse import urljoin, urlsplit\n", 1)

    class_start = text.index("class NetCaps(_NarrowedCapability):\n")
    static_start = text.index("    @staticmethod\n    def post", class_start)
    replacement = dedent(
        '''
        class _ScopedRedirectHandler(urllib.request.HTTPRedirectHandler):
            def __init__(
                self, origin_key: tuple[str, str, int | None] | None
            ) -> None:
                super().__init__()
                self.origin_key = origin_key
                self.redirect_count = 0
                self.blocked_url: str | None = None

            def reset(self) -> None:
                self.redirect_count = 0
                self.blocked_url = None

            def redirect_request(
                self,
                request: urllib.request.Request,
                response: object,
                code: int,
                message: str,
                headers: object,
                new_url: str,
            ) -> urllib.request.Request | None:
                target_url = urljoin(request.full_url, new_url)
                if self.origin_key is None or _origin_key(target_url) != self.origin_key:
                    self.blocked_url = target_url
                    return None
                self.redirect_count += 1
                if self.redirect_count > 5:
                    return None
                return super().redirect_request(
                    request, response, code, message, headers, target_url
                )


        class NetCaps(_NarrowedCapability):
            __slots__ = (
                "origin",
                "origin_key",
                "_redirect_handler",
                "_opener",
            )

            def __init__(self, origin: str) -> None:
                self.origin = origin
                self.origin_key = _origin_key(origin)
                self._redirect_handler = _ScopedRedirectHandler(self.origin_key)
                self._opener = urllib.request.build_opener(self._redirect_handler)

            def _allows(self, url: str) -> bool:
                return self.origin_key is not None and _origin_key(url) == self.origin_key

            def get(self, url: str) -> Response | KsError:
                if not self._allows(url):
                    return KsError(
                        f"KS3402: Ağ origin kapsamı dışında erişim reddedildi: {url}"
                    )
                self._redirect_handler.reset()
                try:
                    request = urllib.request.Request(url, method="GET")
                    with self._opener.open(request, timeout=10) as response:
                        charset = response.headers.get_content_charset() or "utf-8"
                        body = response.read().decode(charset, errors="replace")
                        return Response(body, int(response.status))
                except urllib.error.HTTPError as error:
                    if self._redirect_handler.blocked_url is not None:
                        return KsError(
                            "KS3402: Ağ yönlendirmesi kapsam dışına çıktı: "
                            f"{self._redirect_handler.blocked_url}"
                        )
                    return KsError(f"API isteği başarısız: {error}")
                except (OSError, urllib.error.URLError) as error:
                    return KsError(f"API isteği başarısız: {error}")

        '''
    ).lstrip()
    text = text[:class_start] + replacement + text[static_start:]
    path.write_text(text, encoding="utf-8")

    test_path = Path("tests/test_interpreter.py")
    tests = test_path.read_text(encoding="utf-8")
    if "import tempfile\n" not in tests:
        raise RuntimeError("tempfile import işareti bulunamadı")
    tests = tests.replace("import tempfile\n", "import tempfile\nimport threading\n", 1)
    context_import = "from contextlib import redirect_stderr, redirect_stdout\n"
    if context_import not in tests:
        raise RuntimeError("contextlib import işareti bulunamadı")
    tests = tests.replace(
        context_import,
        context_import + "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n",
        1,
    )
    old_import = dedent(
        '''
        from interpreter import (
            DiskReadCaps,
            Interpreter,
            KoscheiRuntimeError,
            KsError,
            run,
        )
        '''
    ).lstrip()
    new_import = dedent(
        '''
        from interpreter import (
            DiskReadCaps,
            Interpreter,
            KoscheiRuntimeError,
            KsError,
            NetCaps,
            Response,
            run,
        )
        '''
    ).lstrip()
    if old_import not in tests:
        raise RuntimeError("genişletilmiş interpreter test importu bulunamadı")
    tests = tests.replace(old_import, new_import, 1)
    tests = add_test_method(
        tests,
        '''
        def test_cross_origin_redirect_returns_ks3402_without_following(self) -> None:
            target_hits = {"count": 0}

            class TargetHandler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:
                    target_hits["count"] += 1
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"secret")

                def log_message(self, format: str, *args: object) -> None:
                    return

            target_server = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
            target_thread = threading.Thread(
                target=target_server.serve_forever, daemon=True
            )
            target_thread.start()
            target_port = target_server.server_address[1]

            class RedirectHandler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:
                    self.send_response(302)
                    self.send_header(
                        "Location", f"http://127.0.0.1:{target_port}/secret"
                    )
                    self.end_headers()

                def log_message(self, format: str, *args: object) -> None:
                    return

            source_server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
            source_thread = threading.Thread(
                target=source_server.serve_forever, daemon=True
            )
            source_thread.start()
            source_port = source_server.server_address[1]
            try:
                result = NetCaps(f"http://127.0.0.1:{source_port}").get(
                    f"http://127.0.0.1:{source_port}/redirect"
                )
            finally:
                source_server.shutdown()
                source_server.server_close()
                source_thread.join()
                target_server.shutdown()
                target_server.server_close()
                target_thread.join()

            self.assertIsInstance(result, KsError)
            self.assertIn("KS3402", result.message)
            self.assertIn(f":{target_port}/secret", result.message)
            self.assertEqual(target_hits["count"], 0)

        def test_same_origin_redirect_is_followed(self) -> None:
            class SameOriginHandler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:
                    if self.path == "/redirect":
                        self.send_response(302)
                        self.send_header("Location", "/ok")
                        self.end_headers()
                        return
                    body = b"ok"
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, format: str, *args: object) -> None:
                    return

            server = ThreadingHTTPServer(("127.0.0.1", 0), SameOriginHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            port = server.server_address[1]
            try:
                result = NetCaps(f"http://127.0.0.1:{port}").get(
                    f"http://127.0.0.1:{port}/redirect"
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

            self.assertIsInstance(result, Response)
            self.assertEqual(result.status(), 200)
            self.assertEqual(result.text(), "ok")
        ''',
    )
    test_path.write_text(tests, encoding="utf-8")

    docs_path = Path("docs/language-core.md")
    docs = docs_path.read_text(encoding="utf-8")
    row = "| KS1401 | Ele alınmayan hata değeri |\n"
    if row not in docs:
        raise RuntimeError("doküman KS1401 satırı bulunamadı")
    docs = docs.replace(
        row,
        row
        + "| KS3105 | Çağrı derinliği sınırı aşıldı |\n"
        + "| KS3402 | Kapsam dışı disk/ağ erişimi veya kapsam dışı ağ yönlendirmesi |\n",
        1,
    )
    docs_path.write_text(docs, encoding="utf-8")


def verify_scope() -> None:
    actual = set(
        subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines()
    )
    if actual != ALLOWED_FILES:
        raise RuntimeError(
            f"Beklenmeyen diff: expected={sorted(ALLOWED_FILES)} actual={sorted(actual)}"
        )


def main() -> None:
    apply_ks3105()
    run_command("python", "-m", "unittest", "discover", "-s", "tests", "-v")

    apply_ks1401()
    run_command("python", "-m", "unittest", "discover", "-s", "tests", "-v")

    apply_redirect_guard()
    run_command("python", "-m", "unittest", "discover", "-s", "tests", "-v")

    print("\n=== KABUL KOMUTLARI ===", flush=True)
    run_command("python", "-m", "unittest", "discover", "-s", "tests", "-v")
    run_command("python", "koschei.py", "check", "examples/runtime_demo.ks")
    run_command("python", "koschei.py", "run", "examples/runtime_demo.ks")
    run_command("python", "koschei.py", "check", "examples/showcase.ks")
    run_command("python", "koschei.py", "run", "examples/showcase.ks")
    verify_scope()


if __name__ == "__main__":
    main()
