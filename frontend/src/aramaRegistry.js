// Genel Özellik/Modül Arama Kaydı (registry) — uygulamadaki TÜM sekme/alt-sekme/gizli
// bölümleri statik olarak listeler. Arama role göre filtrelenir; seçilince hedef sekmeye
// yönlendirilir (window "oba-git" olayı). Menüde GÖRÜNMEYEN bölümler (Kurslar, Görevler,
// derin Ayarlar alt-sekmeleri, AI CEO, Muhasebe alt görünümleri) bilhassa dahildir.

// hedef: { sekme: <ana sekme/route>, altSekme?: <Ayarlar alt-sekmesi> }
// roller: bu öğeyi görebilen roller. ad: görünen isim. anahtar: eş anlamlı/kısaltma dizisi.
const A = ["admin"], AK = ["admin", "coordinator"], T = ["teacher"], M = ["accountant"], V = ["parent"], O = ["student"];

export const ARAMA_KAYDI = [
  // ─────────── ADMIN / KOORDİNATÖR — ana sekmeler ───────────
  { ad: "Dashboard (Gösterge Panosu)", roller: AK, hedef: { sekme: "dashboard" }, anahtar: ["ana sayfa", "gosterge", "grafik", "kpi", "ozet", "istatistik", "nakit akisi", "reklam gideri"] },
  { ad: "Öğretmenler", roller: AK, hedef: { sekme: "teachers" }, anahtar: ["ogretmen listesi", "personel", "egitmen"] },
  { ad: "Öğrenciler", roller: AK, hedef: { sekme: "students" }, anahtar: ["ogrenci listesi", "kayit", "veli", "tc"] },
  { ad: "Kurslar & Görevler", roller: AK, hedef: { sekme: "courses" }, anahtar: ["kurs", "ders tanimi", "kur", "gizli", "kurs yonetimi"] },
  { ad: "Muhasebe / Ödemeler", roller: A, hedef: { sekme: "payments" }, anahtar: ["odeme", "tahsilat", "finans", "para", "vergi", "hakedis", "alacak"] },
  { ad: "Kullanıcılar & Yetkiler", roller: AK, hedef: { sekme: "users" }, anahtar: ["kullanici", "rol", "yetki", "hesap", "sifre", "rbac"] },
  { ad: "Gelişim (Sınav/Kelime/Oyun)", roller: AK, hedef: { sekme: "gelisim" }, anahtar: ["gelisim", "oyun", "sinav", "kelime"] },
  { ad: "Giriş Analizi", roller: AK, hedef: { sekme: "giris-analizi" }, anahtar: ["analiz", "okuma analizi", "tanilama", "diagnostic", "rapor"] },
  { ad: "Görevler", roller: AK, hedef: { sekme: "gorevler" }, anahtar: ["gorev", "atama", "task"] },
  { ad: "Mesajlar", roller: AK, hedef: { sekme: "mesajlar" }, anahtar: ["mesaj", "iletisim", "bildirim"] },
  { ad: "Ayarlar", roller: AK, hedef: { sekme: "ayarlar" }, anahtar: ["ayar", "sistem ayarlari", "yapilandirma"] },

  // ─────────── ADMIN — Gelişim alt-bölümleri (menüde ikincil) ───────────
  { ad: "Sınav Yönetimi", roller: AK, hedef: { sekme: "sinav" }, anahtar: ["sinav", "test", "deneme"] },
  { ad: "MEB Kelime Listeleri", roller: AK, hedef: { sekme: "meb-kelime" }, anahtar: ["meb", "kelime listesi", "sozcuk"] },
  { ad: "Ders Programı", roller: AK, hedef: { sekme: "ders-programi" }, anahtar: ["program", "takvim", "surukle birak", "ders saati"] },
  { ad: "Okuma Metinleri (Havuz)", roller: AK, hedef: { sekme: "okuma-metinleri" }, anahtar: ["metin", "okuma parcasi", "havuz", "ice aktar", "metin havuzu"] },

  // ─────────── ADMIN — Ayarlar mega-sekmesi alt-bölümleri (gizli/derin) ───────────
  { ad: "AI Yönetim Merkezi", roller: AK, hedef: { sekme: "ai-merkezi" }, anahtar: ["yapay zeka", "ai merkezi", "asistan"] },
  { ad: "AI CEO Kokpiti", roller: A, hedef: { sekme: "ai-ceo" }, anahtar: ["ai ceo", "kokpit", "denetim", "otonom", "zincir", "persona", "rag", "ceo"] },
  { ad: "AI Deniz", roller: A, hedef: { sekme: "ai-deniz" }, anahtar: ["ai deniz", "asistan", "yapay zeka deniz"] },
  { ad: "Loglar / İşlem Kayıtları", roller: AK, hedef: { sekme: "loglar" }, anahtar: ["log", "islem kaydi", "denetim", "audit", "vekaleten", "giris kaydi"] },
  { ad: "SSS Yönetimi", roller: AK, hedef: { sekme: "sss-yonetimi" }, anahtar: ["sss", "sikca sorulan", "yardim", "soru cevap"] },
  { ad: "Tema Yönetimi", roller: AK, hedef: { sekme: "tema-yonetimi" }, anahtar: ["tema", "renk", "gorunum", "dark mode"] },
  { ad: "Rozet Yönetimi", roller: AK, hedef: { sekme: "rozet-yonetimi" }, anahtar: ["rozet", "odul", "basari", "ikon"] },
  { ad: "Toplu Kayıt (Excel)", roller: AK, hedef: { sekme: "toplu-kayit" }, anahtar: ["toplu", "excel", "ice aktar", "import", "toplu ogrenci"] },
  { ad: "Modüller / Yama Yönetimi", roller: AK, hedef: { sekme: "moduller" }, anahtar: ["modul", "yama", "zip", "eklenti", "patch", "surum", "rollback"] },
  { ad: "Güncelleme / Yeni Ne Var", roller: AK, hedef: { sekme: "guncelleme" }, anahtar: ["guncelleme", "surum", "yeni ne var", "changelog"] },
  { ad: "Yedekleme", roller: AK, hedef: { sekme: "yedekleme" }, anahtar: ["yedek", "backup", "geri yukleme", "restore"] },

  // ─────────── ADMIN — SistemAyarlari (Ayarlar → alt-sekme) ───────────
  { ad: "Özellik Yönetimi (Aç/Kapa)", roller: AK, hedef: { sekme: "ayarlar", altSekme: "ozellikler" }, anahtar: ["ozellik", "ac kapa", "modul ac", "feature flag", "toggle"] },
  { ad: "XP Değerleri", roller: AK, hedef: { sekme: "ayarlar", altSekme: "xp" }, anahtar: ["xp", "puan", "deneyim", "katki puani"] },
  { ad: "Öğretmen XP Ağırlıkları", roller: AK, hedef: { sekme: "ayarlar", altSekme: "ogretmen_xp" }, anahtar: ["ogretmen xp", "ogretmen puan", "agirlik"] },
  { ad: "Lig Eşikleri", roller: AK, hedef: { sekme: "ayarlar", altSekme: "lig" }, anahtar: ["lig", "seviye esigi", "liderlik"] },
  { ad: "Öğretmen Rozetleri", roller: AK, hedef: { sekme: "ayarlar", altSekme: "ogretmen_rozet" }, anahtar: ["ogretmen rozet", "odul"] },
  { ad: "Öğrenci Rozetleri", roller: AK, hedef: { sekme: "ayarlar", altSekme: "ogrenci_rozet" }, anahtar: ["ogrenci rozet", "odul"] },
  { ad: "Anket Soruları", roller: AK, hedef: { sekme: "ayarlar", altSekme: "anket" }, anahtar: ["anket", "veli anketi", "memnuniyet", "soru"] },
  { ad: "Kutulu Okuma Ayarı", roller: AK, hedef: { sekme: "ayarlar", altSekme: "kutulu_okuma" }, anahtar: ["kutulu okuma", "kutu", "kelime sayisi"] },
  { ad: "Rapor Ölçütleri (Norm/Eşik)", roller: AK, hedef: { sekme: "ayarlar", altSekme: "rapor_olcutleri" }, anahtar: ["rapor olcut", "norm", "okuma hizi", "dogruluk esigi", "prozodik esigi", "prozodik esikleri", "anlama rubrik", "gelisim esigi"] },
  { ad: "TIMI Puanlama Anahtarı", roller: AK, hedef: { sekme: "ayarlar", altSekme: "timi_anahtar" }, anahtar: ["timi", "puanlama anahtari"] },
  { ad: "TIMI Rapor Metinleri", roller: AK, hedef: { sekme: "ayarlar", altSekme: "timi_metin" }, anahtar: ["timi rapor", "metin bankasi"] },
  { ad: "Giriş Analizi Rapor Metinleri & Sınıf Kategorileri", roller: AK, hedef: { sekme: "ayarlar", altSekme: "giris_rapor" }, anahtar: ["giris analizi rapor", "rapor metin bankasi", "sinif olcum kategorileri", "sinif kategorileri", "sonuc metin", "oneriler"] },
  { ad: "Egzersiz Kalite Kontrol (Askıya Alınanlar/Eşikler)", roller: AK, hedef: { sekme: "ayarlar", altSekme: "egzersiz_kalite" }, anahtar: ["egzersiz kalite", "kalite kontrol", "askiya alma", "bekleyenler", "denetim", "sinif uygunluk esigi"] },
  { ad: "Profil Görünürlüğü", roller: AK, hedef: { sekme: "ayarlar", altSekme: "profil_gorunurluk" }, anahtar: ["profil gorunurluk", "gizlilik"] },
  { ad: "Instagram Ayarları", roller: AK, hedef: { sekme: "ayarlar", altSekme: "instagram" }, anahtar: ["instagram", "sosyal medya"] },
  { ad: "Veri & KVKK", roller: AK, hedef: { sekme: "ayarlar", altSekme: "kvkk" }, anahtar: ["kvkk", "veri", "gizlilik", "kisisel veri", "silme"] },
  { ad: "Sezonluk Reset", roller: AK, hedef: { sekme: "ayarlar", altSekme: "sezon" }, anahtar: ["sezon", "reset", "sifirlama", "donem sonu"] },
  { ad: "Analiz Havuzu Bakımı", roller: A, hedef: { sekme: "ayarlar", altSekme: "analiz_havuz" }, anahtar: ["analiz havuz", "havuz bakim", "metin bakim", "ice aktar", "olcum metinleri"] },
  { ad: "Metin Kalite Denetimi", roller: A, hedef: { sekme: "ayarlar", altSekme: "metin_kalite" }, anahtar: ["metin kalite", "riskli metin", "kalite denetimi", "oneri kuyrugu"] },
  { ad: "Duyurular (Yeni Ne Var)", roller: A, hedef: { sekme: "ayarlar", altSekme: "duyurular" }, anahtar: ["duyuru", "yeni ne var"] },
  { ad: "Altyapı", roller: A, hedef: { sekme: "ayarlar", altSekme: "altyapi" }, anahtar: ["altyapi", "deploy", "sunucu", "render", "vercel"] },
  { ad: "Bakım Modu", roller: A, hedef: { sekme: "ayarlar", altSekme: "bakim" }, anahtar: ["bakim modu", "maintenance"] },

  // ─────────── ÖĞRETMEN ───────────
  { ad: "Dashboard", roller: T, hedef: { sekme: "dashboard" }, anahtar: ["ana sayfa", "gosterge", "ozet"] },
  { ad: "Öğrencilerim", roller: T, hedef: { sekme: "ogrencilerim" }, anahtar: ["ogrenci", "sinif"] },
  { ad: "Görevler", roller: T, hedef: { sekme: "gorevler" }, anahtar: ["gorev", "atama"] },
  { ad: "Giriş Analizi", roller: T, hedef: { sekme: "giris-analizi" }, anahtar: ["analiz", "okuma analizi", "rapor", "tanilama"] },
  { ad: "Gelişim", roller: T, hedef: { sekme: "gelisim" }, anahtar: ["gelisim", "ilerleme"] },
  { ad: "Ders Programı", roller: T, hedef: { sekme: "program" }, anahtar: ["program", "takvim", "ders saati"] },
  { ad: "Egzersiz Kalite Kontrol", roller: T, hedef: { sekme: "kalite-kontrol" }, anahtar: ["kalite kontrol", "egzersiz degerlendirme", "uygun degil", "degisiklik talebi"] },
  { ad: "Mesajlar", roller: T, hedef: { sekme: "mesajlar" }, anahtar: ["mesaj", "iletisim"] },
  { ad: "Danışmanım Miran", roller: T, hedef: { sekme: "kocum-miran" }, anahtar: ["koc", "danisman", "miran", "rehber"] },
  { ad: "Profilim", roller: T, hedef: { sekme: "profilim" }, anahtar: ["profil", "hesabim"] },
  { ad: "Yardım (SSS)", roller: T, hedef: { sekme: "sss" }, anahtar: ["yardim", "sss", "destek"] },

  // ─────────── MUHASEBECİ ───────────
  { ad: "Öğrenci Ödemeleri", roller: M, hedef: { sekme: "ogrenci" }, anahtar: ["ogrenci odeme", "tahsilat", "vergi orani", "ogretmen payi", "ogretmene gore", "gruplu", "alacak", "borclu"] },
  { ad: "Öğretmen Ödemeleri (Dönem/Hakediş)", roller: M, hedef: { sekme: "ogretmen" }, anahtar: ["ogretmen odeme", "hakedis", "donem", "avans"] },
  { ad: "Veli Mesaj Funnel", roller: M, hedef: { sekme: "funnel" }, anahtar: ["funnel", "veli mesaj", "huni", "netgsm"] },

  // ─────────── VELİ ───────────
  { ad: "Özet", roller: V, hedef: { sekme: "ozet" }, anahtar: ["ozet", "ana sayfa", "gosterge"] },
  { ad: "Okumalar", roller: V, hedef: { sekme: "okumalar" }, anahtar: ["okuma", "gecmis", "kitap"] },
  { ad: "Görevler", roller: V, hedef: { sekme: "gorevler" }, anahtar: ["gorev", "odev"] },
  { ad: "Öğretmeni Değerlendir (Anket)", roller: V, hedef: { sekme: "anket" }, anahtar: ["anket", "degerlendir", "memnuniyet", "puanla"] },
  { ad: "Mesajlar", roller: V, hedef: { sekme: "mesajlar" }, anahtar: ["mesaj", "iletisim"] },
  { ad: "Yardım", roller: V, hedef: { sekme: "sss" }, anahtar: ["yardim", "sss"] },

  // ─────────── ÖĞRENCİ ───────────
  { ad: "Ana Sayfa", roller: O, hedef: { sekme: "ana" }, anahtar: ["ana sayfa", "ozet"] },
  { ad: "Görevlerim", roller: O, hedef: { sekme: "gorevler" }, anahtar: ["gorev", "odev"] },
  { ad: "Gelişim", roller: O, hedef: { sekme: "gelisim" }, anahtar: ["gelisim", "ilerleme", "rozet"] },
  { ad: "Sıralama", roller: O, hedef: { sekme: "siralama" }, anahtar: ["siralama", "lig", "liderlik", "puan tablosu"] },
  { ad: "Mesajlar", roller: O, hedef: { sekme: "mesajlar" }, anahtar: ["mesaj"] },
];

