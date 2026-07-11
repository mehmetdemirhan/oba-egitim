"""Muhasebe modülü — sade ödeme paneli için kısıtlı uçlar.

Muhasebe (accountant) rolü YALNIZCA ödeme verisine erişir; CRM detayına (veli
bilgisi, notlar, eğitim verileri) erişmez. Bu modül, ödeme paneli için gereken iki
dar-kapsamlı ucu sunar:

  GET /muhasebe/kisiler  → öğrenci/öğretmen listesi, SADECE ad-soyad + ödeme alanları
  GET /muhasebe/ozet     → KPI özeti (beklenen/tahsil/bekleyen; ödenecek/ödenen)

Erişim: admin + accountant. KPI'lar kişi alanlarından (yapilmasi_gereken_odeme /
yapilan_odeme) hesaplanır — db.payments tahakkuk+tahsilatı karıştırdığı için işlem
toplamı değil kişi bakiyeleri esas alınır. Ödeme geçmişi için /payments kullanılır.
"""
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.audit import islem_kaydet, islem_listele
from core.sistem import get_vergi_orani, VERGI_AYARLARI_DEFAULT, KUR_UCRETLERI_DEFAULT

router = APIRouter()

_ERISIM = require_role(UserRole.ADMIN, UserRole.ACCOUNTANT)

# Satır içi düzenlemede izin verilen alanlar (whitelist) — tip bazlı.
_DUZENLENEBILIR = {
    "ogrenci": {"ad", "soyad", "veli_ad", "veli_soyad", "veli_telefon", "sinif", "kur",
                "yapilmasi_gereken_odeme", "yapilan_odeme", "muhasebe_notu"},
    "ogretmen": {"ad", "soyad", "yapilmasi_gereken_odeme", "yapilan_odeme", "muhasebe_notu"},
}
_PARA_ALANLAR = {"yapilmasi_gereken_odeme", "yapilan_odeme"}
_KOLEKSIYON = {"ogrenci": "students", "ogretmen": "teachers"}


async def _log(user: dict, hedef_tip: str, hedef_id: str, alan: str, eski, yeni):
    """Finansal/kişi alanı değişikliğini genel işlem kaydına (core.audit → db.islem_log)
    yazar. Modül 'muhasebe' etiketiyle birleşik İşlem Kayıtları görünümünde toplanır."""
    islem = "kur_ucreti_ekle" if alan == "kur_ucreti_ekle" else "duzenle"
    await islem_kaydet(user, "muhasebe", islem, hedef_tip, hedef_id, alan, eski, yeni)


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _kur_dagilimi(kurlar: list, toplam_odeme: float) -> list:
    """FIFO: öğrencinin toplam ödemesini kur kayıtlarına (tarih ARTAN) dağıtır.
    Her kur için tutar/odenen/kalan/durum döndürür; fazla ödeme son kur satırına
    eklenir. kisiler listesi ve öğrenci kur-özeti bu tek kaynaktan beslenir."""
    havuz = toplam_odeme
    satirlar = []
    for k in kurlar:
        tutar = _num(k.get("tutar"))
        odenen_k = min(havuz, tutar)
        havuz -= odenen_k
        satirlar.append({
            "kur_ucreti_id": k.get("id"),
            "kur": k.get("kur_adi", ""),
            "kayit_zamani": k.get("baslangic_tarihi") or k.get("tarih") or "",
            "durum": k.get("durum"),
            "yapilmasi_gereken_odeme": round(tutar, 2),
            "yapilan_odeme": round(odenen_k, 2),
            "kalan": round(max(0.0, tutar - odenen_k), 2),
        })
    if havuz > 0 and satirlar:  # fazla ödeme → son kur satırına
        satirlar[-1]["yapilan_odeme"] = round(satirlar[-1]["yapilan_odeme"] + havuz, 2)
        satirlar[-1]["kalan"] = round(max(0.0, satirlar[-1]["yapilmasi_gereken_odeme"] - satirlar[-1]["yapilan_odeme"]), 2)
    return satirlar


