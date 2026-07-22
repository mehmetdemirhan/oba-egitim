"""Egzersiz Kalite Kontrol Sistemi.

Öğretmenler egzersiz kütüphanesindeki (db.egzersiz_icerikler) içerikleri önizleyip
"uygun / uygun değil", "hangi sınıflar için uygun" ve (opsiyonel) değişiklik talebi
ile değerlendirir. Yeterli sayıda olumsuz oy/değişiklik talebi biriken egzersiz
otomatik ASKIYA alınır (öğrencilere sunulmaz) ve admin/koordinatör kuyruğuna düşer.

Koleksiyon: db.egzersiz_kalite_degerlendirme (her doküman = 1 öğretmen × 1 egzersiz).
Türetilmiş alanlar egzersizin kendi kaydına (db.egzersiz_icerikler) yazılır:
  kalite_toplam_degerlendirme, kalite_uygun_sayisi, kalite_uygun_degil_sayisi,
  kalite_degisiklik_talebi_sayisi, kalite_sinif_oy_dagilimi, kalite_uygun_siniflar,
  kalite_dogrulanmis (bool). durum: aktif | askida | retired | arsivli.

Öğrenci seçimi egzersiz_motoru._AKTIF ile YALNIZ durum=aktif içerikleri sunar; askida/
retired otomatik dışlanır (ek değişiklik gerekmez). Sınıf uygunluğu: seçim sorgusu
`sinif` alanına ek olarak `kalite_uygun_siniflar` listesini de eşler (motor tarafında).
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from core.db import db
from core.auth import get_current_user, require_role, UserRole
from core.zaman import iso
from core.sistem import get_puan_ayarlari, get_kalite_kontrol_ayarlari, set_kalite_kontrol_ayarlari
from core.audit import islem_kaydet
from core.egzersiz_tipleri import tip_meta

router = APIRouter()

_YETKILI = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
KATKI_ROLLERI = ("admin", "coordinator", "teacher")


def _tip_ad(tip: str) -> str:
    meta = tip_meta(tip) or {}
    return meta.get("ad") or (tip or "").replace("_", " ").title()


async def _ogretmenin_gordukleri(ogretmen_id: str) -> set:
    """Bu öğretmenin ZATEN değerlendirdiği egzersiz id'leri."""
    cur = db.egzersiz_kalite_degerlendirme.find({"ogretmen_id": ogretmen_id}, {"egzersiz_id": 1})
    return {d["egzersiz_id"] async for d in cur}


