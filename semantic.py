"""Koschei AST için semantic ve capability güvenlik denetleyicisi.

Hata kodları:
    KS1101  Tanımsız isim
    KS1102  Aynı scope içinde tekrar tanım
    KS1201  Immutable değere atama
    KS1301  Tip uyuşmazlığı
    KS1401  Ele alınmayan hata değeri
    KS2401  Gerekli yetki bu scope içinde mevcut değil
    KS2402  Kök yetki doğrudan kullanılamaz (önce allow ile daraltılmalı)
    KS2403  Daraltılmış yetki yeniden genişletilemez
    KS2404  Bu yetki türü ilgili işleme izin vermez

Yetki modeli:
    caps.disk           -> DiskRoot   (yalnızca allow / allow_read_only)
    DiskRoot.allow(...) -> DiskCaps   (read/write/list/delete; allow YOK)
    DiskRoot.allow_read_only(...) -> DiskReadCaps (yalnızca read/list)
Kök tipler G/Ç yapamaz; daraltılmış tipler yeniden allow çağıramaz.
Böylece daraltma tek yönlüdür ve derleme zamanında zorlanır.
"""

from __future__ import annotations

from dataclasses import dataclass

from ast_nodes import (
    AssignmentExpression,
    BinaryExpression,
    Block,
    CallExpression,
    Expression,
    ExpressionStatement,
    FunctionDeclaration,
    Identifier,
    IfStatement,
    InterpolatedString,
    LetStatement,
    Literal,
    MemberExpression,
    OrBlockExpression,
    OrElseExpression,
    OrReturnExpression,
    Program,
    ReturnStatement,
    SourceLocation,
    Statement,
    UnaryExpression,
    WhileStatement,
)


CAPABILITY_MEMBERS = {
    "net": "NetRoot",
    "disk": "DiskRoot",
    "env": "EnvRoot",
    "process": "ProcessRoot",
}

ROOT_METHODS: dict[str, dict[str, str]] = {
    "NetRoot": {"allow": "NetCaps"},
    "DiskRoot": {"allow": "DiskCaps", "allow_read_only": "DiskReadCaps"},
    "EnvRoot": {"allow": "EnvCaps"},
    "ProcessRoot": {"allow": "ProcessCaps"},
}

NARROWED_METHODS: dict[str, set[str]] = {
    "NetCaps": {"get", "post", "put", "delete", "request"},
    "DiskCaps": {"read", "write", "delete", "list", "read_file", "write_file"},
    "DiskReadCaps": {"read", "list", "read_file"},
    "EnvCaps": {"get"},
    "ProcessCaps": {"run", "spawn"},
}

NARROWING_METHODS = {"allow", "allow_read_only"}

GUARDED_METHODS: set[str] = set()
for _methods in NARROWED_METHODS.values():
    GUARDED_METHODS.update(_methods)

CAPABILITY_TYPES = set(ROOT_METHODS) | set(NARROWED_METHODS) | {"SystemCaps"}

BUILTIN_CALLS = {
    "print",
    "println",
    "Error",
    "Some",
    "None",
    "Ok",
    "Err",
    "parse_json",
}

