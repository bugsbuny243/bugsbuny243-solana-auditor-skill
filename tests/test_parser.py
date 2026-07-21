from __future__ import annotations

import unittest

from ast_nodes import LetStatement, OrReturnExpression, ReturnStatement
from parser import ParserError, parse


SAMPLE = '''
fn fetch_data(net: NetCaps, url: String) -> String or Error {
    let response = net.get(url) or return Error("Veri alınamadı")
    return response.text()
}

fn main(caps: SystemCaps) {
    let allowed_net = caps.net.allow("https://api.example.com")
    let mut retry_count = 3
    return
}
'''


class ParserTests(unittest.TestCase):
    def test_parses_functions_parameters_and_union_return_type(self) -> None:
        program = parse(SAMPLE)

        self.assertEqual(len(program.declarations), 2)
        fetch_data = program.declarations[0]
        self.assertEqual(fetch_data.name, "fetch_data")
        self.assertEqual([item.name for item in fetch_data.parameters], ["net", "url"])
        self.assertEqual(str(fetch_data.return_type), "String or Error")

    def test_parses_or_return_and_mutability_metadata(self) -> None:
        program = parse(SAMPLE)
        fetch_data, main = program.declarations

        response = fetch_data.body.statements[0]
        self.assertIsInstance(response, LetStatement)
        self.assertFalse(response.is_mutable)
        self.assertIsInstance(response.value, OrReturnExpression)

        retry_count = main.body.statements[1]
        self.assertIsInstance(retry_count, LetStatement)
        self.assertTrue(retry_count.is_mutable)
        self.assertIsInstance(main.body.statements[-1], ReturnStatement)

    def test_reports_missing_closing_brace(self) -> None:
        with self.assertRaisesRegex(ParserError, "Blok sonunda"):
            parse("fn main() { let value = 1")


if __name__ == "__main__":
    unittest.main()
