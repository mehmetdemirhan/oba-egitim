"""AI Squad v1.2 — GERÇEK ardışık orkestrasyon (Atlas → Lina → Nova → [insan-onaylı Ayaz]).

Her aşama İLGİLİ MOTORU FİİLEN çağırır (uydurma başarı YAZILMAZ) ve GERÇEK sonuçla geçer/durur:
  - Atlas mimari_onay=False veya güvenlik reddi → 'reddedildi'.
  - Lina llm_gerekli → 'durduruldu' (AI yok; uydurma tasarım yok); güvenlik reddi → 'reddedildi';
    aksi halde ÜRETİLEN react_kodu bir sonraki adıma girdi olur.
  - Nova deploy_onayi=False (gerçek RBAC/XSS kapısı dahil) → 'reddedildi'.
  - Üçü de geçerse → 'deploy_bekliyor'. Canlıya alma OTOMATİK DEĞİL: mevcut İNSAN-ONAYLI Ayaz akışıyla
    (patch_manager) yapılır. Orkestratör hiçbir şeyi kendisi deploy ETMEZ.

Sonuç ai_squad_pipeline_runs'a yazılır; denetim core.audit.islem_kaydet (gerçek islem_log). Sahte
'kriptografik zincir' iddiası YOK. Uçlar /ai/squad/orkestrator/*."""
import logging

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso
from core.audit import islem_kaydet
from .atlas_motoru import atlas_analiz_et
from .atlas_semalar import AtlasAnalysisRequest
from .lina_motoru import lina_tasarla
from .lina_semalar import LinaDesignRequest
from .nova_motoru import nova_incele
from .nova_semalar import NovaReviewRequest
from .orkestrator_semalar import PipelineExecutionRequest

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)


async def _bitir(durum: dict, asama: str, not_: str, current_user) -> dict:
    durum["asama"] = asama
    durum["son_not"] = not_
    durum["guncelleme_tarihi"] = iso()
    await db.ai_squad_pipeline_runs.update_one({"task_id": durum["task_id"]}, {"$set": durum}, upsert=True)
    await islem_kaydet(current_user, "ai_squad", "pipeline", "pipeline_run", durum["task_id"], None, None, f"{asama}: {not_[:120]}")
    return durum


