"""Instagram beslemesi modülü (@dogadakiogretmenim).

Instagram postları 3. parti RSS köprüsü (RSSHub vb.) ile RSS olarak çekilir,
`instagram_paylasimlari` koleksiyonuna kaydedilir. Öğretmen OBA içinde beğen/
kaydet/yorum yapıp XP kazanır; "Instagram'da da yaptım" onay kutuları bonus XP verir.

XP (her eylem BİR KEZ; toggle kapatınca XP geri alınmaz):
  beğen +3, kaydet +7, yorum +10, onur_ig_begen +5, onur_ig_kaydet +8  (post başı maks 33)

RSS ayrıştırma: feedparser varsa onunla, yoksa stdlib (xml.etree) ile. Ağ hatasına
karşı graceful fallback + 30 dk cache.

Öğretmen XP'si mevcut desenle `users.puan` alanına işlenir (puan tablosu bunu okur).
"""
import re
import uuid
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from core.db import db
from core.auth import get_current_user, require_role, UserRole

router = APIRouter()

INSTAGRAM_HESABI = "dogadakiogretmenim"
# Denenecek RSS köprüleri (sırayla; biri çalışırsa yeter)
RSS_URLLERI = [
    f"https://rsshub.app/instagram/user/{INSTAGRAM_HESABI}",
    f"https://rss.app/feeds/instagram/{INSTAGRAM_HESABI}.xml",
]
CACHE_DK = 30
AYAR_ID = "global"

XP_KURALLARI = {
    "begen": 3, "kaydet": 7, "yorum": 10,
    "onur_ig_begen": 5, "onur_ig_kaydet": 8,
}
POST_MAKS_XP = sum(XP_KURALLARI.values())  # 33
ETKILESIM_EYLEMLERI = {"begen", "kaydet", "onur_ig_begen", "onur_ig_kaydet"}

_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Basit feed cache (ham xml) — 30 dk
_feed_cache = {"t": None, "xml": None}


# ─────────────────────────────────────────────────────────────
# RSS çekme + ayrıştırma
# ─────────────────────────────────────────────────────────────
async def _rss_ham_getir() -> str | None:
    """RSS köprülerinden ham XML'i getirir (30 dk cache, çoklu URL denemesi)."""
    now = datetime.utcnow()
    if _feed_cache["xml"] and _feed_cache["t"] and (now - _feed_cache["t"]) < timedelta(minutes=CACHE_DK):
        return _feed_cache["xml"]
    for url in RSS_URLLERI:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as ac:
                r = await ac.get(url, headers={"User-Agent": "Mozilla/5.0 OBA"})
                if r.status_code == 200 and ("<rss" in r.text or "<feed" in r.text):
                    _feed_cache["xml"] = r.text
                    _feed_cache["t"] = now
                    return r.text
        except Exception as ex:
            logging.warning(f"[instagram] RSS getirme hatası ({url}): {ex}")
    return None


def _post_id_cikar(link: str, guid: str) -> str:
    m = re.search(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)", link or "")
    if m:
        return m.group(1)
    return (guid or link or str(uuid.uuid4())).strip()


def _medya_bul(item_xml: str, aciklama: str) -> tuple[str | None, str]:
    """(medya_url, medya_tipi) — enclosure/media:content/description<img>'den."""
    url = None
    tip = "resim"
    m = re.search(r'<enclosure[^>]*url="([^"]+)"[^>]*(?:type="([^"]*)")?', item_xml)
    if m:
        url = m.group(1)
        if m.group(2) and "video" in m.group(2):
            tip = "video"
    if not url:
        m = re.search(r'<media:content[^>]*url="([^"]+)"', item_xml)
        if m:
            url = m.group(1)
    if not url and aciklama:
        m = re.search(r'<img[^>]*src="([^"]+)"', aciklama)
        if m:
            url = m.group(1)
    if item_xml.count("<media:content") > 1:
        tip = "carousel"
    return url, tip


