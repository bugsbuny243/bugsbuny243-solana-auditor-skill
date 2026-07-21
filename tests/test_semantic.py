from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
