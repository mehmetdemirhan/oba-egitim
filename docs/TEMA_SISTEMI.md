# OBA Tema / Görünüm Sistemi

Veri-odaklı tema sistemi: renkler artık koda gömülü değil, **CSS değişkeni token'ları**
üzerinden yönetilir. Temalar `theme_configs` koleksiyonunda durur; her tema `light`
ve `dark` modu için 12 semantik token içerir. Dark mode + `auto` (sistem tercihi)
desteklenir. Admin panelden tam CRUD + logo yükleme yapılır.

> **OgrenciPaneli cream paleti korunmuştur** — migrate edilmedi; `ogrenci_cream`
> teması öğrenci rolünün varsayılanıdır.

---

## 1. Mimari

```
core/tema_varsayilan.py   → 5 hazır tema (light+dark, 12 token) — tek doğruluk kaynağı
modules/tema.py           → /tema/* API (okuma+çözümleme + admin CRUD + logo)
scripts/seed_temalar.py   → theme_configs seed (idempotent)

frontend/src/index.css              → :root (light) + .dark token blokları (fallback)
frontend/tailwind.config.js         → semantik renk aliasları (bg-primary, bg-surface…)
frontend/src/context/ThemeContext.jsx → useTheme, CSS var enjeksiyonu, cache, auto
frontend/src/components/tema/*.jsx  → ThemeToggle, TemaYonetimi, TemaKarti, TemaFormu…
frontend/src/components/Logo.jsx    → merkezî marka logosu
```

**12 Token:** `primary, primary_hover, secondary, background, surface, text,
text_secondary, border, accent, danger, success, warning`.

**Semantik Tailwind class'ları** (migration hedefi):
`bg-primary` `hover:bg-primary-hover` `text-primary` `bg-surface` `bg-app`
`text-content` `text-subtle` `border-line` `bg-danger/success/warning`.

**Koleksiyonlar:**
- `theme_configs` — tema tanımları (`kod` unique). Şema:
  ```json
  {"kod":"deniz","ad":"Deniz Mavisi","aciklama":"…","kategori":"hazir",
   "hedef_rol":null,"modlar":{"light":{...12 token},"dark":{...12 token}}}
  ```
- `users.tema_tercihi` — `{tema_kodu, mod, otomatik_gecis_saati}`
- `sistem_ayarlari` (tip `tema_ayarlari`) — `{aktif_tema, logo_url}`

---

## 2. Tema Çözümleme (Öncelik)

```
kullanıcı tercihi (users.tema_tercihi.tema_kodu)
        ↓ yoksa
rol varsayılanı (ROL_VARSAYILAN_TEMA — öğrenci → ogrenci_cream)
        ↓ yoksa
sistem varsayılanı (sistem_ayarlari.tema_ayarlari.aktif_tema)
        ↓ yoksa
"deniz" (fallback)
```

`mod` çözümlemesi: `light` / `dark` doğrudan; `auto` → `prefers-color-scheme`.

Frontend `ThemeContext`:
1. Mount'ta localStorage cache'ten anında uygular (FOUC yok).
2. Login sonrası `GET /tema/aktif` ile backend'den çözümlenmiş temayı çeker.
3. Token'ları `document.documentElement.style.setProperty("--primary", …)` ile uygular,
   `.dark` sınıfını ve `data-theme`/`data-mode` attribute'larını ayarlar.
4. `auto` iken `matchMedia` değişimini dinler.

---

## 3. Hazır Temalar

| Kod | Ad | Birincil | Kategori |
|---|---|---|---|
| `deniz` | Deniz Mavisi | `#2563EB` | hazır (**sistem varsayılanı**) |
| `orman` | Orman Yeşili | `#059669` | hazır |
| `gun_batimi` | Gün Batımı | `#F97316` | hazır (marka rengi) |
| `gece_yarisi` | Gece Yarısı | `#7C3AED` | hazır |
| `ogrenci_cream` | Öğrenci Cream | `#F59E0B` | rol_default (öğrenci) |

Nötr token'ların (background/surface/text/border) **light değerleri mevcut gri
iskeletle eşleşir** → migration sonrası light görünüm değişmez.

---

## 4. Admin Panelden Kullanım

