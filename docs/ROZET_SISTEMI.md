# OBA Rozet Sistemi (v2 — Veri-Odaklı)

Bu doküman, yenilenen rozet sisteminin mimarisini, event akışını, yeni metrik
ekleme adımlarını, API referansını ve üretim migrasyon talimatını içerir.

> Özet: Rozet **tanımları** artık koda gömülü değil, `rozetler` koleksiyonunda
> veri olarak durur. **Koşullar** `metrik / operator / eşik` üçlüsüyle (ve bileşik
> `ve` listesiyle) tanımlanır. Ödüller hem **event-driven** (okuma/görev/kur) hem
> de pull (`POST /rozetler/kontrol`) yoluyla verilir. Kazanımda **bildirim** gider.

---

## 1. Mimari ve Katmanlar

```
core/
  rozet_kosullari.py   → Koşul haritaları (metrik/operator/eşik) — TEK doğruluk kaynağı
  rozet_helpers.py     → odul_puan normalizasyonu, puan haritası, bildirim gönder
  rozet_motor.py       → Metrik hesaplama + koşul değerlendirme + ödül/bildirim
  db.py                → ensure_indexes() (unique index'ler)
modules/
  rozet.py             → Yönetim API'si (/rozet/*) — CRUD, manuel ver, istatistik
  ilerleme.py          → Eski /rozetler/* (geriye dönük) + kur/atla event tetikleyici
  ogrenci_panel.py     → Okuma kaydı event tetikleyici
  gorev.py             → Görev tamamlama event tetikleyici
scripts/
  migrate_rozet_faz1.py → Temizlik + alan adı + unique index
  migrate_rozetler.py   → Kod tanımlarını 'rozetler' koleksiyonuna taşır
```

**Koleksiyonlar**
- `rozetler` — rozet TANIMLARI. Kimlik: `(rol, kod)` (kod tek başına benzersiz
  değildir; `gorev_ilk`/`egz_ilk` hem öğretmen hem öğrencide vardır).
- `kazanilan_rozetler` — KAZANIMLAR: `{id, kullanici_id, rozet_kodu, kazanma_tarihi}`.
  Kimlik: `(kullanici_id, rozet_kodu)` unique.

**Rozet tanım şeması**
```json
{
  "kod": "okuma_100", "rol": "student",
  "ad": "Kitap Kurdu", "aciklama": "…", "ikon": "🐛",
  "renk": null, "kategori": "okuma", "seviye": "gumus",
  "odul_puan": 4, "aktif": true, "sira": 1,
  "kosul": {"metrik": "okuma_dakikasi", "operator": ">=", "esik": 100,
             "ve": [ {"metrik": "...", "operator": ">=", "esik": 0} ]}
}
```
`kosul.ve` opsiyoneldir; tüm alt koşullar **AND** ile bağlanır. Manuel rozet:
`{"metrik": "manuel", "operator": null, "esik": null}` — otomatik verilmez.

---

## 2. Event Akışı

```
Öğrenci okuma kaydı ekler (POST /api/reading-logs)
        │
        ├─ reading_logs.insert
        └─ asyncio.create_task( rozet_tetikle(user_id, "okuma_kaydi") )   ← fire-and-forget
                 │
                 └─ rozet_degerlendir(user_id)
                        1. user + rol çöz
                        2. kazanilan_rozetler → mevcut kodlar
                        3. aktif_tanimlar(rol)  (db.rozetler; yoksa kod fallback)
                        4. kullanici_metrikleri(user_id, rol)  ← TÜM metrikler tek geçişte
                        5. her tanım: koşul sağlanıyor & kazanılmamışsa →
                              insert + rozet_bildirim_gonder + listeye ekle
```

**Bağlı event tetikleyicileri**

| Event | Nerede | Kimi değerlendirir |
|---|---|---|
| Okuma kaydı | `ogrenci_panel.py` `POST /reading-logs` | Öğrenci (okuma/kitap/streak/orman) |
| Görev tamamlama | `gorev.py` `PUT /gorevler/{id}/durum` | Hedef öğrenci + atayan öğretmen |
| Kur atlatma | `ilerleme.py` `POST /kur/atla` | Öğretmen (kur_*) |
| Pull (dashboard) | `POST /rozetler/kontrol` | Giriş yapan kullanıcının tümü |

> Pull yolu (`/rozetler/kontrol`) her şeyin **nihai garantisidir**: event bağlı
> olmayan öğretmen rozetleri (içerik, oy, veli anketi, mesaj, gelişim) dashboard
> yüklemesinde değerlendirilir.

**Bilinen boşluklar (mevcut sistemden devralındı):**
- `egzersiz_*` rozetleri: `egzersiz_tamamlama` koleksiyonunu **hiçbir endpoint
  yazmıyor** (yalnızca seed). Metrik hazır; yazan uç eklenince otomatik çalışır.
- `giris_serisi` (streak) **okuma tarihinden** türetilir; login event'i etkilemez.
  Bu yüzden login'e tetikleyici bağlanmadı (gereksiz olurdu).

---

## 3. Yeni Metrik Nasıl Eklenir?

1. **Metriği hesapla:** `core/rozet_motor.py` içindeki `_ogretmen_metrikleri`
   veya `_ogrenci_metrikleri` fonksiyonuna yeni anahtarı ekle:
   ```python
   return { ..., "yeni_metrik": <hesap> }
   ```
