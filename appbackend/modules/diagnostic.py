"""Tanılama (diagnostic) modülü — /diagnostic/* ve PDF rapor üretimi.

server.py'dan BİREBİR taşındı; yollar ve davranış değişmedi. Norm tablosu,
metin havuzu, analiz oturumları, rapor oluşturma ve PDF çıktısı tek modülde.
İçerik katkı puanları core.sistem.get_puan_ayarlari üzerinden okunur.
"""
import io
import os
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.db import db
from core.auth import get_current_user, require_role, UserRole
from core.sistem import get_puan_ayarlari
from modules.bildirim import bildirim_rapor_tamamlandi

router = APIRouter()


# Varsayılan norm tablosu (admin değiştirebilir)
VARSAYILAN_NORMLAR = {
    "1": {"dusuk": 25, "orta": 40, "yeterli": 60},
    "2": {"dusuk": 55, "orta": 75, "yeterli": 95},
    "3": {"dusuk": 65, "orta": 90, "yeterli": 115},
    "4": {"dusuk": 80, "orta": 110, "yeterli": 140},
    "5": {"dusuk": 90, "orta": 120, "yeterli": 150},
    "6": {"dusuk": 100, "orta": 135, "yeterli": 170},
    "7": {"dusuk": 110, "orta": 150, "yeterli": 185},
    "8": {"dusuk": 120, "orta": 160, "yeterli": 200},
}

async def get_norm_tablosu():
    doc = await db.sistem_ayarlari.find_one({"tip": "okuma_hizi_normlari"})
    if doc:
        return doc.get("normlar", VARSAYILAN_NORMLAR)
    return VARSAYILAN_NORMLAR

async def hiz_degerlendirme(sinif: str, wpm: float) -> str:
    normlar = await get_norm_tablosu()
    sinif_no = sinif.replace("-", "").replace(".", "").strip()[:1]
    n = normlar.get(sinif_no, normlar.get("4", VARSAYILAN_NORMLAR["4"]))
    if wpm <= n["dusuk"]:
        return "dusuk"
    elif wpm <= n["orta"]:
        return "orta"
    elif wpm <= n["yeterli"]:
        return "yeterli"
    else:
        return "ileri"

async def kur_onerisi_hesapla(wpm: float, dogruluk: float, sinif: str) -> str:
    hiz = await hiz_degerlendirme(sinif, wpm)
    if dogruluk >= 97 and hiz in ("yeterli", "ileri"):
        return "Kur 3"
    elif dogruluk >= 93 and hiz in ("orta", "yeterli", "ileri"):
        return "Kur 2"
    else:
        return "Kur 1"


# ── Norm Tablosu Yönetimi ──
class NormGuncelle(BaseModel):
    normlar: dict  # {"1": {"dusuk": 25, "orta": 40, "yeterli": 60}, ...}

@router.get("/diagnostic/normlar")
async def get_normlar(current_user=Depends(get_current_user)):
    return await get_norm_tablosu()

