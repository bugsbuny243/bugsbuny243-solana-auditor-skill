from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from ast_nodes import BinaryExpression, IfStatement, WhileStatement
from codegen_c import generate_c
from koschei import find_c_compiler
from lexer import TokenType, tokenize
from parser import parse
from semantic import SemanticError, check


class ControlFlowTests(unittest.TestCase):
    def test_lexer_recognizes_control_flow_and_bools(self) -> None:
        tokens = tokenize("if true { while false { } } else { }")
        token_types = [item.type for item in tokens]
        self.assertIn(TokenType.IF, token_types)
        self.assertIn(TokenType.ELSE, token_types)
        self.assertIn(TokenType.WHILE, token_types)
        self.assertIn(TokenType.TRUE, token_types)
        self.assertIn(TokenType.FALSE, token_types)

    def test_parser_respects_arithmetic_precedence(self) -> None:
        program = parse("fn main() { let value = 1 + 2 * 3 }")
        value = program.declarations[0].body.statements[0].value
        self.assertIsInstance(value, BinaryExpression)
        self.assertEqual(value.operator, "+")
        self.assertIsInstance(value.right, BinaryExpression)
        self.assertEqual(value.right.operator, "*")

    def test_parser_builds_if_and_while_statements(self) -> None:
        program = parse(
            "fn main() { let mut n = 2 while n > 0 { "
            "if n == 1 { println(n) } n = n - 1 } }"
        )
        body = program.declarations[0].body.statements
        self.assertIsInstance(body[1], WhileStatement)
        self.assertIsInstance(body[1].body.statements[0], IfStatement)

    def test_semantic_requires_boolean_conditions(self) -> None:
        with self.assertRaisesRegex(SemanticError, "KS1305"):
            check(parse("fn main() { if 1 { println(1) } }"))

    def test_semantic_rejects_invalid_arithmetic_types(self) -> None:
        with self.assertRaisesRegex(SemanticError, "KS1305"):
            check(parse('fn main() { let value = "x" - 1 }'))

    def test_codegen_runs_countdown_program(self) -> None:
        source = """
        fn main() {
            let mut count = 3
            while count > 0 {
                println(count)
                count = count - 1
            }
            if count == 0 {
                println(99)
            } else {
                println(0)
            }
        }
        """
        program = parse(source)
        check(program)
        code = generate_c(program)
        self.assertIn("while (count > 0)", code)
        self.assertIn("if (count == 0)", code)
        with tempfile.TemporaryDirectory() as directory:
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
            )
            completed = subprocess.run(
                [str(binary)], capture_output=True, text=True, check=True
            )
        self.assertEqual(completed.stdout, "3\n2\n1\n99\n")


if __name__ == "__main__":
    unittest.main()
