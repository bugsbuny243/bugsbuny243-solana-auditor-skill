// Gerçek bir iş programı: holder listesini risk etiketiyle raporlar.
// Yetki kullanmaz — saf hesaplama, yan etkisi yoktur.
struct Holder {
    address: String,
    percent: Int,
}

fn risk_label(percent: Int) -> String {
    if percent >= 50 {
        return "KRITIK"
    } else if percent >= 20 {
        return "YUKSEK"
    }
    return "NORMAL"
}

fn main() {
    let holders = [
        Holder { address: "7xKq...aB1", percent: 62 },
        Holder { address: "9mPz...cD2", percent: 24 },
        Holder { address: "4nRw...eF3", percent: 5 },
    ]

    let adet = holders.length()
    println("Holder sayisi: {adet}")

    let mut toplam = 0
    for holder in holders {
        let etiket = risk_label(holder.percent)
        println("{holder.address} -> %{holder.percent} [{etiket}]")
        toplam = toplam + holder.percent
    }

    println("Ilk uc holder toplami: %{toplam}")

    let ilk = holders.get(0) or return Error("holder listesi bos")
    println("En buyuk pay: {ilk.address}")

    let guvenli = holders.get(99) or Holder { address: "-", percent: 0 }
    println("Aralik disi erisim guvenli: {guvenli.address}")
}
