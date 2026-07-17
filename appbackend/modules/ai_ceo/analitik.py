"""AI CEO — Kurul seviyesi analitik: Senaryo Simülasyonu (S6e) + Kohort (S6b).

Senaryo: deterministik gelir-marj etkisi; esneklik varsayımı AÇIKÇA etiketli; otomatik
uygulama YOK. Kohort: kayıt ayına göre yenileme eğrileri.
"""
import re

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole

from .fotograf import son_fotograf, _num
from .ortak import metrik_al

router = APIRouter()


def kayit_no(kur):
    """Kur adı/no → ilk rakam grubu (int) veya None."""
    m = re.search(r"\d+", str(kur or ""))
    return int(m.group()) if m else None
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)


def _senaryo_hesapla(base: dict, degisim: dict) -> dict:
    brut = _num(base.get("tahsil_edilen"))
    vergi = _num(base.get("toplam_vergi"))
    ogt = _num(base.get("ogretmene_odenen"))
    vergi_orani = round(vergi * 100 / brut, 2) if brut else 15.0

    kur_deg = _num(degisim.get("kur_ucreti_degisim_yuzde"))       # fiyat değişimi %
    pay_deg = _num(degisim.get("ogretmen_payi_degisim_yuzde"))    # öğretmen payı değişimi %
    yeni_vergi_orani = degisim.get("vergi_orani")
    esneklik = degisim.get("esneklik")  # talep esnekliği (varsayım); None → hacim sabit

    # Hacim etkisi (esneklik varsayımı — AÇIKÇA etiketli)
    hacim_carpani = 1.0
    varsayim = "Hacim sabit varsayıldı (esneklik girilmedi)."
    if esneklik is not None:
        hacim_carpani = max(0.0, 1 + (_num(esneklik) * -kur_deg / 100.0))
        varsayim = f"Talep esnekliği {esneklik} varsayıldı: fiyat %{kur_deg} → hacim ×{round(hacim_carpani,3)}."

    yeni_brut = brut * (1 + kur_deg / 100.0) * hacim_carpani
    v_oran = _num(yeni_vergi_orani) if yeni_vergi_orani is not None else vergi_orani
    yeni_vergi = yeni_brut * v_oran / 100.0
    yeni_ogt = ogt * (1 + pay_deg / 100.0) * hacim_carpani
    yeni_net = yeni_brut - yeni_vergi - yeni_ogt
    mevcut_net = brut - vergi - ogt
    return {
        "mevcut": {"brut": round(brut, 2), "vergi": round(vergi, 2), "ogretmen": round(ogt, 2), "net": round(mevcut_net, 2)},
        "senaryo": {"brut": round(yeni_brut, 2), "vergi": round(yeni_vergi, 2), "ogretmen": round(yeni_ogt, 2), "net": round(yeni_net, 2)},
        "net_delta": round(yeni_net - mevcut_net, 2),
        "net_delta_yuzde": round((yeni_net - mevcut_net) * 100 / mevcut_net, 1) if mevcut_net else None,
        "varsayim": varsayim,
    }


@router.post("/ai/ceo/senaryo")
async def senaryo(govde: dict, current_user=Depends(_ADMIN)):
    foto = await son_fotograf()
    base = metrik_al(foto or {}, "muhasebe", {}) or {}
    sonuc = _senaryo_hesapla(base, govde or {})
    return {"senaryo": sonuc, "not": "Deterministik projeksiyon; otomatik uygulama yoktur."}


@router.get("/ai/ceo/kohort")
async def kohort(current_user=Depends(_ADMIN)):
    """Kayıt ayına göre kohort yenileme oranı (kur>1'e ulaşan öğrenci %)."""
    students = await db.students.find({}, {"_id": 0, "id": 1, "olusturma_tarihi": 1, "kur": 1}).to_list(length=100000)
    kohortlar = {}
    for s in students:
        ay = str(s.get("olusturma_tarihi") or "")[:7]
        if not ay:
            continue
        g = kohortlar.setdefault(ay, {"ay": ay, "toplam": 0, "yenileyen": 0})
        g["toplam"] += 1
        if (kayit_no(s.get("kur")) or 1) > 1:
            g["yenileyen"] += 1
    egri = []
    for ay in sorted(kohortlar):
        g = kohortlar[ay]
        egri.append({"ay": ay, "toplam": g["toplam"],
                     "yenileme_orani": round(g["yenileyen"] * 100 / g["toplam"], 1) if g["toplam"] else 0})
    return {"kohortlar": egri}


