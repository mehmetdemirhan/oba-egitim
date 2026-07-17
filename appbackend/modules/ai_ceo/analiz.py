"""AI CEO — Analiz + Öneriler (Ayda) + halüsinasyon (dayanak) doğrulama.

Sistem fotoğrafı → Gemini (rol: deneyimli eğitim kurumu CEO'su) → yapılandırılmış
öneriler. Her önerinin dayanak_metrikler'i ZORUNLU; backend fotoğrafa karşı doğrular,
doğrulanamayan dayanak "zayıf" etiketi alır (halüsinasyon koruması).

AI yoksa/başarısızsa UYDURMA yapılmaz — sebep döndürülür.
"""
import json
import logging
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.ai import call_claude
from core.config import GEMINI_API_KEY
from core.zaman import simdi, iso as _iso

from .fotograf import sistem_fotografi, son_fotograf, fotograf_kaydet, ai_payload
from .personalar import sistem_promptu

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

KATEGORILER = ["ogretmen_gelisimi", "tahsilat", "urun_iyilestirme", "ogrenci_memnuniyeti", "buyume", "strateji"]
DURUMLAR = ["yeni", "uygulaniyor", "uygulandi", "reddedildi", "ertelendi"]
# Karara bağlanınca kuyruktan düşen durumlar (ertelendi geçici, ötelenir)
KARARLI_DURUMLAR = {"uygulaniyor", "uygulandi", "reddedildi"}


# ─────────────────────────── prompt ───────────────────────────
def _analiz_prompt(payload: dict, plan: dict | None = None, denetim_notu: str = "") -> tuple:
    system = sistem_promptu("ayda")
    plan_metni = ""
    if plan and plan.get("hedefler"):
        hedef_ozet = "; ".join(f"Hedef {i+1}: {h.get('ad')} ({h.get('metrik')} {h.get('mevcut')}→{h.get('hedef')})"
                               for i, h in enumerate(plan["hedefler"]))
        plan_metni = (f"\n\nONAYLI STRATEJİK PLAN (referans al; uygun önerilerde hangi hedefe hizmet "
                      f"ettiğini 'plan_hedef' alanında belirt): {hedef_ozet}")
    denetim_metni = f"\n\nDENETÇİ NOTU (Deniz — dikkate al): {denetim_notu}" if denetim_notu else ""
    user = (
        "Aşağıda kurumun güncel SİSTEM FOTOĞRAFI (agregat metrikler) var. Bunu bir CEO gibi "
        "360° analiz et. Öğrenci memnuniyetini ve kur yenilemesini artıracak, VERİ TEMELLİ "
        "öneriler üret. Ayrıca hazır metriklerin DIŞINDA envanterde dikkat çeken örüntüleri "
        "(atıl özellik, tema yoğunlaşması, anomali) bir KEŞİF TURU olarak raporla. "
        "STRATEJİK öneriler (yeni özellik/uygulama, büyüme, süreç) için kategori 'strateji' "
        "kullan; bunlar trend/sektör mantığına dayanabilir."
        + plan_metni + denetim_metni +
        f"\n\nSİSTEM FOTOĞRAFI (JSON):\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        "SADECE şu JSON'u döndür (markdown yok):\n"
        "{\n"
        '  "ozet": "1-2 cümle genel durum",\n'
        '  "oneriler": [{\n'
        '     "baslik": "...",\n'
        f'     "kategori": "{"|".join(KATEGORILER)}",\n'
        '     "oncelik": "yuksek|orta|dusuk",\n'
        '     "ozet": "öneri 1-2 cümle",\n'
        '     "dayanak_metrikler": [{"metrik":"fotoğraftaki metrik adı","deger": 12.3}],\n'
        '     "beklenen_etki": "ölçülebilir beklenen sonuç"\n'
        "  }],\n"
        '  "kesif_bulgulari": ["envanterde dikkat çeken örüntü cümleleri"]\n'
        "}\n"
        "Her öneride EN AZ bir dayanak_metrik OLMALI ve değerler fotoğraftaki sayılarla "
        "TUTARLI olmalı. Uydurma."
    )
    return system, user


