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
AI_BATCH = 20             # AI'a TEK promptta gönderilecek BENZERSİZ kelime sayısı
AI_BEKLEME_SN = 2.0      # batch'ler arası bekleme (büyük prompt → kota güvenlik payı)
AI_MAX_DENEME = 3
AI_BATCH_SANIYE = 5      # ilerleme tahmini: batch başına ~saniye (çağrı + bekleme)

_YAZMA = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
_OKUMA = require_role(UserRole.ADMIN, UserRole.COORDINATOR, UserRole.TEACHER)

# Aynı (sınıf, ders) için eşzamanlı birden çok AI kuyruğu tetiklenmesin
_ai_aktif: set = set()

# ── Ders sabitleri (5 ders) ──
DERSLER = {
    "turkce": {"ad": "Türkçe", "siniflar": [1, 2, 3, 4, 5, 6, 7, 8], "emoji": "📖"},
    "hayat_bilgisi": {"ad": "Hayat Bilgisi", "siniflar": [1, 2, 3], "emoji": "🌱"},
    "sosyal_bilgiler": {"ad": "Sosyal Bilgiler", "siniflar": [4, 5, 6, 7], "emoji": "🌍"},
    "din_kulturu": {"ad": "Din Kültürü ve Ahlak Bilgisi", "siniflar": [4, 5, 6, 7, 8], "emoji": "☪️"},
    "inkilap_tarihi": {"ad": "T.C. İnkılap Tarihi ve Atatürkçülük", "siniflar": [8], "emoji": "🇹🇷"},
}
VARSAYILAN_DERS = "turkce"


def _ders_gecerli(ders: str) -> bool:
    return ders in DERSLER


def _sinif_derste(ders: str, sinif: int) -> bool:
    return int(sinif) in DERSLER.get(ders, {}).get("siniflar", [])

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
def _ai_prompt(items: list[dict]) -> tuple[str, str]:
    """items: [{"kelime","sinif","ders_ad"}] → TEK promptta çoklu kelime."""
    system = (
        "Sen ilkokul/ortaokul öğretmeni asistanısın. Çocuk dostu, TDK uyumlu, "
        "kısa ve net tanımlar üretirsin."
    )
    satirlar = "\n".join(
        f'- {it["kelime"]} ({it.get("sinif", 1)}. sınıf, {it.get("ders_ad", "Türkçe")})'
        for it in items
    )
    user = (
        "Aşağıdaki her kelime için: (1) çocuk dostu Türkçe anlam (en fazla 15 kelime), "
        "(2) sınıf seviyesine uygun kısa örnek cümle, (3) 1-2 kısa etiket üret.\n"
        f"Kelimeler (sınıf/ders bağlamıyla):\n{satirlar}\n"
        'SADECE şu JSON DİZİSİNİ döndür: '
        '[{"kelime":"...","anlam":"...","ornek_cumle":"...","etiketler":["..."]}]\n'
        "Markdown, kod bloğu veya ek açıklama EKLEME."
    )
    return system, user


async def _ai_batch_uret(items: list[dict]) -> dict:
    """Bir batch (benzersiz kelimeler) için {kelime: {anlam, ornek_cumle, etiketler}}.

    Yanıt hem düz dizi `[...]` hem `{"sonuclar":[...]}` biçimini kabul eder. Tek
    kelimenin parse hatası batch'i düşürmez (yalnızca o kelime haritada olmaz)."""
    system, user = _ai_prompt(items)
    for deneme in range(AI_MAX_DENEME):
        try:
            res = await call_claude(system, user, max_tokens=3500)
            parsed = res.get("parsed")
            sonuc_list = None
            if isinstance(parsed, list):
                sonuc_list = parsed
            elif isinstance(parsed, dict):
                sonuc_list = parsed.get("sonuclar") or parsed.get("kelimeler")
            if isinstance(sonuc_list, list) and sonuc_list:
                harita = {}
                for s in sonuc_list:
                    if not isinstance(s, dict):
                        continue
                    k = _tr_kucuk(str(s.get("kelime", "")).strip())
                    anlam = str(s.get("anlam", "")).strip()
                    if k and anlam:
                        harita[k] = {
                            "anlam": anlam,
                            "ornek_cumle": str(s.get("ornek_cumle", "")).strip(),
                            "etiketler": [str(e).strip() for e in (s.get("etiketler") or []) if str(e).strip()][:3],
                        }
                if harita:
                    return harita
        except Exception as ex:
            logging.warning(f"[meb_kelime] AI batch hatası (deneme {deneme}): {ex}")
        await asyncio.sleep(AI_BEKLEME_SN)
    return {}


def _bekleyen_sorgu(sinif=None, ders=None) -> dict:
    sorgu: dict = {
        "durum": {"$ne": "arsivli"},
        "$or": [{"anlam": {"$in": [None, ""]}}, {"durum": "onaysiz"}],
    }
    if sinif is not None:
        sorgu["sinif"] = int(sinif)
    if ders:
        sorgu["ders"] = ders
    return sorgu


