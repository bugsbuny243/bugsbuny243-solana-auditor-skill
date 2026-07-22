// Koschei v0.1 özelliklerinin tamamı bir arada
fn load_config(disk: DiskReadCaps, path: String) -> String or Error {
    let content = disk.read(path) or return Error("Config okunamadı: {path}")
    return content
}

fn main(caps: SystemCaps) {
    // Daraltma: yalnızca /etc/app/ altında, yalnızca okuma
    let cfg_read = caps.disk.allow_read_only("/etc/app/")
    let api_net = caps.net.allow("https://api.example.com")

    let config = load_config(cfg_read, "/etc/app/config.json") or {
        println("Başlatma hatası")
    }

    let mut attempts = 0
    let limit = 3
    while attempts < limit {
        attempts = attempts + 1
    }

    if attempts == limit && true {
        println("Denemeler tamam: {config}")
    } else if attempts > 0 {
        println("Kısmi deneme")
    } else {
        println("Hiç denenmedi")
    }

    let score = (2 + 3) * 4 - -1
    let ready = !false
    return
}
