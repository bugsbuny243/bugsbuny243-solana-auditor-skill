from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new), encoding="utf-8")


def replace_region(path: str, start: str, end: str, replacement: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    start_index = text.find(start)
    if start_index < 0:
        raise SystemExit(f"{path}: start marker not found: {start!r}")
    end_index = text.find(end, start_index + len(start))
    if end_index < 0:
        raise SystemExit(f"{path}: end marker not found: {end!r}")
    target.write_text(
        text[:start_index] + replacement + text[end_index:],
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Semantic type-integrity wall
# ---------------------------------------------------------------------------

replace_once(
    "koschei/semantic.py",
    'CAPABILITY_TYPES = set(ROOT_METHODS) | set(NARROWED_METHODS) | {"SystemCaps"}\n',
    'CAPABILITY_TYPES = set(ROOT_METHODS) | set(NARROWED_METHODS) | {"SystemCaps"}\n'
    'ROOT_CAPABILITY_TYPES = set(ROOT_METHODS) | {"SystemCaps"}\n',
)

replace_once(
    "koschei/semantic.py",
    "        self.capability_count = 0\n",
    "        self.capability_count = 0\n"
    "        self.current_function: FunctionDeclaration | None = None\n",
)

replace_region(
    "koschei/semantic.py",
    "    def check(self) -> SemanticReport:\n",
    "    def _check_function(self, function: FunctionDeclaration) -> None:\n",
    '''    def check(self) -> SemanticReport:
        for declaration in self.program.structs:
            seen: set[str] = set()
            for field in declaration.fields:
                if field.name in seen:
                    raise SemanticError(
                        "KS1501",
                        f"'{declaration.name}' struct'ında '{field.name}' alanı "
                        "birden fazla tanımlanmış.",
                        field.location,
                    )
                seen.add(field.name)

                roots = set(field.type_ref.names) & ROOT_CAPABILITY_TYPES
                if roots:
                    raise SemanticError(
                        "KS2402",
                        f"'{declaration.name}.{field.name}' alanı kök capability "
                        f"taşıyamaz ({', '.join(sorted(roots))}). Kök yetki yalnızca "
                        "main içindeki SystemCaps'ten daraltılmalı; struct'a yalnızca "
                        "NetCaps / DiskCaps gibi daraltılmış jetonlar konabilir.",
                        field.location,
                    )

        for declaration in self.program.declarations:
            self._validate_function_signature(declaration)

        for declaration in self.program.declarations:
            self._check_function(declaration)

        return SemanticReport(
            functions=len(self.program.declarations),
            variables=self.variable_count,
            capability_values=self.capability_count,
        )

    def _validate_function_signature(self, function: FunctionDeclaration) -> None:
        if function.name == "main":
            if len(function.parameters) > 1:
                raise SemanticError(
                    "KS1301",
                    "'main' sıfır parametre veya yalnızca bir SystemCaps parametresi "
                    "alabilir.",
                    function.location,
                )
            if (
                len(function.parameters) == 1
                and function.parameters[0].type_ref.names != ("SystemCaps",)
            ):
                parameter = function.parameters[0]
                raise SemanticError(
                    "KS2401",
                    "'main' tek parametre alıyorsa bu parametre tam olarak SystemCaps "
                    f"olmalıdır; {parameter.type_ref} bulundu. Runtime başka bir tipe "
                    "SystemCaps enjekte etmez.",
                    parameter.location,
                )

        for parameter in function.parameters:
            if (
                function.name == "main"
                and parameter.type_ref.names == ("SystemCaps",)
            ):
                continue
            roots = set(parameter.type_ref.names) & ROOT_CAPABILITY_TYPES
            if roots:
                raise SemanticError(
                    "KS2402",
                    f"'{function.name}' fonksiyonunun '{parameter.name}' parametresi "
                    f"kök capability taşıyamaz ({', '.join(sorted(roots))}). Kökü "
                    "main içinde daraltın ve yalnızca daraltılmış jetonu geçirin.",
                    parameter.location,
                )

        if function.return_type is not None:
            roots = set(function.return_type.names) & ROOT_CAPABILITY_TYPES
            if roots:
                raise SemanticError(
                    "KS2402",
                    f"'{function.name}' kök capability döndüremez "
                    f"({', '.join(sorted(roots))}). Kök yetkiler dolaşıma çıkamaz.",
                    function.return_type.location,
                )

''',
)

replace_region(
    "koschei/semantic.py",
    "    def _check_function(self, function: FunctionDeclaration) -> None:\n",
    "    def _check_block(self, block: Block) -> None:\n",
    '''    def _check_function(self, function: FunctionDeclaration) -> None:
        self.scopes.append({})
        previous_function = self.current_function
        self.current_function = function
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
            self.current_function = previous_function
            self.scopes.pop()

''',
)

replace_once(
    "koschei/semantic.py",
    '''        if isinstance(statement, ReturnStatement):
            if statement.value is not None:
                self._check_expression(statement.value)
            return
''',
    '''        if isinstance(statement, ReturnStatement):
            value_type = (
                "Void"
                if statement.value is None
                else self._check_expression(statement.value)
            )
            function = self.current_function
            if function is not None and function.return_type is not None:
                self._require_assignable(
                    function.return_type.names,
                    value_type,
                    f"'{function.name}' dönüş değeri",
                    statement.location,
                )
            return
''',
)

replace_region(
    "koschei/semantic.py",
    "    def _check_struct_literal(self, expression: StructLiteral) -> str:\n",
    "    def _check_binary(self, expression: BinaryExpression) -> str | None:\n",
    '''    def _check_struct_literal(self, expression: StructLiteral) -> str:
        declaration = self.structs.get(expression.type_name)
        if declaration is None:
            raise SemanticError(
                "KS1101",
                f"Tanımsız struct: '{expression.type_name}'.",
                expression.location,
            )

        expected = {field.name: field for field in declaration.fields}
        provided: set[str] = set()

        for name, value in expression.fields:
            if name not in expected:
                raise SemanticError(
                    "KS1501",
                    f"'{expression.type_name}' struct'ında '{name}' adında bir alan "
                    f"yok. Beklenen alanlar: {', '.join(sorted(expected))}.",
                    expression.location,
                )
            if name in provided:
                raise SemanticError(
                    "KS1501",
                    f"'{name}' alanı birden fazla kez verilmiş.",
                    expression.location,
                )

            value_type = self._check_expression(value)
            field = expected[name]
            self._require_assignable(
                field.type_ref.names,
                value_type,
                f"'{expression.type_name}.{name}' alanı",
                value.location,
            )
            provided.add(name)

        missing = set(expected) - provided
        if missing:
            raise SemanticError(
                "KS1501",
                f"'{expression.type_name}' struct'ında eksik alan(lar): "
                f"{', '.join(sorted(missing))}.",
                expression.location,
            )

        return expression.type_name

''',
)

replace_region(
    "koschei/semantic.py",
    "    def _check_call_arguments(\n",
    "    def _check_method_call(\n",
    '''    def _type_names(self, type_name: str | None) -> set[str]:
        if type_name is None:
            return set()
        return {
            part.strip()
            for part in type_name.split(" or ")
            if part.strip()
        }

    def _name_is_sensitive(
        self,
        name: str,
        seen: set[str] | None = None,
    ) -> bool:
        if name in CAPABILITY_TYPES:
            return True
        declaration = self.structs.get(name)
        if declaration is None:
            return False
        visited = set(seen or ())
        if name in visited:
            return False
        visited.add(name)
        return any(
            self._name_is_sensitive(type_name, visited)
            for field in declaration.fields
            for type_name in field.type_ref.names
        )

    def _types_are_sensitive(self, names: set[str]) -> bool:
        return any(self._name_is_sensitive(name) for name in names)

    def _require_assignable(
        self,
        expected_names,
        actual_type: str | None,
        subject: str,
        location: SourceLocation,
    ) -> None:
        expected = set(expected_names)
        actual = self._type_names(actual_type)
        expected_sensitive = self._types_are_sensitive(expected)
        actual_sensitive = self._types_are_sensitive(actual)

        if not actual:
            if expected_sensitive:
                raise SemanticError(
                    "KS2401",
                    f"{subject} capability taşıyan {', '.join(sorted(expected))} "
                    "tipini bekliyor; verilen değerin tipi güvenli biçimde "
                    "kanıtlanamadı. Capability type-laundering reddedildi.",
                    location,
                )
            return

        if actual.issubset(expected):
            return

        code = "KS2401" if expected_sensitive or actual_sensitive else "KS1301"
        expected_text = " or ".join(sorted(expected)) or "<bilinmiyor>"
        actual_text = " or ".join(sorted(actual))
        detail = (
            " Capability değerleri başka bir tip gibi gösterilemez."
            if code == "KS2401"
            else ""
        )
        raise SemanticError(
            code,
            f"{subject} {expected_text} bekler, {actual_text} bulundu.{detail}",
            location,
        )

    def _check_call_arguments(
        self,
        function: FunctionDeclaration,
        argument_types: list[str | None],
        location: SourceLocation,
    ) -> None:
        parameters = function.parameters
        if len(argument_types) != len(parameters):
            missing = parameters[len(argument_types):]
            missing_sensitive = [
                parameter
                for parameter in missing
                if any(
                    self._name_is_sensitive(type_name)
                    for type_name in parameter.type_ref.names
                )
            ]
            if missing_sensitive:
                required = ", ".join(
                    f"{parameter.name}: {parameter.type_ref}"
                    for parameter in missing_sensitive
                )
                raise SemanticError(
                    "KS2401",
                    f"'{function.name}' çağrısı gerekli capability taşıyan "
                    f"değeri almadı: {required}.",
                    location,
                )
            raise SemanticError(
                "KS1301",
                f"'{function.name}' çağrısı {len(parameters)} argüman bekler, "
                f"{len(argument_types)} verildi.",
                location,
            )

        for index, (parameter, actual_type) in enumerate(
            zip(parameters, argument_types),
            start=1,
        ):
            self._require_assignable(
                parameter.type_ref.names,
                actual_type,
                f"'{function.name}' çağrısının {index}. argümanı",
                location,
            )

''',
)

# ---------------------------------------------------------------------------
# Runtime defence-in-depth
# ---------------------------------------------------------------------------

replace_once(
    "koschei/interpreter.py",
    '''        self.functions = {
            declaration.name: declaration for declaration in program.declarations
        }
''',
    '''        self.functions = {
            declaration.name: declaration for declaration in program.declarations
        }
        self.structs = {
            declaration.name: declaration for declaration in program.structs
        }
''',
)

replace_region(
    "koschei/interpreter.py",
    "    def _execute_main(self) -> Any:\n",
    "    def _call_function(\n",
    '''    def _execute_main(self) -> Any:
        main = self.functions.get("main")
        if main is None:
            raise KoscheiRuntimeError(
                "KS3101", "'main' fonksiyonu bulunamadı.", SourceLocation(1, 1)
            )
        if len(main.parameters) == 0:
            arguments: list[Any] = []
        elif (
            len(main.parameters) == 1
            and main.parameters[0].type_ref.names == ("SystemCaps",)
        ):
            arguments = [SystemCaps()]
        else:
            raise KoscheiRuntimeError(
                "KS3401",
                "'main' sıfır parametre veya yalnızca bir SystemCaps parametresi "
                "almalıdır; runtime başka bir tipe kök yetki enjekte etmez.",
                main.location,
            )
        return self._call_function(main, arguments)

''',
)

replace_region(
    "koschei/interpreter.py",
    "    def _call_function(\n",
    "    def _execute_block(self, block: Block, *, create_scope: bool = True) -> Any:\n",
    '''    def _call_function(
        self,
        function: FunctionDeclaration,
        arguments: list[Any],
        namespace: dict[str, FunctionDeclaration] | None = None,
    ) -> Any:
        if len(arguments) != len(function.parameters):
            raise KoscheiRuntimeError(
                "KS3101",
                f"'{function.name}' için {len(function.parameters)} argüman bekleniyor, "
                f"{len(arguments)} verildi.",
                function.location,
            )

        for parameter, value in zip(function.parameters, arguments):
            if not self._runtime_matches_type(value, parameter.type_ref.names):
                raise KoscheiRuntimeError(
                    "KS3401",
                    f"'{function.name}' çağrısında '{parameter.name}: "
                    f"{parameter.type_ref}' sözleşmesi ihlal edildi; "
                    f"{self._runtime_type_name(value)} verildi. Runtime capability "
                    "type-laundering girişimini reddetti.",
                    parameter.location,
                )

        if self._depth >= self.MAX_CALL_DEPTH:
            raise KoscheiRuntimeError(
                "KS3105",
                f"Çağrı derinliği sınırı aşıldı ({self.MAX_CALL_DEPTH}); "
                "sonsuz özyineleme olabilir.",
                function.location,
            )
        previous = self.environment
        previous_functions = self.functions
        self.environment = _Environment()
        if namespace is not None:
            self.functions = namespace
        self._depth += 1
        try:
            for parameter, value in zip(function.parameters, arguments):
                self.environment.define(parameter.name, value, False)
            try:
                result = self._execute_block(function.body, create_scope=False)
            except _ReturnSignal as signal:
                result = signal.value

            if (
                function.return_type is not None
                and not self._runtime_matches_type(
                    result,
                    function.return_type.names,
                )
            ):
                raise KoscheiRuntimeError(
                    "KS3401",
                    f"'{function.name}' dönüş sözleşmesi {function.return_type} "
                    f"beklerken {self._runtime_type_name(result)} döndürdü.",
                    function.location,
                )
            return result
        finally:
            self._depth -= 1
            self.environment = previous
            self.functions = previous_functions

''',
)

replace_once(
    "koschei/interpreter.py",
    '''        if isinstance(expression, StructLiteral):
            fields: dict[str, Any] = {}
            for name, value_expression in expression.fields:
                value = self._evaluate(value_expression)
                if isinstance(value, KsError):
                    return value
                fields[name] = value
            return StructValue(expression.type_name, fields)
''',
    '''        if isinstance(expression, StructLiteral):
            fields: dict[str, Any] = {}
            declaration = self.structs.get(expression.type_name)
            expected = (
                {field.name: field for field in declaration.fields}
                if declaration is not None
                else {}
            )
            for name, value_expression in expression.fields:
                value = self._evaluate(value_expression)
                if isinstance(value, KsError):
                    return value
                field = expected.get(name)
                if (
                    field is not None
                    and not self._runtime_matches_type(value, field.type_ref.names)
                ):
                    raise KoscheiRuntimeError(
                        "KS3401",
                        f"'{expression.type_name}.{name}' alanı "
                        f"{field.type_ref} beklerken "
                        f"{self._runtime_type_name(value)} aldı.",
                        value_expression.location,
                    )
                fields[name] = value
            return StructValue(expression.type_name, fields)
''',
)

replace_once(
    "koschei/interpreter.py",
    '''    @staticmethod
    def _require_arity(
''',
    '''    def _runtime_matches_type(
        self,
        value: Any,
        expected_names,
    ) -> bool:
        for name in expected_names:
            if name == "SystemCaps" and isinstance(value, SystemCaps):
                return True
            if name == "NetRoot" and isinstance(value, NetRoot):
                return True
            if name == "DiskRoot" and isinstance(value, DiskRoot):
                return True
            if name == "EnvRoot" and isinstance(value, EnvRoot):
                return True
            if name == "ProcessRoot" and isinstance(value, ProcessRoot):
                return True
            if name == "NetCaps" and isinstance(value, NetCaps):
                return True
            if name == "DiskCaps" and isinstance(value, DiskCaps):
                return True
            if name == "DiskReadCaps" and isinstance(value, DiskReadCaps):
                return True
            if name == "EnvCaps" and isinstance(value, EnvCaps):
                return True
            if name == "ProcessCaps" and isinstance(value, ProcessCaps):
                return True
            if name == "Response" and isinstance(value, Response):
                return True
            if name == "Error" and isinstance(value, KsError):
                return True
            if name == "Void" and value is KsUnit:
                return True
            if name == "String" and isinstance(value, str):
                return True
            if name == "Bool" and isinstance(value, bool):
                return True
            if name == "Int" and isinstance(value, int) and not isinstance(value, bool):
                return True
            if name == "Float" and isinstance(value, float):
                return True
            if name == "List" and isinstance(value, list):
                return True
            if isinstance(value, StructValue) and value.type_name == name:
                return True
        return False

    @staticmethod
    def _runtime_type_name(value: Any) -> str:
        if value is KsUnit:
            return "Void"
        if isinstance(value, StructValue):
            return value.type_name
        if isinstance(value, KsError):
            return "Error"
        mapping = (
            (SystemCaps, "SystemCaps"),
            (NetRoot, "NetRoot"),
            (DiskRoot, "DiskRoot"),
            (EnvRoot, "EnvRoot"),
            (ProcessRoot, "ProcessRoot"),
            (NetCaps, "NetCaps"),
            (DiskCaps, "DiskCaps"),
            (DiskReadCaps, "DiskReadCaps"),
            (EnvCaps, "EnvCaps"),
            (ProcessCaps, "ProcessCaps"),
            (Response, "Response"),
            (bool, "Bool"),
            (str, "String"),
            (float, "Float"),
            (int, "Int"),
            (list, "List"),
        )
        for runtime_type, name in mapping:
            if isinstance(value, runtime_type):
                return name
        return type(value).__name__

    @staticmethod
    def _require_arity(
''',
)

# ---------------------------------------------------------------------------
# Honest manifests for capability-bearing aggregate types
# ---------------------------------------------------------------------------

replace_once(
    "koschei/capabilities.py",
    '''TYPE_DOMAINS = {
    "NetCaps": "net",
    "DiskCaps": "disk",
    "DiskReadCaps": "disk",
    "EnvCaps": "env",
    "ProcessCaps": "process",
}


def analyze(program: Program) -> Manifest:
    manifest = Manifest()
''',
    '''TYPE_DOMAINS = {
    "NetRoot": "net",
    "DiskRoot": "disk",
    "EnvRoot": "env",
    "ProcessRoot": "process",
    "NetCaps": "net",
    "DiskCaps": "disk",
    "DiskReadCaps": "disk",
    "EnvCaps": "env",
    "ProcessCaps": "process",
}


def _type_name_domains(
    type_name: str,
    structs: dict,
    seen: set[str] | None = None,
) -> set[str]:
    direct = TYPE_DOMAINS.get(type_name)
    if direct is not None:
        return {direct}
    declaration = structs.get(type_name)
    if declaration is None:
        return set()
    visited = set(seen or ())
    if type_name in visited:
        return set()
    visited.add(type_name)
    domains: set[str] = set()
    for field in declaration.fields:
        for field_type in field.type_ref.names:
            domains.update(_type_name_domains(field_type, structs, visited))
    return domains


def _type_ref_domains(type_ref, structs: dict) -> set[str]:
    domains: set[str] = set()
    for type_name in type_ref.names:
        domains.update(_type_name_domains(type_name, structs))
    return domains


def analyze(program: Program, imported_structs: dict | None = None) -> Manifest:
    manifest = Manifest()
    structs = {
        declaration.name: declaration for declaration in program.structs
    }
    structs.update(imported_structs or {})
''',
)

replace_once(
    "koschei/capabilities.py",
    '''    for declaration in program.declarations:
        capability_parameters = [
            parameter.name
            for parameter in declaration.parameters
            if any(name in NARROWED_METHODS for name in parameter.type_ref.names)
        ]
        if capability_parameters:
            manifest.holder_functions[declaration.name] = [
                f"{parameter.name}: {parameter.type_ref}"
                for parameter in declaration.parameters
                if any(name in NARROWED_METHODS for name in parameter.type_ref.names)
            ]
            for parameter in declaration.parameters:
                for type_name in parameter.type_ref.names:
                    domain = TYPE_DOMAINS.get(type_name)
                    if domain is not None:
                        manifest.required_domains.add(domain)

        if declaration.name == "main" and declaration.parameters:
            manifest.main_has_capabilities = True
''',
    '''    for declaration in program.declarations:
        capability_parameters = []
        parameter_domains: dict[str, set[str]] = {}
        for parameter in declaration.parameters:
            domains = _type_ref_domains(parameter.type_ref, structs)
            if (
                declaration.name == "main"
                and parameter.type_ref.names == ("SystemCaps",)
            ):
                domains = set()
            if domains:
                capability_parameters.append(parameter)
                parameter_domains[parameter.name] = domains

        if capability_parameters:
            manifest.holder_functions[declaration.name] = [
                f"{parameter.name}: {parameter.type_ref}"
                for parameter in capability_parameters
            ]
            for domains in parameter_domains.values():
                manifest.required_domains.update(domains)

        if (
            declaration.name == "main"
            and any(
                "SystemCaps" in parameter.type_ref.names
                for parameter in declaration.parameters
            )
        ):
            manifest.main_has_capabilities = True
''',
)

replace_once(
    "koschei/capabilities.py",
    '''        bindings: dict[str, str] = {}
        for parameter in declaration.parameters:
            for type_name in parameter.type_ref.names:
                domain = TYPE_DOMAINS.get(type_name)
                if domain is not None:
                    bindings[parameter.name] = domain
''',
    '''        bindings: dict[str, str] = {}
        for parameter in declaration.parameters:
            direct_domains = {
                TYPE_DOMAINS[type_name]
                for type_name in parameter.type_ref.names
                if type_name in TYPE_DOMAINS
            }
            if len(direct_domains) == 1:
                bindings[parameter.name] = next(iter(direct_domains))
''',
)

replace_once(
    "koschei/capabilities.py",
    '''    merged = Manifest()
    for module in graph.in_dependency_order():
        part = analyze(module.program)
''',
    '''    merged = Manifest()
    for module in graph.in_dependency_order():
        imported_structs = {}
        for target_key in module.imports.values():
            target = graph.module_of(target_key)
            for declaration in target.program.structs:
                imported_structs[declaration.name] = declaration
        part = analyze(module.program, imported_structs)
''',
)

# ---------------------------------------------------------------------------
# Permanent adversarial regressions
# ---------------------------------------------------------------------------

Path("tests/test_type_integrity_security.py").write_text(
    r'''from __future__ import annotations

import io
import pathlib
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from koschei.capabilities import analyze, render
from koschei.cli import main
from koschei.interpreter import Interpreter, KoscheiRuntimeError
from koschei.parser import parse
from koschei.semantic import SemanticError, check


ROOT_TUNNEL = """
struct FakeRoot { net: NetRoot }

fn steal(fake: FakeRoot) {
    let net = fake.net.allow("https://evil.example.com")
    let response = net.get("https://evil.example.com/loot") or return
    println(response.text())
}

fn main(caps: SystemCaps) {
    steal(caps)
}
"""


class CapabilityTypeIntegrityTests(unittest.TestCase):
    def assert_security_rejection(self, source: str) -> None:
        with self.assertRaises(SemanticError) as context:
            check(parse(source))
        self.assertIn(context.exception.code, {"KS2401", "KS2402"})

    def test_root_capability_cannot_be_stored_in_struct(self) -> None:
        self.assert_security_rejection(ROOT_TUNNEL)

    def test_main_cannot_receive_system_caps_under_fake_type(self) -> None:
        self.assert_security_rejection(
            'fn main(fake: String) { println("not a capability") }'
        )

    def test_system_caps_cannot_impersonate_capability_bundle_argument(self) -> None:
        self.assert_security_rejection(
            """
            struct NetBox { net: NetCaps }
            fn use(box: NetBox) {
                let response = box.net.get("https://evil.example.com") or return
            }
            fn main(caps: SystemCaps) { use(caps) }
            """
        )

    def test_return_type_cannot_launder_system_caps(self) -> None:
        self.assert_security_rejection(
            """
            struct NetBox { net: NetCaps }
            fn disguise(caps: SystemCaps) -> NetBox { return caps }
            fn main(caps: SystemCaps) { let box = disguise(caps) }
            """
        )

    def test_struct_field_cannot_launder_system_caps(self) -> None:
        self.assert_security_rejection(
            """
            struct NetBox { net: NetCaps }
            fn main(caps: SystemCaps) {
                let box = NetBox { net: caps }
            }
            """
        )

    def test_legitimate_narrowed_capability_bundle_passes(self) -> None:
        program = parse(
            """
            struct NetBox { net: NetCaps }
            fn use(box: NetBox) {
                let response = box.net.get("https://api.example.com") or return
            }
            fn main(caps: SystemCaps) {
                let net = caps.net.allow("https://api.example.com")
                let box = NetBox { net: net }
                use(box)
            }
            """
        )
        report = check(program)
        self.assertGreaterEqual(report.capability_values, 2)

    def test_runtime_rejects_type_laundering_without_semantic_check(self) -> None:
        program = parse(
            """
            struct NetBox { net: NetCaps }
            fn use(box: NetBox) { println("should not run") }
            fn main(caps: SystemCaps) { use(caps) }
            """
        )
        with self.assertRaises(KoscheiRuntimeError) as context:
            Interpreter(program, []).execute_main()
        self.assertEqual(context.exception.code, "KS3401")

    def test_manifest_marks_capability_bearing_struct_parameter(self) -> None:
        source = """
        struct NetBox { net: NetCaps }
        fn use(box: NetBox) {
            let response = box.net.get("https://api.example.com") or return
        }
        fn main() { println("safe") }
        """
        program = parse(source)
        check(program)
        manifest = analyze(program)
        text = render(manifest, "bundle.ks")

        self.assertIn("net", manifest.required_domains)
        self.assertIn("use", manifest.holder_functions)
        self.assertFalse(manifest.is_exact)
        self.assertNotIn("saf hesaplama", text)

    def test_deny_net_blocks_capability_bearing_struct_parameter(self) -> None:
        source = """
        struct NetBox { net: NetCaps }
        fn use(box: NetBox) {
            let response = box.net.get("https://api.example.com") or return
        }
        fn main() { println("safe") }
        """
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "bundle.ks"
            path.write_text(source, encoding="utf-8")
            output = io.StringIO()
            error = io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                exit_code = main(["caps", str(path), "--deny", "net"])

        self.assertEqual(exit_code, 2)
        self.assertIn("reddedilen yetki alanı", error.getvalue())


if __name__ == "__main__":
    unittest.main()
''',
    encoding="utf-8",
)
