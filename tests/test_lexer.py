from __future__ import annotations

import unittest

from lexer import LexerError, TokenType, tokenize


class LexerTests(unittest.TestCase):
    def test_keywords_types_symbols_and_values(self) -> None:
        source = '''
        // yorum atlanmalı
        fn main(caps: SystemCaps) {
            let mut count = 42
            let net = caps.net
            return "ok"
        }
        '''

        tokens = tokenize(source)
        token_types = [token.type for token in tokens]

        self.assertIn(TokenType.FN, token_types)
        self.assertIn(TokenType.LET, token_types)
        self.assertIn(TokenType.MUT, token_types)
        self.assertIn(TokenType.RETURN, token_types)
        self.assertIn(TokenType.TYPE, token_types)
        self.assertIn(TokenType.DOT, token_types)
        self.assertIn(TokenType.STRING, token_types)
        self.assertIn(TokenType.NUMBER, token_types)
        self.assertEqual(tokens[-1].type, TokenType.EOF)

    def test_comment_content_does_not_become_tokens(self) -> None:
        tokens = tokenize("let value = 1 // hidden_name\nreturn value")
        values = [token.value for token in tokens]
        self.assertNotIn("hidden_name", values)

    def test_unterminated_string_reports_location(self) -> None:
        with self.assertRaisesRegex(LexerError, r"satır 1, sütun 9"):
            tokenize('let x = "unfinished')


if __name__ == "__main__":
    unittest.main()
