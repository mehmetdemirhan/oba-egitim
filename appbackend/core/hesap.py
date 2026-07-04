"""Hesap yardımcıları — geçici şifre üretimi + kullanıcı↔öğretmen köprüsü.

users ile teachers koleksiyonlarını birleştiren mantık tek yerde toplanır.
Kanonik kimlik: teachers.id (= users.linked_id). Ek olarak geriye dönük
referans teachers.user_id = users.id tutulur (additive, mevcut veriyi bozmaz).
"""
import uuid
import string
import secrets
from datetime import datetime, timezone

from core.db import db

# Fiilen ders anlatan roller — bunlar için otomatik teachers kaydı açılır.
OGRETMEN_ROLLERI = {"teacher", "coordinator", "admin"}


def gecici_sifre_uret(uzunluk: int = 10) -> str:
    """Güçlü, tek kullanımlık geçici şifre (en az 1 büyük/küçük/rakam)."""
    alfabe = string.ascii_letters + string.digits
    while True:
        p = "".join(secrets.choice(alfabe) for _ in range(uzunluk))
        if (any(c.islower() for c in p) and any(c.isupper() for c in p)
                and any(c.isdigit() for c in p)):
            return p


async def ogretmen_kaydi_olustur(user_doc: dict) -> str | None:
    """role'ü OGRETMEN_ROLLERI içinde olan kullanıcı için teachers kaydı açar
    ve iki yönlü köprüyü kurar (users.linked_id ⇄ teachers.user_id).

    - Zaten linked_id varsa yeni kayıt AÇMAZ; yalnız back-ref'i (user_id) garanti eder.
    - teacher_id döner (rol uygun değilse None).
    Mevcut id'ler değişmez; yalnız yeni köprü alanları eklenir.
    """
    rol = user_doc.get("role")
    if rol not in OGRETMEN_ROLLERI:
        return None

    mevcut = user_doc.get("linked_id")
    if mevcut:
        await db.teachers.update_one({"id": mevcut}, {"$set": {"user_id": user_doc["id"]}})
        return mevcut

    teacher_id = str(uuid.uuid4())
    await db.teachers.insert_one({
        "id": teacher_id,
        "ad": user_doc.get("ad", ""),
        "soyad": user_doc.get("soyad", ""),
        "brans": user_doc.get("brans") or "-",
        "telefon": user_doc.get("telefon") or "",
        "seviye": "yeni",
        "ogrenci_sayisi": 0,
        "atanan_ogrenciler": [],
        "yapilmasi_gereken_odeme": 0.0,
        "yapilan_odeme": 0.0,
        "arsivli": False,
        "user_id": user_doc["id"],
        "olusturma_tarihi": datetime.now(timezone.utc).isoformat(),
    })
    await db.users.update_one({"id": user_doc["id"]}, {"$set": {"linked_id": teacher_id}})
    return teacher_id
