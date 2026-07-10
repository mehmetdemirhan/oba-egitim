"""Kimlik doğrulama endpoint'leri (/auth/*) ve istek/yanıt modelleri.

server.py'dan birebir taşındı. Yollar ve yanıt formatları değişmedi; route'lar
modül-yerel `router` üzerine kaydedilir ve api_router.include_router ile dahil edilir.
NOT: `create_default_admin` startup hook'u `app`'e bağlı olduğu için server.py'de kaldı.
"""
import uuid
import random
import hashlib
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from pydantic import BaseModel

from core.db import db
from core.config import SMTP_ENABLED, FRONTEND_URL, SIFRE_RESET_TOKEN_DK
from core.mail import send_email
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

# ── ŞİFRE SIFIRLAMA (e-posta + tek kullanımlık token) ─────────────────────
# Güvenlik ilkeleri:
#  * Geçici şifre/reset bilgisi ASLA yanıtta dönmez; şifre kimlik doğrulanmadan
#    DEĞİŞTİRİLMEZ (yalnız geçerli token'lı reset ekranı değiştirir).
#  * Yanıt her durumda NÖTR — hesap var/yok sızmaz (enumeration yok).
#  * SMTP tanımlı değilse akış kapalı; kullanıcı yöneticisine yönlendirilir.
#  * Rate limit (IP + hesap girdisi) — kaba kuvvet/spam sınırı.

_rate_buckets: dict = {}  # in-memory sliding-window (tek-process; restart'ta sıfırlanır)
NOTR_MESAJ = ("Eğer bu hesap sistemde kayıtlıysa, şifre sıfırlama bağlantısı "
              "e-posta adresine gönderildi. Lütfen e-postanı kontrol et.")
SMTP_KAPALI_MESAJ = ("Şifre sıfırlama e-postası şu an etkin değil. Lütfen şifre "
                     "sıfırlama için yöneticinize başvurun.")


def _rate_ok(key: str, max_n: int, window_sn: int) -> bool:
    now = time.time()
    arr = [t for t in _rate_buckets.get(key, []) if now - t < window_sn]
    if len(arr) >= max_n:
        _rate_buckets[key] = arr
        return False
    arr.append(now)
    _rate_buckets[key] = arr
    return True


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "bilinmiyor"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _reset_email_html(ad: str, link: str) -> str:
    return f"""\
<div style="font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:520px;margin:0 auto;color:#1f2937">
  <h2 style="color:#4f46e5">OBA Eğitim — Şifre Sıfırlama</h2>
  <p>Merhaba {ad},</p>
  <p>Hesabın için şifre sıfırlama talebi aldık. Aşağıdaki butona tıklayarak yeni şifreni belirleyebilirsin:</p>
  <p style="text-align:center;margin:28px 0">
    <a href="{link}" style="background:#4f46e5;color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:600;display:inline-block">Şifremi Sıfırla</a>
  </p>
  <p style="font-size:13px;color:#6b7280">Bu bağlantı {SIFRE_RESET_TOKEN_DK} dakika geçerlidir ve yalnızca bir kez kullanılabilir.</p>
  <p style="font-size:13px;color:#6b7280">Bu talebi sen yapmadıysan bu e-postayı yok sayabilirsin; şifren değişmez.</p>
</div>"""


