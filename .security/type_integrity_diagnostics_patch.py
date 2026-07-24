from pathlib import Path

path = Path("koschei/diagnostics.py")
text = path.read_text(encoding="utf-8")
marker = '''    "KS3402": Diagnostic(
'''
entry = r'''    "KS3401": Diagnostic(
        code="KS3401",
        title="Çalışma anı: capability tip bütünlüğü ihlali",
        summary=(
            "Runtime, bir capability veya capability taşıyan değerin başka bir tip "
            "gibi geçirildiğini ya da döndürüldüğünü tespit etti."
        ),
        why=(
            "Semantic denetim normalde bu kodu derlemeden reddeder. Runtime aynı "
            "sözleşmeyi savunma derinliği için yeniden kontrol eder; bu hata, tip "
            "denetiminin atlatıldığı veya bozuk bir AST çalıştırıldığı anlamına gelir."
        ),
        fix=(
            "SystemCaps'i yalnızca main parametresi olarak kullanın. Kök yetkiyi main "
            "içinde allow/allow_read_only ile daraltın ve fonksiyonlara gerçek NetCaps, "
            "DiskCaps gibi jetonları, bildirilen tiple birebir uyumlu olarak geçirin."
        ),
        example=(
            "fn fetch(net: NetCaps) {\n"
            "    let response = net.get(\"https://api.example.com\") or return\n"
            "}"
        ),
    ),
'''
if text.count(marker) != 1:
    raise SystemExit(f"diagnostic insertion marker count: {text.count(marker)}")
path.write_text(text.replace(marker, entry + marker), encoding="utf-8")