@router.post("/ai/squad/orkestrator/pipeline-tetikle")
async def pipeline_tetikle(govde: PipelineExecutionRequest, current_user=Depends(_KOORD)):
    tid = govde.task_id
    logging.info(f"[squad_orkestrator] {tid} akışı başlatıldı.")
    durum = {"task_id": tid, "asama": "atlas", "atlas_onay": False, "lina_uretim": False,
             "nova_vize": False, "deploy_hazir": False, "adimlar": [], "son_not": "Atlas bekleniyor.",
             # FAZ 1 — zincir korelasyonu (Öneri→Karar→Üretim); yoksa None (bağımsız üretim).
             "kaynak_oneri_id": govde.kaynak_oneri_id}

    try:
        # ── ADIM 1: ATLAS (gerçek çağrı) ──
        ar = await atlas_analiz_et(AtlasAnalysisRequest(task_id=tid, kod_blogu=govde.baslangic_kodu or govde.talep_metni), current_user=current_user)
        a_rapor = ar.get("rapor", {})
        if ar.get("durum") == "reddedildi" or not a_rapor.get("mimari_onay"):
            return await _bitir(durum, "reddedildi", f"Atlas onay vermedi: {a_rapor.get('neden') or 'mimari_onay=False'}", current_user)
        durum["atlas_onay"] = True
        durum["adimlar"].append({"ajan": "atlas", "sonuc": "onay", "rapor_id": a_rapor.get("rapor_id"), "kaynak": a_rapor.get("kaynak")})

        # ── ADIM 2: LINA (gerçek çağrı — kod üretir) ──
        lr = await lina_tasarla(LinaDesignRequest(task_id=tid, talep=govde.talep_metni), current_user=current_user)
        # AI yok/erişilemez (llm_gerekli, ai_hatasi) → 500 ÇÖKMESİ YOK; zarifçe dur.
        if lr.get("durum") in ("llm_gerekli", "ai_hatasi"):
            durum["asama"] = "lina"
            return await _bitir(durum, "durduruldu", f"Lina duraklatıldı ({lr.get('durum')}): {lr.get('mesaj', 'AI kullanılamadı')} — uydurma tasarım üretilmedi.", current_user)
        l_rapor = lr.get("rapor", {})
        if lr.get("durum") != "tamam":
            durum["asama"] = "lina"
            return await _bitir(durum, "reddedildi", f"Lina güvenlik reddi: {'; '.join(l_rapor.get('guvenlik_bloklari', []))[:200]}", current_user)
        react_kodu = (l_rapor.get("tasarim", {}) or {}).get("react_kodu", "") or ""
        durum["lina_uretim"] = True
        durum["adimlar"].append({"ajan": "lina", "sonuc": "tamam", "rapor_id": l_rapor.get("rapor_id"), "hedef_dosya": (l_rapor.get("tasarim", {}) or {}).get("hedef_dosya")})

        # ── ADIM 3: NOVA (gerçek çağrı — Lina'nın ürettiği kodu inceler) ──
        nova_girdi = react_kodu if len(react_kodu) >= 10 else govde.talep_metni
        nr = await nova_incele(NovaReviewRequest(task_id=tid, kod_blogu=nova_girdi), current_user=current_user)
        n_rapor = nr.get("rapor", {})
        if not n_rapor.get("deploy_onayi"):
            durum["asama"] = "nova"
            return await _bitir(durum, "reddedildi", f"Nova vize vermedi: {'; '.join(n_rapor.get('engelleme_nedenleri', []))[:200]}", current_user)
        durum["nova_vize"] = True
        durum["adimlar"].append({"ajan": "nova", "sonuc": "vize", "rapor_id": n_rapor.get("rapor_id")})

        # ── ADIM 4: AYAZ — OTOMATİK DEĞİL (insan-onaylı akışa bırakılır) ──
        durum["deploy_hazir"] = True
        durum["asama"] = "ayaz_insan_onayi"
        return await _bitir(durum, "deploy_bekliyor",
                            "Atlas+Lina+Nova geçti. Canlıya alma otomatik DEĞİL: mevcut insan-onaylı Ayaz akışıyla yapılır.", current_user)
    except Exception as e:
        # Herhangi bir motor beklenmedik hata fırlatırsa pipeline 500 ile ÇÖKMESİN; 'hata' ile mühürlensin.
        logging.exception(f"[squad_orkestrator] {tid} motor hatası: {e}")
        return await _bitir(durum, "hata", f"Motor hatası ({durum['asama']}): {str(e)[:200]}", current_user)


@router.get("/ai/squad/orkestrator/durum/{task_id}")
async def pipeline_durum(task_id: str, current_user=Depends(_KOORD)):
    d = await db.ai_squad_pipeline_runs.find_one({"task_id": task_id}, {"_id": 0})
    return {"pipeline": d}


@router.get("/ai/squad/ai-saglik")
async def ai_saglik(current_user=Depends(_KOORD)):
    """GEMINI ayakta mı — tek health-ping. Anahtar DEĞERİ sızdırılmaz; yalnız durum döner.
    'çalışmıyor' sebebinin kod mu yoksa AI anahtarı/kotası mı olduğunu ayırt etmek için."""
    from core.ai import call_claude, GEMINI_API_KEY
    if not GEMINI_API_KEY:
        return {"gemini_ok": False, "mesaj": "GEMINI_API_KEY tanımlı değil (Render env eksik)."}
    try:
        res = await call_claude("Sen bir sağlık kontrolüsün.", "Sadece 'OK' yaz.", max_tokens=10, ozellik="ai_saglik")
        if isinstance(res, dict) and not res.get("error") and (res.get("text") or res.get("parsed")):
            return {"gemini_ok": True, "mesaj": "GEMINI yanıt veriyor — akış çalışır.", "cevap": str(res.get("text") or "")[:80]}
        return {"gemini_ok": False, "mesaj": f"GEMINI reddetti: {(res.get('error') if isinstance(res, dict) else 'bilinmeyen')}"}
    except Exception as e:
        return {"gemini_ok": False, "mesaj": f"GEMINI çağrısı başarısız: {str(e)[:150]}"}
