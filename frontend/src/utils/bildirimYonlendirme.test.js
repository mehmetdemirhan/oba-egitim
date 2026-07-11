import { bildirimYonlendir, TUR_HEDEF } from "./bildirimYonlendirme";

describe("bildirimYonlendir — tür → hedef eşlemesi", () => {
  test("görev türleri Görevler'e gider (admin)", () => {
    for (const tur of ["gorev_atandi", "gorev_hatirlatma", "gorev_tamamlandi"]) {
      expect(bildirimYonlendir(tur, "admin")).toEqual({ hedef: "gorevler", sekme: "gorevler" });
    }
  });

  test("kur geçişi/alacak → admin'de Muhasebe (payments)", () => {
    expect(bildirimYonlendir("kur_gecisi", "admin")).toEqual({ hedef: "muhasebe", sekme: "payments" });
  });

  test("geciken kur / risk → öğrenci hedefi; admin muhasebe, öğretmen öğrenci-detay", () => {
    expect(bildirimYonlendir("kur_gecikme", "admin")).toEqual({ hedef: "ogrenci", sekme: "payments" });
    expect(bildirimYonlendir("risk_yuksek", "teacher")).toEqual({ hedef: "ogrenci", sekme: "ogrenci-detay" });
  });

  test("mesaj → Mesajlar", () => {
    expect(bildirimYonlendir("mesaj_geldi", "teacher")).toEqual({ hedef: "mesajlar", sekme: "mesajlar" });
  });

  test("eşlemesi olmayan türler → null (kırılmaz, yalnız okundu)", () => {
    for (const tur of ["streak_kirildi", "rozet_kazandi", "lig_yukseldi", "anket_hatirlatma", "haftalik_ozet", "bilinmeyen_tur"]) {
      expect(bildirimYonlendir(tur, "admin")).toBeNull();
    }
  });
});

describe("bildirimYonlendir — yetkisiz hedefe yönlendirme YOK", () => {
  test("koordinatör muhasebeye gidemez (payments erişimi yok) → null", () => {
    expect(bildirimYonlendir("kur_gecisi", "coordinator")).toBeNull();
  });

  test("öğrenci/veli muhasebeye gidemez → null", () => {
    expect(bildirimYonlendir("kur_gecisi", "student")).toBeNull();
    expect(bildirimYonlendir("kur_gecisi", "parent")).toBeNull();
  });

  test("öğrenci öğrenci-hedefli bildirimde yönlenmez (kendi detayı yok) → null", () => {
    expect(bildirimYonlendir("risk_yuksek", "student")).toBeNull();
  });

  test("bilinmeyen rol → null", () => {
    expect(bildirimYonlendir("gorev_atandi", "uzayli")).toBeNull();
  });

  test("veli öğrenci-hedefli bildirimde okumalar sekmesine gider (erişebildiği)", () => {
    expect(bildirimYonlendir("rapor_tamamlandi", "parent")).toEqual({ hedef: "ogrenci", sekme: "okumalar" });
  });
});

describe("kapsam kontrolü", () => {
  test("her eşlenen tür bilinen bir semantik hedefe işaret eder", () => {
    const gecerli = new Set(["gorevler", "muhasebe", "ogrenci", "mesajlar"]);
    for (const h of Object.values(TUR_HEDEF)) expect(gecerli.has(h)).toBe(true);
  });
});
