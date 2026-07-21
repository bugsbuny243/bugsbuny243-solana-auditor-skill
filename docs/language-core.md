# Koschei Language Core v0.3

> Çökmeyen, Hacklenemeyen, Ölümsüz Dil.

Bu belge, çalışan Koschei compiler çekirdeğinin mevcut kapsamını sabitler.

## Canonical sözdizimi

```ks
fn main(caps: SystemCaps) {
    let immutable_value = 10
    let mut mutable_value = 20
    mutable_value = mutable_value + 1

    if mutable_value > 20 {
        println("arttı")
    }
}
```

- Fonksiyonlar `fn` ile tanımlanır.
- Değişkenler `let` ile tanımlanır ve varsayılan olarak immutable'dır.
- Değiştirilebilir değerler `let mut` ile açıkça işaretlenir.
- Bloklar `{ ... }` kullanır ve kendi scope alanını oluşturur.
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
- String, tam sayı, ondalıklı sayı ve Bool değerleri
- `true` ve `false`
- Aritmetik işlemler: `+`, `-`, `*`, `/`
- Karşılaştırmalar: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Tekli sayısal eksi
- `if { ... } else { ... }`
- `while { ... }`
- Fonksiyon ve metot çağrıları
- Zincirli alan erişimi (`caps.net.allow`)
- `or return` ifadeleri
- `return`
- Satır ve sütun içeren lexer/parser hataları

İşlem önceliği standart matematik sırasını izler: tekli işlemler, çarpma/bölme,
toplama/çıkarma, karşılaştırma ve eşitlik.

## Semantic ve güvenlik kontrolleri

- Scope içi sembol tablosu
- `if` ve `while` bloklarında izole scope
- Tanımsız isim denetimi (`KS1101`)
- Aynı isimle tekrar tanım denetimi (`KS1102`)
- Tekrarlanan fonksiyon denetimi (`KS1103`)
- Immutable değere atama engeli (`KS1201`)
- Fonksiyon argüman sayısı denetimi (`KS1301`)
- Fonksiyon argüman tipi denetimi (`KS1302`)
- Mutable değişkene uyumsuz tip atama denetimi (`KS1303`)
- Fonksiyon dönüş tipi denetimi (`KS1304`)
- Operatör ve koşul tipi denetimi (`KS1305`)
- Geçersiz `or return` kullanımı denetimi (`KS1401`)
- Aktarılamayan hata tipi denetimi (`KS1402`)
- `NetCaps`, `DiskCaps`, `EnvCaps` ve `ProcessCaps` capability kontrolü (`KS2401`)
- `SystemCaps` üzerinden daraltılmış capability türetme

`Int / Int` işlemi de `Float` üretir. `Int`, gerekli olduğunda `Float` beklenen
bir konuma güvenli biçimde yükseltilebilir; ters dönüşüm otomatik yapılmaz.

## Native Option ve Result ABI

C backend artık kullanılan her somut safe type için ayrı ve deterministik bir ABI
üretir:

```c
typedef struct {
    bool is_some;
    long long value;
} ks_option_int;

typedef struct {
    bool is_ok;
    union {
        long long ok;
        const char *err;
    } value;
} ks_result_int_error;
```

`Some`, `None`, `Ok` ve `Err` değerleri bu yapılara ait `static inline`
constructor fonksiyonlarına indirilir. `Error` v0.3 ABI içinde UTF-8 C string
olarak taşınır.

```ks
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
```

Bir `Result<T, E>` değeri `let` içinde `or return` ile açıldığında C backend
sonucu bir kez değerlendirir, hata dalında erken dönüş yapar ve başarı değerini
yeni değişkene bağlar:

```ks
fn checked(enabled: Bool) -> Result<Int, Error> {
    let value = calculate(enabled) or return
    return Ok(value + 1)
}
```

Özel hata üretimi de native olarak desteklenir:

```ks
let value = calculate(enabled) or return Error("custom")
```

## Native control flow örneği

```ks
fn main() {
    let mut count = 3

    while count > 0 {
        println(count)
        count = count - 1
    }

    if count == 0 {
        println("Koschei control flow: PASS")
    } else {
        println("Koschei control flow: FAIL")
    }
}
```

```text
3
2
1
Koschei control flow: PASS
```

## CLI

```bash
python koschei.py tokens examples/capability.ks
python koschei.py ast examples/native_safe_types.ks
python koschei.py check examples/native_safe_types.ks
python koschei.py emit-c examples/native_safe_types.ks -o build/native_safe_types.c
python koschei.py build examples/native_safe_types.ks -o build/native_safe_types
python koschei.py run examples/native_safe_types.ks
```

`check` komutu lexer, parser, tip ve capability güvenlik kontrollerini birlikte çalıştırır.

`emit-c`, `build` ve `run` komutlarının v0.3 native kapsamı:

- `Int`, `Float`, `Bool`, `String`, `Error` ve `Void`
- Aritmetik, karşılaştırma ve tekli eksi
- `let` değişkenleri ve basit atamalar
- `if/else` ve `while`
- `print` ve `println`
- Fonksiyon çağrıları ve `return`
- Somut `Option<T>` ve `Result<T, E>` C yapıları
- `Some`, `None`, `Ok`, `Err` ve `Error` constructor'ları
- `let value = result or return [error]` biçiminde native Result aktarımı

Native constructor'ın eksik generic tarafı yalnızca kullanım bağlamından
belirlenebilir. Örneğin `return Ok(1)` dönüş tipinden `Result<Int, Error>`
olarak çözülür; bağlamsız `let value = Ok(1)` ise sessiz varsayım yapmak yerine
`KS5003` ile reddedilir.

Şimdilik native `or return` yalnızca `Result<T, E>` ve `let` bağlamında çalışır.
`Option<T>` açma, `Result<Void, E>`, pattern `match`, capability runtime ABI ve
kaynak bölgeleri sonraki aşamalardır. Desteklenmeyen kod yanlış C üretmek yerine
`KS5001`, `KS5002` veya `KS5003` ile reddedilir.
