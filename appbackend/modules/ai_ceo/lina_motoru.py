"""AI Squad v1.1 — Lina UI/UX Motoru (çift katman: LLM tasarım üretimi + GERÇEK statik JSX taraması).

Lina bir ÜRETİCİDİR: squad_prompts LINA promtuyla call_claude → React/Tailwind JSX üretir; üretilen kod
ardından GERÇEK statik süzgeçten geçirilir:
  - core.patch_security.scan_jsx_source (dangerouslySetInnerHTML/eval/innerHTML/document.write — XSS/eval),
  - + Lina'ya özel: harici URL/CDN <script> yasağı ve hedef_dosya yol doğrulaması (yalnız
    frontend/src/components|pages, .jsx/.js/.tsx/.ts, path-traversal yok).
Bloklayıcı ihlal → durum 'guvenlik_reddetti' (üretilen tasarım kabul edilmez). LLM yoksa 'llm_gerekli'
(Lina üretici olduğundan uydurma tasarım ÜRETİLMEZ). Süreç-içi exec/deploy YOK; çıktı yalnız rapor.
Denetim: core.audit.islem_kaydet. Uçlar /ai/squad/lina/*."""
import json
import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso
from core.audit import islem_kaydet
from core import patch_security
from .squad_prompts import get_agent_prompt
from .lina_semalar import LinaDesignRequest, LinaDesignResponse

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

_IZINLI_KOK = ("frontend/src/components/", "frontend/src/pages/")
_IZINLI_UZANTI = (".jsx", ".js", ".tsx", ".ts")
_HARICI_URL = re.compile(r"https?://", re.IGNORECASE)
_SCRIPT_TAG = re.compile(r"<script\b", re.IGNORECASE)


def _yol_gecerli(yol: str) -> bool:
    if not yol or yol.startswith("/") or "\\" in yol or ".." in yol:
        return False
    return yol.startswith(_IZINLI_KOK) and yol.endswith(_IZINLI_UZANTI)


def _uretilen_kodu_tara(react_kodu: str, hedef_dosya: str) -> list:
    """Üretilen JSX + hedef yolun bloklayıcı ihlallerini döner (GERÇEK; uydurma yok)."""
    bloklar = []
    tarama = patch_security.scan_jsx_source(react_kodu, "lina.jsx")
    bloklar.extend(tarama["warnings"])  # XSS/eval desenleri → Lina için bloklayıcı
    if _HARICI_URL.search(react_kodu):
        bloklar.append("harici URL saptandı (yalnız bağıl /api'ye izin var)")
    if _SCRIPT_TAG.search(react_kodu):
        bloklar.append("<script> etiketi/CDN enjeksiyonu yasak")
    if not _yol_gecerli(hedef_dosya):
        bloklar.append(f"geçersiz hedef_dosya yolu: {hedef_dosya} (yalnız frontend/src/components|pages, .jsx/.js/.tsx/.ts)")
    return bloklar


def _parse_llm(res) -> LinaDesignResponse | None:
    if not isinstance(res, dict) or res.get("error"):
        return None
    parsed = res.get("parsed")
    try:
        if isinstance(parsed, dict):
            return LinaDesignResponse.model_validate(parsed)
        txt = res.get("text") or ""
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if m:
            return LinaDesignResponse.model_validate_json(m.group(0))
    except Exception:
        return None
    return None


@router.post("/ai/squad/lina/tasarla")
async def lina_tasarla(govde: LinaDesignRequest, current_user=Depends(_KOORD)):
    """LINA promtuyla tasarım üretir, üretileni GERÇEK statik süzgeçten geçirir. Bloklayıcı ihlal →
    guvenlik_reddetti; LLM yok → llm_gerekli (uydurma tasarım üretilmez)."""
    from core.ai import call_claude, GEMINI_API_KEY

    if not GEMINI_API_KEY:
        return {"durum": "llm_gerekli", "mesaj": "Lina üretici bir ajandır; tasarım üretmek için AI (GEMINI) gerekir. Uydurma tasarım üretilmez."}

    try:
        user = (f"Talep: {govde.talep}\n"
                f"Hedef dosya ipucu: {govde.hedef_dosya_ipucu or '(yok)'}\n"
                "OBA tasarım dili + güvenlik kurallarına uy; hedef_dosya frontend/src/components|pages altında .jsx olsun.")
        res = await call_claude(get_agent_prompt("lina"), user, max_tokens=2500, ozellik="ai_squad_lina")
        lina = _parse_llm(res)
    except Exception as e:
        logging.warning(f"[lina_motoru] LLM tasarım hatası: {e}")
        lina = None
    if lina is None:
        # AI çağrısı başarısız (geçersiz anahtar/kota/ayrıştırma) → 502 FIRLATMA; zarifçe dur (uydurma yok).
        # Böylece orkestratör tek motor hatasında 500 ile ÇÖKMEZ, 'durduruldu'ya düşer.
        return {"durum": "ai_hatasi", "mesaj": "Lina AI çağrısı başarısız (geçersiz GEMINI anahtarı/kota/ayrıştırma). Uydurma tasarım üretilmez."}

    bloklar = _uretilen_kodu_tara(lina.react_kodu, lina.hedef_dosya)
    durum = "guvenlik_reddetti" if bloklar else "tamam"
    rapor = {
        "rapor_id": f"rlin_{uuid.uuid4().hex[:6]}", "task_id": govde.task_id, "olusturan": current_user.get("id"),
        "tarih": iso(), "durum": durum, "talep": govde.talep,
        "tasarim": lina.model_dump(), "guvenlik_bloklari": bloklar,
    }
    await db.ai_lina_reports.insert_one({**rapor})
    rapor.pop("_id", None)
    await islem_kaydet(current_user, "ai_squad", "lina_tasarla", "lina_report", rapor["rapor_id"], None, None, f"{durum}/{lina.hedef_dosya}")
    return {"durum": durum, "rapor": rapor}


@router.get("/ai/squad/lina/raporlar/{task_id}")
async def lina_raporlar(task_id: str, current_user=Depends(_KOORD)):
    raporlar = await db.ai_lina_reports.find({"task_id": task_id}, {"_id": 0}).sort("tarih", -1).to_list(length=100)
    return {"raporlar": raporlar}