**Admin → 🎨 Tema** sekmesi (`TemaYonetimi`):
- **+ Yeni Tema:** kod, ad, kategori + light/dark için 12 renk (renk picker + canlı önizleme).
- **Kart → Düzenle / Sil / Sistem aktif yap.** Karta tıklayınca **kendi ekranında canlı önizlenir.**
- **Logo Yükle** (PNG/JPG/SVG/WebP → `/uploads/logo/`).
- **JSON İndir / Yükle** (yedek/aktarım).
- Hazır/rol-varsayılan temalar **silinemez**.

**Her kullanıcı** (admin/öğretmen/veli) header'daki **ThemeToggle**'dan görünüm
modunu (açık/koyu/otomatik) ve temayı seçer; tercih backend'e + localStorage'a yazılır.
(Öğrenci paneli cream kuralı gereği toggle içermez; rol varsayılanı uygulanır.)

---

## 5. API Referansı (`/api/tema/*`)

| Method | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/tema/hazir` | herkes | Hazır + rol-default temalar |
| GET | `/tema/aktif` | auth | Kullanıcının çözümlenmiş teması + mod |
| GET | `/tema/{kod}` | herkes | Tek tema |
| GET | `/tema/kullanici/tercih` | auth | Kullanıcı tercihi |
| POST | `/tema/kullanici/tercih` | auth | Tercih kaydet (`{tema_kodu, mod}`) |
| GET | `/tema/tumu` | admin | Tüm temalar + sistem aktif |
| POST | `/tema` | admin | Yeni özel tema |
| PUT | `/tema/{kod}` | admin | Güncelle |
| DELETE | `/tema/{kod}` | admin | Sil (hazır/rol-default hariç) |
| POST | `/tema/aktif-yap/{kod}` | admin | Sistem varsayılanı ayarla |
| POST | `/tema/logo` | admin | Logo yükle (multipart) |
| GET | `/tema/export` · POST `/tema/import` | admin | JSON yedek/aktarım |

---

## 6. Kurulum / Migration (Üretim)

`appbackend` dizininden (idempotent):
```bash
.venv/Scripts/python.exe scripts/seed_temalar.py   # 5 hazır temayı theme_configs'e yazar
```
- `ensure_indexes()` startup'ta `theme_configs {kod}` unique index'ini garanti eder.
- Seed çalışmasa bile backend `core.tema_varsayilan` fallback'i ile çalışır.
- Frontend `index.css`'teki `:root` deniz light değerleri, backend erişilemezse bile
  arayüzü mevcut görünümde tutar.

---

## 7. Yeni Tema / Token Ekleme

- **Yeni tema:** Admin panel → + Yeni Tema (veya `POST /tema`). Kod değişmez, 12 token
  light+dark doldurulur. Hiç kod değişikliği gerekmez.
- **Yeni token (ör. `--info`):** (a) `core/tema_varsayilan.TOKEN_ALANLARI`'na ekle,
  (b) tüm temaların `modlar.light/dark`'ına değer ver, (c) `index.css` `:root`/`.dark`'a
  fallback ekle, (d) `tailwind.config` colors'a alias, (e) `TemaFormu.TOKENLAR`'a ekle.

---

## 8. Test Süiti

| Test | Kapsam |
|---|---|
| `tests/test_tema_crud_smoke.py` | CRUD, çözümleme, auth, silme kuralları (19/19) |
| `tests/test_tema_e2e_smoke.py` | Çözümleme zinciri + logo + backward-compat (10/10) |

Çalıştırma: `cd appbackend && .venv/Scripts/python.exe tests/test_tema_<ad>_smoke.py`
(Windows'ta `PYTHONIOENCODING=utf-8`).

---

## 9. Bilinen Kısıtlamalar

- **Migration kapsamı:** App.js'te ~1319 nötr/birincil renk class'ı token'a çevrildi
  (bkz. `docs/TEMA_MIGRATION.md`). İçerik-özel renkler (gamification bölgeleri, AI karakter
  renkleri, rozet seviyeleri) ve `components/` altındaki bileşenler token'a taşınmadı;
  light modda görünmez, dark modda küçük tutarsızlıklar kalabilir (sonraki iterasyon).
- **OgrenciPaneli** bilinçli olarak migrate edilmedi (cream paleti korundu).
- **Tailwind Play CDN** (`index.html`) hâlâ yüklü; token'lar derlenen Tailwind'den gelir.
  Üretim için CDN'in kaldırılması ayrı bir iyileştirme adımıdır.
