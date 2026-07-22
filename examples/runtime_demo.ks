// Koschei interpreter v0.1 — ağ gerektirmeyen runtime demosu
fn validate_number(raw: String) -> String or Error {
    let value = raw.to_int() or return Error("Sayı okunamadı")
    return "sayı hazır"
}

fn main(caps: SystemCaps) {
    let env = caps.env.allow("KOSCHEI_RUNTIME_NAME")
    let name = env.get() or "misafir"

    let validation = validate_number("3") or return Error("Doğrulama başarısız")

    let recovered = "x".to_int() or {
        println("Geçersiz sayı blok içinde ele alındı")
        2
    }

    let mut count = 3
    while count > 0 {
        println("Geri sayım: {count}")
        count = count - 1
    }

    println("Merhaba {name}; {validation}; varsayılan: {recovered}")
}
