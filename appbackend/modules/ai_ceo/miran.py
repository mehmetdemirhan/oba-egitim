"""AI CEO — Miran (öğretmen koçu, öğretmen panelinde).

Öğretmene YALNIZ KENDİ verisine dayalı, kırıcı olmayan, motive edici koçluk. Haftada bir
yenilenir (öğretmen başına 1 AI çağrısı). Öğretmen faydalı/faydasız işaretler → karneye.

HİYERARŞİ: Ayda'nın (deterministik) öğretmen-bazlı koçluk odakları Miran'ın girdisidir;
admin raporunda "Miran'ın bu hafta ilettiği odaklar" görünür.

ÜSLUP GUARD: kıyaslama YOK, muhasebe tutarı YOK, ceza/tehdit YOK. Çıktı taranır; ihlalde
deterministik güvenli mesaja düşülür.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole, get_current_user
from core.ai import call_claude
from core.config import GEMINI_API_KEY
from core.zaman import simdi, aware as _aware, iso as _iso

from .personalar import (sistem_promptu, MIRAN_YASAK_ORUNTULER, MIRAN_PARA_ORUNTULER,
                         MIRAN_MUHASEBE_PROMPTU, MIRAN_PEDAGOJIK_ORUNTULER)

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
HAFTA_GUN = 7


# ─────────────────────────── öğretmen odağı (Ayda → Miran girdisi) ───────────────────────────
async def ogretmen_odak(ogretmen_id: str) -> dict:
    """Tek öğretmenin KENDİ verisinden deterministik koçluk odağı + ham metrikler."""
    t = await db.teachers.find_one({"id": ogretmen_id}, {"_id": 0, "ad": 1, "soyad": 1, "atanan_ogrenciler": 1})
    if not t:
        return {}
    ogr_idler = t.get("atanan_ogrenciler") or []
    kurlar = await db.kur_ucretleri.find({"ogrenci_id": {"$in": ogr_idler}}, {"_id": 0}).to_list(length=10000)
    now = simdi()
    yaklasan = 0   # 30. güne yaklaşan açık kur (25-35 gün)
    geciken = 0    # 35 günü aşmış açık kur
    acik = 0
    for k in kurlar:
        if k.get("durum") in (None, "acik", "aktif") and not (k.get("tamamlanma_tarihi") or k.get("odeme_tamamlanma_tarihi")):
            acik += 1
            bas = _aware(k.get("baslangic_tarihi") or k.get("tarih"))
            if bas:
                gun = (now - bas).days
                if gun > 35:
                    geciken += 1
                elif gun >= 25:
                    yaklasan += 1
    if yaklasan >= 1 or geciken >= 1 or acik >= 3:
        odak, odak_etiket = "gecikme_riski", "Gecikme riski odaklı"
    else:
        odak, odak_etiket = "ogrenci_takibi", "Öğrenci takibi odaklı"
    return {
        "ogretmen_id": ogretmen_id,
        "ad": f"{t.get('ad','')} {t.get('soyad','')}".strip(),
        "odak": odak,
        "odak_etiket": odak_etiket,
        "aktif_ogrenci": len(ogr_idler),
        "yaklasan_kur": yaklasan,
        "geciken_kur": geciken,
        "acik_kur": acik,
    }


def _guard_ihlali(metin: str) -> str | None:
    dusuk = (metin or "").lower()
    for p in MIRAN_YASAK_ORUNTULER:
        if p in dusuk:
            return f"kıyas/ceza dili: '{p}'"
    for p in MIRAN_PARA_ORUNTULER:
        if p in dusuk:
            return f"muhasebe tutarı: '{p}'"
    return None


def _deterministik_kocluk(odak: dict) -> dict:
    oneriler = []
    if odak.get("geciken_kur", 0) > 0:
        oneriler.append({
            "baslik": "Süresi uzayan kurları önceliklendir",
            "aciklama": f"{odak['geciken_kur']} kurun 35 günü geçti — bu öğrencilerle kısa bir "
                        "hızlandırma planı yapmak tamamlanmayı ve motivasyonu artırır.",
        })
    if odak.get("yaklasan_kur", 0) > 0:
        oneriler.append({
            "baslik": "Kuru 30. güne yaklaşan öğrenciler",
            "aciklama": f"Bu hafta {odak['yaklasan_kur']} öğrencinin kuru 30. güne yaklaşıyor — "
                        "birer ek ders planlamak, geciktirmeden bitirmeni sağlar.",
        })
    if odak.get("acik_kur", 0) > 0:
        oneriler.append({
            "baslik": "Açık kurları planla",
            "aciklama": f"{odak['acik_kur']} açık kurun var; küçük hedeflerle ilerlemek "
                        "öğrenci motivasyonunu ve tamamlanmayı artırır.",
        })
    if not oneriler:
        oneriler.append({
            "baslik": "Harika gidiyorsun",
            "aciklama": "Öğrenci takibin yolunda. Mevcut ritmini koruyup her öğrenciyle "
                        "kısa bir haftalık hedef belirlemeyi sürdür.",
        })
    return {
        "selam": "Selam! Bu haftaki koçluk notların hazır 👋",
        "oneriler": oneriler,
        "kapanis": "Küçük adımlar büyük fark yaratır — yanındayım!",
    }


def _miran_prompt(odak: dict) -> tuple:
    system = sistem_promptu("miran")
    user = (
        "Aşağıda KENDİNE ait öğretmen verisi var. Bu öğretmene özel, sıcak, motive edici, "
        "uygulanabilir 2-3 koçluk önerisi yaz. Kıyaslama yapma, para/tutar deme, kırıcı olma.\n\n"
        f"Öğretmen verisi: {{'aktif_ogrenci': {odak.get('aktif_ogrenci')}, "
        f"'kuru_30_gune_yaklasan': {odak.get('yaklasan_kur')}, 'acik_kur': {odak.get('acik_kur')}, "
        f"'odak': '{odak.get('odak_etiket')}'}}\n\n"
        "SADECE şu JSON: "
        '{"selam":"...","oneriler":[{"baslik":"...","aciklama":"..."}],"kapanis":"..."}'
    )
    return system, user


async def miran_uret(ogretmen_id: str) -> dict:
    odak = await ogretmen_odak(ogretmen_id)
    if not odak:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    icerik = None
    kaynak = "deterministik"
    if GEMINI_API_KEY:
        try:
            system, user = _miran_prompt(odak)
            res = await call_claude(system, user, max_tokens=1200, ozellik="miran_kocluk")
            p = res.get("parsed")
            if isinstance(p, dict) and p.get("oneriler"):
                # Üslup guard — tüm metni tara
                blob = " ".join([str(p.get("selam", "")), str(p.get("kapanis", ""))] +
                                [f"{o.get('baslik','')} {o.get('aciklama','')}" for o in p.get("oneriler", [])])
                ihlal = _guard_ihlali(blob)
                if ihlal:
                    logging.warning(f"[ai_ceo] Miran guard ihlali ({ogretmen_id}): {ihlal} → deterministik")
                else:
                    icerik = p
                    kaynak = "ai"
        except Exception as e:
            logging.warning(f"[ai_ceo] Miran AI hatası: {e}")
    if not icerik:
        icerik = _deterministik_kocluk(odak)

    kayit = {
        "id": str(uuid.uuid4()),
        "ogretmen_id": ogretmen_id,
        "odak": odak["odak"],
        "odak_etiket": odak["odak_etiket"],
        "icerik": icerik,
        "kaynak": kaynak,
        "tarih": _iso(),
    }
    await db.ai_ceo_miran.insert_one({**kayit})
    kayit.pop("_id", None)
    return kayit


async def _guncel_miran(ogretmen_id: str) -> dict | None:
    doc = await db.ai_ceo_miran.find_one({"ogretmen_id": ogretmen_id}, {"_id": 0}, sort=[("tarih", -1)])
    if not doc:
        return None
    d = _aware(doc.get("tarih"))
    if d and (simdi() - d).days >= HAFTA_GUN:
        return None  # bayat → yenilenmeli
    return doc


# ─────────────────────────── öğretmen ucu (YALNIZ KENDİ) ───────────────────────────
@router.get("/ai/ceo/miran/benim")
async def miran_benim(current_user=Depends(get_current_user)):
    if current_user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Koçum Miran öğretmenler içindir.")
    oid = current_user.get("linked_id") or current_user.get("id")
    mevcut = await _guncel_miran(oid)
    if not mevcut:
        mevcut = await miran_uret(oid)  # haftada 1 üretim
    return {"miran": mevcut}


@router.post("/ai/ceo/miran/{miran_id}/geri-bildirim")
async def miran_geri_bildirim(miran_id: str, govde: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Yetkisiz")
    oid = current_user.get("linked_id") or current_user.get("id")
    m = await db.ai_ceo_miran.find_one({"id": miran_id})
    if not m:
        raise HTTPException(status_code=404, detail="Koçluk kaydı bulunamadı")
    if m.get("ogretmen_id") != oid:  # başka öğretmenin kaydına dokunamaz
        raise HTTPException(status_code=403, detail="Bu kayıt size ait değil")
    await db.ai_ceo_miran_geribildirim.update_one(
        {"miran_id": miran_id, "ogretmen_id": oid},
        {"$set": {"miran_id": miran_id, "ogretmen_id": oid, "faydali": bool(govde.get("faydali")),
                  "tarih": _iso()}},
        upsert=True)
    return {"ok": True}


# ═══════════════════════ MUHASEBE ROLÜNE ÖZEL MİRAN (S7) ═══════════════════════
# Veri kapsamı: finansal (tutar SERBEST); öğrenci PEDAGOJİK verisi YOK (ters guard).

async def _muhasebe_veri() -> dict:
    """Deterministik finansal tespit girdisi (tutar içerir, pedagojik veri İÇERMEZ)."""
    kurlar = await db.kur_ucretleri.find({}, {"_id": 0}).to_list(length=50000)
    now = simdi()
    yas60_sayi = 0
    yas60_tutar = 0.0
    damgasiz_tamamlanan = 0
    yaklasan_hakedis_tutar = 0.0
    yaklasan_hakedis_ogretmen = set()
    yas60_idler = []       # deep-link: yaşlanan alacaklı öğrenci id'leri
    damgasiz_idler = []    # deep-link: işaretsiz tamamlanan öğrenci id'leri
    for k in kurlar:
        kalan = float(k.get("tutar") or 0) - float(k.get("yapilan_odeme") or 0)
        bitmis = bool(k.get("odeme_tamamlanma_tarihi"))
        # 60+ gün yaşlanan açık alacak
        if kalan > 0.01 and not bitmis:
            bas = _aware(k.get("baslangic_tarihi") or k.get("tarih"))
            if bas and (now - bas).days > 60:
                yas60_sayi += 1
                yas60_tutar += kalan
                if k.get("ogrenci_id"):
                    yas60_idler.append(k.get("ogrenci_id"))
        # KALİBRE: Eğitim tamamlandı (durum=tamamlandi; yeni kur / eğitim-tamamla) VE ödemesi
        # bitti (kalan≈0) olduğu HALDE hakediş damgası yoksa işaretsiz say. Yalnız ödeme bitmesi
        # (öğretmen henüz yeni kur/eğitim-tamamlandı işaretlememişse) hata DEĞİL — normal bekleme.
        if kalan <= 0.01 and k.get("durum") == "tamamlandi" and not bitmis:
            damgasiz_tamamlanan += 1
            if k.get("ogrenci_id"):
                damgasiz_idler.append(k.get("ogrenci_id"))
        # Damgalı ama henüz döneme ödenmemiş → yaklaşan hakediş
        if bitmis and not k.get("odendi_donem"):
            yaklasan_hakedis_tutar += float(k.get("ogretmen_pay") or 0)
            if k.get("ogretmen_id"):
                yaklasan_hakedis_ogretmen.add(k.get("ogretmen_id"))
    return {
        "yaslanan_60_sayi": yas60_sayi,
        "yaslanan_60_tutar": round(yas60_tutar, 2),
        "damgasiz_tamamlanan": damgasiz_tamamlanan,
        "yaklasan_hakedis_tutar": round(yaklasan_hakedis_tutar, 2),
        "yaklasan_hakedis_ogretmen_sayisi": len(yaklasan_hakedis_ogretmen),
        "yaslanan_idler": list(dict.fromkeys(yas60_idler)),
        "damgasiz_idler": list(dict.fromkeys(damgasiz_idler)),
    }


def _muhasebe_odak_ekle(icerik: dict, veri: dict) -> None:
    """Miran muhasebe önerilerine tıklanınca gidilecek odağı ekler (deep-link): işaretsiz
    ödemeler → o öğrencilerin ödemeleri; yaşlanan alacaklar → borçlu filtresi. Hem AI hem
    deterministik varyantta başlık/açıklama anahtar kelimesine göre eşler."""
    if not isinstance(icerik, dict):
        return
    dmg = [i for i in veri.get("damgasiz_idler", []) if i]
    yas = [i for i in veri.get("yaslanan_idler", []) if i]
    for o in icerik.get("oneriler", []) or []:
        blob = f"{o.get('baslik', '')} {o.get('aciklama', '')}".lower()
        if ("damga" in blob or "işaretsiz" in blob) and dmg:
            o["hedef"] = "damgasiz"
            o["odak_idler"] = dmg
        elif ("yaşlan" in blob or "alacak" in blob) and yas:
            o["hedef"] = "borclu"
            o["odak_idler"] = yas


def _guard_muhasebe(metin: str) -> str | None:
    """Muhasebe Miran'ı için TERS guard: kıyas/ceza YASAK + pedagojik veri sızıntısı YASAK
    (tutar SERBEST)."""
    dusuk = (metin or "").lower()
    for p in MIRAN_YASAK_ORUNTULER:
        if p in dusuk:
            return f"kıyas/ceza dili: '{p}'"
    for p in MIRAN_PEDAGOJIK_ORUNTULER:
        if p in dusuk:
            return f"pedagojik veri sızıntısı: '{p}'"
    return None


def _deterministik_muhasebe(veri: dict) -> dict:
    oneriler = []
    if veri["yaslanan_60_sayi"] > 0:
        oneriler.append({"baslik": "60+ gün yaşlanan alacaklar",
                         "aciklama": f"{veri['yaslanan_60_sayi']} alacak 60 günü aştı "
                                     f"(toplam {veri['yaslanan_60_tutar']:.0f}₺) — bu hafta aranmalı."})
    if veri["damgasiz_tamamlanan"] > 0:
        oneriler.append({"baslik": "Dönem kapanışına işaretsiz ödemeler",
                         "aciklama": f"{veri['damgasiz_tamamlanan']} kur eğitimi tamamlandı ve ödemesi bittiği "
                                     "halde hakediş damgası yok; damgalanmalı (backfill)."})
    if veri["yaklasan_hakedis_tutar"] > 0:
        oneriler.append({"baslik": "Yaklaşan hakediş",
                         "aciklama": f"{veri['yaklasan_hakedis_ogretmen_sayisi']} öğretmene "
                                     f"{veri['yaklasan_hakedis_tutar']:.0f}₺ hakediş hazır — dönem kapanışına hazırla."})
    if not oneriler:
        oneriler.append({"baslik": "Tablo temiz",
                         "aciklama": "Yaşlanan alacak, işaretsiz ödeme veya bekleyen hakediş görünmüyor. Harika!"})
    return {"selam": "Merhaba! Bu haftanın finansal iş listesi hazır 👋",
            "oneriler": oneriler, "kapanis": "Küçük düzenli adımlar kasayı güçlü tutar!"}


async def miran_muhasebe_uret() -> dict:
    veri = await _muhasebe_veri()
    icerik = None
    kaynak = "deterministik"
    if GEMINI_API_KEY:
        try:
            system = MIRAN_MUHASEBE_PROMPTU
            user = ("Aşağıda finansal veri var. Muhasebeciye özel, pratik, iş listesi çıkaran 2-3 öneri "
                    "yaz. Tutar belirtebilirsin; öğrenci pedagojik verisinden BAHSETME.\n\n"
                    f"Veri: {veri}\n\nSADECE JSON: "
                    '{"selam":"...","oneriler":[{"baslik":"...","aciklama":"..."}],"kapanis":"..."}')
            res = await call_claude(system, user, max_tokens=1200, ozellik="miran_muhasebe")
            p = res.get("parsed")
            if isinstance(p, dict) and p.get("oneriler"):
                blob = " ".join([str(p.get("selam", "")), str(p.get("kapanis", ""))] +
                                [f"{o.get('baslik','')} {o.get('aciklama','')}" for o in p.get("oneriler", [])])
                if _guard_muhasebe(blob):
                    logging.warning(f"[ai_ceo] Miran muhasebe guard ihlali → deterministik")
                else:
                    icerik, kaynak = p, "ai"
        except Exception as e:
            logging.warning(f"[ai_ceo] Miran muhasebe AI hatası: {e}")
    if not icerik:
        icerik = _deterministik_muhasebe(veri)
    _muhasebe_odak_ekle(icerik, veri)  # deep-link odaklarını ekle (tıkla → ilgili ödemeler)
    kayit = {"id": str(uuid.uuid4()), "ogretmen_id": "_muhasebe", "rol": "accountant",
             "icerik": icerik, "kaynak": kaynak, "tarih": _iso()}
    await db.ai_ceo_miran.insert_one({**kayit})
    kayit.pop("_id", None)
    return kayit


@router.get("/ai/ceo/miran/muhasebe")
async def miran_muhasebe(current_user=Depends(get_current_user)):
    if current_user.get("role") not in ("accountant", "admin"):
        raise HTTPException(status_code=403, detail="Bu danışmanlık muhasebe içindir.")
    doc = await db.ai_ceo_miran.find_one({"ogretmen_id": "_muhasebe"}, {"_id": 0}, sort=[("tarih", -1)])
    if doc:
        d = _aware(doc.get("tarih"))
        if not (d and (simdi() - d).days >= HAFTA_GUN):
            # Cache'lenmiş not için de odakları GÜNCEL veriye göre tazele (id'ler değişmiş olabilir)
            _muhasebe_odak_ekle(doc.get("icerik") or {}, await _muhasebe_veri())
            return {"miran": doc}
    return {"miran": await miran_muhasebe_uret()}


# ─────────────────────────── admin: hiyerarşi görünürlüğü ───────────────────────────
@router.get("/ai/ceo/miran/odaklar")
async def miran_odaklar(current_user=Depends(_ADMIN)):
    """Ayda raporunda 'Miran'ın bu hafta ilettiği odaklar' — öğretmen bazlı."""
    teachers = await db.teachers.find({"arsivli": {"$ne": True}}, {"_id": 0, "id": 1}).to_list(length=5000)
    odaklar = []
    for t in teachers:
        o = await ogretmen_odak(t["id"])
        if o:
            odaklar.append({"ogretmen_id": o["ogretmen_id"], "ad": o["ad"], "odak_etiket": o["odak_etiket"]})
    return {"odaklar": odaklar}
