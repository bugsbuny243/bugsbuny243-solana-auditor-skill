from pathlib import Path

FILES = {
    "tests/test_interpreter.py": '''from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import http.server
import socketserver
import threading

from interpreter import DiskReadCaps, KoscheiRuntimeError, KsError, NetCaps, run
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

    def test_infinite_recursion_raises_ks3105_not_python_error(self) -> None:
        source = (
            "fn boom(n: Int) -> Int { return boom(n + 1) } "
            "fn main() { let x = boom(0) }"
        )
        with self.assertRaises(KoscheiRuntimeError) as context:
            self.run_source(source)
        self.assertEqual(context.exception.code, "KS3105")

    def test_statement_after_handled_error_still_runs(self) -> None:
        source = (
            'fn main(caps: SystemCaps) { '
            'let ro = caps.disk.allow_read_only("/tmp") '
            'let x = ro.read("/etc/passwd") or "engellendi" '
            'println("1: {x}") '
            'println("2: devam") '
            '}'
        )
        code, output, _ = self.run_source(source)
        self.assertEqual(code, 0)
        self.assertIn("2: devam", output)


class RedirectConfinementTests(unittest.TestCase):
    """Yönlendirmeler yalnızca izinli origin içinde izlenir (KS3402)."""

    @classmethod
    def setUpClass(cls) -> None:
        class Outside(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"KAPSAM-DISI-VERI")

            def log_message(self, *arguments: object) -> None:
                pass

        cls.outside = socketserver.TCPServer(("127.0.0.1", 0), Outside)
        cls.outside_port = cls.outside.server_address[1]

        outside_port = cls.outside_port

        class Allowed(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/outside":
                    self.send_response(302)
                    self.send_header(
                        "Location", f"http://127.0.0.1:{outside_port}/steal"
                    )
                    self.end_headers()
                    return
                if self.path == "/inside":
                    self.send_response(302)
                    self.send_header("Location", "/ok")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"IZINLI-VERI")

            def log_message(self, *arguments: object) -> None:
                pass

        cls.allowed = socketserver.TCPServer(("127.0.0.1", 0), Allowed)
        cls.allowed_port = cls.allowed.server_address[1]

        for server in (cls.outside, cls.allowed):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        for server in (cls.outside, cls.allowed):
            server.shutdown()
            server.server_close()

    def net(self) -> NetCaps:
        return NetCaps(f"http://127.0.0.1:{self.allowed_port}")

    def test_plain_request_inside_origin_succeeds(self) -> None:
        response = self.net().get(f"http://127.0.0.1:{self.allowed_port}/ok")
        self.assertNotIsInstance(response, KsError)
        self.assertEqual(response.text(), "IZINLI-VERI")

    def test_same_origin_redirect_is_followed(self) -> None:
        response = self.net().get(f"http://127.0.0.1:{self.allowed_port}/inside")
        self.assertNotIsInstance(response, KsError)
        self.assertEqual(response.text(), "IZINLI-VERI")

    def test_cross_origin_redirect_is_denied(self) -> None:
        result = self.net().get(f"http://127.0.0.1:{self.allowed_port}/outside")
        self.assertIsInstance(result, KsError)
        self.assertIn("KS3402", result.message)
        self.assertNotIn("KAPSAM-DISI-VERI", result.message)


if __name__ == "__main__":
    unittest.main()
''',
    "tests/test_semantic.py": '''from __future__ import annotations

import unittest

from parser import parse
from semantic import SemanticError, check


class SemanticTests(unittest.TestCase):
    def test_rejects_assignment_to_immutable_variable(self) -> None:
        program = parse("fn main() { let value = 1 value = 2 }")
        with self.assertRaisesRegex(SemanticError, "KS1201"):
            check(program)

    def test_accepts_assignment_to_mutable_variable(self) -> None:
        program = parse("fn main() { let mut value = 1 value = 2 }")
        report = check(program)
        self.assertEqual(report.variables, 1)

    def test_rejects_network_access_without_net_caps(self) -> None:
        program = parse('fn steal() { net.get("https://evil.example") }')
        with self.assertRaisesRegex(SemanticError, "KS2401"):
            check(program)

    def test_accepts_network_access_with_net_caps(self) -> None:
        program = parse(
            'fn fetch(net: NetCaps) { let response = net.get("https://api.example") }'
        )
        report = check(program)
        self.assertGreaterEqual(report.capability_values, 1)

    def test_system_caps_can_create_restricted_net_caps(self) -> None:
        program = parse(
            'fn main(caps: SystemCaps) { '
            'let api = caps.net.allow("https://api.example") '
            'let response = api.get("https://api.example/v1") '
            '}'
        )
        report = check(program)
        self.assertGreaterEqual(report.capability_values, 2)

    def test_root_capability_cannot_do_io_directly(self) -> None:
        program = parse(
            'fn main(caps: SystemCaps) { '
            'let raw = caps.disk '
            'let secret = raw.read("/etc/shadow") '
            '}'
        )
        with self.assertRaisesRegex(SemanticError, "KS2402"):
            check(program)

    def test_narrowed_capability_cannot_be_rewidened(self) -> None:
        program = parse(
            'fn main(caps: SystemCaps) { '
            'let ro = caps.disk.allow_read_only("/tmp/safe") '
            'let widened = ro.allow("/") '
            '}'
        )
        with self.assertRaisesRegex(SemanticError, "KS2403"):
            check(program)

    def test_read_only_capability_cannot_write(self) -> None:
        program = parse(
            'fn main(caps: SystemCaps) { '
            'let ro = caps.disk.allow_read_only("/tmp/safe") '
            'ro.write("/tmp/safe/x", "data") '
            '}'
        )
        with self.assertRaisesRegex(SemanticError, "KS2404"):
            check(program)

    def test_narrowed_capability_passed_to_function_keeps_permissions(self) -> None:
        program = parse(
            'fn load(disk: DiskReadCaps, path: String) -> String or Error { '
            'let content = disk.read(path) or return Error("okunamadı") '
            'return content '
            '} '
            'fn main(caps: SystemCaps) { '
            'let ro = caps.disk.allow_read_only("/etc/app/") '
            'let cfg = load(ro, "/etc/app/config.json") or return '
            '}'
        )
        report = check(program)
        self.assertGreaterEqual(report.capability_values, 3)

    def test_system_caps_has_no_direct_operations(self) -> None:
        program = parse('fn main(caps: SystemCaps) { caps.allow("https://x") }')
        with self.assertRaisesRegex(SemanticError, "KS2402"):
            check(program)

    def test_arithmetic_type_mismatch_is_rejected(self) -> None:
        program = parse('fn main() { let x = "abc" + 5 }')
        with self.assertRaisesRegex(SemanticError, "KS1301"):
            check(program)

    def test_if_condition_must_be_bool(self) -> None:
        program = parse("fn main() { let x = 3 if x { return } }")
        with self.assertRaisesRegex(SemanticError, "KS1301"):
            check(program)

    def test_while_with_comparison_condition_passes(self) -> None:
        program = parse(
            "fn main() { let mut n = 3 while n > 0 { n = n - 1 } }"
        )
        report = check(program)
        self.assertEqual(report.variables, 1)

    def test_block_scoped_let_does_not_leak(self) -> None:
        program = parse(
            "fn main() { if true { let inner = 1 } let x = inner }"
        )
        with self.assertRaisesRegex(SemanticError, "KS1101"):
            check(program)

    def test_interpolation_checks_identifiers(self) -> None:
        program = parse('fn main() { let msg = "selam {missing_name}" }')
        with self.assertRaisesRegex(SemanticError, "KS1101"):
            check(program)

    def test_interpolation_with_known_member_path_passes(self) -> None:
        program = parse(
            'fn greet(user: String) { println("selam {user}") } '
        )
        report = check(program)
        self.assertEqual(report.functions, 1)

    def test_or_else_and_or_block_pass(self) -> None:
        program = parse(
            'fn read_port(raw: String) -> Int or Error { '
            'return raw.to_int() or return Error("geçersiz") '
            '} '
            'fn main() { '
            'let port = read_port("8080") or 8080 '
            'let other = read_port("x") or { println("varsayılan") } '
            '}'
        )
        report = check(program)
        self.assertEqual(report.functions, 2)

    def test_unhandled_capability_call_is_rejected(self) -> None:
        program = parse(
            'fn main(caps: SystemCaps) { '
            'let ro = caps.disk.allow_read_only("/tmp") '
            'ro.read("/etc/passwd") '
            '}'
        )
        with self.assertRaisesRegex(SemanticError, "KS1401"):
            check(program)

    def test_unhandled_error_constructor_is_rejected(self) -> None:
        program = parse('fn main() { Error("bos") }')
        with self.assertRaisesRegex(SemanticError, "KS1401"):
            check(program)

    def test_unhandled_fallible_function_call_is_rejected(self) -> None:
        program = parse(
            'fn f() -> Int or Error { return Error("x") } '
            'fn main() { f() }'
        )
        with self.assertRaisesRegex(SemanticError, "KS1401"):
            check(program)

    def test_error_bound_with_let_is_accepted(self) -> None:
        program = parse(
            'fn main(caps: SystemCaps) { '
            'let ro = caps.disk.allow_read_only("/tmp") '
            'let x = ro.read("/etc/passwd") or "" '
            '}'
        )
        report = check(program)
        self.assertEqual(report.functions, 1)

    def test_error_handled_with_or_block_is_accepted(self) -> None:
        program = parse(
            'fn main(caps: SystemCaps) { '
            'let ro = caps.disk.allow_read_only("/tmp") '
            'ro.read("/etc/passwd") or { println("ele alındı") } '
            '}'
        )
        report = check(program)
        self.assertEqual(report.functions, 1)


if __name__ == "__main__":
    unittest.main()
''',
    "docs/language-core.md": '''# Koschei Language Core v0.1

> Çökmeyen, Hacklenemeyen, Ölümsüz Dil.

Bu belge, çalışan Koschei compiler çekirdeğinin kapsamını sabitler.

## Dört ilke

1. **Yetki olmadan yan etki yok.** Disk, ağ, ortam, süreç — hepsi jeton ister ve jeton derleme zamanında denetlenir.
2. **Null yok.** İleride `Option<T>` ile `Some(value)` / `None` kullanılacaktır.
3. **Hatalar değerdir.** `or return`, `or varsayilan`, `or { ... }` ile ele alınır; sessizce yutulamaz.
4. **Varsayılan değişmezlik.** `let` immutable, `let mut` açık niyet ister.

## Canonical sözdizimi

```ks
fn load_config(disk: DiskReadCaps, path: String) -> String or Error {
    let content = disk.read(path) or return Error("Config okunamadı: {path}")
    return content
}

fn main(caps: SystemCaps) {
    let cfg_read = caps.disk.allow_read_only("/etc/app/")
    let config = load_config(cfg_read, "/etc/app/config.json") or {
        println("Başlatma hatası")
    }

    let mut attempts = 0
    while attempts < 3 {
        attempts = attempts + 1
    }

    if attempts == 3 {
        println("Tamam: {config}")
    }
}
```

## Yetki modeli (derleme zamanında zorlanır)

Kök ve daraltılmış yetkiler **farklı tiplerdir**; bu yüzden daraltma tek yönlüdür:

| İfade | Tip | Yapabildikleri |
|---|---|---|
| `caps.net` | `NetRoot` | yalnızca `allow(origin)` |
| `caps.disk` | `DiskRoot` | yalnızca `allow(path)`, `allow_read_only(path)` |
| `caps.env` | `EnvRoot` | yalnızca `allow(name)` |
| `caps.process` | `ProcessRoot` | yalnızca `allow(cmd)` |
| `NetRoot.allow(...)` | `NetCaps` | `get post put delete request` — `allow` **yok** |
| `DiskRoot.allow(...)` | `DiskCaps` | `read write list delete` — `allow` **yok** |
| `DiskRoot.allow_read_only(...)` | `DiskReadCaps` | `read list` — yazma ve `allow` **yok** |
| `EnvRoot.allow(...)` | `EnvCaps` | `get` |
| `ProcessRoot.allow(...)` | `ProcessCaps` | `run spawn` |

Sonuçlar:
- Kök yetkiyle doğrudan G/Ç yapılamaz → **KS2402**
- Daraltılmış yetki yeniden `allow` çağıramaz → **KS2403**
- Salt-okunur yetki yazamaz → **KS2404**
- Yetkisiz scope'ta yetkili işlem → **KS2401**

## Sözdizimi kuralları

- Büyük harfle başlayan her isim **tip** sayılır; değişken ve fonksiyon adları küçük harfle başlamalıdır.
- `true` / `false` Bool değerleridir; `if` ve `while` koşulları Bool olmalıdır.
- Mantıksal işleçler `&&`, `||`, `!` — `or` anahtar kelimesi yalnızca hata/varsayılan akışı içindir.
- Operatör önceliği: `or` → `||` → `&&` → `== !=` → `< <= > >=` → `+ -` → `* /` → `! -` (unary) → çağrı.
- String interpolasyonu: `"Selam {user.email}"`. v0.1'de yalnızca değişken ve alan erişimi desteklenir; `{1 + 2}` geçersizdir. Düz süslü parantez için `\{` ve `\}` kullanılır.

## 'or' biçimleri

```ks
let a = f() or return Error("üst kata fırlat")
let b = f() or 8080                  // varsayılan değer
let c = f() or { println("logla") }  // blokla ele al
```

## Hata kodları

| Kod | Anlamı |
|---|---|
| KS1101 | Tanımsız isim |
| KS1102 | Aynı scope içinde tekrar tanım |
| KS1201 | Immutable değere atama |
| KS1301 | Tip uyuşmazlığı (`"abc" + 5`, Bool olmayan `if` koşulu vb.) |
| KS1401 | Ele alınmayan hata değeri (sonuç `let` ile bağlanmalı ya da `or` ile ele alınmalı) |
| KS2401 | Gerekli yetki bu scope içinde mevcut değil |
| KS2402 | Kök yetki doğrudan kullanılamaz; önce daraltılmalı |
| KS2403 | Daraltılmış yetki yeniden genişletilemez |
| KS2404 | Bu yetki türü ilgili işleme izin vermez |

Runtime (çalışma anı) hata kodları:

| Kod | Anlamı |
|---|---|
| KS3101 | Tanımsız isim / geçersiz çağrı (savunma katmanı) |
| KS3105 | Çağrı derinliği sınırı aşıldı (512) — sonsuz özyineleme koruması |
| KS3201 | Immutable değere runtime ataması (savunma katmanı) |
| KS3402 | Kapsam dışı erişim: disk yolu, ağ origin'i **veya kapsam dışına çıkan ağ yönlendirmesi** |
| KS3403 | Runtime'da daraltılmış yetkiyi genişletme girişimi |
| KS3404 | Yetki türünün izin vermediği işlem (ör. salt-okunur yetkiyle yazma) |

## v0.1 compiler hattı

```text
.ks source
    -> lexer.py     (interpolasyon, && || !, if/else/while, true/false)
    -> parser.py    (öncelik zinciri, üç 'or' biçimi, kontrol akışı)
    -> ast_nodes.py
    -> semantic.py  (scope, tip, kök/daraltılmış yetki denetimi)
    -> interpreter / code generator (sonraki aşama)
```

## CLI

```bash
python koschei.py tokens examples/capability.ks
python koschei.py ast examples/capability.ks
python koschei.py check examples/capability.ks
```

`check` komutu lexer, parser ve semantic güvenlik kontrollerini birlikte çalıştırır.

## Bilinen sınırlar (v0.1)

- Birleşik dönüş tipleri (`String or Error`) metin olarak taşınır; tam tip denetimi v0.2'de.
- Struct, enum/match, generics, `for` döngüsü, fonksiyon çağrılarında argüman tipi denetimi yok.
- Yol/origin sınırları (`allow("/etc/app/")` kapsamı) statik olarak tip düzeyinde, dinamik olarak runtime aşamasında zorlanacaktır; runtime henüz yazılmadı.
- Tanı mesajları şimdilik Türkçedir; İngilizce yerelleştirme planlanmaktadır.
''',
}

for path, content in FILES.items():
    Path(path).write_text(content, encoding="utf-8")
