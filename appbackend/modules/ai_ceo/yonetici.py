"""AI CEO — Yönetici "Sıradaki Adımlar" (P5).

İki kaynak: (a) KURULUM/DENEYİM görevleri (öğretmen keşif yolunun admin karşılığı; XP yerine
Yönetim Skoru puanı; otomatik algılanır + geriye dönük migration; Ayarlar'dan yönetilir,
hedef alanıyla). (b) GÜNCEL BEKLEYEN İŞLER (dinamik; "Gözden Kaçan Yok" ile AYNI kaynaktan —
çift hesap yok). Hepsi tıklanınca ilgili yere götürür (hedef). Ayda'nın sesiyle sunulur.
"""
from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso

from .yonetim import puan_kaydet, _bekleyen_sayilar

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
AYAR_TIP = "yonetici_kurulum_gorevleri"

# hedef = admin activeTab id (tıkla → git)
VARSAYILAN_GOREVLER = [
    {"id": "kur_ucret", "baslik": "Kur ücretlerini tanımla", "aciklama": "Muhasebe ayarlarından kur ücretlerini gir.", "puan": 8, "sira": 1, "aktif": True, "hedef": "payments"},
    {"id": "vergi", "baslik": "Vergi oranını kontrol et", "aciklama": "Güncel vergi oranını doğrula.", "puan": 6, "sira": 2, "aktif": True, "hedef": "payments", "ziyaret": True},
    {"id": "ilk_analiz", "baslik": "İlk Ayda analizini çalıştır", "aciklama": "AI CEO'da 'Analiz Çalıştır'.", "puan": 10, "sira": 3, "aktif": True, "hedef": "ai-ceo"},
    {"id": "deneyim_gozden", "baslik": "Öğretmen görev listesini gözden geçir", "aciklama": "Deneyim görevlerini Ayarlar'dan incele.", "puan": 6, "sira": 4, "aktif": True, "hedef": "ayarlar", "ziyaret": True},
    {"id": "sss_baslangic", "baslik": "SSS'ye başlangıç içeriği ekle", "aciklama": "SSS Yönetimi'nden içerik ekle.", "puan": 8, "sira": 5, "aktif": True, "hedef": "sss-yonetimi"},
    {"id": "bakim_mesaj", "baslik": "Bakım modu mesajını yaz", "aciklama": "Sistem ayarlarından bakım mesajını ayarla.", "puan": 6, "sira": 6, "aktif": True, "hedef": "ayarlar", "ziyaret": True},
]


# ── Otomatik algılama koşulları ──
async def _p_kur_ucret(*_):
    d = await db.sistem_ayarlari.find_one({"tip": "kur_ucretleri"})
    return bool(d and ((d.get("degerler") or {}).get("genel") or d.get("genel")))


async def _p_analiz(*_):
    return await db.ai_ceo_analizler.count_documents({}) > 0


async def _p_sss(*_):
    for koll in ("sss_sorular", "sss"):
        try:
            if await db[koll].count_documents({}) > 0:
                return True
        except Exception:
            continue
    return False


async def _p_ziyaret(gorev_id):
    return await db.ai_ceo_yonetici_ziyaret.count_documents({"gorev_id": gorev_id}) > 0


GOREV_KOSULLARI = {"kur_ucret": _p_kur_ucret, "ilk_analiz": _p_analiz, "sss_baslangic": _p_sss}


async def _tanimlar() -> list:
    doc = await db.sistem_ayarlari.find_one({"tip": AYAR_TIP})
    gorevler = (doc or {}).get("gorevler") or VARSAYILAN_GOREVLER
    return sorted([g for g in gorevler if g.get("aktif", True)], key=lambda g: g.get("sira", 99))


async def _tamamlandi(g) -> bool:
    if g.get("ziyaret"):
        return await _p_ziyaret(g["id"])
    fn = GOREV_KOSULLARI.get(g["id"])
    if not fn:
        return False
    try:
        return await fn()
    except Exception:
        return False


