"""AI CEO — Raporlar: GÜNLÜK (hafif, deterministik+kısa yorum) / HAFTALIK (görsel brifing
+ bildirim + opsiyonel e-posta) / AYLIK (kapsamlı + PDF). Tarihli saklanır, geçmiş görünür.
"""
import io
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from core.db import db
from core.auth import require_role, UserRole

from .fotograf import son_fotograf, sistem_fotografi, fotograf_kaydet
from .analiz import calistir_analiz
from .anomali import anomalileri_hesapla, anomali_bildirim_gonder
from .ortak import metrik_al

try:
    from core.config import PUSH_CRON_TOKEN
except Exception:  # pragma: no cover
    PUSH_CRON_TOKEN = ""

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)


def _gun_araligi(gun_once: int = 1):
    now = datetime.now(timezone.utc)
    bas = (now - timedelta(days=gun_once)).replace(hour=0, minute=0, second=0, microsecond=0)
    bit = bas + timedelta(days=1)
    return bas.isoformat(), bit.isoformat()


# ─────────────────────────── GÜNLÜK ───────────────────────────
async def _gunluk_metrikler() -> dict:
    bas, bit = _gun_araligi(1)
    def _rng(alan):
        return {alan: {"$gte": bas, "$lt": bit}}
    dun_tahsilat = 0.0
    try:
        pays = await db.payments.find({"tip": "ogrenci", **_rng("tarih")}, {"_id": 0, "miktar": 1}).to_list(length=50000)
        dun_tahsilat = round(sum(float(p.get("miktar") or 0) for p in pays), 2)
    except Exception:
        pass
    yeni_kayit = await db.students.count_documents(_rng("olusturma_tarihi")) if True else 0
    biten_kur = 0
    for alan in ("tamamlanma_tarihi", "odeme_tamamlanma_tarihi"):
        try:
            biten_kur += await db.kur_ucretleri.count_documents(_rng(alan))
        except Exception:
            pass
    girisler = None
    for koll, alan in (("giris_loglari", "tarih"), ("oturum_loglari", "tarih"), ("login_log", "tarih")):
        try:
            if koll in await db.list_collection_names():
                girisler = await db[koll].count_documents(_rng(alan))
                break
        except Exception:
            continue
    return {"dun_tahsilat": dun_tahsilat, "yeni_kayit": yeni_kayit,
            "biten_kur": biten_kur, "girisler": girisler}


def _gunluk_yorum_det(m: dict, anomali_say: int) -> str:
    parcalar = [f"Dün {m['yeni_kayit']} yeni kayıt ve {m['biten_kur']} tamamlanan kur var."]
    if m["dun_tahsilat"]:
        parcalar.append(f"Tahsilat {m['dun_tahsilat']:.0f}₺.")
    parcalar.append("Kritik anomali yok." if not anomali_say else f"{anomali_say} anomali dikkat istiyor.")
    return " ".join(parcalar)


@router.get("/ai/ceo/rapor/gunluk")
async def rapor_gunluk(current_user=Depends(_ADMIN)):
    m = await _gunluk_metrikler()
    foto = await son_fotograf()
    anomaliler = anomalileri_hesapla(foto) if foto else []
    # MALİYET KURALI: günlük rapor deterministik + hafif yorum — sayfa açılışında AI çağrısı YOK.
    yorum = _gunluk_yorum_det(m, len(anomaliler))
    kayit = {"id": str(uuid.uuid4()), "tip": "gunluk", "tarih": datetime.now(timezone.utc).isoformat(),
             "gostergeler": m, "anomaliler": anomaliler, "yorum": yorum}
    await db.ai_ceo_raporlar.insert_one({**kayit})
    kayit.pop("_id", None)
    return {"rapor": kayit}


# ─────────────────────────── HAFTALIK ───────────────────────────
async def haftalik_calistir(bildir: bool = True, eposta: bool = False) -> dict:
    foto = await son_fotograf()
    if not foto:
        foto = await sistem_fotografi()
        await fotograf_kaydet(foto)
    anomaliler = anomalileri_hesapla(foto)
    await anomali_bildirim_gonder(anomaliler)
    analiz = await calistir_analiz("haftalik", foto)

    # 5 kritik gösterge
    gostergeler = {
        "tahsil_edilen": metrik_al(foto, "muhasebe.tahsil_edilen"),
        "yenileme_orani": metrik_al(foto, "ogretmen.yenileme_orani_yuzde"),
        "aktif_ogrenci": metrik_al(foto, "ogrenci.aktif"),
        "geciken_kur": metrik_al(foto, "ogretmen.geciken_kur_sayisi"),
        "veli_memnuniyeti": metrik_al(foto, "ogretmen.veli_memnuniyeti_5uzerinden"),
    }
    oneriler = (analiz.get("oneriler") or []) if analiz.get("ok") else []
    oncelikli = sorted(oneriler, key=lambda o: {"yuksek": 0, "orta": 1, "dusuk": 2}.get(o.get("oncelik"), 3))[:3]

    kayit = {
        "id": str(uuid.uuid4()), "tip": "haftalik", "tarih": datetime.now(timezone.utc).isoformat(),
        "gostergeler": gostergeler, "oncelikli_oneriler": [{"baslik": o["baslik"], "kategori": o["kategori"],
                                                            "oncelik": o["oncelik"], "ozet": o["ozet"]} for o in oncelikli],
        "anomaliler": anomaliler, "analiz_id": analiz.get("analiz", {}).get("id") if analiz.get("ok") else None,
        "ozet": (analiz.get("analiz", {}) or {}).get("ozet", ""),
    }
    await db.ai_ceo_raporlar.insert_one({**kayit})
    kayit.pop("_id", None)

    if bildir:
        try:
            from modules.bildirim import bildirim_olustur
            adminler = await db.users.find({"role": {"$in": ["admin", "coordinator"]}}, {"_id": 0, "id": 1}).to_list(length=50)
            for a in adminler:
                await bildirim_olustur(a["id"], "ai_ceo_haftalik", "📊 Haftalık AI CEO brifingi hazır.", kayit["id"])
        except Exception as e:
            logging.warning(f"[ai_ceo] haftalik bildirim hatası: {e}")
    if eposta:
        try:
            from core.mail import send_email, SMTP_ENABLED  # type: ignore
        except Exception:
            SMTP_ENABLED = False
        try:
            from core.config import SMTP_ENABLED as _EN
            if _EN:
                from core.mail import send_email
                adminler = await db.users.find({"role": "admin", "email": {"$nin": [None, ""]}}, {"_id": 0, "email": 1}).to_list(length=20)
                html = f"<h3>Haftalık AI CEO Brifingi</h3><p>{kayit['ozet']}</p>"
                for a in adminler:
                    send_email(a["email"], "Haftalık AI CEO Brifingi", html)
        except Exception as e:
            logging.warning(f"[ai_ceo] haftalik e-posta hatası: {e}")

    return {"ok": True, "rapor": kayit}


