"""AI Yönetim Kokpiti — durum şeridi + Yaşam Döngüsü Zinciri (FAZ 1).

Amaç: 7 bağımsız AI bileşenini (Ayda / Karar Zekâsı / Squad / Ayaz / Deploy / Deniz / Karne) tek
bakışta özetlemek ve aralarındaki zinciri `kaynak_oneri_id` korelasyonuyla görünür kılmak.

DÜRÜSTLÜK İLKESİ (AgentScorecardReal ile birebir): tüm sayımlar canlı koleksiyonlardan gelir;
veri yoksa None/0 döner, ASLA uydurma sabit üretilmez. Zincirdeki Denetim (Deniz) ve Skor
(Scorecard) alt sistemleri öğe-bazlı değil AGREGAT çalışır — bu yüzden zincir kartında bunlar
"sistem geneli" bağlam olarak işaretlenir (per-öneri sahte bağ kurulmaz).

Uçlar: /ai/ceo/kokpit/*.
"""
from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso

from .fotograf import son_fotograf, saglik_skoru
from .agent_scorecard_real import scorecard_ozet

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Pipeline'ın "canlı/aktif" sayıldığı asamalar (terminal olmayanlar).
_AKTIF_ASAMALAR = ["atlas", "lina", "nova", "deploy_bekliyor", "onaylandi_devir"]
# Deniz'de "açık" (aksiyon bekleyen) bulgu durumları.
_ACIK_BULGU = ["yeni", "gecerli"]
# Deploy kuyruğunda entegrasyon bekleyen durum.
_DEPLOY_BEKLEYEN = "onaylandi_entegrasyon_bekliyor"


@router.get("/ai/ceo/kokpit/ozet")
async def kokpit_ozet(current_user=Depends(_ADMIN)):
    """Üst durum şeridi: Ayda sağlığı, Deniz denetim durumu, Squad aktif pipeline,
    Deploy bekleyen, kritik riskli ajan sayısı — hepsi gerçek veriden."""
    # 1) Ayda sağlık skoru (deterministik, son fotoğraftan)
    foto = await son_fotograf()
    saglik = saglik_skoru(foto) if foto else {"skor": None, "bilesenler": []}

    # 2) Deniz denetim durumu
    son_denetim = await db.ai_ceo_denetimler.find_one({}, {"_id": 0}, sort=[("tarih", -1)])
    acik_bulgu = await db.ai_ceo_deniz_bulgular.count_documents({"durum": {"$in": _ACIK_BULGU}})
    kritik_bulgu = await db.ai_ceo_deniz_bulgular.count_documents(
        {"durum": {"$in": _ACIK_BULGU}, "onem": {"$in": ["kritik", "yuksek"]}})

    # 3) Squad aktif pipeline sayısı
    squad_aktif = await db.ai_squad_pipeline_runs.count_documents({"asama": {"$in": _AKTIF_ASAMALAR}})

    # 4) Deploy kuyruğunda entegrasyon bekleyen
    deploy_bekleyen = await db.squad_deploy_queue.count_documents({"durum": _DEPLOY_BEKLEYEN})

    # 5) Kritik riskli ajan sayısı (Scorecard read-model'ini yeniden kullan — DRY, tek doğruluk kaynağı)
    karne = await scorecard_ozet(current_user=current_user)
    kritik_ajan = sum(1 for a in karne.agent_matrix if a.risk == "critical")

    return {
        "ayda_saglik": saglik.get("skor"),
        "deniz": {
            "son_denetim_tarih": (son_denetim or {}).get("tarih"),
            "acik_bulgu": acik_bulgu,
            "kritik_bulgu": kritik_bulgu,
        },
        "squad_aktif_pipeline": squad_aktif,
        "deploy_bekleyen": deploy_bekleyen,
        "kritik_risk_ajan": kritik_ajan,
        "ajan_sayisi": len(karne.agent_matrix),
        "tarih": iso(),
    }


