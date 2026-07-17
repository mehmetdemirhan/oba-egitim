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

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.db import db
from core.auth import get_current_user, require_role, UserRole
from modules.timi_metin import (
    timi_rapor_uret, get_rapor_metinleri, set_rapor_metinleri, _varsayilan_paket,
)

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

# ── Puanlama anahtarı VARSAYILANI (timi_scoring_key.json > cards) ──
# kart_no → (A görselinin kategorisi, B görselinin kategorisi).
# Bu doğrulanmış sabit yalnızca VARSAYILANDIR; canlı anahtar DB'de tutulur ve
# Koordinatör/Yönetici panelinden düzenlenebilir (bkz. get_timi_kartlar /
# /timi/anahtar). DB boşsa/eksikse daima buraya düşülür — varsayılan kaybolmaz.
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


def timi_puanla(yanitlar: List[dict], kartlar: dict = None) -> dict:
    """Yanıt listesinden ({kart_no, secim}) kategori puanlarını hesaplar.

    Her seçim, seçilen görselin bağlı olduğu zeka kategorisine +1 puan işler.
    Sonuç, KATEGORI_SIRASI'ndaki tüm anahtarları içerir (seçilmeyenler 0).
    `kartlar` verilmezse doğrulanmış varsayılan (TIMI_KARTLAR) kullanılır; canlı
    puanlamada çağıran, DB'deki güncel anahtarı (get_timi_kartlar) geçirir.
    """
    if kartlar is None:
        kartlar = TIMI_KARTLAR
    puanlar = {k: 0 for k in KATEGORI_SIRASI}
    for y in yanitlar:
        kart_no = y.get("kart_no") if isinstance(y, dict) else getattr(y, "kart_no", None)
        secim = (y.get("secim") if isinstance(y, dict) else getattr(y, "secim", "")) or ""
        if kart_no not in kartlar:
            continue
        a_cat, b_cat = kartlar[kart_no]
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
# Puanlama anahtarı — DB katmanı (Koordinatör/Yönetici düzenlenebilir)
# ─────────────────────────────────────────────
# Anahtar db.sistem_ayarlari'nda {tip, degerler, guncelleyen, guncelleme_tarihi}
# olarak tutulur (rapor_ayarlari deseniyle tutarlı). DB boşsa doğrulanmış
# TIMI_KARTLAR varsayılanına düşülür → varsayılan asla kaybolmaz (ayrı seed'e
# gerek yok; getter'ın fallback'i seed görevini görür).
TIMI_ANAHTAR_TIP = "timi_puanlama_anahtari"


async def get_timi_kartlar():
    """(kartlar_map {int:(a,b)}, guncelleme_tarihi|None) döndürür; DB yoksa varsayılan."""
    doc = await db.sistem_ayarlari.find_one({"tip": TIMI_ANAHTAR_TIP})
    if doc and doc.get("degerler"):
        kartlar = {}
        for k, v in doc["degerler"].items():
            try:
                kartlar[int(k)] = (int(v["a"]), int(v["b"]))
            except (KeyError, ValueError, TypeError):
                continue
        if len(kartlar) == TIMI_KART_SAYISI:
            return kartlar, doc.get("guncelleme_tarihi")
    return dict(TIMI_KARTLAR), None


async def set_timi_kartlar(kartlar_map, guncelleyen: str = "") -> str:
    """Anahtarı DB'ye yazar (upsert); guncelleme_tarihi ISO string döndürür."""
    now = datetime.now(timezone.utc).isoformat()
    degerler = {str(no): {"a": a, "b": b} for no, (a, b) in kartlar_map.items()}
    await db.sistem_ayarlari.update_one(
        {"tip": TIMI_ANAHTAR_TIP},
        {"$set": {"tip": TIMI_ANAHTAR_TIP, "degerler": degerler,
                  "guncelleme_tarihi": now, "guncelleyen": guncelleyen}},
        upsert=True,
    )
    return now


def anahtar_denge(kartlar_map) -> dict:
    """Her kategori anahtarının kaç kez göründüğü (dengeli envanterde hepsi 8)."""
    sayac = {k: 0 for k in KATEGORI_SIRASI}
    for (a, b) in kartlar_map.values():
        for cat in (a, b):
            if cat in TIMI_KATEGORILER:
                sayac[TIMI_KATEGORILER[cat]["key"]] += 1
    return sayac


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


