// ZARARLI PAKET ÖRNEĞİ — bu dosya BİLEREK derlenmez.
// Gerçek npm/pip saldırılarının çalışma biçimini taklit eder: sessizce bir
// gizli dosyayı okuyup dışarı sızdırmaya çalışır.
// Koschei'de 'disk' bir jeton olmadan var olmadığı için KS2401 ile reddedilir.
fn track(event: String) -> String or Error {
    let secret = disk.read("/etc/app/secrets.env") or return Error("okunamadi")
    return secret
}
