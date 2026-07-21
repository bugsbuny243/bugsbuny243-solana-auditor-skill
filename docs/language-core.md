# Koschei Language Core v0.1

> Çökmeyen, Hacklenemeyen, Ölümsüz Dil.

Bu belge, ilk çalışan Koschei compiler çekirdeğinin kapsamını sabitler.

## Canonical sözdizimi

```ks
fn main(caps: SystemCaps) {
    let immutable_value = 10
    let mut mutable_value = 20
    mutable_value = 21
    return
}
```

- Fonksiyonlar `fn` ile tanımlanır.
- Değişkenler `let` ile tanımlanır ve varsayılan olarak immutable'dır.
- Değiştirilebilir değerler `let mut` ile açıkça işaretlenir.
- Bloklar `{ ... }` kullanır.
- `null` ve `nil` dilde bulunmaz; gelecekte `Option<T>` için `Some(value)` ve `None` kullanılacaktır.
- Hata akışı `or return` ile ifade edilir.

## v0.1 compiler hattı

```text
.ks source
    -> lexer.py
    -> parser.py
    -> ast_nodes.py
    -> semantic.py
    -> code generator (sonraki aşama)
```

## Mevcut destek

- `fn` fonksiyon bildirimleri
- Parametre adları ve tipleri
- `String or Error` biçiminde ilk birleşik dönüş tipi
- `let` ve `let mut`
- String ve sayı değerleri
- Fonksiyon/metot çağrıları
- Zincirli alan erişimi (`caps.net.allow`)
- `or return` ifadeleri
- `return`
- Satır ve sütun içeren lexer/parser hataları
- Scope içi sembol tablosu
- Tanımsız isim denetimi (`KS1101`)
- Aynı isimle tekrar tanım denetimi (`KS1102`)
- Immutable değere atama engeli (`KS1201`)
- `NetCaps`, `DiskCaps`, `EnvCaps` ve `ProcessCaps` için ilk capability kontrolü (`KS2401`)
- `SystemCaps` üzerinden daraltılmış capability türetme

## CLI

```bash
python koschei.py tokens examples/capability.ks
python koschei.py ast examples/capability.ks
python koschei.py check examples/capability.ks
```

`check` komutu lexer, parser ve semantic güvenlik kontrollerini birlikte çalıştırır.

Geçerli örnek çıktı:

```text
KOSCHEI CHECK: PASS (2 fonksiyon, 4 değişken, 4 capability değeri)
```

Immutable ihlal örneği:

```ks
fn main() {
    let value = 10
    value = 20
}
```

Compiler sonucu:

```text
KS1201: 'value' immutable bir değerdir; değiştirmek için 'let mut' kullanın.
```
