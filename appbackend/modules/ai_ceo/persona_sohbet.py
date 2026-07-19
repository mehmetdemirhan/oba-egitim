"""AI CEO — Birleşik çok-persona sohbeti (FAZ 3, madde 11).

Tek uç, üstte persona seçici mantığı: Ayda / Deniz / Miran + Atlas/Lina/Nova/Ayaz'a "bu kararı
neden verdin" açıklama sorgusu. Her persona SADECE kendi rolüne uygun veriye erişir
(persona-leakage guard: gorunur_mu + veri kapsamı). Ayda'nın "zayıf dayanak" (uydurma sayı)
uyarısı TÜM personalara uygulanır. Miran'da mevcut üslup/ters guard'lar korunur → ihlalde
deterministik güvenli mesaja düşer.

Uçlar: POST /ai/ceo/persona-sor, GET /ai/ceo/persona-sohbet.
"""
import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import get_current_user
from core.ai import call_claude
from core.config import GEMINI_API_KEY
from core.zaman import iso

from .fotograf import son_fotograf, ai_payload
from .personalar import sistem_promptu, gorunur_mu, MIRAN_MUHASEBE_PROMPTU
from .analiz import _duz_degerler, _sayisal_kume
from .sohbet import _baglam_getir, _cevap_dayanak_kontrol
from .miran import ogretmen_odak, _guard_ihlali, _muhasebe_veri, _guard_muhasebe
from . import squad_prompts

router = APIRouter()

# Serbest-sohbet personaları (kendi rolüne uygun veri kapsamıyla)
_CHAT_PERSONALAR = {"ayda", "deniz", "miran"}
# Squad ajanları: yalnız "bu kararı neden verdin" açıklama sorgusu (kendi raporlarından)
_SQUAD_AJANLAR = {
    "atlas": {"kol": "ai_atlas_reports", "ad": "Atlas"},
    "lina": {"kol": "ai_lina_reports", "ad": "Lina"},
    "nova": {"kol": "ai_nova_reports", "ad": "Nova"},
    "ayaz": {"kol": "ai_programmer_tasks", "ad": "Ayaz"},
}


def _dayanak_genel(cevap: str, baglam: dict) -> dict:
    """Zayıf dayanak (uydurma sayı) kontrolünün persona-bağımsız hali: cevaptaki anlamlı sayılar
    verilen bağlam sözlüğündeki sayısal kümede doğrulanabiliyor mu."""
    sayilar = _sayisal_kume(_duz_degerler(baglam or {}))
    dogrulanamayan = []
    for b in re.findall(r"\d+[.,]?\d*", cevap or ""):
        try:
            n = round(float(b.replace(",", ".")), 2)
        except ValueError:
            continue
        if n < 5:
            continue
        if not any(abs(n - x) <= max(0.5, abs(x) * 0.02) for x in sayilar):
            dogrulanamayan.append(n)
    return {"zayif_dayanak": bool(dogrulanamayan), "dogrulanamayan_sayilar": dogrulanamayan[:8]}


def _yetki_kontrol(persona: str, rol: str):
    """Persona-leakage guard: personayı yalnız yetkili rol çağırabilir."""
    if persona in _CHAT_PERSONALAR:
        if not gorunur_mu(persona, rol):
            raise HTTPException(status_code=403, detail=f"'{persona}' personası bu rolde görünmüyor.")
    elif persona in _SQUAD_AJANLAR:
        if rol not in ("admin", "coordinator"):
            raise HTTPException(status_code=403, detail="Squad ajan açıklamaları yalnız admin/koordinatör.")
    else:
        raise HTTPException(status_code=400, detail="Geçersiz persona.")


async def _ayda_baglam(rapor_id):
    ozet, fotograf = await _baglam_getir(rapor_id)
    system = sistem_promptu("ayda", "Yöneticinin sorusunu rapor bağlamı ve güncel fotoğrafa dayanarak "
                            "NET ve KISA yanıtla. Sayı ver, uydurma.")
    user = ((f"RAPOR BAĞLAMI:\n{ozet}\n\n" if ozet else "") +
            f"GÜNCEL SİSTEM FOTOĞRAFI:\n{json.dumps(ai_payload(fotograf or {}), ensure_ascii=False)[:6000]}\n\n")
    return system, user, ai_payload(fotograf or {})


async def _deniz_baglam(soru):
    foto = await son_fotograf()
    denetim = await db.ai_ceo_denetimler.find_one({}, {"_id": 0}, sort=[("tarih", -1)])
    bulgular = await db.ai_ceo_deniz_bulgular.find(
        {}, {"_id": 0, "tur": 1, "onem": 1, "ozet": 1, "durum": 1}).sort("tarih", -1).to_list(length=30)
    baglam = {"son_denetim": denetim or {}, "bulgular": bulgular, "fotograf": ai_payload(foto or {})}
    system = sistem_promptu("deniz", "Denetim bulguları ve sistem fotoğrafına dayanarak bağımsız, nesnel "
                            "yanıt ver. Yalnız verideki kanıta dayan, uydurma.")
    user = f"DENETİM BAĞLAMI:\n{json.dumps(baglam, ensure_ascii=False)[:6000]}\n\n"
    return system, user, baglam