// Türkçe-toleranslı normalizasyon: küçük harf + aksan/özel karakter sadeleştirme.
export function trNorm(s) {
  return (s || "")
    .toLocaleLowerCase("tr")
    .replace(/ı/g, "i").replace(/İ/g, "i").replace(/ş/g, "s").replace(/ğ/g, "g")
    .replace(/ç/g, "c").replace(/ö/g, "o").replace(/ü/g, "u").replace(/â/g, "a").replace(/î/g, "i")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

// Rol + sorguya göre kayıtları filtrele. Her token (kelime) haystack'te substring olmalı (AND).
export function araKayitlar(q, rol) {
  const nq = trNorm(q);
  if (nq.length < 2) return [];
  const tokenlar = nq.split(" ").filter(Boolean);
  const uygun = ARAMA_KAYDI.filter((e) => e.roller.includes(rol));
  const skorlu = [];
  for (const e of uygun) {
    const haystack = trNorm(e.ad + " " + (e.anahtar || []).join(" "));
    if (tokenlar.every((t) => haystack.includes(t))) {
      // Basit skor: ad'da geçenler önce; tam ad eşleşmesi en üstte
      const adNorm = trNorm(e.ad);
      let skor = 0;
      if (adNorm.includes(nq)) skor += 100;
      for (const t of tokenlar) if (adNorm.includes(t)) skor += 10;
      skorlu.push({ e, skor });
    }
  }
  skorlu.sort((a, b) => b.skor - a.skor);
  return skorlu.map((x) => x.e);
}

export const KAYIT_SAYISI = ARAMA_KAYDI.length;
