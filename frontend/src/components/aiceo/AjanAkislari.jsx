import React from "react";
import { ArrowRight, ArrowDown, Download, Cog, Upload, CornerDownRight } from "lucide-react";

/**
 * AjanAkislari — her ajan için "Nasıl Çalışıyor?" akış kartı (FAZ 3, madde 10).
 * Girdi (ne okur) → Süreç (ne yapar) → Çıktı (ne üretir) → Sıradaki (kime devreder).
 * STATİK/config tabanlı — canlı veri gerektirmez; sistemin gerçek boru hattını yansıtır.
 */
const AJANLAR = [
  {
    key: "ayda", ad: "Ayda", unvan: "AI CEO", renk: "#2563eb",
    girdi: "Tüm sistem fotoğrafı (muhasebe, öğretmen, kullanım, NPS)",
    surec: "Deterministik sağlık skoru + AI analiz → önceliklendirilmiş öneriler; her sayı fotoğrafa karşı doğrulanır (uydurma sayı yakalanır)",
    cikti: "Öneriler (ai_ceo_oneriler) + günlük/haftalık/aylık rapor",
    sonraki: "Karar Zekâsı (öneri → karar dosyası)",
  },
  {
    key: "karar", ad: "Karar Zekâsı", unvan: "Karar Motoru", renk: "#7c3aed",
    girdi: "Ayda önerisi + kurumsal hafıza + geçmiş dersler + fotoğraf",
    surec: "Kanıt/hipotez/alternatif → yapılandırılmış karar dosyası; pilot/kontrol deneyi + net etki ölçümü",
    cikti: "Karar dosyası (ai_ceo_proposals) + ölçüm (net etki)",
    sonraki: "AI Squad (onaylı karar → üretim görevi)",
  },
  {
    key: "atlas", ad: "Atlas", unvan: "Baş Yazılım Mimarı", renk: "#6366f1",
    girdi: "Talep metni + mevcut kod bloğu",
    surec: "SOLID/teknik borç analizi, mimari değerlendirme",
    cikti: "{ kod_kalitesi_notu, teknik_borc, mimari_onay } — onay yoksa hat durur",
    sonraki: "Lina (mimari onaylıysa tasarıma devreder)",
  },
  {
    key: "lina", ad: "Lina", unvan: "UI/UX Tasarımcısı", renk: "#ec4899",
    girdi: "Atlas'ın onayladığı talep",
    surec: "React/Tailwind bileşeni tasarımı + risk seviyesi",
    cikti: "{ react_kodu, hedef_dosya, risk_seviyesi }",
    sonraki: "Nova (üretilen kodu test/vize için devreder)",
  },
  {
    key: "nova", ad: "Nova", unvan: "Test & Kalite Güvence", renk: "#10b981",
    girdi: "Lina'nın ürettiği React kodu",
    surec: "Test senaryoları, regresyon riski, a11y — skorlar AI TAHMİNİDİR (gerçek ölçüm değil)",
    cikti: "{ deploy_onayi, engelleme_nedenleri }",
    sonraki: "Dağıtım Adımı (vize varsa insan onayına devreder)",
  },
  {
    key: "ayaz", ad: "Ayaz", unvan: "Uygulama & Devir", renk: "#f59e0b",
    girdi: "Nova vizeli pipeline + admin gerekçesi",
    surec: "JSX'i yeniden güvenlik tarar (AST), kriptografik hash-chain audit'e mühürler — OTOMATİK DEPLOY YOK",
    cikti: "Onaylı entegrasyon kuyruğu kaydı (squad_deploy_queue)",
    sonraki: "Deploy Kuyruğu (manuel git+Vercel entegrasyonu)",
  },
  {
    key: "deniz", ad: "Deniz", unvan: "Bağımsız Denetçi", renk: "#475569",
    girdi: "Ayda önerileri + Karar dosyaları + Ayaz audit log + Squad ret örüntüleri",
    surec: "DETERMİNİSTİK kurallar (dayanak zayıflığı, hash-chain bütünlüğü, ret dengesizliği) — AI'ya güven yok",
    cikti: "Denetim bulguları (ai_ceo_deniz_bulgular) + karne",
    sonraki: "Admin (bulguları geçerli/geçersiz işaretler)",
  },
  {
    key: "miran", ad: "Miran", unvan: "Öğretmen Koçu / Danışman", renk: "#d97706",
    girdi: "Öğretmen: kendi öğrenci/takip verisi · Muhasebeci: finansal veri (ters kapsam)",
    surec: "Rol-bazlı koçluk; kıyas/ceza/tutar guard'ları (öğretmen ↔ muhasebeci sızıntı önleme)",
    cikti: "Kişisel koçluk kartları / finansal tespit",
    sonraki: "İlgili öğretmen / muhasebeci (kapsam-dışı devir yok)",
  },
];

function Adim({ ikon: Ikon, etiket, metin, renk }) {
  return (
    <div className="flex-1 min-w-[150px] rounded-xl border border-line bg-app p-2.5">
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase mb-1" style={{ color: renk }}>
        <Ikon className="h-3.5 w-3.5" />{etiket}
      </div>
      <div className="text-[11px] text-content leading-snug">{metin}</div>
    </div>
  );
}

export default function AjanAkislari() {
  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="font-semibold text-content">Nasıl Çalışıyor? — Ajan İş Akışları</div>
        <div className="text-xs text-subtle mt-0.5">Her ajanın Girdi → Süreç → Çıktı → Sıradaki devir zinciri. Statik referans (canlı veri değil).</div>
      </div>

      {AJANLAR.map((a) => (
        <div key={a.key} className="rounded-2xl border border-line bg-surface p-3 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: a.renk }} />
            <span className="font-semibold text-content text-sm">{a.ad}</span>
            <span className="text-[11px] text-subtle">· {a.unvan}</span>
          </div>
          <div className="flex flex-col lg:flex-row items-stretch gap-1.5">
            <Adim ikon={Download} etiket="Girdi" metin={a.girdi} renk={a.renk} />
            <div className="flex items-center justify-center text-subtle"><ArrowRight className="h-4 w-4 hidden lg:block" /><ArrowDown className="h-4 w-4 lg:hidden" /></div>
            <Adim ikon={Cog} etiket="Süreç" metin={a.surec} renk={a.renk} />
            <div className="flex items-center justify-center text-subtle"><ArrowRight className="h-4 w-4 hidden lg:block" /><ArrowDown className="h-4 w-4 lg:hidden" /></div>
            <Adim ikon={Upload} etiket="Çıktı" metin={a.cikti} renk={a.renk} />
            <div className="flex items-center justify-center text-subtle"><ArrowRight className="h-4 w-4 hidden lg:block" /><ArrowDown className="h-4 w-4 lg:hidden" /></div>
            <Adim ikon={CornerDownRight} etiket="Sıradaki" metin={a.sonraki} renk={a.renk} />
          </div>
        </div>
      ))}
    </div>
  );
}
