"""Toplu Kayıt Aktarımı — kurumun Excel/CSV öğrenci-kur listesini sisteme aktarır.

Akış (sinav.py taslak-onay deseni): yukle (parse + normalize + TASLAK yaz) →
admin eşleştirme ekranında düzeltir (PUT) → uygula (idempotent kullanıcı/alacak
oluşturma; dry-run destekli). Hiçbir kullanıcı admin onayı olmadan oluşturulmaz.

Her SATIR bir öğrenci-KUR kaydıdır (öğrenci değil). Aynı öğrenci farklı kurlarla
birden çok satırda; aynı veli (telefon) birden çok öğrencide olabilir.

Koleksiyon: db.toplu_kayit_taslaklari  (durum: taslak | uygulandi | iptal)
Normalizasyon: core.kayit_normalize (saf fonksiyonlar).

Yollar (prefix=/api):
  POST   /toplu-kayit/yukle          (admin — xlsx/csv parse + taslak)
  GET    /toplu-kayit/taslak/{id}    (admin — eşleştirme ekranı verisi)
  PUT    /toplu-kayit/taslak/{id}    (admin — kolon eşleme/ücret/satır düzeltmeleri)
  POST   /toplu-kayit/uygula/{id}    (admin — dry_run destekli uygulama)
  GET    /toplu-kayit/rapor/{id}/{tur}.xlsx  (admin — şifre/hata raporu)
"""
import io
import csv
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query

from core.db import db
from core.auth import require_role, UserRole
from core import kayit_normalize as KN

router = APIRouter()

_YAZMA = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
MAX_DOSYA_BYTE = 8 * 1024 * 1024  # 8 MB

# Varsayılan kolon eşlemesi (pozisyon bazlı — başlıklar anlamsız).
_VARSAYILAN_KOLON = {
    "kayit_tarihi": 0, "ogretmen_ad": 1, "ogrenci_ad": 2, "sinif": 3, "kur": 4,
    "veli_ad": 5, "veli_telefon": 7, "notlar": 8, "durum": 9,
}
# Başlık satırı tespiti için ipuçları.
_BASLIK_IPUCU = ["telefon", "öğretmen", "ogretmen", "öğrenci", "ogrenci", "sınıf", "sinif", "kur", "veli", "tarih", "not"]


