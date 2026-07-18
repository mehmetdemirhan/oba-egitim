"""AI CEO — Kurumsal Karar Zekâsı & Öğrenen Yönetim (Faz 2).

Ayda'yı statik rapordan çıkarıp: (1) Semantik Metrik Kataloğu (ai_ceo_metric_catalog),
(2) GERÇEK sistem fotoğrafından (fotograf.sistem_fotografi — KVKK takma-id, deterministik)
kanıta-dayalı yapılandırılmış teklif (ai_ceo_proposals), (3) Kurumsal/karar hafızası
(ai_ceo_institution_memory), (4) kontrollü pilot/ölçüm + öğrenme döngüsü (learning) ile
çalıştıran omurga.

KURALLAR (CLAUDE.md/KVKK/determinizm): Kanıt sayıları YALNIZ gerçek fotoğraftan gelir; AI
ayrıştırılamazsa deterministik taslak (uydurma sayı YOK). Tarih daima core.zaman (aware-UTC,
iso()). AI'a yalnız fotograf.ai_payload (agregat, takma-id) gider. Yollar /ai/ceo/karar/*.
"""
import json
import random
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Body

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso
from core.audit import islem_kaydet
from core.temizlik import yas_gun, throttle_gunluk
from . import fotograf as F

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
_ADMIN = require_role(UserRole.ADMIN)

# ─────────────────────────── Semantik Metrik Kataloğu ───────────────────────────
# foto_yol: gerçek fotoğraf içindeki değerin yolu (grounding — deterministik motor buradan okur)
VARSAYILAN_METRIKLER = [
    {"key": "ogretmen.yenileme_orani", "name": "Öğrenci yenileme oranı",
     "description": "Kuru biten öğrencinin üst kura geçme oranı.", "formula": "gecen / uygun * 100",
     "unit": "percent", "direction": "higher_is_better", "minimum_sample": 20,
     "warning_threshold": 45.0, "target": 55.0, "foto_yol": ["ogretmen", "yenileme_orani_yuzde"]},
    {"key": "muhasebe.tahsilat_orani", "name": "Tahsilat oranı",
     "description": "Tahsil edilen / beklenen tahsilat.", "formula": "tahsil / beklenen * 100",
     "unit": "percent", "direction": "higher_is_better", "minimum_sample": 10,
     "warning_threshold": 80.0, "target": 95.0, "foto_yol": None},
    {"key": "muhasebe.bekleyen_tahsilat", "name": "Bekleyen tahsilat",
     "description": "Henüz tahsil edilmemiş açık alacak.", "formula": "beklenen - tahsil",
     "unit": "currency", "direction": "lower_is_better", "minimum_sample": 1,
     "warning_threshold": 50000.0, "target": 0.0, "foto_yol": ["muhasebe", "bekleyen_tahsilat"]},
    {"key": "ogretmen.geciken_kur", "name": "Geciken kur sayısı",
     "description": "Hedef süreyi aşmış açık kur sayısı.", "formula": "count(geciken)",
     "unit": "count", "direction": "lower_is_better", "minimum_sample": 1,
     "warning_threshold": 10.0, "target": 0.0, "foto_yol": ["ogretmen", "geciken_kur_sayisi"]},
    {"key": "kullanim.gorev_tamamlama", "name": "Görev tamamlama oranı",
     "description": "Atanan görevlerin tamamlanma yüzdesi.", "formula": "biten / toplam * 100",
     "unit": "percent", "direction": "higher_is_better", "minimum_sample": 20,
     "warning_threshold": 60.0, "target": 80.0, "foto_yol": ["kullanim", "gorev_tamamlama_yuzde"]},
    {"key": "ogretmen.veli_memnuniyeti", "name": "Veli memnuniyeti (5)",
     "description": "Veli memnuniyeti (5 üzerinden).", "formula": "ort(anket)",
     "unit": "count", "direction": "higher_is_better", "minimum_sample": 10,
     "warning_threshold": 3.5, "target": 4.5, "foto_yol": ["ogretmen", "veli_memnuniyeti_5uzerinden"]},
]


def _yol_oku(foto: dict, yol):
    if not yol:
        return None
    v = foto
    for k in yol:
        if not isinstance(v, dict):
            return None
        v = v.get(k)
    return v


