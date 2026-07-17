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
