"""AI CEO Faz 2.5 — Araştıran CEO (tool-calling agent) araçları.

Ayda'nın LLM katmanının karar üretmeden ÖNCE çağırdığı deterministik, salt-okunur, KVKK-güvenli
DB araçları: get_metric (metrik/segment değeri), compare_periods (trend), find_segments (ortalamadan
sapan alt segmentler). Her PUBLIC araç çağrısı ai_ceo_tool_runs'a mühürlenir (audit); iç çağrılar
loglanmaz. UYDURMA YOK: segment kaynağı olmayan metrikte value=None döner, sabit sayı üretilmez.

Not: Şema per-öğrenci kur GEÇMİŞİ tutmadığından yenileme segment-hesaplanamaz; segment-hesaplanabilir
tek metrik veli_memnuniyeti'dir (ai_ceo_nps kur+puan ile etiketli). Diğer metrikler kurum-geneli
fotoğraf değerine düşer (dürüst). tarih daima core.zaman (aware-UTC iso)."""
import re
import uuid

from core.db import db
from core.zaman import iso
from . import fotograf as F


async def log_tool_run(teklif_id: str, tool_name: str, arguments: dict, result) -> dict:
    """Ajan araç çağrısını audit için ai_ceo_tool_runs'a kaydeder."""
    kayit = {"id": str(uuid.uuid4()), "teklif_id": teklif_id or "tarama", "tarih": iso(),
             "tool_name": tool_name, "arguments": arguments, "result": result}
    await db.ai_ceo_tool_runs.insert_one({**kayit})
    kayit.pop("_id", None)
    return kayit


def _kur_q(kur):
    """Serbest string kur alanı için (ör. 'Kur 1') güvenli eşleşme sorgusu."""
    d = re.search(r"\d+", str(kur or ""))
    if d:
        return {"$regex": rf"(^|[^0-9]){d.group()}([^0-9]|$)"}
    return str(kur)


async def _nps_segment(kur=None):
    """Bir kur segmentinin (veya tümünün) NPS ortalaması (0-10). GERÇEK; uydurma yok."""
    q = {}
    if kur is not None:
        q["kur"] = _kur_q(kur)
    puanlar = [d["puan"] async for d in db.ai_ceo_nps.find(q, {"puan": 1, "_id": 0})
               if isinstance(d.get("puan"), (int, float))]
    return len(puanlar), (round(sum(puanlar) / len(puanlar), 2) if puanlar else None)


async def get_metric(metric: str, period: str = "last_90_days", filters: dict = None,
                     teklif_id: str = "tarama", _log: bool = True, _foto: dict = None) -> dict:
    """Bir metriğin (opsiyonel segment) GÜNCEL değerini deterministik hesaplar. veli_memnuniyeti +
    kur → NPS segment ortalaması (gerçek); diğerleri katalog foto_yol'undan kurum-geneli değer."""
    from .karar_zekasi import _katalog, _metrik_deger
    filters = filters or {}
    foto = _foto if _foto is not None else await F.sistem_fotografi()
    kmap = {m["key"]: m for m in await _katalog()}
    m = kmap.get(metric)
    res = {"metric": metric, "period": period, "segment": filters or "genel", "value": None, "sample_size": None}
    if metric == "ogretmen.veli_memnuniyeti" and filters.get("kur") is not None:
        n, deger = await _nps_segment(filters.get("kur"))
        res.update({"value": deger, "sample_size": n, "olcek": "0-10 (NPS)"})
    elif m:
        res["value"] = _metrik_deger(foto, m)
    else:
        res["status"] = "metrik_katalogda_yok"
    if _log:
        await log_tool_run(teklif_id, "get_metric", {"metric": metric, "period": period, "filters": filters}, res)
    return res


async def compare_periods(metric: str, current_period: str = "last_30_days",
                          previous_period: str = "onceki_fotograf", teklif_id: str = "tarama",
                          _log: bool = True) -> dict:
    """Metriğin güncel değeri ile en son KAYITLI fotoğraftaki (gerçek geçmiş) değerini kıyaslar.
    Uydurma trend yok: geçmiş fotoğraf yoksa trend='veri_yetersiz'."""
    from .karar_zekasi import _katalog, _metrik_deger
    foto = await F.sistem_fotografi()
    onceki = await F.son_fotograf()
    m = {mm["key"]: mm for mm in await _katalog()}.get(metric)
    curr = _metrik_deger(foto, m) if m else None
    prev = _metrik_deger(onceki, m) if (m and onceki) else None
    delta = trend = None
    if curr is not None and prev is not None:
        delta = round(float(curr) - float(prev), 1)
        trend = "dusus" if delta < 0 else ("artis" if delta > 0 else "sabit")
    else:
        trend = "veri_yetersiz"
    res = {"metric": metric, "current_value": curr, "previous_value": prev, "delta": delta, "trend": trend,
           "current_period": current_period, "previous_period": previous_period}
    if _log:
        await log_tool_run(teklif_id, "compare_periods", {"metric": metric, "current_period": current_period}, res)
    return res


async def find_segments(target_metric: str, dimensions: list, teklif_id: str = "tarama",
                        _log: bool = True) -> list:
    """Alt segmentlerden kurum ortalamasından anlamlı (>%15) DÜŞÜK sapanları bulur. Yalnız gerçek
    segment kaynağı olan metrik/boyutlarda sonuç üretir; aksi halde boş liste (uydurma yok)."""
    foto = await F.sistem_fotografi()
    bulgular = []
    if any(d in ("kur", "course") for d in (dimensions or [])):
        kurlar = [k for k in await db.students.distinct("kur") if k]
        degerler = []
        for kur in kurlar:
            r = await get_metric(target_metric, filters={"kur": kur}, teklif_id=teklif_id, _log=False, _foto=foto)
            if r.get("value") is not None and (r.get("sample_size") or 0) >= 3:
                degerler.append((kur, float(r["value"]), r.get("sample_size")))
        if degerler:
            ort = sum(v for _, v, _ in degerler) / len(degerler)
            for kur, v, n in degerler:
                sapma = round((v - ort) / ort * 100, 1) if ort else 0.0
                if sapma <= -15:
                    bulgular.append({"segment": f"kur={kur}", "metric": target_metric, "value": v,
                                     "ortalama": round(ort, 2), "sapma_yuzde": sapma, "sample_size": n})
    if _log:
        await log_tool_run(teklif_id, "find_segments", {"target_metric": target_metric, "dimensions": dimensions}, bulgular)
    return bulgular
