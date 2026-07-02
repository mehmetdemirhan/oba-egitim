"""Kitap + Soru Havuzu modülü (/kitaplar/*, /kitap-bilgi-cek).

server.py'dan BİREBİR taşındı; yollar ve davranış değişmedi. İki tarihsel
kitap bloğu (klasik `kitaplar` koleksiyonu + `kitap_havuzu` bölüm-bazlı sistem)
aynı dosyada tutulur. Kayıt sırası korunmuştur: ilk blok, çakışan yollarda
(POST/GET /kitaplar, admin-karar) önceliklidir — server.py'daki davranışla aynı.
"""
import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.db import db
from core.auth import get_current_user
from core.sistem import get_xp_tablosu

router = APIRouter()


# ── Kitap + Soru Havuzu ──
class KitapCreate(BaseModel):
    baslik: str
    yazar: str = ""
    yas_grubu: str = "8-10"
    zorluk: str = "orta"
    bolum_sayisi: int = 1

@router.post("/kitaplar")
async def kitap_ekle(data: KitapCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ("admin", "coordinator", "teacher"):
        raise HTTPException(status_code=403, detail="Yetki yok")
    durum = "oylama" if role in ("admin", "coordinator") else "beklemede"
    kitap = {
        "id": str(uuid.uuid4()),
        "baslik": data.baslik,
        "yazar": data.yazar,
        "yas_grubu": data.yas_grubu,
        "zorluk": data.zorluk,
        "bolum_sayisi": data.bolum_sayisi,
        "ekleyen_id": current_user["id"],
        "ekleyen_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip(),
        "durum": durum,
        "oylar": {},
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.kitaplar.insert_one(kitap)
    kitap.pop("_id", None)
    return kitap

@router.get("/kitaplar")
async def kitap_listele(current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    kitaplar = await db.kitaplar.find().sort("olusturma_tarihi", -1).to_list(length=None)
    for k in kitaplar:
        k.pop("_id", None)
    if role in ("admin", "coordinator"):
        return kitaplar
    # Öğretmen: kendi eklediği + oylamada + havuzda
    return [k for k in kitaplar if k.get("durum") in ("oylama", "havuzda") or k.get("ekleyen_id") == current_user["id"]]

@router.put("/kitaplar/{kitap_id}")
async def kitap_guncelle(kitap_id: str, data: dict, current_user=Depends(get_current_user)):
    kitap = await db.kitaplar.find_one({"id": kitap_id})
    if not kitap:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")
    update = {k: v for k, v in data.items() if k in ("baslik", "yazar", "yas_grubu", "zorluk", "bolum_sayisi")}
    if update:
        await db.kitaplar.update_one({"id": kitap_id}, {"$set": update})
    return {"message": "Güncellendi"}

@router.delete("/kitaplar/{kitap_id}")
async def kitap_sil(kitap_id: str, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ("admin", "coordinator"):
        raise HTTPException(status_code=403, detail="Yetki yok")
    await db.kitaplar.delete_one({"id": kitap_id})
    await db.sorular.delete_many({"kitap_id": kitap_id})
    return {"message": "Kitap ve soruları silindi"}

# Kitap admin karar (oylama başlat / direkt havuza al / reddet)
@router.post("/kitaplar/{kitap_id}/admin-karar")
async def kitap_admin_karar(kitap_id: str, data: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ("admin", "coordinator"):
        raise HTTPException(status_code=403, detail="Yetki yok")
    onay = data.get("onay", True)
    direkt = data.get("direkt", False)
    if not onay:
        await db.kitaplar.update_one({"id": kitap_id}, {"$set": {"durum": "reddedildi", "red_sebep": data.get("sebep", "")}})
        return {"message": "Reddedildi"}
    if direkt:
        await db.kitaplar.update_one({"id": kitap_id}, {"$set": {"durum": "havuzda"}})
        return {"message": "Direkt havuza alındı"}
    await db.kitaplar.update_one({"id": kitap_id}, {"$set": {"durum": "oylama"}})
    return {"message": "Oylama başlatıldı"}

# Kitap oylama
@router.post("/kitaplar/{kitap_id}/oy")
async def kitap_oy_ver(kitap_id: str, data: dict, current_user=Depends(get_current_user)):
    kitap = await db.kitaplar.find_one({"id": kitap_id})
    if not kitap or kitap.get("durum") != "oylama":
        raise HTTPException(status_code=400, detail="Bu kitap oylamada değil")
    user_id = current_user["id"]
    oylar = kitap.get("oylar", {})
    if user_id in oylar:
        raise HTTPException(status_code=400, detail="Zaten oy kullandınız")
    onay = data.get("onay", True)
    oylar[user_id] = {"onay": onay, "sebep": data.get("sebep", ""), "tarih": datetime.utcnow().isoformat()}
    update = {"oylar": oylar}
    # Oy eşiği kontrolü
    ayar = await db.ayarlar.find_one({"tip": "puan_ayarlari"})
    esik = ayar.get("oy_esik", 3) if ayar else 3
    onay_sayisi = sum(1 for o in oylar.values() if o.get("onay"))
    red_sayisi = sum(1 for o in oylar.values() if not o.get("onay"))
    if red_sayisi >= 1:
        update["durum"] = "reddedildi"
    elif onay_sayisi >= esik:
        update["durum"] = "havuzda"
    await db.kitaplar.update_one({"id": kitap_id}, {"$set": update})
    # Katkı puanı
    await db.users.update_one({"id": user_id}, {"$inc": {"puan": 3}})
    return {"message": "Oy kaydedildi"}


# ─────────────────────────────────────────────
# KİTAP + BÖLÜM BAZLI SORU HAVUZU (Master Bölüm 8)
# ─────────────────────────────────────────────

# KİTAP + BÖLÜM BAZLI SORU HAVUZU (Master Bölüm 8)
# ─────────────────────────────────────────────

# Kitap ekle
@router.post("/kitaplar")
async def create_kitap(payload: dict, current_user=Depends(get_current_user)):
    kitap = {
        "id": str(uuid.uuid4()),
        "baslik": payload.get("baslik", ""),
        "yazar": payload.get("yazar", ""),
        "yas_grubu": payload.get("yas_grubu", ""),
        "zorluk": payload.get("zorluk", "orta"),
        "bolum_sayisi": payload.get("bolum_sayisi", 1),
        "kapak_url": payload.get("kapak_url", ""),
        "ekleyen_id": current_user["id"],
        "ekleyen_ad": f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip(),
        "durum": "beklemede",  # beklemede → oylama → yayinda
        "oylar": {},
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.kitap_havuzu.insert_one(kitap)
    # Katkı puanı
    await db.users.update_one({"id": current_user["id"]}, {"$inc": {"puan": 4}})
    kitap.pop("_id", None)
    return kitap


# Kitapları listele
@router.get("/kitaplar")
async def get_kitaplar(current_user=Depends(get_current_user)):
    kitaplar = await db.kitap_havuzu.find().sort("olusturma_tarihi", -1).to_list(length=None)
    for k in kitaplar:
        k.pop("_id", None)
    return kitaplar


# Kitap admin kararı (onay/oylama/red)
@router.post("/kitaplar/{kitap_id}/admin-karar")
async def kitap_admin_karar(kitap_id: str, payload: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    onay = payload.get("onay", False)
    direkt = payload.get("direkt", False)
    if not onay:
        await db.kitap_havuzu.update_one({"id": kitap_id}, {"$set": {"durum": "reddedildi"}})
        return {"ok": True, "durum": "reddedildi"}
    if direkt:
        await db.kitap_havuzu.update_one({"id": kitap_id}, {"$set": {"durum": "yayinda"}})
        return {"ok": True, "durum": "yayinda"}
    await db.kitap_havuzu.update_one({"id": kitap_id}, {"$set": {"durum": "oylama"}})
    return {"ok": True, "durum": "oylama"}


# Kitap oylama
@router.post("/kitaplar/{kitap_id}/oyla")
async def kitap_oyla(kitap_id: str, payload: dict, current_user=Depends(get_current_user)):
    onay = payload.get("onay", True)
    sebep = payload.get("sebep", "")
    oy_data = {"onay": onay, "sebep": sebep, "tarih": datetime.utcnow().isoformat()}
    await db.kitap_havuzu.update_one({"id": kitap_id}, {"$set": {f"oylar.{current_user['id']}": oy_data}})
    # Katkı puanı
    await db.users.update_one({"id": current_user["id"]}, {"$inc": {"puan": 3}})
    # Otomatik yayına alma kontrolü
    kitap = await db.kitap_havuzu.find_one({"id": kitap_id})
    if kitap:
        oylar = kitap.get("oylar", {})
        toplam = len(oylar)
        onaylar = sum(1 for o in oylar.values() if o.get("onay"))
        redler = sum(1 for o in oylar.values() if not o.get("onay"))
        if toplam >= 3 and onaylar / toplam >= 0.6:
            await db.kitap_havuzu.update_one({"id": kitap_id}, {"$set": {"durum": "yayinda"}})
        if redler > 0:
            await db.kitap_havuzu.update_one({"id": kitap_id}, {"$set": {"durum": "askida"}})
    return {"ok": True}


# Bölüm bazlı soru ekle
@router.post("/kitaplar/{kitap_id}/sorular")
async def create_soru(kitap_id: str, payload: dict, current_user=Depends(get_current_user)):
    soru = {
        "id": str(uuid.uuid4()),
        "kitap_id": kitap_id,
        "bolum": payload.get("bolum", 1),
        "soru": payload.get("soru", ""),
        "secenekler": payload.get("secenekler", []),
        "dogru_cevap": payload.get("dogru_cevap", 0),
        "taksonomi": payload.get("taksonomi", "kavrama"),
        "ekleyen_id": current_user["id"],
        "ekleyen_ad": f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip(),
        "kullanim_sayisi": 0,
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.kitap_sorulari.insert_one(soru)
    soru.pop("_id", None)
    return soru


# Kitabın sorularını getir
@router.get("/kitaplar/{kitap_id}/sorular")
async def get_kitap_sorulari(kitap_id: str, bolum: int = None, current_user=Depends(get_current_user)):
    filtre = {"kitap_id": kitap_id}
    if bolum:
        filtre["bolum"] = bolum
    sorular = await db.kitap_sorulari.find(filtre).to_list(length=None)
    for s in sorular:
        s.pop("_id", None)
    return sorular


# Soru sil
@router.delete("/kitaplar/sorular/{soru_id}")
async def delete_soru(soru_id: str, current_user=Depends(get_current_user)):
    await db.kitap_sorulari.delete_one({"id": soru_id})
    return {"ok": True}


# Öğrenci için bölüm bazlı test çek (okuma sonrası)
@router.get("/kitaplar/test/{kitap_id}/{bolum}")
async def get_bolum_testi(kitap_id: str, bolum: int, current_user=Depends(get_current_user)):
    sorular = await db.kitap_sorulari.find({"kitap_id": kitap_id, "bolum": bolum}).to_list(length=None)
    for s in sorular:
        s.pop("_id", None)
        # Kullanım sayısını artır
        await db.kitap_sorulari.update_one({"id": s["id"]}, {"$inc": {"kullanim_sayisi": 1}})
    return sorular


# Bölüm testi tamamla (öğrenci cevapladığında)
@router.post("/kitaplar/test/tamamla")
async def bolum_testi_tamamla(payload: dict, current_user=Depends(get_current_user)):
    kitap_id = payload.get("kitap_id", "")
    bolum = payload.get("bolum", 1)
    cevaplar = payload.get("cevaplar", [])  # [{soru_id, secilen_cevap}]

    sorular = await db.kitap_sorulari.find({"kitap_id": kitap_id, "bolum": bolum}).to_list(length=None)
    soru_dict = {s["id"]: s for s in sorular}

    dogru = 0
    toplam = len(cevaplar)
    for c in cevaplar:
        soru = soru_dict.get(c.get("soru_id"))
        if soru and c.get("secilen_cevap") == soru.get("dogru_cevap"):
            dogru += 1

    yuzde = round((dogru / max(toplam, 1)) * 100)

    # Test sonucu kaydet
    sonuc = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": current_user.get("linked_id") or current_user["id"],
        "kitap_id": kitap_id,
        "bolum": bolum,
        "dogru": dogru,
        "toplam": toplam,
        "yuzde": yuzde,
        "cevaplar": cevaplar,
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.kitap_test_sonuclari.insert_one(sonuc)

    # XP kazan
    xp_tablosu = await get_xp_tablosu()
    xp = xp_tablosu.get("anlama_testi", 15)
    ogrenci_id = current_user.get("linked_id") or current_user["id"]
    await db.xp_logs.insert_one({"id": str(uuid.uuid4()), "ogrenci_id": ogrenci_id, "eylem": "anlama_testi", "xp": xp, "tarih": datetime.utcnow().isoformat()})
    await db.students.update_one({"id": ogrenci_id}, {"$inc": {"toplam_xp": xp}})

    sonuc.pop("_id", None)
    return {"sonuc": sonuc, "xp_kazanilan": xp}


# Yayındaki kitapları listele (öğrenci/öğretmen)
@router.get("/kitaplar/havuz")
async def get_kitap_havuzu(current_user=Depends(get_current_user)):
    kitaplar = await db.kitap_havuzu.find({"durum": "yayinda"}).to_list(length=None)
    sonuc = []
    for k in kitaplar:
        k.pop("_id", None)
        soru_sayisi = await db.kitap_sorulari.count_documents({"kitap_id": k["id"]})
        k["soru_sayisi"] = soru_sayisi
        sonuc.append(k)
    return sonuc


# ── Kitap Bilgi Çekme (ISBN / Link) ──
@router.post("/kitap-bilgi-cek")
async def kitap_bilgi_cek(data: dict, current_user=Depends(get_current_user)):
    import urllib.request, urllib.error, ssl, json, asyncio

    deger = data.get("deger", "").strip()
    tip = data.get("tip", "isbn")
    result = {"baslik": "", "yazar": "", "isbn": "", "yayinevi": "", "sayfa_sayisi": "", "aciklama": "", "kapak_url": "", "link": ""}

    def fetch_url(url):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                raw = resp.read()
                try:
                    return raw.decode("utf-8")
                except Exception:
                    return raw.decode("latin-1")
        except Exception:
            return None

    if tip == "isbn":
        isbn_temiz = re.sub(r"[^0-9X]", "", deger.upper())
        # Google Books API
        raw = await asyncio.to_thread(fetch_url, f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn_temiz}")
        if raw:
            try:
                j = json.loads(raw)
                if j.get("totalItems", 0) > 0:
                    vol = j["items"][0]["volumeInfo"]
                    result["baslik"] = vol.get("title", "")
                    result["yazar"] = ", ".join(vol.get("authors", []))
                    result["yayinevi"] = vol.get("publisher", "")
                    result["sayfa_sayisi"] = str(vol.get("pageCount", "") or "")
                    result["aciklama"] = (vol.get("description", "") or "")[:200]
                    result["isbn"] = isbn_temiz
                    imgs = vol.get("imageLinks", {})
                    result["kapak_url"] = imgs.get("thumbnail", imgs.get("smallThumbnail", ""))
                    result["link"] = vol.get("infoLink", "")
            except Exception:
                pass
        # Open Library fallback
        if not result["baslik"]:
            raw = await asyncio.to_thread(fetch_url, f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_temiz}&format=json&jscmd=data")
            if raw:
                try:
                    j = json.loads(raw)
                    key = f"ISBN:{isbn_temiz}"
                    if key in j:
                        book = j[key]
                        result["baslik"] = book.get("title", "")
                        result["yazar"] = ", ".join([a.get("name", "") for a in book.get("authors", [])])
                        result["yayinevi"] = ", ".join([p.get("name", "") for p in book.get("publishers", [])])
                        result["sayfa_sayisi"] = str(book.get("number_of_pages", "") or "")
                        result["isbn"] = isbn_temiz
                        cover = book.get("cover", {})
                        result["kapak_url"] = cover.get("medium", cover.get("small", ""))
                        result["link"] = book.get("url", "")
                except Exception:
                    pass

    elif tip == "link":
        html = await asyncio.to_thread(fetch_url, deger)
        if html:
            QP = """[\"']"""
            m = re.search(r'property\s*=\s*' + QP + r'og:title' + QP + r'[^>]*content\s*=\s*' + QP + r'([^"\']+)', html, re.I)
            if m:
                result["baslik"] = m.group(1).strip()
            else:
                m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
                if m:
                    t = m.group(1).strip()
                    for sep in [" - ", " | ", " :: "]:
                        if sep in t:
                            t = t.split(sep)[0].strip()
                            break
                    result["baslik"] = t
            m = re.search(r'property\s*=\s*' + QP + r'og:description' + QP + r'[^>]*content\s*=\s*' + QP + r'([^"\']+)', html, re.I)
            if m:
                result["aciklama"] = m.group(1).strip()[:200]
            m = re.search(r'property\s*=\s*' + QP + r'og:image' + QP + r'[^>]*content\s*=\s*' + QP + r'([^"\']+)', html, re.I)
            if m:
                result["kapak_url"] = m.group(1).strip()
            m = re.search(r'itemprop\s*=\s*' + QP + r'author' + QP + r'[^>]*>([^<]+)', html, re.I)
            if not m:
                m = re.search(r'Yazar\s*:?\s*</\w+>\s*<[^>]+>([^<]+)', html, re.I)
            if m:
                result["yazar"] = m.group(1).strip()
            m = re.search(r'itemprop\s*=\s*' + QP + r'publisher' + QP + r'[^>]*>([^<]+)', html, re.I)
            if not m:
                m = re.search(r'Yay.nevi\s*:?\s*</\w+>\s*<[^>]+>([^<]+)', html, re.I)
            if m:
                result["yayinevi"] = m.group(1).strip()
            m = re.search(r'(?:Sayfa|sayfa)\s*(?:Say.s.)?\s*:?\s*(\d+)', html)
            if m:
                result["sayfa_sayisi"] = m.group(1)
            m = re.search(r'ISBN[^:]*:\s*([\d\-]{10,})', html, re.I)
            if m:
                result["isbn"] = re.sub(r"[^0-9]", "", m.group(1))
            result["link"] = deger

    if not result["baslik"]:
        raise HTTPException(status_code=404, detail="Kitap bilgisi bulunamadi")
    return result
