"""Temel Koschei (.ks) sözcük çözümleyicisi.

Kaynak kodu Token nesnelerine dönüştürür. Boşluklar ve // yorumları
atlanır; anahtar kelimeler, tip isimleri, semboller, metinler ve sayılar
ayrı token türleri olarak üretilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenType(Enum):
    # Anahtar kelimeler
    FN = auto()
    LET = auto()
    MUT = auto()
    OR = auto()
    RETURN = auto()

    # İsimler ve değerler
    TYPE = auto()
    IDENTIFIER = auto()
    STRING = auto()
    NUMBER = auto()

    # Tek karakterli semboller
    LEFT_PAREN = auto()       # (
    RIGHT_PAREN = auto()      # )
    LEFT_BRACE = auto()       # {
    RIGHT_BRACE = auto()      # }
    COMMA = auto()            # ,
    COLON = auto()            # :
    DOT = auto()              # .
    EQUAL = auto()            # =
    PLUS = auto()             # +
    MINUS = auto()            # -
    STAR = auto()             # *
    SLASH = auto()            # /
    SEMICOLON = auto()        # ;

    # Çok karakterli semboller
    ARROW = auto()            # ->
    EQUAL_EQUAL = auto()      # ==
    BANG_EQUAL = auto()       # !=
    LESS = auto()             # <
    LESS_EQUAL = auto()       # <=
    GREATER = auto()          # >
    GREATER_EQUAL = auto()    # >=

    EOF = auto()


@dataclass(frozen=True, slots=True)
class Token:
    type: TokenType
    value: Any
    line: int
    column: int

    def __repr__(self) -> str:
        return (
            f"Token({self.type.name:<13}, {self.value!r}, "
            f"line={self.line}, column={self.column})"
        )


class LexerError(SyntaxError):
    """Koschei kaynak kodu tokenize edilemediğinde yükseltilir."""


class Lexer:
    KEYWORDS = {
        "fn": TokenType.FN,
        "let": TokenType.LET,
        "mut": TokenType.MUT,
        "or": TokenType.OR,
        "return": TokenType.RETURN,
    }

    # Yerleşik tipler burada açıkça tanımlıdır. Ayrıca büyük harfle başlayan
    # kullanıcı tipleri de TYPE olarak sınıflandırılır.
    BUILTIN_TYPES = {
        "SystemCaps",
        "NetCaps",
        "DiskCaps",
        "EnvCaps",
        "ProcessCaps",
        "String",
        "Int",
        "Float",
        "Bool",
        "Void",
        "Error",
        "Result",
        "Option",
    }

    SINGLE_CHAR_TOKENS = {
        "(": TokenType.LEFT_PAREN,
        ")": TokenType.RIGHT_PAREN,
        "{": TokenType.LEFT_BRACE,
        "}": TokenType.RIGHT_BRACE,
        ",": TokenType.COMMA,
        ":": TokenType.COLON,
        ".": TokenType.DOT,
        "+": TokenType.PLUS,
        "*": TokenType.STAR,
        ";": TokenType.SEMICOLON,
    }

    ESCAPES = {
        "n": "\n",
        "r": "\r",
        "t": "\t",
        '"': '"',
        "\\": "\\",
    }

    def __init__(self, source: str) -> None:
        self.source = source
        self.start = 0
        self.current = 0
        self.line = 1
        self.column = 1
        self.start_line = 1
        self.start_column = 1
        self.tokens: list[Token] = []

    def tokenize(self) -> list[Token]:
        while not self._is_at_end():
            self.start = self.current
            self.start_line = self.line
            self.start_column = self.column
            self._scan_token()

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens

    def _scan_token(self) -> None:
        char = self._advance()

        # Boşluklar token üretmez.
        if char in {" ", "\r", "\t", "\n"}:
            return

        # // yorumları satır sonuna kadar atlanır.
        if char == "/":
            if self._match("/"):
                while self._peek() not in {"\n", "\0"}:
                    self._advance()
                return
            self._add_token(TokenType.SLASH, "/")
            return

        if char == '"':
            self._string()
            return

        if char.isdigit():
            self._number()
            return

        if char.isalpha() or char == "_":
            self._identifier()
            return

        if char == "-":
            if self._match(">"):
                self._add_token(TokenType.ARROW, "->")
            else:
                self._add_token(TokenType.MINUS, "-")
            return

        if char == "=":
            if self._match("="):
                self._add_token(TokenType.EQUAL_EQUAL, "==")
            else:
                self._add_token(TokenType.EQUAL, "=")
            return

        if char == "!":
            if self._match("="):
                self._add_token(TokenType.BANG_EQUAL, "!=")
                return
            self._error("Beklenmeyen '!'. '!=' kullanmak mı istediniz?")

        if char == "<":
            if self._match("="):
                self._add_token(TokenType.LESS_EQUAL, "<=")
            else:
                self._add_token(TokenType.LESS, "<")
            return

        if char == ">":
            if self._match("="):
                self._add_token(TokenType.GREATER_EQUAL, ">=")
            else:
                self._add_token(TokenType.GREATER, ">")
            return

        token_type = self.SINGLE_CHAR_TOKENS.get(char)
        if token_type is not None:
            self._add_token(token_type, char)
            return

        self._error(f"Geçersiz karakter: {char!r}")

    def _identifier(self) -> None:
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()

        text = self.source[self.start:self.current]
        token_type = self.KEYWORDS.get(text)

        if token_type is None:
            if text in self.BUILTIN_TYPES or text[:1].isupper():
                token_type = TokenType.TYPE
            else:
                token_type = TokenType.IDENTIFIER

        self._add_token(token_type, text)

    def _number(self) -> None:
        while self._peek().isdigit():
            self._advance()

        is_float = False
        if self._peek() == "." and self._peek_next().isdigit():
            is_float = True
            self._advance()
            while self._peek().isdigit():
                self._advance()

        text = self.source[self.start:self.current]
        value: int | float = float(text) if is_float else int(text)
        self._add_token(TokenType.NUMBER, value)

    def _string(self) -> None:
        value: list[str] = []

        while not self._is_at_end():
            char = self._advance()

            if char == '"':
                self._add_token(TokenType.STRING, "".join(value))
                return

            if char == "\\":
                if self._is_at_end():
                    self._error("Tamamlanmamış kaçış dizisi.")
                escaped = self._advance()
                if escaped not in self.ESCAPES:
                    self._error(f"Geçersiz kaçış dizisi: \\{escaped}")
                value.append(self.ESCAPES[escaped])
                continue

            value.append(char)

        self._error("Kapatılmamış metin değeri.")

    def _add_token(self, token_type: TokenType, value: Any) -> None:
        self.tokens.append(
            Token(token_type, value, self.start_line, self.start_column)
        )

    def _advance(self) -> str:
        char = self.source[self.current]
        self.current += 1

        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

        return char

    def _match(self, expected: str) -> bool:
        if self._is_at_end() or self.source[self.current] != expected:
            return False
        self._advance()
        return True

    def _peek(self) -> str:
        return "\0" if self._is_at_end() else self.source[self.current]

    def _peek_next(self) -> str:
        if self.current + 1 >= len(self.source):
            return "\0"
        return self.source[self.current + 1]

    def _is_at_end(self) -> bool:
        return self.current >= len(self.source)

    def _error(self, message: str) -> None:
        raise LexerError(
            f"[satır {self.start_line}, sütun {self.start_column}] {message}"
        )


def tokenize(source: str) -> list[Token]:
    """Kolay kullanım için yardımcı fonksiyon."""
    return Lexer(source).tokenize()


if __name__ == "__main__":
    sample_code = r'''
// Kısıtlı ağ fonksiyonu
fn fetch_data(net: NetCaps, url: String) -> String or Error {
    let mut retry_count = 3
    let response = net.get(url) or return Error("Veri alınamadı")
    return response.text()
}

fn main(caps: SystemCaps) {
    // Yetki yalnızca bu domaine açıktır.
    let allowed_net = caps.net.allow("https://api.example.com")
    let result = fetch_data(allowed_net, "https://api.example.com/v1")
}
'''

    print("KOSCHEI LEXER TEST\n" + "=" * 60)
    for token in tokenize(sample_code):
        print(token)