def _tahsilat_orani(foto: dict):
    m = foto.get("muhasebe", {}) or {}
    bek = m.get("beklenen_tahsilat"); tah = m.get("tahsil_edilen")
    try:
        bek = float(bek); tah = float(tah)
    except (TypeError, ValueError):
        return None
    return round(tah * 100 / bek, 1) if bek > 0 else None


def _metrik_deger(foto: dict, m: dict):
    if m["key"] == "muhasebe.tahsilat_orani":
        return _tahsilat_orani(foto)
    v = _yol_oku(foto, m.get("foto_yol"))
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


async def _katalog(seed=True):
    docs = await db.ai_ceo_metric_catalog.find({}, {"_id": 0}).to_list(length=500)
    if not docs and seed:
        now = iso()
        for m in VARSAYILAN_METRIKLER:
            await db.ai_ceo_metric_catalog.update_one(
                {"key": m["key"]}, {"$set": {**m, "olusturma_tarihi": now}}, upsert=True)
        docs = await db.ai_ceo_metric_catalog.find({}, {"_id": 0}).to_list(length=500)
    return docs


def _veri_kalitesi(foto: dict) -> float:
    """Fotoğraf bloklarından hatasız/dolu olanların oranı → 0-100 (deterministik)."""
    bloklar = ["ogretmen", "muhasebe", "ogrenci", "kullanim", "birim_ekonomi", "nps"]
    dolu = sum(1 for b in bloklar if isinstance(foto.get(b), dict) and not foto[b].get("_hata"))
    return round(dolu * 100 / len(bloklar), 1)


def _ihlal_eden_metrikler(foto: dict, katalog: list):
    """Eşiği aşan (kötü yöndeki) metrikleri, sapma büyüklüğüne göre sıralı döndürür — GERÇEK."""
    liste = []
    for m in katalog:
        v = _metrik_deger(foto, m)
        if v is None:
            continue
        esik = m.get("warning_threshold")
        if esik is None:
            continue
        kotu = (m.get("direction") == "higher_is_better" and v < esik) or \
               (m.get("direction") == "lower_is_better" and v > esik)
        if kotu:
            sapma = abs(v - esik) / (abs(esik) or 1.0)
            liste.append({"metrik": m, "deger": v, "esik": esik, "sapma": round(sapma, 3)})
    return sorted(liste, key=lambda x: -x["sapma"])


# ─────────────────────────── Teklif üretimi ───────────────────────────
def _ayda_sistem_prompt():
    return (
        "Sen OBA Eğitim'in Karar Zekâsı ve Öğrenen Yönetim Sistemini yöneten CEO 'Ayda'sın. "
        "6 aşamalı derin analiz yaparsın: (1) Tarama, (2) Önem, (3) Derinleştirme (segment), "
        "(4) Kök neden hipotezleri, (5) Alternatif çözümler (maliyet/etki/risk), (6) Öz eleştiri. "
        "KESİN KURALLAR: Kanıttaki sayıları YALNIZCA sana verilen SİSTEM FOTOĞRAFI'ndan al — "
        "asla sayı UYDURMA. Emin olmadığın alanı null bırak. Çıktın bir 'fikir' değil; kontrol/"
        "pilot gruplu, bütçeli, ölçülebilir bir yönetim DENEYİ dosyasıdır. YALNIZ geçerli JSON dön."
    )


def _teklif_json_sema():
    return (
        '{"title": str, '
        '"problem": {"statement": str, "severity_score": int(0-100), "affected_population": int, "estimated_annual_loss": float}, '
        '"evidence": [{"metric": str, "segment": str, "current": float, "previous": float|null, "confidence": float(0-1), "sample_size": int, "data_quality_score": float}], '
        '"hypotheses": [{"statement": str, "support": "high|medium|low", "evidence_ids": [str], "test": str}], '
        '"alternatives": [{"name": str, "cost": float, "effort": "low|medium|high", "expected_effect": str, "risk": str}], '
        '"recommendation": {"selected_alternative": str, "rationale": str, "confidence": float(0-1)}, '
        '"implementation": {"owner_role": str, "pilot_size": int, "duration_days": int, "steps": [str], "estimated_cost": float}, '
        '"measurement": {"primary_metric": str, "baseline": float, "target": float, "guardrail_metrics": [str], "checkpoints": [int], "stop_conditions": [str]}}'
    )