async def _ai_kuyrugu_isle(sinif=None, ders=None):
    """Anlamı boş/onaysiz kelimeler için AI üretir (arka plan).

    DEDUPE: aynı `kelime` string'i birden fazla (sinif, ders) kombinasyonunda
    bekliyorsa TEK AI isteğiyle üretilir; sonuç o kelimenin bekleyen TÜM
    dokümanlarına yazılır (unique (kelime,sinif,ders) kırılmaz). Her turda en çok
    AI_BATCH (20) BENZERSİZ kelime tek promptta gönderilir. Tam başarısızlıkta
    (kota) döngü durur; kaldığı yerden sonraki tetiklemede devam eder — üretilmiş
    kelimeler tekrar sorulmaz. Kısmi eksik kelimeler "bekliyor" kalır.
    """
    anahtar = (sinif, ders)
    if anahtar in _ai_aktif:
        return
    _ai_aktif.add(anahtar)
    denenen: set = set()  # bu turda AI'a gönderilmiş kelimeler (tekrar denenmesin)
    try:
        while True:
            bekleyen = await db.meb_kelimeleri.find(_bekleyen_sorgu(sinif, ders)).limit(400).to_list(length=400)
            gruplar: dict = {}
            for b in bekleyen:
                k = b.get("kelime")
                if not k or k in denenen:
                    continue
                gruplar.setdefault(k, []).append(b)
            if not gruplar:
                break
            secilen = list(gruplar.keys())[:AI_BATCH]
            items = [{
                "kelime": k,
                "sinif": gruplar[k][0].get("sinif", 1),
                "ders_ad": DERSLER.get(gruplar[k][0].get("ders", VARSAYILAN_DERS), {}).get("ad", "Türkçe"),
            } for k in secilen]

            harita = await _ai_batch_uret(items)
            if not harita:
                # Tam başarısızlık (kota/servis) → dur; kaldığı yerden sonra devam edilir
                break

            now = datetime.utcnow().isoformat()
            for k in secilen:
                denenen.add(k)
                veri = harita.get(k)
                if not (veri and veri.get("anlam")):
                    continue  # bu kelime "bekliyor" kalır (denenen'de → bu tur tekrar denenmez)
                # DEDUPE yazımı: kelimenin bekleyen TÜM dokümanlarına aynı anlam/örnek
                await db.meb_kelimeleri.update_many(
                    {"kelime": k, **_bekleyen_sorgu(sinif, ders)},
                    {"$set": {
                        "anlam": veri["anlam"],
                        "ornek_cumle": veri.get("ornek_cumle", ""),
                        "etiketler": veri.get("etiketler", []),
                        "durum": "aktif",
                        "ai_uretim_tarihi": now,
                    }},
                )
            await asyncio.sleep(AI_BEKLEME_SN)
    except Exception as ex:
        logging.warning(f"[meb_kelime] AI kuyruk hatası (s{sinif}/{ders}): {ex}")
    finally:
        _ai_aktif.discard(anahtar)


# ─────────────────────────────────────────────────────────────
# Endpoint'ler
# ─────────────────────────────────────────────────────────────
@router.get("/meb-kelime/dersler")
async def meb_kelime_dersler(current_user=Depends(get_current_user)):
    """Desteklenen 5 dersi döndürür (frontend dropdown/kart için)."""
    return {"dersler": DERSLER}


@router.post("/meb-kelime/yukle")
async def meb_kelime_yukle(dosya: UploadFile = File(...), sinif: int = Form(...),
                           ders: str = Form(VARSAYILAN_DERS),
                           current_user=Depends(_YAZMA)):
    """PDF/DOCX'i parse eder, kelime önizlemesi döner (DB'ye YAZMAZ)."""
    if not _ders_gecerli(ders):
        raise HTTPException(status_code=400, detail="Geçersiz ders.")
    if not _sinif_derste(ders, sinif):
        raise HTTPException(status_code=400, detail="Bu ders bu sınıfta öğretilmiyor.")
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
        "ders": ders,
    }