def _parse_dosya(icerik: bytes, dosya_adi: str) -> list[list]:
    """xlsx/csv → satır listesi (her satır hücre listesi). İlk sayfa kullanılır."""
    ad = (dosya_adi or "").lower()
    if ad.endswith(".xlsx") or ad.endswith(".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(icerik), read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        satirlar = [[("" if c is None else str(c).strip()) for c in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
        return satirlar
    if ad.endswith(".csv"):
        metin = icerik.decode("utf-8-sig", errors="replace")
        ornek = metin[:2000]
        ayirici = ";" if ornek.count(";") > ornek.count(",") else ","
        return [[str(c).strip() for c in row] for row in csv.reader(io.StringIO(metin), delimiter=ayirici)]
    raise HTTPException(status_code=400, detail="Yalnızca .xlsx veya .csv dosyaları desteklenir")


def _baslik_mi(satir: list) -> bool:
    """İlk satır başlık mı (veri değil) — ipucu kelimelerinden en az 2'si geçiyorsa."""
    metin = " ".join(str(c) for c in satir).lower()
    return sum(1 for ip in _BASLIK_IPUCU if ip in metin) >= 2


def _hucre(satir: list, idx) -> str:
    if idx is None or idx < 0 or idx >= len(satir):
        return ""
    return str(satir[idx] or "").strip()


async def _ogretmen_listesi() -> list[dict]:
    docs = await db.teachers.find({"arsivli": {"$ne": True}}, {"_id": 0, "id": 1, "ad": 1, "soyad": 1}).to_list(length=2000)
    return docs


def _satir_isle(satir: list, kolon: dict, ogretmenler: list[dict], satir_no: int) -> dict:
    """Bir ham satırı normalize eder + kuyruk belirler. Çoklu kur = tek satır kaydı
    ama kur listesi (uygulama her kur için ayrı alacak açar)."""
    ham = {alan: _hucre(satir, idx) for alan, idx in kolon.items()}

    ogr = KN.normalize_ogrenci_ad(ham.get("ogrenci_ad", ""))
    tel = KN.normalize_telefon(ham.get("veli_telefon", ""))
    kurlar = KN.normalize_kur(ham.get("kur", ""))
    veli = KN.normalize_ad(ham.get("veli_ad", ""))
    veli_parca = veli.split(" ", 1)
    not_sinif = KN.siniflandir_not(ham.get("notlar", ""))
    ot = KN.ogretmen_eslestir(ham.get("ogretmen_ad", ""), ogretmenler) if ham.get("ogretmen_ad") else {"oneriler": [], "en_iyi": None, "otomatik": False}

    norm = {
        "kayit_tarihi": KN.normalize_tarih(ham.get("kayit_tarihi", "")),
        "ogrenci_ad": ogr["ad"], "ogrenci_soyad": ogr["soyad"],
        "ogrenci_gecerli": ogr["gecerli"], "ogrenci_sebep": ogr["sebep"],
        "sinif": KN.normalize_sinif(ham.get("sinif", "")),
        "kurlar": kurlar,
        "veli_ad": veli_parca[0] if veli_parca else "",
        "veli_soyad": veli_parca[1] if len(veli_parca) > 1 else "",
        "veli_telefon": tel["e164"], "veli_telefon_gecerli": tel["gecerli"],
        "odeme_durumu": not_sinif["odeme_durumu"],
        "egitim_notu": not_sinif["egitim_notu"],
        "aciklama": not_sinif["aciklama"],
        "taksit_notu": not_sinif["taksit_notu"],
    }

    # Kuyruk: öğrenci adı geçersiz → elle; öğretmen otomatik değil / telefon geçersiz → eşleştirme.
    if not ogr["gecerli"] or not kurlar:
        kuyruk = "elle"
    elif not ot["otomatik"] or not tel["gecerli"]:
        kuyruk = "eslestirme"
    else:
        kuyruk = "temiz"

    return {
        "satir_no": satir_no,
        "ham": ham,
        "norm": norm,
        "ogretmen_oneri": ot,
        "secili_ogretmen_id": ot["en_iyi"]["id"] if ot["otomatik"] and ot["en_iyi"] else None,
        "yeni_ogretmen_ad": ham.get("ogretmen_ad", "") if not ot["en_iyi"] else "",
        "kuyruk": kuyruk,
        "atla": False,   # admin bir satırı atlamak isterse
    }


def _ozet(satirlar: list[dict]) -> dict:
    from collections import Counter
    say = Counter(s["kuyruk"] for s in satirlar)
    return {
        "toplam_satir": len(satirlar),
        "temiz": say.get("temiz", 0),
        "eslestirme": say.get("eslestirme", 0),
        "elle": say.get("elle", 0),
    }


@router.post("/toplu-kayit/yukle")
async def toplu_kayit_yukle(dosya: UploadFile = File(...), current_user=Depends(_YAZMA)):
    """xlsx/csv yükler → parse + normalize → TASLAK oluşturur. DB'ye kullanıcı YAZMAZ."""
    icerik = await dosya.read()
    if len(icerik) > MAX_DOSYA_BYTE:
        raise HTTPException(status_code=400, detail="Dosya en fazla 8 MB olabilir")
    satirlar_ham = _parse_dosya(icerik, dosya.filename or "")
    if not satirlar_ham:
        raise HTTPException(status_code=400, detail="Dosya boş veya okunamadı")

    baslik_atla = _baslik_mi(satirlar_ham[0])
    veri = satirlar_ham[1:] if baslik_atla else satirlar_ham
    kolon = dict(_VARSAYILAN_KOLON)
    ogretmenler = await _ogretmen_listesi()

    # Boş olmayan satırları sakla (yeniden kolon-eşleme için ham liste de tutulur).
    ham_satirlar = [s for s in veri if any(str(c).strip() for c in s)]
    satirlar = [_satir_isle(satir, kolon, ogretmenler, i + 1) for i, satir in enumerate(ham_satirlar)]

    taslak = {
        "id": str(uuid.uuid4()),
        "durum": "taslak",
        "dosya_adi": dosya.filename or "",
        "kolon_esleme": kolon,
        "baslik_atlandi": baslik_atla,
        "ham_satirlar": ham_satirlar,
        "varsayilan_ucret": None,
        "sinif_ucret": {},       # {"3": 2500, ...} opsiyonel
        "satirlar": satirlar,
        "ozet": _ozet(satirlar),
        "yukleyen_id": current_user.get("id"),
        "yukleyen_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip(),
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.toplu_kayit_taslaklari.insert_one(dict(taslak))
    taslak.pop("_id", None)
    return {"taslak_id": taslak["id"], "ozet": taslak["ozet"], "kolon_esleme": kolon,
            "baslik_atlandi": baslik_atla, "satir_sayisi": len(satirlar),
            "ogretmenler": [{"id": t["id"], "ad": f"{t.get('ad','')} {t.get('soyad','')}".strip()} for t in ogretmenler]}


@router.get("/toplu-kayit/taslak/{taslak_id}")
async def toplu_kayit_taslak(taslak_id: str, current_user=Depends(_YAZMA)):
    """Eşleştirme ekranı için tam taslak (satırlar + öneriler + özet + öğretmen listesi)."""
    t = await db.toplu_kayit_taslaklari.find_one({"id": taslak_id}, {"_id": 0, "ham_satirlar": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Taslak bulunamadı")
    ogretmenler = await _ogretmen_listesi()
    t["ogretmenler"] = [{"id": o["id"], "ad": f"{o.get('ad','')} {o.get('soyad','')}".strip()} for o in ogretmenler]
    return t


@router.put("/toplu-kayit/taslak/{taslak_id}")
async def toplu_kayit_taslak_guncelle(taslak_id: str, data: dict, current_user=Depends(_YAZMA)):
    """Admin düzeltmeleri: kolon eşleme, varsayılan/sınıf ücreti, satır bazlı override
    (secili_ogretmen_id, yeni_ogretmen_ad, düzeltilmiş ad/soyad/sınıf/telefon, kuyruk, atla).
    Kolon eşleme değişirse satırlar yeniden normalize edilir."""
    t = await db.toplu_kayit_taslaklari.find_one({"id": taslak_id})
    if not t:
        raise HTTPException(status_code=404, detail="Taslak bulunamadı")
    if t.get("durum") != "taslak":
        raise HTTPException(status_code=400, detail="Yalnız 'taslak' durumundaki kayıt düzenlenebilir")

    guncelle = {}
    if "varsayilan_ucret" in data:
        try:
            guncelle["varsayilan_ucret"] = float(data["varsayilan_ucret"]) if data["varsayilan_ucret"] is not None else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="varsayilan_ucret sayısal olmalı")
    if isinstance(data.get("sinif_ucret"), dict):
        guncelle["sinif_ucret"] = {str(k): float(v) for k, v in data["sinif_ucret"].items()}

    # Kolon eşleme değişti → ham satırlardan yeniden normalize et (gerçek yeniden-eşleme).
    if isinstance(data.get("kolon_esleme"), dict):
        kolon = {**t.get("kolon_esleme", {}), **{k: int(v) for k, v in data["kolon_esleme"].items() if v is not None}}
        ogretmenler = await _ogretmen_listesi()
        ham_satirlar = t.get("ham_satirlar", [])
        guncelle["satirlar"] = [_satir_isle(satir, kolon, ogretmenler, i + 1) for i, satir in enumerate(ham_satirlar)]
        guncelle["ozet"] = _ozet(guncelle["satirlar"])
        guncelle["kolon_esleme"] = kolon

    # Satır bazlı override'lar: [{satir_no, secili_ogretmen_id?, yeni_ogretmen_ad?, kuyruk?, atla?, norm:{...}}]
    if isinstance(data.get("satir_guncelle"), list):
        harita = {s["satir_no"]: s for s in t["satirlar"]}
        for upd in data["satir_guncelle"]:
            sn = upd.get("satir_no")
            if sn not in harita:
                continue
            s = harita[sn]
            for alan in ("secili_ogretmen_id", "yeni_ogretmen_ad", "kuyruk", "atla"):
                if alan in upd:
                    s[alan] = upd[alan]
            if isinstance(upd.get("norm"), dict):
                s["norm"].update({k: v for k, v in upd["norm"].items()})
                # Öğrenci adı elle tamamlandıysa geçerli say.
                if s["norm"].get("ogrenci_ad") and s["norm"].get("ogrenci_soyad"):
                    s["norm"]["ogrenci_gecerli"] = True
        guncelle["satirlar"] = list(harita.values())
        guncelle["ozet"] = _ozet(guncelle["satirlar"])

    if not guncelle:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")
    await db.toplu_kayit_taslaklari.update_one({"id": taslak_id}, {"$set": guncelle})
    return {"ok": True, "ozet": guncelle.get("ozet", t.get("ozet"))}