async def _kurulum_degerlendir(uid: str) -> list:
    tanimlar = await _tanimlar()
    kazanilmis = {k["gorev_id"] async for k in db.ai_ceo_yonetici_tamamlanan.find({}, {"_id": 0, "gorev_id": 1})}
    sonuc = []
    for g in tanimlar:
        bitti = await _tamamlandi(g)
        if bitti and g["id"] not in kazanilmis:
            await db.ai_ceo_yonetici_tamamlanan.insert_one({"gorev_id": g["id"], "puan": g.get("puan", 0), "tarih": iso()})
            kazanilmis.add(g["id"])
            await puan_kaydet(uid, "kurulum", "", f"kurulum_{g['id']}")  # Yönetim Skoru'na işlenir
        sonuc.append({**g, "tamamlandi": bitti})
    return sonuc


async def _dinamik_isler() -> list:
    """'Gözden Kaçan Yok' ile aynı kaynaktan (çift hesap yok)."""
    b = await _bekleyen_sayilar()
    isler = []
    if b.get("bekleyen_karar"):
        isler.append({"tip": "karar", "baslik": f"{b['bekleyen_karar']} karar bekleyen öneri", "hedef": "ai-ceo"})
    if b.get("degerlendirilmemis_bulgu"):
        isler.append({"tip": "bulgu", "baslik": f"{b['degerlendirilmemis_bulgu']} değerlendirilmemiş denetim bulgusu", "hedef": "ai-deniz"})
    if b.get("okunmamis_brifing"):
        isler.append({"tip": "brifing", "baslik": f"{b['okunmamis_brifing']} okunmamış brifing", "hedef": "ai-ceo"})
    # 7 gün+ bekleyen (gözden kaçıyor olabilir) — kuyruktaki eski açık öğeler
    try:
        from .kuyruk import kuyruk as _kuyruk_fn  # aynı deterministik kaynak
        k = await _kuyruk_fn()
        if isinstance(k, dict) and k.get("gozden_kacan_sayi"):
            isler.append({"tip": "gozden_kaciyor", "baslik": f"{k['gozden_kacan_sayi']} öğe 7+ gündür bekliyor", "hedef": "ai-ceo"})
    except Exception:
        pass
    return isler


@router.get("/ai/ceo/yonetici-adimlar")
async def yonetici_adimlar(current_user=Depends(_ADMIN)):
    kurulum = await _kurulum_degerlendir(current_user.get("id"))
    dinamik = await _dinamik_isler()
    biten = sum(1 for k in kurulum if k["tamamlandi"])
    siradaki = next((k for k in kurulum if not k["tamamlandi"]), None)
    return {"kurulum": kurulum, "dinamik": dinamik,
            "kurulum_biten": biten, "kurulum_toplam": len(kurulum),
            "siradaki": siradaki,
            "mesaj": "Sıradaki adımınız hazır." if (siradaki or dinamik) else "Her şey yolunda — gözden kaçan iş yok."}


@router.post("/ai/ceo/yonetici-adimlar/ziyaret/{gorev_id}")
async def yonetici_ziyaret(gorev_id: str, current_user=Depends(_ADMIN)):
    """Ziyaret-tipi kurulum görevleri için otomatik işaret (sayfayı/ayarı açınca)."""
    await db.ai_ceo_yonetici_ziyaret.update_one({"gorev_id": gorev_id},
                                                {"$set": {"gorev_id": gorev_id, "tarih": iso()}}, upsert=True)
    return {"ok": True}


@router.get("/ai/ceo/yonetici-adimlar/tanimlar")
async def yonetici_tanimlar(current_user=Depends(_ADMIN)):
    doc = await db.sistem_ayarlari.find_one({"tip": AYAR_TIP}, {"_id": 0})
    return {"gorevler": (doc or {}).get("gorevler") or VARSAYILAN_GOREVLER}


@router.put("/ai/ceo/yonetici-adimlar/tanimlar")
async def yonetici_tanimlar_guncelle(govde: dict, current_user=Depends(_ADMIN)):
    gorevler = govde.get("gorevler")
    if not isinstance(gorevler, list):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="gorevler (liste) gerekli")
    await db.sistem_ayarlari.update_one({"tip": AYAR_TIP}, {"$set": {"tip": AYAR_TIP, "gorevler": gorevler}}, upsert=True)
    return {"ok": True}
