"""Rozet yardımcıları — tanım getirme, ödül puanı normalizasyonu, bildirim.

FAZ 1 amacı: ilerleme.py içinde 3 ayrı yerde tekrarlanan "rozet puanı toplama"
mantığını tek yere toplamak ve alan adı tutarsızlığını (öğretmen "puan",
öğrenci "xp") tek bir "odul_puan" alanında normalize etmek.

Geriye dönük uyumluluk: eski kayıtlarda/DEFAULT'larda hâlâ "puan" veya "xp"
bulunabileceği için okuma daima üç alanı da yoklar (odul_puan → puan → xp).

Not: Bu modül core katmanındadır ve yalnızca core.db + core.sistem'e bağımlıdır.
Bildirim (modules.bildirim) katman ihlali yaratmasın diye fonksiyon içinde
lazy import edilir ve best-effort çağrılır.
"""
import logging

from core.db import db
from core.sistem import get_ogretmen_rozetleri, get_ogrenci_rozetleri


def _norm_rol(rol):
    r = (rol or "").strip().lower()
    if r in ("ogrenci", "öğrenci", "student"):
        return "student"
    if r in ("ogretmen", "öğretmen", "teacher"):
        return "teacher"
    return None


def rozet_odul_puan(tanim: dict) -> int:
    """Rozet tanımından ödül puanını normalize eder.

    Yeni kanonik alan: ``odul_puan``. Eski veriler için geriye dönük olarak
    ``puan`` (öğretmen) ve ``xp`` (öğrenci) alanlarına düşer.
    """
    if not tanim:
        return 0
    deger = tanim.get("odul_puan", tanim.get("puan", tanim.get("xp", 0)))
    try:
        return int(deger or 0)
    except (TypeError, ValueError):
        return 0


async def rozet_tanimlarini_getir(rol: str = None) -> list:
    """Rol'e göre rozet tanım listesini döner.

    rol = "teacher"/"ogretmen" → öğretmen rozetleri
    rol = "student"/"ogrenci"  → öğrenci rozetleri
    rol = None                 → ikisinin birleşimi
    """
    r = _norm_rol(rol)
    if r == "teacher":
        return await get_ogretmen_rozetleri()
    if r == "student":
        return await get_ogrenci_rozetleri()
    return (await get_ogretmen_rozetleri()) + (await get_ogrenci_rozetleri())


async def rozet_puan_haritasi(rol: str = None) -> dict:
    """{rozet_kodu: odul_puan} haritası döner."""
    return {t["kod"]: rozet_odul_puan(t) for t in await rozet_tanimlarini_getir(rol)}


async def kullanici_toplam_odul_puan(user_id: str, rol: str = None) -> int:
    """Kullanıcının kazandığı tüm rozetlerin toplam ödül puanı."""
    harita = await rozet_puan_haritasi(rol)
    toplam = 0
    async for r in db.kazanilan_rozetler.find({"kullanici_id": user_id}):
        toplam += harita.get(r.get("rozet_kodu"), 0)
    return toplam


async def rozet_bildirim_gonder(user_id: str, tanim: dict):
    """Rozet kazanımında 'rozet_kazandi' bildirimi gönderir (best-effort).

    Bildirim modülü lazy import edilir; herhangi bir hata ödül akışını
    kesmez, yalnızca loglanır.
    """
    try:
        from modules.bildirim import bildirim_olustur
        ad = (tanim or {}).get("ad", "Yeni Rozet")
        ikon = (tanim or {}).get("ikon", "🏅")
        puan = rozet_odul_puan(tanim)
        await bildirim_olustur(
            user_id,
            "rozet_kazandi",
            f"{ikon} Yeni rozet: {ad}! +{puan} puan kazandın.",
            (tanim or {}).get("kod"),
        )
    except Exception as ex:
        logging.warning(f"[rozet] bildirim gönderilemedi (user={user_id}): {ex}")
