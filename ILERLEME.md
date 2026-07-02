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

### 2026-07-02 (2) — Stemmer güçlendirme (madde 1 & 2 kısmen çözüldü)

`_turkce_kok` + `_tum_kelimeleri_cikar` iyileştirildi (`ai_bilgi_tabani.py`):
- **Ünsüz yumuşaması geri-döndürme** (`_sert_geri`): ünlü-başlı ek soyulunca
  b→p, c→ç, d→t, g/ğ→k (kitabından→kitap, sözcüğünü→sözcük, ağacından→ağaç).
- **Yeni ekler:** çoğul+hâl/araç zincirleri (lere/lara/lerden/lardan/lerle/larla/
  lerde/larda/lerdeki/lardaki/deki/daki) + iyelik-belirtme (ını/ini/unu/ünü).
  → sözcük/görsel/bisiklet aileleri artık tek köke iniyor.
- **Fragman + ğ-sonu elemesi:** `_KOK_FRAGMAN` (daki, mek, ları, lim…) ve
  `ğ` ile biten kökler (geldiğ, olduğ) havuza girmiyor.
- **Ölçüm (turkce_1_1.pdf):** 610 → **592 kök**; ≤3 harf gürültü 81 → 71.
- **Test:** `test_ai_egit_anlam_smoke.py` **34/34** (9 yeni stemmer kontrolü eklendi).

**Bilinçli SINIR (over-stem koruması):** Çıplak tek-ünlü belirtme eki (-ı/-i/-u/-ü)
kural-tabanlı SOYULMUYOR; çünkü `milli`→`mill`, `kutu`→`kut`, `sürücü`→`sürüç` gibi
gerçek kökleri kırardı (smoke `millî→milli` bunu koruyor). → Bu, aşağıdaki (3) adımda
kanıt-tabanlı olarak çözüldü.

### 2026-07-02 (3) — Kanıt-tabanlı çıplak çekim birleştirme (madde 2 tamam)

`_kanitli_kok_birlestir` + `_ciplak_adaylar` eklendi. Çıplak ünlü (-ı/-i/-u/-ü/-e/-a)
ve araç eki (-le/-la/-yle/-yla) yalnızca **soyulan hedef kök metinde bağımsız olarak
da geçiyorsa** birleştirilir:
- `kelebeği`+`kelebek`→`kelebek`, `büyüteci`/`büyüteçle`+`büyüteç`→`büyüteç`,
  `sözcüğe`/`sözcüğü`→`sözcük`, `kitaba`/`kitabı`→`kitap` (yumuşamayla).
- **Over-stem YOK:** hedef kanıtsızsa dokunulmaz — `milli`(mill yok), `cümle`(cüml
  yok), `sürücü`(sürüç yok) korunur. Kısa çift-kanıtlı biçimler (`kapı`≠`kap`) len<5
  guard'ıyla ayrı kalır.
- **Ölçüm (turkce_1_1.pdf):** 592 → **577 kök** (kümülatif 610→577).
- **Test:** `test_ai_egit_anlam_smoke.py` **38/38** (+4 kanıtlı-birleştirme kontrolü).

### 2026-07-02 (4) — PDF satır-sonu tireleme onarımı (madde 3 tamam)

`_pdf_metin_birlestir` eklendi (tokenize öncesi çağrılır):
- **Soft hyphen (U+00AD) + satır sonu:** kitapta 106 kez, hepsi tireleme →
  koşulsuz birleştirilir (`ör­\nnekteki`→`örnekteki`, `belir­\nleyerek`→`belirleyerek`).
- **Normal tire + satır sonu:** yalnızca tirenin önünde ≥2 küçük harf varsa
  (`içe-\nriklere`→`içeriklere`). Sözlük harf başlıkları (`-A-\namaç`) KORUNUR.