@router.put("/diagnostic/normlar")
async def update_normlar(data: NormGuncelle, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    await db.sistem_ayarlari.update_one(
        {"tip": "okuma_hizi_normlari"},
        {"$set": {"tip": "okuma_hizi_normlari", "normlar": data.normlar}},
        upsert=True
    )
    return {"message": "Norm tablosu güncellendi", "normlar": data.normlar}



# ─────────────────────────────────────────────
# ★ EKSİK MODELLER VE ENDPOINT'LER (EKLENDİ)
# ─────────────────────────────────────────────

# Metin oluşturma modeli — frontend MetinYonetimi bileşeni kullanıyor
class MetinCreate(BaseModel):
    baslik: str
    icerik: str
    kelime_sayisi: int = 0
    sinif_seviyesi: str = "4"
    tur: str = "hikaye"  # hikaye, bilgilendirici, siir

# Metin oylama modeli — metin_oy_ver endpoint'i kullanıyor (NameError düzeltmesi)
class MetinOyCreate(BaseModel):
    metin_id: str
    onay: bool
    sebep: str = ""


# ★ Metin ekleme endpoint'i (frontend: axios.post(`${API}/diagnostic/texts`, ...))
@router.post("/diagnostic/texts")
async def create_metin(data: MetinCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")

    # Kelime sayısı otomatik hesapla (0 geldiyse)
    kelime_sayisi = data.kelime_sayisi
    if kelime_sayisi == 0 and data.icerik:
        kelime_sayisi = len(data.icerik.strip().split())

    # Admin/Koordinatör eklerse direkt oylama, öğretmen eklerse beklemede
    durum = "oylama" if role in ["admin", "coordinator"] else "beklemede"

    metin_doc = {
        "id": str(uuid.uuid4()),
        "baslik": data.baslik,
        "icerik": data.icerik,
        "kelime_sayisi": kelime_sayisi,
        "sinif_seviyesi": data.sinif_seviyesi,
        "tur": data.tur,
        "durum": durum,
        "ekleyen_id": current_user["id"],
        "ekleyen_ad": f"{current_user.get('ad', '')} {current_user.get('soyad', '')}",
        "oylar": {},
        "olusturma_tarihi": datetime.now(timezone.utc).isoformat(),
        "yayin_tarihi": None,
    }
    await db.analiz_metinler.insert_one(metin_doc)

    # Ekleyene puan ver (dinamik)
    puanlar = await get_puan_ayarlari()
    await db.users.update_one({"id": current_user["id"]}, {"$inc": {"puan": puanlar.get("metin_ekleme", 5)}})

    metin_doc.pop("_id", None)
    return metin_doc


# ★ Metin listeleme endpoint'i (frontend: axios.get(`${API}/diagnostic/texts`))
@router.get("/diagnostic/texts")
async def get_metinler(sinif_seviyesi: Optional[str] = None, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    user_id = current_user.get("id", "")

    query = {}
    if sinif_seviyesi:
        m = re.search(r"\d+", sinif_seviyesi)
        if m:
            query["sinif_seviyesi"] = m.group()

    items = await db.analiz_metinler.find(query).sort("olusturma_tarihi", -1).to_list(length=None)
    result = []
    for item in items:
        item.pop("_id", None)
        durum = item.get("durum", "")

        # Admin her şeyi görür
        if role == "admin":
            result.append(item)
        # Öğretmen: kendi eklediği + oylama bekleyenler + havuzdakiler
        elif role == "teacher":
            if item.get("ekleyen_id") == user_id:
                result.append(item)
            elif durum in ("oylama", "havuzda"):
                result.append(item)
        # Öğrenci/diğer: sadece havuzdakiler
        else:
            if durum == "havuzda":
                result.append(item)

    return result


# ─────────────────────────────────────────────
# MEVCUT GİRİŞ ANALİZİ ROUTE'LARI
# ─────────────────────────────────────────────

@router.post("/diagnostic/texts/{metin_id}/admin-karar")
async def metin_admin_karar(metin_id: str, karar: dict, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    # karar: {"onay": True/False, "direkt": True/False}
    # direkt=True → oylama atla, direkt havuza al
    onay = karar.get("onay", False)
    direkt = karar.get("direkt", False)
    if not onay:
        yeni_durum = "reddedildi"
    elif direkt:
        yeni_durum = "havuzda"
        # Ekleyene bonus puan (havuza direkt girince - dinamik)
        puanlar = await get_puan_ayarlari()
        metin = await db.analiz_metinler.find_one({"id": metin_id})
        if metin and metin.get("ekleyen_id"):
            await db.users.update_one({"id": metin["ekleyen_id"]}, {"$inc": {"puan": puanlar.get("metin_havuza_girme", 10)}})
    else:
        yeni_durum = "oylama"
    await db.analiz_metinler.update_one(
        {"id": metin_id},
        {"$set": {"durum": yeni_durum, **({"yayin_tarihi": datetime.utcnow().isoformat()} if yeni_durum == "havuzda" else {})}}
    )
    return {"durum": yeni_durum}

@router.post("/diagnostic/texts/oy")
async def metin_oy_ver(oy: MetinOyCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Sadece öğretmenler oy verebilir")
    if not oy.onay and not oy.sebep:
        raise HTTPException(status_code=400, detail="Red için sebep belirtmelisiniz")
    metin = await db.analiz_metinler.find_one({"id": oy.metin_id})
    if not metin:
        raise HTTPException(status_code=404, detail="Metin bulunamadı")
    if metin.get("durum") != "oylama":
        raise HTTPException(status_code=400, detail="Bu metin oylamada değil")
    user_id = current_user["id"]
    oylar = metin.get("oylar", {})
    if user_id in oylar:
        raise HTTPException(status_code=400, detail="Zaten oy kullandınız")
    oylar[user_id] = {"onay": oy.onay, "sebep": oy.sebep}
    await db.analiz_metinler.update_one({"id": oy.metin_id}, {"$set": {"oylar": oylar}})
    # Oy veren öğretmene puan (dinamik)
    puanlar = await get_puan_ayarlari()
    await db.users.update_one({"id": user_id}, {"$inc": {"puan": puanlar.get("oylama_katilim", 2)}})
    # %60 kontrolü
    ogretmenler = await db.users.find({"role": {"$in": ["teacher", "coordinator", "admin"]}}).to_list(length=None)
    toplam = len(ogretmenler)
    onay_sayisi = sum(1 for v in oylar.values() if v.get("onay"))
    oy_sayisi = len(oylar)
    yeni_durum = metin.get("durum")
    if toplam > 0:
        onay_orani = onay_sayisi / toplam
        if onay_orani >= 0.6:
            yeni_durum = "havuzda"
            await db.analiz_metinler.update_one(
                {"id": oy.metin_id},
                {"$set": {"durum": "havuzda", "yayin_tarihi": datetime.utcnow().isoformat()}}
            )
            # Metni ekleyene bonus puan (havuza girince - dinamik)
            ekleyen_id = metin.get("ekleyen_id")
            if ekleyen_id:
                await db.users.update_one({"id": ekleyen_id}, {"$inc": {"puan": puanlar.get("metin_havuza_girme", 10)}})
        elif oy_sayisi == toplam and onay_orani < 0.6:
            yeni_durum = "reddedildi"
            await db.analiz_metinler.update_one({"id": oy.metin_id}, {"$set": {"durum": "reddedildi"}})
    return {
        "mesaj": f"Oyunuz kaydedildi (+{puanlar.get('oylama_katilim', 2)} puan)",
        "durum": yeni_durum,
        "onay_orani": round(onay_sayisi / max(toplam, 1) * 100),
        "oy_sayisi": oy_sayisi,
        "toplam": toplam
    }

@router.delete("/diagnostic/texts/{metin_id}")
async def delete_metin(metin_id: str, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    await db.analiz_metinler.delete_one({"id": metin_id})
    return {"message": "Silindi"}

# ── Analiz Oturumları ──
class HataKaydi(BaseModel):
    tip: str  # atlama, yanlis_okuma, takilma, tekrar
    kelime: str = ""

class AnalizOturumBaslat(BaseModel):
    ogrenci_id: str
    metin_id: str

class AnalizTamamla(BaseModel):
    sure_saniye: float
    hatalar: List[HataKaydi]
    gozlem_notu: str = ""
    ogretmen_kur: str = ""

class DiagnosticOturum(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ogrenci_id: str
    metin_id: str
    ogretmen_id: str
    durum: str = "devam"
    sure_saniye: float = 0
    hatalar: List[dict] = []
    gozlem_notu: str = ""
    wpm: float = 0
    dogruluk_yuzde: float = 0
    hiz_deger: str = ""
    sistem_kur: str = ""
    ogretmen_kur: str = ""
    olusturma_tarihi: datetime = Field(default_factory=datetime.utcnow)
    tamamlama_tarihi: Optional[datetime] = None

@router.post("/diagnostic/sessions")
async def baslat_oturum(data: AnalizOturumBaslat, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    # Metni bul (id veya _id ile)
    metin = await db.analiz_metinler.find_one({"id": data.metin_id})
    if not metin:
        raise HTTPException(status_code=404, detail=f"Metin bulunamadı: {data.metin_id}")
    # Öğrenciyi kontrol et
    ogrenci = await db.students.find_one({"id": data.ogrenci_id})
    if not ogrenci:
        raise HTTPException(status_code=404, detail=f"Öğrenci bulunamadı: {data.ogrenci_id}")
    oturum = DiagnosticOturum(
        ogrenci_id=data.ogrenci_id,
        metin_id=data.metin_id,
        ogretmen_id=current_user["id"]
    )
    d = oturum.dict()
    d["olusturma_tarihi"] = d["olusturma_tarihi"].isoformat()
    d["tamamlama_tarihi"] = None
    await db.diagnostic_oturumlar.insert_one(d)
    d.pop("_id", None)
    return d

@router.get("/diagnostic/sessions")
async def get_oturumlar(current_user=Depends(get_current_user)):
    q = {}
    if current_user.get("role") == "teacher":
        q["ogretmen_id"] = current_user["id"]
    items = await db.diagnostic_oturumlar.find(q).sort("olusturma_tarihi", -1).to_list(length=None)
    for i in items: i.pop("_id", None)
    return items

@router.get("/diagnostic/sessions/student/{ogrenci_id}")
async def get_ogrenci_oturumlari(ogrenci_id: str, current_user=Depends(get_current_user)):
    items = await db.diagnostic_oturumlar.find({"ogrenci_id": ogrenci_id}).sort("olusturma_tarihi", -1).to_list(length=None)
    for i in items: i.pop("_id", None)
    return items

@router.post("/diagnostic/sessions/{oturum_id}/complete")
async def tamamla_oturum(oturum_id: str, data: AnalizTamamla, current_user=Depends(get_current_user)):
    oturum = await db.diagnostic_oturumlar.find_one({"id": oturum_id})
    if not oturum:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")

    metin = await db.analiz_metinler.find_one({"id": oturum["metin_id"]})
    kelime_sayisi = metin.get("kelime_sayisi", 100) if metin else 100
    sinif_seviyesi = metin.get("sinif_seviyesi", "4") if metin else "4"

    # Hesaplamalar
    sure_dakika = data.sure_saniye / 60 if data.sure_saniye > 0 else 1
    wpm = round(kelime_sayisi / sure_dakika, 1)

    toplam_hata = len(data.hatalar)
    dogruluk = round(max(0, (kelime_sayisi - toplam_hata) / kelime_sayisi * 100), 1)

    hiz_deger = await hiz_degerlendirme(sinif_seviyesi, wpm)
    sistem_kur = await kur_onerisi_hesapla(wpm, dogruluk, sinif_seviyesi)
    atanan_kur = data.ogretmen_kur if data.ogretmen_kur else sistem_kur

    # Hata dağılımı
    hata_sayilari = {"atlama": 0, "yanlis_okuma": 0, "takilma": 0, "tekrar": 0}
    for h in data.hatalar:
        tip = h.tip if hasattr(h, "tip") else h.get("tip", "")
        if tip in hata_sayilari:
            hata_sayilari[tip] += 1

    now = datetime.utcnow().isoformat()
    guncelle = {
        "durum": "tamamlandi",
        "sure_saniye": data.sure_saniye,
        "hatalar": [h.dict() if hasattr(h, "dict") else h for h in data.hatalar],
        "gozlem_notu": data.gozlem_notu,
        "wpm": wpm,
        "dogruluk_yuzde": dogruluk,
        "hiz_deger": hiz_deger,
        "sistem_kur": sistem_kur,
        "ogretmen_kur": atanan_kur,
        "tamamlama_tarihi": now
    }
    await db.diagnostic_oturumlar.update_one({"id": oturum_id}, {"$set": guncelle})

    # Öğrencinin kurunu güncelle
    await db.students.update_one({"id": oturum["ogrenci_id"]}, {"$set": {"kur": atanan_kur}})

    return {
        "wpm": wpm,
        "dogruluk_yuzde": dogruluk,
        "hiz_deger": hiz_deger,
        "sistem_kur": sistem_kur,
        "atanan_kur": atanan_kur,
        "hata_sayilari": hata_sayilari,
        "sure_saniye": data.sure_saniye
    }



# ── Rapor Sistemi ──
class AnlamaVeri(BaseModel):
    # 4.1 Sözcük düzeyinde
    cumle_anlama: str = "orta"          # zayif / orta / iyi
    bilinmeyen_sozcuk: str = "orta"
    baglac_zamir: str = "orta"
    # 4.2 Ana yapı
    ana_fikir: str = "orta"
    yardimci_fikir: str = "orta"
    konu: str = "orta"
    baslik_onerme: str = "orta"
    # 4.3 Derin anlama
    neden_sonuc: str = "orta"
    cikarim: str = "orta"
    ipuclari: str = "orta"
    yorumlama: str = "orta"
    # 4.4 Eleştirel
    gorus_bildirme: str = "orta"
    yazar_amaci: str = "orta"
    alternatif_fikir: str = "orta"
    guncelle_hayat: str = "orta"
    # 4.5 Soru performansı
    bilgi: str = "iyi"
    kavrama: str = "iyi"
    uygulama: str = "iyi"
    analiz: str = "iyi"
    sentez: str = "iyi"
    degerlendirme: str = "iyi"
    genel_yuzde: int = 0

class ProzodikVeri(BaseModel):
    noktalama: int = 3    # 1-4 puan
    vurgu: int = 3
    tonlama: int = 3
    akicilik: int = 3
    anlamli_gruplama: int = 3

class RaporOlusturCreate(BaseModel):
    oturum_id: str
    anlama: AnlamaVeri
    prozodik: ProzodikVeri
    ogretmen_notu: str = ""

def anlama_yuzde(anlama: AnlamaVeri) -> int:
    alanlar = [
        anlama.cumle_anlama, anlama.bilinmeyen_sozcuk, anlama.baglac_zamir,
        anlama.ana_fikir, anlama.yardimci_fikir, anlama.konu, anlama.baslik_onerme,
        anlama.neden_sonuc, anlama.cikarim, anlama.ipuclari, anlama.yorumlama,
        anlama.gorus_bildirme, anlama.yazar_amaci, anlama.alternatif_fikir, anlama.guncelle_hayat,
        anlama.bilgi, anlama.kavrama, anlama.uygulama, anlama.analiz, anlama.sentez, anlama.degerlendirme
    ]
    puan_map = {"zayif": 0, "orta": 1, "iyi": 2}
    toplam = sum(puan_map.get(a, 1) for a in alanlar)
    return round(toplam / (len(alanlar) * 2) * 100)

def hiz_metni(hiz_deger: str) -> str:
    return {"dusuk": "düşük", "orta": "orta", "yeterli": "yeterli", "ileri": "ileri"}.get(hiz_deger, "orta")

def prozodik_seviye(toplam: int) -> str:
    if toplam >= 18: return "çok iyi"
    elif toplam >= 14: return "iyi"
    elif toplam >= 10: return "orta"
    else: return "geliştirilmeli"

def anlama_seviye(pct: int) -> str:
    if pct >= 85: return "iyi"
    elif pct >= 70: return "orta"
    else: return "zayıf"

def _hata_sayilari_hesapla(hatalar_raw):
    """Ham hata listesinden [{tur, sayi}] formatına çevir"""
    if not hatalar_raw:
        return []
    # Eğer zaten {tur, sayi} formatındaysa dokunma
    if hatalar_raw and isinstance(hatalar_raw[0], dict) and "sayi" in hatalar_raw[0]:
        return hatalar_raw
    # Ham liste: [{tip: "atlama", kelime: "x"}, ...] → sayılarla topla
    sayac = {}
    for h in hatalar_raw:
        tip = h.get("tip", "") if isinstance(h, dict) else ""
        if tip:
            sayac[tip] = sayac.get(tip, 0) + 1
    hata_labels = {"atlama": "Atlama", "yanlis_okuma": "Yanlış Okuma", "takilma": "Takılma", "tekrar": "Tekrar"}
    result = []
    for tip, sayi in sayac.items():
        result.append({"tur": tip, "sayi": sayi})
    # Eğer hiç hata yoksa standart 4 türü 0 olarak göster
    if not result:
        for tip in ["atlama", "yanlis_okuma", "takilma", "tekrar"]:
            result.append({"tur": tip, "sayi": 0})
    return result

@router.post("/diagnostic/rapor")
async def olustur_rapor(data: RaporOlusturCreate, current_user=Depends(get_current_user)):
    oturum = await db.diagnostic_oturumlar.find_one({"id": data.oturum_id})
    if not oturum:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")

    metin = await db.analiz_metinler.find_one({"id": oturum.get("metin_id")})
    ogrenci = await db.students.find_one({"id": oturum.get("ogrenci_id")})
    ogretmen = await db.users.find_one({"id": oturum.get("ogretmen_id")})

    prozodik_toplam = data.prozodik.noktalama + data.prozodik.vurgu + data.prozodik.tonlama + data.prozodik.akicilik + data.prozodik.anlamli_gruplama
    anlama_pct = data.anlama.genel_yuzde if data.anlama.genel_yuzde > 0 else anlama_yuzde(data.anlama)

    rapor_data = {
        "id": str(uuid.uuid4()),
        "oturum_id": data.oturum_id,
        "ogrenci_id": oturum.get("ogrenci_id"),
        "ogretmen_id": oturum.get("ogretmen_id"),
        "ogrenci_ad": f"{ogrenci.get('ad','')} {ogrenci.get('soyad','')}" if ogrenci else "",
        "ogrenci_sinif": ogrenci.get("sinif", "") if ogrenci else "",
        "ogretmen_ad": f"{ogretmen.get('ad','')} {ogretmen.get('soyad','')}" if ogretmen else "",
        "metin_adi": metin.get("baslik", "") if metin else "",
        "metin_turu": metin.get("tur", "") if metin else "",
        "kelime_sayisi": metin.get("kelime_sayisi", 0) if metin else 0,
        "sure_saniye": oturum.get("sure_saniye", 0),
        "wpm": oturum.get("wpm", 0),
        "dogruluk_yuzde": oturum.get("dogruluk_yuzde", 0),
        "hiz_deger": oturum.get("hiz_deger", ""),
        "atanan_kur": oturum.get("ogretmen_kur", ""),
        "hata_sayilari": _hata_sayilari_hesapla(oturum.get("hatalar", [])),
        "anlama": data.anlama.dict(),
        "anlama_yuzde": anlama_pct,
        "prozodik": data.prozodik.dict(),
        "prozodik_toplam": prozodik_toplam,
        "ogretmen_notu": data.ogretmen_notu,
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.diagnostic_raporlar.insert_one(rapor_data)
    rapor_data.pop("_id", None)
    # Veliye bildirim gönder
    try: await bildirim_rapor_tamamlandi(rapor_data.get("ogrenci_id"), rapor_data.get("baslik", "Giriş Analizi Raporu"))
    except: pass
    return rapor_data

@router.get("/diagnostic/rapor/ogrenci/{ogrenci_id}")
async def get_ogrenci_raporlari(ogrenci_id: str, current_user=Depends(get_current_user)):
    items = await db.diagnostic_raporlar.find({"ogrenci_id": ogrenci_id}).sort("olusturma_tarihi", -1).to_list(length=None)
    for i in items: i.pop("_id", None)
    return items

@router.get("/diagnostic/rapor/{rapor_id}")
async def get_rapor(rapor_id: str, current_user=Depends(get_current_user)):
    rapor = await db.diagnostic_raporlar.find_one({"id": rapor_id})
    if not rapor:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı")
    rapor.pop("_id", None)
    return rapor


# ── PDF Rapor Üretimi ──
def _tr_upper(text):
    """Türkçe büyük harf çevirimi (i→İ, ı→I)"""
    if not text:
        return text
    tr_map = str.maketrans("abcçdefgğhıijklmnoöprsştuüvyz", "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ")
    return text.translate(tr_map)

@router.get("/diagnostic/rapor/{rapor_id}/pdf")
async def get_rapor_pdf(rapor_id: str, current_user=Depends(get_current_user)):
    rapor = await db.diagnostic_raporlar.find_one({"id": rapor_id})
    if not rapor:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı")
    rapor.pop("_id", None)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph as RLPara, Spacer, Table as RLTable, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # ── Türkçe Font Kaydı ──
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    font_registered = False
    for fp in font_paths:
        if os.path.exists(fp):
            font_registered = True
            break

    if font_registered:
        pdfmetrics.registerFont(TTFont("TRFont", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont("TRFontBold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
        FONT = "TRFont"
        FONTB = "TRFontBold"
    else:
        FONT = "Helvetica"
        FONTB = "Helvetica-Bold"

    buffer = io.BytesIO()
    doc_pdf = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=2*cm, rightMargin=2*cm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleOBA', fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=4, textColor=colors.HexColor('#1F4E79'), fontName=FONTB))
    styles.add(ParagraphStyle(name='SubOBA', fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=16, textColor=colors.HexColor('#666666'), fontName=FONT))
    styles.add(ParagraphStyle(name='SectOBA', fontSize=12, leading=16, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor('#1F4E79'), fontName=FONTB))
    styles.add(ParagraphStyle(name='SubSectOBA', fontSize=10, leading=13, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor('#333333'), fontName=FONTB))
    styles.add(ParagraphStyle(name='BodyOBA', fontSize=9, leading=13, spaceAfter=4, fontName=FONT))
    styles.add(ParagraphStyle(name='SmallOBA', fontSize=8, leading=11, textColor=colors.HexColor('#999999'), fontName=FONT))
    styles.add(ParagraphStyle(name='BigNum', fontSize=28, leading=32, textColor=colors.HexColor('#1F4E79'), fontName=FONTB))

    el = []  # elements

    hdr_bg = colors.HexColor('#1F4E79')
    alt_bg = colors.HexColor('#F2F7FB')
    bdr = colors.HexColor('#CCCCCC')
    ora = colors.HexColor('#E67E22')

    def tbl_style(rows, has_header=True):
        s = [
            ('FONTNAME', (0,0), (-1,-1), FONT),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('GRID', (0,0), (-1,-1), 0.5, bdr),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]
        if has_header:
            s += [
                ('BACKGROUND', (0,0), (-1,0), hdr_bg),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), FONTB),
            ]
        for i in range(1 if has_header else 0, rows):
            if i % 2 == 0:
                s.append(('BACKGROUND', (0,i), (-1,i), alt_bg))
        return s

    # ── BAŞLIK ──
    el.append(RLPara("Okuma Becerileri Akademisi", styles['TitleOBA']))
    el.append(RLPara("Giriş Analizi Raporu", styles['SubOBA']))

    # ── 1. ÖĞRENCİ BİLGİLERİ ──
    el.append(RLPara("1. Öğrenci Bilgileri", styles['SectOBA']))
    w1, w2, w3, w4 = 3*cm, 5*cm, 3*cm, 5*cm
    info = [
        ["Adı Soyadı:", rapor.get("ogrenci_ad", "-"), "Sınıfı:", rapor.get("ogrenci_sinif", "-")],
        ["Eğitimci:", rapor.get("ogretmen_ad", "-"), "Tarih:", rapor.get("olusturma_tarihi", "")[:10]],
    ]
    t = RLTable(info, colWidths=[w1, w2, w3, w4])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), FONTB), ('FONTNAME', (2,0), (2,-1), FONTB),
        ('FONTNAME', (1,0), (1,-1), FONT), ('FONTNAME', (3,0), (3,-1), FONT),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), hdr_bg), ('TEXTCOLOR', (2,0), (2,-1), hdr_bg),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5), ('TOPPADDING', (0,0), (-1,-1), 5),
    ]))
    el.append(t)

    # ── 2. METİN BİLGİLERİ ──
    el.append(RLPara("2. Metin Bilgileri", styles['SectOBA']))
    kelime_s = rapor.get("kelime_sayisi", 0)
    dogruluk = rapor.get("dogruluk_yuzde", 0)
    yanlis_k = round(kelime_s * (100 - dogruluk) / 100) if kelime_s else 0
    dogru_k = kelime_s - yanlis_k
    sure_sn_total = rapor.get("sure_saniye", 0)
    sure_dk = int(sure_sn_total) // 60
    sure_sn = int(sure_sn_total) % 60
    metin_info = [
        ["Metnin Adı:", _tr_upper(rapor.get("metin_adi", "-"))],
        ["Metnin Türü:", _tr_upper(rapor.get("metin_turu", "-"))],
        ["Toplam Kelime Sayısı:", str(kelime_s)],
        ["Doğru Okunan Kelime:", str(dogru_k)],
        ["Yanlış Okunan Kelime:", str(yanlis_k)],
        ["Tamamlama Süresi:", f"{sure_dk}:{str(sure_sn).zfill(2)} ({sure_sn_total} sn)"],
    ]
    t2 = RLTable(metin_info, colWidths=[5*cm, 11*cm])
    t2.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), FONTB), ('FONTNAME', (1,0), (1,-1), FONT),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, bdr),
        ('BACKGROUND', (0,0), (0,-1), alt_bg),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5), ('TOPPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    el.append(t2)

    # ── 3. OKUMA HIZI ──
    el.append(RLPara("3. Okuma Hızı", styles['SectOBA']))
    wpm = round(rapor.get("wpm", 0))
    hiz_map = {"dusuk": "Düşük", "orta": "Orta", "yeterli": "Yeterli", "ileri": "İleri"}
    hiz_label = hiz_map.get(rapor.get("hiz_deger", ""), "?")
    hiz_renk = {"dusuk": "#E74C3C", "orta": "#F39C12", "yeterli": "#27AE60", "ileri": "#2E86C1"}.get(rapor.get("hiz_deger", ""), "#333")
    el.append(RLPara(f'<font size="28" color="{hiz_renk}"><b>{wpm}</b></font>  <font size="10">kelime/dakika</font>', styles['BodyOBA']))
    el.append(RLPara(f'<font size="12" color="{hiz_renk}"><b>{hiz_label} Düzey</b></font>', styles['BodyOBA']))
    el.append(Spacer(1, 4))
    sinif = rapor.get("ogrenci_sinif", "")
    el.append(RLPara(f"Öğrencinin okuma hızı dakikada <b>{wpm} kelime</b>dir. Bu okuma hızı, öğrencinin bulunduğu sınıf düzeyi normlarına göre <b>{hiz_label.lower()} düzeydedir</b>.", styles['BodyOBA']))

    # ── 4. DOĞRU OKUMA ORANI ──
    el.append(RLPara("3.1. Doğru Okuma Oranı", styles['SubSectOBA']))
    el.append(RLPara(f"Doğruluk: <b>%{round(dogruluk)}</b>", styles['BodyOBA']))
    hatalar = rapor.get("hata_sayilari", [])
    # Dict formatındaysa listeye çevir: {"atlama": 2, ...} → [{"tur": "atlama", "sayi": 2}]
    if isinstance(hatalar, dict):
        hatalar = [{"tur": k, "sayi": v} for k, v in hatalar.items()]
    if hatalar:
        hata_labels = {"atlama": "Atlama", "yanlis_okuma": "Yanlış Okuma", "yanlis": "Yanlış Okuma", "takilma": "Takılma", "tekrar": "Tekrar"}
        hata_desc = {"atlama": "Kelime veya satır atlama", "yanlis_okuma": "Kelimeyi farklı okuma", "yanlis": "Kelimeyi farklı okuma", "takilma": "Kelimede duraksama", "tekrar": "Aynı kelimeyi tekrar okuma"}
        hata_rows = [["Hata Türü", "Açıklama", "Sayı"]]
        toplam_hata = 0
        for h in hatalar:
            tur = h.get("tur", "")
            sayi = h.get("sayi", 0)
            toplam_hata += sayi
            hata_rows.append([hata_labels.get(tur, tur), hata_desc.get(tur, ""), str(sayi)])
        hata_rows.append(["TOPLAM", "", str(toplam_hata)])
        t3 = RLTable(hata_rows, colWidths=[3.5*cm, 6.5*cm, 2*cm])
        t3.setStyle(TableStyle(tbl_style(len(hata_rows)) + [
            ('FONTNAME', (0,-1), (-1,-1), FONTB),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E8F0FE')),
            ('ALIGN', (2,0), (2,-1), 'CENTER'),
        ]))
        el.append(t3)

    # ── 5. OKUDUĞUNU ANLAMA ──
    anlama = rapor.get("anlama", {})
    anlama_pct = rapor.get("anlama_yuzde", 0)
    anlama_sev = "İyi" if anlama_pct >= 85 else "Orta" if anlama_pct >= 70 else "Zayıf"
    el.append(RLPara(f"4. Okuduğunu Anlama Becerileri — %{anlama_pct}", styles['SectOBA']))

    # Anlama alt grupları
    anlama_gruplari = [
        ("4.1 Sözcük Düzeyinde Anlama", [
            ("Cümle anlamını kavrama", "cumle_anlama"),
            ("Bilinmeyen sözcük tahmini", "bilinmeyen_sozcuk"),
            ("Bağlaç ve zamirleri anlama", "baglac_zamir"),
        ]),
        ("4.2 Metnin Ana Yapısını Anlama", [
            ("Ana fikir belirleme", "ana_fikir"),
            ("Yardımcı fikirleri ifade etme", "yardimci_fikir"),
            ("Metnin konusunu ifade etme", "konu"),
            ("Başlık önerme", "baslik_onerme"),
        ]),
        ("4.3 Metinler Arasılık ve Derin Anlama", [
            ("Neden-sonuç ilişkisini belirleme", "neden_sonuc"),
            ("Çıkarım yapma", "cikarim"),
            ("Metindeki ipuçlarını kullanma", "ipuclari"),
            ("Yorumlama", "yorumlama"),
        ]),
        ("4.4 Eleştirel ve Yaratıcı Okuma", [
            ("Metne yönelik görüş bildirme", "gorus_bildirme"),
            ("Yazarın amacını sezme", "yazar_amaci"),
            ("Alternatif son / fikir üretme", "alternatif_fikir"),
            ("Metni günlük hayatla ilişkilendirme", "guncelle_hayat"),
        ]),
        ("4.5 Soru Performans Analizi", [
            ("Bilgi", "bilgi"),
            ("Kavrama", "kavrama"),
            ("Uygulama", "uygulama"),
            ("Analiz", "analiz"),
            ("Sentez", "sentez"),
            ("Değerlendirme", "degerlendirme"),
        ]),
    ]

    seviye_map = {"zayif": "Zayıf", "orta": "Orta", "iyi": "İyi"}
    for grup_baslik, olcutler in anlama_gruplari:
        el.append(RLPara(grup_baslik, styles['SubSectOBA']))
        rows = [["Ölçüt", "Zayıf", "Orta", "İyi"]]
        for label, key in olcutler:
            val = anlama.get(key, "orta")
            row = [label]
            for s in ["zayif", "orta", "iyi"]:
                row.append("+" if val == s else "")
            rows.append(row)
        t_a = RLTable(rows, colWidths=[7*cm, 3*cm, 3*cm, 3*cm])
        st = tbl_style(len(rows))
        # Renklendir: + işaretlerini turuncu yap
        for ri in range(1, len(rows)):
            for ci in range(1, 4):
                if rows[ri][ci] == "+":
                    st.append(('TEXTCOLOR', (ci, ri), (ci, ri), ora))
                    st.append(('FONTNAME', (ci, ri), (ci, ri), FONTB))
        st.append(('ALIGN', (1,0), (-1,-1), 'CENTER'))
        t_a.setStyle(TableStyle(st))
        el.append(t_a)

    # ── 6. PROZODİK OKUMA ──
    proz = rapor.get("prozodik", {})
    proz_toplam = rapor.get("prozodik_toplam", 0)
    proz_sev = "Çok İyi" if proz_toplam >= 18 else "İyi" if proz_toplam >= 14 else "Orta" if proz_toplam >= 10 else "Geliştirilmeli"
    el.append(RLPara("5. Prozodik Okuma Ölçeği", styles['SectOBA']))

    proz_desc = {
        "noktalama": ["Uymuyor", "Kısmen", "Çoğunlukla", "Tam ve bilinçli"],
        "vurgu": ["Tek düze", "Yer yer", "Anlama uygun", "Etkili ve bilinçli"],
        "tonlama": ["Monoton", "Sınırlı", "Metne uygun", "Doğal ve etkileyici"],
        "akicilik": ["Sık duraklama", "Kısmi akış", "Genel akıcı", "Kesintisiz"],
        "anlamli_gruplama": ["Sözcük sözcük", "Kısmen", "Çoğunlukla", "Tam ve tutarlı"],
    }
    proz_labels = {"noktalama": "Noktalama ve Duraklama", "vurgu": "Vurgu", "tonlama": "Tonlama", "akicilik": "Akıcılık", "anlamli_gruplama": "Anlamlı Gruplama"}

    proz_rows = [["Ölçüt", "1 puan", "2 puan", "3 puan", "4 puan", "Puan"]]
    for key in ["noktalama", "vurgu", "tonlama", "akicilik", "anlamli_gruplama"]:
        puan = proz.get(key, 0)
        descs = proz_desc.get(key, ["", "", "", ""])
        row = [proz_labels.get(key, key)]
        for pi in range(4):
            row.append(descs[pi])
        row.append(str(puan))
        proz_rows.append(row)
    proz_rows.append(["", "", "", "", "Toplam", str(proz_toplam)])

    t_p = RLTable(proz_rows, colWidths=[2.8*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.8*cm, 1.5*cm])
    ps = tbl_style(len(proz_rows))
    # Seçili puanı turuncu yap
    for ri in range(1, len(proz_rows) - 1):
        key = list(proz_desc.keys())[ri - 1]
        puan = proz.get(key, 0)
        if 1 <= puan <= 4:
            ps.append(('TEXTCOLOR', (puan, ri), (puan, ri), ora))
            ps.append(('FONTNAME', (puan, ri), (puan, ri), FONTB))
    ps.append(('ALIGN', (5, 0), (5, -1), 'CENTER'))
    ps.append(('FONTNAME', (0, -1), (-1, -1), FONTB))
    ps.append(('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E8F0FE')))
    t_p.setStyle(TableStyle(ps))
    el.append(t_p)
    el.append(RLPara(f"Prozodik okuma performansı: <b>{proz_sev}</b> (Toplam {proz_toplam}/20)", styles['BodyOBA']))

    # ── 7. SONUÇ VE GENEL YORUM ──
    el.append(RLPara("6. Sonuç ve Genel Yorum", styles['SectOBA']))
    if rapor.get("ogretmen_notu"):
        for line in rapor.get("ogretmen_notu", "").split("\n"):
            if line.strip():
                el.append(RLPara(line.strip(), styles['BodyOBA']))

    # AI Yorumları
    ai = rapor.get("ai_yorumlar", {})
    if ai:
        el.append(Spacer(1, 6))
        ai_labels = {"hiz": "Okuma Hızı", "dogruluk": "Doğru Okuma", "anlama": "Anlama", "prozodik": "Prozodik Okuma", "sonuc": "Sonuç", "oneriler": "Öneriler"}
        for key, label in ai_labels.items():
            if ai.get(key):
                el.append(RLPara(f"<b>{label}:</b> {ai[key]}", styles['BodyOBA']))

    # ── KUR ──
    el.append(Spacer(1, 8))
    el.append(RLPara(f"Atanan Kur: <b>{rapor.get('atanan_kur', '-')}</b>", styles['BodyOBA']))

    # ── ALT BİLGİ ──
    el.append(Spacer(1, 20))
    el.append(HRFlowable(width="100%", thickness=0.5, color=bdr))
    el.append(RLPara("Bu rapor Okuma Becerileri Akademisi sistemi tarafından oluşturulmuştur.", styles['SmallOBA']))

    doc_pdf.build(el)
    buffer.seek(0)

    ogrenci_ad = rapor.get("ogrenci_ad", "ogrenci").replace(" ", "_")
    tarih = rapor.get("olusturma_tarihi", "")[:10]
    filename = f"Rapor_{ogrenci_ad}_{tarih}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


