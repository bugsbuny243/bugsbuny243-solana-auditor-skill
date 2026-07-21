"""Koschei parser tarafından üretilen temel AST düğümleri."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class SourceLocation:
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class TypeRef:
    name: str
    location: SourceLocation
    arguments: tuple["TypeRef", ...] = field(default_factory=tuple)
    alternatives: tuple["TypeRef", ...] = field(default_factory=tuple)

    def __str__(self) -> str:
        if self.alternatives:
            return " or ".join(str(item) for item in self.alternatives)
        if self.arguments:
            rendered = ", ".join(str(item) for item in self.arguments)
            return f"{self.name}<{rendered}>"
        return self.name


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    type_ref: TypeRef
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Identifier:
    name: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Literal:
    value: object
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class UnaryExpression:
    operator: str
    operand: "Expression"
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class BinaryExpression:
    left: "Expression"
    operator: str
    right: "Expression"
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class MemberExpression:
    object: "Expression"
    member: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class CallExpression:
    callee: "Expression"
    arguments: tuple["Expression", ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class AssignmentExpression:
    target: "Expression"
    value: "Expression"
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class OrReturnExpression:
    value: "Expression"
    error: "Expression | None"
    location: SourceLocation


Expression: TypeAlias = (
    Identifier
    | Literal
    | UnaryExpression
    | BinaryExpression
    | MemberExpression
    | CallExpression
    | AssignmentExpression
    | OrReturnExpression
)


@dataclass(frozen=True, slots=True)
class LetStatement:
    name: str
    is_mutable: bool
    value: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class ReturnStatement:
    value: Expression | None
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class ExpressionStatement:
    expression: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Block:
    statements: tuple["Statement", ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class IfStatement:
    condition: Expression
    then_branch: Block
    else_branch: Block | None
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class WhileStatement:
    condition: Expression
    body: Block
    location: SourceLocation


Statement: TypeAlias = (
    LetStatement
    | ReturnStatement
    | ExpressionStatement
    | IfStatement
    | WhileStatement
)


@dataclass(frozen=True, slots=True)
class FunctionDeclaration:
    name: str
    parameters: tuple[Parameter, ...]
    return_type: TypeRef | None
    body: Block
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Program:
    declarations: tuple[FunctionDeclaration, ...]