def _rss_ayristir(xml_text: str) -> list[dict]:
    """RSS XML → post dict listesi. feedparser varsa onu, yoksa stdlib kullanır."""
    if not xml_text:
        return []
    postlar: list[dict] = []
    try:
        import feedparser  # tercih edilen
        d = feedparser.parse(xml_text)
        for e in d.entries:
            link = e.get("link", "")
            guid = e.get("id", "") or e.get("guid", "")
            aciklama = e.get("summary", "") or e.get("description", "")
            medya_url, medya_tipi = None, "resim"
            if e.get("enclosures"):
                enc = e["enclosures"][0]
                medya_url = enc.get("href") or enc.get("url")
                if "video" in (enc.get("type") or ""):
                    medya_tipi = "video"
            if not medya_url and e.get("media_content"):
                medya_url = e["media_content"][0].get("url")
            if not medya_url and aciklama:
                mm = re.search(r'<img[^>]*src="([^"]+)"', aciklama)
                if mm:
                    medya_url = mm.group(1)
            try:
                import time as _t
                yt = datetime.utcfromtimestamp(_t.mktime(e.published_parsed)) if e.get("published_parsed") else datetime.utcnow()
            except Exception:
                yt = datetime.utcnow()
            postlar.append({
                "instagram_post_id": _post_id_cikar(link, guid),
                "post_url": link,
                "medya_url": medya_url,
                "medya_tipi": medya_tipi,
                "baslik": (e.get("title") or aciklama or "")[:500],
                "yayin_tarihi": yt.isoformat(),
            })
        return postlar
    except ImportError:
        pass  # stdlib fallback
    except Exception as ex:
        logging.warning(f"[instagram] feedparser hatası, stdlib denenecek: {ex}")

    # ── stdlib fallback ──
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime

    def _yerel(el, ad):
        for c in el:
            if c.tag.split("}")[-1] == ad:
                return c
        return None

    try:
        kok = ET.fromstring(xml_text)
    except Exception as ex:
        logging.warning(f"[instagram] XML ayrıştırma hatası: {ex}")
        return []

    # RSS <item> parçalarını ham metinden de tarayabilmek için item bloklarını çıkar
    ham_itemler = re.findall(r"<item\b.*?</item>", xml_text, re.DOTALL)
    idx = 0
    for item in kok.iter():
        if item.tag.split("}")[-1] != "item":
            continue
        baslik_el = _yerel(item, "title")
        link_el = _yerel(item, "link")
        guid_el = _yerel(item, "guid")
        desc_el = _yerel(item, "description")
        pub_el = _yerel(item, "pubDate")
        link = (link_el.text or "").strip() if link_el is not None else ""
        guid = (guid_el.text or "").strip() if guid_el is not None else ""
        aciklama = (desc_el.text or "") if desc_el is not None else ""
        item_ham = ham_itemler[idx] if idx < len(ham_itemler) else ""
        idx += 1
        medya_url, medya_tipi = _medya_bul(item_ham, aciklama)
        try:
            yt = parsedate_to_datetime(pub_el.text).astimezone().replace(tzinfo=None) if pub_el is not None and pub_el.text else datetime.utcnow()
        except Exception:
            yt = datetime.utcnow()
        postlar.append({
            "instagram_post_id": _post_id_cikar(link, guid),
            "post_url": link,
            "medya_url": medya_url,
            "medya_tipi": medya_tipi,
            "baslik": ((baslik_el.text if baslik_el is not None else None) or aciklama or "")[:500],
            "yayin_tarihi": yt.isoformat(),
        })
    return postlar


