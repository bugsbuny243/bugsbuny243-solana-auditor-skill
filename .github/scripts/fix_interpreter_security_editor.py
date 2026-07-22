from pathlib import Path
from textwrap import dedent, indent


path = Path("/tmp/apply_interpreter_security_v011.py")
source = path.read_text(encoding="utf-8")
function_start = source.index("def apply_ks1401() -> None:\n")
start = source.index("    old_block = dedent(\n", function_start)
end = source.index('    path.write_text(text, encoding="utf-8")\n', start)
replacement = indent(
    dedent(
        '''
        execute_start = text.index("    def _execute_block(")
        execute_end = text.index("\\n    def _execute_statement", execute_start)
        execute_block = text[execute_start:execute_end]
        hidden_exit = (
            "                if isinstance(result, KsError):\\n"
            "                    return result\\n"
        )
        if hidden_exit not in execute_block:
            raise RuntimeError("_execute_block gizli hata çıkışı bulunamadı")
        execute_block = execute_block.replace(hidden_exit, "", 1)
        text = text[:execute_start] + execute_block + text[execute_end:]
        '''
    ).strip("\n"),
    "    ",
) + "\n"
source = source[:start] + replacement + source[end:]
path.write_text(source, encoding="utf-8")
