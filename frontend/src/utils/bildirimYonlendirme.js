// Bildirim tıklama → yönlendirme eşlemesi (saf/testlenebilir).
//
// İki katman:
//  1) TUR_HEDEF: bildirim türü → SEMANTİK hedef (rolden bağımsız niyet).
//  2) ROL_HARITA: her rolün o semantik hedef için ERİŞEBİLDİĞİ gerçek sekme adı.
//     null → rol bu hedefe erişemez → YÖNLENDİRME YAPMA (yalnız okundu işaretle).
//
// Böylece kullanıcının erişemeyeceği sekmeye asla yönlendirme yapılmaz
// (ör. koordinatör/öğrenci → muhasebe = null).

export const TUR_HEDEF = {
  // Görevler
  gorev_atandi: "gorevler",
  gorev_hatirlatma: "gorevler",
  gorev_tamamlandi: "gorevler",
  // Muhasebe / alacak
  kur_gecisi: "muhasebe",   // "Kur Geçişi — Yeni Alacak"
  // Öğrenci-hedefli (geciken kur / risk / rapor / ders değişikliği)
  kur_gecikme: "ogrenci",   // "Kur Süresi Aşıldı"
  risk_yuksek: "ogrenci",
  rapor_tamamlandi: "ogrenci",
  ders_degisiklik: "ogrenci",
  // Mesajlar
  mesaj_geldi: "mesajlar",
  // AI CEO — Ayda (admin) / Miran + mektup (öğretmen)
  ai_ceo_haftalik: "ai_ceo",
  ai_ceo_anomali: "ai_ceo",
  ai_ceo_mektup: "kocum_miran",
  ai_ceo_miran: "kocum_miran",
  // Eşlemesi OLMAYANLAR (streak_*, rozet_kazandi, lig_yukseldi, anket_hatirlatma,
  // haftalik_ozet) → burada yok → null döner → yalnız okundu işaretlenir.
};

// Semantik hedef → o roldeki gerçek sekme adı (yoksa null = erişim yok).
export const ROL_HARITA = {
  admin: { gorevler: "gorevler", mesajlar: "mesajlar", muhasebe: "payments", ogrenci: "payments", ai_ceo: "ai-ceo", kocum_miran: null },
  coordinator: { gorevler: "gorevler", mesajlar: "mesajlar", muhasebe: null, ogrenci: "students", ai_ceo: null, kocum_miran: null },
  teacher: { gorevler: "gorevler", mesajlar: "mesajlar", muhasebe: "ogrenci-detay", ogrenci: "ogrenci-detay", ai_ceo: null, kocum_miran: "kocum-miran" },
  accountant: { gorevler: null, mesajlar: null, muhasebe: "muhasebe", ogrenci: "muhasebe" },
  student: { gorevler: "gorevler", mesajlar: "mesajlar", muhasebe: null, ogrenci: null },
  parent: { gorevler: "gorevler", mesajlar: "mesajlar", muhasebe: null, ogrenci: "okumalar" },
};

/**
 * Bir bildirim türü + kullanıcı rolü için yönlendirme çözümle.
 * @returns {{hedef: string, sekme: string} | null} null → yönlendirme yok (yalnız okundu).
 */
export function bildirimYonlendir(tur, rol) {
  const hedef = TUR_HEDEF[tur];
  if (!hedef) return null; // eşlemesiz tür → kırılmasın, sadece okundu
  const harita = ROL_HARITA[rol] || {};
  const sekme = harita[hedef];
  if (!sekme) return null; // rol bu hedefe erişemez → yönlendirme yok
  return { hedef, sekme };
}
