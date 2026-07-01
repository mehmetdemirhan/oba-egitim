"""MEB kelime yönetim modülü.

Yönetici PDF/DOCX kelime listelerini yükler → sistem parse eder → yönetici onaylar
→ kelimeler `meb_kelimeleri` koleksiyonuna yazılır → arka planda AI ile anlam +
örnek cümle üretilir. Bu kelimeler kelime egzersizlerinde ÖNCELİKLE kullanılır
(bkz. core/kelime_secici.py).

NOT: Mevcut `meb_kelime_haritasi` (ai_bilgi_tabani kitap kelime çıkarımı) AYRI bir
koleksiyondur ve DOKUNULMAZ; bu modül yeni `meb_kelimeleri` koleksiyonunu kullanır.

Yollar (api_router prefix=/api):
  POST   /meb-kelime/yukle            (admin — parse önizleme, DB'ye yazmaz)
  POST   /meb-kelime/onayla           (admin — kaydet + arka plan AI)
  GET    /meb-kelime/liste            (admin/koordinatör/öğretmen — sayfalı)
  PUT    /meb-kelime/{id}             (admin/koordinatör/öğretmen — anlam/örnek düzelt)
  DELETE /meb-kelime/{id}             (admin — soft delete)
  POST   /meb-kelime/toplu-ai-yenile  (admin — boş/onaysız için AI tekrar)
  GET    /meb-kelime/istatistik       (admin — özet)
"""
import io
import re
import uuid
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form

from core.db import db
from core.auth import get_current_user, require_role, UserRole
from core.ai import call_claude

router = APIRouter()

MAX_DOSYA_BYTE = 5 * 1024 * 1024  # 5MB
AI_BATCH = 8              # AI'a tek seferde gönderilecek kelime sayısı
AI_BEKLEME_SN = 1.5      # batch'ler arası bekleme (kota koruması)
AI_MAX_DENEME = 3

_YAZMA = require_role(UserRole.ADMIN)
_OKUMA = require_role(UserRole.ADMIN, UserRole.COORDINATOR, UserRole.TEACHER)

# Aynı (sınıf) için eşzamanlı birden çok AI kuyruğu tetiklenmesin
_ai_aktif: set = set()

# Türkçe küçük harf
_TR_BUYUK = "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ"
_TR_KUCUK = "abcçdefgğhıijklmnoöprsştuüvyz"
_CEV = {b: k for b, k in zip(_TR_BUYUK, _TR_KUCUK)}


def _tr_kucuk(s: str) -> str:
    return "".join(_CEV.get(ch, ch.lower()) for ch in (s or ""))


def _temizle(doc: dict) -> dict:
    if doc:
        doc.pop("_id", None)
    return doc


# ─────────────────────────────────────────────────────────────
# Dosya parse
# ─────────────────────────────────────────────────────────────
def _metin_cikar(icerik: bytes, dosya_adi: str) -> str:
    ad = (dosya_adi or "").lower()
    if ad.endswith(".pdf"):
        import fitz
        metin = ""
        doc = fitz.open(stream=icerik, filetype="pdf")
        for page in doc:
            metin += page.get_text() + "\n"
        doc.close()
        return metin
    if ad.endswith(".docx"):
        from docx import Document as DocxDocument
        doc_obj = DocxDocument(io.BytesIO(icerik))
        parcalar = [p.text for p in doc_obj.paragraphs]
        # Tablolardaki hücreleri de al
        for tablo in getattr(doc_obj, "tables", []):
            for satir in tablo.rows:
                for hucre in satir.cells:
                    parcalar.append(hucre.text)
        return "\n".join(parcalar)
    raise HTTPException(status_code=400, detail="Yalnızca PDF veya DOCX yükleyebilirsiniz.")


