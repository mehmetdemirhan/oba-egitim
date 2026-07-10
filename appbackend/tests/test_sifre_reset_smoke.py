"""Şifre sıfırlama güvenlik smoke testi (izole test DB).

Doğrular:
  * SMTP kapalı → "yöneticinize başvurun" mesajı, token üretilmez.
  * SMTP açık → forgot NÖTR yanıt; hesap ŞİFRESİ DEĞİŞMEZ; token yalnız e-postada
    (DB'de hash). Var olmayan hesapta da AYNI nötr yanıt (enumeration yok).
  * reset: geçerli token → şifre değişir + token tükenir; kullanılmış/geçersiz/
    süresi dolmuş token → 400.
  * Rate limit: aynı IP'den fazla forgot → 429.

Çalıştırma:
  cd appbackend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_sifre_reset_smoke.py
"""
import asyncio
import os
import re
import sys

os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = "oba_test_sifre_reset"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

from fastapi import HTTPException  # noqa: E402
from core.db import db  # noqa: E402
from core.auth import hash_password, verify_password  # noqa: E402
import modules.auth_api as auth  # noqa: E402
from datetime import datetime, timezone, timedelta  # noqa: E402

_gecti = _kaldi = 0


def kontrol(k, ad):
    global _gecti, _kaldi
    if k:
        _gecti += 1; print(f"  [GECTI] {ad}")
    else:
        _kaldi += 1; print(f"  [KALDI] {ad}")


class FakeReq:
    def __init__(self, ip="1.2.3.4", xff=""):
        self.headers = {"x-forwarded-for": xff} if xff else {}
        self.client = type("C", (), {"host": ip})()


# send_email'i yakalayıcıyla değiştir (gerçek gönderim yok; token'ı linkten al)
_captured = {"to": None, "token": None}
def _fake_send(to, subject, html, text=""):
    _captured["to"] = to
    m = re.search(r"token=([A-Za-z0-9_\-]+)", html)
    _captured["token"] = m.group(1) if m else None
    return True
auth.send_email = _fake_send


async def _reset_db():
    await db.client.drop_database("oba_test_sifre_reset")


async def _kullanici(email, sifre="EskiSifre1"):
    import uuid
    doc = {"id": str(uuid.uuid4()), "ad": "Test", "soyad": "K", "email": email,
           "password_hash": hash_password(sifre), "role": "teacher"}
    await db.users.insert_one(doc)
    return doc


