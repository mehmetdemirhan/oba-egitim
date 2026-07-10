"""Ek panel endpoint'leri — registry.json üzerinden aktif olarak yüklenir.

Bu route'lar eski server.py'de mount SONRASI tanımlandıkları için üretimde
404 dönüyordu (frontend panelleri sessizce boş kalıyordu). registry migrasyonu
sonrası kayıt altına alındı.

İçerik:
- /istatistik/global-kelime-haritasi  (Global Kelime Haritası paneli)
- /kullanici/veri-indir, /kullanici/hesap-sil  (KVKK veri paneli)
- /gelisim/peer-review-ozet  (admin peer review özeti)
- /sezon/bilgi, /sezon/reset  (sezonluk reset paneli)

Not: /gelisim/peer-rozet burada TANIMLI DEĞİL — aktif karşılığı ilerleme.py'de
(çift kayıt olmaması için).
"""
import os
import io
import re
import json
import base64
import uuid
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from fastapi.responses import StreamingResponse, JSONResponse

from core.db import db, prepare_for_mongo, parse_from_mongo
from core.auth import get_current_user, require_role, UserRole
from core.sistem import get_xp_tablosu, get_puan_ayarlari, get_lig_esikleri, LIG_SIRA

router = APIRouter()


@router.get("/istatistik/global-kelime-haritasi")
async def global_kelime_haritasi(current_user=Depends(get_current_user)):
    """Türkiye genelinde kelime öğrenme analizi."""
    try:
        # En zor kelimeler - en yüksek yanlış oranına sahip
        pipeline_zor = [
            {"$group": {
                "_id": "$kelime",
                "toplam": {"$sum": 1},
                "yanlis": {"$sum": {"$cond": [{"$eq": ["$dogru", False]}, 1, 0]}},
                "sinif": {"$first": "$sinif"}
            }},
            {"$match": {"toplam": {"$gte": 10}}},
            {"$project": {
                "kelime": "$_id",
                "yanlis_oran": {"$round": [{"$multiply": [{"$divide": ["$yanlis", "$toplam"]}, 100]}, 0]},
                "adet": "$toplam",
                "sinif": 1
            }},
            {"$sort": {"yanlis_oran": -1}},
            {"$limit": 10}
        ]

        # En hızlı öğrenilen - en düşük ortalama öğrenme süresi
        pipeline_hizli = [
            {"$match": {"sure_gun": {"$exists": True, "$gt": 0}}},
            {"$group": {
                "_id": "$kelime",
                "sure_gun": {"$avg": "$sure_gun"},
                "adet": {"$sum": 1},
                "sinif": {"$first": "$sinif"}
            }},
            {"$match": {"adet": {"$gte": 20}}},
            {"$project": {
                "kelime": "$_id",
                "sure_gun": {"$round": ["$sure_gun", 1]},
                "adet": 1, "sinif": 1
            }},
            {"$sort": {"sure_gun": 1}},
            {"$limit": 8}
        ]

        en_zor = await db.kelime_ogrenme.aggregate(pipeline_zor).to_list(10)
        en_hizli = await db.kelime_ogrenme.aggregate(pipeline_hizli).to_list(8)

        # Yazım hataları
        pipeline_yanlis = [
            {"$match": {"yanlis_yazi": {"$exists": True}}},
            {"$group": {
                "_id": {"dogru": "$kelime", "yanlis": "$yanlis_yazi"},
                "adet": {"$sum": 1},
                "sinif": {"$first": "$sinif"}
            }},
            {"$sort": {"adet": -1}},
            {"$limit": 5}
        ]
        yanlislar_raw = await db.kelime_ogrenme.aggregate(pipeline_yanlis).to_list(5)
        yanlislar = [{"yanlis": f"{y['_id']['yanlis']}→{y['_id']['dogru']}", "adet": y["adet"], "sinif": y.get("sinif","?")} for y in yanlislar_raw]

        # Özet
        toplam_kelime = await db.kelime_ogrenme.distinct("kelime")
        toplam_ogrenme = await db.kelime_ogrenme.count_documents({"dogru": True})

        return {
            "en_zor": en_zor if en_zor else [],
            "en_hizli": en_hizli if en_hizli else [],
            "yanlislar": yanlislar if yanlislar else [],
            "ozet": {
                "toplam_kelime": len(toplam_kelime),
                "toplam_ogrenme": toplam_ogrenme,
                "ortalama_sure": 3.4,
                "aktif_il": 52
            }
        }
    except Exception as e:
        logging.error(f"[GLOBAL-KELIME] {e}")
        return {"en_zor": [], "en_hizli": [], "yanlislar": [], "ozet": {}}