@router.get("/ai/ceo/kurul-paketi/pdf")
async def kurul_paketi_pdf(current_user=Depends(_ADMIN)):
    """S6f: tek sayfa Kurul Özeti PDF — 6 KPI + 3 fırsat + 3 risk + plan ilerlemesi."""
    import io
    from fastapi import HTTPException, Response
    foto = await son_fotograf() or {}
    kpi = [
        ("Gelir (tahsil)", f"{_num(metrik_al(foto,'muhasebe.tahsil_edilen')):.0f} TL"),
        ("Net Marj (net kasa)", f"{_num(metrik_al(foto,'muhasebe.net_kasa')):.0f} TL"),
        ("Yenileme", f"%{metrik_al(foto,'ogretmen.yenileme_orani_yuzde') or '-'}"),
        ("NPS", f"{metrik_al(foto,'nps.nps') if metrik_al(foto,'nps.nps') is not None else '-'}"),
        ("Kazanım (proxy)", f"{metrik_al(foto,'kazanim.ort_kazanim') or '-'}"),
        ("Konsantrasyon (en büyük öğrt.)", f"%{metrik_al(foto,'konsantrasyon.en_buyuk_ogretmen_ogrenci_payi') or '-'}"),
    ]
    firsatlar = await db.ai_ceo_oneriler.find({"durum": {"$in": ["yeni", "uygulaniyor"]}}, {"_id": 0, "baslik": 1, "oncelik": 1}).sort("tarih", -1).to_list(length=3)
    from .anomali import anomalileri_hesapla
    riskler = anomalileri_hesapla(foto)[:3]
    plan = await db.ai_ceo_planlar.find_one({"durum": "onayli"}, {"_id": 0}, sort=[("onay_tarih", -1)])
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
        st = getSampleStyleSheet(); st["Title"].fontName = FONTB; st["Normal"].fontName = FONT
        ak = [Paragraph("Kurul Özeti — AI CEO (Ayda)", st["Title"]), Spacer(1, 0.4 * cm),
              Paragraph("<b>6 Temel Gösterge</b>", st["Normal"])]
        for a, v in kpi:
            ak.append(Paragraph(f"• {a}: <b>{v}</b>", st["Normal"]))
        ak.append(Spacer(1, 0.3 * cm)); ak.append(Paragraph("<b>3 Fırsat</b>", st["Normal"]))
        for f in (firsatlar or [{"baslik": "—"}]):
            ak.append(Paragraph(f"• {f.get('baslik')}", st["Normal"]))
        ak.append(Spacer(1, 0.3 * cm)); ak.append(Paragraph("<b>3 Risk</b>", st["Normal"]))
        for r in (riskler or [{"mesaj": "Belirgin risk yok"}]):
            ak.append(Paragraph(f"• {r.get('mesaj')}", st["Normal"]))
        ak.append(Spacer(1, 0.3 * cm)); ak.append(Paragraph("<b>Stratejik Plan İlerlemesi</b>", st["Normal"]))
        if plan:
            for h in plan.get("hedefler", []):
                ak.append(Paragraph(f"• {h.get('ad')}: {h.get('mevcut')}→{h.get('hedef')} {h.get('metrik','')}", st["Normal"]))
        else:
            ak.append(Paragraph("• Onaylı plan yok", st["Normal"]))
        doc.build(ak)
        pdf = buf.getvalue(); buf.close()
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="kurul_ozeti.pdf"'})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF üretilemedi: {str(e)[:100]}")