def _kur_gizli(satir: dict) -> bool:
    """Ana muhasebe listesinde gizlenecek kur: geçilmiş (tamamlandi) VE tam ödenmiş.
    Detay/özet görünümünde yine de gösterilir (tarihçe)."""
    return satir.get("durum") == "tamamlandi" and _num(satir.get("kalan")) <= 0.01


@router.get("/muhasebe/kisiler")
async def muhasebe_kisiler(current_user=Depends(_ERISIM)):
    """Ödeme kaydı/tablosu için kişi listesi — CRM detayı OLMADAN, sadece ad-soyad
    ve ödeme alanları döner."""
    # Öğretmen ad haritası (İŞ 2 "Öğretmeni" sütunu) — N+1'den kaçın
    ogretmen_ad = {}
    try:
        async for t in db.teachers.find({}, {"_id": 0, "id": 1, "ad": 1, "soyad": 1}):
            ogretmen_ad[t.get("id")] = f"{t.get('ad','')} {t.get('soyad','')}".strip()
    except Exception:
        pass

    # Kur ücretleri öğrenci bazında, tarih ARTAN (FIFO — eski kur önce) — İŞ 3
    kur_map = {}
    try:
        async for k in db.kur_ucretleri.find({}, {"_id": 0}):
            kur_map.setdefault(k.get("ogrenci_id"), []).append(k)
    except Exception:
        pass
    for _oid in kur_map:
        kur_map[_oid].sort(key=lambda k: str(k.get("baslangic_tarihi") or k.get("tarih") or ""))

    ogrenciler = []
    try:
        async for s in db.students.find({}, {
            "_id": 0, "id": 1, "ad": 1, "soyad": 1, "sinif": 1, "kur": 1,
            "veli_ad": 1, "veli_soyad": 1, "veli_telefon": 1, "muhasebe_notu": 1,
            "ogretmen_id": 1, "olusturma_tarihi": 1,
            "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1, "ogretmene_yapilacak_odeme": 1,
        }):
            ortak = {
                "kisi_id": s.get("id"),  # PATCH hedefi (öğrenci alanları)
                "ad": s.get("ad", ""), "soyad": s.get("soyad", ""),
                "sinif": s.get("sinif", ""),
                "veli_ad": s.get("veli_ad", ""), "veli_soyad": s.get("veli_soyad", ""),
                "veli_telefon": s.get("veli_telefon", ""),
                "muhasebe_notu": s.get("muhasebe_notu", ""),
                "ogretmen_ad": ogretmen_ad.get(s.get("ogretmen_id"), ""),
                "ogretmene_yapilacak_odeme": _num(s.get("ogretmene_yapilacak_odeme")),
            }
            kurlar = kur_map.get(s.get("id")) or []
            if kurlar:
                # FIFO dağılımı (paylaşımlı helper) → satırlar; geçilmiş VE tam ödenmiş
                # kur ana listede GİZLENİR (öğrenci detayında yine görünür).
                for d in _kur_dagilimi(kurlar, _num(s.get("yapilan_odeme"))):
                    if _kur_gizli(d):
                        continue
                    ogrenciler.append({
                        **ortak,
                        "id": d["kur_ucreti_id"],  # satır kimliği = kur kaydı (React key)
                        "kur_ucreti_id": d["kur_ucreti_id"],
                        "kur": d["kur"],
                        "kayit_zamani": d["kayit_zamani"] or s.get("olusturma_tarihi") or "",
                        "durum": d["durum"],
                        "yapilmasi_gereken_odeme": d["yapilmasi_gereken_odeme"],
                        "yapilan_odeme": d["yapilan_odeme"],
                        "kalan": d["kalan"],
                    })
            else:
                # Kur kaydı olmayan öğrenci → tek satır (güncel kur + toplam bakiye)
                gereken = _num(s.get("yapilmasi_gereken_odeme"))
                yapilan = _num(s.get("yapilan_odeme"))
                ogrenciler.append({
                    **ortak,
                    "id": s.get("id"),
                    "kur_ucreti_id": None,
                    "kur": s.get("kur", ""),
                    "kayit_zamani": s.get("olusturma_tarihi") or "",
                    "yapilmasi_gereken_odeme": round(gereken, 2),
                    "yapilan_odeme": round(yapilan, 2),
                    "kalan": round(max(0.0, gereken - yapilan), 2),
                })
    except Exception as ex:
        logging.warning(f"[muhasebe] öğrenci listesi hatası: {ex}")

    ogretmenler = []
    try:
        async for t in db.teachers.find({}, {
            "_id": 0, "id": 1, "ad": 1, "soyad": 1, "muhasebe_notu": 1, "telefon": 1,
            "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1,
        }):
            gereken = _num(t.get("yapilmasi_gereken_odeme"))
            yapilan = _num(t.get("yapilan_odeme"))
            ogretmenler.append({
                "id": t.get("id"), "kisi_id": t.get("id"),
                "ad": t.get("ad", ""), "soyad": t.get("soyad", ""),
                "telefon": t.get("telefon", ""),
                "muhasebe_notu": t.get("muhasebe_notu", ""),
                "yapilmasi_gereken_odeme": gereken,
                "yapilan_odeme": yapilan,
                "kalan": max(0.0, gereken - yapilan),
            })
    except Exception as ex:
        logging.warning(f"[muhasebe] öğretmen listesi hatası: {ex}")

    return {"ogrenciler": ogrenciler, "ogretmenler": ogretmenler}