@router.get("/kullanici/veri-indir")
async def veri_indir(current_user=Depends(get_current_user)):
    """KVKK madde 11: Kullanıcının tüm verilerini JSON olarak indir."""
    try:
        user_id = current_user["id"]

        # Okuma kayıtları
        okuma = await db.reading_logs.find({"student_id": user_id}, {"_id": 0}).to_list(1000)
        # XP kayıtları
        xp = await db.xp_logs.find({"kullanici_id": user_id}, {"_id": 0}).to_list(1000)
        # Rozetler
        rozetler = await db.kullanici_rozetler.find({"kullanici_id": user_id}, {"_id": 0}).to_list(100)
        # Mesajlar
        mesajlar = await db.messages.find({"$or": [{"sender_id": user_id}, {"receiver_id": user_id}]}, {"_id": 0}).to_list(500)
        # Kelime bankası
        kelimeler = await db.kelime_ogrenme.find({"kullanici_id": user_id}, {"_id": 0}).to_list(5000)

        veri = {
            "meta": {
                "export_tarihi": datetime.utcnow().isoformat(),
                "kullanici_id": user_id,
                "kvkk_not": "Bu dosya KVKK madde 11 kapsamında üretilmiştir.",
                "platform": "OBA - Okuma Becerileri Akademisi"
            },
            "profil": {
                "ad": current_user.get("name", ""),
                "email": current_user.get("email", ""),
                "rol": current_user.get("role", ""),
                "okul": current_user.get("school", ""),
            },
            "okuma_kayitlari": okuma,
            "xp_gecmisi": xp,
            "rozetler": rozetler,
            "mesajlar_ozet": {"toplam": len(mesajlar)},
            "kelime_bankasi": kelimeler,
        }

        import json
        from fastapi.responses import Response
        json_str = json.dumps(veri, ensure_ascii=False, indent=2, default=str)
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=oba_verilerim.json"}
        )
    except Exception as e:
        logging.error(f"[VERİ-İNDİR] {e}")
        raise HTTPException(status_code=500, detail="Veri hazırlanamadı")


@router.delete("/kullanici/hesap-sil")
async def hesap_sil(current_user=Depends(get_current_user)):
    """KVKK madde 11: Kullanıcının tüm verilerini ve hesabını sil."""
    try:
        user_id = current_user["id"]
        # Tüm collection'lardan kullanıcı verilerini sil
        await db.users.delete_one({"id": user_id})
        await db.reading_logs.delete_many({"student_id": user_id})
        await db.xp_logs.delete_many({"kullanici_id": user_id})
        await db.kullanici_rozetler.delete_many({"kullanici_id": user_id})
        await db.messages.delete_many({"$or": [{"sender_id": user_id}, {"receiver_id": user_id}]})
        await db.kelime_ogrenme.delete_many({"kullanici_id": user_id})
        await db.gelisim_tamamlama.delete_many({"kullanici_id": user_id})
        return {"ok": True, "mesaj": "Tüm verileriniz silindi"}
    except Exception as e:
        logging.error(f"[HESAP-SİL] {e}")
        raise HTTPException(status_code=500, detail="Hesap silinemedi")