async def _agregasyonu_guncelle(egzersiz_id: str):
    """Bir egzersizin tüm değerlendirmelerinden türetilmiş alanları yeniden hesaplar
    ve (eşik aşıldıysa) otomatik askıya alma uygular."""
    ayar = await get_kalite_kontrol_ayarlari()
    askiya_esigi = int(ayar.get("askiya_alma_esigi", 2))
    sinif_esigi = int(ayar.get("sinif_uygunluk_esigi", 1))
    dogrulama_esigi = int(ayar.get("dogrulama_esigi", 3))

    degerlendirmeler = await db.egzersiz_kalite_degerlendirme.find({"egzersiz_id": egzersiz_id}).to_list(length=None)
    toplam = len(degerlendirmeler)
    uygun = sum(1 for d in degerlendirmeler if d.get("uygun"))
    uygun_degil = sum(1 for d in degerlendirmeler if not d.get("uygun"))
    degisiklik = sum(1 for d in degerlendirmeler if (d.get("degisiklik_talebi") or "").strip())

    # Sınıf oy dağılımı: yalnız "uygun" diyenlerin işaretlediği sınıflar sayılır
    sinif_oy: dict = {}
    for d in degerlendirmeler:
        if not d.get("uygun"):
            continue
        for s in (d.get("uygun_sinif_seviyeleri") or []):
            k = str(s)
            sinif_oy[k] = sinif_oy.get(k, 0) + 1
    # Seçimde kullanılacak int sınıf listesi (eşiği geçen; "lise" motor tarafında karşılıksız)
    uygun_siniflar = []
    for k, v in sinif_oy.items():
        if v >= sinif_esigi:
            try:
                uygun_siniflar.append(int(k))
            except (ValueError, TypeError):
                pass  # "lise" gibi metinsel seviyeler seçim int sorgusuna girmez

    # Olumsuz sinyal = farklı öğretmen sayısı ("uygun değil" VEYA değişiklik talebi)
    olumsuz = sum(1 for d in degerlendirmeler
                  if (not d.get("uygun")) or (d.get("degisiklik_talebi") or "").strip())

    guncelle = {
        "kalite_toplam_degerlendirme": toplam,
        "kalite_uygun_sayisi": uygun,
        "kalite_uygun_degil_sayisi": uygun_degil,
        "kalite_degisiklik_talebi_sayisi": degisiklik,
        "kalite_sinif_oy_dagilimi": sinif_oy,
        "kalite_uygun_siniflar": sorted(set(uygun_siniflar)),
        "kalite_dogrulanmis": uygun >= dogrulama_esigi,
    }

    mevcut = await db.egzersiz_icerikler.find_one({"id": egzersiz_id}, {"durum": 1})
    durum = (mevcut or {}).get("durum", "aktif")
    askiya_alindi = False
    # Otomatik askıya alma: yalnız aktif içerik askıya alınır (retired/arsivli'ye dokunma)
    if durum in ("aktif", None) and olumsuz >= askiya_esigi:
        guncelle["durum"] = "askida"
        guncelle["kalite_askiya_tarihi"] = iso()
        askiya_alindi = True

    await db.egzersiz_icerikler.update_one({"id": egzersiz_id}, {"$set": guncelle})
    return askiya_alindi, guncelle


# ═══════════════════════════════════════════════════════════════════
# ÖĞRETMEN: değerlendirme kuyruğu + gönderim
# ═══════════════════════════════════════════════════════════════════
@router.get("/egzersiz-kalite/kuyruk")
async def kalite_kuyruk(limit: int = 3, current_user=Depends(get_current_user)):
    """Bu öğretmene gösterilecek, değerlendirilmemiş egzersizler (öncelik: en az
    değerlendirilmiş + tip dönüşümlü). durum=aktif olanlar arasından seçilir."""
    if current_user.get("role") not in KATKI_ROLLERI:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    limit = max(1, min(int(limit or 3), 10))
    gorulen = await _ogretmenin_gordukleri(current_user["id"])

    # Aday havuz: aktif + mock olmayan içerikler, en az değerlendirilenler önce
    q = {"$and": [
        {"$or": [{"durum": "aktif"}, {"durum": {"$exists": False}}]},
        {"$or": [{"mock": {"$ne": True}}, {"mock": {"$exists": False}}]},
    ]}
    adaylar = await db.egzersiz_icerikler.find(q).sort(
        [("kalite_toplam_degerlendirme", 1), ("kullanim_sayisi", -1)]).to_list(length=400)
    adaylar = [a for a in adaylar if a["id"] not in gorulen]

    # Tip dönüşümlü seçim: aynı tipte yığılmasın (round-robin)
    from collections import OrderedDict
    tip_kova: "OrderedDict[str, list]" = OrderedDict()
    for a in adaylar:
        tip_kova.setdefault(a.get("tip", "?"), []).append(a)
    secilen = []
    while len(secilen) < limit and any(tip_kova.values()):
        for t in list(tip_kova.keys()):
            if tip_kova[t]:
                secilen.append(tip_kova[t].pop(0))
                if len(secilen) >= limit:
                    break

    def _ozet(a):
        return {
            "egzersiz_id": a["id"], "tip": a.get("tip"), "tip_ad": _tip_ad(a.get("tip")),
            "sinif": a.get("sinif"), "konu": a.get("konu", ""), "zorluk": a.get("zorluk", "orta"),
            "icerik": a.get("icerik"),
            "toplam_degerlendirme": a.get("kalite_toplam_degerlendirme", 0),
        }
    return {"toplam_bekleyen": len(adaylar), "egzersizler": [_ozet(a) for a in secilen]}