def _kelimeleri_ayir(metin: str) -> list[str]:
    """Metinden Türkçe kelimeleri çıkarır: temizle, küçük harf, tekilleştir.

    Sayı, noktalama ve tek harfli parçalar atılır. Sıra korunur.
    """
    kucuk = _tr_kucuk(metin or "")
    ham = re.findall(r"[a-zçğıöşü]+", kucuk)
    gorulen: set[str] = set()
    out: list[str] = []
    for k in ham:
        if len(k) < 2 or len(k) > 20:
            continue
        if k in gorulen:
            continue
        gorulen.add(k)
        out.append(k)
    return out


def _zorluk(kelime: str, sinif: int) -> str:
    u = len(kelime)
    if u <= 4 and sinif <= 4:
        return "kolay"
    if u >= 8 or sinif >= 7:
        return "zor"
    return "orta"


# ─────────────────────────────────────────────────────────────
# AI üretimi (arka plan)
# ─────────────────────────────────────────────────────────────
def _ai_prompt(kelimeler: list[str], sinif: int) -> tuple[str, str]:
    system = (
        "Sen ilkokul/ortaokul Türkçe öğretmeni asistanısın. Çocuk dostu, TDK uyumlu, "
        "kısa ve net tanımlar üretirsin."
    )
    liste = ", ".join(kelimeler)
    user = (
        f"Aşağıdaki kelimeler {sinif}. sınıf öğrencisi içindir: {liste}\n"
        "Her kelime için: (1) çocuk dostu Türkçe anlam (en fazla 15 kelime), "
        "(2) o sınıf seviyesine uygun kısa bir örnek cümle, (3) 1-2 kısa etiket "
        "(ör. 'duygu', 'günlük hayat', 'doğa').\n"
        'SADECE şu JSON ile yanıt ver: {"sonuclar": [{"kelime": "...", "anlam": "...", '
        '"ornek_cumle": "...", "etiketler": ["..."]}]}\n'
        "Markdown veya kod bloğu ekleme."
    )
    return system, user


async def _ai_batch_uret(kelimeler: list[str], sinif: int) -> dict:
    """Bir batch için {kelime: {anlam, ornek_cumle, etiketler}} döndürür."""
    system, user = _ai_prompt(kelimeler, sinif)
    for deneme in range(AI_MAX_DENEME):
        try:
            res = await call_claude(system, user, max_tokens=2000)
            parsed = res.get("parsed")
            if isinstance(parsed, dict) and isinstance(parsed.get("sonuclar"), list):
                harita = {}
                for s in parsed["sonuclar"]:
                    k = _tr_kucuk(str(s.get("kelime", "")).strip())
                    if k:
                        harita[k] = {
                            "anlam": str(s.get("anlam", "")).strip(),
                            "ornek_cumle": str(s.get("ornek_cumle", "")).strip(),
                            "etiketler": [str(e).strip() for e in (s.get("etiketler") or []) if str(e).strip()][:3],
                        }
                if harita:
                    return harita
        except Exception as ex:
            logging.warning(f"[meb_kelime] AI batch hatası (deneme {deneme}): {ex}")
        await asyncio.sleep(AI_BEKLEME_SN)
    return {}


async def _ai_kuyrugu_isle(sinif: int):
    """Anlamı boş veya durum=onaysiz olan kelimeler için AI üretir (arka plan)."""
    anahtar = int(sinif)
    if anahtar in _ai_aktif:
        return
    _ai_aktif.add(anahtar)
    try:
        while True:
            bekleyen = await db.meb_kelimeleri.find({
                "sinif": int(sinif),
                "durum": {"$ne": "arsivli"},
                "$or": [{"anlam": {"$in": [None, ""]}}, {"durum": "onaysiz"}],
            }).limit(AI_BATCH).to_list(length=AI_BATCH)
            if not bekleyen:
                break
            kelimeler = [b["kelime"] for b in bekleyen]
            harita = await _ai_batch_uret(kelimeler, sinif)
            for b in bekleyen:
                k = b["kelime"]
                veri = harita.get(k)
                if veri and veri.get("anlam"):
                    await db.meb_kelimeleri.update_one({"id": b["id"]}, {"$set": {
                        "anlam": veri["anlam"],
                        "ornek_cumle": veri.get("ornek_cumle", ""),
                        "etiketler": veri.get("etiketler", []),
                        "durum": "aktif",
                        "ai_uretim_tarihi": datetime.utcnow().isoformat(),
                    }})
                else:
                    # Üretilemedi → onaysiz bırak (sonra toplu-ai-yenile ile denenir)
                    await db.meb_kelimeleri.update_one({"id": b["id"]}, {"$set": {"durum": "onaysiz"}})
            await asyncio.sleep(AI_BEKLEME_SN)
    except Exception as ex:
        logging.warning(f"[meb_kelime] AI kuyruk hatası (s{sinif}): {ex}")
    finally:
        _ai_aktif.discard(anahtar)


