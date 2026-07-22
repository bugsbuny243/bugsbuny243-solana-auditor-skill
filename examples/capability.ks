// Kısıtlı ağ yetkisi kullanan Koschei örneği
fn fetch_data(net: NetCaps, url: String) -> String or Error {
    let response = net.get(url) or return Error("Veri alınamadı: {url}")
    return response.text()
}

fn main(caps: SystemCaps) {
    let allowed_net = caps.net.allow("https://api.example.com")
    let mut retry_count = 3
    while retry_count > 0 {
        retry_count = retry_count - 1
    }
    let result = fetch_data(allowed_net, "https://api.example.com/v1") or "varsayılan"
    return
}