class TimiAnahtarKart(BaseModel):
    kart_no: int = Field(ge=1, le=TIMI_KART_SAYISI)
    a_kategori: int = Field(ge=1, le=7)
    b_kategori: int = Field(ge=1, le=7)


class TimiAnahtarGuncelle(BaseModel):
    kartlar: List[TimiAnahtarKart]


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


# ── Puanlama anahtarı yönetimi (yalnız Koordinatör/Yönetici) ──
# NOT: Bu route'lar /timi/{sonuc_id} catch-all'ından ÖNCE tanımlanmalı.
def _anahtar_yaniti(kartlar_map, guncelleme_tarihi, guncelleyen=""):
    denge = anahtar_denge(kartlar_map)
    return {
        "kartlar": [
            {"kart_no": no, "a_kategori": a, "b_kategori": b}
            for no, (a, b) in sorted(kartlar_map.items())
        ],
        "kategoriler": {
            i: {"key": TIMI_KATEGORILER[i]["key"], "tr": TIMI_KATEGORILER[i]["tr"]}
            for i in range(1, 8)
        },
        "denge": denge,
        "dengeli": all(v == 8 for v in denge.values()),
        "guncelleme_tarihi": guncelleme_tarihi,
        "guncelleyen": guncelleyen,
    }


@router.get("/timi/anahtar")
async def get_timi_anahtar(current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Canlı puanlama anahtarı (DB → varsayılan) + kategori adları + denge bilgisi."""
    kartlar, tarih = await get_timi_kartlar()
    doc = await db.sistem_ayarlari.find_one({"tip": TIMI_ANAHTAR_TIP})
    guncelleyen = (doc or {}).get("guncelleyen", "")
    return _anahtar_yaniti(kartlar, tarih, guncelleyen)


@router.put("/timi/anahtar")
async def put_timi_anahtar(data: TimiAnahtarGuncelle,
                           current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Anahtarı toplu kaydeder. Denge (her kategori 8×) ENGELLENMEZ; yanıtta bilgi
    olarak döner — uyarıyı frontend gösterir."""
    if len(data.kartlar) != TIMI_KART_SAYISI:
        raise HTTPException(status_code=400, detail=f"28 kart gerekli ({len(data.kartlar)} geldi)")
    kartlar_map = {k.kart_no: (k.a_kategori, k.b_kategori) for k in data.kartlar}
    if len(kartlar_map) != TIMI_KART_SAYISI:
        raise HTTPException(status_code=400, detail="Kart numaraları 1–28 arası benzersiz olmalı")
    ad = f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip()
    tarih = await set_timi_kartlar(kartlar_map, guncelleyen=ad)
    return {"ok": True, **_anahtar_yaniti(kartlar_map, tarih, ad)}


@router.post("/timi/anahtar/varsayilana-don")
async def timi_anahtar_varsayilana_don(current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """DB kaydını siler → doğrulanmış varsayılan anahtara döner."""
    await db.sistem_ayarlari.delete_one({"tip": TIMI_ANAHTAR_TIP})
    return {"ok": True, **_anahtar_yaniti(dict(TIMI_KARTLAR), None, "")}


# ─────────────────────────────────────────────
# Rapor Metin Bankası (yalnız Yönetici/Koordinatör) — /timi/{sonuc_id} catch-all'ından ÖNCE
# ─────────────────────────────────────────────
@router.get("/timi/rapor-metinleri")
async def get_timi_rapor_metinleri(current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Canlı rapor metin bankası (DB → varsayılan) + varsayılan (sıfırlama için) + alan sözlüğü."""
    metinler, tarih = await get_rapor_metinleri(db)
    doc = await db.sistem_ayarlari.find_one({"tip": "timi_rapor_metinleri"})
    return {
        "metinler": metinler,
        "varsayilan": _varsayilan_paket(),
        "kategoriler": [{"key": TIMI_KATEGORILER[i]["key"], "tr": TIMI_KATEGORILER[i]["tr"]} for i in range(1, 8)],
        "guncelleme_tarihi": tarih,
        "guncelleyen": (doc or {}).get("guncelleyen", ""),
    }


@router.put("/timi/rapor-metinleri")
async def put_timi_rapor_metinleri(data: dict = Body(...),
                                   current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Metin bankasını toplu kaydeder (alan bazlı; eksik alanlar üretimde varsayılana düşer)."""
    metinler = data.get("metinler")
    if not isinstance(metinler, dict):
        raise HTTPException(status_code=400, detail="metinler (nesne) gerekli")
    ad = f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip()
    tarih = await set_rapor_metinleri(db, metinler, guncelleyen=ad)
    return {"ok": True, "guncelleme_tarihi": tarih, "guncelleyen": ad}


@router.post("/timi/rapor-metinleri/varsayilana-don")
async def timi_rapor_metinleri_varsayilana_don(current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    await db.sistem_ayarlari.delete_one({"tip": "timi_rapor_metinleri"})
    return {"ok": True, "metinler": _varsayilan_paket()}


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

    # Puanlama, o ANDAKİ canlı anahtarla yapılır; kullanılan anahtar sürümü
    # (guncelleme_tarihi) sonuca damgalanır. Geçmiş sonuçlar sonradan anahtar
    # değişse bile YENİDEN hesaplanmaz — kayıtlı kategori_puanlari kalıcıdır.
    kartlar, anahtar_tarihi = await get_timi_kartlar()
    kategori_puanlari = timi_puanla(yanitlar, kartlar)
    baskin = baskin_zeka_alanlari(kategori_puanlari)
    now = datetime.now(timezone.utc).isoformat()
    guncelle = {
        "durum": "tamamlandi",
        "yanitlar": sorted(yanitlar, key=lambda y: y.get("kart_no", 0)),
        "kategori_puanlari": kategori_puanlari,
        "baskin_zeka_alanlari": baskin,
        "kullanilan_anahtar_tarihi": anahtar_tarihi or "varsayilan",
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
    await _taslak_temizlik_throttle()  # cron yoksa: günde bir kez taslak temizliği
    q = {}
    if current_user.get("role") == "teacher":
        q["ogretmen_id"] = current_user["id"]
    items = await db.timi_sonuclar.find(q).sort("created_at", -1).to_list(length=None)
    for i in items:
        i.pop("_id", None)
    return items


@router.get("/timi/ogrenci/{ogrenci_id}")
async def timi_ogrenci_gecmisi(ogrenci_id: str, current_user=Depends(get_current_user)):
    if not _yetkili(current_user):
        raise HTTPException(status_code=403, detail="Bu TIMI kaydına erişim yetkiniz yok")
    items = await db.timi_sonuclar.find(
        {"ogrenci_id": ogrenci_id, "durum": "tamamlandi"}
    ).sort("uygulama_tarihi", -1).to_list(length=None)
    for i in items:
        i.pop("_id", None)
    return items


@router.get("/timi/{sonuc_id}")
async def timi_sonuc_getir(sonuc_id: str, current_user=Depends(get_current_user)):
    if not _yetkili(current_user):
        raise HTTPException(status_code=403, detail="Bu TIMI sonucuna erişim yetkiniz yok")
    sonuc = await db.timi_sonuclar.find_one({"id": sonuc_id})
    if not sonuc:
        raise HTTPException(status_code=404, detail="TIMI sonucu bulunamadı")
    sonuc.pop("_id", None)
    return sonuc


async def _rapor_bolumleri(sonuc: dict) -> dict:
    """Sonuçtan deterministik anlatı raporu (metin bankası DB → varsayılan)."""
    metinler, _ = await get_rapor_metinleri(db)
    return timi_rapor_uret(sonuc.get("kategori_puanlari", {}) or {}, metinler)


@router.get("/timi/{sonuc_id}/rapor")
async def timi_rapor_getir(sonuc_id: str, current_user=Depends(get_current_user)):
    """Tam anlatılı rapor (ekran görünümü) — PDF ile AYNI bölümler; deterministik, AI yok."""
    if not _yetkili(current_user):
        raise HTTPException(status_code=403, detail="Yetkisiz")
    sonuc = await db.timi_sonuclar.find_one({"id": sonuc_id})
    if not sonuc:
        raise HTTPException(status_code=404, detail="TIMI sonucu bulunamadı")
    sonuc.pop("_id", None)
    return {"sonuc": sonuc, "rapor": await _rapor_bolumleri(sonuc)}


# ── Taslak (yarım kalan) otomatik temizlik yardımcıları ──
def _yas_gun(created_at, now) -> int | None:
    if not created_at:
        return None
    try:
        d = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (now - d).days
    except Exception:
        return None


async def _taslak_temizlik() -> dict:
    """15 günü geçmiş tamamlanmamış taslakları siler; 13-15 gün arası olanlara (silmeden ~2
    gün önce) uygulayan öğretmene BİR KEZ uyarı gönderir. Her silme islem_log'a düşer."""
    now = datetime.now(timezone.utc)
    from core.audit import islem_kaydet
    sistem = {"id": "system", "role": "system", "ad": "Sistem", "soyad": ""}
    silinen = uyarilan = 0
    taslaklar = await db.timi_sonuclar.find({"durum": {"$ne": "tamamlandi"}}).to_list(length=10000)
    for s in taslaklar:
        yas = _yas_gun(s.get("created_at"), now)
        if yas is None:
            continue
        if yas >= 15:
            await db.timi_sonuclar.delete_one({"id": s["id"]})
            await islem_kaydet(sistem, "timi", "taslak_oto_sil", "timi_sonuc", s["id"], "yas_gun", yas, "silindi")
            silinen += 1
        elif yas >= 13 and not s.get("silme_uyari_tarihi"):
            try:
                from modules.bildirim import bildirim_olustur
                await bildirim_olustur(s.get("ogretmen_id"), "timi_taslak_uyari",
                                       "Yarım kalan bir TIMI taslağın ~2 gün içinde otomatik silinecek — devam etmek ister misin?", s["id"])
            except Exception:
                pass
            await db.timi_sonuclar.update_one({"id": s["id"]}, {"$set": {"silme_uyari_tarihi": now.isoformat()}})
            uyarilan += 1
    return {"ok": True, "silinen": silinen, "uyarilan": uyarilan}


async def _taslak_temizlik_throttle():
    """Cron yoksa: ilk-istek tetikli, günde bir kez (sessions okumasından çağrılır)."""
    try:
        son = await db.sistem_ayarlari.find_one({"tip": "timi_taslak_temizlik_son"})
        now = datetime.now(timezone.utc)
        if son and son.get("zaman"):
            d = _yas_gun(son["zaman"], now)
            if d is not None and d < 1:
                return
        await db.sistem_ayarlari.update_one({"tip": "timi_taslak_temizlik_son"},
            {"$set": {"tip": "timi_taslak_temizlik_son", "zaman": now.isoformat()}}, upsert=True)
        await _taslak_temizlik()
    except Exception:
        pass


@router.post("/timi/gunluk-temizlik")
async def timi_gunluk_temizlik(anahtar: str = Query(default="")):
    """Harici cron (günlük) — token korumalı (push.py deseni)."""
    from core.config import PUSH_CRON_TOKEN
    if PUSH_CRON_TOKEN and anahtar != PUSH_CRON_TOKEN:
        raise HTTPException(status_code=403, detail="Geçersiz anahtar")
    return await _taslak_temizlik()


@router.get("/timi/{sonuc_id}/pdf")
async def timi_pdf(sonuc_id: str, current_user=Depends(get_current_user)):
    """TIMI sonuç raporu PDF'i — grafik + baskın zeka vurgusu + öğrenci/tarih.
    Mevcut Gelişim PDF altyapısını (reportlab + TR font) yeniden kullanır."""
    if not _yetkili(current_user):
        raise HTTPException(status_code=403, detail="Yetkisiz")
    sonuc = await db.timi_sonuclar.find_one({"id": sonuc_id})
    if not sonuc:
        raise HTTPException(status_code=404, detail="TIMI sonucu bulunamadı")
    if sonuc.get("durum") != "tamamlandi":
        raise HTTPException(status_code=400, detail="Yalnız tamamlanmış TIMI raporu PDF olarak alınabilir")

    ogr = await db.students.find_one({"id": sonuc.get("ogrenci_id")}) or {}
    ogretmen = await db.users.find_one({"id": sonuc.get("ogretmen_id")}) or {}

    import io
    from modules.diagnostic import _tr_font
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph as RLPara, Spacer, Table as RLTable, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.graphics.shapes import Drawing, Rect, String
    FONT, FONTB = _tr_font()
    MAVI = colors.HexColor('#1F4E79'); ACIK = colors.HexColor('#F2F7FB')
    VURGU = colors.HexColor('#F39C12'); BAR = colors.HexColor('#3B7DD8')

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TT', fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=4, textColor=colors.white, fontName=FONTB))
    styles.add(ParagraphStyle(name='TS', fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=2, textColor=colors.HexColor('#DCE9F7'), fontName=FONT))
    styles.add(ParagraphStyle(name='TSect', fontSize=12, leading=16, spaceBefore=14, spaceAfter=8, textColor=MAVI, fontName=FONTB))
    styles.add(ParagraphStyle(name='TBody', fontSize=10, leading=15, fontName=FONT, spaceAfter=3))
    styles.add(ParagraphStyle(name='TListe', fontSize=10, leading=15, fontName=FONT, leftIndent=12, spaceAfter=2))

    kp = sonuc.get("kategori_puanlari", {}) or {}
    baskin = sonuc.get("baskin_zeka_alanlari", []) or []
    en_yuksek = max([kp.get(k, 0) for k in KATEGORI_SIRASI] + [1])

    el = []
    # Kapak başlığı — kurumsal renkli şerit (kurum adı + rapor adı)
    kapak = RLTable([[RLPara("Okuma Becerileri Akademisi", styles['TT'])],
                     [RLPara("TIMI Çoklu Zekâ Envanteri Raporu", styles['TS'])]], colWidths=[17*cm])
    kapak.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), MAVI), ('TOPPADDING', (0,0), (-1,0), 16),
        ('BOTTOMPADDING', (0,-1), (-1,-1), 14), ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('ROUNDEDCORNERS', [6, 6, 6, 6])]))
    el.append(kapak)
    el.append(Spacer(1, 12))
    el.append(RLPara("Öğrenci Bilgileri", styles['TSect']))
    info = [
        ["Adı Soyadı:", f"{ogr.get('ad','')} {ogr.get('soyad','')}".strip() or "-", "Sınıfı:", sonuc.get("sinif_seviyesi") or ogr.get("sinif", "-")],
        ["Eğitimci:", f"{ogretmen.get('ad','')} {ogretmen.get('soyad','')}".strip() or "-", "Tarih:", (sonuc.get("uygulama_tarihi") or sonuc.get("created_at") or "")[:10]],
    ]
    t = RLTable(info, colWidths=[3*cm, 5*cm, 3*cm, 5*cm])
    t.setStyle(TableStyle([('FONTNAME', (0,0), (0,-1), FONTB), ('FONTNAME', (2,0), (2,-1), FONTB),
        ('FONTNAME', (1,0), (1,-1), FONT), ('FONTNAME', (3,0), (3,-1), FONT), ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), MAVI), ('TEXTCOLOR', (2,0), (2,-1), MAVI),
        ('BACKGROUND', (0,0), (-1,-1), ACIK), ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#CCC')),
        ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor('#DDD')), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('PADDING', (0,0), (-1,-1), 6)]))
    el.append(t)

    # Baskın zeka vurgusu
    baskin_tr = [TIMI_KATEGORILER[i]["tr"] for i in range(1, 8) if TIMI_KATEGORILER[i]["key"] in baskin]
    el.append(RLPara("Baskın Zeka Alanı" + ("ları" if len(baskin_tr) > 1 else ""), styles['TSect']))
    vurgu_t = RLTable([[", ".join(baskin_tr) or "-"]], colWidths=[16*cm])
    vurgu_t.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), FONTB), ('FONTSIZE', (0,0), (-1,-1), 12),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.white), ('BACKGROUND', (0,0), (-1,-1), VURGU),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('PADDING', (0,0), (-1,-1), 10)]))
    el.append(vurgu_t)

    # Kategori grafiği (yatay bar)
    el.append(RLPara("Zeka Alanları Dağılımı", styles['TSect']))
    satir_yuksek = 22
    d = Drawing(460, satir_yuksek * len(KATEGORI_SIRASI) + 10)
    for idx, k in enumerate(KATEGORI_SIRASI):
        puan = kp.get(k, 0)
        y = d.height - (idx + 1) * satir_yuksek
        etiket = TIMI_KATEGORILER[idx + 1]["tr"]
        d.add(String(2, y + 6, etiket, fontName=FONT, fontSize=8, fillColor=colors.HexColor('#333')))
        bar_x = 190
        tam_gen = 230
        gen = (puan / en_yuksek) * tam_gen if en_yuksek else 0
        d.add(Rect(bar_x, y + 2, tam_gen, 12, fillColor=ACIK, strokeColor=colors.HexColor('#DDD'), strokeWidth=0.5))
        renk = VURGU if k in baskin else BAR
        d.add(Rect(bar_x, y + 2, max(gen, 0.5), 12, fillColor=renk, strokeColor=None))
        d.add(String(bar_x + tam_gen + 6, y + 6, str(puan), fontName=FONTB, fontSize=9, fillColor=colors.HexColor('#333')))
    el.append(d)

    # ── TAM ANLATILI RAPOR (deterministik metin bankasından — AI yok) ──
    rapor = await _rapor_bolumleri(sonuc)
    for b in rapor["bolumler"]:
        el.append(RLPara(b["baslik"], styles['TSect']))
        if b.get("tip") == "liste":
            for m in b.get("maddeler", []):
                el.append(RLPara("•&nbsp;&nbsp;" + str(m), styles['TListe']))
        else:
            el.append(RLPara(str(b.get("paragraf", "")), styles['TBody']))

    if sonuc.get("notlar"):
        el.append(RLPara("Uygulayan Öğretmen Notu", styles['TSect']))
        el.append(RLPara(str(sonuc.get("notlar")), styles['TBody']))

    # Alt bilgi: uygulama tarihi + sayfa no
    tarih_str = str(sonuc.get("uygulama_tarihi") or sonuc.get("created_at") or "")[:10]

    def _footer(canvas, docx):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.HexColor('#999999'))
        canvas.drawString(2*cm, 1*cm, f"TIMI Çoklu Zekâ Envanteri Raporu · {tarih_str}")
        canvas.drawRightString(A4[0] - 2*cm, 1*cm, f"Sayfa {docx.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=2*cm, rightMargin=2*cm)
    doc.build(el, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    ad = f"{ogr.get('ad','')}_{ogr.get('soyad','')}".strip("_") or "TIMI"
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="TIMI_Raporu_{ad}.pdf"'})


@router.delete("/timi/{sonuc_id}")
async def timi_sil(sonuc_id: str, onay: bool = Query(default=False), current_user=Depends(get_current_user)):
    """Taslak (yarım kalan) → uygulayan ÖĞRETMEN veya admin/koordinatör silebilir.
    Tamamlanmış rapor → yalnız admin, ayrı onayla (onay=true). Her silme islem_log'a düşer."""
    sonuc = await db.timi_sonuclar.find_one({"id": sonuc_id})
    if not sonuc:
        raise HTTPException(status_code=404, detail="TIMI sonucu bulunamadı")
    rol = current_user.get("role")
    taslak = sonuc.get("durum") != "tamamlandi"
    if taslak:
        sahip = sonuc.get("ogretmen_id") == current_user.get("id")
        if not (sahip or rol in ("admin", "coordinator")):
            raise HTTPException(status_code=403, detail="Bu taslağı silme yetkiniz yok")
    else:
        if rol != "admin":
            raise HTTPException(status_code=403, detail="Tamamlanmış rapor yalnız yönetici tarafından silinebilir")
        if not onay:
            raise HTTPException(status_code=400, detail="Tamamlanmış raporu silmek için onay gerekli")
    await db.timi_sonuclar.delete_one({"id": sonuc_id})
    from core.audit import islem_kaydet
    await islem_kaydet(current_user, "timi", "taslak_sil" if taslak else "rapor_sil",
                       "timi_sonuc", sonuc_id, "durum", sonuc.get("durum"), "silindi")
    return {"message": "Silindi", "taslak": taslak}
