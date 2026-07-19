"""AI Yönetim Kokpiti — gerçek-veri trend grafikleri (FAZ 2, madde 5).

AiCeo dışındaki bileşenlere zaman serisi/karşılaştırma beslemesi:
  - Karar Zekâsı  → net etki (pilot−kontrol) zaman serisi
  - Ajan Karnesi  → ajan başına haftalık skor trendi
  - Deploy Kuyruğu→ onay→entegrasyon ortalama bekleme süresi
  - AI Squad      → pipeline başarı/red oranı zaman serisi

DÜRÜSTLÜK (AgentScorecardReal ilkesi): veri yoksa `yeterli_veri=false` + boş seri döner;
frontend "—" gösterir. ASLA sabit/uydurma sayı üretilmez. Tarihler `core.zaman.aware()` ile
normalize edilir (naive/aware karışımı YASAK).

Uçlar: /ai/ceo/karar/trend, /ai/squad/scorecard/trend, /ai/squad/deploy-queue/bekleme-trend,
/ai/squad/orkestrator/trend.
"""
from collections import defaultdict

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import aware, gun_farki

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Anlamlı trend için asgari nokta sayısı (altında "henüz yeterli veri yok")
_ASGARI_NOKTA = 2


def _hafta(tarih) -> str | None:
    """ISO hafta etiketi 'YYYY-Www' (aware-normalize; çözümlenemezse None)."""
    d = aware(tarih)
    if d is None:
        return None
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


@router.get("/ai/ceo/karar/trend")
async def karar_trend(current_user=Depends(_KOORD)):
    """Uygulanan (implemented) tekliflerin checkpoint ölçümlerinden net etki (pilot−kontrol)
    zaman serisi. Sadece gerçek ölçüm olan noktalar; yoksa yeterli_veri=false."""
    teklifler = await db.ai_ceo_proposals.find(
        {"measurement.olcumler": {"$exists": True, "$ne": []}},
        {"_id": 0, "id": 1, "title": 1, "measurement.olcumler": 1}
    ).to_list(length=500)

    seri = []
    for t in teklifler:
        for o in (t.get("measurement", {}) or {}).get("olcumler", []) or []:
            if o.get("net_etki") is None and o.get("genel_deger") is None:
                continue
            seri.append({
                "tarih": o.get("tarih"), "teklif_id": t.get("id"), "baslik": t.get("title"),
                "gun": o.get("gun"), "net_etki": o.get("net_etki"),
                "pilot": o.get("pilot_deger"), "kontrol": o.get("kontrol_deger"),
                "genel": o.get("genel_deger"),
            })
    seri.sort(key=lambda x: x.get("tarih") or "")
    net_olan = [s for s in seri if s.get("net_etki") is not None]
    return {"seri": seri, "yeterli_veri": len(net_olan) >= _ASGARI_NOKTA,
            "net_nokta_sayisi": len(net_olan), "toplam_nokta": len(seri)}


async def _ajan_hafta_skor(koleksiyon, olumlu_filtre: dict, tarih_alani: str = "tarih") -> list:
    """Bir ajan koleksiyonunu haftaya böl; hafta başına skor (olumlu/toplam) döner."""
    kayitlar = await db[koleksiyon].find({}, {"_id": 0}).to_list(length=20000)
    hafta_top, hafta_ol = defaultdict(int), defaultdict(int)
    for k in kayitlar:
        h = _hafta(k.get(tarih_alani))
        if not h:
            continue
        hafta_top[h] += 1
        if all(k.get(alan) == deger for alan, deger in olumlu_filtre.items()):
            hafta_ol[h] += 1
    return [{"hafta": h, "toplam": hafta_top[h], "olumlu": hafta_ol[h],
             "skor": round(hafta_ol[h] * 100 / hafta_top[h]) if hafta_top[h] else None}
            for h in sorted(hafta_top)]


