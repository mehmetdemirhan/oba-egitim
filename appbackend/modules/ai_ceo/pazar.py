"""AI CEO — Pazar Araştırması (opsiyonel, Google Search grounding ile).

SEYREK/elle tetiklenir (her analizde DEĞİL) — maliyetlidir. Gemini arama grounding'i
çalışıyorsa rakip platformları KAYNAK LİNKLİ kıyaslar; çalışmıyorsa "yapılandırılmadı"
döner ve UYDURMA analiz üretmez.
"""
import uuid

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.ai import gemini_grounded_call
from core.zaman import iso

from .personalar import sistem_promptu

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

MALIYET_NOTU = ("Pazar araştırması web araması (grounding) kullanır; maliyeti standart "
                "analizden yüksektir. Elle, seyrek tetikleyin (ayda birkaç kez).")


@router.post("/ai/ceo/pazar-arastirma")
async def pazar_arastirma(govde: dict = None, current_user=Depends(_ADMIN)):
    odak = str((govde or {}).get("odak", "")).strip() or (
        "Türkiye'de okuma/hızlı okuma ve eğitim teknolojisi platformları")
    system = sistem_promptu("ayda", "Pazar araştırması yapıyorsun. Yalnız web'de bulduğun, "
                            "KAYNAKLI bilgilere dayan; emin olmadığını yazma.")
    prompt = (
        f"'{odak}' için rakip/benzer platformları araştır. Fiyatlandırma, öne çıkan özellikler, "
        "farklılaşma noktaları ve bizim (bir okuma/eğitim platformu) için 3 somut fırsatı kısaca "
        "özetle. İddiaları web kaynaklarına dayandır."
    )
    sonuc = await gemini_grounded_call(prompt, system, max_tokens=3000)
    if sonuc.get("error") or not sonuc.get("text"):
        # UYDURMA YOK — durumu dürüstçe bildir
        return {"ok": False, "durum": "yapilandirilmadi",
                "sebep": sonuc.get("error") or "Grounding yanıtı boş.",
                "maliyet_notu": MALIYET_NOTU}
    kayit = {
        "id": str(uuid.uuid4()),
        "odak": odak,
        "ozet": sonuc["text"][:8000],
        "kaynaklar": sonuc.get("kaynaklar", [])[:20],
        "model": sonuc.get("model"),
        "tarih": iso(),
    }
    await db.ai_ceo_pazar.insert_one({**kayit})
    kayit.pop("_id", None)
    return {"ok": True, "arastirma": kayit, "maliyet_notu": MALIYET_NOTU}


@router.get("/ai/ceo/pazar-arastirma/gecmis")
async def pazar_gecmis(current_user=Depends(_ADMIN)):
    docs = await db.ai_ceo_pazar.find({}, {"_id": 0}).sort("tarih", -1).to_list(length=50)
    return {"arastirmalar": docs}
