"""AI CEO — Yönetici Oyunlaştırması: "Yönetim Skoru" (DETERMİNİSTİK).

Ayda'nın teklif/tespitlerini yönetici için görev gibi oyunlaştırır. Puanlar YALNIZ durum
işaretlerinden türetilir — Ayda puan VEREMEZ. Ölçülü kutlama; konfeti/ses yok.

Puan kaynakları: karar (uygulanacak/reddet — ERTELE PUAN VERMEZ; ağırlık önceliğe göre),
haftalık brifing okuma, aylık rapor inceleme, Deniz bulgusu değerlendirme, stratejik plan
onayı. "Gözden Kaçan Yok" rozeti: bekleyen karar + değerlendirilmemiş bulgu + okunmamış
brifing = 0 iken yanar.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import simdi, aware as _aware, iso as _iso

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Puan ağırlıkları
KARAR_AGIRLIK = {"yuksek": 10, "orta": 6, "dusuk": 3}
ETKINLIK_PUAN = {
    "brifing_okundu": 5,
    "rapor_incelendi": 8,
    "bulgu_degerlendirildi": 4,
    "plan_onaylandi": 15,
    "sinav_degerlendirme": 4,
    "kurulum": 8,  # yönetici kurulum/deneyim görevi (XP değil Yönetim Skoru)
}
SEVIYELER = [(0, "Acemi Yönetici"), (100, "Stratejist"), (300, "Vizyoner")]


def _seviye(puan: int) -> str:
    ad = SEVIYELER[0][1]
    for esik, e in SEVIYELER:
        if puan >= esik:
            ad = e
    return ad


async def puan_kaydet(kullanici_id: str, tur: str, agirlik_anahtar: str = "", ref: str = "") -> int:
    """Bir yönetim etkinliğini deterministik puanla loglar. Aynı ref+tur bir kez sayılır."""
    if tur == "karar":
        puan = KARAR_AGIRLIK.get(agirlik_anahtar, 6)
    else:
        puan = ETKINLIK_PUAN.get(tur, 0)
    if puan <= 0:
        return 0
    # idempotent: aynı (tur, ref) tekrar puanlanmaz
    if ref:
        var = await db.ai_ceo_yonetim_log.find_one({"tur": tur, "ref": ref})
        if var:
            return 0
    await db.ai_ceo_yonetim_log.insert_one({
        "kullanici_id": kullanici_id, "tur": tur, "ref": ref or "", "puan": puan, "tarih": _iso(),
    })
    return puan


async def _bekleyen_sayilar() -> dict:
    """Kuyruk (karar bekleyen) + Deniz bulgu + okunmamış brifing sayıları."""
    simdiki = simdi().isoformat()
    # Karar bekleyen: durum 'yeni' veya süresi gelmiş 'ertelendi'
    bekleyen_karar = await db.ai_ceo_oneriler.count_documents({"durum": "yeni"})
    bekleyen_karar += await db.ai_ceo_oneriler.count_documents(
        {"durum": "ertelendi", "ertele_tarih": {"$lte": simdiki}})
    # Deniz bulguları (koleksiyon yoksa 0)
    try:
        degerlendirilmemis = await db.ai_ceo_deniz_bulgular.count_documents({"durum": "yeni"})
    except Exception:
        degerlendirilmemis = 0
    # Okunmamış haftalık brifingler
    haftaliklar = await db.ai_ceo_raporlar.find({"tip": "haftalik"}, {"_id": 0, "id": 1}).to_list(length=500)
    okunan = set()
    async for e in db.ai_ceo_yonetim_log.find({"tur": "brifing_okundu"}, {"_id": 0, "ref": 1}):
        okunan.add(e.get("ref"))
    okunmamis_brifing = sum(1 for h in haftaliklar if h["id"] not in okunan)
    return {"bekleyen_karar": bekleyen_karar, "degerlendirilmemis_bulgu": degerlendirilmemis,
            "okunmamis_brifing": okunmamis_brifing}


async def _seri_hafta() -> int:
    """Aktivite olan ardışık hafta sayısı (bu haftadan geriye)."""
    now = simdi()
    haftalar = set()
    async for e in db.ai_ceo_yonetim_log.find({}, {"_id": 0, "tarih": 1}):
        d = _aware(e.get("tarih"))
        if d:
            haftalar.add((now - d).days // 7)
    seri = 0
    while seri in haftalar:
        seri += 1
    return seri


async def yonetim_skoru() -> dict:
    toplam = 0
    kirilim = {}
    async for e in db.ai_ceo_yonetim_log.find({}, {"_id": 0, "puan": 1, "tur": 1}):
        toplam += e.get("puan", 0)
        kirilim[e["tur"]] = kirilim.get(e["tur"], 0) + e.get("puan", 0)
    bekleyen = await _bekleyen_sayilar()
    gozden_kacan_yok = all(v == 0 for v in bekleyen.values())
    return {
        "puan": toplam,
        "seviye": _seviye(toplam),
        "seri_hafta": await _seri_hafta(),
        "kirilim": kirilim,
        "bekleyenler": bekleyen,
        "gozden_kacan_yok": gozden_kacan_yok,
    }


@router.get("/ai/ceo/yonetim-skoru")
async def yonetim_skoru_endpoint(current_user=Depends(_ADMIN)):
    return {"skor": await yonetim_skoru()}


@router.post("/ai/ceo/yonetim/etkinlik")
async def yonetim_etkinlik(govde: dict, current_user=Depends(_ADMIN)):
    """Puanlanabilir yönetim etkinliği kaydı (brifing_okundu / rapor_incelendi / ...)."""
    tur = govde.get("tur")
    if tur not in ETKINLIK_PUAN:
        return {"ok": False, "sebep": "Geçersiz etkinlik türü"}
    kazanilan = await puan_kaydet(current_user.get("id"), tur, "", str(govde.get("ref", "")))
    return {"ok": True, "kazanilan_puan": kazanilan}
