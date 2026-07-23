#!/usr/bin/env python3
"""Koschei compiler prototipi için ilk komut satırı aracı."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from codegen_go import CodegenError, generate_go
from diagnostics import known_codes, lookup as lookup_diagnostic
from interpreter import KoscheiRuntimeError, run as interpret
from lexer import LexerError, tokenize
from parser import ParserError, parse
from semantic import SemanticError, check as semantic_check


def read_source(path: str) -> str:
    source_path = Path(path)
    if source_path.suffix != ".ks":
        raise ValueError("Koschei kaynak dosyası '.ks' uzantılı olmalıdır.")
    return source_path.read_text(encoding="utf-8")


def command_tokens(path: str) -> int:
    for token in tokenize(read_source(path)):
        print(token)
    return 0


def command_ast(path: str) -> int:
    program = parse(read_source(path))
    print(json.dumps(asdict(program), ensure_ascii=False, indent=2))
    return 0


def command_check(path: str) -> int:
    program = parse(read_source(path))
    report = semantic_check(program)
    print(
        "KOSCHEI CHECK: PASS "
        f"({report.functions} fonksiyon, {report.variables} değişken, "
        f"{report.capability_values} capability değeri)"
    )
    return 0


def command_run(path: str) -> int:
    program = parse(read_source(path))
    return interpret(program, [])


def command_emit_go(path: str) -> int:
    program = parse(read_source(path))
    semantic_check(program)
    print(generate_go(program), end="")
    return 0


def command_build(path: str, output: str | None) -> int:
    program = parse(read_source(path))
    semantic_check(program)
    go_source = generate_go(program)

    go_binary = shutil.which("go")
    if go_binary is None:
        print(
            "KOSCHEI ERROR: 'go' bulunamadı. Native derleme için Go kurulu olmalıdır "
            "(https://go.dev/dl). Go kurmadan çalıştırmak için 'koschei.py run' "
            "kullanabilir, üretilen Go kaynağını görmek için 'koschei.py emit-go' "
            "çalıştırabilirsiniz.",
            file=sys.stderr,
        )
        return 1

    source_path = Path(path)
    target = Path(output) if output else source_path.with_suffix("")
    target = target.resolve()

    with tempfile.TemporaryDirectory(prefix="koschei-build-") as workspace:
        directory = Path(workspace)
        (directory / "main.go").write_text(go_source, encoding="utf-8")
        (directory / "go.mod").write_text(
            "module koscheiprogram\n\ngo 1.21\n", encoding="utf-8"
        )
        completed = subprocess.run(
            [go_binary, "build", "-o", str(target), "."],
            cwd=directory,
            capture_output=True,
            text=True,
        )

    if completed.returncode != 0:
        print(
            "KOSCHEI ERROR: Go derlemesi başarısız oldu. Bu bir derleyici hatasıdır; "
            "lütfen kaynak dosyayla birlikte bildirin.\n" + completed.stderr.strip(),
            file=sys.stderr,
        )
        return 1

    print(f"KOSCHEI BUILD: {target}")
    return 0


def command_explain(code: str) -> int:
    diagnostic = lookup_diagnostic(code)
    if diagnostic is None:
        print(
            f"KOSCHEI ERROR: '{code}' bilinen bir hata kodu değil. "
            f"Bilinen kodlar: {', '.join(known_codes())}",
            file=sys.stderr,
        )
        return 1
    print(diagnostic.render())
    return 0


def print_explain_hint(message: str) -> None:
    """Hata metninde bir KS kodu varsa 'explain' komutunu önerir."""
    diagnostic = lookup_diagnostic(message)
    if diagnostic is not None:
        print(
            f"İpucu: bu hatanın açıklaması için "
            f"'python koschei.py explain {diagnostic.code}' çalıştırın.",
            file=sys.stderr,
        )


def build_parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="koschei",
        description="Koschei (.ks) compiler prototipi",
    )
    subcommands = cli.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("tokens", "Lexer tokenlarını yazdırır"),
        ("ast", "Parser AST çıktısını JSON olarak yazdırır"),
        ("check", "Sözdizimi, değişmezlik ve capability kurallarını doğrular"),
        ("run", "Koschei programını yorumlayıcı ile çalıştırır"),
        ("emit-go", "Üretilen Go ara kaynağını yazdırır (Go kurulumu gerekmez)"),
    ):
        command = subcommands.add_parser(name, help=help_text)
        command.add_argument("source", help=".ks kaynak dosyası")

    build = subcommands.add_parser(
        "build", help="Koschei programını tek bir native binary olarak derler"
    )
    build.add_argument("source", help=".ks kaynak dosyası")
    build.add_argument("-o", "--output", help="Çıktı binary yolu")

    explain = subcommands.add_parser(
        "explain", help="Bir Koschei hata kodunu açıklar ve düzeltme örneği verir"
    )
    explain.add_argument("code", help="Hata kodu (ör. KS2403) veya kodu içeren hata metni")

    return cli


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "tokens":
            return command_tokens(args.source)
        if args.command == "ast":
            return command_ast(args.source)
        if args.command == "check":
            return command_check(args.source)
        if args.command == "run":
            return command_run(args.source)
        if args.command == "emit-go":
            return command_emit_go(args.source)
        if args.command == "build":
            return command_build(args.source, args.output)
        if args.command == "explain":
            return command_explain(args.code)
    except KoscheiRuntimeError as error:
        print(f"KOSCHEI RUNTIME ERROR: {error}", file=sys.stderr)
        print_explain_hint(str(error))
        return 1
    except (
        OSError,
        ValueError,
        LexerError,
        ParserError,
        SemanticError,
        CodegenError,
    ) as error:
        print(f"KOSCHEI ERROR: {error}", file=sys.stderr)
        print_explain_hint(str(error))
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
