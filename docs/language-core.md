# Koschei Language Core v0.1

> Çökmeyen, Hacklenemeyen, Ölümsüz Dil.

Bu belge, ilk çalışan Koschei compiler çekirdeğinin kapsamını sabitler.

## Canonical sözdizimi

```ks
fn main(caps: SystemCaps) {
    let immutable_value = 10
    let mut mutable_value = 20
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
    -> semantic checker (sonraki aşama)
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

## CLI

```bash
python koschei.py tokens examples/capability.ks
python koschei.py ast examples/capability.ks
python koschei.py check examples/capability.ks
```

`check` komutu şu aşamada lexer ve parser doğrulaması yapar. Semantic güvenlik kontrolleri sonraki compiler aşamasında eklenecektir.
