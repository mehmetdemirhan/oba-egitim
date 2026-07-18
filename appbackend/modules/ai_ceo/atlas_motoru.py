"""AI Squad v1.1 — Atlas Mimari Motoru (çift katman: deterministik statik analiz + LLM yorumu).

Katman 1 (deterministik, GERÇEK): satır/karmaşıklık/import sayımı + core.patch_security.scan_python_source
(projenin gerçek AST güvenlik tarayıcısı). Tehlikeli import/çağrı veya path-traversal → LLM'e SORMADAN
reddet. Katman 2 (LLM): squad_prompts ATLAS promtuyla call_claude → çıktı katı Pydantic sözleşmesinden
geçirilir. LLM yoksa/ayrıştırılamazsa DETERMİNİSTİK-only rapor döner (uydurma LLM analizi ÜRETİLMEZ).

Denetim: core.audit.islem_kaydet (gerçek islem_log). NOT: "kriptografik zincir" burada YOK — Atlas
olaylarını hash-chain'e almak istenirse ayrı bir birleştirme işidir; sahte zincir iddiası yapılmaz."""
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
from .atlas_semalar import AtlasAnalysisRequest, AtlasArchitectureResponse

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

_TRAVERSAL = re.compile(r"\.\.[\\/]")  # gerçek yol-tırmanma deseni (ellipsis '...' tetiklemez)


def _deterministik_statik_olcum(kod: str) -> dict:
    """LLM öncesi %100 deterministik ölçüm + gerçek AST güvenlik taraması (uydurma yok)."""
    tarama = patch_security.scan_python_source(kod, "atlas.py")
    # Sözdizimi hatası = 'kod değil / prose talep' olabilir → güvenlik reddi SAYILMAZ; ayır.
    guvenlik_hatalari = [e for e in tarama["errors"] if "sözdizimi hatası" not in e]
    kod_degil = any("sözdizimi hatası" in e for e in tarama["errors"])
    return {
        "satir_sayisi": len(kod.splitlines()),
        "cyclomatic_complexity": 1 + kod.count("if ") + kod.count("for ") + kod.count("while ") + kod.count(" and ") + kod.count(" or "),
        "import_count": kod.count("import "),
        "path_traversal_risk": bool(_TRAVERSAL.search(kod)),
        "guvenlik_hatalari": guvenlik_hatalari,
        "guvenlik_uyarilari": tarama["warnings"],
        "kod_olarak_ayristirilamadi": kod_degil,
    }


def _parse_llm(res) -> AtlasArchitectureResponse | None:
    if not isinstance(res, dict) or res.get("error"):
        return None
    parsed = res.get("parsed")
    try:
        if isinstance(parsed, dict):
            return AtlasArchitectureResponse.model_validate(parsed)
        txt = res.get("text") or ""
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if m:
            return AtlasArchitectureResponse.model_validate_json(m.group(0))
    except Exception:
        return None
    return None


@router.post("/ai/squad/atlas/analiz-et")
async def atlas_analiz_et(govde: AtlasAnalysisRequest, current_user=Depends(_KOORD)):
    """Deterministik statik analiz + (varsa) Atlas LLM yorumu. Güvenlik ihlali → LLM'siz reddet."""
    from core.ai import call_claude, GEMINI_API_KEY
    statik = _deterministik_statik_olcum(govde.kod_blogu)

    # Katı güvenlik: gerçek tehlikeli import/çağrı ya da yol-tırmanma → doğrudan reddet
    if statik["guvenlik_hatalari"] or statik["path_traversal_risk"]:
        nedenler = list(statik["guvenlik_hatalari"]) + (["path traversal deseni (../)"] if statik["path_traversal_risk"] else [])
        rapor = {"rapor_id": f"ratl_{uuid.uuid4().hex[:6]}", "task_id": govde.task_id, "olusturan": current_user.get("id"),
                 "tarih": iso(), "durum": "reddedildi", "statik_olcumler": statik, "llm_analizi": None,
                 "neden": "Güvenlik engeli: " + "; ".join(nedenler)}
        await db.ai_atlas_reports.insert_one({**rapor})
        rapor.pop("_id", None)
        await islem_kaydet(current_user, "ai_squad", "atlas_reddetti", "atlas_report", rapor["rapor_id"], None, None, rapor["neden"][:150])
        return {"durum": "reddedildi", "rapor": rapor}

    # Katman 2: LLM mimari yorumu (varsa). Yoksa/ayrıştırılamazsa deterministik-only (uydurma yok).
    llm = None
    if GEMINI_API_KEY:
        try:
            user = f"Analiz edilecek kod/talep:\n{govde.kod_blogu[:8000]}\n\nDeterministik ölçümler:\n{json.dumps(statik, ensure_ascii=False)}"
            res = await call_claude(get_agent_prompt("atlas"), user, max_tokens=1500, ozellik="ai_squad_atlas")
            llm = _parse_llm(res)
        except Exception as e:
            logging.warning(f"[atlas_motoru] LLM analizi başarısız: {e}")
            llm = None

    kaynak = "cift_katman" if llm else "deterministik"
    rapor = {
        "rapor_id": f"ratl_{uuid.uuid4().hex[:6]}", "task_id": govde.task_id, "olusturan": current_user.get("id"),
        "tarih": iso(), "durum": "tamam", "kaynak": kaynak,
        "statik_olcumler": statik,
        "llm_analizi": llm.model_dump() if llm else None,
        # LLM yoksa mimari_onay'ı deterministik güvenlikten türet (uydurma karar yok)
        "mimari_onay": llm.mimari_onay if llm else (not statik["guvenlik_hatalari"]),
    }
    await db.ai_atlas_reports.insert_one({**rapor})
    rapor.pop("_id", None)
    await islem_kaydet(current_user, "ai_squad", "atlas_analiz", "atlas_report", rapor["rapor_id"], None, None, f"{kaynak}/onay={rapor['mimari_onay']}")
    return {"durum": "basarili", "rapor": rapor}


@router.get("/ai/squad/atlas/raporlar/{task_id}")
async def atlas_raporlar(task_id: str, current_user=Depends(_KOORD)):
    raporlar = await db.ai_atlas_reports.find({"task_id": task_id}, {"_id": 0}).sort("tarih", -1).to_list(length=100)
    return {"raporlar": raporlar}
