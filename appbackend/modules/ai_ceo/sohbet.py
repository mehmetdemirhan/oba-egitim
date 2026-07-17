"""AI CEO — "Ayda'ya Sor" (rapor bağlamlı sohbet).

Admin, rapor/öneri bağlamında soru sorar → soru + rapor bağlamı + güncel fotoğraf →
Gemini → NET, dayanaklı cevap. Cevaplar da dayanak korumasından geçer (uydurma sayı
tespiti). Konuşma geçmişi bağlama (rapor_id) bağlı saklanır; genel soru da desteklenir.
"""
import json
import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.ai import call_claude
from core.config import GEMINI_API_KEY

from .fotograf import son_fotograf, ai_payload
from .personalar import sistem_promptu
from .analiz import _duz_degerler, _sayisal_kume

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)


def _cevap_dayanak_kontrol(cevap: str, fotograf: dict) -> dict:
    """Cevaptaki sayısal iddiaları fotoğrafa karşı yoklar (halüsinasyon guard)."""
    duz = _duz_degerler(ai_payload(fotograf or {}))
    sayilar = _sayisal_kume(duz)
    # cevaptaki büyük/anlamlı sayılar (yüzde ve tutar benzeri)
    bulunan = re.findall(r"\d+[.,]?\d*", cevap or "")
    dogrulanamayan = []
    for b in bulunan:
        try:
            n = round(float(b.replace(",", ".")), 2)
        except ValueError:
            continue
        if n < 5:  # küçük sayılar (madde no vb.) göz ardı
            continue
        if not any(abs(n - x) <= max(0.5, abs(x) * 0.02) for x in sayilar):
            dogrulanamayan.append(n)
    return {"zayif_dayanak": bool(dogrulanamayan), "dogrulanamayan_sayilar": dogrulanamayan[:8]}


async def _baglam_getir(rapor_id: str | None) -> tuple:
    """(rapor_ozeti, fotograf) — rapor varsa özetini, yoksa boş bağlam."""
    fotograf = await son_fotograf()
    ozet = ""
    if rapor_id:
        rap = await db.ai_ceo_raporlar.find_one({"id": rapor_id}, {"_id": 0})
        if rap:
            ozet = json.dumps({k: rap.get(k) for k in ("tip", "ozet", "gostergeler", "yorum") if k in rap}, ensure_ascii=False)[:2500]
        else:
            an = await db.ai_ceo_analizler.find_one({"id": rapor_id}, {"_id": 0})
            if an:
                ozet = json.dumps({k: an.get(k) for k in ("ozet", "kesif_bulgulari") if k in an}, ensure_ascii=False)[:2500]
    return ozet, fotograf


@router.post("/ai/ceo/sor")
async def ayda_ya_sor(govde: dict, current_user=Depends(_ADMIN)):
    soru = str(govde.get("soru", "")).strip()
    if not soru:
        raise HTTPException(status_code=400, detail="soru gerekli")
    rapor_id = govde.get("rapor_id")
    if not GEMINI_API_KEY:
        return {"ok": False, "sebep": "AI yapılandırılmadı (GEMINI_API_KEY yok)."}

    ozet, fotograf = await _baglam_getir(rapor_id)
    system = sistem_promptu("ayda", "Yöneticinin sorusunu, verilen rapor bağlamı ve güncel "
                            "sistem fotoğrafına dayanarak NET ve KISA yanıtla. Sayı ver, uydurma.")
    user = (
        (f"RAPOR BAĞLAMI:\n{ozet}\n\n" if ozet else "") +
        f"GÜNCEL SİSTEM FOTOĞRAFI:\n{json.dumps(ai_payload(fotograf or {}), ensure_ascii=False)[:6000]}\n\n"
        f"SORU: {soru}\n\nKısa, dayanaklı, düz metin cevap ver."
    )
    res = await call_claude(system, user, max_tokens=1200, ozellik="ceo_sohbet")
    if res.get("error"):
        return {"ok": False, "sebep": res.get("error")}
    cevap = (res.get("text") or "").strip()
    dayanak = _cevap_dayanak_kontrol(cevap, fotograf)

    kayit = {
        "id": str(uuid.uuid4()),
        "rapor_id": rapor_id or "genel",
        "soru": soru[:1000],
        "cevap": cevap[:4000],
        "zayif_dayanak": dayanak["zayif_dayanak"],
        "dogrulanamayan_sayilar": dayanak["dogrulanamayan_sayilar"],
        "soran": current_user.get("id"),
        "tarih": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_ceo_sohbet.insert_one({**kayit})
    kayit.pop("_id", None)
    return {"ok": True, "mesaj": kayit}


@router.get("/ai/ceo/sohbet")
async def sohbet_getir(rapor_id: str = "genel", current_user=Depends(_ADMIN)):
    docs = await db.ai_ceo_sohbet.find({"rapor_id": rapor_id}, {"_id": 0}).sort("tarih", 1).to_list(length=200)
    return {"mesajlar": docs}
