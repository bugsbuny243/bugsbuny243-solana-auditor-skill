from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from codegen_c import CodegenError, generate_c
from parser import parse
from semantic import check


SOURCE = '''
fn maybe_value(enabled: Bool) -> Option<Int> {
    if enabled {
        return Some(42)
    }
    return None
}

fn calculate(enabled: Bool) -> Result<Int, Error> {
    if enabled {
        return Ok(7)
    }
    return Err(Error("disabled"))
}

fn checked(enabled: Bool) -> Result<Int, Error> {
    let value = calculate(enabled) or return
    return Ok(value + 1)
}

fn checked_custom(enabled: Bool) -> Result<Int, Error> {
    let value = calculate(enabled) or return Error("custom")
    return Ok(value)
}

fn main() {
    maybe_value(true)
    maybe_value(false)
    checked(true)
    checked(false)
    checked_custom(false)
    println("Koschei native safe types: PASS")
}
'''


class NativeSafeTypesTests(unittest.TestCase):
    def test_emits_option_and_result_abi(self) -> None:
        program = parse(SOURCE)
        check(program)
        code = generate_c(program)

        self.assertIn("typedef struct {\n    bool is_some;", code)
        self.assertIn("ks_option_int_some", code)
        self.assertIn("ks_option_int_none", code)
        self.assertIn("ks_result_int_error_ok", code)
        self.assertIn("ks_result_int_error_err", code)

    def test_or_return_lowers_to_early_result_propagation(self) -> None:
        program = parse(SOURCE)
        check(program)
        code = generate_c(program)

        self.assertIn("if (!__ks_result_", code)
        self.assertIn("return ks_result_int_error_err", code)
        self.assertIn(".value.ok;", code)

    def test_contextless_result_constructor_is_rejected(self) -> None:
        program = parse("fn main() { let value = Ok(1) }")
        check(program)
        with self.assertRaisesRegex(CodegenError, "KS5003"):
            generate_c(program)

    def test_identifier_conditions_are_parenthesized_in_c(self) -> None:
        program = parse(
            "fn choose(flag: Bool) -> Int { "
            "if flag { return 1 } return 0 "
            "} fn main() { choose(true) }"
        )
        check(program)
        code = generate_c(program)
        self.assertIn("if (flag) {", code)

    def test_native_safe_type_program_compiles_and_runs(self) -> None:
        compiler = next(
            (
                shutil.which(name)
                for name in ("clang", "gcc", "cc")
                if shutil.which(name)
            ),
            None,
        )
        if compiler is None:
            self.skipTest("C compiler bulunamadı")

        program = parse(SOURCE)
        check(program)
        code = generate_c(program)

        with tempfile.TemporaryDirectory(prefix="koschei-safe-types-") as temp_dir:
            c_path = Path(temp_dir) / "program.c"
            binary_path = Path(temp_dir) / "program"
            c_path.write_text(code, encoding="utf-8")
            subprocess.run(
                [
                    compiler,
                    str(c_path),
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-o",
                    str(binary_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            completed = subprocess.run(
                [str(binary_path)],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.stdout, "Koschei native safe types: PASS\n")


if __name__ == "__main__":
    unittest.main()
