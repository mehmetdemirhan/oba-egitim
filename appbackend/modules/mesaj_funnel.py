"""Veli Mesaj Funnel'ı — SMS (Faz 1) + WhatsApp (Faz 2 iskelet), ONAYLI KUYRUK.

Hiçbir mesaj insan onayı olmadan gitmez. KVKK/İYS: onaysız veliye PAZARLAMA mesajı
gönderilmez (API seviyesinde de). Segmentler mevcut veriden on-demand hesaplanır.

Erişim: yalnız admin + accountant (öğretmen erişmez).

Koleksiyonlar:
  db.iletisim_onaylari  {telefon(normalize), durum: yok|var|ret, tarih, kaydeden_id, not}
  db.mesaj_sablonlari   {id, ad, kanal, tur: hizmet|pazarlama, metin, durum, olusturma_tarihi}
  db.mesaj_gonderimleri {id, segment, sablon_id, kanal, tur, alicilar[], tahmini_maliyet,
                         durum: taslak|tamamlandi, olusturan_id, onaylayan_id, tarih*}
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field

from core.db import db
from core.auth import require_role, UserRole
from core.audit import islem_kaydet
from core.config import SMS_BIRIM_UCRET, WHATSAPP_BIRIM_UCRET
from core.mesaj_kanallari import kanal_al, kanallar_bilgi, _tr_telefon, tr_gsm_no, sms_parca_sayisi
from modules.crm import _kur_no

router = APIRouter()

_YETKI = require_role(UserRole.ADMIN, UserRole.ACCOUNTANT)

FUNNEL_AYAR_DEFAULT = {"yenileme_gun": 7, "odeme_gun": 14}
DEGISKENLER = ["{veli_adi}", "{ogrenci_adi}", "{kur_no}", "{kalan_borc}"]
_BIRIM = {"sms": SMS_BIRIM_UCRET, "whatsapp": WHATSAPP_BIRIM_UCRET}


# ── Yardımcılar ──────────────────────────────────────────────────────────────
def _simdi():
    return datetime.now(timezone.utc)


def _tl(v) -> str:
    try:
        return f"{float(v or 0):.0f}₺"
    except Exception:
        return "0₺"


async def get_funnel_ayar() -> dict:
    doc = await db.sistem_ayarlari.find_one({"tip": "funnel_ayarlari"})
    return {**FUNNEL_AYAR_DEFAULT, **((doc or {}).get("degerler") or {})}


async def onay_durum(telefon: str) -> str:
    """Bir telefonun iletişim onayı: 'yok' (varsayılan) | 'var' | 'ret'."""
    tel = _tr_telefon(telefon)
    if not tel:
        return "yok"
    doc = await db.iletisim_onaylari.find_one({"telefon": tel}, {"_id": 0, "durum": 1})
    return (doc or {}).get("durum", "yok")


def _sablon_doldur(metin: str, alici: dict) -> str:
    return (str(metin or "")
            .replace("{veli_adi}", str(alici.get("veli_adi") or ""))
            .replace("{ogrenci_adi}", str(alici.get("ogrenci_adi") or ""))
            .replace("{kur_no}", str(alici.get("kur_no") or ""))
            .replace("{kalan_borc}", _tl(alici.get("kalan_borc"))))


def _alici(s: dict, kur_no=None, kalan_borc=None) -> dict:
    return {
        "ogrenci_id": s.get("id"),
        "ogrenci_adi": f"{s.get('ad', '')} {s.get('soyad', '')}".strip(),
        "veli_adi": f"{s.get('veli_ad', '')} {s.get('veli_soyad', '')}".strip() or None,
        "telefon": s.get("veli_telefon") or "",
        "kur_no": kur_no if kur_no is not None else _kur_no(s.get("kur")),
        "kalan_borc": kalan_borc if kalan_borc is not None
        else max(0.0, float(s.get("yapilmasi_gereken_odeme", 0)) - float(s.get("yapilan_odeme", 0))),
    }


# ── Segment hesaplayıcılar (mevcut veriden, on-demand) ───────────────────────
async def _seg_yenileme(ayar: dict) -> list:
    """Kuru tamamlanalı X gün olmuş, açık kuru olmayan (sonraki kura geçmemiş)."""
    esik = (_simdi() - timedelta(days=int(ayar["yenileme_gun"]))).isoformat()
    out = []
    async for s in db.students.find({"arsivli": {"$ne": True}}):
        # Açık/aktif kuru varsa aday değil (durum None de "aktif" sayılır)
        if await db.kur_ucretleri.count_documents({"ogrenci_id": s["id"], "durum": {"$in": [None, "acik"]}}):
            continue
        son = await db.kur_ucretleri.find(
            {"ogrenci_id": s["id"], "durum": "tamamlandi"}).sort("tamamlanma_tarihi", -1).to_list(1)
        tt = son[0].get("tamamlanma_tarihi") if son else None
        if tt and tt <= esik:
            out.append(_alici(s, kur_no=_kur_no(son[0].get("kur_adi"))))
    return out


async def _seg_odeme(ayar: dict) -> list:
    """Kalan borcu olan ve son ödemesinden Y gün geçen (veya hiç ödeme yok)."""
    esik = (_simdi() - timedelta(days=int(ayar["odeme_gun"]))).isoformat()
    out = []
    async for s in db.students.find({"arsivli": {"$ne": True}}):
        kalan = float(s.get("yapilmasi_gereken_odeme", 0)) - float(s.get("yapilan_odeme", 0))
        if kalan <= 0:
            continue
        son = await db.payments.find({"tip": "ogrenci", "kisi_id": s["id"]}).sort("tarih", -1).to_list(1)
        son_tarih = son[0].get("tarih") if son else None
        if son_tarih is None or son_tarih <= esik:
            out.append(_alici(s, kalan_borc=kalan))
    return out


async def _seg_tebrik(ayar: dict) -> list:
    """Kuru bu hafta (son 7 gün) tamamlanan."""
    esik = (_simdi() - timedelta(days=7)).isoformat()
    out = []
    async for ku in db.kur_ucretleri.find(
            {"durum": "tamamlandi", "tamamlanma_tarihi": {"$gte": esik}}):
        s = await db.students.find_one({"id": ku.get("ogrenci_id")})
        if s and not s.get("arsivli"):
            out.append(_alici(s, kur_no=_kur_no(ku.get("kur_adi"))))
    return out


SEGMENTLER = {
    "yenileme": {"ad": "Yenileme adayı", "tur": "pazarlama", "fn": _seg_yenileme,
                 "aciklama": "Kuru tamamlanalı X gün olmuş, sonraki kura geçmemiş."},
    "odeme": {"ad": "Ödeme hatırlatma", "tur": "hizmet", "fn": _seg_odeme,
              "aciklama": "Kalan borcu olan, son ödemesinden Y gün geçen."},
    "tebrik": {"ad": "Kur tebriği", "tur": "pazarlama", "fn": _seg_tebrik,
               "aciklama": "Kuru bu hafta tamamlanan."},
    "elle": {"ad": "Elle seçim", "tur": "hizmet", "fn": None,
             "aciklama": "Muhasebe/öğrenci tablosundan işaretlenen kişiler."},
}


async def _segment_alicilar(segment: str, ayar: dict, elle_ogrenci_ids: list = None) -> list:
    seg = SEGMENTLER.get(segment)
    if not seg:
        raise HTTPException(status_code=404, detail=f"Bilinmeyen segment: {segment}")
    if segment == "elle":
        out = []
        for oid in (elle_ogrenci_ids or []):
            s = await db.students.find_one({"id": oid})
            if s:
                out.append(_alici(s))
        return out
    return await seg["fn"](ayar)


# ── KANALLAR ─────────────────────────────────────────────────────────────────
@router.get("/funnel/kanallar")
async def funnel_kanallar(current_user=Depends(_YETKI)):
    return {"kanallar": kanallar_bilgi()}


# ── İLETİŞİM ONAYI (KVKK) ────────────────────────────────────────────────────
@router.get("/funnel/onay/{telefon}")
async def onay_getir(telefon: str, current_user=Depends(_YETKI)):
    return {"telefon": _tr_telefon(telefon), "durum": await onay_durum(telefon)}


@router.put("/funnel/onay")
async def onay_ayarla(payload: dict = Body(...), current_user=Depends(_YETKI)):
    """Bir telefonun onay durumunu işaretle (telefonla/yazılı onay/ret alındıysa)."""
    tel = _tr_telefon(payload.get("telefon", ""))
    durum = payload.get("durum")
    if not tel or durum not in ("yok", "var", "ret"):
        raise HTTPException(status_code=422, detail="Geçerli telefon + durum (yok|var|ret) gerekli")
    await db.iletisim_onaylari.update_one(
        {"telefon": tel},
        {"$set": {"telefon": tel, "durum": durum, "tarih": _simdi().isoformat(),
                  "kaydeden_id": current_user.get("id"), "not": payload.get("not", "")}},
        upsert=True)
    await islem_kaydet(current_user, "funnel_onay", "ayarla", "telefon", tel, "durum", None, durum)
    return {"ok": True, "telefon": tel, "durum": durum}


@router.put("/funnel/onay/toplu")
async def onay_toplu(payload: dict = Body(...), current_user=Depends(_YETKI)):
    """Toplu onay işaretleme: {telefonlar: [...], durum}."""
    durum = payload.get("durum")
    if durum not in ("yok", "var", "ret"):
        raise HTTPException(status_code=422, detail="durum yok|var|ret olmalı")
    n = 0
    for t in (payload.get("telefonlar") or []):
        tel = _tr_telefon(t)
        if not tel:
            continue
        await db.iletisim_onaylari.update_one(
            {"telefon": tel},
            {"$set": {"telefon": tel, "durum": durum, "tarih": _simdi().isoformat(),
                      "kaydeden_id": current_user.get("id")}}, upsert=True)
        n += 1
    await islem_kaydet(current_user, "funnel_onay", "toplu", "telefon", None, "durum", None, durum,
                       ekstra={"adet": n})
    return {"ok": True, "islenen": n, "durum": durum}


# ── ŞABLONLAR ────────────────────────────────────────────────────────────────
class SablonIn(BaseModel):
    ad: str
    kanal: str = "sms"
    tur: str = "pazarlama"        # hizmet | pazarlama
    metin: str
    durum: str = "aktif"


@router.get("/funnel/sablonlar")
async def sablon_liste(current_user=Depends(_YETKI)):
    docs = await db.mesaj_sablonlari.find({}, {"_id": 0}).sort("olusturma_tarihi", -1).to_list(length=None)
    return {"sablonlar": docs, "degiskenler": DEGISKENLER}


@router.post("/funnel/sablonlar")
async def sablon_olustur(s: SablonIn, current_user=Depends(_YETKI)):
    if s.tur not in ("hizmet", "pazarlama"):
        raise HTTPException(status_code=422, detail="tur hizmet|pazarlama olmalı")
    if s.kanal not in ("sms", "whatsapp"):
        raise HTTPException(status_code=422, detail="kanal sms|whatsapp olmalı")
    doc = {"id": str(uuid.uuid4()), **s.dict(), "olusturma_tarihi": _simdi().isoformat(),
           "olusturan_id": current_user.get("id")}
    await db.mesaj_sablonlari.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


@router.put("/funnel/sablonlar/{sablon_id}")
async def sablon_guncelle(sablon_id: str, s: SablonIn, current_user=Depends(_YETKI)):
    r = await db.mesaj_sablonlari.update_one({"id": sablon_id}, {"$set": s.dict()})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Şablon bulunamadı")
    return {"ok": True}


@router.delete("/funnel/sablonlar/{sablon_id}")
async def sablon_sil(sablon_id: str, current_user=Depends(_YETKI)):
    await db.mesaj_sablonlari.delete_one({"id": sablon_id})
    return {"ok": True}


# ── SEGMENTLER ───────────────────────────────────────────────────────────────
@router.get("/funnel/segmentler")
async def segment_liste(current_user=Depends(_YETKI)):
    """Segment tanımları + canlı alıcı sayıları (elle hariç)."""
    ayar = await get_funnel_ayar()
    out = []
    for ad, seg in SEGMENTLER.items():
        sayi = None
        if seg["fn"]:
            sayi = len(await seg["fn"](ayar))
        out.append({"ad": ad, "baslik": seg["ad"], "tur": seg["tur"],
                    "aciklama": seg["aciklama"], "alici_sayisi": sayi})
    return {"segmentler": out, "ayar": ayar}


@router.get("/funnel/segmentler/{segment}")
async def segment_alicilar(segment: str, current_user=Depends(_YETKI)):
    """Bir segmentin alıcıları + onay durumları (önizleme için)."""
    ayar = await get_funnel_ayar()
    alicilar = await _segment_alicilar(segment, ayar)
    for a in alicilar:
        a["onay_durum"] = await onay_durum(a["telefon"])
    return {"segment": segment, "alicilar": alicilar, "toplam": len(alicilar)}


# ── GÖNDERİM (ONAYLI KUYRUK) ─────────────────────────────────────────────────
def _gonderilebilir(tur: str, onay: str) -> bool:
    """PAZARLAMA: yalnız onay='var'. HİZMET: onaysızlara gider ama 'ret'e saygı."""
    if tur == "pazarlama":
        return onay == "var"
    return onay != "ret"   # hizmet


@router.post("/funnel/gonderim")
async def gonderim_olustur(payload: dict = Body(...), current_user=Depends(_YETKI)):
    """Segment + şablondan onay kuyruğu oluşturur (TASLAK). Henüz GÖNDERMEZ.

    Onaysız/ret alıcılar 'onaysiz' işaretlenir (gönderilmez). Maliyet = gönderilebilir
    alıcı × birim ücret. body: {segment, sablon_id, elle_ogrenci_ids?, cikar_ogrenci_ids?}.
    """
    segment = payload.get("segment")
    sablon_id = payload.get("sablon_id")
    sablon = await db.mesaj_sablonlari.find_one({"id": sablon_id}, {"_id": 0})
    if not sablon:
        raise HTTPException(status_code=404, detail="Şablon bulunamadı")
    kanal = sablon.get("kanal", "sms")
    tur = sablon.get("tur", "pazarlama")

    ayar = await get_funnel_ayar()
    alicilar = await _segment_alicilar(segment, ayar, payload.get("elle_ogrenci_ids"))
    cikar = set(payload.get("cikar_ogrenci_ids") or [])

    hazir = []
    gorulen_tel = set()   # aynı veli (telefon) birden çok öğrencide → tek mesaj (dedup)
    for a in alicilar:
        if a["ogrenci_id"] in cikar:
            continue
        tel_norm = _tr_telefon(a["telefon"])
        if tel_norm and tel_norm in gorulen_tel:
            continue  # bu veliye zaten bir alıcı eklendi
        if tel_norm:
            gorulen_tel.add(tel_norm)
        mesaj = _sablon_doldur(sablon["metin"], a)
        onay = await onay_durum(a["telefon"])
        if kanal == "sms" and not tr_gsm_no(a["telefon"]):
            durum = "yurtdisi"   # TR-dışı/geçersiz numara — gönderilemez (hata DEĞİL)
        elif bool(a["telefon"]) and _gonderilebilir(tur, onay):
            durum = "kuyrukta"
        else:
            durum = "onaysiz"
        hazir.append({
            **a, "onay_durum": onay, "mesaj": mesaj,
            "parca": sms_parca_sayisi(mesaj) if kanal == "sms" else 1,
            "durum": durum, "saglayici_id": None, "hata": None,
        })

    kuyrukta = [h for h in hazir if h["durum"] == "kuyrukta"]
    yurtdisi = sum(1 for h in hazir if h["durum"] == "yurtdisi")
    toplam_parca = sum(h["parca"] for h in kuyrukta)
    birim = _BIRIM.get(kanal, SMS_BIRIM_UCRET)
    doc = {
        "id": str(uuid.uuid4()),
        "segment": segment, "sablon_id": sablon_id, "kanal": kanal, "tur": tur,
        "alicilar": hazir,
        "ozet": {"toplam": len(hazir), "kuyrukta": len(kuyrukta),
                 "onaysiz": len(hazir) - len(kuyrukta) - yurtdisi, "yurtdisi": yurtdisi,
                 "toplam_parca": toplam_parca},
        "tahmini_maliyet": round(toplam_parca * birim, 2),
        "birim_ucret": birim,
        "durum": "taslak",
        "olusturan_id": current_user.get("id"),
        "onaylayan_id": None,
        "olusturma_tarihi": _simdi().isoformat(),
        "onay_tarihi": None,
    }
    await db.mesaj_gonderimleri.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


@router.post("/funnel/gonderim/{gid}/onayla")
async def gonderim_onayla(gid: str, current_user=Depends(_YETKI)):
    """Taslağı ONAYLA ve gönder. YALNIZ durum='kuyrukta' alıcılara gider —
    'onaysiz' alıcılara gönderim yolu YOKTUR (KVKK). Kanal mock'lanabilir."""
    g = await db.mesaj_gonderimleri.find_one({"id": gid})
    if not g:
        raise HTTPException(status_code=404, detail="Gönderim bulunamadı")
    if g.get("durum") == "tamamlandi":
        raise HTTPException(status_code=409, detail="Bu gönderim zaten tamamlandı")

    kanal = kanal_al(g.get("kanal"))
    if kanal is None or not kanal.kurulu:
        raise HTTPException(status_code=400,
                            detail=f"'{g.get('kanal')}' kanalı kurulmadı — gönderim yapılamaz")

    gonderildi = iletildi = hata = 0
    for a in g["alicilar"]:
        if a.get("durum") != "kuyrukta":
            continue  # onaysiz / yurtdisi → ASLA gönderilmez
        sonuc = await kanal.gonder(a["telefon"], a["mesaj"], g.get("tur", "hizmet"))
        if sonuc.ok:
            a["durum"] = "gonderildi"
            a["saglayici_id"] = sonuc.saglayici_id
            gonderildi += 1
        else:
            a["durum"] = "hata"
            a["hata"] = sonuc.hata
            hata += 1

    ozet = {**g.get("ozet", {}), "gonderildi": gonderildi, "iletildi": iletildi, "hata": hata}
    await db.mesaj_gonderimleri.update_one({"id": gid}, {"$set": {
        "alicilar": g["alicilar"], "ozet": ozet, "durum": "tamamlandi",
        "onaylayan_id": current_user.get("id"), "onay_tarihi": _simdi().isoformat()}})
    await islem_kaydet(current_user, "funnel_gonderim", "onayla", "gonderim", gid,
                       ekstra={"segment": g.get("segment"), "kanal": g.get("kanal"),
                               "gonderildi": gonderildi, "hata": hata})
    return {"ok": True, "ozet": ozet}


