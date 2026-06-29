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
from core.auth import (
    UserRole, get_current_user, require_role,
    hash_password, verify_password, create_access_token,
)

router = APIRouter()


# ─────────────────────────────────────────────
# AUTH MODELS
# ─────────────────────────────────────────────

class UserCreate(BaseModel):
    ad: str
    soyad: str
    email: str
    password: str
    role: UserRole
    telefon: Optional[str] = None
    linked_id: Optional[str] = None  # teacher_id, student_id or parent's student_id

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

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

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

    user_response = UserResponse(
        id=user["id"],
        ad=user["ad"],
        soyad=user["soyad"],
        email=user["email"],
        role=user["role"],
        telefon=user.get("telefon"),
        linked_id=user.get("linked_id"),
        olusturma_tarihi=datetime.fromisoformat(user["olusturma_tarihi"]) if isinstance(user.get("olusturma_tarihi"), str) else user.get("olusturma_tarihi", datetime.now(timezone.utc)),
        puan=user.get("puan", 0)
    )

    return TokenResponse(access_token=token, user=user_response)

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
        puan=current_user.get("puan", 0)
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
    # NOT: Gerçek uygulamada burada e-posta veya SMS gönderilir
    # Şimdilik geçici şifreyi response'da döndürüyoruz (geliştirme aşaması)
    return {
        "message": f"Geçici şifre oluşturuldu",
        "gecici_sifre": gecici_sifre,
        "kullanici": f"{user['ad']} {user['soyad']}",
        "email": user.get("email", ""),
        "telefon": user.get("telefon", ""),
    }

@router.post("/auth/change-password")
async def change_password(data: ChangePassword, current_user=Depends(get_current_user)):
    if not verify_password(data.old_password, current_user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Mevcut şifre hatalı")

    new_hash = hash_password(data.new_password)
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"password_hash": new_hash}}
    )
    return {"message": "Şifre başarıyla güncellendi"}

# Admin: kullanıcı oluşturma (sadece admin)
@router.post("/auth/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user=Depends(require_role(UserRole.ADMIN))
):
    # Email kontrolü
    existing = await db.users.find_one({"email": user_data.email.lower().strip()})
    if existing:
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")

    user_doc = {
        "id": str(uuid.uuid4()),
        "ad": user_data.ad,
        "soyad": user_data.soyad,
        "email": user_data.email.lower().strip(),
        "telefon": user_data.telefon.strip() if user_data.telefon else None,
        "password_hash": hash_password(user_data.password),
        "role": user_data.role.value,
        "linked_id": user_data.linked_id,
        "olusturma_tarihi": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)

    return UserResponse(
        id=user_doc["id"],
        ad=user_doc["ad"],
        soyad=user_doc["soyad"],
        email=user_doc["email"],
        role=user_doc["role"],
        linked_id=user_doc.get("linked_id"),
        olusturma_tarihi=datetime.now(timezone.utc)
    )

@router.get("/auth/users", response_model=List[UserResponse])
async def list_users(current_user=Depends(require_role(UserRole.ADMIN))):
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