def _deterministik_teklif(foto: dict, katalog: list, onceki: dict | None):
    """AI yoksa/ayrıştırılamazsa: GERÇEK en kötü metrikten uydurma sayı OLMADAN taslak teklif."""
    ihlaller = _ihlal_eden_metrikler(foto, katalog)
    vk = _veri_kalitesi(foto)
    if not ihlaller:
        return {
            "title": "Belirgin eşik ihlali yok — izleme önerisi",
            "problem": {"statement": "Katalogdaki metrikler eşik içinde; acil müdahale gerektiren sapma saptanmadı.",
                        "severity_score": 10, "affected_population": 0, "estimated_annual_loss": 0.0},
            "evidence": [], "hypotheses": [],
            "alternatives": [{"name": "Mevcut izlemeyi sürdür", "cost": 0.0, "effort": "low", "expected_effect": "low", "risk": "low"}],
            "recommendation": {"selected_alternative": "Mevcut izlemeyi sürdür", "rationale": "Sapma yok; veri toplamaya devam.", "confidence": round(vk / 100, 2)},
            "implementation": {"owner_role": "coordinator", "pilot_size": 0, "duration_days": 0, "steps": [], "estimated_cost": 0.0},
            "measurement": {"primary_metric": "", "baseline": None, "target": None, "guardrail_metrics": [], "checkpoints": [], "stop_conditions": []},
            "_kaynak": "deterministik", "_not": "Eşik ihlali yok.",
        }
    en = ihlaller[0]
    m = en["metrik"]
    onceki_deger = _metrik_deger(onceki, m) if onceki else None
    return {
        "title": f"{m['name']} eşik altında — kontrollü iyileştirme önerisi",
        "problem": {"statement": f"{m['name']} = {en['deger']} (eşik {en['esik']}, yön {m['direction']}). Sapma {round(en['sapma']*100)}%.",
                    "severity_score": min(95, 40 + round(en["sapma"] * 40)), "affected_population": None, "estimated_annual_loss": None},
        "evidence": [{"metric": m["key"], "segment": "genel", "current": en["deger"], "previous": onceki_deger,
                      "confidence": round(vk / 100, 2), "sample_size": None, "data_quality_score": vk}],
        "hypotheses": [{"statement": f"{m['name']} düşüşünün kök nedeni segment/süreç kırılımında aranmalı.",
                        "support": "medium", "evidence_ids": [m["key"]], "test": "Kontrollü pilot ile doğrula"}],
        "alternatives": [{"name": "Hedefli pilot müdahale", "cost": None, "effort": "medium", "expected_effect": "orta-yüksek", "risk": "düşük"}],
        "recommendation": {"selected_alternative": "Hedefli pilot müdahale",
                           "rationale": "Determinist taslak: en yüksek sapmalı metrik önceliklendirildi. AI derin analizi için tekrar tetikleyin.",
                           "confidence": round(vk / 100, 2)},
        "implementation": {"owner_role": "coordinator", "pilot_size": None, "duration_days": 45, "steps": ["Segment kırılımını çıkar", "Pilot/kontrol grubu tanımla"], "estimated_cost": None},
        "measurement": {"primary_metric": m["key"], "baseline": en["deger"], "target": m.get("target"),
                        "guardrail_metrics": [], "checkpoints": [14, 30, 45], "stop_conditions": []},
        "_kaynak": "deterministik", "_not": "AI ayrıştırılamadı veya kullanılamıyor; gerçek metrikten taslak.",
    }