async def _miran_baglam(current_user):
    """Miran: rol-bazlı ters kapsam. teacher→kendi pedagojik/takip verisi; accountant→finansal."""
    rol = current_user.get("role")
    if rol == "accountant":
        veri = await _muhasebe_veri()
        system = MIRAN_MUHASEBE_PROMPTU
        guard = _guard_muhasebe
    else:  # teacher
        oid = current_user.get("linked_id") or current_user.get("id")
        veri = await ogretmen_odak(oid)
        system = sistem_promptu("miran", "Bu öğretmene özel, sıcak ve motive edici yanıt ver.")
        guard = _guard_ihlali
    user = f"KENDİ VERİN:\n{json.dumps(veri, ensure_ascii=False)[:4000]}\n\n"
    return system, user, veri, guard


async def _squad_baglam(persona, task_id):
    cfg = _SQUAD_AJANLAR[persona]
    filtre = {"task_id": task_id} if task_id else {}
    rapor = await db[cfg["kol"]].find_one(filtre, {"_id": 0}, sort=[("tarih", -1)])
    if not rapor:
        rapor = await db[cfg["kol"]].find_one({}, {"_id": 0}, sort=[("tarih", -1)])
    if persona in ("atlas", "lina", "nova"):
        temel = squad_prompts.get_agent_prompt(persona)
    else:
        temel = ("Sen Ayaz'sın: insan-onaylı devir/uygulama sorumlususun. Otomatik deploy YAPMAZSIN. "
                 "Kararlarını dürüstçe açıkla, uydurma.")
    system = temel + ("\n\nGÖREV: Aşağıdaki KENDİ raporundaki kararı sade Türkçeyle AÇIKLA "
                      "(neden bu sonuca vardın). Uydurma; yalnız rapordaki verilere dayan. Düz metin yaz.")
    user = f"RAPORUN:\n{json.dumps(rapor or {}, ensure_ascii=False)[:5000]}\n\nSORU: "
    return system, user, (rapor or {})


@router.post("/ai/ceo/persona-sor")
async def persona_sor(govde: dict, current_user=Depends(get_current_user)):
    persona = str(govde.get("persona", "")).strip().lower()
    soru = str(govde.get("soru", "")).strip()
    if not soru:
        raise HTTPException(status_code=400, detail="soru gerekli")
    _yetki_kontrol(persona, current_user.get("role"))
    if not GEMINI_API_KEY:
        return {"ok": False, "sebep": "AI yapılandırılmadı (GEMINI_API_KEY yok)."}

    guard = None
    if persona == "ayda":
        system, user, baglam = await _ayda_baglam(govde.get("rapor_id"))
    elif persona == "deniz":
        system, user, baglam = await _deniz_baglam(soru)
    elif persona == "miran":
        system, user, baglam, guard = await _miran_baglam(current_user)
    else:  # squad ajanı
        system, user, baglam = await _squad_baglam(persona, govde.get("task_id"))

    user += f"SORU: {soru}\n\nKısa, dayanaklı, düz metin cevap ver."
    res = await call_claude(system, user, max_tokens=1200, ozellik=f"persona_{persona}")
    if res.get("error"):
        return {"ok": False, "sebep": res.get("error")}
    cevap = (res.get("text") or "").strip()
    kaynak = "ai"

    # Miran üslup/ters guard'ı: ihlalde deterministik güvenli mesaja düş (leakage önleme)
    if guard is not None:
        ihlal = guard(cevap)
        if ihlal:
            cevap = ("Bu soruya güvenli çerçevede yanıt veremiyorum (persona kapsamı ihlali: "
                     f"{ihlal}). Lütfen kendi kapsamındaki bir soru sor.")
            kaynak = "deterministik"

    dayanak = _dayanak_genel(cevap, baglam) if kaynak == "ai" else {"zayif_dayanak": False, "dogrulanamayan_sayilar": []}
    kayit = {
        "id": str(uuid.uuid4()), "persona": persona, "soru": soru[:1000], "cevap": cevap[:4000],
        "kaynak": kaynak, "zayif_dayanak": dayanak["zayif_dayanak"],
        "dogrulanamayan_sayilar": dayanak["dogrulanamayan_sayilar"],
        "soran": current_user.get("id"), "tarih": iso(),
    }
    await db.ai_ceo_persona_sohbet.insert_one({**kayit})
    kayit.pop("_id", None)
    return {"ok": True, "mesaj": kayit}


@router.get("/ai/ceo/persona-sohbet")
async def persona_sohbet_gecmis(persona: str = "", current_user=Depends(get_current_user)):
    """Kullanıcının kendi persona sohbet geçmişi (yalnız yetkili olduğu personalar)."""
    if persona:
        _yetki_kontrol(persona.strip().lower(), current_user.get("role"))
    q = {"soran": current_user.get("id")}
    if persona:
        q["persona"] = persona.strip().lower()
    kayitlar = await db.ai_ceo_persona_sohbet.find(q, {"_id": 0}).sort("tarih", -1).to_list(length=50)
    return {"mesajlar": kayitlar}