# ─────────────────────────────────────────────────────────────
# Endpoint'ler
# ─────────────────────────────────────────────────────────────
@router.post("/instagram/senkronize")
async def instagram_senkronize(current_user=Depends(_ADMIN)):
    """RSS'ten postları çeker, yeni olanları kaydeder."""
    xml_text = await _rss_ham_getir()
    if not xml_text:
        raise HTTPException(status_code=503, detail="Instagram beslemesi geçici olarak kullanılamıyor.")
    postlar = _rss_ayristir(xml_text)
    yeni, mevcut, hata = 0, 0, 0
    now = datetime.utcnow().isoformat()
    for p in postlar:
        try:
            pid = p.get("instagram_post_id")
            if not pid:
                hata += 1
                continue
            var = await db.instagram_paylasimlari.find_one({"instagram_post_id": pid})
            if var:
                mevcut += 1
                continue
            await db.instagram_paylasimlari.insert_one({
                "id": str(uuid.uuid4()),
                "instagram_post_id": pid,
                "post_url": p.get("post_url", ""),
                "medya_url": p.get("medya_url"),
                "medya_tipi": p.get("medya_tipi", "resim"),
                "baslik": p.get("baslik"),
                "yayin_tarihi": p.get("yayin_tarihi", now),
                "cekilme_tarihi": now,
                "durum": "aktif",
            })
            yeni += 1
        except Exception as ex:
            logging.warning(f"[instagram] post kayıt hatası: {ex}")
            hata += 1

    toplam = await db.instagram_paylasimlari.count_documents({"durum": "aktif"})
    await db.instagram_ayar.update_one(
        {"_id": AYAR_ID},
        {"$set": {"son_senkron": now, "toplam_post": toplam}},
        upsert=True,
    )
    return {"yeni": yeni, "mevcut": mevcut, "hata": hata, "toplam": toplam}


async def _ayar_getir() -> dict:
    doc = await db.instagram_ayar.find_one({"_id": AYAR_ID}) or {}
    return {
        "aktif": doc.get("aktif", True),
        "son_senkron": doc.get("son_senkron"),
        "toplam_post": doc.get("toplam_post", 0),
    }


@router.get("/instagram/postlar")
async def instagram_postlar(sayfa: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=50),
                            current_user=Depends(get_current_user)):
    """En yeni postlar + çağıran öğretmenin etkileşim durumu."""
    if current_user.get("role") not in ("teacher", "admin", "coordinator"):
        raise HTTPException(status_code=403, detail="Yetkiniz yok.")
    ayar = await _ayar_getir()
    atla = (sayfa - 1) * limit
    docs = await db.instagram_paylasimlari.find({"durum": "aktif"}).sort("yayin_tarihi", -1).skip(atla).limit(limit).to_list(length=limit)
    toplam = await db.instagram_paylasimlari.count_documents({"durum": "aktif"})

    ogretmen_id = current_user["id"]
    postlar = []
    for d in docs:
        d.pop("_id", None)
        etk = await db.instagram_etkilesimleri.find_one(
            {"ogretmen_id": ogretmen_id, "instagram_post_id": d["instagram_post_id"]}
        ) or {}
        d["kullanici_durumu"] = {
            "begen": bool(etk.get("begen")),
            "kaydet": bool(etk.get("kaydet")),
            "yorum": etk.get("yorum"),
            "onur_ig_begen": bool(etk.get("onur_ig_begen")),
            "onur_ig_kaydet": bool(etk.get("onur_ig_kaydet")),
            "kazandigi_xp": etk.get("kazandigi_xp", 0),
        }
        postlar.append(d)
    return {"aktif": ayar["aktif"], "postlar": postlar, "toplam": toplam, "sayfa": sayfa, "limit": limit}


async def _etkilesim_al(ogretmen_id: str, post_id: str) -> dict:
    return await db.instagram_etkilesimleri.find_one(
        {"ogretmen_id": ogretmen_id, "instagram_post_id": post_id}
    ) or {
        "id": str(uuid.uuid4()), "ogretmen_id": ogretmen_id, "instagram_post_id": post_id,
        "begen": False, "begen_tarihi": None, "kaydet": False, "kaydet_tarihi": None,
        "yorum": None, "yorum_tarihi": None, "onur_ig_begen": False, "onur_ig_kaydet": False,
        "kazandigi_xp": 0, "xp_verilen": [],
    }


async def _teacher_puan(ogretmen_id: str) -> int:
    u = await db.users.find_one({"id": ogretmen_id})
    return (u or {}).get("puan", 0)


