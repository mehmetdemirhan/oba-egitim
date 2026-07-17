"""AI CEO — Denetçi AI "Deniz" (S8 temel + S10 karne). YALNIZ ADMIN.

Bağımsız müfettiş: Ayda'nın çıktılarını denetler. Deterministik kontroller + (opsiyonel)
AI denetim turu + admin ONAYIYLA sonraki analize giren "denetim notu". Otomatik kendi
kendini değiştirme YOK (API guard). Değerlendirilen veriler deterministik kaynaklardan.

Bulgu: { tur, onem: kritik|orta|dusuk, ozet, kanit, durum: yeni|admin_gecerli|admin_gecersiz|cozuldu }
"""
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.ai import call_claude
from core.config import GEMINI_API_KEY
from core.zaman import simdi, aware as _aware, iso

from .fotograf import son_fotograf, ai_payload
from .personalar import sistem_promptu

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN)  # Deniz YALNIZ admin
BULGU_DURUMLAR = ["yeni", "admin_gecerli", "admin_gecersiz", "cozuldu"]


# ─────────────────────────── S8a: deterministik kontroller ───────────────────────────
async def deterministik_kontroller() -> list:
    """Ayda'nın karnesi/önerileri üzerinde kural bazlı denetim (AI YOK)."""
    bulgular = []
    oneriler = await db.ai_ceo_oneriler.find({}, {"_id": 0}).to_list(length=5000)
    toplam = len(oneriler)

    # 1) Zayıf dayanak oranı yüksek mi?
    if toplam >= 5:
        zayif = sum(1 for o in oneriler if o.get("zayif_dayanak"))
        oran = zayif * 100 / toplam
        if oran > 40:
            bulgular.append({"tur": "dayanak_zayifligi", "onem": "kritik",
                             "ozet": f"Önerilerin %{oran:.0f}'i zayıf dayanaklı (halüsinasyon riski).",
                             "kanit": {"zayif": zayif, "toplam": toplam}})

    # 2) Tekrarlanan öneriler (aynı başlık ≥3)
    baslik_say = {}
    for o in oneriler:
        b = (o.get("baslik") or "").strip().lower()
        if b:
            baslik_say[b] = baslik_say.get(b, 0) + 1
    tekrarli = {b: n for b, n in baslik_say.items() if n >= 3}
    if tekrarli:
        bulgular.append({"tur": "tekrarlanan_oneri", "onem": "orta",
                         "ozet": f"{len(tekrarli)} öneri başlığı tekrar tekrar üretiliyor (uygulanmıyor olabilir).",
                         "kanit": tekrarli})

    # 3) Kategori dengesizliği (tek kategori > %60)
    if toplam >= 5:
        kat = {}
        for o in oneriler:
            kat[o.get("kategori", "?")] = kat.get(o.get("kategori", "?"), 0) + 1
        enb = max(kat.values())
        if enb * 100 / toplam > 60:
            dom = max(kat, key=kat.get)
            bulgular.append({"tur": "kategori_dengesizligi", "onem": "dusuk",
                             "ozet": f"Öneriler tek kategoride yoğunlaşmış ('{dom}' %{enb*100/toplam:.0f}).",
                             "kanit": kat})

    # 4) Beklemede takılı öneriler (7+ gün 'yeni' + ertelenmiş çok)
    now = simdi()
    takili = 0
    for o in oneriler:
        if o.get("durum") == "yeni":
            d = _aware(o.get("tarih"))
            if d and (now - d).days >= 7:
                takili += 1
    if takili >= 5:
        bulgular.append({"tur": "beklemede_takili", "onem": "orta",
                         "ozet": f"{takili} öneri 7+ gündür karara bağlanmamış (gözden kaçıyor).",
                         "kanit": {"takili": takili}})

    # 5) Miran geri bildirim düşüşü (faydalı oranı < %50, en az 5 geri bildirim)
    mgb = await db.ai_ceo_miran_geribildirim.find({}, {"_id": 0, "faydali": 1}).to_list(length=20000)
    if len(mgb) >= 5:
        faydali = sum(1 for m in mgb if m.get("faydali"))
        if faydali * 100 / len(mgb) < 50:
            bulgular.append({"tur": "miran_geri_bildirim_dususu", "onem": "orta",
                             "ozet": f"Miran koçluk faydalı oranı düşük (%{faydali*100/len(mgb):.0f}).",
                             "kanit": {"faydali": faydali, "toplam": len(mgb)}})
    return bulgular


