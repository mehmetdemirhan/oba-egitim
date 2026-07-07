"""Akıcı Okuma metinlerini ortak metin havuzuna (analiz_metinler) aktarır.

Kaynak: appbackend/data/akici_okuma_metinleri.json (150 metin).
Her metin, Giriş Analizi "Analiz Metni Seç" dropdown'ını besleyen aynı
`analiz_metinler` koleksiyonuna, durum="havuzda" olarak eklenir.

Alan eşleştirmesi:
  title        → baslik
  word_count   → seviye  (asıl SEVİYE göstergesi) + kelime_sayisi (senkron)
  body         → icerik
  mcqs[]       → sorular[]  (answer→dogru_cevap, answer_confidence→guven,
                             low ise kontrol_gerekli=True)
  open_questions → acik_sorular[]
  image_prompt → gorsel_prompt  (🔒 BACKEND-ONLY, hiçbir role gösterilmez)

- SINIF eşleştirmesi YAPILMAZ (sinif_seviyesi=None). Seviye = kelime sayısı.
- zorluk = core.metin_zorluk.zorluk_hesapla(body) — Kutulu Okuma zorluk rozeti/
  fallback'i için (sınıf değil, okunabilirlik sezgiseli).
- İdempotent: id = uuid5(NS, "akici_okuma:"+baslik) → sabit. Var olan kayıt
  $setOnInsert ile KORUNUR (öğretmen düzeltmeleri/görselleri ezilmez).

VARSAYILAN MOD = DRY-RUN. Uygulamak için: --apply

Çalıştırma (appbackend dizininden; MONGO_URL/DB_NAME ortamdan okunur):
  Önizleme:  .venv/Scripts/python.exe scripts/akici_okuma_import.py
  Uygula:    .venv/Scripts/python.exe scripts/akici_okuma_import.py --apply
Türkçe çıktı için Windows'ta: set PYTHONIOENCODING=utf-8
"""
import sys
import json
import uuid
import asyncio
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

APPLY = "--apply" in sys.argv

KAYNAK = "akici_okuma"
EKLEYEN_AD = "OBA Akıcı Okuma Havuzu"
# Sabit tarih (idempotent çıktı; sıralama tutarlı olsun)
SABIT_TARIH = "2026-07-07T00:00:00+00:00"
# Metin ID'leri için sabit isim uzayı (deterministik uuid5)
NS = uuid.UUID("a51c0000-0000-4000-8000-000000000001")

VERI_YOLU = Path(__file__).resolve().parent.parent / "data" / "akici_okuma_metinleri.json"


def _metin_id(baslik: str, word_count: int, body: str) -> str:
    # İçeriğe dayalı deterministik id: aynı başlık farklı gövde/seviye ile birden
    # fazla metin olabilir (ör. "Ormanda Macera" 69 ve 281 kelimelik iki ayrı metin).
    # title+word_count+body → farklı metinler ayrı id alır, birebir kopya deduplenir.
    return str(uuid.uuid5(NS, f"{KAYNAK}:{baslik}:{word_count}:{body}"))


def _soru_id(metin_id: str, i: int) -> str:
    return str(uuid.uuid5(NS, f"{metin_id}:soru:{i}"))


def _acik_id(metin_id: str, i: int) -> str:
    return str(uuid.uuid5(NS, f"{metin_id}:acik:{i}"))