async def main():
    global _kaldi
    await _reset_db()

    # ── SMTP KAPALI ──
    print("\n== SMTP kapalı ==")
    auth.SMTP_ENABLED = False
    auth._rate_buckets.clear()
    u = await _kullanici("kapali@test.com")
    r = await auth.forgot_password(FakeReq(), {"email_or_phone": "kapali@test.com"})
    kontrol(r.get("smtp_kapali") is True, "SMTP kapalı bayrağı")
    kontrol("yönetici" in r.get("message", "").lower(), "yöneticinize başvurun mesajı")
    kontrol(await db.sifre_reset_tokenlari.count_documents({}) == 0, "token üretilmedi")
    u2 = await db.users.find_one({"id": u["id"]})
    kontrol(verify_password("EskiSifre1", u2["password_hash"]), "şifre DEĞİŞMEDİ (SMTP kapalı)")

    # ── SMTP AÇIK ──
    print("\n== SMTP açık ==")
    auth.SMTP_ENABLED = True
    auth._rate_buckets.clear()

    # var olan hesap → nötr, token üretilir, şifre değişmez
    r = await auth.forgot_password(FakeReq(), {"email_or_phone": "kapali@test.com"})
    kontrol("smtp_kapali" not in r, "açıkken smtp_kapali bayrağı yok")
    kontrol(_captured["token"] is not None, "token e-postaya kondu (link)")
    kontrol(await db.sifre_reset_tokenlari.count_documents({"user_id": u["id"]}) == 1, "DB'de 1 token (hash)")
    tok_doc = await db.sifre_reset_tokenlari.find_one({"user_id": u["id"]})
    kontrol(tok_doc.get("token_hash") and _captured["token"] not in str(tok_doc), "DB'de plaintext token YOK (yalnız hash)")
    u3 = await db.users.find_one({"id": u["id"]})
    kontrol(verify_password("EskiSifre1", u3["password_hash"]), "forgot sonrası şifre HÂLÂ DEĞİŞMEDİ")

    # var olmayan hesap → AYNI nötr yanıt, yeni token yok (enumeration yok)
    once = await db.sifre_reset_tokenlari.count_documents({})
    r_yok = await auth.forgot_password(FakeReq(), {"email_or_phone": "yok@test.com"})
    kontrol(r_yok.get("message") == r.get("message"), "var olmayan hesap AYNI nötr mesaj")
    kontrol(await db.sifre_reset_tokenlari.count_documents({}) == once, "var olmayan hesap için token yok")

    # reset: geçerli token → şifre değişir
    token = _captured["token"]
    rr = await auth.reset_password(FakeReq(), {"token": token, "yeni_sifre": "YeniSifre9"})
    kontrol("güncellendi" in rr.get("message", ""), "reset başarı mesajı")
    u4 = await db.users.find_one({"id": u["id"]})
    kontrol(verify_password("YeniSifre9", u4["password_hash"]), "şifre YENİ ile değişti")
    kontrol(not verify_password("EskiSifre1", u4["password_hash"]), "eski şifre artık geçersiz")

    # aynı token tekrar → 400 (tek kullanım)
    try:
        await auth.reset_password(FakeReq(), {"token": token, "yeni_sifre": "Baska123"})
        kontrol(False, "kullanılmış token reddedilmeli")
    except HTTPException as e:
        kontrol(e.status_code == 400, "kullanılmış token → 400")

    # geçersiz token → 400
    try:
        await auth.reset_password(FakeReq(), {"token": "gecersiz-token-xyz", "yeni_sifre": "Baska123"})
        kontrol(False, "geçersiz token reddedilmeli")
    except HTTPException as e:
        kontrol(e.status_code == 400, "geçersiz token → 400")

    # süresi dolmuş token → 400
    auth._rate_buckets.clear()
    _captured["token"] = None
    await auth.forgot_password(FakeReq(ip="5.5.5.5"), {"email_or_phone": "kapali@test.com"})
    exp_token = _captured["token"]
    exp_hash = auth._token_hash(exp_token)
    gecmis = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    await db.sifre_reset_tokenlari.update_one({"token_hash": exp_hash}, {"$set": {"gecerlilik": gecmis}})
    try:
        await auth.reset_password(FakeReq(ip="5.5.5.5"), {"token": exp_token, "yeni_sifre": "Baska123"})
        kontrol(False, "süresi dolmuş token reddedilmeli")
    except HTTPException as e:
        kontrol(e.status_code == 400, "süresi dolmuş token → 400")

    # ── RATE LIMIT (IP) ──
    print("\n== Rate limit ==")
    auth._rate_buckets.clear()
    limit_asildi = False
    for i in range(7):
        try:
            await auth.forgot_password(FakeReq(ip="9.9.9.9"), {"email_or_phone": f"rl{i}@test.com"})
        except HTTPException as e:
            if e.status_code == 429:
                limit_asildi = True
                break
    kontrol(limit_asildi, "aynı IP'den aşırı forgot → 429")

    await _reset_db()
    print(f"\n=== SONUÇ: {_gecti} geçti, {_kaldi} kaldı ===")
    return 0 if _kaldi == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(_loop.run_until_complete(main()))
    except Exception as ex:
        print(f"[KALDI] istisna: {ex}")
        try:
            _loop.run_until_complete(_reset_db())
        except Exception:
            pass
        sys.exit(1)
