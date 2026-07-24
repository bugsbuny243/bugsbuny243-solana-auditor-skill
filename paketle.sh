#!/usr/bin/env bash
set -euo pipefail

MODULES="lexer parser ast_nodes semantic interpreter modules diagnostics formatter capabilities codegen_go"

# 1) Derleyici dosyalarını pakete taşı
mkdir -p koschei
for name in $MODULES; do
    git mv "$name.py" "koschei/$name.py"
done
git mv koschei.py koschei/cli.py

# 2) Paket içi importları göreli yap (satır başı ve girintili biçimler)
for name in $MODULES; do
    sed -i -E "s/^from ${name} import /from .${name} import /" koschei/*.py
    sed -i -E "s/^([[:space:]]+)from ${name} import /\1from .${name} import /" koschei/*.py
done

# 3) Testleri paket düzenine uyarla
for name in $MODULES; do
    sed -i -E "s/^from ${name} import /from koschei.${name} import /" tests/*.py
    sed -i -E "s/^([[:space:]]+)from ${name} import /\1from koschei.${name} import /" tests/*.py
done
sed -i -E "s/^from koschei import main$/from koschei.cli import main/" tests/*.py
sed -i -E 's#REPO_ROOT / name#REPO_ROOT / "koschei" / name#' tests/*.py
sed -i -E 's#"python3", "koschei\.py", "run"#"python3", "-m", "koschei", "run"#' tests/*.py
python3 - <<'PY'
from pathlib import Path
p = Path("tests/test_codegen_go.py")
t = p.read_text(encoding="utf-8")
t = t.replace('                    "python3",\n                    "koschei.py",\n                    "build",',
              '                    "python3",\n                    "-m",\n                    "koschei",\n                    "build",')
p.write_text(t, encoding="utf-8")
PY

touch koschei/py.typed
