from pathlib import Path

FILES = {
    "interpreter.py": '''"""Koschei AST için tree-walking runtime yorumlayıcısı."""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
from semantic import check as semantic_check


@dataclass(frozen=True, slots=True)
class KsError:
    message: str

    def __str__(self) -> str:
        return self.message


class _KsUnit:
    __slots__ = ()

    def __repr__(self) -> str:
        return "KsUnit"

    def __str__(self) -> str:
        return "unit"


KsUnit = _KsUnit()


class KoscheiRuntimeError(Exception):
    def __init__(self, code: str, message: str, location: SourceLocation) -> None:
        self.code = code
        self.message = message
        self.location = location
        super().__init__(
            f"{code} [satır {location.line}, sütun {location.column}]: {message}"
        )


@dataclass(slots=True)
class _Cell:
    value: Any
    is_mutable: bool


class _Environment:
    def __init__(self) -> None:
        self.scopes: list[dict[str, _Cell]] = [{}]

    def push(self) -> None:
        self.scopes.append({})

    def pop(self) -> None:
        self.scopes.pop()

    def define(self, name: str, value: Any, is_mutable: bool) -> None:
        self.scopes[-1][name] = _Cell(value, is_mutable)

    def resolve(self, name: str, location: SourceLocation) -> _Cell:
        for scope in reversed(self.scopes):
            cell = scope.get(name)
            if cell is not None:
                return cell
        raise KoscheiRuntimeError(
            "KS3101", f"Tanımsız isim: '{name}'.", location
        )

    def assign(self, name: str, value: Any, location: SourceLocation) -> Any:
        cell = self.resolve(name, location)
        if not cell.is_mutable:
            raise KoscheiRuntimeError(
                "KS3201",
                f"'{name}' immutable bir değerdir; runtime ataması reddedildi.",
                location,
            )
        cell.value = value
        return value


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


@dataclass(frozen=True, slots=True)
class _BoundMember:
    receiver: Any
    name: str
    location: SourceLocation


@dataclass(frozen=True, slots=True)
class Response:
    body: str
    status_code: int

    def text(self) -> str:
        return self.body

    def status(self) -> int:
        return self.status_code


class SystemCaps:
    __slots__ = ("net", "disk", "env", "process")

    def __init__(self) -> None:
        self.net = NetRoot()
        self.disk = DiskRoot()
        self.env = EnvRoot()
        self.process = ProcessRoot()


class NetRoot:
    __slots__ = ()

    def allow(self, origin: str) -> "NetCaps":
        return NetCaps(origin)


class DiskRoot:
    __slots__ = ()

    def allow(self, prefix: str) -> "DiskCaps":
        return DiskCaps(prefix)

    def allow_read_only(self, prefix: str) -> "DiskReadCaps":
        return DiskReadCaps(prefix)


class EnvRoot:
    __slots__ = ()

    def allow(self, name: str) -> "EnvCaps":
        return EnvCaps(name)


class ProcessRoot:
    __slots__ = ()

    def allow(self, command: str) -> "ProcessCaps":
        return ProcessCaps(command)


class _NarrowedCapability:
    __slots__ = ()


class _DiskCapability(_NarrowedCapability):
    __slots__ = ("prefix",)

    def __init__(self, prefix: str) -> None:
        self.prefix = os.path.realpath(os.fspath(prefix))

    def _checked_path(self, path: str) -> str | KsError:
        target = os.path.realpath(os.fspath(path))
        try:
            inside = os.path.commonpath((self.prefix, target)) == self.prefix
        except ValueError:
            inside = False
        if not inside:
            return KsError(
                f"KS3402: Disk kapsamı dışında erişim reddedildi: {path}"
            )
        return target

    def read(self, path: str) -> str | KsError:
        return self.read_file(path)

    def read_file(self, path: str) -> str | KsError:
        checked = self._checked_path(path)
        if isinstance(checked, KsError):
            return checked
        try:
            return Path(checked).read_text(encoding="utf-8")
        except OSError as error:
            return KsError(f"Dosya okunamadı: {error}")

    def list(self, path: str) -> list[str] | KsError:
        checked = self._checked_path(path)
        if isinstance(checked, KsError):
            return checked
        try:
            return sorted(os.listdir(checked))
        except OSError as error:
            return KsError(f"Dizin listelenemedi: {error}")


class DiskReadCaps(_DiskCapability):
    __slots__ = ()

    @staticmethod
    def _denied(operation: str) -> KsError:
        return KsError(
            f"KS3404: DiskReadCaps '{operation}' işlemine izin vermez."
        )

    def write(self, path: str, value: str) -> KsError:
        checked = self._checked_path(path)
        return checked if isinstance(checked, KsError) else self._denied("write")

    def write_file(self, path: str, value: str) -> KsError:
        checked = self._checked_path(path)
        return checked if isinstance(checked, KsError) else self._denied("write_file")

    def delete(self, path: str) -> KsError:
        checked = self._checked_path(path)
        return checked if isinstance(checked, KsError) else self._denied("delete")


class DiskCaps(_DiskCapability):
    __slots__ = ()

    def write(self, path: str, value: str) -> _KsUnit | KsError:
        return self.write_file(path, value)

    def write_file(self, path: str, value: str) -> _KsUnit | KsError:
        checked = self._checked_path(path)
        if isinstance(checked, KsError):
            return checked
        try:
            Path(checked).write_text(str(value), encoding="utf-8")
        except OSError as error:
            return KsError(f"Dosya yazılamadı: {error}")
        return KsUnit

    def delete(self, path: str) -> _KsUnit | KsError:
        checked = self._checked_path(path)
        if isinstance(checked, KsError):
            return checked
        try:
            if os.path.isdir(checked):
                os.rmdir(checked)
            else:
                os.remove(checked)
        except OSError as error:
            return KsError(f"Dosya silinemedi: {error}")
        return KsUnit


class _ScopedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Yönlendirmeyi yalnızca aynı origin içinde izler.

    Kapsam dışı bir yönlendirme hedefi görülürse istek TAKİP EDİLMEZ ve
    _ScopedRedirectDenied yükseltilir; NetCaps.get bunu KS3402 hata DEĞERİNE
    çevirir. Böylece izinli sunucu 302 ile başka bir host'a yönlendirse bile
    yetki sınırı aşılamaz.
    """

    max_redirections = 5

    def __init__(self, origin_key: tuple[str, str, int | None] | None) -> None:
        self.origin_key = origin_key

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if self.origin_key is None or _origin_key(newurl) != self.origin_key:
            raise _ScopedRedirectDenied(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class _ScopedRedirectDenied(Exception):
    def __init__(self, target: str) -> None:
        self.target = target
        super().__init__(target)


class NetCaps(_NarrowedCapability):
    __slots__ = ("origin", "origin_key", "_opener")

    def __init__(self, origin: str) -> None:
        self.origin = origin
        self.origin_key = _origin_key(origin)
        self._opener = urllib.request.build_opener(
            _ScopedRedirectHandler(self.origin_key)
        )

    def _allows(self, url: str) -> bool:
        return self.origin_key is not None and _origin_key(url) == self.origin_key

    def get(self, url: str) -> Response | KsError:
        if not self._allows(url):
            return KsError(
                f"KS3402: Ağ origin kapsamı dışında erişim reddedildi: {url}"
            )
        try:
            request = urllib.request.Request(url, method="GET")
            with self._opener.open(request, timeout=10) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset, errors="replace")
                return Response(body, int(response.status))
        except _ScopedRedirectDenied as denied:
            return KsError(
                f"KS3402: Ağ yönlendirmesi kapsam dışına çıktı: {denied.target}"
            )
        except (OSError, urllib.error.URLError) as error:
            if isinstance(getattr(error, "reason", None), _ScopedRedirectDenied):
                return KsError(
                    "KS3402: Ağ yönlendirmesi kapsam dışına çıktı: "
                    f"{error.reason.target}"
                )
            return KsError(f"API isteği başarısız: {error}")

    @staticmethod
    def post(*arguments: Any) -> KsError:
        return KsError("post henüz desteklenmiyor")

    @staticmethod
    def put(*arguments: Any) -> KsError:
        return KsError("put henüz desteklenmiyor")

    @staticmethod
    def delete(*arguments: Any) -> KsError:
        return KsError("delete henüz desteklenmiyor")

    @staticmethod
    def request(*arguments: Any) -> KsError:
        return KsError("request henüz desteklenmiyor")


class EnvCaps(_NarrowedCapability):
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def get(self) -> str | KsError:
        value = os.environ.get(self.name)
        if value is None:
            return KsError(f"Ortam değişkeni bulunamadı: {self.name}")
        return value


class ProcessCaps(_NarrowedCapability):
    __slots__ = ("command",)

    def __init__(self, command: str) -> None:
        self.command = command

    @staticmethod
    def run(*arguments: Any) -> KsError:
        return KsError("process yetkisi v0.1'de kapalı")

    @staticmethod
    def spawn(*arguments: Any) -> KsError:
        return KsError("process yetkisi v0.1'de kapalı")


def _origin_key(url: str) -> tuple[str, str, int | None] | None:
    try:
        parsed = urlsplit(url)
        if not parsed.scheme or not parsed.hostname:
            return None
        scheme = parsed.scheme.lower()
        host = parsed.hostname.lower()
        port = parsed.port
        if port is None:
            port = 443 if scheme == "https" else 80 if scheme == "http" else None
        return scheme, host, port
    except ValueError:
        return None


class Interpreter:
    def __init__(self, program: Program, argv: list[str] | None = None) -> None:
        self.program = program
        self.argv = list(argv or [])
        self.functions = {
            declaration.name: declaration for declaration in program.declarations
        }
        self.environment = _Environment()
        self._depth = 0

    MAX_CALL_DEPTH = 512

    # Her Koschei çağrısı birden fazla Python çerçevesi kullanır; KS3105'in
    # Python'un kendi RecursionError'ından ÖNCE devreye girmesi için yorumlayıcı
    # çalışırken Python limiti yükseltilir.
    _PYTHON_RECURSION_HEADROOM = 20000

    def execute_main(self) -> Any:
        previous_limit = sys.getrecursionlimit()
        if previous_limit < self._PYTHON_RECURSION_HEADROOM:
            sys.setrecursionlimit(self._PYTHON_RECURSION_HEADROOM)
        try:
            return self._execute_main()
        except RecursionError as error:  # güvenlik ağı: KS koduna çevrilir
            raise KoscheiRuntimeError(
                "KS3105",
                f"Çağrı derinliği sınırı aşıldı ({self.MAX_CALL_DEPTH}); "
                "sonsuz özyineleme olabilir.",
                SourceLocation(1, 1),
            ) from error
        finally:
            sys.setrecursionlimit(previous_limit)

    def _execute_main(self) -> Any:
        main = self.functions.get("main")
        if main is None:
            raise KoscheiRuntimeError(
                "KS3101", "'main' fonksiyonu bulunamadı.", SourceLocation(1, 1)
            )
        if len(main.parameters) == 0:
            arguments: list[Any] = []
        elif len(main.parameters) == 1:
            arguments = [SystemCaps()]
        else:
            raise KoscheiRuntimeError(
                "KS3101",
                "'main' fonksiyonu sıfır veya bir parametre almalıdır.",
                main.location,
            )
        return self._call_function(main, arguments)

    def _call_function(
        self, function: FunctionDeclaration, arguments: list[Any]
    ) -> Any:
        if len(arguments) != len(function.parameters):
            raise KoscheiRuntimeError(
                "KS3101",
                f"'{function.name}' için {len(function.parameters)} argüman bekleniyor, "
                f"{len(arguments)} verildi.",
                function.location,
            )
        if self._depth >= self.MAX_CALL_DEPTH:
            raise KoscheiRuntimeError(
                "KS3105",
                f"Çağrı derinliği sınırı aşıldı ({self.MAX_CALL_DEPTH}); "
                "sonsuz özyineleme olabilir.",
                function.location,
            )
        previous = self.environment
        self.environment = _Environment()
        self._depth += 1
        try:
            for parameter, value in zip(function.parameters, arguments):
                self.environment.define(parameter.name, value, False)
            try:
                return self._execute_block(function.body, create_scope=False)
            except _ReturnSignal as signal:
                return signal.value
        finally:
            self._depth -= 1
            self.environment = previous

    def _execute_block(self, block: Block, *, create_scope: bool = True) -> Any:
        if create_scope:
            self.environment.push()
        try:
            result: Any = KsUnit
            for statement in block.statements:
                result = self._execute_statement(statement)
            return result
        finally:
            if create_scope:
                self.environment.pop()

    def _execute_statement(self, statement: Statement) -> Any:
        if isinstance(statement, LetStatement):
            value = self._evaluate(statement.value)
            self.environment.define(statement.name, value, statement.is_mutable)
            return KsUnit

        if isinstance(statement, ReturnStatement):
            value = KsUnit if statement.value is None else self._evaluate(statement.value)
            raise _ReturnSignal(value)

        if isinstance(statement, ExpressionStatement):
            return self._evaluate(statement.expression)

        if isinstance(statement, IfStatement):
            condition = self._evaluate(statement.condition)
            if isinstance(condition, KsError):
                return condition
            if bool(condition):
                return self._execute_block(statement.then_block)
            if isinstance(statement.else_branch, Block):
                return self._execute_block(statement.else_branch)
            if isinstance(statement.else_branch, IfStatement):
                return self._execute_statement(statement.else_branch)
            return KsUnit

        if isinstance(statement, WhileStatement):
            result: Any = KsUnit
            while True:
                condition = self._evaluate(statement.condition)
                if isinstance(condition, KsError):
                    return condition
                if not bool(condition):
                    return result
                result = self._execute_block(statement.body)
                if isinstance(result, KsError):
                    return result

        raise AssertionError(f"Desteklenmeyen statement: {type(statement).__name__}")

    def _evaluate(self, expression: Expression) -> Any:
        if isinstance(expression, Literal):
            return expression.value

        if isinstance(expression, Identifier):
            if expression.name in self.functions:
                return self.functions[expression.name]
            if expression.name in {"print", "println", "Error"}:
                return expression.name
            return self.environment.resolve(expression.name, expression.location).value

        if isinstance(expression, InterpolatedString):
            return "".join(str(self._evaluate(part)) for part in expression.parts)

        if isinstance(expression, MemberExpression):
            receiver = self._evaluate(expression.object)
            return self._member(receiver, expression.member, expression.location)

        if isinstance(expression, CallExpression):
            callee = self._evaluate(expression.callee)
            arguments = [self._evaluate(item) for item in expression.arguments]
            return self._invoke(callee, arguments, expression.location)

        if isinstance(expression, AssignmentExpression):
            value = self._evaluate(expression.value)
            if isinstance(expression.target, Identifier):
                return self.environment.assign(
                    expression.target.name, value, expression.location
                )
            raise KoscheiRuntimeError(
                "KS3201", "Yalnızca değişkenlere atama yapılabilir.", expression.location
            )

        if isinstance(expression, BinaryExpression):
            return self._binary(expression)

        if isinstance(expression, UnaryExpression):
            operand = self._evaluate(expression.operand)
            if isinstance(operand, KsError):
                return operand
            if expression.operator == "!":
                return not bool(operand)
            if expression.operator == "-":
                return -operand
            raise AssertionError(expression.operator)

        if isinstance(expression, OrReturnExpression):
            value = self._evaluate(expression.value)
            if isinstance(value, KsError):
                replacement = (
                    value
                    if expression.error is None
                    else self._evaluate(expression.error)
                )
                raise _ReturnSignal(replacement)
            return value

        if isinstance(expression, OrElseExpression):
            value = self._evaluate(expression.value)
            return self._evaluate(expression.fallback) if isinstance(value, KsError) else value

        if isinstance(expression, OrBlockExpression):
            value = self._evaluate(expression.value)
            return self._execute_block(expression.handler) if isinstance(value, KsError) else value

        raise AssertionError(f"Desteklenmeyen expression: {type(expression).__name__}")

    def _binary(self, expression: BinaryExpression) -> Any:
        left = self._evaluate(expression.left)
        if isinstance(left, KsError):
            return left
        if expression.operator == "&&":
            if not bool(left):
                return False
            right = self._evaluate(expression.right)
            return right if isinstance(right, KsError) else bool(right)
        if expression.operator == "||":
            if bool(left):
                return True
            right = self._evaluate(expression.right)
            return right if isinstance(right, KsError) else bool(right)

        right = self._evaluate(expression.right)
        if isinstance(right, KsError):
            return right
        operator = expression.operator
        if operator == "+":
            return left + right
        if operator == "-":
            return left - right
        if operator == "*":
            return left * right
        if operator == "/":
            if right == 0:
                return KsError("Sıfıra bölme")
            return left / right
        if operator == "==":
            return left == right
        if operator == "!=":
            return left != right
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        raise AssertionError(operator)

    def _member(self, receiver: Any, name: str, location: SourceLocation) -> Any:
        if isinstance(receiver, SystemCaps):
            if name in {"net", "disk", "env", "process"}:
                return getattr(receiver, name)

        if isinstance(receiver, _NarrowedCapability) and name in {
            "allow", "allow_read_only"
        }:
            raise KoscheiRuntimeError(
                "KS3403",
                f"Daraltılmış yetki '{name}' ile yeniden genişletilemez.",
                location,
            )

        allowed_members: dict[type[Any], set[str]] = {
            NetRoot: {"allow"},
            DiskRoot: {"allow", "allow_read_only"},
            EnvRoot: {"allow"},
            ProcessRoot: {"allow"},
            NetCaps: {"get", "post", "put", "delete", "request"},
            DiskCaps: {"read", "read_file", "write", "write_file", "list", "delete"},
            DiskReadCaps: {"read", "read_file", "write", "write_file", "list", "delete"},
            EnvCaps: {"get"},
            ProcessCaps: {"run", "spawn"},
            Response: {"text", "status"},
            str: {"length", "to_int", "to_float", "contains"},
        }
        for receiver_type, members in allowed_members.items():
            if isinstance(receiver, receiver_type) and name in members:
                return _BoundMember(receiver, name, location)

        raise KoscheiRuntimeError(
            "KS3101", f"Tanımsız alan veya metot: '{name}'.", location
        )

    def _invoke(
        self, callee: Any, arguments: list[Any], location: SourceLocation
    ) -> Any:
        if isinstance(callee, FunctionDeclaration):
            return self._call_function(callee, arguments)
        if callee == "println":
            self._require_arity("println", arguments, 1, location)
            print(arguments[0])
            return KsUnit
        if callee == "print":
            self._require_arity("print", arguments, 1, location)
            print(arguments[0], end="")
            return KsUnit
        if callee == "Error":
            self._require_arity("Error", arguments, 1, location)
            return KsError(str(arguments[0]))
        if isinstance(callee, _BoundMember):
            return self._invoke_member(callee, arguments)
        raise KoscheiRuntimeError(
            "KS3101", "Çağrılabilir bir değer bekleniyordu.", location
        )

    def _invoke_member(self, member: _BoundMember, arguments: list[Any]) -> Any:
        receiver = member.receiver
        name = member.name
        if isinstance(receiver, str):
            if name == "length":
                self._require_arity(name, arguments, 0, member.location)
                return len(receiver)
            if name == "to_int":
                self._require_arity(name, arguments, 0, member.location)
                try:
                    return int(receiver.strip())
                except ValueError:
                    return KsError(f"Int dönüşümü başarısız: {receiver}")
            if name == "to_float":
                self._require_arity(name, arguments, 0, member.location)
                try:
                    return float(receiver.strip())
                except ValueError:
                    return KsError(f"Float dönüşümü başarısız: {receiver}")
            if name == "contains":
                self._require_arity(name, arguments, 1, member.location)
                return str(arguments[0]) in receiver

        method = getattr(receiver, name)
        try:
            return method(*arguments)
        except TypeError as error:
            raise KoscheiRuntimeError(
                "KS3101", f"'{name}' çağrısı geçersiz: {error}", member.location
            ) from error

    @staticmethod
    def _require_arity(
        name: str, arguments: list[Any], expected: int, location: SourceLocation
    ) -> None:
        if len(arguments) != expected:
            raise KoscheiRuntimeError(
                "KS3101",
                f"'{name}' için {expected} argüman bekleniyor, {len(arguments)} verildi.",
                location,
            )


def run(program: Program, argv: list[str]) -> int:
    semantic_check(program)
    result = Interpreter(program, argv).execute_main()
    if isinstance(result, KsError):
        print(f"KOSCHEI RUNTIME ERROR: {result.message}", file=sys.stderr)
        return 1
    return 0
''',
    "semantic.py": '''"""Koschei AST için semantic ve capability güvenlik denetleyicisi.

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
''',
}

for path, content in FILES.items():
    Path(path).write_text(content, encoding="utf-8")
