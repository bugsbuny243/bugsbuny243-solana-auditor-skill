// Çok dosyalı program: 'risk' modülünü içe aktarır.
// import hiçbir yetki taşımaz — risk modülü de diske/ağa dokunamaz.
import risk

fn main() {
    let holders = [
        Holder { address: "7xKq...aB1", percent: 62 },
        Holder { address: "9mPz...cD2", percent: 24 },
        Holder { address: "4nRw...eF3", percent: 5 },
    ]

    for holder in holders {
        let etiket = risk.label(holder.percent)
        println("{holder.address} -> %{holder.percent} [{etiket}]")
    }

    let toplam = risk.total(holders)
    println("Toplam: %{toplam}")
}
