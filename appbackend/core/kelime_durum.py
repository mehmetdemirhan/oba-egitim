"""Öğrenci bazlı kelime öğrenme durumu — merkezî Leitner servisi.

Tek koleksiyon: `db.kelime_tekrar` (öğrenci × kelime). Alanlar (Leitner Box):
  ogrenci_id, kelime, anlam, ornek_cumle, sinif,
  kutu (1-5), tekrar_sayisi, dogru_sayisi, yanlis_sayisi,
  son_gosterim, sonraki_gosterim, ogrenildi_tarihi, tarih

"Öğrenildi" eşiği = kutu >= OGRENILDI_KUTU (4). Bu modül, ai_kelime.py'deki mevcut
Kelime Evrimi sistemini GENİŞLETİR (ayrı koleksiyon kurmaz): tüm kelime/anlam
egzersizleri bir kelimeyle karşılaşınca `kelime_karsilasma` çağırır; kelime seçim
algoritması `ogrenci_kelime_sec` ile öğrenilmiş kelimeleri rotasyondan çıkarır.
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timedelta

from core.db import db

OGRENILDI_KUTU = 4  # kutu >= 4 → "öğrenildi" (kullanıcı kararı)


def _araliklar(sinif: int) -> dict:
    """Yaş/sınıf bazlı Leitner tekrar aralıkları (gün)."""
    if sinif <= 2:      # 6-8 yaş
        return {1: 1, 2: 2, 3: 5, 4: 12, 5: 30}
    if sinif <= 5:      # 9-11 yaş
        return {1: 1, 2: 3, 3: 7, 4: 21, 5: 45}
    return {1: 1, 2: 3, 3: 7, 4: 30, 5: 60}   # 12+ yaş


def leitner_ilerlet(mevcut_kutu: int, dogru: bool, sinif: int) -> tuple[int, str, int]:
    """Leitner ilerlemesi. Dönüş: (yeni_kutu, sonraki_gosterim_iso, xp).

    Doğru → kutu +1 (max 5), +2 XP. Yanlış → kutu 1'e döner, +1 XP.
    ai_kelime.py /cevapla ile AYNI algoritma (tek kaynak)."""
    if dogru:
        yeni_kutu = min(5, int(mevcut_kutu) + 1)
        xp = 2
    else:
        yeni_kutu = 1
        xp = 1
    gun = _araliklar(int(sinif)).get(yeni_kutu, 7)
    sonraki = (datetime.utcnow() + timedelta(days=gun)).isoformat()
    return yeni_kutu, sonraki, xp


def durum_etiket(kutu: int | None) -> str:
    """Kutu → durum etiketi. (Kayıt yoksa None geçilir.)"""
    if kutu is None:
        return "ogrenilmedi"
    if int(kutu) >= OGRENILDI_KUTU:
        return "ogrenildi"
    return "ogreniliyor"


async def kelime_karsilasma(ogrenci_id: str, kelime: str, dogru: bool, sinif: int = 3,
                            anlam: str = "", ornek_cumle: str = "", xp_ver: bool = False) -> dict | None:
    """Bir kelimeyle karşılaşmayı (doğru/yanlış) Leitner'e işler; kayıt yoksa oluşturur.

    Kutu ilk kez OGRENILDI_KUTU'ya ulaştığında `ogrenildi_tarihi` damgalanır.
    `xp_ver=True` ise öğrenciye XP eklenir (Kelime Evrimi kendi XP'sini verir; motor
    egzersizleri kendi XP'sini /bitir'de verdiği için varsayılan False).
    Dönüş: {kelime, kutu, durum} veya None (geçersiz kelime)."""
    k = (kelime or "").strip().lower()
    if not k:
        return None
    try:
        kayit = await db.kelime_tekrar.find_one({"ogrenci_id": ogrenci_id, "kelime": k})
        simdi = datetime.utcnow()
        # Yeni kart Leitner'de kutu 1'den girer; mevcutsa kendi kutusundan ilerler.
        baz_kutu = int(kayit.get("kutu", 1)) if kayit else 1
        onceki_kutu = int(kayit.get("kutu", 0)) if kayit else 0
        yeni_kutu, sonraki, xp = leitner_ilerlet(baz_kutu, dogru, sinif)

        set_alan = {
            "kutu": yeni_kutu,
            "son_gosterim": simdi.isoformat(),
            "sonraki_gosterim": sonraki,
        }
        # İlk kez öğrenildi eşiğine ulaştıysa tarihini damgala (bir kez).
        if yeni_kutu >= OGRENILDI_KUTU and onceki_kutu < OGRENILDI_KUTU and not (kayit and kayit.get("ogrenildi_tarihi")):
            set_alan["ogrenildi_tarihi"] = simdi.isoformat()

        if kayit:
            await db.kelime_tekrar.update_one(
                {"id": kayit["id"]},
                {
                    "$set": set_alan,
                    "$inc": {
                        "tekrar_sayisi": 1,
                        "dogru_sayisi": 1 if dogru else 0,
                        "yanlis_sayisi": 0 if dogru else 1,
                    },
                },
            )
        else:
            await db.kelime_tekrar.insert_one({
                "id": str(uuid.uuid4()),
                "ogrenci_id": ogrenci_id,
                "kelime": k,
                "anlam": anlam or "",
                "ornek_cumle": ornek_cumle or "",
                "sinif": int(sinif),
                "kutu": yeni_kutu,
                "tekrar_sayisi": 1,
                "dogru_sayisi": 1 if dogru else 0,
                "yanlis_sayisi": 0 if dogru else 1,
                "son_gosterim": simdi.isoformat(),
                "sonraki_gosterim": sonraki,
                "ogrenildi_tarihi": simdi.isoformat() if yeni_kutu >= OGRENILDI_KUTU else None,
                "tarih": simdi.isoformat(),
            })

        if xp_ver:
            try:
                await db.users.update_one({"id": ogrenci_id}, {"$inc": {"toplam_xp": xp}})
            except Exception:
                pass

        return {"kelime": k, "kutu": yeni_kutu, "durum": durum_etiket(yeni_kutu)}
    except Exception as ex:
        logging.warning(f"[kelime_durum] karşılaşma hatası ({k}): {ex}")
        return None


async def ogrenilmis_set(ogrenci_id: str) -> set[str]:
    """Öğrencinin 'öğrenildi' (kutu>=OGRENILDI_KUTU) kelimelerinin küçük-harf kümesi."""
    try:
        docs = await db.kelime_tekrar.find(
            {"ogrenci_id": ogrenci_id, "kutu": {"$gte": OGRENILDI_KUTU}},
            {"kelime": 1},
        ).to_list(length=5000)
        return {str(d.get("kelime", "")).strip().lower() for d in docs if d.get("kelime")}
    except Exception as ex:
        logging.warning(f"[kelime_durum] öğrenilmiş sorgu hatası: {ex}")
        return set()


async def ogrenci_kelime_sec(ogrenci_id: str, sinif: int, sayi: int,
                             ders_filtre: list | None = None) -> list[dict]:
    """MEB-öncelikli kelime seçer AMA öğrencinin 'öğrenildi' kelimelerini rotasyondan
    ÇIKARIR (tekrar etmesin). Öğrenilmemiş/öğreniliyor kelimeler öncelikli döner.
    Kayıtları core.kelime_secici'den alır; öğrenilmiş olanları filtreler."""
    from core.kelime_secici import kelime_sec
    ogrenilmis = await ogrenilmis_set(ogrenci_id)
    # Öğrenilmişleri eleyebilmek için biraz fazla iste, sonra kırp.
    havuz = await kelime_sec(sinif, max(sayi * 2, sayi + len(ogrenilmis)), ders_filtre=ders_filtre,
                             meb_orani=1.0, istatistik=False)
    out = [k for k in havuz if k.get("kelime", "").strip().lower() not in ogrenilmis]
    return out[:sayi] if out else havuz[:sayi]