# ─────────────────────────────────────────────────────────────
# Endpoint'ler
# ─────────────────────────────────────────────────────────────
@router.post("/meb-kelime/yukle")
async def meb_kelime_yukle(dosya: UploadFile = File(...), sinif: int = Form(...),
                           current_user=Depends(_YAZMA)):
    """PDF/DOCX'i parse eder, kelime önizlemesi döner (DB'ye YAZMAZ)."""
    icerik = await dosya.read()
    if len(icerik) > MAX_DOSYA_BYTE:
        raise HTTPException(status_code=400, detail="Dosya en fazla 5MB olabilir.")
    metin = _metin_cikar(icerik, dosya.filename or "")
    kelimeler = _kelimeleri_ayir(metin)
    return {
        "onizleme": kelimeler,
        "toplam": len(kelimeler),
        "dosya_adi": dosya.filename or "",
        "sinif": int(sinif),
    }


@router.post("/meb-kelime/onayla")
async def meb_kelime_onayla(data: dict, current_user=Depends(_YAZMA)):
    """Önizlenen kelimeleri kaydeder ve arka planda AI üretimini başlatır."""
    kelimeler = data.get("kelimeler") or []
    sinif = int(data.get("sinif", 1))
    kaynak = data.get("kaynak_dosya", "")
    if not isinstance(kelimeler, list) or not kelimeler:
        raise HTTPException(status_code=400, detail="Kelime listesi boş.")

    ad = f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip() or "Yönetici"
    now = datetime.utcnow().isoformat()
    yeni, atlanan = 0, 0
    for ham in kelimeler:
        k = _tr_kucuk(str(ham).strip())
        if len(k) < 2:
            continue
        mevcut = await db.meb_kelimeleri.find_one({"kelime": k, "sinif": sinif})
        if mevcut:
            atlanan += 1
            continue
        await db.meb_kelimeleri.insert_one({
            "id": str(uuid.uuid4()),
            "kelime": k,
            "sinif": sinif,
            "kaynak_dosya": kaynak,
            "anlam": "",
            "ornek_cumle": "",
            "zorluk": _zorluk(k, sinif),
            "durum": "aktif",
            "onaylandi": True,
            "etiketler": [],
            "ai_uretim_tarihi": None,
            "yukleme_tarihi": now,
            "yukleyen_id": current_user.get("id"),
            "yukleyen_ad": ad,
            "kullanim_sayisi": 0,
        })
        yeni += 1

    # Arka planda AI üretimi (kullanıcıyı bekletmez)
    if yeni > 0:
        asyncio.create_task(_ai_kuyrugu_isle(sinif))

    return {"yeni_eklenen": yeni, "mevcut_atlanan": atlanan, "ai_kuyrukta": yeni}


