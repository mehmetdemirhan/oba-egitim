"""Ortak 'yarım kalan kayıt' temizleyici.

TIMI taslakları (timi_sonuclar) ve okuma analizi oturumları (diagnostic_oturumlar) gibi
TAMAMLANMAMIŞ kayıtlar için TEK mekanizma — kod tekrarı yok. Her tür kendi koleksiyon/alan/
bildirim ayarını geçer. >15 gün olanları siler; 13-15 gün arası olanlara başlatan öğretmene
BİR KEZ uyarı gönderir; her silme islem_log'a düşer.
"""
from datetime import datetime, timezone

from core.db import db


def yas_gun(tarih, now=None):
    """ISO tarih → bugünden fark (gün). Çözümlenemezse None."""
    if not tarih:
        return None
    now = now or datetime.now(timezone.utc)
    try:
        d = datetime.fromisoformat(str(tarih).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (now - d).days
    except Exception:
        return None


async def yarim_kayit_temizle(*, koleksiyon, filtre, tarih_alan, ogretmen_alan,
                              modul, silme_islem, hedef_tip, bildirim_tur, uyari_mesaj,
                              sil_gun=15, uyari_gun=13):
    """`filtre`'ye uyan (tamamlanmamış) kayıtlardan yaşı ≥ sil_gun olanları KALICI siler;
    uyari_gun ≤ yaş < sil_gun olanlara (silmeden ~2 gün önce) başlatan öğretmene BİR KEZ bildirim
    yollar (silme_uyari_tarihi damgasıyla tekrarı önler). Her silme islem_log'a düşer.

    Döner: {"ok", "silinen", "uyarilan"}.
    """
    now = datetime.now(timezone.utc)
    from core.audit import islem_kaydet
    sistem = {"id": "system", "role": "system", "ad": "Sistem", "soyad": ""}
    silinen = uyarilan = 0
    kayitlar = await db[koleksiyon].find(filtre).to_list(length=20000)
    for s in kayitlar:
        yas = yas_gun(s.get(tarih_alan), now)
        if yas is None:
            continue
        if yas >= sil_gun:
            await db[koleksiyon].delete_one({"id": s["id"]})
            await islem_kaydet(sistem, modul, silme_islem, hedef_tip, s["id"], "yas_gun", yas, "silindi")
            silinen += 1
        elif yas >= uyari_gun and not s.get("silme_uyari_tarihi"):
            try:
                from modules.bildirim import bildirim_olustur
                await bildirim_olustur(s.get(ogretmen_alan), bildirim_tur, uyari_mesaj, s["id"])
            except Exception:
                pass
            await db[koleksiyon].update_one({"id": s["id"]}, {"$set": {"silme_uyari_tarihi": now.isoformat()}})
            uyarilan += 1
    return {"ok": True, "silinen": silinen, "uyarilan": uyarilan}


async def throttle_gunluk(tip: str, fn):
    """Cron yoksa ilk-istek tetikli: günde bir kez fn() çalıştırır (sistem_ayarlari zaman damgası)."""
    try:
        son = await db.sistem_ayarlari.find_one({"tip": tip})
        now = datetime.now(timezone.utc)
        if son and son.get("zaman"):
            d = yas_gun(son["zaman"], now)
            if d is not None and d < 1:
                return
        await db.sistem_ayarlari.update_one({"tip": tip},
            {"$set": {"tip": tip, "zaman": now.isoformat()}}, upsert=True)
        await fn()
    except Exception:
        pass
