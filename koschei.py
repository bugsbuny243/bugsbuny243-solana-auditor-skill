#!/usr/bin/env python3
"""Koschei compiler prototipi için ilk komut satırı aracı."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

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
    ):
        command = subcommands.add_parser(name, help=help_text)
        command.add_argument("source", help=".ks kaynak dosyası")

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
    except KoscheiRuntimeError as error:
        print(f"KOSCHEI RUNTIME ERROR: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, LexerError, ParserError, SemanticError) as error:
        print(f"KOSCHEI ERROR: {error}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
