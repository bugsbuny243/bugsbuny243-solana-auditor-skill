#!/usr/bin/env python3
"""Koschei compiler prototipi için komut satırı aracı."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from codegen_c import CodegenError, generate_c
from lexer import LexerError, tokenize
from parser import ParserError, parse
from semantic import SemanticError, check


def read_source(path: str) -> str:
    source_path = Path(path)
    if source_path.suffix != ".ks":
        raise ValueError("Koschei kaynak dosyası '.ks' uzantılı olmalıdır.")
    return source_path.read_text(encoding="utf-8")


def checked_program(path: str):
    program = parse(read_source(path))
    report = check(program)
    return program, report


def command_tokens(path: str) -> int:
    for token in tokenize(read_source(path)):
        print(token)
    return 0


def command_ast(path: str) -> int:
    program = parse(read_source(path))
    print(json.dumps(asdict(program), ensure_ascii=False, indent=2))
    return 0


def command_check(path: str) -> int:
    _, report = checked_program(path)
    print(
        "KOSCHEI CHECK: PASS "
        f"({report.functions} fonksiyon, {report.variables} değişken, "
        f"{report.capability_values} capability değeri)"
    )
    return 0


def command_emit_c(path: str, output: str | None) -> int:
    program, _ = checked_program(path)
    code = generate_c(program)
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code, encoding="utf-8")
        print(f"KOSCHEI C OUTPUT: {output_path}")
    else:
        print(code, end="")
    return 0


def find_c_compiler() -> str:
    compiler = next(
        (
            shutil.which(name)
            for name in ("clang", "gcc", "cc")
            if shutil.which(name)
        ),
        None,
    )
    if compiler is None:
        raise RuntimeError("C compiler bulunamadı; clang, gcc veya cc yükleyin.")
    return compiler


def build_binary(path: str, output: str) -> Path:
    program, _ = checked_program(path)
    code = generate_c(program)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="koschei-") as temp_dir:
        c_path = Path(temp_dir) / "program.c"
        c_path.write_text(code, encoding="utf-8")
        subprocess.run(
            [
                find_c_compiler(),
                str(c_path),
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-o",
                str(output_path),
            ],
            check=True,
        )
    return output_path


def command_build(path: str, output: str) -> int:
    built = build_binary(path, output)
    print(f"KOSCHEI BUILD: PASS ({built})")
    return 0


def command_run(path: str) -> int:
    with tempfile.TemporaryDirectory(prefix="koschei-run-") as temp_dir:
        binary = build_binary(path, str(Path(temp_dir) / "app"))
        completed = subprocess.run([str(binary)], check=False)
        return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="koschei",
        description="Koschei (.ks) compiler prototipi",
    )
    subcommands = cli.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("tokens", "Lexer tokenlarını yazdırır"),
        ("ast", "Parser AST çıktısını JSON olarak yazdırır"),
        ("check", "Sözdizimi, tip ve capability güvenliğini doğrular"),
        ("run", "Desteklenen alt kümeyi native binary olarak çalıştırır"),
    ):
        command = subcommands.add_parser(name, help=help_text)
        command.add_argument("source", help=".ks kaynak dosyası")

    emit_c = subcommands.add_parser(
        "emit-c",
        help="Koschei kodundan C kaynağı üretir",
    )
    emit_c.add_argument("source", help=".ks kaynak dosyası")
    emit_c.add_argument("-o", "--output", help="C çıktı dosyası")

    build = subcommands.add_parser("build", help="Native binary üretir")
    build.add_argument("source", help=".ks kaynak dosyası")
    build.add_argument("-o", "--output", default="app", help="Binary çıktı yolu")
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
        if args.command == "emit-c":
            return command_emit_c(args.source, args.output)
        if args.command == "build":
            return command_build(args.source, args.output)
        if args.command == "run":
            return command_run(args.source)
    except (
        OSError,
        ValueError,
        LexerError,
        ParserError,
        SemanticError,
        CodegenError,
        RuntimeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"KOSCHEI ERROR: {error}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