async def karar_teklifi_uret() -> dict:
    """GERÇEK fotoğraf + kurumsal hafıza + geçmiş dersler → yapılandırılmış teklif. AI JSON'u
    doğrulanır; ayrıştırılamazsa deterministik taslağa düşer (uydurma yok)."""
    from core.ai import call_claude, GEMINI_API_KEY
    foto = await F.sistem_fotografi()
    onceki = await F.son_fotograf()  # trend için en son kayıtlı fotoğraf
    katalog = await _katalog()
    payload = F.ai_payload(foto)
    vk = _veri_kalitesi(foto)

    hafiza = [f"[{h.get('type','').upper()}] {h.get('key')}: {h.get('statement')}"
              async for h in db.ai_ceo_institution_memory.find({"approved": True}, {"_id": 0}).limit(30)]
    dersler = [d.get("learning", {}).get("lesson") for d in
               await db.ai_ceo_proposals.find({"learning.lesson": {"$exists": True}}, {"_id": 0, "learning": 1})
               .sort("tarih", -1).limit(3).to_list(length=3)]

    teklif = None
    if GEMINI_API_KEY:
        user = (
            f"[SİSTEM FOTOĞRAFI — kanıt sayıları YALNIZ buradan]\n{json.dumps(payload, ensure_ascii=False)[:8000]}\n\n"
            f"[ONAYLI KURUMSAL HAFIZA]\n{json.dumps(hafiza, ensure_ascii=False)}\n\n"
            f"[GEÇMİŞ DERSLER]\n{json.dumps([d for d in dersler if d], ensure_ascii=False)}\n\n"
            f"Aşağıdaki JSON şemasında TEK teklif üret (başka metin yok):\n{_teklif_json_sema()}"
        )
        try:
            res = await call_claude(_ayda_sistem_prompt(), user, max_tokens=3000, ozellik="ai_ceo_karar")
            parsed = res.get("parsed") if isinstance(res, dict) else None
            if not parsed and isinstance(res, dict) and res.get("text"):
                import re as _re
                mt = _re.search(r"\{.*\}", res["text"], _re.DOTALL)
                if mt:
                    parsed = json.loads(mt.group(0))
            if isinstance(parsed, dict) and parsed.get("title") and parsed.get("recommendation"):
                teklif = parsed
                teklif["_kaynak"] = "ai"
        except Exception:
            teklif = None

    if teklif is None:
        teklif = _deterministik_teklif(foto, katalog, onceki)

    # Kanonik alanlar (id/tarih/durum) + veri kalitesi işareti
    teklif["id"] = str(uuid.uuid4())
    teklif["tarih"] = iso()
    teklif["persona"] = "Ayda"
    teklif["status"] = "awaiting_decision"
    teklif["veri_kalitesi"] = vk
    teklif["fotograf_id"] = foto.get("id")
    await db.ai_ceo_proposals.insert_one({**teklif})
    teklif.pop("_id", None)
    return teklif


# ─────────────────────── Faz 3: otonom deney grupları + segment ölçüm ───────────────────────
def _hedef_kur_regex(teklif: dict):
    """Teklif başlığı/probleminden 'Kur N' segmentini çıkarır → students.kur (serbest string) için
    tam-sayı token regex'i. Segment yoksa None (tüm aktif kitle)."""
    metin = f"{teklif.get('title', '')} {teklif.get('problem', {}).get('statement', '')}".lower()
    m = re.search(r"kur\s*(\d+)", metin)
    if not m:
        return None
    return {"$regex": rf"(^|[^0-9]){m.group(1)}([^0-9]|$)"}