# ─────────────────────────── dayanak doğrulama ───────────────────────────
def _duz_degerler(obj, prefix="") -> dict:
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_duz_degerler(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(_duz_degerler(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def _sayisal_kume(duz: dict) -> set:
    s = set()
    for v in duz.values():
        try:
            if isinstance(v, bool):
                continue
            s.add(round(float(v), 2))
        except (TypeError, ValueError):
            continue
    return s


def _dayanak_dogrula(dayanaklar: list, fotograf: dict) -> tuple:
    """Her dayanağı fotoğrafa karşı doğrular. (doğrulanmış_liste, zayif_mi)."""
    duz = _duz_degerler(ai_payload(fotograf))
    sayilar = _sayisal_kume(duz)
    yollar = " ".join(duz.keys()).lower()
    sonuc = []
    if not dayanaklar:
        return [], True  # dayanak yoksa zayıf
    for d in dayanaklar:
        if not isinstance(d, dict):
            continue
        metrik = str(d.get("metrik", "")).strip()
        ham = d.get("deger")
        deger_uyumlu = False
        try:
            num = round(float(ham), 2)
            # birebir ya da %1 tolerans
            deger_uyumlu = any(abs(num - x) <= max(0.5, abs(x) * 0.01) for x in sayilar)
        except (TypeError, ValueError):
            deger_uyumlu = False
        # metrik adı token'ları fotoğraf yollarında geçiyor mu?
        tokenlar = [t for t in metrik.lower().replace("_", " ").split() if len(t) > 3]
        ad_uyumlu = any(t in yollar for t in tokenlar) if tokenlar else False
        dogrulandi = bool(deger_uyumlu)  # değer eşleşmesi = güçlü kanıt
        sonuc.append({
            "metrik": metrik, "deger": ham,
            "dogrulandi": dogrulandi,
            "ad_uyumlu": ad_uyumlu,
            "guven": "guclu" if dogrulandi else "zayif",
        })
    zayif = any(not d["dogrulandi"] for d in sonuc)
    return sonuc, zayif


# ─────────────────────────── ana analiz ───────────────────────────
async def calistir_analiz(tetik: str = "manuel", fotograf: dict | None = None, persist: bool = True) -> dict:
    """Fotoğraf → Gemini → öneriler + dayanak doğrulama → sakla. AI yoksa sebep döndürür.
    Onaylı stratejik plan + onaylı denetim notu (Deniz) referans olarak prompt'a girer."""
    if fotograf is None:
        fotograf = await son_fotograf()
        if not fotograf:
            fotograf = await sistem_fotografi()
            await fotograf_kaydet(fotograf)

    if not GEMINI_API_KEY:
        return {"ok": False, "sebep": "AI yapılandırılmadı (GEMINI_API_KEY yok).", "fotograf_tarih": fotograf.get("tarih")}

    # Referanslar: onaylı plan + admin ONAYLI denetim notu (oto self-modifikasyon YOK)
    try:
        from .plan import onayli_plan
        plan = await onayli_plan()
    except Exception:
        plan = None
    denetim_notu = ""
    try:
        dn = await db.ai_ceo_denetim_notlari.find_one({"onayli": True}, sort=[("onay_tarih", -1)])
        denetim_notu = (dn or {}).get("metin", "")
    except Exception:
        pass
    system, user = _analiz_prompt(ai_payload(fotograf), plan, denetim_notu)
    parsed = None
    for _ in range(2):
        res = await call_claude(system, user, max_tokens=4000)
        if res.get("error"):
            logging.warning(f"[ai_ceo] analiz AI hatası: {res.get('error')}")
            continue
        parsed = res.get("parsed")
        if isinstance(parsed, dict) and parsed.get("oneriler"):
            break
    if not isinstance(parsed, dict) or not parsed.get("oneriler"):
        return {"ok": False, "sebep": "AI yanıtı ayrıştırılamadı.", "fotograf_tarih": fotograf.get("tarih")}

    now = _iso()
    analiz_id = str(uuid.uuid4())
    oneri_kayitlari = []
    for o in parsed.get("oneriler", []):
        if not isinstance(o, dict):
            continue
        dayanaklar, zayif = _dayanak_dogrula(o.get("dayanak_metrikler") or [], fotograf)
        kategori = o.get("kategori") if o.get("kategori") in KATEGORILER else "urun_iyilestirme"
        # Stratejik öneri + sert dayanağı yoksa "vizyon önerisi" (meşru tür; zayıf dayanaktan farklı)
        vizyon = (kategori == "strateji" and zayif)
        oneri_kayitlari.append({
            "id": str(uuid.uuid4()),
            "analiz_id": analiz_id,
            "baslik": str(o.get("baslik", "")).strip()[:200],
            "kategori": kategori,
            "oncelik": o.get("oncelik") if o.get("oncelik") in ("yuksek", "orta", "dusuk") else "orta",
            "ozet": str(o.get("ozet", "")).strip()[:1000],
            "beklenen_etki": str(o.get("beklenen_etki", "")).strip()[:500],
            "plan_hedef": str(o.get("plan_hedef", "")).strip()[:120],
            "dayanaklar": dayanaklar,
            "zayif_dayanak": zayif and not vizyon,   # vizyon önerisi zayıf sayılmaz
            "vizyon_onerisi": vizyon,
            "durum": "yeni",
            "durum_notu": "",
            "tarih": now,
        })

    analiz = {
        "id": analiz_id,
        "tarih": now,
        "tetik": tetik,  # manuel | haftalik
        "fotograf_tarih": fotograf.get("tarih"),
        "ozet": str(parsed.get("ozet", "")).strip()[:1000],
        "kesif_bulgulari": [str(x)[:400] for x in (parsed.get("kesif_bulgulari") or [])][:10],
        "oneri_sayisi": len(oneri_kayitlari),
        "zayif_dayanak_sayisi": sum(1 for o in oneri_kayitlari if o["zayif_dayanak"]),
    }
    # SINAV MODU (persist=False): sentetik değerlendirme gerçek kuyruğa/karneye KARIŞMAZ
    if persist:
        await db.ai_ceo_analizler.insert_one({**analiz})
        if oneri_kayitlari:
            await db.ai_ceo_oneriler.insert_many([{**o} for o in oneri_kayitlari])
    analiz.pop("_id", None)
    return {"ok": True, "analiz": analiz, "oneriler": [{k: v for k, v in o.items() if k != "_id"} for o in oneri_kayitlari]}


# ─────────────────────────── endpointler ───────────────────────────
@router.post("/ai/ceo/analiz/calistir")
async def analiz_calistir(current_user=Depends(_ADMIN)):
    sonuc = await calistir_analiz("manuel")
    return sonuc


@router.get("/ai/ceo/analiz/son")
async def analiz_son(current_user=Depends(_ADMIN)):
    a = await db.ai_ceo_analizler.find_one({}, {"_id": 0}, sort=[("tarih", -1)])
    if not a:
        return {"analiz": None, "oneriler": []}
    oneriler = await db.ai_ceo_oneriler.find({"analiz_id": a["id"]}, {"_id": 0}).to_list(length=200)
    return {"analiz": a, "oneriler": oneriler}


@router.get("/ai/ceo/analiz/gecmis")
async def analiz_gecmis(current_user=Depends(_ADMIN)):
    docs = await db.ai_ceo_analizler.find({}, {"_id": 0}).sort("tarih", -1).to_list(length=60)
    return {"analizler": docs}


@router.get("/ai/ceo/oneri/{oneri_id}")
async def oneri_detay(oneri_id: str, current_user=Depends(_ADMIN)):
    o = await db.ai_ceo_oneriler.find_one({"id": oneri_id}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Öneri bulunamadı")
    return {"oneri": o}


@router.put("/ai/ceo/oneri/{oneri_id}/durum")
async def oneri_durum(oneri_id: str, govde: dict, current_user=Depends(_ADMIN)):
    durum = govde.get("durum")
    if durum not in DURUMLAR:
        raise HTTPException(status_code=400, detail="Geçersiz durum")
    onceki = await db.ai_ceo_oneriler.find_one({"id": oneri_id}, {"_id": 0, "durum": 1, "oncelik": 1})
    if not onceki:
        raise HTTPException(status_code=404, detail="Öneri bulunamadı")
    guncelle = {"durum": durum, "durum_notu": str(govde.get("not", ""))[:500],
                "durum_tarih": _iso()}
    # Ertele: belirlenen tarihte kuyruğa geri gelir (varsayılan +7 gün)
    if durum == "ertelendi":
        guncelle["ertele_tarih"] = str(govde.get("ertele_tarih") or (simdi() + timedelta(days=7)).isoformat())
    # 'uygulandi' işaretlenince, etki ölçümü için o anki fotoğrafı referansla
    if durum == "uygulandi":
        foto = await son_fotograf()
        guncelle["uygulama_fotograf_tarih"] = foto.get("tarih") if foto else None
    await db.ai_ceo_oneriler.update_one({"id": oneri_id}, {"$set": guncelle})
    # Yönetim skoru: yalnız KARARLI durum (ertele PUAN VERMEZ), ilk kez karara bağlanınca
    if durum in KARARLI_DURUMLAR and onceki.get("durum") not in KARARLI_DURUMLAR:
        from .yonetim import puan_kaydet
        await puan_kaydet(current_user.get("id"), "karar", onceki.get("oncelik", "orta"), oneri_id)
    return {"ok": True, "durum": durum}