class DegerlendirmeIstek(BaseModel):
    egzersiz_id: str
    uygun: bool
    uygun_sinif_seviyeleri: List = []          # [2, 3] veya ["lise"] — çoklu
    degisiklik_talebi: Optional[str] = None


@router.post("/egzersiz-kalite/degerlendir")
async def kalite_degerlendir(data: DegerlendirmeIstek, current_user=Depends(get_current_user)):
    if current_user.get("role") not in KATKI_ROLLERI:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    egz = await db.egzersiz_icerikler.find_one({"id": data.egzersiz_id})
    if not egz:
        raise HTTPException(status_code=404, detail="Egzersiz bulunamadı")
    # "Uygun" işaretlendiyse en az bir sınıf seçilmeli
    if data.uygun and not (data.uygun_sinif_seviyeleri or []):
        raise HTTPException(status_code=400, detail="'Uygun' için en az bir sınıf seviyesi seçmelisiniz.")
    # Aynı öğretmen aynı egzersizi bir daha değerlendiremez
    var = await db.egzersiz_kalite_degerlendirme.find_one(
        {"egzersiz_id": data.egzersiz_id, "ogretmen_id": current_user["id"]})
    if var:
        raise HTTPException(status_code=409, detail="Bu egzersizi zaten değerlendirdiniz.")

    talep = (data.degisiklik_talebi or "").strip() or None
    doc = {
        "id": str(uuid.uuid4()),
        "egzersiz_id": data.egzersiz_id,
        "egzersiz_tipi": egz.get("tip"),
        "ogretmen_id": current_user["id"],
        "ogretmen_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip(),
        "tarih": iso(),
        "uygun": bool(data.uygun),
        "uygun_sinif_seviyeleri": data.uygun_sinif_seviyeleri or [],
        "degisiklik_talebi": talep,
    }
    await db.egzersiz_kalite_degerlendirme.insert_one(doc)

    # XP: değerlendirme (küçük) + değişiklik talebi (biraz daha yüksek) — katkı rollerine
    puanlar = await get_puan_ayarlari()
    kazanilan = int(puanlar.get("egzersiz_degerlendirme", 1))
    if talep:
        kazanilan += int(puanlar.get("degisiklik_talebi", 2))
    await db.users.update_one({"id": current_user["id"]}, {"$inc": {"puan": kazanilan}})

    askiya_alindi, agg = await _agregasyonu_guncelle(data.egzersiz_id)
    if askiya_alindi:
        await islem_kaydet(current_user, "egzersiz_kalite", "otomatik_askiya_alma",
                           hedef_tip="egzersiz", hedef_id=data.egzersiz_id,
                           ekstra={"olumsuz_esik": agg.get("kalite_uygun_degil_sayisi", 0)})
    return {"ok": True, "kazanilan_xp": kazanilan, "askiya_alindi": askiya_alindi,
            "durum": agg.get("durum", egz.get("durum", "aktif"))}


# ═══════════════════════════════════════════════════════════════════
# ADMIN/KOORDİNATÖR: bekleyenler kuyruğu + karar
# ═══════════════════════════════════════════════════════════════════
@router.get("/egzersiz-kalite/bekleyenler")
async def kalite_bekleyenler(current_user=Depends(_YETKILI)):
    """Askıya alınmış egzersizler + değerlendirme detayları (değişiklik talepleri dahil)."""
    egzersizler = await db.egzersiz_icerikler.find({"durum": "askida"}).sort(
        "kalite_askiya_tarihi", -1).to_list(length=None)
    out = []
    for e in egzersizler:
        degs = await db.egzersiz_kalite_degerlendirme.find({"egzersiz_id": e["id"]}).to_list(length=None)
        talepler = [{"ogretmen_ad": d.get("ogretmen_ad", ""), "uygun": d.get("uygun"),
                     "degisiklik_talebi": d.get("degisiklik_talebi"), "tarih": d.get("tarih")}
                    for d in degs]
        out.append({
            "egzersiz_id": e["id"], "tip": e.get("tip"), "tip_ad": _tip_ad(e.get("tip")),
            "sinif": e.get("sinif"), "konu": e.get("konu", ""), "zorluk": e.get("zorluk", "orta"),
            "icerik": e.get("icerik"),
            "uygun_sayisi": e.get("kalite_uygun_sayisi", 0),
            "uygun_degil_sayisi": e.get("kalite_uygun_degil_sayisi", 0),
            "degisiklik_talebi_sayisi": e.get("kalite_degisiklik_talebi_sayisi", 0),
            "askiya_tarihi": e.get("kalite_askiya_tarihi"),
            "degerlendirmeler": talepler,
        })
    return {"toplam": len(out), "egzersizler": out}