async def _deney_gruplarini_olustur(teklif: dict) -> dict:
    """Onaylanan teklifin segmentine uyan AKTİF öğrencileri (arsivli/mezun değil) rastgele ~%50
    pilot / %50 kontrol olarak böler ve db.students.ai_experiments'e teklif_id ile mühürler.
    Idempotent ($addToSet). Segment yoksa tüm aktif kitle. GERÇEK alanlar; uydurma yok."""
    teklif_id = teklif["id"]
    filtre = {"arsivli": {"$ne": True}, "mezun": {"$ne": True}}
    kur_regex = _hedef_kur_regex(teklif)
    if kur_regex:
        filtre["kur"] = kur_regex
    ogrenciler = await db.students.find(filtre, {"id": 1}).to_list(length=100000)
    if not ogrenciler:
        return {"pilot": 0, "kontrol": 0}
    random.shuffle(ogrenciler)
    hedef = teklif.get("implementation", {}).get("pilot_size")
    hedef = int(hedef) if isinstance(hedef, (int, float)) and hedef else len(ogrenciler) // 2
    sinir = max(1, min(hedef, len(ogrenciler) // 2)) if len(ogrenciler) > 1 else 1
    pilot_ids = [s["id"] for s in ogrenciler[:sinir]]
    kontrol_ids = [s["id"] for s in ogrenciler[sinir:sinir * 2]]
    if pilot_ids:
        await db.students.update_many({"id": {"$in": pilot_ids}}, {"$addToSet": {"ai_experiments.pilot_groups": teklif_id}})
    if kontrol_ids:
        await db.students.update_many({"id": {"$in": kontrol_ids}}, {"$addToSet": {"ai_experiments.control_groups": teklif_id}})
    return {"pilot": len(pilot_ids), "kontrol": len(kontrol_ids)}


async def _segment_bazli_metrik_hesapla(ogrenci_ids: list, m: dict, global_foto: dict):
    """Bir öğrenci kümesinin (pilot/kontrol) birincil metriğini deterministik hesaplar. Şimdilik
    yalnız YENİLEME segment-hesaplanabilir (kur seviyesi); segment kaynağı olmayan metrikler
    dürüstçe kurum-geneli değere düşer (pilot=kontrol → net etki 0; UYDURMA YOK)."""
    if not ogrenci_ids or not m:
        return None
    if m["key"] == "ogretmen.yenileme_orani":
        toplam = yenileyen = 0
        async for s in db.students.find({"id": {"$in": ogrenci_ids}}, {"kur": 1}):
            toplam += 1
            mt = re.search(r"\d+", str(s.get("kur") or ""))
            if mt and int(mt.group()) > 1:
                yenileyen += 1
        return round(yenileyen * 100 / toplam, 1) if toplam else None
    return _metrik_deger(global_foto, m)  # segment kaynağı yok → kurum-geneli (dürüst)


def _ilerleme(deg, b, tg):
    try:
        if deg is not None and b is not None and tg is not None and (float(tg) - float(b)) != 0:
            return round((float(deg) - float(b)) / (float(tg) - float(b)) * 100, 1)
    except (TypeError, ValueError):
        pass
    return None


async def olcum_calistir() -> dict:
    """Uygulamadaki (implemented) tekliflerde, kontrol noktalarında (checkpoints) birincil metriği
    kurum-geneli + PİLOT + KONTROL segmentlerinde GERÇEK ver'den ölçer; hedefe ilerlemeyi ve net
    deney etkisini (pilot−kontrol) kaydeder. Idempotent (gün tekrar ölçülmez). Uydurma yok."""
    foto = await F.sistem_fotografi()
    katalog = await _katalog()
    kmap = {m["key"]: m for m in katalog}
    guncellenen = 0
    proposals = await db.ai_ceo_proposals.find({"status": "implemented"}, {"_id": 0}).to_list(length=2000)
    for t in proposals:
        yas = yas_gun(t.get("uygulama_tarihi"))
        if yas is None:
            continue
        meas = t.get("measurement") or {}
        checkpoints = [c for c in (meas.get("checkpoints") or []) if isinstance(c, (int, float))]
        olcumler = meas.get("olcumler") or []
        olculen_gunler = {o.get("gun") for o in olcumler}
        m = kmap.get(meas.get("primary_metric"))
        b = meas.get("baseline"); tg = meas.get("target")
        pilot_ids = [s["id"] async for s in db.students.find({"ai_experiments.pilot_groups": t["id"]}, {"id": 1})]
        kontrol_ids = [s["id"] async for s in db.students.find({"ai_experiments.control_groups": t["id"]}, {"id": 1})]
        genel = _metrik_deger(foto, m) if m else None
        pilot = await _segment_bazli_metrik_hesapla(pilot_ids, m, foto) if m else None
        kontrol = await _segment_bazli_metrik_hesapla(kontrol_ids, m, foto) if m else None
        net = None
        try:
            if pilot is not None and kontrol is not None:
                net = round(float(pilot) - float(kontrol), 1)
        except (TypeError, ValueError):
            net = None
        yeni = False
        for c in sorted(checkpoints):
            if c <= yas and c not in olculen_gunler:
                olcumler.append({
                    "gun": c, "tarih": iso(),
                    "genel_deger": genel, "pilot_deger": pilot, "kontrol_deger": kontrol,
                    "genel_ilerleme_yuzde": _ilerleme(genel, b, tg),
                    "pilot_ilerleme_yuzde": _ilerleme(pilot, b, tg),
                    "kontrol_ilerleme_yuzde": _ilerleme(kontrol, b, tg),
                    "net_etki": net, "baseline": b, "target": tg,
                    "deger": genel, "ilerleme_yuzde": _ilerleme(genel, b, tg),  # geriye-uyum (Faz 2)
                    "fotograf_id": foto.get("id"),
                })
                yeni = True
        if yeni:
            await db.ai_ceo_proposals.update_one({"id": t["id"]}, {"$set": {"measurement.olcumler": olcumler}})
            guncellenen += 1
    return {"ok": True, "guncellenen_teklif": guncellenen}


async def _olcum_throttle():
    await throttle_gunluk("karar_olcum_son", olcum_calistir)


# ─────────────────────────── Endpointler ───────────────────────────
@router.get("/ai/ceo/karar/metrik-katalog")
async def metrik_katalog(current_user=Depends(_KOORD)):
    return {"metrikler": await _katalog()}


@router.put("/ai/ceo/karar/metrik-katalog/{key}")
async def metrik_katalog_guncelle(key: str, data: dict = Body(...), current_user=Depends(_ADMIN)):
    data.pop("_id", None)
    await db.ai_ceo_metric_catalog.update_one({"key": key}, {"$set": {**data, "key": key}}, upsert=True)
    return {"ok": True, "key": key}


@router.post("/ai/ceo/karar/olcum-calistir")
async def karar_olcum_calistir(current_user=Depends(_ADMIN)):
    """Uygulamadaki tekliflerin kontrol noktası ölçümlerini elle çalıştırır (otomatik olarak da
    /durum açılışında günde bir kez tetiklenir)."""
    return await olcum_calistir()


@router.get("/ai/ceo/karar/durum")
async def karar_durum(current_user=Depends(_KOORD)):
    """Çok katmanlı GERÇEK fotoğraf + sağlık skoru + katalog ihlalleri + son teklifler."""
    await _olcum_throttle()  # cron yoksa: günde bir kez checkpoint ölçümü
    foto = await F.son_fotograf() or await F.sistem_fotografi()
    katalog = await _katalog()
    teklifler = await db.ai_ceo_proposals.find({}, {"_id": 0}).sort("tarih", -1).limit(8).to_list(length=8)
    return {
        "fotograf": F.ai_payload(foto),
        "saglik": F.saglik_skoru(foto),
        "veri_kalitesi": _veri_kalitesi(foto),
        "ihlaller": [{"key": i["metrik"]["key"], "ad": i["metrik"]["name"], "deger": i["deger"],
                      "esik": i["esik"], "sapma_yuzde": round(i["sapma"] * 100, 1)}
                     for i in _ihlal_eden_metrikler(foto, katalog)],
        "son_teklifler": teklifler,
    }


@router.post("/ai/ceo/karar/teklif-uret")
async def teklif_uret(current_user=Depends(_KOORD)):
    teklif = await karar_teklifi_uret()
    await islem_kaydet(current_user, "ai_ceo", "karar_teklif_uret", "ai_ceo_proposal", teklif["id"], None, None, teklif.get("title"))
    return {"ok": True, "teklif": teklif}


@router.get("/ai/ceo/karar/teklifler")
async def teklifler(status: str = "", current_user=Depends(_KOORD)):
    q = {"status": status} if status else {}
    items = await db.ai_ceo_proposals.find(q, {"_id": 0}).sort("tarih", -1).to_list(length=200)
    return {"teklifler": items}


@router.get("/ai/ceo/karar/teklif/{teklif_id}")
async def teklif_detay(teklif_id: str, current_user=Depends(_KOORD)):
    t = await db.ai_ceo_proposals.find_one({"id": teklif_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı")
    return t


@router.post("/ai/ceo/karar/teklif/{teklif_id}/karar")
async def teklif_karar(teklif_id: str, data: dict = Body(...), current_user=Depends(_ADMIN)):
    """Yönetici kararı: approved | rejected. (Uygulama başlatma ayrı: /uygula.)"""
    karar = data.get("karar")
    if karar not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="karar 'approved' veya 'rejected' olmalı")
    t = await db.ai_ceo_proposals.find_one({"id": teklif_id})
    if not t:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı")
    if t.get("status") != "awaiting_decision":
        raise HTTPException(status_code=400, detail="Yalnız karar bekleyen teklif için karar verilir")
    await db.ai_ceo_proposals.update_one({"id": teklif_id}, {"$set": {"status": karar, "karar_tarihi": iso()}})
    await islem_kaydet(current_user, "ai_ceo", "karar_teklif_karar", "ai_ceo_proposal", teklif_id, "status", t.get("status"), karar)
    return {"ok": True, "status": karar}


@router.post("/ai/ceo/karar/teklif/{teklif_id}/uygula")
async def teklif_uygula(teklif_id: str, current_user=Depends(_ADMIN)):
    """Onaylı teklifi UYGULAMAYA al: segmentine göre pilot/kontrol gruplarını (db.students'e)
    kilitler ve deneyi başlatır → status=implemented."""
    t = await db.ai_ceo_proposals.find_one({"id": teklif_id})
    if not t:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı")
    if t.get("status") != "approved":
        raise HTTPException(status_code=400, detail="Yalnız onaylı (approved) teklif uygulamaya alınır")
    gruplar = await _deney_gruplarini_olustur(t)  # FAZ 3: pilot/kontrol mühürle
    await db.ai_ceo_proposals.update_one({"id": teklif_id},
        {"$set": {"status": "implemented", "uygulama_tarihi": iso(), "deney_gruplari": gruplar}})
    await islem_kaydet(current_user, "ai_ceo", "karar_teklif_uygula", "ai_ceo_proposal", teklif_id,
                       "status", "approved", f"implemented (pilot {gruplar['pilot']}/kontrol {gruplar['kontrol']})")
    return {"ok": True, "status": "implemented", "gruplar": gruplar}


@router.post("/ai/ceo/karar/teklif/{teklif_id}/ogrenme")
async def teklif_ogrenme(teklif_id: str, data: dict = Body(...), current_user=Depends(_ADMIN)):
    """Deney sonucu → learning (beklenen vs gerçek + ders + gerçek maliyet). Ders kurumsal
    hafızaya 'pattern' adayı olarak eklenir (onay bekler)."""
    t = await db.ai_ceo_proposals.find_one({"id": teklif_id})
    if not t:
        raise HTTPException(status_code=404, detail="Teklif bulunamadı")
    learning = {
        "expected_result": data.get("expected_result"),
        "actual_result": data.get("actual_result"),
        "lesson": (data.get("lesson") or "").strip(),
        "execution_cost_actual": data.get("execution_cost_actual"),
        "tarih": iso(),
    }
    await db.ai_ceo_proposals.update_one({"id": teklif_id}, {"$set": {"learning": learning}})
    if learning["lesson"]:
        await db.ai_ceo_institution_memory.update_one(
            {"key": f"lesson_{teklif_id}"},
            {"$set": {"type": "pattern", "key": f"lesson_{teklif_id}", "statement": learning["lesson"],
                      "confidence": 0.5, "support_count": 1, "approved": False, "valid_from": iso()}},
            upsert=True)
    await islem_kaydet(current_user, "ai_ceo", "karar_teklif_ogrenme", "ai_ceo_proposal", teklif_id, None, None, learning["lesson"][:120])
    return {"ok": True, "learning": learning}


@router.get("/ai/ceo/karar/hafiza")
async def hafiza_listele(current_user=Depends(_KOORD)):
    items = await db.ai_ceo_institution_memory.find({}, {"_id": 0}).sort("valid_from", -1).to_list(length=300)
    return {"hafiza": items}


@router.post("/ai/ceo/karar/hafiza")
async def hafiza_ekle(data: dict = Body(...), current_user=Depends(_ADMIN)):
    tur = data.get("type")
    key = (data.get("key") or "").strip()
    if tur not in ("principle", "pattern", "preference") or not key:
        raise HTTPException(status_code=400, detail="type (principle/pattern/preference) + key gerekli")
    kayit = {"type": tur, "key": key, "statement": (data.get("statement") or "").strip(),
             "confidence": float(data.get("confidence", 1.0)), "support_count": int(data.get("support_count", 1)),
             "approved": bool(data.get("approved", True)), "valid_from": iso()}
    await db.ai_ceo_institution_memory.update_one({"key": key}, {"$set": kayit}, upsert=True)
    await islem_kaydet(current_user, "ai_ceo", "karar_hafiza_ekle", "ai_ceo_memory", key, None, None, kayit["statement"][:120])
    return {"ok": True, "key": key}


@router.post("/ai/ceo/karar/hafiza/{key}/onayla")
async def hafiza_onayla(key: str, current_user=Depends(_ADMIN)):
    r = await db.ai_ceo_institution_memory.update_one({"key": key}, {"$set": {"approved": True, "valid_from": iso()}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Hafıza kaydı bulunamadı")
    return {"ok": True, "key": key, "approved": True}
