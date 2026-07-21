from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from ast_nodes import MatchStatement
from codegen_c import generate_c
from koschei import find_c_compiler
from lexer import TokenType, tokenize
from parser import parse
from semantic import SemanticError, check


SOURCE = '''
fn maybe_value(enabled: Bool) -> Option<Int> {
    if enabled { return Some(42) }
    return None
}

fn calculate(enabled: Bool) -> Result<Int, Error> {
    if enabled { return Ok(7) }
    return Err(Error("disabled"))
}

fn main() {
    match maybe_value(true) {
        Some(value) => { println(value) }
        None => { println(0) }
    }
    match calculate(false) {
        Ok(value) => { println(value) }
        Err(error) => { println(error) }
    }
    println("Koschei match: PASS")
}
'''


class MatchTests(unittest.TestCase):
    def test_lexer_recognizes_match_and_fat_arrow(self) -> None:
        tokens = tokenize("match value { Some(x) => { println(x) } }")
        token_types = [item.type for item in tokens]
        self.assertIn(TokenType.MATCH, token_types)
        self.assertIn(TokenType.FAT_ARROW, token_types)

    def test_parser_builds_match_arms_and_bindings(self) -> None:
        program = parse(SOURCE)
        statement = program.declarations[-1].body.statements[0]
        self.assertIsInstance(statement, MatchStatement)
        self.assertEqual([arm.pattern.kind for arm in statement.arms], ["Some", "None"])
        self.assertEqual(statement.arms[0].pattern.binding, "value")
        self.assertIsNone(statement.arms[1].pattern.binding)

    def test_semantic_accepts_exhaustive_option_and_result_matches(self) -> None:
        report = check(parse(SOURCE))
        self.assertEqual(report.functions, 3)

    def test_semantic_rejects_non_exhaustive_match(self) -> None:
        source = (
            "fn maybe() -> Option<Int> { return Some(1) } "
            "fn main() { match maybe() { Some(value) => { println(value) } } }"
        )
        with self.assertRaisesRegex(SemanticError, "KS1503"):
            check(parse(source))

    def test_semantic_rejects_duplicate_match_arm(self) -> None:
        source = (
            "fn maybe() -> Option<Int> { return Some(1) } "
            "fn main() { match maybe() { "
            "Some(a) => { println(a) } Some(b) => { println(b) } "
            "None => { println(0) } } }"
        )
        with self.assertRaisesRegex(SemanticError, "KS1502"):
            check(parse(source))

    def test_match_binding_does_not_escape_arm_scope(self) -> None:
        source = (
            "fn maybe() -> Option<Int> { return Some(1) } "
            "fn main() { match maybe() { "
            "Some(value) => { println(value) } None => { println(0) } "
            "} println(value) }"
        )
        with self.assertRaisesRegex(SemanticError, "KS1101"):
            check(parse(source))

    def test_codegen_evaluates_match_value_once(self) -> None:
        program = parse(SOURCE)
        check(program)
        code = generate_c(program)
        self.assertIn("__ks_match_", code)
        self.assertEqual(code.count("maybe_value(true)"), 1)

    def test_native_match_program_compiles_and_runs(self) -> None:
        program = parse(SOURCE)
        check(program)
        code = generate_c(program)

        with tempfile.TemporaryDirectory(prefix="koschei-match-") as directory:
            c_path = Path(directory) / "program.c"
            binary = Path(directory) / "program"
            c_path.write_text(code, encoding="utf-8")
            subprocess.run(
                [
                    find_c_compiler(),
                    str(c_path),
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-o",
                    str(binary),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            completed = subprocess.run(
                [str(binary)],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(
            completed.stdout,
            "42\ndisabled\nKoschei match: PASS\n",
        )


if __name__ == "__main__":
    unittest.main()
