from __future__ import annotations

import unittest

from codegen_c import CodegenError, generate_c
from parser import parse
from semantic import SemanticError, check


class SafeTypesAndCodegenTests(unittest.TestCase):
    def test_parses_nested_generic_types(self) -> None:
        program = parse(
            'fn value() -> Result<Option<String>, Error> { '
            'return Err(Error("x")) '
            '}'
        )
        self.assertEqual(
            str(program.declarations[0].return_type),
            "Result<Option<String>, Error>",
        )

    def test_accepts_some_and_none_for_option(self) -> None:
        check(parse('fn some() -> Option<String> { return Some("x") }'))
        check(parse('fn none() -> Option<String> { return None }'))

    def test_rejects_wrong_option_inner_type(self) -> None:
        with self.assertRaisesRegex(SemanticError, "KS1304"):
            check(parse("fn wrong() -> Option<String> { return Some(42) }"))

    def test_accepts_ok_and_err_for_result(self) -> None:
        check(parse("fn ok() -> Result<Int, Error> { return Ok(42) }"))
        check(
            parse(
                'fn err() -> Result<Int, Error> { '
                'return Err(Error("x")) '
                '}'
            )
        )

    def test_checks_function_argument_types(self) -> None:
        source = (
            'fn greet(name: String) { println(name) } '
            'fn main() { greet(7) }'
        )
        with self.assertRaisesRegex(SemanticError, "KS1302"):
            check(parse(source))

    def test_checks_function_argument_count(self) -> None:
        source = (
            'fn greet(name: String) { println(name) } '
            'fn main() { greet() }'
        )
        with self.assertRaisesRegex(SemanticError, "KS1301"):
            check(parse(source))

    def test_codegen_emits_native_main(self) -> None:
        program = parse(
            'fn main() { let name = "Koschei" println(name) }'
        )
        check(program)
        code = generate_c(program)
        self.assertIn("int main(void)", code)
        self.assertIn('printf("%s\\n", name);', code)
        self.assertIn("return 0;", code)

    def test_codegen_rejects_unsupported_capability_runtime_calls(self) -> None:
        program = parse(
            'fn main(caps: SystemCaps) { '
            'let net = caps.net.allow("https://api.example") '
            '}'
        )
        check(program)
        with self.assertRaisesRegex(CodegenError, "KS5002|KS5001"):
            generate_c(program)


if __name__ == "__main__":
    unittest.main()
