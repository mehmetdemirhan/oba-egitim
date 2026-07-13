"""Görev atama sistemi endpoint'leri (/gorevler/*) ve modelleri.

İki yönlü: Yönetici → Öğretmen, Öğretmen → Öğrenci.
server.py'dan birebir taşındı. Yollar ve davranış değişmedi.
Görev atandığında modules.bildirim.bildirim_gorev_atandi ile bildirim üretilir.
"""
import uuid
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import db
from core.auth import get_current_user
from core.rozet_motor import rozet_tetikle
from modules.bildirim import bildirim_gorev_atandi

router = APIRouter()


class GorevCreate(BaseModel):
    hedef_id: str
    hedef_tip: str  # "ogretmen" veya "ogrenci"
    baslik: str
    aciklama: str = ""
    tur: str = "ozel"  # ozel, film, kitap, makale, hizmetici, egzersiz
    icerik_id: Optional[str] = None
    son_tarih: Optional[str] = None
    makale_link: Optional[str] = None
    kitap_yazar: Optional[str] = None
    kitap_isbn: Optional[str] = None
    kitap_link: Optional[str] = None
    kitap_kapak: Optional[str] = None
    film_link: Optional[str] = None

class GorevModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hedef_id: str
    hedef_tip: str
    hedef_ad: str = ""
    baslik: str
    aciklama: str = ""
    tur: str = "ozel"
    icerik_id: Optional[str] = None
    son_tarih: Optional[str] = None
    atayan_id: str = ""
    atayan_ad: str = ""
    atayan_rol: str = ""
    durum: str = "bekliyor"
    tamamlama_tarihi: Optional[str] = None
    tamamlama_notu: Optional[str] = None
    makale_link: Optional[str] = None
    kitap_yazar: Optional[str] = None
    kitap_isbn: Optional[str] = None
    kitap_link: Optional[str] = None
    kitap_kapak: Optional[str] = None
    film_link: Optional[str] = None
    olusturma_tarihi: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


