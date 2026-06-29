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
