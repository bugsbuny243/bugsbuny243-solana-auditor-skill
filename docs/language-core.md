# Koschei Language Core v0.1

> Çökmeyen, Hacklenemeyen, Ölümsüz Dil.

Bu belge, çalışan Koschei compiler çekirdeğinin kapsamını sabitler.

## Dört ilke

1. **Yetki olmadan yan etki yok.** Disk, ağ, ortam, süreç — hepsi jeton ister ve jeton derleme zamanında denetlenir.
2. **Null yok.** İleride `Option<T>` ile `Some(value)` / `None` kullanılacaktır.
3. **Hatalar değerdir.** `or return`, `or varsayilan`, `or { ... }` ile ele alınır; sessizce yutulamaz.
4. **Varsayılan değişmezlik.** `let` immutable, `let mut` açık niyet ister.

## Canonical sözdizimi

```ks
fn load_config(disk: DiskReadCaps, path: String) -> String or Error {
    let content = disk.read(path) or return Error("Config okunamadı: {path}")
    return content
}

fn main(caps: SystemCaps) {
    let cfg_read = caps.disk.allow_read_only("/etc/app/")
    let config = load_config(cfg_read, "/etc/app/config.json") or {
        println("Başlatma hatası")
    }

    let mut attempts = 0
    while attempts < 3 {
        attempts = attempts + 1
    }

    if attempts == 3 {
        println("Tamam: {config}")
    }
}
```

## Yetki modeli (derleme zamanında zorlanır)

Kök ve daraltılmış yetkiler **farklı tiplerdir**; bu yüzden daraltma tek yönlüdür:

| İfade | Tip | Yapabildikleri |
|---|---|---|
| `caps.net` | `NetRoot` | yalnızca `allow(origin)` |
| `caps.disk` | `DiskRoot` | yalnızca `allow(path)`, `allow_read_only(path)` |
| `caps.env` | `EnvRoot` | yalnızca `allow(name)` |
| `caps.process` | `ProcessRoot` | yalnızca `allow(cmd)` |
| `NetRoot.allow(...)` | `NetCaps` | `get post put delete request` — `allow` **yok** |
| `DiskRoot.allow(...)` | `DiskCaps` | `read write list delete` — `allow` **yok** |
| `DiskRoot.allow_read_only(...)` | `DiskReadCaps` | `read list` — yazma ve `allow` **yok** |
| `EnvRoot.allow(...)` | `EnvCaps` | `get` |
| `ProcessRoot.allow(...)` | `ProcessCaps` | `run spawn` |

Sonuçlar:
- Kök yetkiyle doğrudan G/Ç yapılamaz → **KS2402**
- Daraltılmış yetki yeniden `allow` çağıramaz → **KS2403**
- Salt-okunur yetki yazamaz → **KS2404**
- Yetkisiz scope'ta yetkili işlem → **KS2401**

## Sözdizimi kuralları

- Büyük harfle başlayan her isim **tip** sayılır; değişken ve fonksiyon adları küçük harfle başlamalıdır.
- `true` / `false` Bool değerleridir; `if` ve `while` koşulları Bool olmalıdır.
- Mantıksal işleçler `&&`, `||`, `!` — `or` anahtar kelimesi yalnızca hata/varsayılan akışı içindir.
- Operatör önceliği: `or` → `||` → `&&` → `== !=` → `< <= > >=` → `+ -` → `* /` → `! -` (unary) → çağrı.
- String interpolasyonu: `"Selam {user.email}"`. v0.1'de yalnızca değişken ve alan erişimi desteklenir; `{1 + 2}` geçersizdir. Düz süslü parantez için `\{` ve `\}` kullanılır.

## 'or' biçimleri

```ks
let a = f() or return Error("üst kata fırlat")
let b = f() or 8080                  // varsayılan değer
let c = f() or { println("logla") }  // blokla ele al
```

## Hata kodları

| Kod | Anlamı |
|---|---|
| KS1101 | Tanımsız isim |
| KS1102 | Aynı scope içinde tekrar tanım |
| KS1201 | Immutable değere atama |
| KS1301 | Tip uyuşmazlığı (`"abc" + 5`, Bool olmayan `if` koşulu vb.) |
| KS2401 | Gerekli yetki bu scope içinde mevcut değil |
| KS2402 | Kök yetki doğrudan kullanılamaz; önce daraltılmalı |
| KS2403 | Daraltılmış yetki yeniden genişletilemez |
| KS2404 | Bu yetki türü ilgili işleme izin vermez |

## v0.1 compiler hattı

```text
.ks source
    -> lexer.py     (interpolasyon, && || !, if/else/while, true/false)
    -> parser.py    (öncelik zinciri, üç 'or' biçimi, kontrol akışı)
    -> ast_nodes.py
    -> semantic.py  (scope, tip, kök/daraltılmış yetki denetimi)
    -> interpreter / code generator (sonraki aşama)
```

## CLI

```bash
python koschei.py tokens examples/capability.ks
python koschei.py ast examples/capability.ks
python koschei.py check examples/capability.ks
```

`check` komutu lexer, parser ve semantic güvenlik kontrollerini birlikte çalıştırır.

## Bilinen sınırlar (v0.1)

- Birleşik dönüş tipleri (`String or Error`) metin olarak taşınır; tam tip denetimi v0.2'de.
- Struct, enum/match, generics, `for` döngüsü, fonksiyon çağrılarında argüman tipi denetimi yok.
- Yol/origin sınırları (`allow("/etc/app/")` kapsamı) statik olarak tip düzeyinde, dinamik olarak runtime aşamasında zorlanacaktır; runtime henüz yazılmadı.
- Tanı mesajları şimdilik Türkçedir; İngilizce yerelleştirme planlanmaktadır.
