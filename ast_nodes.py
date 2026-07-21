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
    names: tuple[str, ...]
    location: SourceLocation

    def __str__(self) -> str:
        return " or ".join(self.names)


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
class MemberExpression:
    object: Expression
    member: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class CallExpression:
    callee: Expression
    arguments: tuple[Expression, ...]
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class AssignmentExpression:
    target: Expression
    value: Expression
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class OrReturnExpression:
    value: Expression
    error: Expression | None
    location: SourceLocation


Expression: TypeAlias = (
    Identifier
    | Literal
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


Statement: TypeAlias = LetStatement | ReturnStatement | ExpressionStatement


@dataclass(frozen=True, slots=True)
class Block:
    statements: tuple[Statement, ...] = field(default_factory=tuple)


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