@router.post("/meb-kelime/onayla")
async def meb_kelime_onayla(data: dict, current_user=Depends(_YAZMA)):
    """Önizlenen kelimeleri kaydeder ve arka planda AI üretimini başlatır."""
    kelimeler = data.get("kelimeler") or []
    sinif = int(data.get("sinif", 1))
    ders = data.get("ders", VARSAYILAN_DERS)
    kaynak = data.get("kaynak_dosya", "")
    if not isinstance(kelimeler, list) or not kelimeler:
        raise HTTPException(status_code=400, detail="Kelime listesi boş.")
    if not _ders_gecerli(ders):
        raise HTTPException(status_code=400, detail="Geçersiz ders.")
    if not _sinif_derste(ders, sinif):
        raise HTTPException(status_code=400, detail="Bu ders bu sınıfta öğretilmiyor.")

    ad = f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip() or "Yönetici"
    now = datetime.utcnow().isoformat()
    yeni, atlanan = 0, 0
    for ham in kelimeler:
        k = _tr_kucuk(str(ham).strip())
        if len(k) < 2:
            continue
        mevcut = await db.meb_kelimeleri.find_one({"kelime": k, "sinif": sinif, "ders": ders})
        if mevcut:
            atlanan += 1
            continue
        await db.meb_kelimeleri.insert_one({
            "id": str(uuid.uuid4()),
            "kelime": k,
            "sinif": sinif,
            "ders": ders,
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
        asyncio.create_task(_ai_kuyrugu_isle(sinif, ders))

    return {"yeni_eklenen": yeni, "mevcut_atlanan": atlanan, "ai_kuyrukta": yeni}


@router.get("/meb-kelime/liste")
async def meb_kelime_liste(
    sinif: int | None = Query(None),
    ders: str | None = Query(None),
    durum: str = Query("aktif"),
    kelime: str | None = Query(None),
    sayfa: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(_OKUMA),
):
    sorgu: dict = {}
    if sinif is not None:
        sorgu["sinif"] = int(sinif)
    if ders:
        sorgu["ders"] = ders
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
    """Anlamı boş veya onaysız kelimeler için AI'ı tekrar dener (arka plan).

    Bekleyen kelimeler (sınıf, ders) çiftlerine göre gruplanır; her çift için
    ayrı kuyruk tetiklenir. Opsiyonel `sinif`/`ders` ile daraltılabilir.
    """
    data = data or {}
    sinif = int(data["sinif"]) if data.get("sinif") is not None else None
    ders = data.get("ders") or None

    bekleyenler = await db.meb_kelimeleri.find(_bekleyen_sorgu(sinif, ders), {"kelime": 1}).to_list(length=None)
    bekleyen_kelime = len(bekleyenler)
    benzersiz = len({b.get("kelime") for b in bekleyenler if b.get("kelime")})
    # DEDUPE sonrası gerçek AI çağrı (batch) sayısı benzersiz kelimeye göre hesaplanır
    toplam_batch = max(0, -(-benzersiz // AI_BATCH))  # ceil
    tahmini_kalan_sure_sn = toplam_batch * AI_BATCH_SANIYE

    if bekleyen_kelime:
        # TEK görev: dedupe (sinif) ve varsa (ders) genelinde çalışır
        asyncio.create_task(_ai_kuyrugu_isle(sinif, ders))

    return {
        "kuyruk_baslatildi": bool(bekleyen_kelime),
        "bekleyen_kelime": bekleyen_kelime,
        "benzersiz_kelime": benzersiz,
        "toplam_batch": toplam_batch,
        "tamamlanan_batch": 0,
        "tahmini_kalan_sure_sn": tahmini_kalan_sure_sn,
    }


@router.get("/meb-kelime/istatistik")
async def meb_kelime_istatistik(sinif: int | None = Query(None),
                                ders: str | None = Query(None),
                                current_user=Depends(_YAZMA)):
    taban: dict = {"durum": {"$ne": "arsivli"}}
    if sinif is not None:
        taban["sinif"] = int(sinif)
    if ders:
        taban["ders"] = ders
    toplam = await db.meb_kelimeleri.count_documents(taban)
    ai_tamam = await db.meb_kelimeleri.count_documents({**taban, "anlam": {"$nin": [None, ""]}})
    ai_bekleyen = toplam - ai_tamam

    en_cok = await db.meb_kelimeleri.find(taban).sort("kullanim_sayisi", -1).limit(10).to_list(length=10)
    hic = await db.meb_kelimeleri.find({**taban, "kullanim_sayisi": 0}).limit(20).to_list(length=20)

    # Ders bazlı ve ders×sınıf dağılımı (arşivli hariç, tüm dersler)
    ders_bazli: dict = {}
    ders_x_sinif: dict = {}
    for dk in DERSLER:
        d_taban = {"durum": {"$ne": "arsivli"}, "ders": dk}
        d_toplam = await db.meb_kelimeleri.count_documents(d_taban)
        d_hazir = await db.meb_kelimeleri.count_documents({**d_taban, "anlam": {"$nin": [None, ""]}})
        ders_bazli[dk] = {"toplam": d_toplam, "ai_hazir": d_hazir, "ai_bekleyen": d_toplam - d_hazir}
        for s in DERSLER[dk]["siniflar"]:
            ders_x_sinif[f"{dk}_{s}"] = await db.meb_kelimeleri.count_documents(
                {"durum": {"$ne": "arsivli"}, "ders": dk, "sinif": s})

    return {
        "toplam_kelime": toplam,
        "ai_uretimi_tamamlanan": ai_tamam,
        "ai_bekleyen": ai_bekleyen,
        "ders_bazli": ders_bazli,
        "ders_x_sinif": ders_x_sinif,
        "en_cok_kullanilan": [{"kelime": d.get("kelime"), "kullanim": d.get("kullanim_sayisi", 0)} for d in en_cok],
        "hic_kullanilmayan": [d.get("kelime") for d in hic],
    }
