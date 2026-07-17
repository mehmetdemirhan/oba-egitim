# CLAUDE.md — OBA Eğitim projesi rehberi

Bu dosya, depo üzerinde çalışan ajanlar (Claude Code) içindir. Kısa, kritik
konvansiyonlar; ayrıntı için ilgili dokümanlara bakın.

## Mimari
- **Backend:** FastAPI (`appbackend/`), MongoDB (Motor/async). Render'da deploy.
- **Frontend:** React + CRA/craco (`frontend/`). Vercel'de deploy.
- **Çekirdek katman:** `appbackend/core/` → `config`, `db`, `auth`, `ai`, `sistem`,
  `patch_manager`, `patch_security`, `registry`. DB/kimlik/ayar/AI erişimi **daima
  core üzerinden** yapılır.
- **Modüller:** `appbackend/modules/<ad>.py`, her biri `router = APIRouter()` ihraç
  eder. `server.py` artık modülleri elle include ETMEZ; `core.registry.register_routers`
  `modules/registry.json` **sırasıyla** aktif modülleri dinamik yükler. Sıra route
  eşleşmesi için kritiktir (catch-all / duplicate yollar) — bozmayın.

## Modül / Yama sistemi
- Admin paneli **Modüller** sekmesi: ZIP yükle/güncelle/aç-kapa/sil/sürüme dön.
- Kod: `core/patch_manager.py` (kurulum, sürüm arşivi, rollback, sil),
  `core/patch_security.py` (AST güvenlik), `modules/admin_patch.py` (API),
  `frontend/src/components/ModulYonetimi.jsx` (UI).
- Çekirdek (kapatılamaz/silinemez): `yedekleme, auth_api, dashboard, bildirim,
  admin_patch, seed` (`core.registry.KORUMALI_MODULLER`).
- Sürüm arşivi: `appbackend/eski_versiyonlar/` (git'te yoksayılır), son 3 sürüm.
- Rehber: **`docs/MODUL_GELISTIRME.md`**, örnek paket: `docs/ornek_modul.zip`.

## Test
- Smoke testleri: `appbackend/tests/test_*_smoke.py`. Çalıştırma:
  `cd appbackend && .venv/Scripts/python.exe tests/test_<ad>_smoke.py`.
- Türkçe çıktı için Windows'ta `PYTHONIOENCODING=utf-8` kullanın (cp1254 hatası).
- Yama su'iti: `test_patch_smoke`, `test_patch_security_smoke`,
  `test_patch_version_smoke`, `test_patch_rollback_smoke`,
  `test_patch_registry_smoke`, `test_patch_e2e_smoke`.
- Route regresyonu: `python tests/route_snapshot.py` (toplam route sayısını verir).
- Modül smoke'ları `server.py`'den **kaldırılmış** sembollere değil, `modules.*`
  veya `core.*`'a bağlanmalı (registry migrasyonu re-export'ları kaldırdı).

## Konvansiyonlar
- Kod/yorum dili: mevcut dosyalardaki gibi **Türkçe** açıklamalar.
- **Tarih/zaman (KURAL):** Tarih üretimi **yalnız `core.zaman`** üzerinden — `simdi()`
  (aware UTC), `iso()` (aware UTC ISO string). **`datetime.utcnow()` YASAK** (naive üretir →
  "can't compare offset-naive and offset-aware datetimes" + sessiz yanlış hesap). İki tarihi
  karşılaştırmadan/çıkarmadan önce her iki tarafı `core.zaman.aware(x)` ile normalize et
  (naive → UTC varsayılır; Mongo kayıtları UTC'dir). `parse_from_mongo` okunan tarih alanlarını
  zaten aware UTC'ye çevirir (core/db.py).
- Büyük her adımdan sonra commit; commit mesajları Türkçe ve açıklayıcı.
- Frontend build doğrulaması: `cd frontend && CI=false npm run build` (react-scripts;
  Tailwind CRA'nın yerleşik desteğiyle `tailwind.config.js` üzerinden derlenir —
  craco KULLANILMIYOR, `cdn.tailwindcss.com` script'i YOK).
