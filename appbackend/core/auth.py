"""Kimlik doğrulama: roller, parola hashleme, JWT ve FastAPI bağımlılıkları.

server.py'daki orijinal tanımların birebir aynısıdır. `create_default_admin`
başlangıç görevi olduğu için server.py'da kalmaya devam eder.
"""
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt

from core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from core.db import db


# ── Enums ──
class TeacherLevel(str, Enum):
    YENI = "yeni"
    UZMAN = "uzman"


class UserRole(str, Enum):
    ADMIN = "admin"
    COORDINATOR = "coordinator"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"


# ── Parola hashleme & güvenlik şeması ──
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ── Refresh token (45 günlük kalıcı oturum, DB'de saklı & iptal edilebilir) ──
def _refresh_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def refresh_token_olustur(user_id: str) -> str:
    """Opak refresh token üretir, hash'ini DB'ye yazar, düz metni döner (yalnız istemciye)."""
    token = secrets.token_urlsafe(48)
    await db.refresh_tokens.insert_one({
        "token_hash": _refresh_hash(token),
        "user_id": user_id,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).isoformat(),
        "olusturma_tarihi": datetime.now(timezone.utc).isoformat(),
    })
    return token


async def refresh_token_dogrula(token: str) -> Optional[str]:
    """Geçerli & süresi dolmamışsa user_id döner; süresi geçmişse siler ve None döner."""
    if not token:
        return None
    doc = await db.refresh_tokens.find_one({"token_hash": _refresh_hash(token)})
    if not doc:
        return None
    if doc.get("expires_at", "") < datetime.now(timezone.utc).isoformat():
        await db.refresh_tokens.delete_one({"_id": doc["_id"]})
        return None
    return doc.get("user_id")


async def refresh_token_sil(token: str) -> bool:
    if not token:
        return False
    res = await db.refresh_tokens.delete_one({"token_hash": _refresh_hash(token)})
    return res.deleted_count > 0


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Geçersiz token")
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
    return user


def require_role(*roles: UserRole):
    async def checker(current_user=Depends(get_current_user)):
        if current_user.get("role") not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için yetkiniz yok"
            )
        return current_user
    return checker
