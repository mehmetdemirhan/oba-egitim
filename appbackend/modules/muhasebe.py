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
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.audit import islem_kaydet, islem_listele
from core.sistem import (
    get_vergi_orani, get_ogretmen_payi, get_kur_ucreti,
    VERGI_AYARLARI_DEFAULT, KUR_UCRETLERI_DEFAULT, OGRETMEN_PAYLARI_DEFAULT,
)

router = APIRouter()

_ERISIM = require_role(UserRole.ADMIN, UserRole.ACCOUNTANT)

# Satır içi düzenlemede izin verilen alanlar (whitelist) — tip bazlı.
_DUZENLENEBILIR = {
    "ogrenci": {"ad", "soyad", "veli_ad", "veli_soyad", "veli_telefon", "sinif", "kur",
                "yapilmasi_gereken_odeme", "yapilan_odeme", "ogretmene_yapilacak_odeme", "muhasebe_notu"},
    "ogretmen": {"ad", "soyad", "yapilmasi_gereken_odeme", "yapilan_odeme", "muhasebe_notu"},
}
_PARA_ALANLAR = {"yapilmasi_gereken_odeme", "yapilan_odeme", "ogretmene_yapilacak_odeme"}
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


async def _odeme_sonrasi_islem(ogrenci_id: str, user: dict | None = None) -> None:
    """Ödeme kaydı sonrası tetiklenir (SPEC B + SPEC A). Asla exception fırlatmaz.
    (1) Veli ödemesi TAMAMLANAN (kalan=0) kur kayıtlarına `odeme_tamamlanma_tarihi`
        damgalar — ödeme-bazlı öğretmen hakedişi bu tarihe göre döneme girer. Damga
        yalnız yoksa konur (idempotent, ileriye dönük; kısmi ödeme damga doğurmaz).
        TERS YÖN: "Ödenen" elle azaltılıp kalan tekrar >0 olursa, HENÜZ hakedişe
        girmemiş (odendi_donem boş) kurun tamamlanma damgası kaldırılır → hakediş
        tetiği geri alınır (audit'e düşer). Zaten ödenmiş döneme (odendi_donem)
        girmiş kur otomatik geri alınamaz; yalnız uyarı loglanır (elle düzeltme).
    (2) SPEC A: mezun + borçlu öğrenci borcunu kapattıysa otomatik arşivlenir + admin/
        muhasebeye bildirim (borç kapanınca normal arşiv + son ödeme hakediş kuralı).

    user verilirse hakediş tetik/geri-alma değişiklikleri audit'e (kim/ne zaman) düşer."""
    try:
        s = await db.students.find_one({"id": ogrenci_id})
        if not s:
            return
        kurlar = await db.kur_ucretleri.find({"ogrenci_id": ogrenci_id}, {"_id": 0}).to_list(length=500)
        kurlar.sort(key=lambda k: str(k.get("baslangic_tarihi") or k.get("tarih") or ""))
        now = datetime.now(timezone.utc).isoformat()
        for d in _kur_dagilimi(kurlar, _num(s.get("yapilan_odeme"))):
            kid = d.get("kur_ucreti_id")
            if not kid:
                continue
            k = next((x for x in kurlar if x.get("id") == kid), None)
            if not k:
                continue
            tamamlandi = _num(d.get("kalan")) <= 0.01
            damgali = bool(k.get("odeme_tamamlanma_tarihi"))
            if tamamlandi and not damgali:
                # Hakediş tetiği: tam ödenen kura tamamlanma damgası koy
                await db.kur_ucretleri.update_one(
                    {"id": kid}, {"$set": {"odeme_tamamlanma_tarihi": now}})
                if user:
                    await _log(user, "kur_ucreti", kid, "odeme_tamamlanma", None, now)
            elif not tamamlandi and damgali:
                # "Ödenen" geri alındı → kalan tekrar >0. Hakedişe girmemişse damgayı kaldır.
                if k.get("odendi_donem"):
                    logging.warning(
                        f"[muhasebe] kur {kid} '{k.get('odendi_donem')}' dönemine ödenmiş; "
                        f"kalan tekrar >0 oldu — hakediş kaydı elle düzeltilmeli.")
                    if user:
                        await _log(user, "kur_ucreti", kid, "hakedis_uyari",
                                   k.get("odendi_donem"), "kalan>0 (ödenmiş dönem)")
                else:
                    await db.kur_ucretleri.update_one(
                        {"id": kid}, {"$unset": {"odeme_tamamlanma_tarihi": ""}})
                    if user:
                        await _log(user, "kur_ucreti", kid, "odeme_tamamlanma_geri",
                                   k.get("odeme_tamamlanma_tarihi"), None)
        # SPEC A: mezun + borç kapandı → otomatik arşiv
        if s.get("mezun") and not s.get("arsivli"):
            borc = max(0.0, _num(s.get("yapilmasi_gereken_odeme")) - _num(s.get("yapilan_odeme")))
            if borc <= 0.01:
                await db.students.update_one({"id": ogrenci_id}, {"$set": {"arsivli": True}})
                try:
                    from modules.bildirim import bildirim_olustur
                    ad = f"{s.get('ad', '')} {s.get('soyad', '')}".strip()
                    async for u in db.users.find({"role": {"$in": ["admin", "accountant"]}}, {"_id": 0, "id": 1}):
                        if u.get("id"):
                            await bildirim_olustur(u["id"], "egitim_tamamla",
                                                   f"{ad} borcunu kapattı, arşive alındı.", ogrenci_id)
                except Exception:
                    pass
    except Exception as ex:
        logging.warning(f"[muhasebe] odeme_sonrasi_islem hatası: {ex}")