def _stage(var: bool, **kv) -> dict:
    """Zincir aşaması kartı — 'var' bağ olup olmadığını, kv detayları taşır."""
    return {"var": var, **kv}


@router.get("/ai/ceo/kokpit/zincir")
async def kokpit_zincir(limit: int = 20, current_user=Depends(_ADMIN)):
    """Yaşam Döngüsü Zinciri: Öneri (Ayda) → Karar → Üretim (Squad) → Deploy — hepsi
    `kaynak_oneri_id` korelasyonuyla bağlanır. Denetim + Skor alt sistemleri agregat çalıştığı
    için per-zincir değil 'sistem geneli' bağlam olarak status şeridinden okunur.

    Bağ pivotu KARAR kaydıdır (ai_ceo_proposals): yukarı Ayda önerisine (kaynak_oneri_id),
    aşağı pipeline + deploy kuyruğuna (aynı kaynak_oneri_id) bağlanır. Korelasyonsuz (eski/bağımsız)
    kararlar tek-aşamalı zincir olarak gösterilir (geriye dönük uyumlu)."""
    limit = max(1, min(int(limit or 20), 100))
    kararlar = await db.ai_ceo_proposals.find({}, {"_id": 0}).sort("tarih", -1).to_list(length=limit)

    # Korelasyon köklerini topla (kaynak_oneri_id set'i) → tek sorguyla üretim/deploy çek
    kokler = [k.get("kaynak_oneri_id") for k in kararlar if k.get("kaynak_oneri_id")]
    oneri_map, uretim_map, deploy_map = {}, {}, {}
    if kokler:
        for o in await db.ai_ceo_oneriler.find({"id": {"$in": kokler}}, {"_id": 0}).to_list(length=limit):
            oneri_map[o["id"]] = o
        for p in await db.ai_squad_pipeline_runs.find({"kaynak_oneri_id": {"$in": kokler}}, {"_id": 0}).to_list(length=limit * 3):
            uretim_map.setdefault(p["kaynak_oneri_id"], p)  # en yeni değil ama tek temsilci yeterli
        for dq in await db.squad_deploy_queue.find({"kaynak_oneri_id": {"$in": kokler}}, {"_id": 0}).to_list(length=limit * 3):
            deploy_map.setdefault(dq["kaynak_oneri_id"], dq)

    zincirler = []
    for k in kararlar:
        kok = k.get("kaynak_oneri_id")
        oneri = oneri_map.get(kok) if kok else None
        uretim = uretim_map.get(kok) if kok else None
        deploy = deploy_map.get(kok) if kok else None
        zincirler.append({
            "kaynak_oneri_id": kok,
            "oneri": _stage(bool(oneri), id=(oneri or {}).get("id"), baslik=(oneri or {}).get("baslik"),
                            durum=(oneri or {}).get("durum"), tarih=(oneri or {}).get("tarih"),
                            hedef_gorunum="ayda") if oneri else _stage(False, hedef_gorunum="ayda"),
            "karar": _stage(True, id=k.get("id"), baslik=k.get("title"), durum=k.get("status"),
                            tarih=k.get("tarih"), hedef_gorunum="karar"),
            "uretim": _stage(bool(uretim), id=(uretim or {}).get("task_id"), durum=(uretim or {}).get("asama"),
                             tarih=(uretim or {}).get("guncelleme_tarihi") or (uretim or {}).get("tarih"),
                             hedef_gorunum="squad") if uretim else _stage(False, hedef_gorunum="squad"),
            "deploy": _stage(bool(deploy), id=(deploy or {}).get("id"), durum=(deploy or {}).get("durum"),
                             tarih=(deploy or {}).get("tarih"), hedef_gorunum="deploy") if deploy else _stage(False, hedef_gorunum="deploy"),
            "tarih": k.get("tarih"),
        })

    return {"zincirler": zincirler, "sayi": len(zincirler), "tarih": iso(),
            "not": "Denetim (Deniz) + Skor (Scorecard) agregat çalışır; per-zincir değil status şeridinden okunur."}
