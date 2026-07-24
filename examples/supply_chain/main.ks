// Bu programı derlemeye çalışın: 'analytics' modülü yetkisiz erişim denediği
// için derleme KS2401 ile durur. Saldırı çalışma anında değil, derlemede ölür.
import analytics

fn main() {
    let veri = analytics.track("click") or "engellendi"
    println(veri)
}