@router.post("/instagram/etkilesim")
async def instagram_etkilesim(data: dict, current_user=Depends(get_current_user)):
    """Beğen/kaydet/onur onay kutusu. İlk aktivasyonda XP verir (idempotent)."""
    if current_user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Bu işlem yalnızca öğretmenler içindir.")
    post_id = data.get("instagram_post_id")
    eylem = data.get("eylem")
    deger = bool(data.get("deger", True))
    if not post_id or eylem not in ETKILESIM_EYLEMLERI:
        raise HTTPException(status_code=400, detail="Geçersiz eylem veya post.")

    ogretmen_id = current_user["id"]
    etk = await _etkilesim_al(ogretmen_id, post_id)
    xp_verilen = set(etk.get("xp_verilen", []))
    kazandigi = 0

    etk[eylem] = deger
    if eylem in ("begen", "kaydet") and deger and not etk.get(f"{eylem}_tarihi"):
        etk[f"{eylem}_tarihi"] = datetime.utcnow().isoformat()

    # İlk kez aktifleştirme → XP (toggle kapatma XP geri almaz, tekrar açma XP vermez)
    if deger and eylem not in xp_verilen:
        kazandigi = XP_KURALLARI[eylem]
        xp_verilen.add(eylem)
        etk["kazandigi_xp"] = etk.get("kazandigi_xp", 0) + kazandigi

    etk["xp_verilen"] = list(xp_verilen)
    etk.pop("_id", None)
    await db.instagram_etkilesimleri.update_one(
        {"ogretmen_id": ogretmen_id, "instagram_post_id": post_id},
        {"$set": etk}, upsert=True,
    )
    if kazandigi:
        await db.users.update_one({"id": ogretmen_id}, {"$inc": {"puan": kazandigi}})

    return {"kazandigi_xp": kazandigi, "toplam_xp": await _teacher_puan(ogretmen_id),
            "post_toplam_xp": etk["kazandigi_xp"]}


@router.post("/instagram/yorum")
async def instagram_yorum(data: dict, current_user=Depends(get_current_user)):
    """OBA içi yorum. İlk yorumda +10 XP; sonradan düzenleme ek XP vermez.
    Yorum Instagram'a YAZILMAZ (yalnızca OBA'da saklanır)."""
    if current_user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Bu işlem yalnızca öğretmenler içindir.")
    post_id = data.get("instagram_post_id")
    yorum = (data.get("yorum") or "").strip()
    if not post_id or not yorum:
        raise HTTPException(status_code=400, detail="Post ve yorum gerekli.")

    ogretmen_id = current_user["id"]
    etk = await _etkilesim_al(ogretmen_id, post_id)
    xp_verilen = set(etk.get("xp_verilen", []))
    kazandigi = 0

    etk["yorum"] = yorum[:1000]
    if "yorum" not in xp_verilen:
        kazandigi = XP_KURALLARI["yorum"]
        xp_verilen.add("yorum")
        etk["yorum_tarihi"] = datetime.utcnow().isoformat()
        etk["kazandigi_xp"] = etk.get("kazandigi_xp", 0) + kazandigi

    etk["xp_verilen"] = list(xp_verilen)
    etk.pop("_id", None)
    await db.instagram_etkilesimleri.update_one(
        {"ogretmen_id": ogretmen_id, "instagram_post_id": post_id},
        {"$set": etk}, upsert=True,
    )
    if kazandigi:
        await db.users.update_one({"id": ogretmen_id}, {"$inc": {"puan": kazandigi}})

    return {"kazandigi_xp": kazandigi, "toplam_xp": await _teacher_puan(ogretmen_id),
            "post_toplam_xp": etk["kazandigi_xp"]}


@router.get("/instagram/durum")
async def instagram_durum(current_user=Depends(_ADMIN)):
    """Admin: son senkron, toplam post, aktif/pasif."""
    return await _ayar_getir()


@router.put("/instagram/durum")
async def instagram_durum_guncelle(data: dict, current_user=Depends(_ADMIN)):
    """Admin: widget aktif/pasif toggle."""
    aktif = bool(data.get("aktif", True))
    await db.instagram_ayar.update_one({"_id": AYAR_ID}, {"$set": {"aktif": aktif}}, upsert=True)
    return await _ayar_getir()
