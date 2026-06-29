"""Generic AI alt-modül smoke sürücüsü.

Bir AI modülünün TÜM route'larını, Gemini çağrıları stub'lanmış halde tetikler
ve hiçbirinin 500 (sunucu/kod hatası) dönmediğini doğrular. 422/400/403/404 gibi
durumlar "handler çalıştı, validasyon/iş kuralı" sayılır ve kabul edilir.

Amaç: refactor sonrası eksik import / tanımsız isim / NameError gibi kod
regresyonlarını yakalamak (diagnostic'teki timezone/List/os tipi hatalar).

    cd appbackend
    .venv/Scripts/python.exe tests/ai_smoke.py <modul_adi>
"""
import asyncio
import os
import sys
import uuid

MODUL = sys.argv[1]
TEST_DB = f"oba_test_{MODUL}_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("GEMINI_API_KEY", "test-key")  # call_claude'un mock/erken-çıkış yolu yerine stub'ı kullanması için
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = 0
_kalan = 0
_fail_detay = []


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1
    else:
        _kalan += 1
        _fail_detay.append(mesaj)


async def _stub_gemini(prompt, system="", max_tokens=4000):
    return '{"ok": true, "sonuc": "stub", "kelimeler": [], "sorular": []}'


async def _stub_call_claude(system_prompt, user_message, model="sonnet", max_tokens=2000):
    return {"text": '{"ok": true}', "parsed": {"ok": True}, "tokens": 0, "maliyet": 0, "error": None}


def fill_path(path, sid):
    out = []
    for seg in path.split("/"):
        if seg.startswith("{") and seg.endswith("}"):
            name = seg[1:-1]
            if "ogrenci" in name or "kullanici" in name or "user" in name:
                out.append(sid)
            else:
                out.append("dummy-" + name)
        else:
            out.append(seg)
    return "/".join(out)


BODY = {
    "ogrenci_id": None, "kullanici_id": None, "metin": "Bir varmış bir yokmuş kısa metin.",
    "icerik": "Bir varmış bir yokmuş kısa metin.", "kitap_id": "k1", "kitap_adi": "Kitap",
    "sinif": 4, "sinif_seviyesi": "4", "kur": "1", "cevap": "x", "mesaj": "merhaba",
    "hedef": "x", "secim": "x", "seviye": 1, "bolum": 1, "yukleme_id": "u1",
    "karakter": "elif", "soru": "x", "metin_id": "m1", "wpm": 100, "dogruluk": 90,
    "zorluk": 3, "tur": "hikaye", "baslik": "T", "konu": "doğa", "skor": 80,
    "sure_saniye": 60, "cevaplar": [], "secenekler": [], "hedef_kelimeler": [],
}


async def run():
    import importlib
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    # AI çağrılarını stub'la (hem core.ai hem modülün bağladığı isimler)
    import core.ai as core_ai
    core_ai._gemini_call = _stub_gemini
    core_ai.call_claude = _stub_call_claude
    mod = importlib.import_module(f"modules.{MODUL}")
    if hasattr(mod, "_gemini_call"):
        mod._gemini_call = _stub_gemini
    if hasattr(mod, "call_claude"):
        mod.call_claude = _stub_call_claude

    await server.client.drop_database(TEST_DB)
    sid = str(uuid.uuid4())
    aid = str(uuid.uuid4())
    await server.db.users.insert_one({"id": aid, "ad": "Admin", "soyad": "T", "role": "admin", "puan": 0})
    await server.db.students.insert_one({"id": sid, "ad": "Ali", "soyad": "V", "sinif": "4", "kur": "1", "toplam_xp": 50})
    H = {"Authorization": f"Bearer {create_access_token({'sub': aid})}"}

    body = dict(BODY); body["ogrenci_id"] = sid; body["kullanici_id"] = sid

    routes = [r for r in mod.router.routes]
    print(f"  modül {MODUL}: {len(routes)} route")
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as ac:
        for r in routes:
            for method in sorted(r.methods):
                if method in ("HEAD", "OPTIONS"):
                    continue
                url = "/api" + fill_path(r.path, sid)
                try:
                    if method == "GET":
                        resp = await ac.get(url, headers=H)
                    elif method == "DELETE":
                        resp = await ac.delete(url, headers=H)
                    elif method == "PUT":
                        resp = await ac.put(url, json=body, headers=H)
                    else:
                        resp = await ac.post(url, json=body, headers=H)
                    ok = resp.status_code != 500
                    check(ok, f"{method} {r.path} → {resp.status_code}" + ("" if ok else f" :: {resp.text[:200]}"))
                except Exception as e:
                    check(False, f"{method} {r.path} → EXCEPTION {type(e).__name__}: {str(e)[:200]}")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    for d in _fail_detay:
        print("  [500/HATA]", d)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} route 500'süz çalıştı")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
