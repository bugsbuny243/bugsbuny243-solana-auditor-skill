from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class DiagnosticsAcceptanceCommands(unittest.TestCase):
    def test_acceptance_commands(self) -> None:
        commands = (
            ("explain", "KS2403"),
            ("explain", "KS1401"),
            ("check", "examples/capability.ks"),
            ("check", "examples/runtime_demo.ks"),
            ("run", "examples/runtime_demo.ks"),
            ("check", "examples/control_flow.ks"),
            ("run", "examples/control_flow.ks"),
            ("check", "examples/showcase.ks"),
            ("run", "examples/showcase.ks"),
        )
        for arguments in commands:
            command = [sys.executable, "koschei.py", *arguments]
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            print(f"$ {' '.join(command)}")
            print(completed.stdout, end="")
            print(completed.stderr, end="")
            self.assertEqual(
                completed.returncode,
                0,
                f"Komut başarısız: {' '.join(command)}",
            )


if __name__ == "__main__":
    unittest.main()
