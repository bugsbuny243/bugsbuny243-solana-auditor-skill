"""Koschei AST için semantic, tip ve capability güvenlik denetleyicisi."""

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
    LetStatement,
    Literal,
    MemberExpression,
    OrReturnExpression,
    Program,
    ReturnStatement,
    SourceLocation,
    UnaryExpression,
    WhileStatement,
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

BUILTIN_CALLS = {"print", "println", "Error", "Some", "Ok", "Err"}
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
        self.functions = {item.name: item for item in program.declarations}
        self.scopes: list[dict[str, Symbol]] = []
        self.variable_count = 0
        self.capability_count = 0
        self.current_function: FunctionDeclaration | None = None

    def check(self) -> SemanticReport:
        if len(self.functions) != len(self.program.declarations):
            seen: set[str] = set()
            for function in self.program.declarations:
                if function.name in seen:
                    raise SemanticError(
                        "KS1103",
                        f"'{function.name}' fonksiyonu birden fazla tanımlandı.",
                        function.location,
                    )
                seen.add(function.name)

        for declaration in self.program.declarations:
            self._check_function(declaration)

        return SemanticReport(
            functions=len(self.program.declarations),
            variables=self.variable_count,
            capability_values=self.capability_count,
        )

    def _check_function(self, function: FunctionDeclaration) -> None:
        self.scopes.append({})
        previous = self.current_function
        self.current_function = function
        try:
            for parameter in function.parameters:
                self._declare(
                    Symbol(
                        parameter.name,
                        str(parameter.type_ref),
                        False,
                        parameter.location,
                    )
                )
            self._check_block(function.body, new_scope=False)
        finally:
            self.current_function = previous
            self.scopes.pop()

    def _check_block(self, block: Block, *, new_scope: bool = True) -> None:
        if new_scope:
            self.scopes.append({})
        try:
            for statement in block.statements:
                self._check_statement(statement)
        finally:
            if new_scope:
                self.scopes.pop()

    def _check_statement(self, statement: object) -> None:
        if isinstance(statement, LetStatement):
            value_type = self._check_expression(statement.value)
            self._declare(
                Symbol(
                    statement.name,
                    value_type,
                    statement.is_mutable,
                    statement.location,
                )
            )
            self.variable_count += 1
            return

        if isinstance(statement, ReturnStatement):
            actual = (
                "Void"
                if statement.value is None
                else self._check_expression(statement.value)
            )
            expected = (
                str(self.current_function.return_type)
                if self.current_function and self.current_function.return_type
                else "Void"
            )
            if not self._is_assignable(actual, expected):
                raise SemanticError(
                    "KS1304",
                    f"Dönüş tipi uyuşmuyor: '{expected}' beklenirken '{actual}' döndürüldü.",
                    statement.location,
                )
            return

        if isinstance(statement, ExpressionStatement):
            self._check_expression(statement.expression)
            return

        if isinstance(statement, IfStatement):
            self._require_bool(
                self._check_expression(statement.condition),
                statement.condition.location,
                "if",
            )
            self._check_block(statement.then_branch)
            if statement.else_branch is not None:
                self._check_block(statement.else_branch)
            return

        if isinstance(statement, WhileStatement):
            self._require_bool(
                self._check_expression(statement.condition),
                statement.condition.location,
                "while",
            )
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

        if isinstance(expression, Identifier):
            if expression.name == "None":
                return "None"
            symbol = self._resolve(expression.name)
            if symbol is not None:
                return symbol.type_name
            if expression.name in self.functions:
                function = self.functions[expression.name]
                return str(function.return_type) if function.return_type else "Void"
            if expression.name in BUILTIN_CALLS:
                return None
            self._raise_unknown_identifier(expression)

        if isinstance(expression, UnaryExpression):
            operand_type = self._check_expression(expression.operand)
            if expression.operator == "-" and operand_type in NUMERIC_TYPES:
                return operand_type
            raise SemanticError(
                "KS1305",
                f"'{expression.operator}' işleci '{operand_type}' tipiyle kullanılamaz.",
                expression.location,
            )

        if isinstance(expression, BinaryExpression):
            left_type = self._check_expression(expression.left)
            right_type = self._check_expression(expression.right)
            return self._binary_type(
                expression.operator,
                left_type,
                right_type,
                expression.location,
            )

        if isinstance(expression, MemberExpression):
            object_type = self._check_expression(expression.object)
            if object_type == "SystemCaps" and expression.member in CAPABILITY_MEMBERS:
                capability_type = CAPABILITY_MEMBERS[expression.member]
                self.capability_count += 1
                return capability_type
            return object_type

        if isinstance(expression, CallExpression):
            argument_types = [
                self._check_expression(item) for item in expression.arguments
            ]

            if isinstance(expression.callee, Identifier):
                name = expression.callee.name
                if name in self.functions:
                    return self._check_function_call(
                        name, argument_types, expression.location
                    )
                if name in BUILTIN_CALLS:
                    return self._check_builtin_call(
                        name, argument_types, expression.location
                    )

            if isinstance(expression.callee, MemberExpression):
                receiver_type = self._check_expression(expression.callee.object)
                method_name = expression.callee.member
                self._check_capability_call(
                    expression.callee.object,
                    receiver_type,
                    method_name,
                    expression.location,
                )
                return self._member_call_type(receiver_type, method_name)

            return self._check_expression(expression.callee)

        if isinstance(expression, OrReturnExpression):
            value_type = self._check_expression(expression.value)
            if value_type is None:
                raise SemanticError(
                    "KS1401",
                    "'or return' yalnızca hata taşıyabilen bir değerle kullanılabilir.",
                    expression.location,
                )
            success_type, error_type = self._fallible_parts(value_type)
            if success_type is None:
                raise SemanticError(
                    "KS1401",
                    f"'{value_type}' tipi 'or return' ile açılamaz.",
                    expression.location,
                )
            propagated = (
                self._check_expression(expression.error)
                if expression.error is not None
                else error_type
            )
            expected = (
                str(self.current_function.return_type)
                if self.current_function and self.current_function.return_type
                else "Void"
            )
            if propagated and not self._is_error_compatible(propagated, expected):
                raise SemanticError(
                    "KS1402",
                    f"'{propagated}' hatası '{expected}' dönüş tipinden aktarılamaz.",
                    expression.location,
                )
            return success_type

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
                if symbol.type_name and not self._is_assignable(
                    value_type, symbol.type_name
                ):
                    raise SemanticError(
                        "KS1303",
                        f"'{symbol.name}' için '{symbol.type_name}' beklenirken '{value_type}' atandı.",
                        expression.location,
                    )
                return symbol.type_name or value_type
            self._check_expression(expression.target)
            return value_type

        raise AssertionError(f"Desteklenmeyen expression: {type(expression).__name__}")

    def _binary_type(
        self,
        operator: str,
        left: str | None,
        right: str | None,
        location: SourceLocation,
    ) -> str:
        if operator in {"+", "-", "*", "/"}:
            if left in NUMERIC_TYPES and right in NUMERIC_TYPES:
                if operator == "/" or "Float" in {left, right}:
                    return "Float"
                return "Int"
            raise SemanticError(
                "KS1305",
                f"'{operator}' işleci sayısal değerler bekliyor; '{left}' ve '{right}' verildi.",
                location,
            )

        if operator in {"<", "<=", ">", ">="}:
            if left in NUMERIC_TYPES and right in NUMERIC_TYPES:
                return "Bool"
            raise SemanticError(
                "KS1305",
                f"'{operator}' karşılaştırması sayısal değerler bekliyor.",
                location,
            )

        if operator in {"==", "!="}:
            if self._is_assignable(left, right or "Unknown") or self._is_assignable(
                right, left or "Unknown"
            ):
                return "Bool"
            raise SemanticError(
                "KS1305",
                f"'{left}' ile '{right}' karşılaştırılamaz.",
                location,
            )

        raise AssertionError(operator)

    @staticmethod
    def _require_bool(
        actual: str | None, location: SourceLocation, owner: str
    ) -> None:
        if actual != "Bool":
            raise SemanticError(
                "KS1305",
                f"'{owner}' koşulu Bool olmalıdır; '{actual}' bulundu.",
                location,
            )

    def _check_function_call(
        self,
        name: str,
        argument_types: list[str | None],
        location: SourceLocation,
    ) -> str:
        function = self.functions[name]
        if len(argument_types) != len(function.parameters):
            raise SemanticError(
                "KS1301",
                f"'{name}' {len(function.parameters)} argüman bekliyor; {len(argument_types)} verildi.",
                location,
            )
        for index, (actual, parameter) in enumerate(
            zip(argument_types, function.parameters, strict=True), start=1
        ):
            expected = str(parameter.type_ref)
            if not self._is_assignable(actual, expected):
                raise SemanticError(
                    "KS1302",
                    f"'{name}' çağrısında {index}. argüman '{expected}' olmalı; '{actual}' verildi.",
                    location,
                )
        return str(function.return_type) if function.return_type else "Void"

    def _check_builtin_call(
        self,
        name: str,
        argument_types: list[str | None],
        location: SourceLocation,
    ) -> str:
        if name in {"print", "println"}:
            self._require_arity(name, argument_types, 1, location)
            return "Void"
        if name == "Error":
            self._require_arity(name, argument_types, 1, location)
            if not self._is_assignable(argument_types[0], "String"):
                raise SemanticError(
                    "KS1302", "Error mesajı String olmalıdır.", location
                )
            return "Error"
        if name == "Some":
            self._require_arity(name, argument_types, 1, location)
            return f"Option<{argument_types[0] or 'Unknown'}>"
        if name == "Ok":
            self._require_arity(name, argument_types, 1, location)
            return f"Result<{argument_types[0] or 'Unknown'}, Unknown>"
        if name == "Err":
            self._require_arity(name, argument_types, 1, location)
            return f"Result<Unknown, {argument_types[0] or 'Unknown'}>"
        raise AssertionError(name)

    @staticmethod
    def _require_arity(
        name: str,
        arguments: list[str | None],
        expected: int,
        location: SourceLocation,
    ) -> None:
        if len(arguments) != expected:
            raise SemanticError(
                "KS1301",
                f"'{name}' {expected} argüman bekliyor; {len(arguments)} verildi.",
                location,
            )

    @staticmethod
    def _member_call_type(
        receiver_type: str | None, method_name: str
    ) -> str | None:
        if method_name == "allow" and receiver_type in CAPABILITY_METHODS:
            return receiver_type
        if receiver_type == "NetCaps" and method_name in {
            "get",
            "post",
            "put",
            "delete",
            "request",
        }:
            return "Result<String, Error>"
        if receiver_type == "DiskCaps" and method_name in {"read", "list"}:
            return "Result<String, Error>"
        if receiver_type == "DiskCaps" and method_name in {"write", "delete"}:
            return "Result<Void, Error>"
        if receiver_type == "EnvCaps" and method_name == "get":
            return "Option<String>"
        if receiver_type == "ProcessCaps" and method_name in {"run", "spawn"}:
            return "Result<Int, Error>"
        if receiver_type == "String" and method_name == "text":
            return "String"
        return None

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

    @classmethod
    def _is_assignable(cls, actual: str | None, expected: str) -> bool:
        if actual is None or actual == "Unknown" or expected == "Unknown":
            return True
        if actual == expected:
            return True
        if actual == "Int" and expected == "Float":
            return True

        union = cls._split_union(expected)
        if len(union) > 1:
            return any(cls._is_assignable(actual, item) for item in union)

        expected_generic = cls._generic_parts(expected)
        actual_generic = cls._generic_parts(actual)
        if expected_generic:
            base, expected_args = expected_generic
            if base == "Option" and actual == "None":
                return True
            if actual_generic and actual_generic[0] == base:
                actual_args = actual_generic[1]
                return len(actual_args) == len(expected_args) and all(
                    cls._is_assignable(a, e)
                    for a, e in zip(actual_args, expected_args, strict=True)
                )
        return False

    @classmethod
    def _is_error_compatible(cls, error_type: str, expected: str) -> bool:
        if cls._is_assignable(error_type, expected):
            return True
        generic = cls._generic_parts(expected)
        if generic and generic[0] == "Result" and len(generic[1]) == 2:
            return cls._is_assignable(error_type, generic[1][1])
        return False

    @classmethod
    def _fallible_parts(cls, type_name: str) -> tuple[str | None, str | None]:
        generic = cls._generic_parts(type_name)
        if generic and generic[0] == "Result" and len(generic[1]) == 2:
            return generic[1][0], generic[1][1]
        union = cls._split_union(type_name)
        if len(union) > 1 and "Error" in union:
            return next((item for item in union if item != "Error"), None), "Error"
        return None, None

    @staticmethod
    def _split_union(type_name: str) -> list[str]:
        parts: list[str] = []
        start = 0
        depth = 0
        index = 0
        while index < len(type_name):
            char = type_name[index]
            depth += char == "<"
            depth -= char == ">"
            if depth == 0 and type_name.startswith(" or ", index):
                parts.append(type_name[start:index])
                index += 4
                start = index
                continue
            index += 1
        parts.append(type_name[start:])
        return parts

    @staticmethod
    def _generic_parts(type_name: str) -> tuple[str, list[str]] | None:
        if "<" not in type_name or not type_name.endswith(">"):
            return None
        base, raw = type_name.split("<", 1)
        raw = raw[:-1]
        args: list[str] = []
        start = 0
        depth = 0
        for index, char in enumerate(raw):
            depth += char == "<"
            depth -= char == ">"
            if char == "," and depth == 0:
                args.append(raw[start:index].strip())
                start = index + 1
        args.append(raw[start:].strip())
        return base, args

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