2. **Açıklama ekle:** `core/rozet_kosullari.py` `METRIK_ACIKLAMALARI`'na bir satır.
3. **(Ops.) Frontend dropdown:** `components/rozet/RozetFormu.jsx` `METRIKLER`
   listesine ekle (admin formunda seçilebilsin).
4. **Rozeti tanımla:** Admin panel → Rozetler → + Yeni Rozet (koşul = yeni_metrik),
   veya `scripts` ile `rozetler` koleksiyonuna ekle.
5. **(Ops.) Event tetikleyici:** Metriği değiştiren endpoint'e
   `asyncio.create_task(rozet_tetikle(user_id, "event_adi"))` ekle.

> Not: Yeni metrik hiçbir motor kod değişikliği olmadan sadece **veri** olarak da
> yaşayamaz — metrik değerini üreten Python fonksiyonu gerekir. Eşik/operator/rozet
> ise tamamen veridir (koda dokunmadan admin panelinden değişir).

---

## 4. Admin Panelinden Kullanım

**Admin → 🏅 Rozetler** sekmesi (`RozetYonetimi`):
- **+ Yeni Rozet:** kod, rol, ad, ikon, kategori, seviye, ödül puanı, koşul
  (metrik + operator + eşik), aktif, sıra.
- **Karta tıkla → Düzenle:** aynı form; kod/rol sabittir.
- **Kazananlar:** listeler; manuel ver (kullanıcı ID) / geri al.
- **Sil:** "kazanımları da sil" seçeneğiyle (yalnız o roldeki kazanımlar).
- **JSON İndir / Yükle:** toplu yedek / aktarım.
- **İstatistik:** tanım/aktif/kazanım sayıları, en yaygın/en nadir rozet.

Bileşik (AND) koşulları form tek satır düzenler; çok koşullu rozetler için
**JSON Yükle** kullanın (`kosul.ve` listesi).

---

## 5. API Referansı

### Yeni yönetim API'si (`/api/rozet/*`)
| Method | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/rozet/tanim?rol=` | herkes | Tüm tanımlar (rol filtresi ops.) |
| GET | `/rozet/{rol}/{kod}` | herkes | Tek tanım |
| POST | `/rozet/tanim` | admin | Yeni rozet |
| PUT | `/rozet/{rol}/{kod}` | admin | Güncelle |
| DELETE | `/rozet/{rol}/{kod}` | admin | Sil (`{kazananlari_koru}`) |
| GET | `/rozet/{rol}/{kod}/kazananlar` | admin | Kazananlar listesi |
| POST | `/rozet/{rol}/{kod}/ver` | admin | Manuel ver (`{user_id}`) + bildirim |
| POST | `/rozet/{rol}/{kod}/geri-al` | admin | Kazanımı geri al (`{user_id}`) |
| GET | `/rozet/ogrenci/{ogrenci_id}` | auth | Çocuğun vitrini (veli/öğretmen) |
| GET | `/rozet/istatistik` | admin | Kazanan sayıları + özet |
| GET | `/rozet/export` | admin | JSON dışa aktar |
| POST | `/rozet/import` | admin | JSON içe aktar (upsert) |

### Geriye dönük (`/api/rozetler/*`, ilerleme.py) — KORUNDU
| Method | Yol | Açıklama |
|---|---|---|
| GET | `/rozetler/tanim` | `{ogretmen, ogrenci}` (kod defaults) |
| GET | `/rozetler/{user_id}` | Kullanıcının kazandıkları |
| POST | `/rozetler/kontrol` | Motoru çağırır (pull değerlendirme) |

---

## 6. Üretim Migrasyon Talimatı

Sıra önemlidir. `appbackend` dizininden:

```bash
# 1) FAZ 1 — temizlik + alan adı + unique index (idempotent)
.venv/Scripts/python.exe scripts/migrate_rozet_faz1.py

# 2) FAZ 2 — kod tanımlarını 'rozetler' koleksiyonuna taşı (idempotent)
.venv/Scripts/python.exe scripts/migrate_rozetler.py
```

- Her iki script **idempotent**tir; tekrar çalıştırmak güvenlidir.
- `migrate_rozetler.py` mevcut kayıtların elle düzenlenmiş alanlarını (aktif,
  odul_puan, kosul) **korur**, yalnız eksikleri tamamlar.
- Startup'ta `ensure_indexes()` otomatik çalışır (server.py) — index'ler garanti.
- Migration çalışmasa bile motor **kod fallback** ile çalışır; migration sadece
  admin panelinden yönetimi (CRUD) aktif eder.

---

## 7. Test Süiti

| Test | Kapsam |
|---|---|
| `tests/test_rozet_faz1_smoke.py` | Temizlik, unique index, bildirim, helper |
| `tests/test_rozet_motor_smoke.py` | Metrikler, koşullar, veri-odaklı/fallback, event |
| `tests/test_rozet_crud_smoke.py` | Yönetim API'si (CRUD, ver/geri-al, import/export) |
| `tests/test_rozet_e2e_smoke.py` | 4 rol uçtan uca (event → ödül → bildirim → veli) |
| `tests/test_rozet_performans_smoke.py` | 100 kullanıcı ölçüm (~45 ms/kullanıcı) |

Çalıştırma: `cd appbackend && .venv/Scripts/python.exe tests/test_rozet_<ad>_smoke.py`
(Windows'ta `PYTHONIOENCODING=utf-8`).
