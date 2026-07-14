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
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field

from core.db import db
from core.auth import get_current_user, require_role, UserRole
from core.sistem import get_puan_ayarlari
from core.metin_zorluk import zorluk_hesapla
from core.rapor_ayarlari import (
    get_rapor_ayari, set_rapor_ayari, DUZENLENEBILIR_TIPLER,
    RAPOR_AYAR_VARSAYILAN, VARSAYILAN_NORMLAR,
)
from modules.bildirim import bildirim_rapor_tamamlandi

router = APIRouter()

# Metin havuzu katkısı yapabilen roller (üçü de EŞİT yetkili)
KATKI_ROLLERI = ("admin", "coordinator", "teacher")


def _serialize_metin(item: dict, role: str) -> dict:
    """Metin dokümanını API yanıtı için hazırlar.

    - `gorsel_prompt` HİÇBİR role dönmez (yalnız backend'de saklı; ileride AI
      görsel üretimi için). `gorsel` ham base64'ü de liste yanıtında taşınmaz —
      yerine `gorsel_var` bayrağı konur (görsel /gorsel endpoint'inden çekilir).
    - Öğrenci/veli: MCQ'ların doğru cevabı ve iç bayrakları (güven, kontrol) gizlenir.
    """
    item = dict(item)
    item.pop("_id", None)
    item.pop("gorsel_prompt", None)
    gorsel = item.pop("gorsel", None)
    item["gorsel_var"] = bool(gorsel)

    egitici = role in KATKI_ROLLERI
    sorular = item.get("sorular") or []
    temiz = []
    for s in sorular:
        s = dict(s)
        if not egitici:
            # Öğrenciye doğru cevap ve iç işaretler sızmasın
            for gizli in ("dogru_cevap", "dogru_cevap_kaynak", "guven",
                          "kontrol_gerekli", "ilk_duzelten_id",
                          "son_duzelten_id", "son_duzelten_tarih"):
                s.pop(gizli, None)
        temiz.append(s)
    if sorular:
        item["sorular"] = temiz

    # Açık uçlu sorular: öğrenciye model cevap / örnek gösterilmez
    acik = item.get("acik_sorular") or []
    if acik and not egitici:
        temiz_acik = []
        for s in acik:
            if isinstance(s, dict):
                s = dict(s)
                s.pop("model_cevap", None)
            temiz_acik.append(s)
        item["acik_sorular"] = temiz_acik
    return item


# Norm tablosu artık core.rapor_ayarlari üzerinden (DB → varsayılan). Getter'lar
# geriye dönük uyum için burada kalıyor ama ayar panelinden yönetiliyor.
async def get_norm_tablosu():
    return await get_rapor_ayari("okuma_hizi_normlari")

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
    esik = await get_rapor_ayari("kur_onerisi_esikleri")
    kur3 = esik.get("kur3_dogruluk", 97)
    kur2 = esik.get("kur2_dogruluk", 93)
    if dogruluk >= kur3 and hiz in ("yeterli", "ileri"):
        return "Kur 3"
    elif dogruluk >= kur2 and hiz in ("orta", "yeterli", "ileri"):
        return "Kur 2"
    else:
        return "Kur 1"


async def dogruluk_seviyesi(dogruluk: float) -> str:
    """Doğru okuma oranını (dogruluk_esikleri ayarına göre) etikete çevirir."""
    esik = await get_rapor_ayari("dogruluk_esikleri")
    if dogruluk >= esik.get("iyi", 98):
        return "İyi"
    if dogruluk >= esik.get("gelistirilmeli", 90):
        return "Geliştirilmeli"
    return "Yetersiz"


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