async def ogrenci_kelime_ozet(ogrenci_id: str, sinif: int) -> dict:
    """Öğretmen paneli için özet: {ogrenilen, ogreniliyor, toplam_havuz, oran}.

    ogrenilen   : kutu>=OGRENILDI_KUTU kelime sayısı
    ogreniliyor : kutu 1-3 (karşılaşılmış ama henüz öğrenilmemiş)
    toplam_havuz: öğrencinin sınıfına uygun MEB havuzundaki benzersiz kelime sayısı
    """
    try:
        ogrenilen = await db.kelime_tekrar.count_documents(
            {"ogrenci_id": ogrenci_id, "kutu": {"$gte": OGRENILDI_KUTU}})
        ogreniliyor = await db.kelime_tekrar.count_documents(
            {"ogrenci_id": ogrenci_id, "kutu": {"$lt": OGRENILDI_KUTU}})
    except Exception:
        ogrenilen, ogreniliyor = 0, 0
    toplam_havuz = 0
    try:
        from core.kelime_secici import meb_kelime_stringleri
        havuz = await meb_kelime_stringleri(int(sinif), limit=5000)
        toplam_havuz = len(havuz)
    except Exception as ex:
        logging.warning(f"[kelime_durum] havuz sayımı hatası: {ex}")
    oran = round(ogrenilen / toplam_havuz * 100) if toplam_havuz else 0
    return {"ogrenilen": ogrenilen, "ogreniliyor": ogreniliyor,
            "toplam_havuz": toplam_havuz, "oran": oran}
