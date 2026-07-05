"""Kimlik doğrulama endpoint'leri (/auth/*) ve istek/yanıt modelleri.

server.py'dan birebir taşındı. Yollar ve yanıt formatları değişmedi; route'lar
modül-yerel `router` üzerine kaydedilir ve api_router.include_router ile dahil edilir.
NOT: `create_default_admin` startup hook'u `app`'e bağlı olduğu için server.py'de kaldı.
"""
import uuid
import random
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel

from core.db import db
from core.config import SIFRE_SIFIRLAMA_DEBUG
from core.auth import (
    UserRole, get_current_user, require_role,
    hash_password, verify_password, create_access_token,
    refresh_token_olustur, refresh_token_dogrula, refresh_token_sil,
)

router = APIRouter()


# ─────────────────────────────────────────────
# AUTH MODELS
# ─────────────────────────────────────────────

class UserCreate(BaseModel):
    ad: str
    soyad: str
    email: str
    password: Optional[str] = None  # boş bırakılırsa güçlü geçici şifre otomatik üretilir
    role: UserRole
    telefon: Optional[str] = None
    linked_id: Optional[str] = None  # teacher_id, student_id or parent's student_id

class UserUpdate(BaseModel):
    ad: Optional[str] = None
    soyad: Optional[str] = None
    email: Optional[str] = None
    telefon: Optional[str] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None  # verilirse şifre değiştirilir (yeni şifre belirleme)

class UserLogin(BaseModel):
    email_or_phone: Optional[str] = None
    email: Optional[str] = None  # eski frontend uyumluluğu
    password: str

class UserResponse(BaseModel):
    id: str
    ad: str
    soyad: str
    email: str
    role: UserRole
    telefon: Optional[str] = None
    linked_id: Optional[str] = None
    olusturma_tarihi: datetime
    puan: int = 0
    sifre_degistirme_zorunlu: bool = False

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    must_change_password: bool = False
    refresh_token: Optional[str] = None

class ChangePassword(BaseModel):
    old_password: str
    new_password: str


# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────

@router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    girdi = (credentials.email_or_phone or credentials.email or "").lower().strip()
    if not girdi:
        raise HTTPException(status_code=400, detail="E-posta veya telefon gerekli")
    # Email veya telefon ile kullanıcı bul
    user = await db.users.find_one({"email": girdi})
    if not user:
        user = await db.users.find_one({"telefon": girdi})
    if not user or not verify_password(credentials.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta/telefon veya şifre hatalı"
        )

    token = create_access_token({"sub": user["id"], "role": user["role"]})

    zorunlu = bool(user.get("sifre_degistirme_zorunlu", False))
    user_response = UserResponse(
        id=user["id"],
        ad=user["ad"],
        soyad=user["soyad"],
        email=user["email"],
        role=user["role"],
        telefon=user.get("telefon"),
        linked_id=user.get("linked_id"),
        olusturma_tarihi=datetime.fromisoformat(user["olusturma_tarihi"]) if isinstance(user.get("olusturma_tarihi"), str) else user.get("olusturma_tarihi", datetime.now(timezone.utc)),
        puan=user.get("puan", 0),
        sifre_degistirme_zorunlu=zorunlu,
    )

    refresh = await refresh_token_olustur(user["id"])
    return TokenResponse(access_token=token, user=user_response,
                         must_change_password=zorunlu, refresh_token=refresh)


@router.post("/auth/refresh")
async def refresh_access(payload: dict = Body(...)):
    """Refresh token ile yeni kısa ömürlü access token üretir (kalıcı oturum)."""
    user_id = await refresh_token_dogrula(payload.get("refresh_token", ""))
    if not user_id:
        raise HTTPException(status_code=401, detail="Geçersiz veya süresi dolmuş oturum")
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
    token = create_access_token({"sub": user["id"], "role": user["role"]})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/auth/logout")
async def logout(payload: dict = Body(default={})):
    """Refresh token'ı iptal eder (bu cihaz için oturumu kapatır)."""
    await refresh_token_sil(payload.get("refresh_token", ""))
    return {"ok": True}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        ad=current_user["ad"],
        soyad=current_user["soyad"],
        email=current_user["email"],
        role=current_user["role"],
        telefon=current_user.get("telefon"),
        linked_id=current_user.get("linked_id"),
        olusturma_tarihi=datetime.fromisoformat(current_user["olusturma_tarihi"]) if isinstance(current_user.get("olusturma_tarihi"), str) else current_user.get("olusturma_tarihi", datetime.now(timezone.utc)),
        puan=current_user.get("puan", 0),
        sifre_degistirme_zorunlu=bool(current_user.get("sifre_degistirme_zorunlu", False)),
    )

@router.post("/auth/forgot-password")
async def forgot_password(data: dict = Body(...)):
    email_or_phone = data.get("email_or_phone", "").lower().strip()
    if not email_or_phone:
        raise HTTPException(status_code=400, detail="E-posta veya telefon giriniz")
    user = await db.users.find_one({"email": email_or_phone})
    if not user:
        user = await db.users.find_one({"telefon": email_or_phone})
    if not user:
        raise HTTPException(status_code=404, detail="Bu bilgilerle kayıtlı kullanıcı bulunamadı")
    # 6 haneli geçici şifre oluştur
    gecici_sifre = str(random.randint(100000, 999999))
    new_hash = hash_password(gecici_sifre)
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": new_hash}})
    # NOT: Gerçek uygulamada burada e-posta veya SMS gönderilir.
    # Güvenlik: geçici şifre yalnızca lokal geliştirmede (SIFRE_SIFIRLAMA_DEBUG=1)
    # yanıtta döner; prod varsayılanında SIZDIRILMAZ.
    yanit = {
        "message": "Geçici şifre oluşturuldu",
        "kullanici": f"{user['ad']} {user['soyad']}",
        "email": user.get("email", ""),
        "telefon": user.get("telefon", ""),
    }
    if SIFRE_SIFIRLAMA_DEBUG:
        yanit["gecici_sifre"] = gecici_sifre
    return yanit