COMPARISON_OPERATORS = {"==", "!=", "<", "<=", ">", ">="}
LOGICAL_OPERATORS = {"&&", "||"}
ARITHMETIC_OPERATORS = {"+", "-", "*", "/"}
NUMERIC_TYPES = {"Int", "Float"}


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
            self._check_statements(function.body)
        finally:
            self.scopes.pop()

    def _check_block(self, block: Block) -> None:
        self.scopes.append({})
        try:
            self._check_statements(block)
        finally:
            self.scopes.pop()

    def _check_statements(self, block: Block) -> None:
        for statement in block.statements:
            self._check_statement(statement)

    def _check_statement(self, statement: Statement) -> None:
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
            return

        if isinstance(statement, ReturnStatement):
            if statement.value is not None:
                self._check_expression(statement.value)
            return

        if isinstance(statement, ExpressionStatement):
            self._check_expression(statement.expression)
            if self._is_fallible_call(statement.expression):
                raise SemanticError(
                    "KS1401",
                    "Hata dönebilen çağrının sonucu ele alınmalıdır "
                    "('let ... = ...', 'or return', 'or varsayılan' "
                    "veya 'or { ... }' kullanın).",
                    statement.location,
                )
            return

        if isinstance(statement, IfStatement):
            condition_type = self._check_expression(statement.condition)
            self._require_bool(condition_type, "if koşulu", statement.location)
            self._check_block(statement.then_block)
            if isinstance(statement.else_branch, Block):
                self._check_block(statement.else_branch)
            elif isinstance(statement.else_branch, IfStatement):
                self._check_statement(statement.else_branch)
            return

        if isinstance(statement, WhileStatement):
            condition_type = self._check_expression(statement.condition)
            self._require_bool(condition_type, "while koşulu", statement.location)
            self._check_block(statement.body)
            return

        raise AssertionError(f"Desteklenmeyen statement: {type(statement).__name__}")

    def _check_expression(self, expression: Expression) -> str | None:
        if isinstance(expression, Literal):
            if isinstance(expression.value, bool):
                return "Bool"
            if isinstance(expression.value, str):
                return "String"
            if isinstance(expression.value, int):
                return "Int"
            if isinstance(expression.value, float):
                return "Float"
            return None

        if isinstance(expression, InterpolatedString):
            for part in expression.parts:
                self._check_expression(part)
            return "String"

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
                self.capability_count += 1
                return CAPABILITY_MEMBERS[expression.member]

            if object_type in CAPABILITY_TYPES:
                return None

            return object_type

        if isinstance(expression, CallExpression):
            for argument in expression.arguments:
                self._check_expression(argument)

            if isinstance(expression.callee, MemberExpression):
                receiver_type = self._check_expression(expression.callee.object)
                return self._check_method_call(
                    receiver_type,
                    expression.callee.member,
                    expression.location,
                )

            return self._check_expression(expression.callee)

        if isinstance(expression, BinaryExpression):
            return self._check_binary(expression)

        if isinstance(expression, UnaryExpression):
            operand_type = self._check_expression(expression.operand)
            if expression.operator == "!":
                self._require_bool(operand_type, "'!' işleci", expression.location)
                return "Bool"
            if operand_type is not None and operand_type not in NUMERIC_TYPES:
                raise SemanticError(
                    "KS1301",
                    f"'-' işleci sayısal tip bekler, {operand_type} bulundu.",
                    expression.location,
                )
            return operand_type

        if isinstance(expression, OrReturnExpression):
            value_type = self._check_expression(expression.value)
            if expression.error is not None:
                self._check_expression(expression.error)
            return value_type

        if isinstance(expression, OrElseExpression):
            value_type = self._check_expression(expression.value)
            fallback_type = self._check_expression(expression.fallback)
            return value_type or fallback_type

        if isinstance(expression, OrBlockExpression):
            value_type = self._check_expression(expression.value)
            self._check_block(expression.handler)
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

    def _check_binary(self, expression: BinaryExpression) -> str | None:
        left_type = self._check_expression(expression.left)
        right_type = self._check_expression(expression.right)
        operator = expression.operator

        if operator in LOGICAL_OPERATORS:
            self._require_bool(left_type, f"'{operator}' işlecinin sol tarafı", expression.location)
            self._require_bool(right_type, f"'{operator}' işlecinin sağ tarafı", expression.location)
            return "Bool"

        if operator in COMPARISON_OPERATORS:
            if (
                left_type is not None
                and right_type is not None
                and left_type != right_type
            ):
                raise SemanticError(
                    "KS1301",
                    f"'{operator}' iki farklı tipi karşılaştıramaz: {left_type} ve {right_type}.",
                    expression.location,
                )
            return "Bool"

        if operator in ARITHMETIC_OPERATORS:
            if left_type is not None and right_type is not None:
                if left_type != right_type:
                    raise SemanticError(
                        "KS1301",
                        f"'{operator}' iki farklı tipe uygulanamaz: {left_type} ve {right_type}.",
                        expression.location,
                    )
                if left_type == "String":
                    if operator != "+":
                        raise SemanticError(
                            "KS1301",
                            f"String yalnızca '+' ile birleştirilebilir; '{operator}' geçersiz.",
                            expression.location,
                        )
                    return "String"
                if left_type not in NUMERIC_TYPES:
                    raise SemanticError(
                        "KS1301",
                        f"'{operator}' işleci {left_type} tipine uygulanamaz.",
                        expression.location,
                    )
                return left_type
            return left_type or right_type

        return None

    def _check_method_call(
        self,
        receiver_type: str | None,
        method_name: str,
        location: SourceLocation,
    ) -> str | None:
        if receiver_type in ROOT_METHODS:
            mapping = ROOT_METHODS[receiver_type]
            if method_name in mapping:
                self.capability_count += 1
                return mapping[method_name]
            raise SemanticError(
                "KS2402",
                f"{receiver_type} kök yetkisi doğrudan '{method_name}' yapamaz; "
                f"önce {' veya '.join(sorted(mapping))} ile daraltın.",
                location,
            )

        if receiver_type in NARROWED_METHODS:
            if method_name in NARROWING_METHODS:
                raise SemanticError(
                    "KS2403",
                    f"{receiver_type} daraltılmış bir yetkidir; '{method_name}' ile "
                    "yeniden genişletilemez. Yeni kapsam için kök yetkiden türetin.",
                    location,
                )
            if method_name in NARROWED_METHODS[receiver_type]:
                return None
            raise SemanticError(
                "KS2404",
                f"{receiver_type} yetkisi '{method_name}' işlemine izin vermez.",
                location,
            )

        if receiver_type == "SystemCaps":
            raise SemanticError(
                "KS2402",
                "SystemCaps üzerinde doğrudan işlem yapılamaz; "
                "caps.net / caps.disk gibi kök yetkilerden daraltın.",
                location,
            )

        if method_name in GUARDED_METHODS:
            raise SemanticError(
                "KS2401",
                f"'{method_name}' işlemi için gerekli yetki bu scope içinde mevcut değil.",
                location,
            )

        return None

    def _is_fallible_call(self, expression: Expression) -> bool:
        if not isinstance(expression, CallExpression):
            return False

        callee = expression.callee
        if isinstance(callee, Identifier):
            if callee.name == "Error":
                return True
            function = self.functions.get(callee.name)
            return (
                function is not None
                and function.return_type is not None
                and "Error" in function.return_type.names
            )

        if isinstance(callee, MemberExpression):
            return self._receiver_type(callee.object) in NARROWED_METHODS

        return False

    def _receiver_type(self, expression: Expression) -> str | None:
        if isinstance(expression, Identifier):
            symbol = self._resolve(expression.name)
            return symbol.type_name if symbol is not None else None
        if isinstance(expression, MemberExpression):
            object_type = self._receiver_type(expression.object)
            if object_type == "SystemCaps" and expression.member in CAPABILITY_MEMBERS:
                return CAPABILITY_MEMBERS[expression.member]
            return None
        return None

    def _require_bool(
        self, type_name: str | None, subject: str, location: SourceLocation
    ) -> None:
        if type_name is not None and type_name != "Bool":
            raise SemanticError(
                "KS1301",
                f"{subject} Bool olmalıdır, {type_name} bulundu.",
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
        if symbol.type_name in CAPABILITY_TYPES:
            self.capability_count += 1

    def _resolve(self, name: str) -> Symbol | None:
        for scope in reversed(self.scopes):
            symbol = scope.get(name)
            if symbol is not None:
                return symbol
        return None

    def _raise_unknown_identifier(self, identifier: Identifier) -> None:
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
