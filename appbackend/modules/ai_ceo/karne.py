"""AI CEO — Ayda'nın Karnesi (DETERMİNİSTİK — kendi karnesini kendisi yazamaz).

Kabul oranı (kategori kırılımlı), isabet oranı (beklenen_etki vs 30+ gün sonra ölçülen
gerçek değişim; erken=beklemede), zayıf dayanak oranı, Miran koç geri bildirimleri
(faydalı %), aylık trend. Kovma kararının dayanağı bu ekran → bu yüzden AI'sız, saf sayı.
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import simdi, aware as _aware

from .ortak import metrik_al, KATEGORI_METRIK

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

ISABET_OLCUM_GUN = 30  # uygulanan öneri en az bu kadar süre geçmişse ölçülür


def _oran(pay, payda):
    return round(pay * 100 / payda, 1) if payda else None


async def _fotograf_by_tarih(tarih: str) -> dict | None:
    if not tarih:
        return None
    return await db.ai_ceo_fotograflar.find_one({"tarih": tarih}, {"_id": 0})


async def _isabet_olc(oneri: dict, son_foto: dict) -> str:
    """uygulandi önerinin etkisi: 'isabetli' | 'isabetsiz' | 'beklemede'."""
    d = _aware(oneri.get("durum_tarih") or oneri.get("tarih"))
    if not d:
        return "beklemede"
    if (simdi() - d).days < ISABET_OLCUM_GUN:
        return "beklemede"
    yol, yon = KATEGORI_METRIK.get(oneri.get("kategori"), (None, "artis"))
    if not yol:
        return "beklemede"
    onceki_foto = await _fotograf_by_tarih(oneri.get("uygulama_fotograf_tarih"))
    onceki = metrik_al(onceki_foto or {}, yol)
    guncel = metrik_al(son_foto or {}, yol)
    try:
        onceki = float(onceki); guncel = float(guncel)
    except (TypeError, ValueError):
        return "beklemede"
    iyilesme = (guncel > onceki) if yon == "artis" else (guncel < onceki)
    return "isabetli" if iyilesme else "isabetsiz"


async def karne_hesapla(gun: int = 90) -> dict:
    esik = (simdi() - timedelta(days=gun)).isoformat()
    oneriler = await db.ai_ceo_oneriler.find({"tarih": {"$gte": esik}}, {"_id": 0}).to_list(length=5000)
    son_foto = await db.ai_ceo_fotograflar.find_one({}, {"_id": 0}, sort=[("tarih", -1)])

    toplam = len(oneriler)
    karar_verilen = [o for o in oneriler if o.get("durum") in ("uygulaniyor", "uygulandi", "reddedildi")]
    kabul = [o for o in karar_verilen if o.get("durum") in ("uygulaniyor", "uygulandi")]
    kabul_orani = _oran(len(kabul), len(karar_verilen))

    # Kategori kırılımı
    kategori = {}
    for o in oneriler:
        k = o.get("kategori", "diger")
        kategori.setdefault(k, {"toplam": 0, "kabul": 0})
        kategori[k]["toplam"] += 1
        if o.get("durum") in ("uygulaniyor", "uygulandi"):
            kategori[k]["kabul"] += 1
    for k, v in kategori.items():
        v["kabul_orani"] = _oran(v["kabul"], v["toplam"])

    # İsabet ölçümü (yalnız uygulandi)
    isabetli = isabetsiz = beklemede = 0
    for o in [x for x in oneriler if x.get("durum") == "uygulandi"]:
        sonuc = await _isabet_olc(o, son_foto)
        if sonuc == "isabetli":
            isabetli += 1
        elif sonuc == "isabetsiz":
            isabetsiz += 1
        else:
            beklemede += 1
    olculen = isabetli + isabetsiz
    isabet_orani = _oran(isabetli, olculen)

    # Zayıf dayanak oranı
    zayif = sum(1 for o in oneriler if o.get("zayif_dayanak"))
    zayif_orani = _oran(zayif, toplam)

    # Miran koç geri bildirimleri (faydalı %)
    mgb = await db.ai_ceo_miran_geribildirim.find({}, {"_id": 0, "faydali": 1}).to_list(length=20000)
    faydali = sum(1 for m in mgb if m.get("faydali"))
    miran_faydali_orani = _oran(faydali, len(mgb))

    # Aylık trend (öneri sayısı + kabul)
    trend = {}
    for o in oneriler:
        ay = str(o.get("tarih", ""))[:7]
        if not ay:
            continue
        trend.setdefault(ay, {"ay": ay, "oneri": 0, "kabul": 0})
        trend[ay]["oneri"] += 1
        if o.get("durum") in ("uygulaniyor", "uygulandi"):
            trend[ay]["kabul"] += 1

    return {
        "donem_gun": gun,
        "toplam_oneri": toplam,
        "kabul_orani": kabul_orani,
        "kategori_kirilim": kategori,
        "isabet": {"isabetli": isabetli, "isabetsiz": isabetsiz, "beklemede": beklemede,
                   "isabet_orani": isabet_orani, "olculen": olculen},
        "zayif_dayanak_orani": zayif_orani,
        "miran_faydali_orani": miran_faydali_orani,
        "miran_geri_bildirim_sayisi": len(mgb),
        "aylik_trend": sorted(trend.values(), key=lambda x: x["ay"]),
        "ozet": (f"Son {gun} gün: {toplam} öneri, "
                 f"%{kabul_orani if kabul_orani is not None else 0} kabul, "
                 f"%{isabet_orani if isabet_orani is not None else 0} ölçülmüş etki."),
    }


@router.get("/ai/ceo/karne")
async def karne_endpoint(gun: int = 90, current_user=Depends(_ADMIN)):
    return {"karne": await karne_hesapla(gun)}