@router.get("/meb-kelime/liste")
async def meb_kelime_liste(
    sinif: int | None = Query(None),
    durum: str = Query("aktif"),
    kelime: str | None = Query(None),
    sayfa: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(_OKUMA),
):
    sorgu: dict = {}
    if sinif is not None:
        sorgu["sinif"] = int(sinif)
    if durum and durum != "hepsi":
        sorgu["durum"] = durum
    if kelime:
        sorgu["kelime"] = {"$regex": _tr_kucuk(kelime.strip()), "$options": "i"}

    toplam = await db.meb_kelimeleri.count_documents(sorgu)
    atla = (sayfa - 1) * limit
    docs = await db.meb_kelimeleri.find(sorgu).sort([("sinif", 1), ("kelime", 1)]).skip(atla).limit(limit).to_list(length=limit)
    return {
        "kelimeler": [_temizle(d) for d in docs],
        "toplam": toplam,
        "sayfa": sayfa,
        "limit": limit,
        "sayfa_sayisi": max(1, -(-toplam // limit)),
    }


@router.put("/meb-kelime/{kelime_id}")
async def meb_kelime_guncelle(kelime_id: str, data: dict, current_user=Depends(_OKUMA)):
    """Anlam/örnek/etiket/zorluk elle düzeltme (AI çıktısı hatalıysa)."""
    izinli = {}
    for alan in ("anlam", "ornek_cumle", "zorluk"):
        if alan in data:
            izinli[alan] = str(data[alan]).strip()
    if "etiketler" in data and isinstance(data["etiketler"], list):
        izinli["etiketler"] = [str(e).strip() for e in data["etiketler"] if str(e).strip()][:5]
    if izinli.get("anlam"):
        izinli["durum"] = "aktif"  # elle anlam girildiyse aktif say
    if not izinli:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok.")
    res = await db.meb_kelimeleri.update_one({"id": kelime_id}, {"$set": izinli})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Kelime bulunamadı.")
    return {"id": kelime_id, **izinli}


@router.delete("/meb-kelime/{kelime_id}")
async def meb_kelime_sil(kelime_id: str, current_user=Depends(_YAZMA)):
    """Soft delete (durum=arsivli)."""
    res = await db.meb_kelimeleri.update_one({"id": kelime_id}, {"$set": {"durum": "arsivli"}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Kelime bulunamadı.")
    return {"id": kelime_id, "durum": "arsivli"}


@router.post("/meb-kelime/toplu-ai-yenile")
async def meb_kelime_toplu_ai(data: dict = None, current_user=Depends(_YAZMA)):
    """Anlamı boş veya onaysız kelimeler için AI'ı tekrar dener (arka plan)."""
    data = data or {}
    siniflar = []
    if data.get("sinif") is not None:
        siniflar = [int(data["sinif"])]
    else:
        siniflar = await db.meb_kelimeleri.distinct("sinif")
    baslatilan = 0
    for s in siniflar:
        bekleyen = await db.meb_kelimeleri.count_documents({
            "sinif": int(s), "durum": {"$ne": "arsivli"},
            "$or": [{"anlam": {"$in": [None, ""]}}, {"durum": "onaysiz"}],
        })
        if bekleyen > 0:
            asyncio.create_task(_ai_kuyrugu_isle(int(s)))
            baslatilan += 1
    return {"kuyruk_baslatilan_sinif": baslatilan}


@router.get("/meb-kelime/istatistik")
async def meb_kelime_istatistik(sinif: int | None = Query(None), current_user=Depends(_YAZMA)):
    taban: dict = {"durum": {"$ne": "arsivli"}}
    if sinif is not None:
        taban["sinif"] = int(sinif)
    toplam = await db.meb_kelimeleri.count_documents(taban)
    ai_tamam = await db.meb_kelimeleri.count_documents({**taban, "anlam": {"$nin": [None, ""]}})
    ai_bekleyen = toplam - ai_tamam

    en_cok = await db.meb_kelimeleri.find(taban).sort("kullanim_sayisi", -1).limit(10).to_list(length=10)
    hic = await db.meb_kelimeleri.find({**taban, "kullanim_sayisi": 0}).limit(20).to_list(length=20)
    return {
        "toplam_kelime": toplam,
        "ai_uretimi_tamamlanan": ai_tamam,
        "ai_bekleyen": ai_bekleyen,
        "en_cok_kullanilan": [{"kelime": d.get("kelime"), "kullanim": d.get("kullanim_sayisi", 0)} for d in en_cok],
        "hic_kullanilmayan": [d.get("kelime") for d in hic],
    }