@router.post("/ai/ceo/rapor/haftalik/calistir")
async def rapor_haftalik(govde: dict = None, current_user=Depends(_ADMIN)):
    eposta = bool((govde or {}).get("eposta"))
    return await haftalik_calistir(bildir=True, eposta=eposta)


@router.post("/ai/ceo/haftalik-cron")
async def rapor_haftalik_cron(anahtar: str = Query(default="")):
    """Harici cron (haftalık) — token korumalı. bkz. push.py deseni."""
    if PUSH_CRON_TOKEN and anahtar != PUSH_CRON_TOKEN:
        raise HTTPException(status_code=403, detail="Geçersiz anahtar")
    return await haftalik_calistir(bildir=True, eposta=True)


# ─────────────────────────── AYLIK + PDF ───────────────────────────
async def _aylik_veri() -> dict:
    foto = await son_fotograf()
    if not foto:
        foto = await sistem_fotografi()
        await fotograf_kaydet(foto)
    return {
        "id": str(uuid.uuid4()), "tip": "aylik", "tarih": datetime.now(timezone.utc).isoformat(),
        "donem": datetime.now(timezone.utc).strftime("%Y-%m"),
        "muhasebe": foto.get("muhasebe"), "ogretmen": foto.get("ogretmen"),
        "ogrenci": foto.get("ogrenci"), "kullanim": foto.get("kullanim"),
        "fotograf_tarih": foto.get("tarih"),
    }


@router.post("/ai/ceo/rapor/aylik/olustur")
async def rapor_aylik(current_user=Depends(_ADMIN)):
    kayit = await _aylik_veri()
    await db.ai_ceo_raporlar.insert_one({**kayit})
    kayit.pop("_id", None)
    return {"rapor": kayit}


@router.get("/ai/ceo/raporlar")
async def raporlar_listesi(tip: str = "", current_user=Depends(_ADMIN)):
    q = {"tip": tip} if tip in ("gunluk", "haftalik", "aylik") else {}
    docs = await db.ai_ceo_raporlar.find(q, {"_id": 0}).sort("tarih", -1).to_list(length=200)
    return {"raporlar": docs}


@router.get("/ai/ceo/rapor/{rapor_id}")
async def rapor_detay(rapor_id: str, current_user=Depends(_ADMIN)):
    r = await db.ai_ceo_raporlar.find_one({"id": rapor_id}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı")
    return {"rapor": r}


@router.get("/ai/ceo/rapor/{rapor_id}/pdf")
async def rapor_pdf(rapor_id: str, current_user=Depends(_ADMIN)):
    r = await db.ai_ceo_raporlar.find_one({"id": rapor_id}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı")
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        try:
            from modules.diagnostic import _tr_font
            FONT, FONTB = _tr_font()
        except Exception:
            FONT, FONTB = "Helvetica", "Helvetica-Bold"
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
        st = getSampleStyleSheet()
        st["Title"].fontName = FONTB
        st["Normal"].fontName = FONT
        akis = [Paragraph(f"AI CEO Raporu — {r.get('tip','').title()} ({r.get('donem') or r.get('tarih','')[:10]})", st["Title"]),
                Spacer(1, 0.5 * cm)]
        if r.get("ozet"):
            akis += [Paragraph(str(r["ozet"]), st["Normal"]), Spacer(1, 0.3 * cm)]
        for baslik, alan in (("Muhasebe", "muhasebe"), ("Öğretmen", "ogretmen"), ("Öğrenci", "ogrenci")):
            blok = r.get(alan)
            if isinstance(blok, dict):
                akis.append(Paragraph(f"<b>{baslik}</b>", st["Normal"]))
                for k, v in blok.items():
                    if not isinstance(v, (dict, list)):
                        akis.append(Paragraph(f"• {k}: {v}", st["Normal"]))
                akis.append(Spacer(1, 0.3 * cm))
        doc.build(akis)
        pdf = buf.getvalue()
        buf.close()
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="ai_ceo_{r.get("tip")}_{rapor_id[:8]}.pdf"'})
    except Exception as e:
        logging.error(f"[ai_ceo] PDF hatası: {e}")
        raise HTTPException(status_code=500, detail=f"PDF üretilemedi: {str(e)[:100]}")