@router.post("/auth/forgot-password")
async def forgot_password(request: Request, data: dict = Body(...)):
    email_or_phone = (data.get("email_or_phone") or data.get("email") or "").lower().strip()
    ip = _client_ip(request)
    # Rate limit: IP başına 5/15dk
    if not _rate_ok(f"forgot:ip:{ip}", 5, 900):
        raise HTTPException(status_code=429, detail="Çok fazla deneme. Lütfen biraz sonra tekrar deneyin.")
    if not email_or_phone:
        raise HTTPException(status_code=400, detail="E-posta veya telefon giriniz")
    # Hesap girdisi başına 3/15dk — aşılırsa yine NÖTR yanıt (sızdırma yok)
    if not _rate_ok(f"forgot:acc:{email_or_phone}", 3, 900):
        return {"message": NOTR_MESAJ}

    # SMTP kapalıysa akış kapalı — herkese aynı mesaj (hesap varlığı sızmaz)
    if not SMTP_ENABLED:
        return {"message": SMTP_KAPALI_MESAJ, "smtp_kapali": True}

    # Kullanıcıyı bul; YOKSA da aynı nötr yanıt. Şifre ÜRETİLMEZ/DEĞİŞMEZ.
    user = await db.users.find_one({"email": email_or_phone})
    if not user:
        user = await db.users.find_one({"telefon": email_or_phone})
    hedef_email = (user or {}).get("email", "")
    if user and hedef_email:
        raw = secrets.token_urlsafe(32)  # yüksek entropili; e-postada plaintext, DB'de yalnız hash
        simdi = datetime.now(timezone.utc)
        await db.sifre_reset_tokenlari.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "token_hash": _token_hash(raw),
            "olusturma": simdi.isoformat(),
            "gecerlilik": (simdi + timedelta(minutes=SIFRE_RESET_TOKEN_DK)).isoformat(),
            "kullanildi": False,
            "ip": ip,
        })
        link = f"{FRONTEND_URL}/sifre-sifirla?token={raw}"
        ad = f"{user.get('ad', '')} {user.get('soyad', '')}".strip() or "Merhaba"
        send_email(
            hedef_email, "OBA Eğitim — Şifre Sıfırlama",
            _reset_email_html(ad, link),
            text=f"Şifreni sıfırlamak için: {link}  (Bağlantı {SIFRE_RESET_TOKEN_DK} dk geçerlidir.)",
        )
        # send_email False dönse bile (SMTP hatası) yanıt NÖTR kalır.
    return {"message": NOTR_MESAJ}


@router.get("/auth/reset-password/gecerli")
async def reset_token_gecerli(token: str = ""):
    """Reset ekranı, formu göstermeden önce token'ın geçerliliğini sorar."""
    if not token:
        return {"gecerli": False}
    kayit = await db.sifre_reset_tokenlari.find_one({"token_hash": _token_hash(token), "kullanildi": False})
    if not kayit:
        return {"gecerli": False}
    gecerli = datetime.now(timezone.utc) <= datetime.fromisoformat(kayit["gecerlilik"])
    return {"gecerli": gecerli}


@router.post("/auth/reset-password")
async def reset_password(request: Request, data: dict = Body(...)):
    ip = _client_ip(request)
    if not _rate_ok(f"reset:ip:{ip}", 10, 900):
        raise HTTPException(status_code=429, detail="Çok fazla deneme. Lütfen biraz sonra tekrar deneyin.")
    token = (data.get("token") or "").strip()
    yeni = data.get("yeni_sifre") or data.get("new_password") or ""
    if not token:
        raise HTTPException(status_code=400, detail="Geçersiz bağlantı.")
    if len(yeni) < 6:
        raise HTTPException(status_code=400, detail="Şifre en az 6 karakter olmalı.")
    kayit = await db.sifre_reset_tokenlari.find_one({"token_hash": _token_hash(token), "kullanildi": False})
    if not kayit:
        raise HTTPException(status_code=400, detail="Sıfırlama bağlantısı geçersiz veya kullanılmış.")
    if datetime.now(timezone.utc) > datetime.fromisoformat(kayit["gecerlilik"]):
        raise HTTPException(status_code=400, detail="Sıfırlama bağlantısının süresi dolmuş.")
    # Şifreyi güncelle, token'ı tüket, kullanıcının diğer aktif token'larını iptal et.
    await db.users.update_one(
        {"id": kayit["user_id"]},
        {"$set": {"password_hash": hash_password(yeni), "sifre_degistirme_zorunlu": False}},
    )
    await db.sifre_reset_tokenlari.update_many(
        {"user_id": kayit["user_id"], "kullanildi": False}, {"$set": {"kullanildi": True}}
    )
    return {"message": "Şifreniz güncellendi. Yeni şifrenizle giriş yapabilirsiniz."}

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