# ─────────────────────────── S8b: AI denetim turu (opsiyonel) ───────────────────────────
async def _ai_denetim(det_bulgular: list) -> dict:
    if not GEMINI_API_KEY:
        return {"ozet": "", "ek_bulgular": [], "iyilestirme_plani": ""}
    foto = await son_fotograf()
    karne = await db.ai_ceo_analizler.find({}, {"_id": 0}).sort("tarih", -1).to_list(length=5)
    system = sistem_promptu("deniz")
    user = (
        "Ayda'nın son analizleri ve deterministik denetim bulguları aşağıda. Nesnel bir "
        "müfettiş olarak tutarsızlık/gözden kaçan/zayıf mantık tespit et ve bir İYİLEŞTİRME "
        "PLANI öner (kısa, uygulanabilir).\n\n"
        f"DETERMİNİSTİK BULGULAR: {json.dumps(det_bulgular, ensure_ascii=False)[:2000]}\n"
        f"SON ANALİZLER: {json.dumps([a.get('ozet') for a in karne], ensure_ascii=False)[:1500]}\n"
        f"FOTOĞRAF ÖZET: {json.dumps(ai_payload(foto or {}), ensure_ascii=False)[:2500]}\n\n"
        'SADECE JSON: {"ozet":"...","ek_bulgular":[{"tur":"...","onem":"orta","ozet":"...","kanit":"..."}],"iyilestirme_plani":"..."}'
    )
    res = await call_claude(system, user, max_tokens=2000)
    p = res.get("parsed")
    if isinstance(p, dict):
        return {"ozet": str(p.get("ozet", ""))[:1000],
                "ek_bulgular": [b for b in (p.get("ek_bulgular") or []) if isinstance(b, dict)][:8],
                "iyilestirme_plani": str(p.get("iyilestirme_plani", ""))[:2000]}
    return {"ozet": "", "ek_bulgular": [], "iyilestirme_plani": ""}


async def denetle(tetik: str = "manuel") -> dict:
    det = await deterministik_kontroller()
    ai = await _ai_denetim(det)
    now = iso()
    denetim_id = str(uuid.uuid4())
    tum = list(det)
    for b in ai.get("ek_bulgular", []):
        tum.append({"tur": b.get("tur", "ai_bulgu"), "onem": b.get("onem", "orta"),
                    "ozet": str(b.get("ozet", ""))[:500], "kanit": b.get("kanit"), "kaynak": "ai"})
    kayitlar = []
    for b in tum:
        kayitlar.append({"id": str(uuid.uuid4()), "denetim_id": denetim_id,
                         "tur": b["tur"], "onem": b.get("onem", "orta"),
                         "ozet": b["ozet"], "kanit": b.get("kanit"),
                         "kaynak": b.get("kaynak", "deterministik"),
                         "durum": "yeni", "tarih": now})
    if kayitlar:
        await db.ai_ceo_deniz_bulgular.insert_many([{**k} for k in kayitlar])
    denetim = {"id": denetim_id, "tarih": now, "tetik": tetik, "ozet": ai.get("ozet", ""),
               "iyilestirme_plani": ai.get("iyilestirme_plani", ""), "bulgu_sayisi": len(kayitlar),
               "kritik_sayi": sum(1 for k in kayitlar if k["onem"] == "kritik")}
    await db.ai_ceo_denetimler.insert_one({**denetim})
    denetim.pop("_id", None)
    # Kritik bulgu → admin bildirimi
    if denetim["kritik_sayi"]:
        try:
            from modules.bildirim import bildirim_olustur
            for a in await db.users.find({"role": "admin"}, {"_id": 0, "id": 1}).to_list(length=50):
                await bildirim_olustur(a["id"], "ai_ceo_anomali", f"🔍 Deniz {denetim['kritik_sayi']} kritik denetim bulgusu buldu.", denetim_id)
        except Exception as e:
            logging.warning(f"[ai_ceo] deniz bildirim hatası: {e}")
    return {"ok": True, "denetim": denetim, "bulgular": [{k: v for k, v in b.items() if k != "_id"} for b in kayitlar]}


@router.post("/ai/ceo/deniz/denetle")
async def deniz_denetle(current_user=Depends(_ADMIN)):
    return await denetle("manuel")


@router.get("/ai/ceo/deniz/son")
async def deniz_son(current_user=Depends(_ADMIN)):
    d = await db.ai_ceo_denetimler.find_one({}, {"_id": 0}, sort=[("tarih", -1)])
    bulgular = await db.ai_ceo_deniz_bulgular.find({}, {"_id": 0}).sort("tarih", -1).to_list(length=200) if d else []
    return {"denetim": d, "bulgular": bulgular}


