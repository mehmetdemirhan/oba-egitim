"""MongoDB bağlantısı, GridFS bucket ve Mongo (de)serileştirme yardımcıları.

server.py'daki orijinal tanımların birebir aynısı; sadece tek bir yere taşındı.
"""
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

from core.config import MONGO_URL, DB_NAME

# MongoDB connection
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# Backup (GridFS) bucket
backup_fs = AsyncIOMotorGridFSBucket(db, bucket_name="backups")


def prepare_for_mongo(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = prepare_for_mongo(value)
            elif isinstance(value, list):
                data[key] = [prepare_for_mongo(item) if isinstance(item, dict) else item for item in value]
    return data


def parse_from_mongo(item):
    if isinstance(item, dict):
        for key, value in item.items():
            if key.endswith('_tarihi') or key in ('olusturma_tarihi', 'tarih'):
                if isinstance(value, str):
                    try:
                        item[key] = datetime.fromisoformat(value)
                    except:
                        pass
            elif isinstance(value, dict):
                item[key] = parse_from_mongo(value)
            elif isinstance(value, list):
                item[key] = [parse_from_mongo(s) if isinstance(s, dict) else s for s in value]
    return item


# ─────────────────────────────────────────────
# INDEX YÖNETİMİ (startup'ta çağrılır — idempotent)
# ─────────────────────────────────────────────

async def _dedup_kazanilan_rozetler():
    """kazanilan_rozetler'de aynı (kullanici_id, rozet_kodu) çiftinin fazla
    kopyalarını siler. Unique index oluşturmadan ÖNCE çağrılmalıdır; aksi halde
    mevcut duplikeler yüzünden index kurulumu patlar."""
    import logging
    seen = set()
    silinen = 0
    async for r in db.kazanilan_rozetler.find(
        {}, {"kullanici_id": 1, "rozet_kodu": 1}
    ).sort("_id", 1):
        anahtar = (r.get("kullanici_id"), r.get("rozet_kodu"))
        if anahtar in seen:
            await db.kazanilan_rozetler.delete_one({"_id": r["_id"]})
            silinen += 1
        else:
            seen.add(anahtar)
    if silinen:
        logging.info(f"[db] kazanilan_rozetler: {silinen} duplike rozet temizlendi")
    return silinen


async def ensure_indexes():
    """Kritik koleksiyon index'lerini oluşturur (idempotent).

    server.py startup event'ine bağlanır. Hata olsa bile uygulama açılmaya
    devam etsin diye tüm blok try/except ile sarılıdır.
    """
    import logging
    try:
        await _dedup_kazanilan_rozetler()
        await db.kazanilan_rozetler.create_index(
            [("kullanici_id", 1), ("rozet_kodu", 1)],
            unique=True,
            name="uq_kullanici_rozet",
        )
        # Rozet TANIM koleksiyonu (FAZ 2'de dolar) — (rol, kod) benzersiz.
        # NOT: kod tek başına benzersiz DEĞİL; gorev_ilk/egz_ilk gibi kodlar hem
        # öğretmen hem öğrenci rozetlerinde bulunur, rol ile ayrışır.
        try:
            await db.rozetler.drop_index("uq_rozet_kod")  # eski (yanlış) index varsa kaldır
        except Exception:
            pass
        await db.rozetler.create_index(
            [("rol", 1), ("kod", 1)], unique=True, name="uq_rozet_rol_kod")
        # Tema TANIM koleksiyonu — kod benzersiz
        await db.theme_configs.create_index("kod", unique=True, name="uq_tema_kod")
        # Web Push: abonelik endpoint benzersiz + hatırlatma idempotency anahtarı
        await db.push_abonelikleri.create_index("endpoint", unique=True, name="uq_push_endpoint")
        await db.push_gonderimler.create_index("anahtar", unique=True, name="uq_push_anahtar")
        # Kalıcı oturum refresh token'ları
        await db.refresh_tokens.create_index("token_hash", unique=True, name="uq_refresh_hash")
        await db.refresh_tokens.create_index("user_id", name="ix_refresh_user")
        # Giriş/çıkış logu (giris_log): TTL ile otomatik silme + sorgu index'leri.
        # Saklama süresi ayardan (tip=log_saklama, gün); yoksa 90 gün.
        try:
            _ayar = await db.sistem_ayarlari.find_one({"tip": "log_saklama"})
            _gun = int(((_ayar or {}).get("degerler") or {}).get("gun") or 90)
        except Exception:
            _gun = 90
        _ttl_saniye = max(1, _gun) * 86400
        try:
            await db.giris_log.create_index(
                "olusturma", expireAfterSeconds=_ttl_saniye, name="ttl_giris_log")
        except Exception:
            # Index farklı süreyle zaten var → collMod ile güncelle
            try:
                await db.command({
                    "collMod": "giris_log",
                    "index": {"name": "ttl_giris_log", "expireAfterSeconds": _ttl_saniye},
                })
            except Exception as _ie:
                logging.warning(f"[db] giris_log TTL güncellenemedi: {_ie}")
        await db.giris_log.create_index([("tip", 1), ("olusturma", -1)], name="ix_giris_tip")
        await db.giris_log.create_index([("rol", 1), ("olusturma", -1)], name="ix_giris_rol")
        # SSS: yayın kayıtları (kategori+sıra) ve bekleyen kuyruk (durum+tarih)
        await db.sss.create_index([("aktif", 1), ("kategori", 1), ("sira", 1)], name="ix_sss_liste")
        await db.sss_sorular.create_index([("durum", 1), ("olusturma", -1)], name="ix_sss_kuyruk")
        await db.sss_sorular.create_index([("soran_id", 1), ("olusturma", -1)], name="ix_sss_soran")
        logging.info("[db] rozet+tema+giris_log+sss index'leri hazır")
    except Exception as ex:
        logging.error(f"[db] ensure_indexes hatası: {type(ex).__name__}: {ex}")