@router.post("/gorevler")
async def create_gorev(gorev: GorevCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if gorev.hedef_tip == "ogretmen" and role not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Öğretmenlere görev yalnızca yönetici/koordinatör atayabilir")
    if gorev.hedef_tip == "ogrenci" and role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Öğrencilere görev yalnızca öğretmen/yönetici atayabilir")

    hedef_ad = ""
    if gorev.hedef_tip == "ogretmen":
        user = await db.users.find_one({"id": gorev.hedef_id})
        if user:
            hedef_ad = f"{user.get('ad', '')} {user.get('soyad', '')}".strip()
        else:
            raise HTTPException(status_code=404, detail="Hedef öğretmen bulunamadı")
    elif gorev.hedef_tip == "ogrenci":
        student = await db.students.find_one({"id": gorev.hedef_id})
        if student:
            hedef_ad = f"{student.get('ad', '')} {student.get('soyad', '')}".strip()
        else:
            raise HTTPException(status_code=404, detail="Hedef öğrenci bulunamadı")

    model = GorevModel(
        **gorev.dict(),
        hedef_ad=hedef_ad,
        atayan_id=current_user["id"],
        atayan_ad=f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip(),
        atayan_rol=role,
    )
    data = model.dict()
    await db.gorevler.insert_one(data)
    data.pop("_id", None)  # insert_one'ın eklediği ObjectId'i response'tan çıkar (JSON serialize edilemez)
    # Bildirim gönder
    try: await bildirim_gorev_atandi(data.get("hedef_id"), data.get("baslik", ""), data.get("atayan_ad", ""))
    except: pass
    return data


@router.post("/gorevler/toplu")
async def create_toplu_gorev(payload: dict, current_user=Depends(get_current_user)):
    hedef_idler = payload.get("hedef_idler", [])
    hedef_tip = payload.get("hedef_tip", "")
    gorev_bilgi = payload.get("gorev", {})
    role = current_user.get("role", "")

    if hedef_tip == "ogretmen" and role not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    if hedef_tip == "ogrenci" and role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")

    olusturulan = []
    for hid in hedef_idler:
        hedef_ad = ""
        if hedef_tip == "ogretmen":
            u = await db.users.find_one({"id": hid})
            hedef_ad = f"{u.get('ad', '')} {u.get('soyad', '')}".strip() if u else ""
        elif hedef_tip == "ogrenci":
            s = await db.students.find_one({"id": hid})
            hedef_ad = f"{s.get('ad', '')} {s.get('soyad', '')}".strip() if s else ""

        model = GorevModel(
            hedef_id=hid, hedef_tip=hedef_tip, hedef_ad=hedef_ad,
            baslik=gorev_bilgi.get("baslik", ""), aciklama=gorev_bilgi.get("aciklama", ""),
            tur=gorev_bilgi.get("tur", "ozel"), icerik_id=gorev_bilgi.get("icerik_id"),
            son_tarih=gorev_bilgi.get("son_tarih"),
            makale_link=gorev_bilgi.get("makale_link"), kitap_yazar=gorev_bilgi.get("kitap_yazar"),
            kitap_isbn=gorev_bilgi.get("kitap_isbn"), kitap_link=gorev_bilgi.get("kitap_link"),
            kitap_kapak=gorev_bilgi.get("kitap_kapak"), film_link=gorev_bilgi.get("film_link"),
            atayan_id=current_user["id"],
            atayan_ad=f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip(),
            atayan_rol=role,
        )
        data = model.dict()
        await db.gorevler.insert_one(data)
        data.pop("_id", None)  # insert_one'ın eklediği ObjectId'i response'tan çıkar (JSON serialize edilemez)
        olusturulan.append(data)

    return {"olusturulan": len(olusturulan), "gorevler": olusturulan}


@router.get("/gorevler")
async def get_gorevler(
    hedef_tip: Optional[str] = None,
    hedef_id: Optional[str] = None,
    durum: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    role = current_user.get("role", "")
    user_id = current_user.get("id", "")
    filtre = {}
    if hedef_tip:
        filtre["hedef_tip"] = hedef_tip
    if hedef_id:
        filtre["hedef_id"] = hedef_id
    if durum:
        filtre["durum"] = durum

    if role == "teacher":
        items_atanan = await db.gorevler.find({"hedef_id": user_id, **({k: v for k, v in filtre.items() if k != "hedef_id"})}).sort("olusturma_tarihi", -1).to_list(length=None)
        items_atadigi = await db.gorevler.find({"atayan_id": user_id, **({k: v for k, v in filtre.items() if k != "hedef_id"})}).sort("olusturma_tarihi", -1).to_list(length=None)
        seen = set()
        items = []
        for i in items_atanan + items_atadigi:
            if i["id"] not in seen:
                seen.add(i["id"])
                items.append(i)
    else:
        items = await db.gorevler.find(filtre).sort("olusturma_tarihi", -1).to_list(length=None)

    for item in items:
        item.pop("_id", None)
    return items


@router.put("/gorevler/{gorev_id}/durum")
async def update_gorev_durum(gorev_id: str, payload: dict, current_user=Depends(get_current_user)):
    gorev = await db.gorevler.find_one({"id": gorev_id})
    if not gorev:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")

    yeni_durum = payload.get("durum", "")
    update = {"durum": yeni_durum}
    if yeni_durum == "tamamlandi":
        update["tamamlama_tarihi"] = datetime.utcnow().isoformat()
        if payload.get("not"):
            update["tamamlama_notu"] = payload["not"]

    await db.gorevler.update_one({"id": gorev_id}, {"$set": update})

    # Event: görev tamamlanınca hem hedef öğrencinin (gorev_tamamlama) hem atayan
    # öğretmenin (gorev_20) rozetlerini değerlendir (fire-and-forget)
    if yeni_durum == "tamamlandi":
        hedef_user = await db.users.find_one(
            {"$or": [{"id": gorev.get("hedef_id")}, {"linked_id": gorev.get("hedef_id")}]})
        if hedef_user:
            asyncio.create_task(rozet_tetikle(hedef_user["id"], "gorev_tamam"))
        if gorev.get("atayan_id"):
            asyncio.create_task(rozet_tetikle(gorev["atayan_id"], "gorev_tamam"))

    return {"durum": yeni_durum}


@router.delete("/gorevler/{gorev_id}")
async def delete_gorev(gorev_id: str, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    gorev = await db.gorevler.find_one({"id": gorev_id})
    if not gorev:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    if gorev.get("atayan_id") != current_user["id"] and role not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Yalnızca atayan veya yönetici silebilir")
    await db.gorevler.delete_one({"id": gorev_id})
    return {"message": "Görev silindi"}


@router.get("/gorevler/istatistik")
async def get_gorev_istatistik(current_user=Depends(get_current_user)):
    tum = await db.gorevler.find().to_list(length=None)
    og = [g for g in tum if g.get("hedef_tip") == "ogretmen"]
    os = [g for g in tum if g.get("hedef_tip") == "ogrenci"]
    def h(l):
        return {"toplam": len(l), "bekliyor": len([g for g in l if g.get("durum") == "bekliyor"]),
                "devam_ediyor": len([g for g in l if g.get("durum") == "devam_ediyor"]),
                "tamamlandi": len([g for g in l if g.get("durum") == "tamamlandi"]),
                "suresi_doldu": len([g for g in l if g.get("durum") == "suresi_doldu"])}
    return {"ogretmen": h(og), "ogrenci": h(os)}
