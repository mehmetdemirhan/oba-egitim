"""TIMI (Teele Çoklu Zeka Envanteri) modülü — /timi/*.

Howard Gardner'ın Çoklu Zeka Kuramı'na dayanan, Sue Teele (1992) tarafından
geliştirilmiş, 28 kart / 56 görselden oluşan zorlamalı-seçim (forced-choice)
envanter. Öğretmen, öğrenciyle karşılıklı oturarak her kartta iki panda
görselinden (A/B) öğrencinin özdeşleştiğini seçer; sistem seçimleri 7 zeka
kategorisine göre puanlar ve baskın zeka alanı profili üretir.

Mimari, "Giriş Analizi" (modules/diagnostic.py) modülüyle kardeş kalıptadır:
DB/kimlik erişimi daima core üzerinden yapılır.

Puanlama anahtarı, repo kökündeki doğrulanmış `timi_scoring_key.json` dosyasından
BİREBİR türetilmiş sabittir (her kategori tam 8 kez görsel olarak görünür;
28 kart x 2 = 56, 56/7 = 8). Anahtar burada yeniden üretilmemiş, dosyadaki
doğrulanmış değerler sabitlenmiştir.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import db
from core.auth import get_current_user, UserRole

router = APIRouter()


# ── Kategori tanımları (timi_scoring_key.json > categories) ──
# Kategori numarası → makine anahtarı / Türkçe etiket
TIMI_KATEGORILER = {
    1: {"key": "dilsel",                 "tr": "Dilsel Zeka",                       "en": "Linguistic"},
    2: {"key": "mantiksal_matematiksel", "tr": "Mantıksal-Matematiksel Zeka",       "en": "Logical-Mathematical"},
    3: {"key": "mekansal",               "tr": "Mekansal (Görsel-Uzamsal) Zeka",    "en": "Spatial"},
    4: {"key": "muziksel",               "tr": "Müziksel Zeka",                     "en": "Musical"},
    5: {"key": "bedensel",               "tr": "Bedensel-Kinestetik Zeka",          "en": "Bodily-Kinesthetic"},
    6: {"key": "kisisel",                "tr": "Kişisel (İçsel) Zeka",              "en": "Intrapersonal"},
    7: {"key": "kisilerarasi",           "tr": "Kişilerarası (Sosyal) Zeka",        "en": "Interpersonal"},
}

# Sıralı kategori anahtarları (rapor/tablo düzeni için)
KATEGORI_SIRASI = [TIMI_KATEGORILER[i]["key"] for i in range(1, 8)]

# ── Puanlama anahtarı (timi_scoring_key.json > cards) ──
# kart_no → (A görselinin kategorisi, B görselinin kategorisi)
TIMI_KARTLAR = {
    1:  (1, 3), 2:  (4, 5), 3:  (1, 7), 4:  (7, 2), 5:  (3, 5), 6:  (1, 6), 7:  (4, 3),
    8:  (1, 5), 9:  (2, 3), 10: (4, 7), 11: (1, 4), 12: (1, 2), 13: (6, 5), 14: (6, 7),
    15: (7, 5), 16: (2, 5), 17: (4, 2), 18: (4, 6), 19: (3, 7), 20: (2, 3), 21: (1, 7),
    22: (5, 4), 23: (2, 6), 24: (6, 3), 25: (1, 6), 26: (3, 5), 27: (2, 4), 28: (7, 6),
}
TIMI_KART_SAYISI = 28

# Her zeka alanı için kısa, öğretmen/veli dostu yorum metni
TIMI_YORUMLAR = {
    "dilsel": "Kelimelerle, okuma-yazma ve konuşma yoluyla öğrenmeye yatkındır; hikâye, "
              "kelime oyunları ve sözlü anlatımdan keyif alır.",
    "mantiksal_matematiksel": "Sayılar, örüntüler, mantık ve neden-sonuç ilişkileriyle "
              "düşünmeye yatkındır; problem çözmeyi ve keşfetmeyi sever.",
    "mekansal": "Görsellerle, renklerle, şekil ve haritalarla düşünmeye yatkındır; çizim, "
              "yapbozlar ve görsel tasarımdan keyif alır.",
    "muziksel": "Ritim, melodi ve seslere duyarlıdır; müzik dinleyerek, mırıldanarak veya "
              "ritim tutarak öğrenmeye eğilimlidir.",
    "bedensel": "Hareket ederek, dokunarak ve yaparak öğrenmeye yatkındır; el becerileri, "
              "spor ve uygulamalı etkinliklerden keyif alır.",
    "kisisel": "Kendi iç dünyasına, duygularına ve hedeflerine dönüktür; bağımsız çalışmayı "
              "ve üzerine düşünmeyi sever.",
    "kisilerarasi": "Başkalarını anlama ve onlarla iş birliği yapmaya yatkındır; grup "
              "çalışması, paylaşım ve sosyal etkileşimden keyif alır.",
}

# Rapor altına eklenecek ihtiyatlı dil / psikometrik uyarı notu
TIMI_UYARI_NOTU = (
    "Bu envanter öğrencinin kendi algıladığı ilgi ve tercihlerini ölçen keşfedici bir "
    "araçtır; kesin/klinik bir zeka testi değildir. Sonuçlar tek başına değil, öğretmen "
    "gözlemleriyle birlikte değerlendirilmelidir."
)


def timi_puanla(yanitlar: List[dict]) -> dict:
    """Yanıt listesinden ({kart_no, secim}) kategori puanlarını hesaplar.

    Her seçim, seçilen görselin bağlı olduğu zeka kategorisine +1 puan işler.
    Sonuç, KATEGORI_SIRASI'ndaki tüm anahtarları içerir (seçilmeyenler 0).
    """
    puanlar = {k: 0 for k in KATEGORI_SIRASI}
    for y in yanitlar:
        kart_no = y.get("kart_no") if isinstance(y, dict) else getattr(y, "kart_no", None)
        secim = (y.get("secim") if isinstance(y, dict) else getattr(y, "secim", "")) or ""
        if kart_no not in TIMI_KARTLAR:
            continue
        a_cat, b_cat = TIMI_KARTLAR[kart_no]
        cat = a_cat if secim.upper() == "A" else b_cat if secim.upper() == "B" else None
        if cat is None:
            continue
        puanlar[TIMI_KATEGORILER[cat]["key"]] += 1
    return puanlar


def baskin_zeka_alanlari(kategori_puanlari: dict) -> List[str]:
    """En yüksek puanlı kategori anahtarlarını döndürür (eşitlikte hepsi listelenir)."""
    if not kategori_puanlari:
        return []
    en_yuksek = max(kategori_puanlari.values())
    if en_yuksek <= 0:
        return []
    return [k for k in KATEGORI_SIRASI if kategori_puanlari.get(k, 0) == en_yuksek]


# ─────────────────────────────────────────────
# Pydantic modelleri
# ─────────────────────────────────────────────
class TimiBaslat(BaseModel):
    ogrenci_id: str
    notlar: str = ""


class TimiYanit(BaseModel):
    kart_no: int = Field(ge=1, le=TIMI_KART_SAYISI)
    secim: str  # "A" | "B"


class TimiTamamla(BaseModel):
    # Frontend tüm yanıtları yerelde toplayıp gönderebilir; boşsa DB'deki
    # kademeli kaydedilmiş yanıtlar kullanılır.
    yanitlar: Optional[List[TimiYanit]] = None
    notlar: str = ""


def _yetkili(current_user) -> bool:
    return current_user.get("role") in ["admin", "coordinator", "teacher"]


# ─────────────────────────────────────────────
# Meta / puanlama anahtarı
# ─────────────────────────────────────────────
@router.get("/timi/meta")
async def get_timi_meta(current_user=Depends(get_current_user)):
    """Kategori tanımları, kart sayısı, yorum metinleri ve uyarı notu."""
    return {
        "kart_sayisi": TIMI_KART_SAYISI,
        "kategoriler": {
            TIMI_KATEGORILER[i]["key"]: {
                "no": i,
                "tr": TIMI_KATEGORILER[i]["tr"],
                "en": TIMI_KATEGORILER[i]["en"],
            } for i in range(1, 8)
        },
        "kategori_sirasi": KATEGORI_SIRASI,
        "yorumlar": TIMI_YORUMLAR,
        "uyari_notu": TIMI_UYARI_NOTU,
    }


# ─────────────────────────────────────────────
# Oturum / uygulama akışı
# ─────────────────────────────────────────────
@router.post("/timi/baslat")
async def timi_baslat(data: TimiBaslat, current_user=Depends(get_current_user)):
    if not _yetkili(current_user):
        raise HTTPException(status_code=403, detail="Yetkisiz")
    ogrenci = await db.students.find_one({"id": data.ogrenci_id})
    if not ogrenci:
        raise HTTPException(status_code=404, detail=f"Öğrenci bulunamadı: {data.ogrenci_id}")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": data.ogrenci_id,
        "ogretmen_id": current_user["id"],
        "sinif_seviyesi": ogrenci.get("sinif", ""),
        "durum": "devam",  # devam | tamamlandi
        "yanitlar": [],
        "kategori_puanlari": {},
        "baskin_zeka_alanlari": [],
        "notlar": data.notlar or "",
        "uygulama_tarihi": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.timi_sonuclar.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/timi/{sonuc_id}/yanit")
async def timi_yanit_kaydet(sonuc_id: str, data: TimiYanit, current_user=Depends(get_current_user)):
    """Tek bir kart yanıtını kademeli olarak kaydeder (varsa üzerine yazar)."""
    if not _yetkili(current_user):
        raise HTTPException(status_code=403, detail="Yetkisiz")
    sonuc = await db.timi_sonuclar.find_one({"id": sonuc_id})
    if not sonuc:
        raise HTTPException(status_code=404, detail="TIMI oturumu bulunamadı")
    secim = (data.secim or "").upper()
    if secim not in ("A", "B"):
        raise HTTPException(status_code=400, detail="Seçim A veya B olmalı")

    yanitlar = [y for y in sonuc.get("yanitlar", []) if y.get("kart_no") != data.kart_no]
    yanitlar.append({"kart_no": data.kart_no, "secim": secim})
    yanitlar.sort(key=lambda y: y.get("kart_no", 0))
    await db.timi_sonuclar.update_one(
        {"id": sonuc_id},
        {"$set": {"yanitlar": yanitlar, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"kart_no": data.kart_no, "secim": secim, "yanit_sayisi": len(yanitlar)}


@router.post("/timi/{sonuc_id}/tamamla")
async def timi_tamamla(sonuc_id: str, data: TimiTamamla, current_user=Depends(get_current_user)):
    if not _yetkili(current_user):
        raise HTTPException(status_code=403, detail="Yetkisiz")
    sonuc = await db.timi_sonuclar.find_one({"id": sonuc_id})
    if not sonuc:
        raise HTTPException(status_code=404, detail="TIMI oturumu bulunamadı")

    # Yanıtlar: istekte geldiyse onu kullan, yoksa kademeli kaydedileni kullan
    if data.yanitlar is not None:
        yanitlar = [{"kart_no": y.kart_no, "secim": (y.secim or "").upper()} for y in data.yanitlar]
    else:
        yanitlar = sonuc.get("yanitlar", [])

    if len(yanitlar) != TIMI_KART_SAYISI:
        raise HTTPException(
            status_code=400,
            detail=f"28 kartın tamamı yanıtlanmalı ({len(yanitlar)}/{TIMI_KART_SAYISI})",
        )

    kategori_puanlari = timi_puanla(yanitlar)
    baskin = baskin_zeka_alanlari(kategori_puanlari)
    now = datetime.now(timezone.utc).isoformat()
    guncelle = {
        "durum": "tamamlandi",
        "yanitlar": sorted(yanitlar, key=lambda y: y.get("kart_no", 0)),
        "kategori_puanlari": kategori_puanlari,
        "baskin_zeka_alanlari": baskin,
        "notlar": data.notlar or sonuc.get("notlar", ""),
        "uygulama_tarihi": now,
        "updated_at": now,
    }
    await db.timi_sonuclar.update_one({"id": sonuc_id}, {"$set": guncelle})
    sonuc.update(guncelle)
    sonuc.pop("_id", None)
    return sonuc


# ─────────────────────────────────────────────
# Sorgulama
# ─────────────────────────────────────────────
@router.get("/timi/sessions")
async def timi_sessions(current_user=Depends(get_current_user)):
    """Panel listesi — öğretmen yalnızca kendi uyguladıklarını görür."""
    q = {}
    if current_user.get("role") == "teacher":
        q["ogretmen_id"] = current_user["id"]
    items = await db.timi_sonuclar.find(q).sort("created_at", -1).to_list(length=None)
    for i in items:
        i.pop("_id", None)
    return items


@router.get("/timi/ogrenci/{ogrenci_id}")
async def timi_ogrenci_gecmisi(ogrenci_id: str, current_user=Depends(get_current_user)):
    items = await db.timi_sonuclar.find(
        {"ogrenci_id": ogrenci_id, "durum": "tamamlandi"}
    ).sort("uygulama_tarihi", -1).to_list(length=None)
    for i in items:
        i.pop("_id", None)
    return items


@router.get("/timi/{sonuc_id}")
async def timi_sonuc_getir(sonuc_id: str, current_user=Depends(get_current_user)):
    sonuc = await db.timi_sonuclar.find_one({"id": sonuc_id})
    if not sonuc:
        raise HTTPException(status_code=404, detail="TIMI sonucu bulunamadı")
    sonuc.pop("_id", None)
    return sonuc


@router.delete("/timi/{sonuc_id}")
async def timi_sil(sonuc_id: str, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    await db.timi_sonuclar.delete_one({"id": sonuc_id})
    return {"message": "Silindi"}
