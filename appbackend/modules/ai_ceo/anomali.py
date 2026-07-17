"""AI CEO — Kural bazlı anomali uyarıları (AI YOK, deterministik).

Tahsilat düşüşü, giriş azalması, geciken kur birikimi → kırmızı "dikkat" kartı + admin
bildirimi. Eşikler tek yerde; yeni kural eklemek kolay.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole

from .fotograf import son_fotograf
from .ortak import metrik_al

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Eşikler
ESIK_TAHSILAT_DUSUS = 20.0     # % — son ay bir önceki aya göre bu kadar düşerse
ESIK_GIRIS_DUSUS = 30.0        # % — son 7 gün bir önceki 7 güne göre
ESIK_GECIKEN_KUR = 10          # adet — geciken kur bu sayıyı aşarsa


def _yuzde_dusus(onceki, simdi) -> float | None:
    try:
        onceki = float(onceki); simdi = float(simdi)
        if onceki <= 0:
            return None
        return round((onceki - simdi) * 100 / onceki, 1)
    except (TypeError, ValueError):
        return None


def anomalileri_hesapla(fotograf: dict) -> list:
    """Fotoğraftan kural bazlı anomalileri üretir."""
    if not fotograf:
        return []
    uyarilar = []

    # 1) Tahsilat düşüşü (son 3 ay trendinden son iki ay)
    trend = metrik_al(fotograf, "muhasebe.tahsilat_trendi_son3ay", {}) or {}
    aylar = sorted(trend.items())
    if len(aylar) >= 2:
        dusus = _yuzde_dusus(aylar[-2][1], aylar[-1][1])
        if dusus is not None and dusus >= ESIK_TAHSILAT_DUSUS:
            uyarilar.append({
                "tip": "tahsilat_dususu", "seviye": "kritik",
                "mesaj": f"Tahsilat son ay %{dusus} düştü ({aylar[-2][0]}→{aylar[-1][0]}).",
                "deger": dusus,
            })

    # 2) Geciken kur birikimi
    geciken = metrik_al(fotograf, "ogretmen.geciken_kur_sayisi", 0) or 0
    if geciken >= ESIK_GECIKEN_KUR:
        uyarilar.append({
            "tip": "geciken_kur_birikimi", "seviye": "orta",
            "mesaj": f"{geciken} kur 35 günlük hedefi aştı — tahsilat/tamamlama riski.",
            "deger": geciken,
        })

    # 3) Giriş azalması (envanter: aktivite/log koleksiyonlarının son 7 gün toplamı)
    env = metrik_al(fotograf, "envanter.koleksiyonlar", {}) or {}
    son7 = sum((o.get("son_7gun") or 0) for o in env.values() if isinstance(o, dict))
    son30 = sum((o.get("son_30gun") or 0) for o in env.values() if isinstance(o, dict))
    if son30 > 0:
        beklenen_haftalik = son30 / 4.0
        dusus = _yuzde_dusus(beklenen_haftalik, son7)
        if dusus is not None and dusus >= ESIK_GIRIS_DUSUS:
            uyarilar.append({
                "tip": "giris_azalmasi", "seviye": "orta",
                "mesaj": f"Son 7 gün sistem hareketi beklenene göre %{dusus} düşük.",
                "deger": dusus,
            })

    # NPS düşüşü (S6d): NPS negatifse (detractor ağırlıklı) uyarı
    nps = metrik_al(fotograf, "nps.nps", None)
    nps_sayi = metrik_al(fotograf, "nps.sayi", 0) or 0
    if nps is not None and nps_sayi >= 3 and nps < 0:
        uyarilar.append({"tip": "nps_dususu", "seviye": "orta",
                         "mesaj": f"NPS negatif ({nps}) — memnuniyet riski, çıkış nedenlerini incele.",
                         "deger": nps})

    # 4) Konsantrasyon riski (S6c): tek öğretmen/tür bağımlılığı eşik aşımı
    kons = metrik_al(fotograf, "konsantrasyon", {}) or {}
    esik = kons.get("esik_yuzde", 25.0)
    for anahtar, etiket in (("en_buyuk_ogretmen_ogrenci_payi", "Tek öğretmen öğrenci payı"),
                            ("en_buyuk_ogretmen_gelir_payi", "Tek öğretmen gelir payı"),
                            ("en_buyuk_tur_payi", "Tek eğitim türü payı")):
        v = kons.get(anahtar)
        if v is not None and v > esik:
            uyarilar.append({"tip": "konsantrasyon_riski", "seviye": "orta",
                             "mesaj": f"{etiket} %{v} — eşiği (%{esik:.0f}) aşıyor; bağımlılık riski.",
                             "deger": v})
    return uyarilar


async def konsantrasyon_gorevi(fotograf: dict):
    """Konsantrasyon eşiği aşılırsa Ayda'nın karar kuyruğuna risk azaltma önerisi ekler
    (deterministik; açık aynı öneri varsa tekrar eklemez)."""
    kons = metrik_al(fotograf, "konsantrasyon", {}) or {}
    esik = kons.get("esik_yuzde", 25.0)
    en_buyuk = kons.get("en_buyuk_ogretmen_ogrenci_payi") or 0
    if en_buyuk <= esik:
        return
    var = await db.ai_ceo_oneriler.find_one({"kaynak": "konsantrasyon", "durum": {"$in": ["yeni", "ertelendi"]}})
    if var:
        return
    import uuid
    from core.zaman import iso
    await db.ai_ceo_oneriler.insert_one({
        "id": str(uuid.uuid4()), "analiz_id": "sistem", "baslik": "Konsantrasyon riskini azalt",
        "kategori": "strateji", "oncelik": "yuksek", "kaynak": "konsantrasyon",
        "ozet": f"En büyük öğretmenin öğrenci payı %{en_buyuk} (eşik %{esik:.0f}). Öğrenci/gelir "
                "dağılımını çeşitlendirecek adımlar planla.",
        "beklenen_etki": "Tek noktaya bağımlılığın azalması.",
        "dayanaklar": [{"metrik": "en_buyuk_ogretmen_ogrenci_payi", "deger": en_buyuk, "dogrulandi": True, "guven": "guclu"}],
        "zayif_dayanak": False, "vizyon_onerisi": False, "durum": "yeni", "durum_notu": "", "tarih": iso()})


async def anomali_bildirim_gonder(uyarilar: list):
    """Kritik anomaliler için admin'e bildirim (cooldown bildirim.py'de)."""
    if not uyarilar:
        return
    try:
        from modules.bildirim import bildirim_olustur
        adminler = await db.users.find({"role": {"$in": ["admin", "coordinator"]}}, {"_id": 0, "id": 1}).to_list(length=50)
        for u in uyarilar:
            if u.get("seviye") != "kritik":
                continue
            for a in adminler:
                await bildirim_olustur(a["id"], "ai_ceo_anomali", f"⚠️ {u['mesaj']}", None)
    except Exception as e:
        logging.warning(f"[ai_ceo] anomali bildirim hatası: {e}")


@router.get("/ai/ceo/anomali")
async def anomali_listesi(current_user=Depends(_ADMIN)):
    foto = await son_fotograf()
    uyarilar = anomalileri_hesapla(foto) if foto else []
    return {"anomaliler": uyarilar, "fotograf_tarih": foto.get("tarih") if foto else None}
