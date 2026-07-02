# İlerleme Notları — OBA Eğitim

Bu dosya, üzerinde çalışılan işlerin durumunu ve sıradaki adımları tutar.
(Kod yapısı/geçmiş için git log'a bakın; burası "ne yarım kaldı, sırada ne var" notudur.)

## Aktif iş: Kitap kelime taraması (PDF → temiz kelime havuzu)

**Amaç:** Yüklenen ders kitabı PDF'inden gürültüsüz benzersiz kelime kökleri
çıkarıp `meb_kelime_haritasi`'na eklemek; sonra AI ile anlam üretmek.

**Kod:** `appbackend/modules/ai_bilgi_tabani.py` → `_tum_kelimeleri_cikar`,
`_turkce_kok`, `_STOPWORDS`. Smoke: `tests/test_ai_egit_anlam_smoke.py` (25/25).

**Son commit'ler:** b747fc6 (kümülatif sınıf) → f51debf (stemming) →
cda42d2 (kalite filtreleri) → 3d07539 (iyelik/belirtme/yönelme eki) →
a49ed9e (stopword + şapkalı harf).

### 2026-07-02 — Gerçek kitapta uçtan uca doğrulama (turkce_1_1.pdf, 1. sınıf)

94 KB metin / 6784 token → **610 benzersiz kök** çıktı. Havuz büyük ölçüde
doğru ama **üç tür gürültü** hâlâ sızıyor (bir sonraki iyileştirmenin hedefi):

1. **Ek parçaları / aşırı köklenme** (anlamsız kökler):
   `daki, den, nin, nın, lim, lım, rum, relim, yelim, yalım, rek, me, mek, mak,
   ma, ça, cik, cık, gi, ta, ör, oyu, met`
   → `_turkce_kok` bazı kelimeleri fazla kesiyor veya ek fragmanı kök sanıyor.

2. **Birleşmeyen çekimli formlar** (aynı kelime birden çok kök olarak kalıyor):
   `ad/adı/adını/adım`, `anlam/anlamlı/anlamın/anlamını`,
   `sözcük/sözcüğe/sözcüğü/sözcüğün/sözcüklere/sözcüklerle`,
   `bisiklet/bisikleti/bisikletin/bisikletle`, `görsel/görseli/görselini/görsellerdeki`,
   `büyüteç/büyüteci/büyüteçle`, `gökyüzü/gökyüzüne/gökyüzünü`, `tasarla*` (7+ form).
   → Stemmer iyelik+hâl eki zincirlerini ve yumuşama (ç→c, k→ğ) sonrası formları
   tam indirgemiyor.

3. **PDF satır/sütun kırılmasından gelen kesik tokenlar:**
   `nekteki` (örnekteki), `hika` (hikâye), `metn, geldiğ, varl, şekl, hakk, duma,
   sıras, rüyas, aras, leyerek`
   → Tokenizer öncesi PDF metninde tireleme/satır sonu birleştirme yok.

**Doğrulama scripti (tek seferlik, repoya girmedi):** fitz ile PDF metni çıkarıp
`_tum_kelimeleri_cikar`'a verir, kök sayısı + kısa/şüpheli kök listesi raporlar.

### Sıradaki mantıklı adım
- **Öncelik 1:** Stemmer'ı yukarıdaki 2. maddeye göre güçlendir (iyelik+hâl eki
  zinciri + ünsüz yumuşaması geri-döndürme) ve 1. maddedeki fragman köklere karşı
  bir "geçerli kök" beyaz/kara listesi veya min-uzunluk+ek-sözlüğü kontrolü ekle.
  Her değişiklikte `test_ai_egit_anlam_smoke.py` yeşil kalmalı.
- **Öncelik 2:** PDF metnini tokenize etmeden önce satır sonu tireleme/kırılma
  birleştirme (3. madde) — kesik tokenları azaltır.

## Bilinen teknik borç (kitap taramasından bağımsız)
- **`modules/auth_api.py` şifre sıfırlama** — (2026-07-02 çözüldü) Geçici şifre artık
  yalnızca `SIFRE_SIFIRLAMA_DEBUG=1` iken (lokal geliştirme) yanıtta döner; prod
  varsayılanında sızdırılmaz. Kalan iş: prod'da gerçek e-posta/SMS gönderimi
  (şu an prod'da kullanıcı geçici şifreyi göremez — altyapı bağlanmalı).
- **`modules/admin_debug.py:73`** — Gemini modellerini listeleyen endpoint "geçici
  public" (auth eksik).