# ── Rapor Ölçütleri Yönetim Paneli (koordinatör/yönetici) ──
# Tüm rapor ölçütleri sistem_ayarlari'nda tip bazında; panel bunları CRUD eder.
@router.get("/admin/rapor-ayarlari")
async def get_tum_rapor_ayarlari(current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Tüm düzenlenebilir rapor ölçütlerini (DB → varsayılan) tek seferde döner."""
    sonuc = {}
    for tip in DUZENLENEBILIR_TIPLER:
        sonuc[tip] = await get_rapor_ayari(tip)
    return sonuc

@router.get("/admin/rapor-ayarlari/{tip}")
async def get_rapor_ayari_endpoint(tip: str, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    if tip not in DUZENLENEBILIR_TIPLER:
        raise HTTPException(status_code=404, detail=f"Bilinmeyen ayar tipi: {tip}")
    return {"tip": tip, "degerler": await get_rapor_ayari(tip)}

@router.put("/admin/rapor-ayarlari/{tip}")
async def put_rapor_ayari_endpoint(tip: str, payload: dict = Body(...),
                                   current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    if tip not in DUZENLENEBILIR_TIPLER:
        raise HTTPException(status_code=404, detail=f"Bilinmeyen ayar tipi: {tip}")
    degerler = payload.get("degerler")
    if degerler is None:
        raise HTTPException(status_code=400, detail="'degerler' zorunlu")
    ad = f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip()
    await set_rapor_ayari(tip, degerler, guncelleyen=ad)
    return {"ok": True, "tip": tip, "degerler": degerler}

@router.post("/admin/rapor-ayarlari/{tip}/varsayilana-don")
async def rapor_ayari_varsayilana_don(tip: str, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    if tip not in DUZENLENEBILIR_TIPLER:
        raise HTTPException(status_code=404, detail=f"Bilinmeyen ayar tipi: {tip}")
    ad = f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip()
    await set_rapor_ayari(tip, RAPOR_AYAR_VARSAYILAN[tip], guncelleyen=ad)
    return {"ok": True, "tip": tip, "degerler": RAPOR_AYAR_VARSAYILAN[tip]}



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
    bolum: str = "analiz"  # analiz (Analiz havuzu) | okuma_parcalari (Gelişim→Okuma Metinleri)

# Metin oylama modeli — metin_oy_ver endpoint'i kullanıyor (NameError düzeltmesi)
class MetinOyCreate(BaseModel):
    metin_id: str
    onay: bool
    sebep: str = ""


# ★ Metin ekleme endpoint'i (frontend: axios.post(`${API}/diagnostic/texts`, ...))
def _kelime_sinif(k: int) -> str:
    """Akıcı okuma metnini kelime sayısına göre sınıf seviyesine eşler (1-8).
    İçerik ilkokula ağırlıklı olduğundan bantlar buna göre kalibre edilmiştir."""
    if k <= 45:  return "1"
    if k <= 70:  return "2"
    if k <= 105: return "3"
    if k <= 150: return "4"
    if k <= 210: return "5"
    if k <= 280: return "6"
    if k <= 360: return "7"
    return "8"


@router.post("/diagnostic/akici-okuma-goc")
async def akici_okuma_goc(current_user=Depends(require_role(UserRole.ADMIN))):
    """AKICI OKUMA metinlerini (150, sorularıyla) Analiz havuzuna yükler; DİĞER tüm
    metinleri 'Okuma Parçaları' bölümüne taşır (SİLMEZ). Başlık eşleşmesinde mükerrer
    oluşturmaz (mevcut kaydı günceller). İdempotent — tekrar çalıştırılabilir."""
    import json as _json
    import os as _os
    yol = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                        "data", "akici_okuma_metinleri.json")
    if not _os.path.exists(yol):
        raise HTTPException(status_code=404, detail="akici_okuma_metinleri.json bulunamadı")
    with open(yol, encoding="utf-8") as f:
        metinler = _json.load(f)

    now = datetime.utcnow().isoformat()
    # 1) TÜM mevcut metinleri geçici olarak 'okuma_parcalari'na al; 150 yeni metin
    #    aşağıda (başlık+kelime eşleşmesiyle) 'analiz'e geri çekilir. Aynı başlıklı ama
    #    farklı kelime sayılı metinler ayrı sayılır (docx'te tekrar eden başlıklar var).
    toplam_mevcut = await db.analiz_metinler.count_documents({})
    await db.analiz_metinler.update_many({}, {"$set": {"bolum": "okuma_parcalari"}})

    eklenen, guncellenen = 0, 0
    for m in metinler:
        ortak = {
            "baslik": m["baslik"], "icerik": m["icerik"], "kelime_sayisi": m["kelime_sayisi"],
            "sorular": m.get("sorular", []), "acik_uclu": m.get("acik_uclu", []),
            "bolum": "analiz", "durum": "havuzda", "kaynak": "akici_okuma_yeni",
            "sinif_seviyesi": _kelime_sinif(m["kelime_sayisi"]),  # öğrenci sınıfına göre gelsin
            "guncelleme_tarihi": now,
        }
        # Bileşik anahtar: başlık + kelime sayısı (mükerrer başlıkları çökertmemek için)
        mevcut = await db.analiz_metinler.find_one(
            {"baslik": m["baslik"], "kelime_sayisi": m["kelime_sayisi"]})
        if mevcut:
            await db.analiz_metinler.update_one({"id": mevcut["id"]}, {"$set": ortak})
            guncellenen += 1
        else:
            await db.analiz_metinler.insert_one({
                "id": str(uuid.uuid4()), **ortak, "tur": "olcum", "zorluk": "orta",
                "oylar": {}, "ekleyen_id": current_user["id"],
                "olusturma_tarihi": now, "yayin_tarihi": now,
            })
            eklenen += 1
    okuma_parcalari_say = await db.analiz_metinler.count_documents({"bolum": "okuma_parcalari"})
    return {"ok": True, "eklenen": eklenen, "guncellenen": guncellenen,
            "okuma_parcalarina_tasinan": okuma_parcalari_say, "onceki_toplam": toplam_mevcut,
            "toplam_metin": len(metinler)}


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
        "bolum": data.bolum if data.bolum in ("analiz", "okuma_parcalari") else "analiz",
        # Kutulu Okuma metin seçimi için otomatik zorluk etiketi (sezgisel).
        "zorluk": zorluk_hesapla(data.icerik or ""),
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
    await db.users.update_one({"id": current_user["id"]}, {"$inc": {"puan": puanlar.get("metin_ekleme", 2)}})

    metin_doc.pop("_id", None)
    return metin_doc


# ★ Metin GÜNCELLEME (tam ekran düzenleme ekranı → tek Kaydet)
class MetinGuncelle(BaseModel):
    baslik: Optional[str] = None
    icerik: Optional[str] = None
    kelime_sayisi: Optional[int] = None
    sinif_seviyesi: Optional[str] = None
    tur: Optional[str] = None
    zorluk: Optional[str] = None
    sorular: Optional[List[dict]] = None        # MCQ listesi (id ile birleştirilir)
    acik_sorular: Optional[List[dict]] = None   # açık uçlu soru listesi


@router.put("/diagnostic/texts/{metin_id}")
async def metin_guncelle(metin_id: str, data: MetinGuncelle, current_user=Depends(get_current_user)):
    """Metnin içeriğini/sorularını/cevap anahtarını düzenler (tam ekran editör).

    Öğretmen/Koordinatör/Yönetici EŞİT yetkili. Görsel, gorsel_prompt, durum,
    oylar, ekleyen ve kaynak alanlarına DOKUNULMAZ (onlar ayrı akışlarla yönetilir).
    XP yalnız satır-içi hızlı düzeltmede (PATCH .../soru/...) verilir; toplu formda
    verilmez (farming önlemi) — ama XP anti-farm meta'sı korunur.
    """
    from core.acik_soru import normalize_kategori
    role = current_user.get("role", "")
    if role not in KATKI_ROLLERI:
        raise HTTPException(status_code=403, detail="Yetkisiz")

    metin = await db.analiz_metinler.find_one({"id": metin_id})
    if not metin:
        raise HTTPException(status_code=404, detail="Metin bulunamadı")

    now = datetime.now(timezone.utc).isoformat()
    guncel = {}

    if data.baslik is not None:
        guncel["baslik"] = data.baslik
    icerik = data.icerik if data.icerik is not None else metin.get("icerik", "")
    if data.icerik is not None:
        guncel["icerik"] = data.icerik
    # Kelime sayısı: açıkça verildiyse onu, yoksa (içerik değiştiyse) yeniden hesapla
    if data.kelime_sayisi is not None:
        ks = data.kelime_sayisi
    elif data.icerik is not None:
        ks = len((data.icerik or "").strip().split())
    else:
        ks = None
    if ks is not None:
        guncel["kelime_sayisi"] = ks
        guncel["seviye"] = ks   # seviye = kelime sayısı (senkron)
    if data.tur is not None:
        guncel["tur"] = data.tur
    # Zorluk: verildiyse onu, yoksa içerik değiştiyse yeniden hesapla
    if data.zorluk is not None:
        guncel["zorluk"] = data.zorluk
    elif data.icerik is not None:
        guncel["zorluk"] = zorluk_hesapla(icerik or "")
    # sinif_seviyesi: boş string → None (havuz metinleri sınıfsız)
    if data.sinif_seviyesi is not None:
        guncel["sinif_seviyesi"] = (data.sinif_seviyesi or None)

    # ── MCQ soruları: id ile birleştir; XP anti-farm meta'sını koru ──
    if data.sorular is not None:
        mevcut = {s.get("id"): s for s in (metin.get("sorular") or [])}
        yeni = []
        for s in data.sorular:
            sid = s.get("id") or str(uuid.uuid4())
            onceki = mevcut.get(sid, {})
            secenekler = s.get("secenekler", onceki.get("secenekler", {})) or {}
            dogru = (s.get("dogru_cevap") if s.get("dogru_cevap") is not None else onceki.get("dogru_cevap") or "")
            dogru = (dogru or "").strip().upper()
            birlesik = {
                "id": sid,
                "soru": s.get("soru", onceki.get("soru", "")),
                "secenekler": secenekler,
                "dogru_cevap": dogru,
                "dogru_cevap_kaynak": onceki.get("dogru_cevap_kaynak", "otomatik"),
                "guven": s.get("guven", onceki.get("guven", "high")),
                "kontrol_gerekli": bool(s.get("kontrol_gerekli", onceki.get("kontrol_gerekli", False))),
                "ilk_duzelten_id": onceki.get("ilk_duzelten_id"),
                "son_duzelten_id": onceki.get("son_duzelten_id"),
                "son_duzelten_tarih": onceki.get("son_duzelten_tarih"),
            }
            # Doğru cevap değiştiyse: manuel işaretle, kontrol bayrağını düşür
            if dogru and dogru != onceki.get("dogru_cevap"):
                birlesik["dogru_cevap_kaynak"] = "manuel"
                birlesik["kontrol_gerekli"] = False
                birlesik["son_duzelten_id"] = current_user["id"]
                birlesik["son_duzelten_tarih"] = now
            yeni.append(birlesik)
        guncel["sorular"] = yeni

    # ── Açık uçlu sorular: içerik olarak değiştir (id korunur/atanır) ──
    if data.acik_sorular is not None:
        mevcut_a = {s.get("id"): s for s in (metin.get("acik_sorular") or []) if isinstance(s, dict)}
        yeni_a = []
        for i, s in enumerate(data.acik_sorular):
            sid = s.get("id") or str(uuid.uuid4())
            onceki = mevcut_a.get(sid, {})
            kategori_ham = s.get("kategori_ham", s.get("kategori", onceki.get("kategori_ham")))
            yeni_a.append({
                "id": sid,
                "no": s.get("no", onceki.get("no", i + 1)),
                "kategori": normalize_kategori(s.get("kategori", onceki.get("kategori"))),
                "kategori_ham": kategori_ham or None,
                "soru": s.get("soru", onceki.get("soru", "")),
                "model_cevap": s.get("model_cevap", onceki.get("model_cevap")),
                "subjektif": bool(s.get("subjektif", onceki.get("subjektif", False))),
            })
        guncel["acik_sorular"] = yeni_a

    if guncel:
        await db.analiz_metinler.update_one({"id": metin_id}, {"$set": guncel})

    yeni_metin = await db.analiz_metinler.find_one({"id": metin_id})
    return _serialize_metin(yeni_metin, role)


# ★ Metin listeleme endpoint'i (frontend: axios.get(`${API}/diagnostic/texts`))
@router.get("/diagnostic/texts")
async def get_metinler(
    sinif_seviyesi: Optional[str] = None,
    min_kelime: Optional[int] = None,   # SEVİYE (kelime sayısı) alt sınırı
    max_kelime: Optional[int] = None,   # SEVİYE (kelime sayısı) üst sınırı
    bolum: Optional[str] = None,        # None/"analiz" = Analiz havuzu; "okuma_parcalari" = eski metinler
    current_user=Depends(get_current_user),
):
    role = current_user.get("role", "")
    user_id = current_user.get("id", "")

    query = {}
    # Bölüm ayrımı:
    #   bolum="okuma_parcalari" → Gelişim→Okuma Metinleri (eski/taşınan metinler).
    #   bolum="analiz"          → Analiz havuzu (yalnız AKICI OKUMA + analiz etiketli).
    #   bolum yok               → geriye uyumlu: okuma_parcalari HARİÇ tümü.
    if bolum == "okuma_parcalari":
        query["bolum"] = "okuma_parcalari"
    elif bolum == "analiz":
        query["bolum"] = "analiz"
    else:
        query["bolum"] = {"$ne": "okuma_parcalari"}
    if sinif_seviyesi:
        m = re.search(r"\d+", sinif_seviyesi)
        if m:
            # Sınıf filtresi eski (sınıf etiketli) metinler için geçerli; ama seviye
            # (kelime sayısı) bazlı havuz metinleri sinif_seviyesi=null olduğundan
            # HER ZAMAN dahil edilir — aksi halde 159 havuz metni bir öğrenci
            # seçilince dropdown'dan gizlenirdi. Seviye daraltması kelime filtresiyle.
            query["$or"] = [
                {"sinif_seviyesi": m.group()},
                {"sinif_seviyesi": None},
                {"sinif_seviyesi": {"$exists": False}},
            ]
    # Kelime sayısı (seviye) aralık filtresi — akıcı okuma metinleri sınıfa değil
    # kelime sayısına göre seçilir.
    if min_kelime is not None or max_kelime is not None:
        aralik = {}
        if min_kelime is not None:
            aralik["$gte"] = min_kelime
        if max_kelime is not None:
            aralik["$lte"] = max_kelime
        query["kelime_sayisi"] = aralik

    items = await db.analiz_metinler.find(query).sort("olusturma_tarihi", -1).to_list(length=None)
    result = []
    for item in items:
        durum = item.get("durum", "")

        # Admin her şeyi görür
        if role == "admin":
            gorunur = True
        # Öğretmen: kendi eklediği + oylama bekleyenler + havuzdakiler
        elif role == "teacher":
            gorunur = item.get("ekleyen_id") == user_id or durum in ("oylama", "havuzda")
        # Öğrenci/diğer: sadece havuzdakiler
        else:
            gorunur = durum == "havuzda"

        if gorunur:
            result.append(_serialize_metin(item, role))

    return result


# ─────────────────────────────────────────────
# MEVCUT GİRİŞ ANALİZİ ROUTE'LARI
# ─────────────────────────────────────────────

@router.post("/diagnostic/texts/{metin_id}/admin-karar")
async def metin_admin_karar(metin_id: str, karar: dict, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    # karar: {"onay": True/False}
    # Admin kararı öğretmen oylamasını (>%60) BYPASS eder:
    #   onay=True  → metin doğrudan havuza (yayında) alınır, oylama beklenmez
    #   onay=False → metin reddedilir
    # Not: Öğretmen oylaması (metin_oy_ver) hâlâ >%60 kuralıyla yayına alabilir.
    onay = karar.get("onay", False)
    if onay:
        yeni_durum = "havuzda"
        # Ekleyene bonus puan (havuza direkt girince - dinamik)
        puanlar = await get_puan_ayarlari()
        metin = await db.analiz_metinler.find_one({"id": metin_id})
        if metin and metin.get("ekleyen_id"):
            await db.users.update_one({"id": metin["ekleyen_id"]}, {"$inc": {"puan": puanlar.get("metin_havuza_girme", 3)}})
    else:
        yeni_durum = "reddedildi"
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
    await db.users.update_one({"id": user_id}, {"$inc": {"puan": puanlar.get("oylama_katilim", 1)}})
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
                await db.users.update_one({"id": ekleyen_id}, {"$inc": {"puan": puanlar.get("metin_havuza_girme", 3)}})
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


# ─────────────────────────────────────────────
# ★ MCQ DOĞRU CEVAP DÜZELTME (öğretmen/koordinatör/yönetici — eşit yetki)
# ─────────────────────────────────────────────
class SoruCevapGuncelle(BaseModel):
    dogru_cevap: str  # "A" | "B" | "C" | "D"


@router.patch("/diagnostic/texts/{metin_id}/soru/{soru_id}")
async def mcq_cevap_duzelt(metin_id: str, soru_id: str, data: SoruCevapGuncelle,
                           current_user=Depends(get_current_user)):
    """Bir MCQ'nun doğru cevabını manuel olarak işaretler/düzeltir.

    Öğretmen, koordinatör ve yönetici EŞİT yetkiye sahiptir. Bir soru İLK kez
    düzeltildiğinde düzeltene küçük bir XP verilir; sonraki düzeltmeler ödül vermez
    (aynı soruyu tekrar tekrar işaretleyerek puan biriktirme engellenir).
    """
    role = current_user.get("role", "")
    if role not in KATKI_ROLLERI:
        raise HTTPException(status_code=403, detail="Yetkisiz")

    yeni = (data.dogru_cevap or "").strip().upper()
    metin = await db.analiz_metinler.find_one({"id": metin_id})
    if not metin:
        raise HTTPException(status_code=404, detail="Metin bulunamadı")
    sorular = metin.get("sorular") or []
    idx = next((i for i, s in enumerate(sorular) if s.get("id") == soru_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")

    soru = sorular[idx]
    if yeni not in (soru.get("secenekler") or {"A": 1, "B": 1, "C": 1, "D": 1}):
        raise HTTPException(status_code=400, detail="Geçersiz cevap şıkkı")

    ilk_defa = not soru.get("ilk_duzelten_id")
    now = datetime.now(timezone.utc).isoformat()
    soru["dogru_cevap"] = yeni
    soru["dogru_cevap_kaynak"] = "manuel"
    soru["kontrol_gerekli"] = False   # manuel onaylandı → düşük güven bayrağı kalkar
    soru["son_duzelten_id"] = current_user["id"]
    soru["son_duzelten_tarih"] = now
    odul = 0
    if ilk_defa:
        soru["ilk_duzelten_id"] = current_user["id"]

    await db.analiz_metinler.update_one({"id": metin_id}, {"$set": {f"sorular.{idx}": soru}})

    if ilk_defa:
        puanlar = await get_puan_ayarlari()
        odul = puanlar.get("cevap_duzeltme", 2)
        if odul:
            await db.users.update_one({"id": current_user["id"]}, {"$inc": {"puan": odul}})

    return {"soru": soru, "odul": odul, "ilk_defa": ilk_defa}


# ─────────────────────────────────────────────
# ★ METİN GÖRSELİ EKLEME / GETİRME (öğretmen/koordinatör/yönetici — eşit yetki)
# ─────────────────────────────────────────────
_IZINLI_GORSEL_MIME = {"image/jpeg", "image/jpg", "image/png"}
_MAKS_GORSEL_BYTE = 3 * 1024 * 1024  # 3 MB


@router.post("/diagnostic/texts/{metin_id}/gorsel")
async def metin_gorsel_ekle(metin_id: str, dosya: UploadFile = File(...),
                            current_user=Depends(get_current_user)):
    """Metne jpg/png görsel yükler. Yüklenen görsel, saklı `gorsel_prompt`'un
    YERİNE öğrenciye gösterilecek görsel olur. Bir metne İLK görsel eklendiğinde
    ekleyene küçük bir XP verilir; sonraki değişiklikler ödül vermez."""
    import base64
    role = current_user.get("role", "")
    if role not in KATKI_ROLLERI:
        raise HTTPException(status_code=403, detail="Yetkisiz")

    mime = (dosya.content_type or "").lower()
    if mime not in _IZINLI_GORSEL_MIME:
        raise HTTPException(status_code=400, detail="Sadece JPG/PNG yüklenebilir")

    icerik = await dosya.read()
    if len(icerik) > _MAKS_GORSEL_BYTE:
        raise HTTPException(status_code=400, detail="Görsel 3 MB'tan büyük olamaz")

    metin = await db.analiz_metinler.find_one({"id": metin_id})
    if not metin:
        raise HTTPException(status_code=404, detail="Metin bulunamadı")

    ilk_defa = not metin.get("gorsel_ilk_ekleyen_id")
    now = datetime.now(timezone.utc).isoformat()
    gorsel = {
        "dosya_b64": base64.b64encode(icerik).decode("ascii"),
        "mime": mime if mime != "image/jpg" else "image/jpeg",
        "ekleyen_id": current_user["id"],
        "tarih": now,
    }
    set_alan = {"gorsel": gorsel}
    if ilk_defa:
        set_alan["gorsel_ilk_ekleyen_id"] = current_user["id"]
    await db.analiz_metinler.update_one({"id": metin_id}, {"$set": set_alan})

    odul = 0
    if ilk_defa:
        puanlar = await get_puan_ayarlari()
        odul = puanlar.get("gorsel_ekleme", 2)
        if odul:
            await db.users.update_one({"id": current_user["id"]}, {"$inc": {"puan": odul}})

    return {"ok": True, "odul": odul, "ilk_defa": ilk_defa}


@router.get("/diagnostic/texts/{metin_id}/gorsel")
async def metin_gorsel_getir(metin_id: str, current_user=Depends(get_current_user)):
    """Metnin yüklenmiş görselini binary olarak döner (<img src> için).
    Not: `gorsel_prompt` ASLA dönmez — yalnızca yüklenmiş görsel."""
    import base64
    metin = await db.analiz_metinler.find_one({"id": metin_id}, {"gorsel": 1})
    gorsel = (metin or {}).get("gorsel")
    if not gorsel or not gorsel.get("dosya_b64"):
        raise HTTPException(status_code=404, detail="Görsel yok")
    try:
        ham = base64.b64decode(gorsel["dosya_b64"])
    except Exception:
        raise HTTPException(status_code=500, detail="Görsel çözülemedi")
    return Response(content=ham, media_type=gorsel.get("mime", "image/jpeg"))

# ── Analiz Oturumları ──
class HataKaydi(BaseModel):
    tip: str  # atlama, yanlis_okuma, takilma, tekrar
    kelime: str = ""

OTURUM_TIPLERI = ("ilk_analiz", "ara_analiz", "kur_sonu_analiz")

class AnalizOturumBaslat(BaseModel):
    ogrenci_id: str
    metin_id: str
    oturum_tipi: Optional[str] = None  # None → otomatik (ilk tamamlanmışsa ilk_analiz)

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
    oturum_tipi: str = "ilk_analiz"  # ilk_analiz | ara_analiz | kur_sonu_analiz
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
    # Oturum tipi: öğretmen elle seçebilir; seçmezse otomatik — öğrencinin ilk
    # TAMAMLANMIŞ oturumu yoksa "ilk_analiz", varsa "ara_analiz".
    oturum_tipi = data.oturum_tipi
    if oturum_tipi not in OTURUM_TIPLERI:
        tamamlanan = await db.diagnostic_oturumlar.count_documents(
            {"ogrenci_id": data.ogrenci_id, "durum": "tamamlandi"})
        oturum_tipi = "ilk_analiz" if tamamlanan == 0 else "ara_analiz"
    oturum = DiagnosticOturum(
        ogrenci_id=data.ogrenci_id,
        metin_id=data.metin_id,
        ogretmen_id=current_user["id"],
        oturum_tipi=oturum_tipi,
    )
    d = oturum.dict()
    d["olusturma_tarihi"] = d["olusturma_tarihi"].isoformat()
    d["tamamlama_tarihi"] = None
    # Taslaktan devam edebilmek için metin bilgisini oturuma sakla
    d["metin_baslik"] = metin.get("baslik", "")
    d["metin_kelime_sayisi"] = metin.get("kelime_sayisi", 0)
    d["metin_icerik"] = metin.get("icerik", "")
    ogr = await db.students.find_one({"id": data.ogrenci_id})
    d["ogrenci_ad"] = f"{(ogr or {}).get('ad','')} {(ogr or {}).get('soyad','')}".strip()
    d["ogrenci_sinif"] = (ogr or {}).get("sinif", "")
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

@router.post("/diagnostic/sessions/{oturum_id}/taslak")
async def taslak_kaydet_oturum(oturum_id: str, data: dict, current_user=Depends(get_current_user)):
    """Yarım bırakılan analizi taslak olarak kaydeder (ilerleme/cevaplar). durum 'devam'
    kalır → RAPOR ÜRETMEZ. 'Devam et' ile kaldığı yerden sürer. Zaten tamamlanmışsa dokunmaz."""
    oturum = await db.diagnostic_oturumlar.find_one({"id": oturum_id})
    if not oturum:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    if oturum.get("durum") == "tamamlandi":
        raise HTTPException(status_code=400, detail="Tamamlanmış oturum taslak olarak kaydedilemez")
    await db.diagnostic_oturumlar.update_one(
        {"id": oturum_id},
        {"$set": {"taslak_veri": (data or {}).get("taslak_veri", data or {}),
                  "taslak_tarihi": datetime.utcnow().isoformat(), "durum": "devam"}})
    return {"ok": True, "durum": "devam"}


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

    # Hata dağılımı — tüm türleri dinamik say (18 kategorili tür; eski türler de dahil)
    hata_sayilari = {}
    for h in data.hatalar:
        tip = h.tip if hasattr(h, "tip") else h.get("tip", "")
        if tip:
            hata_sayilari[tip] = hata_sayilari.get(tip, 0) + 1

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
        "taslak_veri": None,  # tamamlanınca taslak temizlenir
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
# Anlama ve prozodik ölçütleri DİNAMİK: maddeler/ölçütler core.rapor_ayarlari
# panelinden gelir (eski sabit AnlamaVeri/ProzodikVeri modelleri kaldırıldı).
#   anlama:   {madde_id → "zayif"|"orta"|"iyi"}  (4.1-4.4 rubrik + 4.5 bloom, düz)
#   prozodik: {olcut_id → 1..4}
# Geriye dönük uyum: eski raporlarda anlama/prozodik zaten aynı id'li düz sözlük.
class RaporOlusturCreate(BaseModel):
    oturum_id: str
    anlama: Dict[str, str] = {}
    prozodik: Dict[str, int] = {}
    anlama_yuzde: Optional[int] = None   # verilmezse anlama'dan hesaplanır
    ogretmen_notu: str = ""

def anlama_yuzde_hesapla(anlama: dict) -> int:
    """Anlama sözlüğündeki zayif/orta/iyi değerlerinden ortalama yüzde (0-100)."""
    puan_map = {"zayif": 0, "orta": 1, "iyi": 2}
    degerler = [puan_map.get(v, 1) for v in (anlama or {}).values() if isinstance(v, str)]
    if not degerler:
        return 0
    return round(sum(degerler) / (len(degerler) * 2) * 100)

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

    prozodik_toplam = sum(int(v) for v in (data.prozodik or {}).values())
    anlama_pct = data.anlama_yuzde if data.anlama_yuzde else anlama_yuzde_hesapla(data.anlama)

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
        "anlama": data.anlama,
        "anlama_yuzde": anlama_pct,
        "prozodik": data.prozodik,
        "prozodik_toplam": prozodik_toplam,
        "ogretmen_notu": data.ogretmen_notu,
        "rapor_tipi": "olcum",   # olcum | gelisim
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.diagnostic_raporlar.insert_one(rapor_data)
    rapor_data.pop("_id", None)
    # Veliye bildirim gönder (metin adıyla; eski hatalı "baslik" anahtarı düzeltildi)
    try: await bildirim_rapor_tamamlandi(rapor_data.get("ogrenci_id"), rapor_data.get("metin_adi") or "Giriş Analizi Raporu")
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


# ── Gelişim Raporu (ön test / son test karşılaştırması) ──
class GelisimRaporCreate(BaseModel):
    ogrenci_id: str
    ilk_oturum_id: str
    son_oturum_id: str
    ders_sayisi: int = 12
    ogretmen_notu: str = ""


async def _oturum_olcum_raporu(oturum_id: str):
    """Bir oturumun ölçüm raporunu (en yeni) döner; yoksa None."""
    return await db.diagnostic_raporlar.find_one(
        {"oturum_id": oturum_id, "rapor_tipi": "olcum"}, sort=[("olusturma_tarihi", -1)])


def _degisim_duzeyi(metrik: str, degisim: float, esikler: dict) -> str:
    """Değişim referans tablosu: Anlamlı Gelişim / Sabit-Sınırlı / Gerileme."""
    e = esikler.get(metrik, {"anlamli": 0, "gerileme": 0})
    if degisim <= e.get("gerileme", 0):
        return "Gerileme"
    if degisim >= e.get("anlamli", 0) and degisim > 0:
        return "Anlamlı Gelişim"
    return "Sabit/Sınırlı Gelişim"


@router.post("/diagnostic/gelisim-raporu")
async def olustur_gelisim_raporu(data: GelisimRaporCreate,
                                 current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR, UserRole.TEACHER))):
    ilk_ot = await db.diagnostic_oturumlar.find_one({"id": data.ilk_oturum_id})
    son_ot = await db.diagnostic_oturumlar.find_one({"id": data.son_oturum_id})
    if not ilk_ot or not son_ot:
        raise HTTPException(status_code=404, detail="Oturum(lar) bulunamadı")
    ilk_rapor = await _oturum_olcum_raporu(data.ilk_oturum_id)
    son_rapor = await _oturum_olcum_raporu(data.son_oturum_id)
    if not ilk_rapor or not son_rapor:
        raise HTTPException(status_code=400,
                            detail="Her iki oturum için de önce Ölçüm Raporu oluşturulmalı")

    ogrenci = await db.students.find_one({"id": data.ogrenci_id})
    ogretmen = await db.users.find_one({"id": son_ot.get("ogretmen_id")})
    sinif = (ogrenci or {}).get("sinif", "")

    esikler = await get_rapor_ayari("gelisim_degisim_esikleri")

    def _sayi(r, k):
        try:
            return float(r.get(k, 0) or 0)
        except Exception:
            return 0.0

    # Metrikler: (anahtar, etiket, ön değer, son değer, "normlara göre düzey" fonksiyonu)
    metrik_tanim = [
        ("wpm", "Okuma Hızı (kelime/dk)", _sayi(ilk_rapor, "wpm"), _sayi(son_rapor, "wpm")),
        ("dogruluk", "Doğru Okuma Oranı (%)", _sayi(ilk_rapor, "dogruluk_yuzde"), _sayi(son_rapor, "dogruluk_yuzde")),
        ("prozodik", "Prozodik Okuma (20 puan)", _sayi(ilk_rapor, "prozodik_toplam"), _sayi(son_rapor, "prozodik_toplam")),
        ("anlama", "Okuduğunu Anlama (%)", _sayi(ilk_rapor, "anlama_yuzde"), _sayi(son_rapor, "anlama_yuzde")),
    ]

    ozet_tablo = []
    for anahtar, etiket, on, son in metrik_tanim:
        degisim = round(son - on, 1)
        # Normlara göre düzey (son test)
        if anahtar == "wpm":
            duzey = (await hiz_degerlendirme(sinif, son)).capitalize()
        elif anahtar == "dogruluk":
            duzey = await dogruluk_seviyesi(son)
        elif anahtar == "prozodik":
            duzey = prozodik_seviye(int(son)).capitalize()
        else:
            duzey = anlama_seviye(int(son)).capitalize()
        ozet_tablo.append({
            "metrik": anahtar, "etiket": etiket,
            "on_test": on, "son_test": son,
            "degisim": degisim, "sayisal_artis": degisim,
            "yon": "artis" if degisim > 0 else ("dusus" if degisim < 0 else "sabit"),
            "normlara_gore_duzey": duzey,
            "gelisim_duzeyi": _degisim_duzeyi(anahtar, degisim, esikler),
        })

    # Hata analizi gelişimi (ön/son)
    hata_analizi = {
        "on_test": _hata_sayilari_hesapla(ilk_ot.get("hatalar", [])),
        "son_test": _hata_sayilari_hesapla(son_ot.get("hatalar", [])),
    }

    rapor = {
        "id": str(uuid.uuid4()),
        "rapor_tipi": "gelisim",
        "ogrenci_id": data.ogrenci_id,
        "ogretmen_id": son_ot.get("ogretmen_id"),
        "ogrenci_ad": f"{(ogrenci or {}).get('ad','')} {(ogrenci or {}).get('soyad','')}".strip(),
        "ogrenci_sinif": sinif,
        "ogretmen_ad": f"{(ogretmen or {}).get('ad','')} {(ogretmen or {}).get('soyad','')}".strip(),
        "ders_sayisi": data.ders_sayisi,
        "ilk_oturum_id": data.ilk_oturum_id,
        "son_oturum_id": data.son_oturum_id,
        "ilk_rapor_id": ilk_rapor.get("id"),
        "son_rapor_id": son_rapor.get("id"),
        "ilk_metin_adi": ilk_rapor.get("metin_adi", ""),
        "son_metin_adi": son_rapor.get("metin_adi", ""),
        "ozet_tablo": ozet_tablo,
        "hata_analizi": hata_analizi,
        "ogretmen_notu": data.ogretmen_notu,
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.diagnostic_raporlar.insert_one(rapor)
    rapor.pop("_id", None)
    return rapor


# ── PDF Rapor Üretimi ──
def _tr_upper(text):
    """Türkçe büyük harf çevirimi (i→İ, ı→I)"""
    if not text:
        return text
    tr_map = str.maketrans("abcçdefgğhıijklmnoöprsştuüvyz", "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ")
    return text.translate(tr_map)

# Türkçe destekli PDF fontu — çok platformlu (Linux DejaVu, Windows Arial/Segoe,
# macOS Arial). Bulunamazsa Helvetica'ya düşer (latin-1; TR karakterlerde patlar).
_TR_FONT_ADAYLARI = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]
_tr_font_kayitli = False

def _tr_font():
    """Türkçe destekli fontu (bir kez) kaydeder; (FONT, FONTB) ad çiftini döner."""
    global _tr_font_kayitli
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if _tr_font_kayitli:
        return "TRFont", "TRFontBold"
    for reg, bold in _TR_FONT_ADAYLARI:
        if os.path.exists(reg) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("TRFont", reg))
            pdfmetrics.registerFont(TTFont("TRFontBold", bold))
            _tr_font_kayitli = True
            return "TRFont", "TRFontBold"
    return "Helvetica", "Helvetica-Bold"


def _gelisim_raporu_pdf(rapor: dict):
    """Gelişim (ön test/son test) raporu PDF'i — Word şablonundaki tabloları yansıtır."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph as RLPara, Spacer, Table as RLTable, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    FONT, FONTB = _tr_font()

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='GT', fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=4, textColor=colors.HexColor('#1F4E79'), fontName=FONTB))
    styles.add(ParagraphStyle(name='GS', fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=14, textColor=colors.HexColor('#666666'), fontName=FONT))
    styles.add(ParagraphStyle(name='GSect', fontSize=12, leading=16, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor('#1F4E79'), fontName=FONTB))
    styles.add(ParagraphStyle(name='GBody', fontSize=9, leading=13, spaceAfter=4, fontName=FONT))

    hdr_bg = colors.HexColor('#1F4E79')
    alt_bg = colors.HexColor('#F2F7FB')
    bdr = colors.HexColor('#CCCCCC')
    YESIL, GRI, KIRMIZI = colors.HexColor('#1E8449'), colors.HexColor('#7F8C8D'), colors.HexColor('#C0392B')
    duzey_renk = {"Anlamlı Gelişim": YESIL, "Sabit/Sınırlı Gelişim": GRI, "Gerileme": KIRMIZI}
    yon_ikon = {"artis": "▲", "dusus": "▼", "sabit": "■"}

    el = []
    el.append(RLPara("Okuma Becerileri Akademisi", styles['GT']))
    el.append(RLPara("Bireysel Gelişim Raporu", styles['GS']))

    # Öğrenci bilgileri
    el.append(RLPara("1. Öğrenci Bilgileri", styles['GSect']))
    info = [
        ["Adı Soyadı:", rapor.get("ogrenci_ad", "-"), "Sınıfı:", rapor.get("ogrenci_sinif", "-")],
        ["Eğitimci:", rapor.get("ogretmen_ad", "-"), "Tarih:", rapor.get("olusturma_tarihi", "")[:10]],
    ]
    t = RLTable(info, colWidths=[3*cm, 5*cm, 3*cm, 5*cm])
    t.setStyle(TableStyle([('FONTNAME', (0,0), (0,-1), FONTB), ('FONTNAME', (2,0), (2,-1), FONTB),
        ('FONTNAME', (1,0), (1,-1), FONT), ('FONTNAME', (3,0), (3,-1), FONT), ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), hdr_bg), ('TEXTCOLOR', (2,0), (2,-1), hdr_bg),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]))
    el.append(t)

    ders = rapor.get("ders_sayisi", 12)
    el.append(Spacer(1, 6))
    el.append(RLPara(f"<b>Raporun Amacı:</b> {ders} derslik yapılandırılmış okuma eğitimi süreci sonunda "
                     "öğrencinin okuma becerilerindeki gelişimin ön test/son test karşılaştırmasıyla değerlendirilmesidir.", styles['GBody']))

    # Metin tablosu (ön/son)
    el.append(RLPara("2. Ölçüm Metinleri", styles['GSect']))
    mt = [["", "Ön Test (İlk Ölçüm)", "Son Test (Kur Sonu)"],
          ["Metin", _tr_upper(rapor.get("ilk_metin_adi", "-")), _tr_upper(rapor.get("son_metin_adi", "-"))]]
    tm = RLTable(mt, colWidths=[3*cm, 6.5*cm, 6.5*cm])
    tm.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, bdr), ('FONTSIZE', (0,0), (-1,-1), 9),
        ('FONTNAME', (0,0), (-1,-1), FONT), ('BACKGROUND', (0,0), (-1,0), hdr_bg), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), FONTB), ('FONTNAME', (0,1), (0,-1), FONTB),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]))
    el.append(tm)

    # Bireysel Gelişim Özet Tablo
    el.append(RLPara("3. Bireysel Gelişim Özet Tablosu", styles['GSect']))
    head = ["Ölçüt", "Ön Test", "Son Test", "Değişim", "Normlara Göre", "Gelişim"]
    rows = [head]
    ozet = rapor.get("ozet_tablo", [])
    for m in ozet:
        deg = m.get("degisim", 0)
        ok = yon_ikon.get(m.get("yon", "sabit"), "■")
        isaret = "+" if deg > 0 else ""
        rows.append([
            m.get("etiket", m.get("metrik", "")),
            _fmt_sayi(m.get("on_test")), _fmt_sayi(m.get("son_test")),
            f"{ok} {isaret}{_fmt_sayi(deg)}",
            m.get("normlara_gore_duzey", "-"),
            m.get("gelisim_duzeyi", "-"),
        ])
    tw = [4.2*cm, 2*cm, 2*cm, 2.4*cm, 2.6*cm, 2.8*cm]
    tt = RLTable(rows, colWidths=tw)
    st = [('GRID', (0,0), (-1,-1), 0.5, bdr), ('FONTSIZE', (0,0), (-1,-1), 8.5), ('FONTNAME', (0,0), (-1,-1), FONT),
          ('BACKGROUND', (0,0), (-1,0), hdr_bg), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('FONTNAME', (0,0), (-1,0), FONTB),
          ('ALIGN', (1,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]
    for i, m in enumerate(ozet, start=1):
        renk = duzey_renk.get(m.get("gelisim_duzeyi"), GRI)
        st.append(('TEXTCOLOR', (5,i), (5,i), renk))
        st.append(('TEXTCOLOR', (3,i), (3,i), renk))
        if i % 2 == 0:
            st.append(('BACKGROUND', (0,i), (-1,i), alt_bg))
    tt.setStyle(TableStyle(st))
    el.append(tt)

    # Hata Analizi Gelişimi
    el.append(RLPara("4. Hata Analizi Gelişimi", styles['GSect']))
    ha = rapor.get("hata_analizi", {}) or {}
    def _hmap(lst):
        etk = {"atlama": "Atlama", "yanlis_okuma": "Yanlış Okuma", "takilma": "Takılma", "tekrar": "Tekrar"}
        d = {etk.get(x.get("tur"), x.get("tur")): x.get("sayi", 0) for x in (lst or [])}
        return d
    on_h, son_h = _hmap(ha.get("on_test")), _hmap(ha.get("son_test"))
    turler = ["Atlama", "Yanlış Okuma", "Takılma", "Tekrar"]
    hrows = [["Hata Türü", "Ön Test", "Son Test", "Değişim"]]
    for tr in turler:
        o, s = on_h.get(tr, 0), son_h.get(tr, 0)
        d = s - o
        hrows.append([tr, str(o), str(s), ("+" if d > 0 else "") + str(d)])
    th = RLTable(hrows, colWidths=[5*cm, 3.5*cm, 3.5*cm, 3*cm])
    th.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, bdr), ('FONTSIZE', (0,0), (-1,-1), 9), ('FONTNAME', (0,0), (-1,-1), FONT),
        ('BACKGROUND', (0,0), (-1,0), hdr_bg), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('FONTNAME', (0,0), (-1,0), FONTB),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]))
    el.append(th)

    # Değişim Referans Tablosu (lejant)
    el.append(RLPara("5. Değişim Referans Tablosu", styles['GSect']))
    ref = [["Gösterge", "Anlamı"],
           ["▲ Anlamlı Gelişim", "Belirlenen eşiğin üzerinde ilerleme"],
           ["■ Sabit / Sınırlı Gelişim", "Eşik altında, korunan düzey"],
           ["▼ Gerileme (nadir)", "Ölçülen düzeyde düşüş"]]
    tr_ = RLTable(ref, colWidths=[6*cm, 9*cm])
    tr_.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, bdr), ('FONTSIZE', (0,0), (-1,-1), 9), ('FONTNAME', (0,0), (-1,-1), FONT),
        ('BACKGROUND', (0,0), (-1,0), hdr_bg), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('FONTNAME', (0,0), (-1,0), FONTB),
        ('TEXTCOLOR', (0,1), (0,1), YESIL), ('TEXTCOLOR', (0,2), (0,2), GRI), ('TEXTCOLOR', (0,3), (0,3), KIRMIZI),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]))
    el.append(tr_)

    # Genel değerlendirme (öğretmen notu)
    if rapor.get("ogretmen_notu"):
        el.append(RLPara("6. Genel Gelişim Değerlendirmesi", styles['GSect']))
        el.append(RLPara(rapor.get("ogretmen_notu", ""), styles['GBody']))

    buffer = io.BytesIO()
    doc_pdf = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=2*cm, rightMargin=2*cm)
    doc_pdf.build(el)
    buffer.seek(0)
    ad = _ascii_dosya(rapor.get("ogrenci_ad", "ogrenci"))
    return StreamingResponse(buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Gelisim_Raporu_{ad}.pdf"'})


def _fmt_sayi(v):
    """Sayıyı gereksiz .0 olmadan yazar (100.0 → 100)."""
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else str(round(f, 1))
    except Exception:
        return str(v)


def _ascii_dosya(ad: str) -> str:
    """Dosya adını latin-1 HTTP başlığına güvenli ASCII'ye çevirir (Türkçe→ASCII)."""
    tr = str.maketrans("şğıİöüçŞĞÖÜÇ ", "sgiIoucSGOUC_")
    ad = (ad or "ogrenci").translate(tr)
    temiz = "".join(c for c in ad if c.isalnum() or c in "_-")
    return temiz or "ogrenci"


@router.get("/diagnostic/rapor/{rapor_id}/pdf")
async def get_rapor_pdf(rapor_id: str, current_user=Depends(get_current_user)):
    rapor = await db.diagnostic_raporlar.find_one({"id": rapor_id})
    if not rapor:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı")
    rapor.pop("_id", None)

    # Gelişim raporu → ayrı şablon
    if rapor.get("rapor_tipi") == "gelisim":
        return _gelisim_raporu_pdf(rapor)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph as RLPara, Spacer, Table as RLTable, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # ── Türkçe Font Kaydı (çok platformlu ortak yardımcı) ──
    FONT, FONTB = _tr_font()

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

    ogrenci_ad = _ascii_dosya(rapor.get("ogrenci_ad", "ogrenci"))
    tarih = rapor.get("olusturma_tarihi", "")[:10]
    filename = f"Rapor_{ogrenci_ad}_{tarih}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