- `teki/taki` eki eklendi (`örnekteki`→`örnek`, `çiftlikteki`→`çiftlik`).
- Font mojibake (`÷`=ğ, 7 kez) ihmal edildi — tekil, sıklık filtresi eliyor.
- **Ölçüm (turkce_1_1.pdf):** 577 → **569 kök**; ≤3 harf gürültü 72 → 63.
- **Test:** `test_ai_egit_anlam_smoke.py` **43/43** (+5 tireleme kontrolü).

**Kümülatif sonuç (610 → 569 kök, ≤3 harf gürültü 81 → 63):** kitap kelime havuzu
tarama boru hattı temizlendi; kalan gürültü çoğunlukla tekil mojibake ve gerçek
kısa kelimelerle karışan birkaç fragman (`haf, met, nok, oyu, ın, ça`).

### Sıradaki mantıklı adım
- **Öncelik 1 (opsiyonel, düşük getiri):** Kalan kısa fragmanlar (`haf, met, nok,
  oyu, ın, ça`) — gerçek kısa kelimeleri (göz, söz, yol, kız…) BOZMADAN elemek zor;
  ancak istenirse elle küçük bir kara-liste genişletmesi yapılabilir.
- **Öncelik 2:** Havuz kalitesi artık iyi → asıl AI anlam üretimini (`_harita_anlam_uret`)
  gerçek kitapla uçtan uca (mock değil) bir kez çalıştırıp anlam/örnek kalitesini
  gözden geçirmek daha yüksek değerli olabilir.

## 2026-07-02 (5) — Puan/XP deflasyonu (tüm ödül puanları tek haneli)

Şişmiş puan totallerini önlemek için tüm **kazanılabilir** ödül değerleri monotonik
harita (`2→1, 3→2, 5→2, 8→3, 10→3, 15→4, 20→5, 25→5, 30→6, 35→6, 40→7, 50→7,
75→8, 100→9`) ile 1–9 aralığına indirildi. Değişen tanımlar:
- `core/sistem.py`: `XP_TABLOSU_DEFAULT`, `OGRETMEN_ROZETLERI_DEFAULT` (puan),
  `OGRENCI_ROZETLERI_DEFAULT` (xp), `VARSAYILAN_PUANLAR`, `OGRETMEN_PUAN_AGIRLIKLARI_DEFAULT`.
- `LIG_ESIKLERI_DEFAULT`: biriktirilen hedef olduğu için orantılı küçültüldü →
  bronz 0 / gümüş 20 / altın 50 / elmas 100 (kullanıcı onayı).
- Sabit-kodlanmış ödüller: `ilerleme.py` PUAN_* yedekleri, `ai_bilgi_tabani.py`
  `AI_EGITIM_PUANLARI`, `kitap.py` (15→4), `ai_uretim.py` adaptif hikaye xp (10→3),
  `diagnostic.py` yedek (10→3), `ai_kitap_zeka.py` oyun prompt örneği (10→7).
- **Test:** `test_ogretmen_basarilarim_smoke.py` beklenen XP'leri güncellendi;
  **tüm 23 smoke dosyası yeşil**, route 288 değişmedi.
- Not: Bunlar **varsayılan**; admin panelinden DB override'ı ile ayarlanabilir.
  Mevcut kullanıcıların birikmiş `puan/toplam_xp` totalleri geriye dönük değişmez
  (yalnızca bundan sonraki kazanımlar tek haneli).

## Bilinen teknik borç (kitap taramasından bağımsız)
- **`modules/auth_api.py` şifre sıfırlama** — (2026-07-02 çözüldü) Geçici şifre artık
  yalnızca `SIFRE_SIFIRLAMA_DEBUG=1` iken (lokal geliştirme) yanıtta döner; prod
  varsayılanında sızdırılmaz. Kalan iş: prod'da gerçek e-posta/SMS gönderimi
  (şu an prod'da kullanıcı geçici şifreyi göremez — altyapı bağlanmalı).
- **`modules/admin_debug.py:73`** — Gemini modellerini listeleyen endpoint "geçici
  public" (auth eksik).
