"""Muhasebe ayarları (vergi oranı + kur ücretleri) — rol/yetki smoke testi.

Doğrular: admin + accountant /muhasebe/ayarlar okur ve vergi oranı / kur ücretlerini
düzenler; öğretmen bu uçlara erişemez (403); doğrulama (oran 0-100, sayısal);
kur ücreti normalizasyonu (<=0 türler düşer); değişiklikler audit'e (islem_log,
modul=muhasebe) düşer; kaydedilen vergi oranı get_vergi_orani'ye yansır.
İzole DB (oba_test_muhasebe_ayarlar). Gerçek DB'ye dokunmaz.
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_muhasebe_ayarlar"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1; print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1; print(f"  [KALDI] {mesaj}")


async def run():
    import uuid
    import server
    from core.auth import create_access_token
    from core.sistem import get_vergi_orani, get_kur_ucreti
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    admin_id, acc_id, teacher_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yön", "soyad": "Etici", "role": "admin"},
        {"id": acc_id, "ad": "Muh", "soyad": "Asebe", "role": "accountant"},
        {"id": teacher_id, "ad": "Öğ", "soyad": "Retmen", "role": "teacher"},
    ])
    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_acc = {"Authorization": f"Bearer {create_access_token({'sub': acc_id})}"}
    H_teacher = {"Authorization": f"Bearer {create_access_token({'sub': teacher_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── GET: admin + accountant okur, öğretmen 403 ──
        r = await ac.get("/api/muhasebe/ayarlar", headers=H_acc)
        check(r.status_code == 200 and "vergi_ayarlari" in r.json() and "kur_ucretleri" in r.json(),
              f"accountant /muhasebe/ayarlar okudu ({r.status_code})")
        check((await ac.get("/api/muhasebe/ayarlar", headers=H_admin)).status_code == 200, "admin de okuyabiliyor")
        check((await ac.get("/api/muhasebe/ayarlar", headers=H_teacher)).status_code == 403,
              "öğretmen /muhasebe/ayarlar okuyamaz (403)")

        # ── Vergi oranı: accountant günceller ──
        r = await ac.put("/api/muhasebe/ayarlar/vergi", headers=H_acc, json={"vergi_orani": 18})
        check(r.status_code == 200 and r.json().get("vergi_orani") == 18, f"accountant vergi oranını 18 yaptı ({r.status_code})")
        v = await server.db.sistem_ayarlari.find_one({"tip": "vergi_ayarlari"})
        check(v and v.get("degerler", {}).get("vergi_orani") == 18, "vergi oranı DB'ye yazıldı")
        check(await get_vergi_orani() == 18, "get_vergi_orani yeni oranı yansıtıyor")

        # Öğretmen vergi güncelleyemez (403)
        check((await ac.put("/api/muhasebe/ayarlar/vergi", headers=H_teacher, json={"vergi_orani": 5})).status_code == 403,
              "öğretmen vergi oranı değiştiremez (403)")
        # Doğrulama: aralık dışı + sayısal olmayan → 422
        check((await ac.put("/api/muhasebe/ayarlar/vergi", headers=H_acc, json={"vergi_orani": 150})).status_code == 422,
              "vergi oranı >100 reddedildi (422)")
        check((await ac.put("/api/muhasebe/ayarlar/vergi", headers=H_acc, json={"vergi_orani": "abc"})).status_code == 422,
              "vergi oranı sayısal değilse reddedildi (422)")

        # ── Kur ücretleri: accountant günceller (genel + tür) ──
        r = await ac.put("/api/muhasebe/ayarlar/kur-ucretleri", headers=H_acc,
                         json={"degerler": {"genel": 1200, "turler": {"Hızlı Okuma": 1800, "Bedava": 0}}})
        check(r.status_code == 200, f"accountant kur ücretlerini güncelledi ({r.status_code})")
        k = await server.db.sistem_ayarlari.find_one({"tip": "kur_ucretleri"})
        d = k.get("degerler", {}) if k else {}
        check(d.get("genel") == 1200, "genel kur ücreti yazıldı (1200)")
        check(d.get("turler", {}).get("Hızlı Okuma") == 1800, "eğitim türü bazlı ücret yazıldı (1800)")
        check("Bedava" not in d.get("turler", {}), "0/negatif tür ücreti normalizasyonda düştü")
        check(await get_kur_ucreti("Hızlı Okuma") == 1800, "get_kur_ucreti tür ücretini yansıtıyor")
        check(await get_kur_ucreti("Tanımsız") == 1200, "tanımsız tür genel ücreti alıyor")

        # Öğretmen kur ücreti güncelleyemez (403)
        check((await ac.put("/api/muhasebe/ayarlar/kur-ucretleri", headers=H_teacher,
                            json={"degerler": {"genel": 1}})).status_code == 403,
              "öğretmen kur ücreti değiştiremez (403)")
        # Doğrulama: degerler yoksa 422
        check((await ac.put("/api/muhasebe/ayarlar/kur-ucretleri", headers=H_acc, json={})).status_code == 422,
              "degerler eksikse reddedildi (422)")

        # ── Admin de düzenleyebilir ──
        check((await ac.put("/api/muhasebe/ayarlar/vergi", headers=H_admin, json={"vergi_orani": 20})).status_code == 200,
              "admin de vergi oranını düzenleyebiliyor")

        # ── Audit: islem_log (modul=muhasebe) ──
        av = await server.db.islem_log.count_documents({"modul": "muhasebe", "islem": "ayar_vergi"})
        ak = await server.db.islem_log.count_documents({"modul": "muhasebe", "islem": "ayar_kur_ucreti"})
        check(av >= 2, f"vergi ayar değişikliği audit'e düştü ({av})")
        check(ak >= 1, f"kur ücreti ayar değişikliği audit'e düştü ({ak})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
