"""Koschei (.ks) için recursive-descent parser prototipi."""

from __future__ import annotations

from ast_nodes import (
    AssignmentExpression,
    Block,
    CallExpression,
    Expression,
    ExpressionStatement,
    FunctionDeclaration,
    Identifier,
    LetStatement,
    Literal,
    MemberExpression,
    OrReturnExpression,
    Parameter,
    Program,
    ReturnStatement,
    SourceLocation,
    Statement,
    TypeRef,
)
from lexer import Token, TokenType, tokenize


class ParserError(SyntaxError):
    """Koschei token akışı geçerli bir programa dönüştürülemediğinde yükseltilir."""


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.current = 0

    @classmethod
    def from_source(cls, source: str) -> "Parser":
        return cls(tokenize(source))

    def parse(self) -> Program:
        declarations: list[FunctionDeclaration] = []
        while not self._is_at_end():
            declarations.append(self._function_declaration())
        return Program(tuple(declarations))

    def _function_declaration(self) -> FunctionDeclaration:
        fn_token = self._consume(TokenType.FN, "Fonksiyon 'fn' ile başlamalıdır.")
        name = self._consume(TokenType.IDENTIFIER, "Fonksiyon adı bekleniyordu.")
        self._consume(TokenType.LEFT_PAREN, "Fonksiyon adından sonra '(' bekleniyordu.")

        parameters: list[Parameter] = []
        if not self._check(TokenType.RIGHT_PAREN):
            while True:
                parameters.append(self._parameter())
                if not self._match(TokenType.COMMA):
                    break

        self._consume(TokenType.RIGHT_PAREN, "Parametrelerden sonra ')' bekleniyordu.")
        return_type = self._type_ref() if self._match(TokenType.ARROW) else None
        body = self._block()
        return FunctionDeclaration(
            name=name.value,
            parameters=tuple(parameters),
            return_type=return_type,
            body=body,
            location=self._location(fn_token),
        )

    def _parameter(self) -> Parameter:
        name = self._consume(TokenType.IDENTIFIER, "Parametre adı bekleniyordu.")
        self._consume(TokenType.COLON, "Parametre adından sonra ':' bekleniyordu.")
        return Parameter(name.value, self._type_ref(), self._location(name))

    def _type_ref(self) -> TypeRef:
        first = self._single_type_ref()
        alternatives = [first]
        while self._match(TokenType.OR):
            alternatives.append(self._single_type_ref())
        if len(alternatives) == 1:
            return first
        return TypeRef(
            name="Union",
            location=first.location,
            alternatives=tuple(alternatives),
        )

    def _single_type_ref(self) -> TypeRef:
        token = self._consume(TokenType.TYPE, "Tip adı bekleniyordu.")
        arguments: list[TypeRef] = []
        if self._match(TokenType.LESS):
            while True:
                arguments.append(self._type_ref())
                if not self._match(TokenType.COMMA):
                    break
            self._consume(TokenType.GREATER, "Generic tip sonunda '>' bekleniyordu.")
        return TypeRef(
            name=token.value,
            location=self._location(token),
            arguments=tuple(arguments),
        )

    def _block(self) -> Block:
        self._consume(TokenType.LEFT_BRACE, "Blok başlangıcı için '{' bekleniyordu.")
        statements: list[Statement] = []
        while not self._check(TokenType.RIGHT_BRACE) and not self._is_at_end():
            statements.append(self._statement())
        self._consume(TokenType.RIGHT_BRACE, "Blok sonunda '}' bekleniyordu.")
        return Block(tuple(statements))

    def _statement(self) -> Statement:
        if self._match(TokenType.LET):
            return self._let_statement(self._previous())
        if self._match(TokenType.RETURN):
            return self._return_statement(self._previous())
        expression = self._expression()
        self._match(TokenType.SEMICOLON)
        return ExpressionStatement(expression, expression.location)

    def _let_statement(self, let_token: Token) -> LetStatement:
        is_mutable = self._match(TokenType.MUT)
        name = self._consume(TokenType.IDENTIFIER, "Değişken adı bekleniyordu.")
        self._consume(TokenType.EQUAL, "Değişken tanımında '=' bekleniyordu.")
        value = self._expression()
        self._match(TokenType.SEMICOLON)
        return LetStatement(
            name=name.value,
            is_mutable=is_mutable,
            value=value,
            location=self._location(let_token),
        )

    def _return_statement(self, return_token: Token) -> ReturnStatement:
        value: Expression | None = None
        if not self._check(TokenType.RIGHT_BRACE) and not self._check(TokenType.SEMICOLON):
            value = self._expression()
        self._match(TokenType.SEMICOLON)
        return ReturnStatement(value, self._location(return_token))

    def _expression(self) -> Expression:
        return self._assignment()

    def _assignment(self) -> Expression:
        expression = self._or_return()
        if self._match(TokenType.EQUAL):
            equals = self._previous()
            value = self._assignment()
            if not isinstance(expression, (Identifier, MemberExpression)):
                self._error(equals, "Geçersiz atama hedefi.")
            return AssignmentExpression(expression, value, self._location(equals))
        return expression

    def _or_return(self) -> Expression:
        expression = self._call()
        if self._match(TokenType.OR):
            or_token = self._previous()
            self._consume(TokenType.RETURN, "İlk sürümde 'or' sonrasında 'return' bekleniyor.")
            error: Expression | None = None
            if not self._check(TokenType.RIGHT_BRACE) and not self._check(TokenType.SEMICOLON):
                error = self._call()
            return OrReturnExpression(expression, error, self._location(or_token))
        return expression

    def _call(self) -> Expression:
        expression = self._primary()
        while True:
            if self._match(TokenType.LEFT_PAREN):
                expression = self._finish_call(expression, self._previous())
            elif self._match(TokenType.DOT):
                member = self._consume(
                    TokenType.IDENTIFIER,
                    "'.' sonrasında alan veya metot adı bekleniyordu.",
                )
                expression = MemberExpression(expression, member.value, self._location(member))
            else:
                break
        return expression

    def _finish_call(self, callee: Expression, left_paren: Token) -> CallExpression:
        arguments: list[Expression] = []
        if not self._check(TokenType.RIGHT_PAREN):
            while True:
                arguments.append(self._expression())
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RIGHT_PAREN, "Fonksiyon çağrısı sonunda ')' bekleniyordu.")
        return CallExpression(callee, tuple(arguments), self._location(left_paren))

    def _primary(self) -> Expression:
        if self._match(TokenType.STRING, TokenType.NUMBER):
            token = self._previous()
            return Literal(token.value, self._location(token))
        if self._match(TokenType.IDENTIFIER, TokenType.TYPE):
            token = self._previous()
            return Identifier(token.value, self._location(token))
        if self._match(TokenType.LEFT_PAREN):
            expression = self._expression()
            self._consume(TokenType.RIGHT_PAREN, "İfade sonunda ')' bekleniyordu.")
            return expression
        self._error(self._peek(), "İfade bekleniyordu.")

    def _match(self, *types: TokenType) -> bool:
        for token_type in types:
            if self._check(token_type):
                self._advance()
                return True
        return False

    def _consume(self, token_type: TokenType, message: str) -> Token:
        if self._check(token_type):
            return self._advance()
        self._error(self._peek(), message)

    def _check(self, token_type: TokenType) -> bool:
        if self._is_at_end():
            return token_type is TokenType.EOF
        return self._peek().type is token_type

    def _advance(self) -> Token:
        if not self._is_at_end():
            self.current += 1
        return self._previous()

    def _is_at_end(self) -> bool:
        return self._peek().type is TokenType.EOF

    def _peek(self) -> Token:
        return self.tokens[self.current]

    def _previous(self) -> Token:
        return self.tokens[self.current - 1]

    @staticmethod
    def _location(token: Token) -> SourceLocation:
        return SourceLocation(token.line, token.column)

    @staticmethod
    def _error(token: Token, message: str) -> None:
        raise ParserError(f"[satır {token.line}, sütun {token.column}] {message}")


def parse(source: str) -> Program:
    """Kaynak metni tek çağrıda AST'ye dönüştürür."""
    return Parser.from_source(source).parse()