@router.get("/funnel/gonderim")
async def gonderim_liste(current_user=Depends(_YETKI)):
    docs = await db.mesaj_gonderimleri.find(
        {}, {"_id": 0, "alicilar": 0}).sort("olusturma_tarihi", -1).to_list(length=100)
    return {"gonderimler": docs}


@router.get("/funnel/gonderim/{gid}")
async def gonderim_detay(gid: str, current_user=Depends(_YETKI)):
    g = await db.mesaj_gonderimleri.find_one({"id": gid}, {"_id": 0})
    if not g:
        raise HTTPException(status_code=404, detail="Gönderim bulunamadı")
    return g


@router.get("/funnel/gonderim/{gid}/donusum")
async def gonderim_donusum(gid: str, current_user=Depends(_YETKI)):
    """Yenileme funnel dönüşümü: gönderimden sonra 14 gün içinde yeni kur açıldı mı?"""
    g = await db.mesaj_gonderimleri.find_one({"id": gid}, {"_id": 0})
    if not g:
        raise HTTPException(status_code=404, detail="Gönderim bulunamadı")
    baz = g.get("onay_tarihi") or g.get("olusturma_tarihi")
    try:
        bitis = (datetime.fromisoformat(baz) + timedelta(days=14)).isoformat()
    except Exception:
        bitis = _simdi().isoformat()
    gonderilenler = [a for a in g.get("alicilar", []) if a.get("durum") == "gonderildi"]
    donusen = 0
    for a in gonderilenler:
        yeni = await db.kur_ucretleri.count_documents({
            "ogrenci_id": a["ogrenci_id"], "durum": "acik",
            "tarih": {"$gte": baz, "$lte": bitis}})
        if yeni:
            donusen += 1
    n = len(gonderilenler)
    return {"gonderilen": n, "donusen": donusen,
            "oran": round(donusen / n * 100) if n else 0, "pencere_gun": 14}