@router.get("/gelisim/peer-review-ozet")
async def peer_review_ozet(current_user=Depends(get_current_user)):
    """Admin: Peer review genel özeti ve lider tablosu."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403)
    try:
        from datetime import timedelta
        haftanin_basi = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        haftanin_basi = haftanin_basi.replace(hour=0, minute=0, second=0, microsecond=0)

        toplam = await db.gelisim_oylar.count_documents({})
        bu_hafta = await db.gelisim_oylar.count_documents({"tarih": {"$gte": haftanin_basi}})

        # Onay oranı
        onay_count = await db.gelisim_oylar.count_documents({"onay": True})
        onay_orani = round(onay_count / toplam * 100) if toplam > 0 else 0

        # Kullanıcı başına oy sayısı
        pipeline = [
            {"$group": {"_id": "$kullanici_id", "toplam_oy": {"$sum": 1}}},
            {"$sort": {"toplam_oy": -1}},
            {"$limit": 5}
        ]
        lider_ids = await db.gelisim_oylar.aggregate(pipeline).to_list(5)

        liderler = []
        for l in lider_ids:
            u = await db.users.find_one({"id": l["_id"]})
            if u:
                t = l["toplam_oy"]
                rozet = "🥉 Bronz Onaycı"
                if t >= 50: rozet = "💎 Platin Uzman"
                elif t >= 20: rozet = "🥇 Altın Moderatör"
                elif t >= 5:  rozet = "🥈 Gümüş Değerlendirici"
                liderler.append({"ad": u.get("name",""), "toplam_oy": t, "rozet": rozet, "okul": u.get("school","")})

        aktif = await db.gelisim_oylar.distinct("kullanici_id", {"tarih": {"$gte": haftanin_basi}})

        return {
            "ozet": {"toplam_oy": toplam, "bu_hafta": bu_hafta, "aktif_moderator": len(aktif), "onay_orani": onay_orani},
            "liderler": liderler,
            "rozet_dagilim": [
                {"rozet": "💎 Platin Uzman", "min": 50, "sayi": 0, "renk": "from-blue-400 to-cyan-300"},
                {"rozet": "🥇 Altın Moderatör", "min": 20, "sayi": 0, "renk": "from-yellow-500 to-amber-400"},
                {"rozet": "🥈 Gümüş Değerlendirici", "min": 5, "sayi": 0, "renk": "from-gray-400 to-gray-300"},
                {"rozet": "🥉 Bronz Onaycı", "min": 0, "sayi": 0, "renk": "from-amber-700 to-amber-500"},
            ],
            "haftalik_trend": [0]*7
        }
    except Exception as e:
        logging.error(f"[PEER-REVIEW-OZET] {e}")
        return {"ozet": {}, "liderler": [], "rozet_dagilim": [], "haftalik_trend": [0]*7}


# ── Ölü route'lar (orijinalde mount sonrası): /sezon/* — kayıt-dışı korundu.
@router.get("/sezon/bilgi")
async def sezon_bilgi(current_user=Depends(get_current_user)):
    """Mevcut sezon bilgisi."""
    try:
        sezon = await db.sezon_meta.find_one({}, {"_id": 0})
        if not sezon:
            katilimci = await db.users.count_documents({})
            sezon = {"sezon_no": 1, "baslangic": datetime.utcnow().isoformat(), "katilimci": katilimci}
        return sezon
    except Exception as e:
        return {"sezon_no": "—", "katilimci": 0}


@router.post("/sezon/reset")
async def sezon_reset(current_user=Depends(get_current_user)):
    """Admin: Sezon sıfırlama - XP sıfırla, rozetleri koru."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Sadece admin yapabilir")
    try:
        # Tüm kullanıcıların XP ve lig puanını sıfırla
        await db.users.update_many({}, {"$set": {"xp": 0, "lig": "bronz"}})
        # XP loglarını arşivle
        sezon_no = (await db.sezon_meta.find_one({}) or {}).get("sezon_no", 1)
        await db.xp_logs_arsiv.insert_many(
            [{"sezon": sezon_no, **log} async for log in db.xp_logs.find({})]
        )
        await db.xp_logs.delete_many({})
        # Sezon numarasını artır
        await db.sezon_meta.update_one(
            {}, {"$inc": {"sezon_no": 1}, "$set": {"baslangic": datetime.utcnow().isoformat()}},
            upsert=True
        )
        return {"ok": True, "mesaj": f"Sezon {sezon_no} tamamlandı, yeni sezon başladı"}
    except Exception as e:
        logging.error(f"[SEZON-RESET] {e}")
        raise HTTPException(status_code=500, detail="Sezon sıfırlanamadı")
