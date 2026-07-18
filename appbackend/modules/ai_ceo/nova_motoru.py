"""AI Squad v1.1 — Nova QA Motoru (çift katman: GERÇEK deterministik kapı + LLM incelemesi).

DÜRÜSTLÜK: Bu backend'de gerçek Playwright/Lighthouse/axe YOK. Bu yüzden Nova'nın sayısal skorları
(lighthouse/a11y) LLM TAHMİNİDİR — raporda ayrı `llm_tahmini` altında ve `olcum_uyarisi` ile
etiketlenir; ASLA "gerçek ölçüm" gibi sunulmaz. deploy_onayi LLM insafına BIRAKILMAZ: gerçek
deterministik kapılar (RBAC eksik rota, XSS/eval deseni) onayı zorla False yapar.

Katman 1 (GERÇEK): rota+auth referansı tespiti (RBAC riski), patch_security.scan_jsx_source (XSS/eval).
Katman 2 (LLM tahmin/inceleme): call_claude(NOVA) → NovaQAResponse. Süreç-içi exec/deploy YOK; çıktı
yalnız rapor (ai_nova_reports). Denetim: islem_kaydet. Uçlar /ai/squad/nova/*."""
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
from .nova_semalar import NovaReviewRequest, NovaQAResponse

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

_AUTH_ISARET = re.compile(r"require_role|get_current_user|Depends\(|current_user|Authorization|Bearer")
_ROTA = re.compile(r"@router\.(get|post|put|delete|patch)", re.IGNORECASE)


def _deterministik_qa(kod: str) -> dict:
    """LLM'den bağımsız GERÇEK sinyaller (uydurma yok)."""
    jsx = patch_security.scan_jsx_source(kod, "nova.jsx")
    rota_var = bool(_ROTA.search(kod))
    auth_var = bool(_AUTH_ISARET.search(kod))
    return {
        "satir_sayisi": len(kod.splitlines()),
        "rota_var": rota_var,
        "auth_referansi_var": auth_var,
        "rbac_riski": rota_var and not auth_var,  # yetki koruması olmayan rota
        "xss_eval_uyarilari": jsx["warnings"],
    }


def _parse_llm(res) -> NovaQAResponse | None:
    if not isinstance(res, dict) or res.get("error"):
        return None
    parsed = res.get("parsed")
    try:
        if isinstance(parsed, dict):
            return NovaQAResponse.model_validate(parsed)
        txt = res.get("text") or ""
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if m:
            return NovaQAResponse.model_validate_json(m.group(0))
    except Exception:
        return None
    return None


@router.post("/ai/squad/nova/incele")
async def nova_incele(govde: NovaReviewRequest, current_user=Depends(_KOORD)):
    """Deterministik QA kapısı + (varsa) Nova LLM incelemesi. deploy_onayi gerçek kapılarla sıkılaşır;
    lighthouse/a11y LLM tahmini olarak etiketlenir (ölçüm değil)."""
    from core.ai import call_claude, GEMINI_API_KEY
    det = _deterministik_qa(govde.kod_blogu)

    llm = None
    if GEMINI_API_KEY:
        try:
            user = (f"İncelenecek kod:\n{govde.kod_blogu[:8000]}\n\n"
                    f"Deterministik sinyaller:\n{json.dumps(det, ensure_ascii=False)}\n\n"
                    "Not: gerçek tarayıcı/Lighthouse çalıştırmıyorsun; sayısal skorlar TAHMİNDİR.")
            res = await call_claude(get_agent_prompt("nova"), user, max_tokens=1500, ozellik="ai_squad_nova")
            llm = _parse_llm(res)
        except Exception as e:
            logging.warning(f"[nova_motoru] LLM inceleme hatası: {e}")
            llm = None

    # GERÇEK deterministik kapılar → deploy onayını zorla düşür
    engelleme = list(llm.engelleme_nedenleri) if llm else []
    if det["rbac_riski"]:
        engelleme.append("RBAC/yetki koruması olmayan rota saptandı (deterministik).")
    if det["xss_eval_uyarilari"]:
        engelleme.extend(det["xss_eval_uyarilari"])
    deterministik_kapi = not det["rbac_riski"] and not det["xss_eval_uyarilari"]
    deploy_onayi = (llm.deploy_onayi if llm else True) and deterministik_kapi

    rapor = {
        "rapor_id": f"rnov_{uuid.uuid4().hex[:6]}", "task_id": govde.task_id, "olusturan": current_user.get("id"),
        "tarih": iso(), "kaynak": "cift_katman" if llm else "deterministik",
        "deterministik_gercek": det,
        "llm_tahmini": ({
            "test_senaryolari": llm.test_senaryolari, "regresyon_riski": llm.regresyon_riski,
            "lighthouse_tahmini_performans": llm.lighthouse_tahmini_performans,
            "a11y_uyumluluk_skoru": llm.a11y_uyumluluk_skoru,
        } if llm else None),
        "olcum_uyarisi": "lighthouse/a11y skorları LLM TAHMİNİDİR — gerçek Playwright/Lighthouse ölçümü değildir.",
        "deploy_onayi": deploy_onayi,
        "engelleme_nedenleri": engelleme,
    }
    await db.ai_nova_reports.insert_one({**rapor})
    rapor.pop("_id", None)
    await islem_kaydet(current_user, "ai_squad", "nova_incele", "nova_report", rapor["rapor_id"], None, None, f"{rapor['kaynak']}/deploy={deploy_onayi}")
    return {"durum": "basarili", "rapor": rapor}


@router.get("/ai/squad/nova/raporlar/{task_id}")
async def nova_raporlar(task_id: str, current_user=Depends(_KOORD)):
    raporlar = await db.ai_nova_reports.find({"task_id": task_id}, {"_id": 0}).sort("tarih", -1).to_list(length=100)
    return {"raporlar": raporlar}