@router.get("/muhasebe/ozet")
async def muhasebe_ozet(current_user=Depends(_ERISIM)):
    """KPI özeti — kişi bakiyelerinden hesaplanır.
    Öğrenci: beklenen tahsilat / tahsil edilen / bekleyen.
    Öğretmen: ödenecek / ödenen / kalan."""
    ogr_beklenen = ogr_tahsil = 0.0
    try:
        async for s in db.students.find({}, {"_id": 0, "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1}):
            ogr_beklenen += _num(s.get("yapilmasi_gereken_odeme"))
            ogr_tahsil += _num(s.get("yapilan_odeme"))
    except Exception as ex:
        logging.warning(f"[muhasebe] öğrenci özet hatası: {ex}")

    ogt_odenecek = ogt_odenen = 0.0
    try:
        async for t in db.teachers.find({}, {"_id": 0, "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1}):
            ogt_odenecek += _num(t.get("yapilmasi_gereken_odeme"))
            ogt_odenen += _num(t.get("yapilan_odeme"))
    except Exception as ex:
        logging.warning(f"[muhasebe] öğretmen özet hatası: {ex}")

    # İŞ 1 — Vergi: öğrenci tahsilat işlemlerinin vergisi (kayıtta saklı; eski
    # kayıt vergisiz ise güncel oranla türetilir).
    guncel_oran = await get_vergi_orani()
    toplam_vergi = 0.0
    try:
        async for p in db.payments.find({"tip": "ogrenci"}, {"_id": 0, "miktar": 1, "vergi": 1}):
            if p.get("vergi") is not None:
                toplam_vergi += _num(p.get("vergi"))
            else:
                toplam_vergi += round(_num(p.get("miktar")) * guncel_oran / 100.0, 2)
    except Exception as ex:
        logging.warning(f"[muhasebe] vergi özet hatası: {ex}")
    toplam_vergi = round(toplam_vergi, 2)
    net_tahsilat = round(ogr_tahsil - toplam_vergi, 2)
    kasa_net = round(net_tahsilat - ogt_odenen, 2)

    return {
        "ogrenci": {
            "beklenen": round(ogr_beklenen, 2),
            "tahsil_edilen": round(ogr_tahsil, 2),
            "bekleyen": round(max(0.0, ogr_beklenen - ogr_tahsil), 2),
        },
        "ogretmen": {
            "odenecek": round(ogt_odenecek, 2),
            "odenen": round(ogt_odenen, 2),
            "kalan": round(max(0.0, ogt_odenecek - ogt_odenen), 2),
        },
        "vergi": {
            "oran": guncel_oran,
            "toplam_vergi": toplam_vergi,
            "brut_tahsilat": round(ogr_tahsil, 2),
            "net_tahsilat": net_tahsilat,
        },
        "kasa_net": kasa_net,
    }


@router.patch("/muhasebe/kisi/{tip}/{kisi_id}")
async def muhasebe_kisi_duzenle(tip: str, kisi_id: str, data: dict, current_user=Depends(_ERISIM)):
    """Satır içi (hücre bazlı) düzenleme — yalnız değişen alan(lar) gönderilir.
    İzinli alanlar tip'e göre whitelist'lenir; para alanları negatif olamaz.
    Her değişiklik db.muhasebe_log'a yazılır (kim/ne zaman/eski→yeni)."""
    if tip not in _KOLEKSIYON:
        raise HTTPException(status_code=400, detail="Geçersiz tip")
    izinli = _DUZENLENEBILIR[tip]
    koleksiyon = getattr(db, _KOLEKSIYON[tip])
    kayit = await koleksiyon.find_one({"id": kisi_id})
    if not kayit:
        raise HTTPException(status_code=404, detail="Kişi bulunamadı")

    guncelle = {}
    for alan, deger in (data or {}).items():
        if alan not in izinli:
            continue
        if alan in _PARA_ALANLAR:
            try:
                deger = round(float(deger), 2)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"{alan} sayısal olmalı")
            if deger < 0:
                raise HTTPException(status_code=422, detail=f"{alan} negatif olamaz")
        else:
            deger = str(deger).strip()
        guncelle[alan] = deger

    if not guncelle:
        raise HTTPException(status_code=400, detail="Düzenlenebilir alan yok")

    await koleksiyon.update_one({"id": kisi_id}, {"$set": guncelle})
    for alan, yeni in guncelle.items():
        await _log(current_user, tip, kisi_id, alan, kayit.get(alan), yeni)

    guncel = await koleksiyon.find_one({"id": kisi_id}, {"_id": 0})
    gereken = _num(guncel.get("yapilmasi_gereken_odeme"))
    yapilan = _num(guncel.get("yapilan_odeme"))
    return {"ok": True, "kalan": max(0.0, gereken - yapilan),
            "guncellenen": list(guncelle.keys())}


@router.post("/muhasebe/ogrenci/{ogrenci_id}/kur-ucreti")
async def kur_ucreti_ekle(ogrenci_id: str, data: dict, current_user=Depends(_ERISIM)):
    """Yeni kur/dönem ücreti ekler: db.kur_ucretleri'ne detay kaydı + öğrencinin
    beklenen toplamını (yapilmasi_gereken_odeme) `$inc` ile artırır. Beklenenin tek
    kaynağı hâlâ yapilmasi_gereken_odeme'dir (dashboard/hesap mantığı korunur)."""
    ogr = await db.students.find_one({"id": ogrenci_id})
    if not ogr:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    kur_adi = str(data.get("kur_adi", "")).strip()
    try:
        tutar = round(float(data.get("tutar")), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Tutar sayısal olmalı")
    if not kur_adi or tutar <= 0:
        raise HTTPException(status_code=422, detail="Kur adı ve pozitif tutar gerekli")
    kayit = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "kur_adi": kur_adi,
        "tutar": tutar,
        "baslangic_tarihi": str(data.get("baslangic_tarihi", "")).strip() or None,
        "tarih": datetime.utcnow().isoformat(),
        "ekleyen_id": current_user.get("id"),
    }
    await db.kur_ucretleri.insert_one(kayit)
    eski = _num(ogr.get("yapilmasi_gereken_odeme"))
    await db.students.update_one({"id": ogrenci_id}, {"$inc": {"yapilmasi_gereken_odeme": tutar}})
    await _log(current_user, "ogrenci", ogrenci_id, "kur_ucreti_ekle", eski, round(eski + tutar, 2))
    return {"ok": True, "yeni_beklenen": round(eski + tutar, 2), "kur_ucreti_id": kayit["id"]}


@router.get("/muhasebe/ogrenci/{ogrenci_id}/kur-ucretleri")
async def kur_ucretleri_listesi(ogrenci_id: str, current_user=Depends(_ERISIM)):
    """Öğrencinin eklenmiş kur/dönem ücretleri (kırılım/geçmiş)."""
    docs = await db.kur_ucretleri.find({"ogrenci_id": ogrenci_id}, {"_id": 0}) \
        .sort("tarih", -1).to_list(length=500)
    return {"ogeler": docs}


@router.get("/muhasebe/ogrenci/{ogrenci_id}/kur-ozet")
async def muhasebe_ogrenci_kur_ozet(ogrenci_id: str, current_user=Depends(_ERISIM)):
    """Öğrencinin TÜM kurları (ana listede gizlenen tamamlanmış+ödenmişler DAHİL) —
    tutar/ödenen/kalan/durum + toplamlar. Öğrenci satırına tıklayınca toplu görünüm."""
    s = await db.students.find_one({"id": ogrenci_id})
    if not s:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    kurlar = await db.kur_ucretleri.find({"ogrenci_id": ogrenci_id}, {"_id": 0}).to_list(length=500)
    kurlar.sort(key=lambda k: str(k.get("baslangic_tarihi") or k.get("tarih") or ""))
    dagilim = _kur_dagilimi(kurlar, _num(s.get("yapilan_odeme")))
    if not dagilim:
        # Kur kaydı yoksa öğrenci toplamından tek kalem
        gereken = _num(s.get("yapilmasi_gereken_odeme"))
        yapilan = _num(s.get("yapilan_odeme"))
        dagilim = [{
            "kur_ucreti_id": None, "kur": s.get("kur", ""),
            "kayit_zamani": s.get("olusturma_tarihi") or "", "durum": None,
            "yapilmasi_gereken_odeme": round(gereken, 2),
            "yapilan_odeme": round(yapilan, 2),
            "kalan": round(max(0.0, gereken - yapilan), 2),
        }]
    for d in dagilim:
        d["gizli"] = _kur_gizli(d)  # ana listede gizlenmiş mi (bilgi amaçlı)
    beklenen = round(sum(d["yapilmasi_gereken_odeme"] for d in dagilim), 2)
    odenen = round(sum(d["yapilan_odeme"] for d in dagilim), 2)
    return {
        "ogrenci": {"id": ogrenci_id, "ad": s.get("ad", ""), "soyad": s.get("soyad", ""),
                    "kur": s.get("kur", "")},
        "kurlar": dagilim,
        "toplam": {"beklenen": beklenen, "odenen": odenen,
                   "kalan": round(max(0.0, beklenen - odenen), 2)},
    }


@router.patch("/muhasebe/kur-ucreti/{kur_id}")
async def kur_ucreti_guncelle(kur_id: str, data: dict, current_user=Depends(_ERISIM)):
    """Kur kaydını satır içi düzenler: kur_adi ve/veya tutar (Beklenen). Tutar
    değişirse öğrencinin beklenen toplamı (yapilmasi_gereken_odeme) delta kadar
    güncellenir — beklenenin tek kaynağı invariant'ı korunur."""
    kayit = await db.kur_ucretleri.find_one({"id": kur_id})
    if not kayit:
        raise HTTPException(status_code=404, detail="Kur kaydı bulunamadı")
    guncelle, delta = {}, 0.0
    if data.get("kur_adi") is not None:
        yeni_ad = str(data.get("kur_adi", "")).strip()
        if yeni_ad:
            guncelle["kur_adi"] = yeni_ad
    if data.get("tutar") is not None:
        try:
            yeni_tutar = round(float(data.get("tutar")), 2)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Tutar sayısal olmalı")
        if yeni_tutar < 0:
            raise HTTPException(status_code=422, detail="Tutar negatif olamaz")
        delta = round(yeni_tutar - _num(kayit.get("tutar")), 2)
        guncelle["tutar"] = yeni_tutar
    if not guncelle:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")
    await db.kur_ucretleri.update_one({"id": kur_id}, {"$set": guncelle})
    if delta:
        await db.students.update_one({"id": kayit.get("ogrenci_id")},
                                     {"$inc": {"yapilmasi_gereken_odeme": delta}})
    await _log(current_user, "ogrenci", kayit.get("ogrenci_id"), "kur_ucreti_guncelle",
               _num(kayit.get("tutar")), guncelle.get("tutar", _num(kayit.get("tutar"))))
    return {"ok": True, "guncellenen": list(guncelle.keys()), "delta": delta}


@router.get("/muhasebe/log")
async def muhasebe_log_listesi(hedef_id: str | None = None, limit: int = 100,
                               current_user=Depends(require_role(UserRole.ADMIN))):
    """Muhasebe değişiklik izi (yalnız admin). Birleşik islem_log'dan modül=muhasebe."""
    kayitlar = await islem_listele(modul="muhasebe", hedef_id=hedef_id, limit=min(limit, 500))
    return {"kayitlar": kayitlar}


# ── Muhasebe Ayarları (vergi oranı + kur ücretleri) — admin + accountant ──
# Bu ayarlar generic /ayarlar/{tip} (admin-only) yerine BURADAN yönetilir; tam-yetki
# kararımıza uygun olarak muhasebeci de düzenleyebilir. Depolama aynı sistem_ayarlari.


@router.get("/muhasebe/ayarlar")
async def muhasebe_ayarlar_getir(current_user=Depends(_ERISIM)):
    """Muhasebe ayarları — admin + accountant okur (vergi oranı + kur ücretleri)."""
    v = await db.sistem_ayarlari.find_one({"tip": "vergi_ayarlari"})
    k = await db.sistem_ayarlari.find_one({"tip": "kur_ucretleri"})
    return {
        "vergi_ayarlari": (v.get("degerler") if v else None) or VERGI_AYARLARI_DEFAULT,
        "kur_ucretleri": (k.get("degerler") if k else None) or KUR_UCRETLERI_DEFAULT,
    }


@router.put("/muhasebe/ayarlar/vergi")
async def muhasebe_vergi_guncelle(data: dict, current_user=Depends(_ERISIM)):
    """Vergi oranını günceller (admin + accountant). Oran yüzde [0-100]."""
    try:
        oran = round(float(data.get("vergi_orani")), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Vergi oranı sayısal olmalı")
    if oran < 0 or oran > 100:
        raise HTTPException(status_code=422, detail="Vergi oranı 0-100 arasında olmalı")
    eski = await db.sistem_ayarlari.find_one({"tip": "vergi_ayarlari"})
    eski_oran = (eski.get("degerler", {}) if eski else {}).get(
        "vergi_orani", VERGI_AYARLARI_DEFAULT.get("vergi_orani"))
    await db.sistem_ayarlari.update_one(
        {"tip": "vergi_ayarlari"},
        {"$set": {"tip": "vergi_ayarlari", "degerler": {"vergi_orani": oran},
                  "guncelleme_tarihi": datetime.utcnow().isoformat(),
                  "guncelleyen": current_user.get("ad", "")}},
        upsert=True)
    await islem_kaydet(current_user, "muhasebe", "ayar_vergi", "ayar", "vergi_ayarlari",
                       "vergi_orani", eski_oran, oran)
    return {"ok": True, "vergi_orani": oran}


@router.put("/muhasebe/ayarlar/kur-ucretleri")
async def muhasebe_kur_ucretleri_guncelle(data: dict, current_user=Depends(_ERISIM)):
    """Kur ücretleri (genel + eğitim türü bazlı) günceller (admin + accountant)."""
    degerler = data.get("degerler")
    if not isinstance(degerler, dict):
        raise HTTPException(status_code=422, detail="degerler nesnesi gerekli")
    try:
        genel = round(float(degerler.get("genel", 0) or 0), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Genel ücret sayısal olmalı")
    if genel < 0:
        raise HTTPException(status_code=422, detail="Genel ücret negatif olamaz")
    turler = {}
    for ad, v in (degerler.get("turler", {}) or {}).items():
        try:
            n = round(float(v), 2)
        except (TypeError, ValueError):
            continue
        if n > 0:
            turler[str(ad)] = n
    temiz = {"genel": genel, "turler": turler}
    await db.sistem_ayarlari.update_one(
        {"tip": "kur_ucretleri"},
        {"$set": {"tip": "kur_ucretleri", "degerler": temiz,
                  "guncelleme_tarihi": datetime.utcnow().isoformat(),
                  "guncelleyen": current_user.get("ad", "")}},
        upsert=True)
    await islem_kaydet(current_user, "muhasebe", "ayar_kur_ucreti", "ayar", "kur_ucretleri",
                       "kur_ucretleri", None, f"genel={genel}₺, {len(turler)} tür özel")
    return {"ok": True, "degerler": temiz}