@router.post("/egzersiz-kalite/{egzersiz_id}/aktif-et")
async def kalite_aktif_et(egzersiz_id: str, current_user=Depends(_YETKILI)):
    """Askıdaki egzersizi (düzeltildikten sonra) tekrar aktifleştir."""
    egz = await db.egzersiz_icerikler.find_one({"id": egzersiz_id})
    if not egz:
        raise HTTPException(status_code=404, detail="Egzersiz bulunamadı")
    await db.egzersiz_icerikler.update_one({"id": egzersiz_id},
        {"$set": {"durum": "aktif"}, "$unset": {"kalite_askiya_tarihi": ""}})
    await islem_kaydet(current_user, "egzersiz_kalite", "tekrar_aktif",
                       hedef_tip="egzersiz", hedef_id=egzersiz_id)
    return {"ok": True, "durum": "aktif"}


@router.post("/egzersiz-kalite/{egzersiz_id}/retire")
async def kalite_retire(egzersiz_id: str, current_user=Depends(_YETKILI)):
    """Egzersizi kalıcı olarak kaldır (retired) — öğrencilere bir daha sunulmaz."""
    egz = await db.egzersiz_icerikler.find_one({"id": egzersiz_id})
    if not egz:
        raise HTTPException(status_code=404, detail="Egzersiz bulunamadı")
    await db.egzersiz_icerikler.update_one({"id": egzersiz_id}, {"$set": {"durum": "retired"}})
    await islem_kaydet(current_user, "egzersiz_kalite", "retired",
                       hedef_tip="egzersiz", hedef_id=egzersiz_id)
    return {"ok": True, "durum": "retired"}


class DegisiklikUygula(BaseModel):
    icerik: dict


@router.patch("/egzersiz-kalite/{egzersiz_id}/icerik")
async def kalite_icerik_duzelt(egzersiz_id: str, data: DegisiklikUygula, current_user=Depends(_YETKILI)):
    """Admin/koordinatör egzersiz içeriğini düzeltir (değişiklik talebi doğrultusunda)."""
    egz = await db.egzersiz_icerikler.find_one({"id": egzersiz_id})
    if not egz:
        raise HTTPException(status_code=404, detail="Egzersiz bulunamadı")
    await db.egzersiz_icerikler.update_one({"id": egzersiz_id}, {"$set": {"icerik": data.icerik}})
    await islem_kaydet(current_user, "egzersiz_kalite", "icerik_duzeltme",
                       hedef_tip="egzersiz", hedef_id=egzersiz_id)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# AYARLAR (admin/koordinatör): eşikler
# ═══════════════════════════════════════════════════════════════════
@router.get("/egzersiz-kalite/ayarlar")
async def kalite_ayar_getir(current_user=Depends(_YETKILI)):
    return await get_kalite_kontrol_ayarlari()


@router.put("/egzersiz-kalite/ayarlar")
async def kalite_ayar_kaydet(payload: dict = Body(...), current_user=Depends(_YETKILI)):
    temiz = {}
    for k in ("askiya_alma_esigi", "sinif_uygunluk_esigi", "dogrulama_esigi"):
        if k in payload:
            try:
                temiz[k] = max(1, int(payload[k]))
            except (ValueError, TypeError):
                pass
    ad = f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip()
    await set_kalite_kontrol_ayarlari(temiz, guncelleyen=ad)
    return {"ok": True, "degerler": await get_kalite_kontrol_ayarlari()}
