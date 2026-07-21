"""Koschei AST için ilk semantic ve capability güvenlik denetleyicisi."""

from __future__ import annotations

from dataclasses import dataclass

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
    Program,
    ReturnStatement,
    SourceLocation,
)


CAPABILITY_MEMBERS = {
    "net": "NetCaps",
    "disk": "DiskCaps",
    "env": "EnvCaps",
    "process": "ProcessCaps",
}

CAPABILITY_METHODS = {
    "NetCaps": {"allow", "get", "post", "put", "delete", "request"},
    "DiskCaps": {"allow", "read", "write", "delete", "list"},
    "EnvCaps": {"allow", "get"},
    "ProcessCaps": {"allow", "run", "spawn"},
}

BUILTIN_CALLS = {
    "print",
    "println",
    "Error",
    "Some",
    "None",
    "Ok",
    "Err",
}


@dataclass(frozen=True, slots=True)
class Symbol:
    name: str
    type_name: str | None
    is_mutable: bool
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class SemanticReport:
    functions: int
    variables: int
    capability_values: int


class SemanticError(Exception):
    def __init__(self, code: str, message: str, location: SourceLocation) -> None:
        self.code = code
        self.message = message
        self.location = location
        super().__init__(
            f"{code} [satır {location.line}, sütun {location.column}]: {message}"
        )


class SemanticChecker:
    def __init__(self, program: Program) -> None:
        self.program = program
        self.functions = {declaration.name: declaration for declaration in program.declarations}
        self.scopes: list[dict[str, Symbol]] = []
        self.variable_count = 0
        self.capability_count = 0

    def check(self) -> SemanticReport:
        for declaration in self.program.declarations:
            self._check_function(declaration)

        return SemanticReport(
            functions=len(self.program.declarations),
            variables=self.variable_count,
            capability_values=self.capability_count,
        )

    def _check_function(self, function: FunctionDeclaration) -> None:
        self.scopes.append({})
        try:
            for parameter in function.parameters:
                type_name = str(parameter.type_ref)
                self._declare(
                    Symbol(
                        name=parameter.name,
                        type_name=type_name,
                        is_mutable=False,
                        location=parameter.location,
                    )
                )
            self._check_block(function.body)
        finally:
            self.scopes.pop()

    def _check_block(self, block: Block) -> None:
        for statement in block.statements:
            if isinstance(statement, LetStatement):
                value_type = self._check_expression(statement.value)
                self._declare(
                    Symbol(
                        name=statement.name,
                        type_name=value_type,
                        is_mutable=statement.is_mutable,
                        location=statement.location,
                    )
                )
                self.variable_count += 1
                continue

            if isinstance(statement, ReturnStatement):
                if statement.value is not None:
                    self._check_expression(statement.value)
                continue

            if isinstance(statement, ExpressionStatement):
                self._check_expression(statement.expression)
                continue

            raise AssertionError(f"Desteklenmeyen statement: {type(statement).__name__}")

    def _check_expression(self, expression: Expression) -> str | None:
        if isinstance(expression, Literal):
            if isinstance(expression.value, str):
                return "String"
            if isinstance(expression.value, int):
                return "Int"
            if isinstance(expression.value, float):
                return "Float"
            return None

        if isinstance(expression, Identifier):
            symbol = self._resolve(expression.name)
            if symbol is not None:
                return symbol.type_name
            if expression.name in self.functions:
                function = self.functions[expression.name]
                return str(function.return_type) if function.return_type else "Void"
            if expression.name in BUILTIN_CALLS:
                return None
            self._raise_unknown_identifier(expression)

        if isinstance(expression, MemberExpression):
            object_type = self._check_expression(expression.object)
            if object_type == "SystemCaps" and expression.member in CAPABILITY_MEMBERS:
                capability_type = CAPABILITY_MEMBERS[expression.member]
                self.capability_count += 1
                return capability_type
            return object_type

        if isinstance(expression, CallExpression):
            for argument in expression.arguments:
                self._check_expression(argument)

            if isinstance(expression.callee, MemberExpression):
                receiver_type = self._check_expression(expression.callee.object)
                method_name = expression.callee.member
                self._check_capability_call(
                    expression.callee.object,
                    receiver_type,
                    method_name,
                    expression.location,
                )
                if method_name == "allow" and receiver_type in CAPABILITY_METHODS:
                    return receiver_type
                return None

            return self._check_expression(expression.callee)

        if isinstance(expression, OrReturnExpression):
            value_type = self._check_expression(expression.value)
            if expression.error is not None:
                self._check_expression(expression.error)
            return value_type

        if isinstance(expression, AssignmentExpression):
            value_type = self._check_expression(expression.value)
            if isinstance(expression.target, Identifier):
                symbol = self._resolve(expression.target.name)
                if symbol is None:
                    self._raise_unknown_identifier(expression.target)
                if not symbol.is_mutable:
                    raise SemanticError(
                        "KS1201",
                        f"'{symbol.name}' immutable bir değerdir; değiştirmek için 'let mut' kullanın.",
                        expression.location,
                    )
                return symbol.type_name or value_type

            self._check_expression(expression.target)
            return value_type

        raise AssertionError(f"Desteklenmeyen expression: {type(expression).__name__}")

    def _check_capability_call(
        self,
        receiver: Expression,
        receiver_type: str | None,
        method_name: str,
        location: SourceLocation,
    ) -> None:
        for capability_type, methods in CAPABILITY_METHODS.items():
            if method_name not in methods:
                continue
            if receiver_type == capability_type:
                return

            root_name = self._root_identifier(receiver)
            if root_name in CAPABILITY_MEMBERS or method_name != "allow":
                raise SemanticError(
                    "KS2401",
                    f"'{method_name}' işlemi için {capability_type} yetkisi bu scope içinde mevcut değil.",
                    location,
                )

    def _declare(self, symbol: Symbol) -> None:
        scope = self.scopes[-1]
        if symbol.name in scope:
            raise SemanticError(
                "KS1102",
                f"'{symbol.name}' bu scope içinde zaten tanımlı.",
                symbol.location,
            )
        scope[symbol.name] = symbol
        if symbol.type_name in CAPABILITY_METHODS or symbol.type_name == "SystemCaps":
            self.capability_count += 1

    def _resolve(self, name: str) -> Symbol | None:
        for scope in reversed(self.scopes):
            symbol = scope.get(name)
            if symbol is not None:
                return symbol
        return None

    @staticmethod
    def _root_identifier(expression: Expression) -> str | None:
        while isinstance(expression, MemberExpression):
            expression = expression.object
        return expression.name if isinstance(expression, Identifier) else None

    @staticmethod
    def _raise_unknown_identifier(identifier: Identifier) -> None:
        if identifier.name in CAPABILITY_MEMBERS:
            required = CAPABILITY_MEMBERS[identifier.name]
            raise SemanticError(
                "KS2401",
                f"{required} yetkisi bu scope içinde mevcut değil.",
                identifier.location,
            )
        raise SemanticError(
            "KS1101",
            f"Tanımsız isim: '{identifier.name}'.",
            identifier.location,
        )


def check(program: Program) -> SemanticReport:
    return SemanticChecker(program).check()