@router.post("/auth/change-password")
async def change_password(data: ChangePassword, current_user=Depends(get_current_user)):
    if not verify_password(data.old_password, current_user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Mevcut şifre hatalı")

    new_hash = hash_password(data.new_password)
    # Şifre değişince zorunlu-değiştirme bayrağı düşer (ilk giriş akışını kapatır)
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"password_hash": new_hash, "sifre_degistirme_zorunlu": False}}
    )
    return {"message": "Şifre başarıyla güncellendi"}

# Admin/Koordinatör: kullanıcı oluşturma
@router.post("/auth/users")
async def create_user(
    user_data: UserCreate,
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))
):
    from core.hesap import gecici_sifre_uret, ogretmen_kaydi_olustur

    # Koordinatör kullanıcı oluşturabilir AMA admin/yönetici hesabı açamaz
    # (yetki yükseltme engeli). Sadece admin, admin hesabı oluşturabilir.
    if current_user.get("role") == "coordinator" and user_data.role == UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Koordinatör yönetici (admin) hesabı oluşturamaz")

    # Email kontrolü
    existing = await db.users.find_one({"email": user_data.email.lower().strip()})
    if existing:
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")

    # Şifre: admin bir şey girmediyse güçlü geçici şifre üret (tek kullanımlık)
    uretildi = not (user_data.password and user_data.password.strip())
    gecici_sifre = (user_data.password or "").strip() or gecici_sifre_uret()

    user_doc = {
        "id": str(uuid.uuid4()),
        "ad": user_data.ad,
        "soyad": user_data.soyad,
        "email": user_data.email.lower().strip(),
        "telefon": user_data.telefon.strip() if user_data.telefon else None,
        "password_hash": hash_password(gecici_sifre),
        "role": user_data.role.value,
        "linked_id": user_data.linked_id or None,
        "sifre_degistirme_zorunlu": True,  # ilk girişte zorunlu değiştirme
        "olusturma_tarihi": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)

    # role teacher/coordinator/admin ise otomatik teachers kaydı + köprü
    teacher_id = await ogretmen_kaydi_olustur(user_doc)
    if teacher_id:
        user_doc["linked_id"] = teacher_id

    return {
        "id": user_doc["id"],
        "ad": user_doc["ad"],
        "soyad": user_doc["soyad"],
        "email": user_doc["email"],
        "role": user_doc["role"],
        "telefon": user_doc.get("telefon"),
        "linked_id": user_doc.get("linked_id"),
        "olusturma_tarihi": user_doc["olusturma_tarihi"],
        "sifre_degistirme_zorunlu": True,
        "teacher_id": teacher_id,
        # Geçici şifre: SMS/e-posta olmadığı için admin'e bir kereliğine gösterilir
        "gecici_sifre": gecici_sifre,
        "gecici_sifre_uretildi": uretildi,
    }

@router.put("/auth/users/{user_id}")
async def update_user(user_id: str, data: UserUpdate,
                      current_user=Depends(require_role(UserRole.ADMIN))):
    """Admin kullanıcı düzenleme: ad/soyad/email/telefon/rol + opsiyonel yeni şifre."""
    from core.hesap import ogretmen_kaydi_olustur
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    upd = {}
    if data.ad is not None:
        upd["ad"] = data.ad
    if data.soyad is not None:
        upd["soyad"] = data.soyad
    if data.telefon is not None:
        upd["telefon"] = data.telefon.strip() or None
    if data.email is not None:
        yeni_email = data.email.lower().strip()
        if yeni_email and yeni_email != user.get("email"):
            if await db.users.find_one({"email": yeni_email, "id": {"$ne": user_id}}):
                raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")
            upd["email"] = yeni_email
    if data.role is not None:
        upd["role"] = data.role.value
    if data.password and data.password.strip():
        upd["password_hash"] = hash_password(data.password.strip())
        # Admin yeni şifre belirledi → kullanıcı ilk girişte değiştirsin (tek kullanımlık mantığı)
        upd["sifre_degistirme_zorunlu"] = True
    if not upd:
        raise HTTPException(status_code=400, detail="Güncellenecek veri yok")
    await db.users.update_one({"id": user_id}, {"$set": upd})
    # Rol teacher/coordinator/admin'e döndüyse teachers köprüsünü garanti et
    guncel = await db.users.find_one({"id": user_id})
    await ogretmen_kaydi_olustur(guncel)
    return {"ok": True, "id": user_id}


@router.get("/auth/users", response_model=List[UserResponse])
async def list_users(current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR, UserRole.TEACHER))):
    # Öğretmen de listeye erişebilir: mesajlaşmada alıcı (yönetici/koordinatör/öğretmen)
    # seçimi için gerekli. Salt-okunur; oluşturma/silme hâlâ admin/koordinatöre özel.
    users = await db.users.find().to_list(length=None)
    result = []
    for u in users:
        result.append(UserResponse(
            id=u["id"],
            ad=u["ad"],
            soyad=u["soyad"],
            email=u["email"],
            role=u["role"],
            telefon=u.get("telefon"),
            linked_id=u.get("linked_id"),
            olusturma_tarihi=datetime.fromisoformat(u["olusturma_tarihi"]) if isinstance(u.get("olusturma_tarihi"), str) else datetime.now(timezone.utc),
            puan=u.get("puan", 0)
        ))
    return result

@router.delete("/auth/users/{user_id}")
async def delete_user(user_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı silemezsiniz")
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return {"message": "Kullanıcı silindi"}
