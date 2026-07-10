"""Risk skoru hesaplama endpoint'leri (/risk-skor/*).

server.py'dan birebir taşındı. Yollar ve davranış değişmedi.
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import get_current_user

router = APIRouter()


@router.get("/risk-skor/{ogrenci_id}")
async def get_risk_skor(ogrenci_id: str, current_user=Depends(get_current_user)):
    logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).to_list(length=None)
    gorevler = await db.gorevler.find({"hedef_id": ogrenci_id, "hedef_tip": "ogrenci"}).to_list(length=None)

    from datetime import timedelta
    simdi = datetime.utcnow()
    yedi_gun = simdi - timedelta(days=7)
    otuz_gun = simdi - timedelta(days=30)

    # Faktörler
    son_7_gun_log = [l for l in logs if l.get("tarih", "") >= yedi_gun.isoformat()]
    son_30_gun_log = [l for l in logs if l.get("tarih", "") >= otuz_gun.isoformat()]
    aktif_gunler_7 = len(set(l.get("tarih", "")[:10] for l in son_7_gun_log))
    toplam_dakika_7 = sum(l.get("sure_dakika", 0) for l in son_7_gun_log)
    tamamlanmamis = len([g for g in gorevler if g.get("durum") == "bekliyor"])
    suresi_dolmus = len([g for g in gorevler if g.get("durum") == "suresi_doldu"])

    # Streak
    tarihler = sorted(set(l.get("tarih", "")[:10] for l in logs), reverse=True)
    streak = 0
    for i in range(60):
        gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
        if gun in tarihler:
            streak += 1
        elif i > 0:
            break

    # Risk hesapla (0-100, yüksek = riskli)
    risk = 0
    faktorler = []

    if aktif_gunler_7 == 0:
        risk += 40; faktorler.append("Son 7 günde hiç okuma yok")
    elif aktif_gunler_7 < 2:
        risk += 25; faktorler.append(f"Son 7 günde sadece {aktif_gunler_7} gün aktif")
    elif aktif_gunler_7 < 4:
        risk += 10; faktorler.append(f"Haftalık hedefin altında ({aktif_gunler_7}/4)")

    if toplam_dakika_7 < 12:
        risk += 20; faktorler.append(f"Haftalık okuma çok düşük ({toplam_dakika_7} dk)")
    elif toplam_dakika_7 < 48:
        risk += 10; faktorler.append(f"Haftalık okuma ortalamanın altında")

    if streak == 0:
        risk += 15; faktorler.append("Streak kırılmış")

    if tamamlanmamis > 2:
        risk += 10; faktorler.append(f"{tamamlanmamis} tamamlanmamış görev")

    if suresi_dolmus > 0:
        risk += 10; faktorler.append(f"{suresi_dolmus} süresi dolmuş görev")

    if len(son_30_gun_log) == 0:
        risk += 20; faktorler.append("Son 30 günde hiç okuma yok")

    risk = min(100, risk)
    seviye = "dusuk" if risk < 30 else "orta" if risk < 60 else "yuksek"

    return {
        "risk_skoru": risk,
        "seviye": seviye,
        "seviye_label": {"dusuk": "🟢 Düşük", "orta": "🟡 Orta", "yuksek": "🔴 Yüksek"}[seviye],
        "faktorler": faktorler,
        "istatistik": {
            "aktif_gunler_7": aktif_gunler_7,
            "toplam_dakika_7": toplam_dakika_7,
            "streak": streak,
            "tamamlanmamis_gorev": tamamlanmamis,
        }
    }


# Tüm öğrencilerin risk skorları (öğretmen/admin için)
@router.get("/risk-skor/toplu")
async def get_toplu_risk(current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")

    students = await db.students.find({"arsivli": {"$ne": True}}).to_list(length=None)
    sonuc = []
    for s in students:
        try:
            # Hızlı risk hesaplama
            logs = await db.reading_logs.find({"ogrenci_id": s["id"]}).to_list(length=None)
            from datetime import timedelta
            simdi = datetime.utcnow()
            yedi_gun = simdi - timedelta(days=7)
            son_7 = [l for l in logs if l.get("tarih", "") >= yedi_gun.isoformat()]
            aktif_7 = len(set(l.get("tarih", "")[:10] for l in son_7))
            dakika_7 = sum(l.get("sure_dakika", 0) for l in son_7)
            tarihler = sorted(set(l.get("tarih", "")[:10] for l in logs), reverse=True)
            streak = 0
            for i in range(60):
                gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
                if gun in tarihler: streak += 1
                elif i > 0: break

            risk = 0
            if aktif_7 == 0: risk += 40
            elif aktif_7 < 2: risk += 25
            elif aktif_7 < 4: risk += 10
            if dakika_7 < 12: risk += 20
            if streak == 0: risk += 15
            risk = min(100, risk)
            seviye = "dusuk" if risk < 30 else "orta" if risk < 60 else "yuksek"

            sonuc.append({
                "id": s["id"], "ad": s.get("ad", ""), "soyad": s.get("soyad", ""),
                "sinif": s.get("sinif", ""), "kur": s.get("kur", ""),
                "toplam_xp": s.get("toplam_xp", 0),
                "risk_skoru": risk, "risk_seviye": seviye,
                "streak": streak, "aktif_gunler_7": aktif_7, "dakika_7": dakika_7,
                "ogretmen_id": s.get("ogretmen_id", ""),
            })
        except Exception as e:
            logging.error(f"[risk] öğrenci risk hesabı atlandı (id {s.get('id','?')}): {e}")

    sonuc.sort(key=lambda x: x["risk_skoru"], reverse=True)
    return sonuc