@router.get("/ai/squad/scorecard/trend")
async def scorecard_trend(current_user=Depends(_KOORD)):
    """Ajan başına haftalık skor trendi (gerçek rapor koleksiyonlarından). Veri yoksa boş seri."""
    atlas = await _ajan_hafta_skor("ai_atlas_reports", {"mimari_onay": True})
    lina = await _ajan_hafta_skor("ai_lina_reports", {"durum": "tamam"})
    nova = await _ajan_hafta_skor("ai_nova_reports", {"deploy_onayi": True})
    # Ayaz: canlida = olumlu (operasyonel patch tablosu)
    ayaz = await _ajan_hafta_skor("ai_programmer_tasks", {"durum": "canlida"})
    ajanlar = {"atlas": atlas, "lina": lina, "nova": nova, "ayaz": ayaz}
    yeterli = any(len(v) >= _ASGARI_NOKTA for v in ajanlar.values())
    return {"ajanlar": ajanlar, "yeterli_veri": yeterli}


@router.get("/ai/squad/deploy-queue/bekleme-trend")
async def deploy_bekleme_trend(current_user=Depends(_KOORD)):
    """Entegre edilen kayıtlarda onay(oluşturma)→entegrasyon ortalama bekleme süresi (gün),
    entegrasyon haftasına göre. Sadece iki tarih de olan kayıtlar."""
    items = await db.squad_deploy_queue.find(
        {"durum": "entegre_edildi", "entegrasyon_tarihi": {"$ne": None}},
        {"_id": 0, "tarih": 1, "entegrasyon_tarihi": 1}
    ).to_list(length=5000)

    hafta_sure = defaultdict(list)
    for it in items:
        bekleme = gun_farki(it.get("tarih"), it.get("entegrasyon_tarihi"))  # entegrasyon − oluşturma
        h = _hafta(it.get("entegrasyon_tarihi"))
        if bekleme is None or bekleme < 0 or not h:
            continue
        hafta_sure[h].append(bekleme)
    seri = [{"hafta": h, "ort_bekleme_gun": round(sum(v) / len(v), 1), "sayi": len(v)}
            for h, v in sorted(hafta_sure.items())]
    return {"seri": seri, "yeterli_veri": len(seri) >= _ASGARI_NOKTA}


@router.get("/ai/squad/orkestrator/trend")
async def orkestrator_trend(current_user=Depends(_KOORD)):
    """Pipeline başarı/red oranı zaman serisi (haftalık). Başarı = deploy'a ulaşan/tamamlanan;
    red = reddedildi/durduruldu. Diğer (koşan) ara aşamalar 'devam' sayılır, oranı bozmaz."""
    runs = await db.ai_squad_pipeline_runs.find(
        {}, {"_id": 0, "asama": 1, "guncelleme_tarihi": 1, "olusturma_tarihi": 1, "tarih": 1}
    ).to_list(length=20000)

    _BASARI = {"deploy_bekliyor", "onaylandi_devir", "tamamlandi"}
    _RED = {"reddedildi", "durduruldu", "hata"}
    hafta = defaultdict(lambda: {"basari": 0, "red": 0, "devam": 0})
    for r in runs:
        h = _hafta(r.get("guncelleme_tarihi") or r.get("olusturma_tarihi") or r.get("tarih"))
        if not h:
            continue
        asama = r.get("asama")
        if asama in _BASARI:
            hafta[h]["basari"] += 1
        elif asama in _RED:
            hafta[h]["red"] += 1
        else:
            hafta[h]["devam"] += 1
    seri = []
    for h in sorted(hafta):
        d = hafta[h]
        karara_baglanan = d["basari"] + d["red"]
        seri.append({"hafta": h, "basari": d["basari"], "red": d["red"], "devam": d["devam"],
                     "toplam": d["basari"] + d["red"] + d["devam"],
                     "basari_orani": round(d["basari"] * 100 / karara_baglanan) if karara_baglanan else None})
    return {"seri": seri, "yeterli_veri": len(seri) >= _ASGARI_NOKTA}
