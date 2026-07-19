"""Deniz denetim kapsam genişletme (FAZ 2, madde 6).

Deniz artık yalnız Ayda'yı değil, zincirin tamamını denetler. HEPSİ DETERMİNİSTİK kurallar —
AI'ya "güven bana" dedirtilmez; her bulgu yeniden hesaplanabilir kanıtla gelir:

  1) karar_dayanak_kontrol   → Karar Zekâsı tekliflerinin kanıt kalitesi (zayıf dayanak oranı)
  2) ayaz_zincir_kontrol     → Ayaz hash-chain audit log tutarlılığı (kriptografik yeniden hesap)
  3) squad_ret_oruntu_kontrol→ Squad ret/onay örüntüsü (bir ajan orantısız mı reddediyor)

Her fonksiyon `{tur, onem, ozet, kanit}` sözlükleri listesi döner; deniz.py::denetle()
id/denetim_id/kaynak/durum/tarih ekleyip ai_ceo_deniz_bulgular'a mühürler.
"""
from collections import defaultdict

from core.db import db

# Ayaz hash-chain'i BİREBİR aynı algoritmayla yeniden hesaplamak için (tek doğruluk kaynağı)
from .ayaz_v1 import _olay_hash, _GENESIS


async def karar_dayanak_kontrol() -> list:
    """Karar Zekâsı tekliflerinde zayıf dayanak oranı. Zayıf = deterministik fallback VEYA
    kanıt boş VEYA veri_kalitesi < 50. ≥3 teklifte oran > %40 ise bulgu."""
    teklifler = await db.ai_ceo_proposals.find(
        {}, {"_id": 0, "id": 1, "_kaynak": 1, "evidence": 1, "veri_kalitesi": 1, "title": 1}
    ).to_list(length=2000)
    toplam = len(teklifler)
    if toplam < 3:
        return []

    def _zayif(t: dict) -> bool:
        vk = t.get("veri_kalitesi")
        return (t.get("_kaynak") == "deterministik"
                or not (t.get("evidence") or [])
                or (isinstance(vk, (int, float)) and vk < 50))

    zayiflar = [t for t in teklifler if _zayif(t)]
    oran = len(zayiflar) * 100 / toplam
    if oran <= 40:
        return []
    onem = "kritik" if oran > 70 else "orta"
    return [{
        "tur": "karar_dayanak_zayifligi", "onem": onem,
        "ozet": f"Karar tekliflerinin %{oran:.0f}'i zayıf dayanaklı (deterministik/boş kanıt/düşük veri kalitesi).",
        "kanit": {"zayif": len(zayiflar), "toplam": toplam,
                  "ornek_id": [t.get("id") for t in zayiflar[:5]]},
    }]


async def ayaz_zincir_kontrol() -> list:
    """Ayaz hash-chain audit log'unu görev bazında yeniden hesaplar; kırılma varsa KRİTİK bulgu.
    Kanıt yeniden üretilebilir: (task_id, kirilma_seq, neden)."""
    task_ids = await db.ayaz_audit.distinct("task_id")
    kirilmalar = []
    for tid in task_ids:
        olaylar = await db.ayaz_audit.find({"task_id": tid}, {"_id": 0}).sort("seq", 1).to_list(length=2000)
        prev = _GENESIS
        for i, e in enumerate(olaylar):
            neden = None
            if e.get("seq") != i:
                neden = "seq boşluğu/atlaması"
            elif e.get("previous_hash") != prev:
                neden = "previous_hash zinciri kopuk"
            else:
                beklenen = _olay_hash(e["task_id"], e["seq"], e["previous_hash"], e["actor"],
                                      e["action"], e["timestamp"], e.get("metadata"))
                if beklenen != e.get("event_hash"):
                    neden = "event_hash yeniden hesaplamayla uyuşmuyor (kayıt değiştirilmiş)"
            if neden:
                kirilmalar.append({"task_id": tid, "kirilma_seq": e.get("seq"), "neden": neden})
                break
            prev = e["event_hash"]
    if not kirilmalar:
        return []
    return [{
        "tur": "ayaz_audit_zincir_kirilmasi", "onem": "kritik",
        "ozet": f"Ayaz hash-chain audit log'unda {len(kirilmalar)} görevde bütünlük kırılması saptandı (olası kayıt değişikliği).",
        "kanit": {"kirilmalar": kirilmalar[:10], "kontrol_edilen_gorev": len(task_ids)},
    }]


async def squad_ret_oruntu_kontrol() -> list:
    """Squad ret örüntüsü: bir ajan reddedilen pipeline'ların orantısız payını mı üretiyor.
    reddedilen pipeline'ların `adimlar` günlüğünden reddeden ajan çıkarılır. ≥3 rette bir ajan
    payı > %60 ise bulgu."""
    redler = await db.ai_squad_pipeline_runs.find(
        {"asama": {"$in": ["reddedildi", "durduruldu"]}},
        {"_id": 0, "task_id": 1, "adimlar": 1, "son_not": 1}
    ).to_list(length=5000)
    toplam_ret = len(redler)
    if toplam_ret < 3:
        return []

    ajan_ret = defaultdict(int)
    for r in redler:
        # reddeden ajan = son 'reddedildi/engelleme' sonuçlu adım; yoksa son adımın ajanı
        reddeden = None
        for adim in reversed(r.get("adimlar") or []):
            sonuc = str(adim.get("sonuc", "")).lower()
            if any(x in sonuc for x in ("red", "engel", "blok", "vize yok", "reddet")):
                reddeden = adim.get("ajan")
                break
        if not reddeden and (r.get("adimlar") or []):
            reddeden = (r["adimlar"][-1] or {}).get("ajan")
        ajan_ret[reddeden or "bilinmiyor"] += 1

    if not ajan_ret:
        return []
    en_cok_ajan, en_cok = max(ajan_ret.items(), key=lambda kv: kv[1])
    pay = en_cok * 100 / toplam_ret
    if pay <= 60:
        return []
    return [{
        "tur": "squad_ret_oruntusu", "onem": "orta",
        "ozet": f"Reddedilen pipeline'ların %{pay:.0f}'i '{en_cok_ajan}' ajanından kaynaklanıyor — orantısız ret örüntüsü (neden incelenmeli).",
        "kanit": {"ajan_ret_dagilimi": dict(ajan_ret), "toplam_ret": toplam_ret,
                  "baskin_ajan": en_cok_ajan, "pay_yuzde": round(pay, 1)},
    }]