async def _alinmayan_ozet() -> dict:
    """İŞ 4 — Alınmayan ödeme: ödenen < beklenen (kalan>0) olan GÖRÜNÜR kur/alacak
    kayıtlarının sayısı + toplam kalan. Gizli (tamamlanmış+ödenmiş) kayıtlar sayılmaz."""
    kur_map = {}
    async for k in db.kur_ucretleri.find({}, {"_id": 0}):
        kur_map.setdefault(k.get("ogrenci_id"), []).append(k)
    for _oid in kur_map:
        kur_map[_oid].sort(key=lambda k: str(k.get("baslangic_tarihi") or k.get("tarih") or ""))
    sayi, toplam = 0, 0.0
    async for s in db.students.find({}, {"_id": 0, "id": 1, "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1}):
        kurlar = kur_map.get(s.get("id")) or []
        if kurlar:
            for d in _kur_dagilimi(kurlar, _num(s.get("yapilan_odeme"))):
                if not _kur_gizli(d) and d["kalan"] > 0.01:
                    sayi += 1; toplam += d["kalan"]
        else:
            kalan = max(0.0, _num(s.get("yapilmasi_gereken_odeme")) - _num(s.get("yapilan_odeme")))
            if kalan > 0.01:
                sayi += 1; toplam += kalan
    return {"sayi": sayi, "toplam_kalan": round(toplam, 2)}


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
                "ogretmen_id": s.get("ogretmen_id"),
                "ogretmene_yapilacak_odeme": _num(s.get("ogretmene_yapilacak_odeme")),
                # "Ödenen" satır-içi düzenlemesi öğrencinin TOPLAM ödemesini (yapilan_odeme)
                # hedefler; FIFO en-eski-borç-önce dağıtır. Frontend aşım uyarısını bu
                # toplam beklenene göre verir (per-kur tutara göre değil).
                "beklenen_toplam": round(_num(s.get("yapilmasi_gereken_odeme")), 2),
                "odenen_toplam": round(_num(s.get("yapilan_odeme")), 2),
            }
            kurlar = kur_map.get(s.get("id")) or []
            if kurlar:
                pay_map = {k.get("id"): k.get("ogretmen_pay") for k in kurlar}  # SPEC B — kur snapshot payı
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
                        "ogretmen_pay": pay_map.get(d["kur_ucreti_id"]),
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
                    # Kur kaydı olmayan (eski) öğrencide "Öğr. Payı" = student.ogretmene_yapilacak_odeme;
                    # satır-içi düzenleme bu alanı hedefler (kur snapshot yok → hakedişe girmez).
                    "ogretmen_pay": round(_num(s.get("ogretmene_yapilacak_odeme")), 2),
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
    try:
        await _geciken_kur_kontrol()  # muhasebe görüntülenince throttle'lı gecikme taraması
    except Exception as ex:
        logging.warning(f"[muhasebe] gecikme kontrol hatası: {ex}")
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
        "alinmayan": await _alinmayan_ozet(),
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

    # Ödeme değiştiyse: kur ödeme-tamamlanma damgası (tetik/geri-al) + mezun borç kapanış
    if tip == "ogrenci" and "yapilan_odeme" in guncelle:
        await _odeme_sonrasi_islem(kisi_id, current_user)

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
    egitim_turu = str(data.get("egitim_turu", "")).strip() or ogr.get("aldigi_egitim")
    # Tutar verilmemiş/0 ise Ayarlar'daki genel/tür kur ücretinden otomatik doldur
    # (varsayılan ₺14.400). Kullanıcı düzeltebilir.
    ham_tutar = data.get("tutar")
    if ham_tutar in (None, "", 0, "0"):
        tutar = round(float(await get_kur_ucreti(egitim_turu)), 2)
    else:
        try:
            tutar = round(float(ham_tutar), 2)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Tutar sayısal olmalı")
    if not kur_adi or tutar <= 0:
        raise HTTPException(status_code=422, detail="Kur adı ve pozitif tutar gerekli")
    # Öğretmen payı snapshot: kur oluşturulurken o anki pay tanımından sabitlenir
    pay_snapshot = await get_ogretmen_payi(egitim_turu)
    kayit = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "kur_adi": kur_adi,
        "tutar": tutar,
        "egitim_turu": egitim_turu,
        "ogretmen_pay": pay_snapshot,   # snapshot (admin/muhasebe satır-içi düzeltebilir)
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
    pay_map = {k.get("id"): k.get("ogretmen_pay") for k in kurlar}
    for d in dagilim:
        d["gizli"] = _kur_gizli(d)  # ana listede gizlenmiş mi (bilgi amaçlı)
        d["ogretmen_pay"] = pay_map.get(d.get("kur_ucreti_id"))  # SPEC B — satır-içi düzeltilebilir
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
    # Tamamlanma tarihi (dönem hesabı için) — admin/muhasebeci eksik/yanlış tarihi düzeltebilir
    if "tamamlanma_tarihi" in data:
        t = data.get("tamamlanma_tarihi")
        guncelle["tamamlanma_tarihi"] = str(t).strip() if t else None
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


def _normalize_genel_turler(degerler: dict) -> dict:
    """{genel, turler} ayarını doğrular/temizler: genel>=0, tür değerleri >0 olanlar
    kalır. kur ücretleri ve öğretmen payları AYNI şekli paylaşır."""
    if not isinstance(degerler, dict):
        raise HTTPException(status_code=422, detail="degerler nesnesi gerekli")
    try:
        genel = round(float(degerler.get("genel", 0) or 0), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Genel değer sayısal olmalı")
    if genel < 0:
        raise HTTPException(status_code=422, detail="Genel değer negatif olamaz")
    turler = {}
    for ad, v in (degerler.get("turler", {}) or {}).items():
        try:
            n = round(float(v), 2)
        except (TypeError, ValueError):
            continue
        if n > 0:
            turler[str(ad)] = n
    return {"genel": genel, "turler": turler}


@router.get("/muhasebe/ayarlar")
async def muhasebe_ayarlar_getir(current_user=Depends(_ERISIM)):
    """Muhasebe ayarları — admin + accountant okur (vergi oranı + kur ücretleri +
    öğretmen payları)."""
    v = await db.sistem_ayarlari.find_one({"tip": "vergi_ayarlari"})
    k = await db.sistem_ayarlari.find_one({"tip": "kur_ucretleri"})
    o = await db.sistem_ayarlari.find_one({"tip": "ogretmen_paylari"})
    return {
        "vergi_ayarlari": (v.get("degerler") if v else None) or VERGI_AYARLARI_DEFAULT,
        "kur_ucretleri": (k.get("degerler") if k else None) or KUR_UCRETLERI_DEFAULT,
        "ogretmen_paylari": (o.get("degerler") if o else None) or OGRETMEN_PAYLARI_DEFAULT,
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
    temiz = _normalize_genel_turler(data.get("degerler"))
    await db.sistem_ayarlari.update_one(
        {"tip": "kur_ucretleri"},
        {"$set": {"tip": "kur_ucretleri", "degerler": temiz,
                  "guncelleme_tarihi": datetime.utcnow().isoformat(),
                  "guncelleyen": current_user.get("ad", "")}},
        upsert=True)
    await islem_kaydet(current_user, "muhasebe", "ayar_kur_ucreti", "ayar", "kur_ucretleri",
                       "kur_ucretleri", None, f"genel={temiz['genel']}₺, {len(temiz['turler'])} tür özel")
    return {"ok": True, "degerler": temiz}


@router.put("/muhasebe/ayarlar/ogretmen-paylari")
async def muhasebe_ogretmen_paylari_guncelle(data: dict, current_user=Depends(_ERISIM)):
    """Öğretmen payları (genel + eğitim türü bazlı) günceller (admin + accountant).
    Dönem bazlı öğretmen ödemesinde tamamlanan her kur için bu pay uygulanır."""
    temiz = _normalize_genel_turler(data.get("degerler"))
    await db.sistem_ayarlari.update_one(
        {"tip": "ogretmen_paylari"},
        {"$set": {"tip": "ogretmen_paylari", "degerler": temiz,
                  "guncelleme_tarihi": datetime.utcnow().isoformat(),
                  "guncelleyen": current_user.get("ad", "")}},
        upsert=True)
    await islem_kaydet(current_user, "muhasebe", "ayar_ogretmen_payi", "ayar", "ogretmen_paylari",
                       "ogretmen_paylari", None, f"genel={temiz['genel']}₺, {len(temiz['turler'])} tür özel")
    return {"ok": True, "degerler": temiz}


# ── Dönem bazlı öğretmen ödemesi (ayın 15'i) — admin + accountant ──
# Ödeme dönemi: önceki ayın 15'i (HARİÇ) → bu ayın 15'i (DAHİL). Bir kur döneme
# girmek için TAMAMLANMIŞ (durum=tamamlandi + tamamlanma_tarihi dönem içi) ve daha
# önce ödenmemiş olmalı (odendi_donem boş). Öğretmen payı ayardan hesaplanır.

def _tarih_gun(s):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _donem_araligi(donem: str):
    """donem 'YYYY-MM-15' → (baslangic_haric_date, bitis_dahil_date). Dönem = önceki
    ayın 15'i (hariç) → bu ayın 15'i (dahil)."""
    from datetime import date as _date
    try:
        y, m = int(donem[:4]), int(donem[5:7])
        bitis = _date(y, m, 15)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Geçersiz dönem (YYYY-MM-15 bekleniyor)")
    oy, om = (y - 1, 12) if m == 1 else (y, m - 1)
    from datetime import date as _date2
    baslangic = _date2(oy, om, 15)
    return baslangic, bitis


def _donem_icinde(tamamlanma_tarihi, baslangic, bitis) -> bool:
    """baslangic (hariç) < tamamlanma <= bitis (dahil)."""
    d = _tarih_gun(tamamlanma_tarihi)
    return bool(d) and baslangic < d <= bitis


def _guncel_donem() -> str:
    """İçinde bulunulan ödeme dönemi (bir sonraki/bu ayın 15'i)."""
    b = datetime.now(timezone.utc).date()
    if b.day <= 15:
        return f"{b.year:04d}-{b.month:02d}-15"
    y, m = (b.year + 1, 1) if b.month == 12 else (b.year, b.month + 1)
    return f"{y:04d}-{m:02d}-15"


async def _donem_kalemleri(donem: str, ogretmen_id: str = None):
    """SPEC B: Veli ödemesi TAMAMLANAN (odeme_tamamlanma_tarihi damgalı), henüz
    hakedişe girmemiş kurları öğretmen bazında gruplar. Dönem ataması ödemenin
    tamamlandığı tarihe göre (önceki ayın 15'i hariç → bu ayın 15'i dahil). Pay,
    kur kaydındaki snapshot (`ogretmen_pay`) varsa ondan; yoksa güncel tanımdan.
    ogretmen_id verilirse yalnız o öğretmen."""
    baslangic, bitis = _donem_araligi(donem)
    ogretmen_ad, ogrenci = {}, {}
    async for t in db.teachers.find({}, {"_id": 0, "id": 1, "ad": 1, "soyad": 1}):
        ogretmen_ad[t.get("id")] = f"{t.get('ad', '')} {t.get('soyad', '')}".strip()
    oq = {"ogretmen_id": ogretmen_id} if ogretmen_id else {}
    async for s in db.students.find(oq, {"_id": 0, "id": 1, "ad": 1, "soyad": 1, "ogretmen_id": 1, "aldigi_egitim": 1}):
        ogrenci[s.get("id")] = s
    gruplar = {}
    if not ogrenci:
        return gruplar
    async for k in db.kur_ucretleri.find(
            {"ogrenci_id": {"$in": list(ogrenci)}, "odeme_tamamlanma_tarihi": {"$ne": None}}, {"_id": 0}):
        if k.get("odendi_donem"):
            continue
        if not _donem_icinde(k.get("odeme_tamamlanma_tarihi"), baslangic, bitis):
            continue
        s = ogrenci.get(k.get("ogrenci_id")) or {}
        oid = s.get("ogretmen_id")
        if not oid:
            continue
        # Snapshot pay öncelikli; yoksa güncel tanımdan
        pay = k.get("ogretmen_pay")
        if pay is None:
            pay = await get_ogretmen_payi(k.get("egitim_turu") or s.get("aldigi_egitim"))
        pay = _num(pay)
        g = gruplar.setdefault(oid, {"ogretmen_id": oid, "ogretmen_ad": ogretmen_ad.get(oid, ""),
                                     "kurlar": [], "toplam": 0.0})
        g["kurlar"].append({
            "kur_ucreti_id": k.get("id"),
            "ogrenci_id": k.get("ogrenci_id"),
            "ogrenci_ad": f"{s.get('ad', '')} {s.get('soyad', '')}".strip(),
            "kur": k.get("kur_adi", ""),
            "egitim_turu": k.get("egitim_turu") or s.get("aldigi_egitim", ""),
            "tamamlanma_tarihi": k.get("tamamlanma_tarihi"),
            "odeme_tamamlanma_tarihi": k.get("odeme_tamamlanma_tarihi"),
            "pay": pay,
        })
        g["toplam"] = round(g["toplam"] + pay, 2)
    return gruplar


@router.get("/muhasebe/ogretmen-donem")
async def ogretmen_donem_getir(donem: str = None, current_user=Depends(_ERISIM)):
    """Dönemde tamamlanan kurlardan öğretmen bazında ödenecek liste + toplam.
    donem verilmezse içinde bulunulan dönem (ayın 15'i)."""
    donem = donem or _guncel_donem()
    baslangic, bitis = _donem_araligi(donem)
    gruplar = await _donem_kalemleri(donem)
    return {"donem": donem,
            "araligi": {"baslangic_haric": str(baslangic), "bitis_dahil": str(bitis)},
            "ogretmenler": list(gruplar.values())}


@router.post("/muhasebe/ogretmen-donem/ode")
async def ogretmen_donem_ode(data: dict, current_user=Depends(_ERISIM)):
    """Bir öğretmenin dönem ödemesini KAYDET. İdempotent: aynı öğretmen+dönem iki kez
    ödenemez (409); ödenen kurlar 'odendi_donem' ile mühürlenir → başka döneme giremez."""
    ogretmen_id = data.get("ogretmen_id")
    donem = data.get("donem") or _guncel_donem()
    if not ogretmen_id:
        raise HTTPException(status_code=422, detail="ogretmen_id gerekli")
    varmi = await db.ogretmen_donem_odemeleri.find_one({"ogretmen_id": ogretmen_id, "donem": donem})
    if varmi:
        raise HTTPException(status_code=409, detail="Bu öğretmen için bu dönem zaten ödendi")
    gruplar = await _donem_kalemleri(donem, ogretmen_id=ogretmen_id)
    grup = gruplar.get(ogretmen_id)
    if not grup or not grup["kurlar"]:
        raise HTTPException(status_code=400, detail="Bu dönemde ödenecek tamamlanmış kur yok")
    kur_ids = [c["kur_ucreti_id"] for c in grup["kurlar"] if c.get("kur_ucreti_id")]
    toplam = grup["toplam"]
    kayit = {
        "id": str(uuid.uuid4()),
        "ogretmen_id": ogretmen_id,
        "ogretmen_ad": grup["ogretmen_ad"],
        "donem": donem,
        "kur_ids": kur_ids,
        "kalemler": grup["kurlar"],
        "toplam": toplam,
        "tarih": datetime.now(timezone.utc).isoformat(),
        "odeyen_id": current_user.get("id"),
    }
    await db.ogretmen_donem_odemeleri.insert_one(kayit)
    # Kurları döneme mühürle (idempotency) + mevcut bakiye katmanına yansıt
    await db.kur_ucretleri.update_many({"id": {"$in": kur_ids}}, {"$set": {"odendi_donem": donem}})
    await db.teachers.update_one({"id": ogretmen_id}, {"$inc": {"yapilan_odeme": toplam}})
    await islem_kaydet(current_user, "muhasebe", "ogretmen_donem_ode", "ogretmen", ogretmen_id,
                       "donem", None, f"{donem}: ₺{toplam} ({len(kur_ids)} kur)")
    return {"ok": True, "donem": donem, "toplam": toplam, "kur_sayisi": len(kur_ids)}


@router.get("/muhasebe/ogretmen-donem/gecmis")
async def ogretmen_donem_gecmis(ogretmen_id: str = None, limit: int = 100, current_user=Depends(_ERISIM)):
    """Geçmiş dönem ödemeleri (en yeni önce)."""
    q = {"ogretmen_id": ogretmen_id} if ogretmen_id else {}
    docs = await db.ogretmen_donem_odemeleri.find(q, {"_id": 0}).sort("tarih", -1).to_list(length=min(limit, 500))
    return {"odemeler": docs}


@router.patch("/muhasebe/kur-ucreti/{kur_id}/pay")
async def kur_ogretmen_pay_duzelt(kur_id: str, data: dict, current_user=Depends(_ERISIM)):
    """SPEC B: Bir kur kaydının öğretmen payı snapshot'ını satır-içi düzeltir (yalnız
    admin/muhasebe; öğretmen bu alanı görmez/erişemez). Değişiklik audit'e düşer.
    Zaten hakedişe girmiş (odendi_donem) kur düzeltilemez."""
    kur = await db.kur_ucretleri.find_one({"id": kur_id})
    if not kur:
        raise HTTPException(status_code=404, detail="Kur kaydı bulunamadı")
    if kur.get("odendi_donem"):
        raise HTTPException(status_code=400, detail="Bu kur hakedişe girmiş, payı değiştirilemez")
    try:
        yeni_pay = round(float(data.get("ogretmen_pay")), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Geçersiz pay değeri")
    if yeni_pay < 0:
        raise HTTPException(status_code=400, detail="Pay negatif olamaz")
    eski = kur.get("ogretmen_pay")
    await db.kur_ucretleri.update_one({"id": kur_id}, {"$set": {"ogretmen_pay": yeni_pay}})
    await _log(current_user, "kur_ucreti", kur_id, "ogretmen_pay", eski, yeni_pay)
    return {"ok": True, "ogretmen_pay": yeni_pay}


@router.post("/muhasebe/gecis/odeme-tarihi-backfill")
async def odeme_tarihi_backfill(current_user=Depends(require_role(UserRole.ADMIN))):
    """SPEC B geçişi (tek seferlik, yalnız admin, idempotent): ödeme-bazlı hakediş
    kuralına geçerken, HÂLEN tam ödenmiş (kalan=0) ama henüz hakedişe girmemiş ve
    `odeme_tamamlanma_tarihi` damgası OLMAYAN kurlara bugünün tarihini damgalar — bu
    kurlar GEÇMİŞ dönemlere değil, İÇİNDE bulunulan döneme bir kez girer (geçmiş
    yeniden hesaplanmaz). Zaten damgalı/ödenmiş kurlara dokunmaz."""
    now = datetime.now(timezone.utc).isoformat()
    ogrenciler = await db.students.find(
        {}, {"_id": 0, "id": 1, "yapilan_odeme": 1}).to_list(length=None)
    damgalanan = 0
    for s in ogrenciler:
        kurlar = await db.kur_ucretleri.find({"ogrenci_id": s.get("id")}, {"_id": 0}).to_list(length=500)
        if not kurlar:
            continue
        kurlar.sort(key=lambda k: str(k.get("baslangic_tarihi") or k.get("tarih") or ""))
        for d in _kur_dagilimi(kurlar, _num(s.get("yapilan_odeme"))):
            kid = d.get("kur_ucreti_id")
            if kid and d.get("kalan", 1) <= 0.01:
                k = next((x for x in kurlar if x.get("id") == kid), None)
                if k and not k.get("odeme_tamamlanma_tarihi") and not k.get("odendi_donem"):
                    await db.kur_ucretleri.update_one({"id": kid}, {"$set": {"odeme_tamamlanma_tarihi": now}})
                    damgalanan += 1
    return {"ok": True, "damgalanan_kur": damgalanan,
            "not": "Bu kurlar içinde bulunulan döneme girecek; geçmiş yeniden hesaplanmadı."}


@router.get("/muhasebe/ogretmen-gruplu")
async def muhasebe_ogretmen_gruplu(current_user=Depends(_ERISIM)):
    """SPEC B: Öğrenci ödemelerinin öğretmen bazlı gruplu görünümü. Her öğretmen satırı:
    öğrenci sayısı, toplam beklenen/ödenen/kalan, bu dönem hakedişi; altında öğrenciler.
    (Düz liste görünümü mevcut uçtan gelir; bu, 'Öğretmene Göre' anahtarını besler.)"""
    donem = _guncel_donem()
    kalemler = await _donem_kalemleri(donem)  # {ogretmen_id: {..., "toplam": ₺}}
    gruplar = {}

    def _grup(oid, ad):
        return gruplar.setdefault(oid or "_atanmamis", {
            "ogretmen_id": oid, "ogretmen_ad": ad, "ogrenciler": [],
            "ogrenci_sayisi": 0, "beklenen": 0.0, "odenen": 0.0, "kalan": 0.0,
            "bu_donem_hakedis": _num((kalemler.get(oid) or {}).get("toplam", 0)),
        })

    async for t in db.teachers.find({}, {"_id": 0, "id": 1, "ad": 1, "soyad": 1}):
        _grup(t.get("id"), f"{t.get('ad', '')} {t.get('soyad', '')}".strip())

    async for s in db.students.find({"arsivli": {"$ne": True}},
                                    {"_id": 0, "id": 1, "ad": 1, "soyad": 1, "ogretmen_id": 1,
                                     "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1, "mezun": 1}):
        oid = s.get("ogretmen_id")
        g = gruplar.get(oid) or _grup(None, "Atanmamış")
        beklenen = _num(s.get("yapilmasi_gereken_odeme"))
        odenen = _num(s.get("yapilan_odeme"))
        kalan = max(0.0, round(beklenen - odenen, 2))
        g["ogrenciler"].append({
            "id": s.get("id"), "ad": f"{s.get('ad', '')} {s.get('soyad', '')}".strip(),
            "beklenen": beklenen, "odenen": odenen, "kalan": kalan,
            "mezun": bool(s.get("mezun")), "mezun_borclu": bool(s.get("mezun")) and kalan > 0.01,
        })
        g["ogrenci_sayisi"] += 1
        g["beklenen"] = round(g["beklenen"] + beklenen, 2)
        g["odenen"] = round(g["odenen"] + odenen, 2)
        g["kalan"] = round(g["kalan"] + kalan, 2)

    result = sorted((g for g in gruplar.values() if g["ogrenci_sayisi"] > 0),
                    key=lambda g: g["ogretmen_ad"] or "zzz")
    return {"gruplar": result, "donem": donem}


# ── İŞ 2: Kur süresi gecikme uyarısı ──
# 12 derslik kur en geç 5 haftada (35 gün) bitmeli. Aktif kur eşiği aşarsa öğretmen +
# admin + accountant'a bildirim. Spam koruması: kur başına son_uyari_tarihi; hâlâ
# açıksa haftada bir hatırlatma. Scheduler yok → ilk-istek/görüntüleme tetikli
# (günlük throttle). Migration gerekmez; alanlar ilk taramada oluşur.
GECIKME_ESIK_GUN = 35
GECIKME_HATIRLATMA_GUN = 7


async def _geciken_kur_listesi():
    """Aktif (durum acik/None) + başlangıcı 35 günü aşan kurlar."""
    bugun = datetime.now(timezone.utc).date()
    ogrenci = {}
    async for s in db.students.find({"arsivli": {"$ne": True}},
                                    {"_id": 0, "id": 1, "ad": 1, "soyad": 1, "ogretmen_id": 1}):
        ogrenci[s["id"]] = s
    sonuc = []
    async for k in db.kur_ucretleri.find({"durum": {"$in": [None, "acik"]}}, {"_id": 0}):
        bas = _tarih_gun(k.get("baslangic_tarihi") or k.get("tarih"))
        if not bas:
            continue
        gun = (bugun - bas).days
        if gun <= GECIKME_ESIK_GUN:
            continue
        s = ogrenci.get(k.get("ogrenci_id"))
        if not s:
            continue
        sonuc.append({
            "kur_ucreti_id": k.get("id"), "ogrenci_id": k.get("ogrenci_id"),
            "ogrenci_ad": f"{s.get('ad', '')} {s.get('soyad', '')}".strip(),
            "ogretmen_id": s.get("ogretmen_id"), "kur": k.get("kur_adi", ""),
            "baslangic": str(bas), "gun": gun, "son_uyari_tarihi": k.get("son_uyari_tarihi"),
        })
    return sonuc


async def _geciken_kur_kontrol(zorla: bool = False):
    """Throttle'lı tarama: eşik aşan + uyarı zamanı gelen kurlar için öğretmen +
    admin + accountant bildirimi; son_uyari_tarihi ile haftalık hatırlatma."""
    simdi = datetime.now(timezone.utc)
    if not zorla:
        son = await db.sistem_ayarlari.find_one({"tip": "gecikme_son_kontrol"})
        if son and son.get("zaman"):
            try:
                if (simdi - datetime.fromisoformat(son["zaman"])).total_seconds() < 20 * 3600:
                    return
            except (TypeError, ValueError):
                pass
    await db.sistem_ayarlari.update_one({"tip": "gecikme_son_kontrol"},
                                        {"$set": {"tip": "gecikme_son_kontrol", "zaman": simdi.isoformat()}}, upsert=True)
    try:
        from modules.bildirim import bildirim_olustur
    except Exception:
        return
    ortak = []
    async for u in db.users.find({"role": {"$in": ["admin", "accountant"]}}, {"_id": 0, "id": 1}):
        if u.get("id"):
            ortak.append(u["id"])
    for g in await _geciken_kur_listesi():
        su = _tarih_gun(g.get("son_uyari_tarihi"))
        if su and (simdi.date() - su).days < GECIKME_HATIRLATMA_GUN:
            continue  # haftalık cooldown
        icerik = (f"{g['ogrenci_ad']} öğrencisinin {g['kur']}. kuru 5 haftayı aştı "
                  f"(başlangıç: {g['baslangic']}, {g['gun']} gün).")
        alicilar = set(ortak)
        if g.get("ogretmen_id"):
            tu = await db.users.find_one({"linked_id": g["ogretmen_id"], "role": "teacher"}, {"_id": 0, "id": 1})
            if tu and tu.get("id"):
                alicilar.add(tu["id"])
        for aid in alicilar:
            try:
                await bildirim_olustur(aid, "kur_gecikme", icerik, g["kur_ucreti_id"])
            except Exception:
                pass
        await db.kur_ucretleri.update_one({"id": g["kur_ucreti_id"]},
                                          {"$set": {"son_uyari_tarihi": simdi.isoformat()}})


@router.get("/muhasebe/geciken-kurlar")
async def geciken_kurlar(current_user=Depends(_ERISIM)):
    """35 günü aşan aktif kurlar (Geciken Kurlar sayacı/listesi). Görüntülenince
    throttle'lı bildirim taraması da tetiklenir (scheduler yok → ilk-istek tetikli)."""
    await _geciken_kur_kontrol()
    liste = await _geciken_kur_listesi()
    liste.sort(key=lambda x: -x["gun"])
    return {"sayi": len(liste), "kurlar": liste}
