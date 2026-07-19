"""AI Yönetim Kokpiti — "Bugün Ne Yapmalıyım" öncelik kuyruğu (FAZ 1).

Dört kaynağı TEK sıralı listede birleştirir:
  1) Ayda'nın karar bekleyenleri   → ai_ceo_proposals (status=awaiting_decision)
  2) Deniz'in bayrakladıkları       → ai_ceo_deniz_bulgular (durum=yeni|gecerli)
  3) Squad'ın reddedilen/takılı'ları → ai_squad_pipeline_runs (asama=reddedildi|durduruldu)
  4) 7 günden eski deploy bekleyen   → squad_deploy_queue (bekliyor + yas>7g)

Sıralama: her öğeye deterministik `oncelik_puani` (0-100) verilir; kritik denetim ve yaşlanan
deploy en üste çıkar. Uydurma yok — tüm alanlar gerçek kayıttan; yaş `core.zaman.gun_farki` ile
aware-normalize edilerek hesaplanır (naive/aware karışımı YASAK).

Uç: /ai/ceo/kokpit/oncelik.
"""
from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso, gun_farki

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

_DEPLOY_ESKI_GUN = 7  # bu yaştan büyük bekleyen deploy "yaşlanmış" sayılır


def _yas_gun(tarih) -> float | None:
    """Kaydın yaşını gün olarak döndürür (aware-normalize; hesaplanamazsa None)."""
    g = gun_farki(tarih)
    return round(g, 1) if g is not None else None


@router.get("/ai/ceo/kokpit/oncelik")
async def oncelik_kuyrugu(current_user=Depends(_ADMIN)):
    """Kokpit açılışında ilk görülen tek sıralı aksiyon listesi (önem sırasına göre)."""
    ogeler = []

    # 1) Ayda — karar bekleyen teklifler
    kararlar = await db.ai_ceo_proposals.find(
        {"status": "awaiting_decision"}, {"_id": 0, "id": 1, "title": 1, "tarih": 1, "veri_kalitesi": 1}
    ).sort("tarih", -1).to_list(length=100)
    for k in kararlar:
        yas = _yas_gun(k.get("tarih"))
        # Yaşlandıkça önem artar; taban 55, +yaş (maks 80). Zayıf veri kalitesi ekstra puan.
        puan = min(80, 55 + int(yas or 0))
        ogeler.append({
            "kaynak": "ayda", "tur": "karar_bekliyor", "hedef_gorunum": "karar",
            "id": k.get("id"), "baslik": k.get("title") or "Karar dosyası",
            "aciklama": "Yönetici kararı bekliyor (onay/ret).", "yas_gun": yas,
            "oncelik_puani": puan,
        })

    # 2) Deniz — açık denetim bulguları (kritik/yüksek daha önemli)
    bulgular = await db.ai_ceo_deniz_bulgular.find(
        {"durum": {"$in": ["yeni", "gecerli"]}}, {"_id": 0, "id": 1, "ozet": 1, "onem": 1, "tarih": 1, "tur": 1}
    ).sort("tarih", -1).to_list(length=100)
    _ONEM_PUAN = {"kritik": 100, "yuksek": 88, "orta": 62, "dusuk": 45}
    for b in bulgular:
        yas = _yas_gun(b.get("tarih"))
        puan = _ONEM_PUAN.get(b.get("onem", "orta"), 62)
        ogeler.append({
            "kaynak": "deniz", "tur": "denetim_bulgusu", "hedef_gorunum": "deniz",
            "id": b.get("id"), "baslik": b.get("ozet") or "Denetim bulgusu",
            "aciklama": f"Deniz bulgusu ({b.get('onem', 'orta')} önem, {b.get('tur', '—')}).",
            "yas_gun": yas, "oncelik_puani": puan,
        })

    # 3) Squad — reddedilen / takılı pipeline'lar
    pipelines = await db.ai_squad_pipeline_runs.find(
        {"asama": {"$in": ["reddedildi", "durduruldu"]}},
        {"_id": 0, "task_id": 1, "asama": 1, "son_not": 1, "guncelleme_tarihi": 1, "tarih": 1}
    ).sort("guncelleme_tarihi", -1).to_list(length=100)
    for p in pipelines:
        yas = _yas_gun(p.get("guncelleme_tarihi") or p.get("tarih"))
        puan = 70 if p.get("asama") == "reddedildi" else 65
        ogeler.append({
            "kaynak": "squad", "tur": f"pipeline_{p.get('asama')}", "hedef_gorunum": "squad",
            "id": p.get("task_id"), "baslik": f"Pipeline {p.get('task_id')}",
            "aciklama": p.get("son_not") or f"Üretim hattı durumu: {p.get('asama')}.",
            "yas_gun": yas, "oncelik_puani": puan,
        })

    # 4) Deploy — 7 günden eski entegrasyon bekleyen kayıtlar
    dq = await db.squad_deploy_queue.find(
        {"durum": "onaylandi_entegrasyon_bekliyor"},
        {"_id": 0, "id": 1, "hedef_dosya": 1, "tarih": 1}
    ).sort("tarih", 1).to_list(length=100)
    for q in dq:
        yas = _yas_gun(q.get("tarih"))
        if yas is None or yas < _DEPLOY_ESKI_GUN:
            continue  # sadece yaşlanmış olanlar öncelik kuyruğuna girer
        puan = min(95, 75 + int(yas - _DEPLOY_ESKI_GUN))  # yaşlandıkça yükselir
        ogeler.append({
            "kaynak": "deploy", "tur": "deploy_yaslandi", "hedef_gorunum": "deploy",
            "id": q.get("id"), "baslik": q.get("hedef_dosya") or "Deploy kaydı",
            "aciklama": f"{int(yas)} gündür entegrasyon bekliyor (git/Vercel manuel adımı).",
            "yas_gun": yas, "oncelik_puani": puan,
        })

    # Önem sırasına göre azalan; eşitlikte yaşça eski önce
    ogeler.sort(key=lambda x: (x["oncelik_puani"], x.get("yas_gun") or 0), reverse=True)

    ozet = {"ayda": len(kararlar), "deniz": len(bulgular), "squad": len(pipelines),
            "deploy_yaslandi": sum(1 for o in ogeler if o["kaynak"] == "deploy")}
    return {"ogeler": ogeler, "toplam": len(ogeler), "kaynak_ozet": ozet, "tarih": iso()}