def _doc_olustur(kayit: dict) -> dict:
    baslik = (kayit.get("title") or "").strip()
    body = kayit.get("body") or ""
    word_count = int(kayit.get("word_count") or 0)
    mid = _metin_id(baslik, word_count, body)

    from core.metin_zorluk import zorluk_hesapla
    from core.acik_soru import stringten_acik_soru

    sorular = []
    for i, m in enumerate(kayit.get("mcqs") or []):
        guven = (m.get("answer_confidence") or "high").lower()
        sorular.append({
            "id": _soru_id(mid, i),
            "soru": m.get("question", ""),
            "secenekler": m.get("options", {}) or {},
            "dogru_cevap": (m.get("answer") or "").strip().upper(),
            "dogru_cevap_kaynak": "otomatik",          # otomatik | manuel
            "guven": "low" if guven == "low" else "high",
            "kontrol_gerekli": guven == "low",          # düşük güven → öğretmen paneli bayrağı
            "ilk_duzelten_id": None,                    # XP anti-farm
            "son_duzelten_id": None,
            "son_duzelten_tarih": None,
        })

    return {
        "id": mid,
        "baslik": baslik,
        "icerik": body,
        "kelime_sayisi": word_count,
        "seviye": word_count,                 # asıl seviye göstergesi (= kelime sayısı)
        "sinif_seviyesi": None,               # SINIF eşleştirmesi yapılmaz
        "tur": "akici_okuma",
        "zorluk": zorluk_hesapla(body),       # Kutulu Okuma zorluk sezgiseli
        "durum": "havuzda",                   # küratörlü → doğrudan havuzda
        "kaynak": KAYNAK,
        "ekleyen_id": "sistem",
        "ekleyen_ad": EKLEYEN_AD,
        "oylar": {},
        "sorular": sorular,
        "acik_sorular": [
            stringten_acik_soru(_acik_id(mid, i), i + 1, q)
            for i, q in enumerate(kayit.get("open_questions") or [])
        ],
        "gorsel_prompt": kayit.get("image_prompt"),   # 🔒 backend-only
        "gorsel": None,                       # yüklenince prompt yerine bu gösterilir
        "gorsel_ilk_ekleyen_id": None,        # XP anti-farm
        "olusturma_tarihi": SABIT_TARIH,
        "yayin_tarihi": SABIT_TARIH,
    }


async def main():
    from core.db import db

    mod = "UYGULA (--apply)" if APPLY else "DRY-RUN (önizleme — hiçbir şey yazılmaz)"
    print("═══ AKICI OKUMA METİN İÇE AKTARIM ═══")
    print(f"  Mod: {mod}")
    print(f"  Kaynak: {VERI_YOLU}")

    if not VERI_YOLU.exists():
        print(f"  ✗ HATA: veri dosyası bulunamadı: {VERI_YOLU}")
        sys.exit(1)

    with open(VERI_YOLU, encoding="utf-8") as f:
        kayitlar = json.load(f)
    print(f"  Toplam kayıt: {len(kayitlar)}\n")

    sayac = {"eklendi": 0, "mevcut_korundu": 0, "bos_baslik": 0}
    toplam_mcq = toplam_dusuk = toplam_acik = 0
    for kayit in kayitlar:
        baslik = (kayit.get("title") or "").strip()
        if not baslik:
            sayac["bos_baslik"] += 1
            continue
        doc = _doc_olustur(kayit)
        toplam_mcq += len(doc["sorular"])
        toplam_dusuk += sum(1 for s in doc["sorular"] if s["kontrol_gerekli"])
        toplam_acik += len(doc["acik_sorular"])

        if APPLY:
            r = await db.analiz_metinler.update_one(
                {"id": doc["id"]},
                {"$setOnInsert": doc},
                upsert=True,
            )
            if r.upserted_id is not None:
                sayac["eklendi"] += 1
            else:
                sayac["mevcut_korundu"] += 1
        else:
            mevcut = await db.analiz_metinler.find_one({"id": doc["id"]}, {"_id": 1})
            if mevcut:
                sayac["mevcut_korundu"] += 1
            else:
                sayac["eklendi"] += 1

    print("─── ÖZET ───")
    print(f"  {'Eklenecek' if not APPLY else 'Eklenen'} yeni metin : {sayac['eklendi']}")
    print(f"  Zaten var (korunur)       : {sayac['mevcut_korundu']}")
    print(f"  Boş başlık (atlandı)      : {sayac['bos_baslik']}")
    print(f"  Toplam MCQ                : {toplam_mcq}  (düşük güven / kontrol: {toplam_dusuk})")
    print(f"  Toplam açık soru          : {toplam_acik}")
    if not APPLY:
        print("\n  ⚠  DRY-RUN: hiçbir şey yazılmadı. Uygulamak için: --apply")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
