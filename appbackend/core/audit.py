"""Genel işlem/audit kaydı — db.islem_log.

Kim, ne zaman, hangi modülde, hangi işlemi, hangi hedefte, hangi alanı eski→yeni
yaptı. Finansal alanlar (muhasebe) ve öğrenci düzenleme/kaldırma gibi geri-dönüş
gerektirebilecek işlemler için ortak yardımcı. Yönetici panelindeki salt-okunur
"İşlem Kayıtları" görünümü bu koleksiyonu okur.

muhasebe.py'nin eski `_log`/db.muhasebe_log deseni buraya genelleştirildi.
"""
import uuid
import logging
from datetime import datetime

from core.db import db


def _kullanici_ad(user: dict) -> str:
    return f"{(user or {}).get('ad', '')} {(user or {}).get('soyad', '')}".strip()


async def islem_kaydet(user: dict, modul: str, islem: str, hedef_tip: str | None = None,
                       hedef_id: str | None = None, alan: str | None = None,
                       eski=None, yeni=None, ekstra: dict | None = None) -> None:
    """Bir işlemi db.islem_log'a yazar. Asla exception fırlatmaz (log yazımı esas
    işlemi bozmamalı).

    modul     : "muhasebe" | "ogrenci" | "egitim_turu" | ...
    islem     : "duzenle" | "kaldir" | "geri_al" | "olustur" | "kur_ucreti_ekle" ...
    hedef_tip : "ogrenci" | "ogretmen" | "egitim_turu" | ...
    """
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "kullanici_id": (user or {}).get("id"),
            "kullanici_rol": (user or {}).get("role"),
            "kullanici_ad": _kullanici_ad(user),
            "tarih": datetime.utcnow().isoformat(),
            "modul": modul,
            "islem": islem,
            "hedef_tip": hedef_tip,
            "hedef_id": hedef_id,
            "alan": alan,
            "eski": eski,
            "yeni": yeni,
        }
        if ekstra:
            doc["ekstra"] = ekstra
        await db.islem_log.insert_one(doc)
    except Exception as ex:
        logging.warning(f"[audit] islem_log yazılamadı: {ex}")


async def islem_listele(modul: str | None = None, hedef_id: str | None = None,
                        kullanici_id: str | None = None, hedef_tip: str | None = None,
                        limit: int = 200) -> list[dict]:
    """Salt-okunur işlem kayıtları (yeni→eski). Yönetici İşlem Kayıtları görünümü için."""
    sorgu: dict = {}
    if modul:
        sorgu["modul"] = modul
    if hedef_id:
        sorgu["hedef_id"] = hedef_id
    if kullanici_id:
        sorgu["kullanici_id"] = kullanici_id
    if hedef_tip:
        sorgu["hedef_tip"] = hedef_tip
    try:
        return await db.islem_log.find(sorgu, {"_id": 0}).sort("tarih", -1) \
            .to_list(length=min(max(1, limit), 1000))
    except Exception as ex:
        logging.warning(f"[audit] islem_listele hatası: {ex}")
        return []
