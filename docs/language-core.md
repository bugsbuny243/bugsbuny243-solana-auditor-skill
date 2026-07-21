# Koschei Language Core v0.1

> Çökmeyen, Hacklenemeyen, Ölümsüz Dil.

Bu belge, ilk çalışan Koschei compiler çekirdeğinin mevcut kapsamını sabitler.

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
- `null` ve `nil` dilde bulunmaz.
- Bulunmayabilecek değerler `Option<T>`, `Some(value)` ve `None` ile taşınır.
- Başarılı veya hatalı sonuçlar `Result<T, E>`, `Ok(value)` ve `Err(error)` ile taşınır.
- Hata akışı `or return` ile ifade edilir.

## Compiler hattı

```text
.ks source
    -> lexer.py
    -> parser.py
    -> ast_nodes.py
    -> semantic.py
    -> codegen_c.py
    -> clang / gcc / cc
    -> native binary
```

## Mevcut dil desteği

- `fn` fonksiyon bildirimleri
- Parametre adları ve tipleri
- Generic tipler: `Option<T>` ve `Result<T, E>`
- İç içe generic tipler: `Result<Option<String>, Error>`
- `String or Error` biçimindeki birleşik dönüş tipi
- `let` ve `let mut`
- String, tam sayı ve ondalıklı sayı değerleri
- Fonksiyon ve metot çağrıları
- Zincirli alan erişimi (`caps.net.allow`)
- `or return` ifadeleri
- `return`
- Satır ve sütun içeren lexer/parser hataları

## Semantic ve güvenlik kontrolleri

- Scope içi sembol tablosu
- Tanımsız isim denetimi (`KS1101`)
- Aynı isimle tekrar tanım denetimi (`KS1102`)
- Tekrarlanan fonksiyon denetimi (`KS1103`)
- Immutable değere atama engeli (`KS1201`)
- Fonksiyon argüman sayısı denetimi (`KS1301`)
- Fonksiyon argüman tipi denetimi (`KS1302`)
- Mutable değişkene uyumsuz tip atama denetimi (`KS1303`)
- Fonksiyon dönüş tipi denetimi (`KS1304`)
- Geçersiz `or return` kullanımı denetimi (`KS1401`)
- Aktarılamayan hata tipi denetimi (`KS1402`)
- `NetCaps`, `DiskCaps`, `EnvCaps` ve `ProcessCaps` capability kontrolü (`KS2401`)
- `SystemCaps` üzerinden daraltılmış capability türetme

## Güvenli tip örnekleri

```ks
fn maybe_name() -> Option<String> {
    return Some("Koschei")
}

fn safe_number() -> Result<Int, Error> {
    return Ok(42)
}

fn failed_number() -> Result<Int, Error> {
    return Err(Error("Sayı üretilemedi"))
}
```

## CLI

```bash
python koschei.py tokens examples/capability.ks
python koschei.py ast examples/safe_types.ks
python koschei.py check examples/safe_types.ks
python koschei.py emit-c examples/hello.ks -o build/hello.c
python koschei.py build examples/hello.ks -o build/hello
python koschei.py run examples/hello.ks
```

`check` komutu lexer, parser, tip ve capability güvenlik kontrollerini birlikte çalıştırır.

`emit-c`, `build` ve `run` komutları şimdilik dilin güvenli temel alt kümesini destekler:

- `Int`, `Float`, `Bool`, `String` ve `Void`
- Literal veya desteklenen fonksiyon çağrısından tip çıkarımı
- `let` değişkenleri
- Basit atamalar
- `print` ve `println`
- Fonksiyon çağrıları ve `return`

Capability runtime çağrıları ile `Option`/`Result` değerlerinin C temsili henüz code generator kapsamına alınmamıştır. Desteklenmeyen kod sessizce yanlış çıktı üretmek yerine `KS5001` veya `KS5002` ile reddedilir.

## Native örnek

```ks
fn main() {
    let language = "Koschei"
    let version = 1
    println(language)
    println(version)
}
```

```text
Koschei
1
```
