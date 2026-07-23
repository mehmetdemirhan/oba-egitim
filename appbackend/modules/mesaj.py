"""Mesajlaşma sistemi endpoint'leri (/mesajlar/*) ve modelleri.

Gmail-tarzı: yıldızlama, erteleme (snooze) + hatırlatma bildirimi, yanıtla (aynı thread),
dosya/görsel eki (GridFS 'mesaj_ekleri' bucket'ı — paralel depolama YOK). Bildirim üretimi
modules.bildirim.bildirim_olustur ile (mevcut bildirim sistemi).
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from bson import ObjectId

from core.db import db, mesaj_fs
from core.auth import get_current_user
from core.zaman import iso, simdi, aware
from modules.bildirim import bildirim_olustur

router = APIRouter()

# ── Ek dosya güvenliği: izinli uzantı + MIME (magic byte) + boyut ──
MAX_EK_BOYUT = 15 * 1024 * 1024   # 15 MB
IZINLI_UZANTI = {"jpg", "jpeg", "png", "gif", "pdf", "doc", "docx"}
# Magic byte imzaları (uzantıya değil içeriğe güven)
_IMZALAR = {
    "jpg": [b"\xff\xd8\xff"], "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"], "gif": [b"GIF87a", b"GIF89a"],
    "pdf": [b"%PDF"], "docx": [b"PK\x03\x04"], "doc": [b"\xd0\xcf\x11\xe0"],
}
_GORSEL = {"jpg", "jpeg", "png", "gif"}


def _uzanti(ad: str) -> str:
    return (ad.rsplit(".", 1)[-1] if "." in ad else "").lower()


def _magic_uyuyor(uzanti: str, bas: bytes) -> bool:
    imzalar = _IMZALAR.get(uzanti, [])
    # docx bir zip; doc OLE — bazı .doc'lar farklı olabilir, docx için PK yeterli
    return any(bas.startswith(sig) for sig in imzalar) if imzalar else False


class EkModel(BaseModel):
    dosya_id: str
    ad: str
    tur: str          # "gorsel" | "belge"
    uzanti: str
    boyut: int


class MesajCreate(BaseModel):
    alici_id: str
    alici_tip: str = ""
    icerik: str = ""
    konu: str = ""
    ekler: List[EkModel] = []


class MesajModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gonderen_id: str
    gonderen_ad: str = ""
    gonderen_rol: str = ""
    alici_id: str
    alici_ad: str = ""
    alici_rol: str = ""
    konu: str = ""
    icerik: str = ""
    okundu: bool = False
    arsiv: bool = False
    yildiz: bool = False                      # yıldızlı (ayrı görünüm)
    ertele_zaman: Optional[str] = None        # snooze: bu zamana kadar gelen kutusundan gizli
    ertele_bildirildi: bool = False           # erteleme hatırlatması gönderildi mi
    ekler: list = []                          # [{dosya_id, ad, tur, uzanti, boyut}]
    tarih: str = Field(default_factory=iso)


# ── Ertelenen mesaj hatırlatması: zamanı gelenler için bildirim + tekrar görünür ──
async def _ertelenen_bildirim(user_id: str):
    """Kullanıcının erteleme zamanı GELMİŞ ama henüz hatırlatılmamış mesajları için
    bildirim tetikler (mevcut bildirim sistemi). Zamanlayıcı yok — kullanıcı aktifken
    (mesaj/bildirim çekerken) kontrol edilir. Mesaj zaten gelen kutusunda tekrar üste çıkar."""
    now = simdi()
    try:
        cur = db.mesajlar.find({"alici_id": user_id, "ertele_zaman": {"$ne": None},
                                "ertele_bildirildi": {"$ne": True}})
        async for m in cur:
            ez = m.get("ertele_zaman")
            if not ez:
                continue
            try:
                if aware(ez) <= now:
                    await db.mesajlar.update_one({"id": m["id"]}, {"$set": {"ertele_bildirildi": True}})
                    await bildirim_olustur(user_id, "mesaj_ertelendi",
                                           f"Ertelediğiniz mesaj hatırlatması: {m.get('gonderen_ad','')} — {m.get('konu','') or 'Mesaj'}")
            except Exception:
                continue
    except Exception:
        pass


@router.post("/mesajlar/ek-yukle")
async def ek_yukle(dosya: UploadFile = File(...), current_user=Depends(get_current_user)):
    """Mesaj eki yükle → GridFS. İzinli uzantı + MIME (magic byte) + boyut doğrulanır."""
    ad = dosya.filename or "dosya"
    uz = _uzanti(ad)
    if uz not in IZINLI_UZANTI:
        raise HTTPException(status_code=422, detail=f"İzin verilmeyen dosya türü (.{uz}). İzinli: {', '.join(sorted(IZINLI_UZANTI))}")
    veri = await dosya.read()
    if len(veri) > MAX_EK_BOYUT:
        raise HTTPException(status_code=413, detail=f"Dosya çok büyük (max {MAX_EK_BOYUT // (1024*1024)} MB)")
    if len(veri) == 0:
        raise HTTPException(status_code=422, detail="Boş dosya")
    if not _magic_uyuyor(uz, veri[:16]):
        raise HTTPException(status_code=422, detail="Dosya içeriği uzantısıyla uyuşmuyor (güvenlik reddi)")
    gid = await mesaj_fs.upload_from_stream(ad, veri, metadata={
        "yukleyen_id": current_user["id"], "uzanti": uz,
        "content_type": dosya.content_type or "", "tarih": iso()})
    return {"dosya_id": str(gid), "ad": ad, "uzanti": uz,
            "tur": "gorsel" if uz in _GORSEL else "belge", "boyut": len(veri)}


@router.get("/mesajlar/ek/{dosya_id}")
async def ek_indir(dosya_id: str, current_user=Depends(get_current_user)):
    """Eki indir/görüntüle. Yetki: kullanıcı, bu eke referans veren bir mesajın tarafı olmalı."""
    uid = current_user["id"]
    mesaj = await db.mesajlar.find_one({
        "ekler.dosya_id": dosya_id,
        "$or": [{"gonderen_id": uid}, {"alici_id": uid}],
    })
    if not mesaj:
        raise HTTPException(status_code=403, detail="Bu eke erişim yetkiniz yok")
    ek = next((e for e in (mesaj.get("ekler") or []) if e.get("dosya_id") == dosya_id), {})
    try:
        stream = await mesaj_fs.open_download_stream(ObjectId(dosya_id))
        veri = await stream.read()
    except Exception:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    uz = ek.get("uzanti", "")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
            "pdf": "application/pdf", "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}.get(uz, "application/octet-stream")
    import io
    disp = "inline" if uz in _GORSEL else "attachment"
    return StreamingResponse(io.BytesIO(veri), media_type=mime,
                             headers={"Content-Disposition": f'{disp}; filename="{ek.get("ad", "dosya")}"'})


@router.post("/mesajlar")
async def create_mesaj(mesaj: MesajCreate, current_user=Depends(get_current_user)):
    gonderen_ad = f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip()
    gonderen_rol = current_user.get("role", "")
    alici = await db.users.find_one({"id": mesaj.alici_id})
    alici_ad = ""
    alici_rol = ""
    if alici:
        alici_ad = f"{alici.get('ad', '')} {alici.get('soyad', '')}".strip()
        alici_rol = alici.get("role", "")
    model = MesajModel(
        gonderen_id=current_user["id"], gonderen_ad=gonderen_ad, gonderen_rol=gonderen_rol,
        alici_id=mesaj.alici_id, alici_ad=alici_ad, alici_rol=alici_rol,
        konu=mesaj.konu, icerik=mesaj.icerik,
        ekler=[e.dict() for e in (mesaj.ekler or [])],
    )
    data = model.dict()
    await db.mesajlar.insert_one(data)
    try:
        ek_not = f" ({len(data['ekler'])} ek)" if data.get("ekler") else ""
        await bildirim_olustur(data.get("alici_id"), "mesaj_geldi",
                               f"{data.get('gonderen_ad', '')} size mesaj gönderdi: {data.get('konu', '')}{ek_not}")
    except Exception:
        pass
    data.pop("_id", None)
    return data


@router.get("/mesajlar")
async def get_mesajlar(current_user=Depends(get_current_user)):
    user_id = current_user["id"]
    await _ertelenen_bildirim(user_id)   # zamanı gelen ertelemeler için hatırlatma
    mesajlar = await db.mesajlar.find({
        "$or": [{"gonderen_id": user_id}, {"alici_id": user_id}]
    }).sort("tarih", -1).to_list(length=None)
    for m in mesajlar:
        m.pop("_id", None)
    return mesajlar


@router.put("/mesajlar/{mesaj_id}/okundu")
async def mesaj_okundu(mesaj_id: str, current_user=Depends(get_current_user)):
    await db.mesajlar.update_one({"id": mesaj_id, "alici_id": current_user["id"]}, {"$set": {"okundu": True}})
    return {"ok": True}


class ArsivIstek(BaseModel):
    arsiv: bool = True


@router.put("/mesajlar/{mesaj_id}/arsiv")
async def mesaj_arsivle(mesaj_id: str, istek: ArsivIstek = ArsivIstek(), current_user=Depends(get_current_user)):
    sonuc = await db.mesajlar.update_one(
        {"id": mesaj_id, "alici_id": current_user["id"]}, {"$set": {"arsiv": bool(istek.arsiv)}})
    if sonuc.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı veya arşivleme yetkiniz yok")
    return {"ok": True, "arsiv": bool(istek.arsiv)}


class YildizIstek(BaseModel):
    yildiz: bool = True


@router.put("/mesajlar/{mesaj_id}/yildiz")
async def mesaj_yildiz(mesaj_id: str, istek: YildizIstek = YildizIstek(), current_user=Depends(get_current_user)):
    """Mesajı yıldızla/kaldır. Kullanıcı, mesajın tarafı olmalı (gönderen veya alıcı)."""
    uid = current_user["id"]
    sonuc = await db.mesajlar.update_one(
        {"id": mesaj_id, "$or": [{"gonderen_id": uid}, {"alici_id": uid}]},
        {"$set": {"yildiz": bool(istek.yildiz)}})
    if sonuc.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı")
    return {"ok": True, "yildiz": bool(istek.yildiz)}


class ErteleIstek(BaseModel):
    ertele_zaman: Optional[str] = None   # ISO datetime; None → ertelemeyi iptal et


@router.put("/mesajlar/{mesaj_id}/ertele")
async def mesaj_ertele(mesaj_id: str, istek: ErteleIstek, current_user=Depends(get_current_user)):
    """Mesajı ertele (belirtilen zamana kadar gelen kutusundan gizle); None → iptal.
    Zaman değiştirilebilir (yeni zaman verilir) — hatırlatma bayrağı sıfırlanır."""
    uid = current_user["id"]
    guncelle = {"ertele_zaman": istek.ertele_zaman, "ertele_bildirildi": False}
    sonuc = await db.mesajlar.update_one(
        {"id": mesaj_id, "alici_id": uid}, {"$set": guncelle})
    if sonuc.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı veya erteleme yetkiniz yok")
    return {"ok": True, "ertele_zaman": istek.ertele_zaman}


@router.get("/mesajlar/okunmamis-sayisi")
async def okunmamis_sayisi(current_user=Depends(get_current_user)):
    await _ertelenen_bildirim(current_user["id"])
    sayi = await db.mesajlar.count_documents(
        {"alici_id": current_user["id"], "okundu": False, "arsiv": {"$ne": True}})
    return {"sayi": sayi}
