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

function_start = source.index("def apply_ks1401() -> None:\n")
start = source.index("    old_statement = dedent(\n", function_start)
end = source.index("    helpers = indent(\n", start)
replacement = indent(
    dedent(
        '''
        statement_start = semantic.index(
            "        if isinstance(statement, ExpressionStatement):\\n"
        )
        statement_end = semantic.index(
            "\\n        if isinstance(statement, IfStatement):", statement_start
        )
        current_statement = semantic[statement_start:statement_end]
        expected_statement = (
            "        if isinstance(statement, ExpressionStatement):\\n"
            "            self._check_expression(statement.expression)\\n"
            "            return\\n"
        )
        if current_statement != expected_statement:
            raise RuntimeError("ExpressionStatement semantic bloğu beklenenden farklı")
        new_statement = (
            "        if isinstance(statement, ExpressionStatement):\\n"
            "            self._check_expression(statement.expression)\\n"
            "            if self._is_unhandled_error_call(statement.expression):\\n"
            "                raise SemanticError(\\n"
            "                    \\"KS1401\\",\\n"
            "                    \\"Hata dönebilen çağrının sonucu ele alınmalıdır \\"\\n"
            "                    \\"('let ... = ...', 'or return', 'or varsayılan' veya \\"\\n"
            "                    \\"'or { ... }' kullanın).\\",\\n"
            "                    statement.location,\\n"
            "                )\\n"
            "            return\\n"
        )
        semantic = (
            semantic[:statement_start]
            + new_statement
            + semantic[statement_end:]
        )
        '''
    ).strip("\n"),
    "    ",
) + "\n"
source = source[:start] + replacement + source[end:]
path.write_text(source, encoding="utf-8")