@router.put("/ai/ceo/deniz/bulgu/{bulgu_id}/durum")
async def deniz_bulgu_durum(bulgu_id: str, govde: dict, current_user=Depends(_ADMIN)):
    durum = govde.get("durum")
    if durum not in BULGU_DURUMLAR:
        raise HTTPException(status_code=400, detail="Geçersiz durum")
    onceki = await db.ai_ceo_deniz_bulgular.find_one({"id": bulgu_id}, {"_id": 0, "durum": 1})
    if not onceki:
        raise HTTPException(status_code=404, detail="Bulgu bulunamadı")
    await db.ai_ceo_deniz_bulgular.update_one({"id": bulgu_id}, {"$set": {
        "durum": durum, "durum_notu": str(govde.get("not", ""))[:400], "durum_tarih": iso()}})
    # Yönetim skoru: bulgu değerlendirme (geçerli/geçersiz), ilk kez
    if durum in ("admin_gecerli", "admin_gecersiz") and onceki.get("durum") == "yeni":
        try:
            from .yonetim import puan_kaydet
            await puan_kaydet(current_user.get("id"), "bulgu_degerlendirildi", "", bulgu_id)
        except Exception:
            pass
    return {"ok": True, "durum": durum}


# ─────────────────────────── S8c: iyileştirme notu (admin onaylı) ───────────────────────────
@router.post("/ai/ceo/deniz/not")
async def deniz_not_ekle(govde: dict, current_user=Depends(_ADMIN)):
    """Deniz iyileştirme planından admin'in seçtiği notu TASLAK olarak kaydeder."""
    metin = str(govde.get("metin", "")).strip()
    if not metin:
        raise HTTPException(status_code=400, detail="metin gerekli")
    kayit = {"id": str(uuid.uuid4()), "metin": metin[:2000], "onayli": False, "tarih": iso()}
    await db.ai_ceo_denetim_notlari.insert_one({**kayit})
    kayit.pop("_id", None)
    return {"ok": True, "not": kayit}


@router.post("/ai/ceo/deniz/not/{not_id}/onayla")
async def deniz_not_onayla(not_id: str, current_user=Depends(_ADMIN)):
    """ONAY GUARD: yalnız admin onayıyla not sonraki analize girer. Oto self-modifikasyon YOK."""
    r = await db.ai_ceo_denetim_notlari.update_one({"id": not_id}, {"$set": {
        "onayli": True, "onaylayan": current_user.get("id"), "onay_tarih": iso()}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not bulunamadı")
    return {"ok": True, "onaylandi": True}


@router.get("/ai/ceo/deniz/notlar")
async def deniz_notlar(current_user=Depends(_ADMIN)):
    docs = await db.ai_ceo_denetim_notlari.find({}, {"_id": 0}).sort("tarih", -1).to_list(length=100)
    return {"notlar": docs}


# ─────────────────────────── S10: Deniz'in karnesi (deterministik) ───────────────────────────
def _oran(p, t):
    return round(p * 100 / t, 1) if t else None


@router.get("/ai/ceo/deniz/karne")
async def deniz_karne(current_user=Depends(_ADMIN)):
    bulgular = await db.ai_ceo_deniz_bulgular.find({}, {"_id": 0}).to_list(length=10000)
    degerlendirilen = [b for b in bulgular if b.get("durum") in ("admin_gecerli", "admin_gecersiz", "cozuldu")]
    gecerli = [b for b in bulgular if b.get("durum") in ("admin_gecerli", "cozuldu")]
    # Bulgu doğruluğu (ana gösterge): geçerli / değerlendirilen
    bulgu_dogrulugu = _oran(len(gecerli), len(degerlendirilen))
    # Yakalama değeri: kritiklerin kaçı çözüldü
    kritikler = [b for b in bulgular if b.get("onem") == "kritik"]
    cozulen_kritik = [b for b in kritikler if b.get("durum") == "cozuldu"]
    yakalama_degeri = _oran(len(cozulen_kritik), len(kritikler))
    # Kaçırma oranı: admin "Deniz kaçırdı" kayıtları
    kacirma = await db.ai_ceo_deniz_kacirma.count_documents({})
    return {"karne": {
        "toplam_bulgu": len(bulgular),
        "degerlendirilen": len(degerlendirilen),
        "bulgu_dogrulugu": bulgu_dogrulugu,
        "yakalama_degeri": yakalama_degeri,
        "kritik_toplam": len(kritikler),
        "kacirilan_bildirilen": kacirma,
        "ozet": (f"{len(bulgular)} bulgu; doğruluk %{bulgu_dogrulugu if bulgu_dogrulugu is not None else 0}, "
                 f"kritik yakalama %{yakalama_degeri if yakalama_degeri is not None else 0}."),
    }}


@router.post("/ai/ceo/deniz/kacirma")
async def deniz_kacirma(govde: dict, current_user=Depends(_ADMIN)):
    """Admin: 'Deniz bunu kaçırdı' — kaçırma oranına işlenir (kalibrasyon)."""
    await db.ai_ceo_deniz_kacirma.insert_one({"id": str(uuid.uuid4()), "aciklama": str(govde.get("aciklama", ""))[:400], "tarih": iso()})
    return {"ok": True}
