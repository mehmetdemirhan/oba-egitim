"""Metin öneri kuyruğu + analiz raporu 422 regresyon smoke testi.

Kapsar:
- Öğretmen metin düzeltme + yeni Bloom sorusu önerisi → CANLIYA YAZILMAZ, kuyruğa düşer.
- Admin/koordinatör kuyruğu görür; öğretmen göremez (403); öğrenci öneremez (403).
- Onay → değişiklik havuza uygulanır (Bloom kategori normalize) + öneren XP kazanır
  (metin_duzeltme + soru_ekleme). Aynı öneri ikinci kez karar → 400.
- Reddet → havuza uygulanmaz.
- REGRESYON (madde 4): /diagnostic/rapor, anlama içinde sayısal genel_yuzde (int)
  ile 422 VERMEZ (Dict[str,Any] gevşetmesi).

İzole test DB'sine karşı çalışır. Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_metin_oneri_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_metin_oneri"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = 0
_kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1
        print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1
        print(f"  [KALDI] {mesaj}")


async def run():
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    metin_id = str(uuid.uuid4())
    await server.db.analiz_metinler.insert_one({
        "id": metin_id, "baslik": "Eski Başlık", "icerik": "Eski içerik.",
        "kelime_sayisi": 20, "seviye": 20, "sinif_seviyesi": None, "tur": "hikaye",
        "bolum": "analiz", "zorluk": "kolay", "durum": "havuzda", "kaynak": "elle",
        "sorular": [], "acik_sorular": [
            {"id": "a1", "no": 1, "kategori": "Hatırlama", "kategori_ham": "Hatırlama",
             "soru": "Kim koştu?", "model_cevap": "Ali", "subjektif": False},
        ],
        "olusturma_tarihi": "2026-01-01T00:00:00",
    })

    teacher_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": teacher_id, "role": "teacher", "ad": "Ög", "soyad": "Retmen", "puan": 0})
    H_t = {"Authorization": f"Bearer {create_access_token({'sub': teacher_id})}"}

    admin_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": admin_id, "role": "admin", "ad": "Ad", "soyad": "Min", "puan": 0})
    H_a = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}

    stu_rec = str(uuid.uuid4()); stu_user = str(uuid.uuid4())
    await server.db.students.insert_one({"id": stu_rec, "ad": "Ö", "soyad": "Ğ", "sinif": "4", "kur": "Kur 1", "ogretmen_id": teacher_id})
    await server.db.users.insert_one({"id": stu_user, "role": "student", "linked_id": stu_rec})
    H_s = {"Authorization": f"Bearer {create_access_token({'sub': stu_user})}"}

    async def puan():
        u = await server.db.users.find_one({"id": teacher_id})
        return u.get("puan", 0)

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── 1) Öğretmen öneri gönderir (düzeltme + yeni Bloom sorusu) ──
        oneri_govde = {
            "baslik": "Yeni Başlık",
            "icerik": "Düzeltilmiş içerik.",
            "acik_sorular": [
                {"id": "a1", "no": 1, "kategori": "Hatırlama", "soru": "Kim koştu?"},
                {"no": 2, "kategori": "sentez", "soru": "Farklı bir son yazar mısın?"},
            ],
        }
        r = await ac.post(f"/api/diagnostic/texts/{metin_id}/oneri", json=oneri_govde, headers=H_t)
        check(r.status_code == 200 and r.json().get("durum") == "beklemede", f"öğretmen önerisi kuyruğa düştü ({r.status_code})")
        oneri_id = r.json().get("id")

        # ── 2) Canlı metin DEĞİŞMEDİ ──
        m = await server.db.analiz_metinler.find_one({"id": metin_id})
        check(m["baslik"] == "Eski Başlık" and len(m["acik_sorular"]) == 1, "öneri canlıya YAZILMADI (metin değişmedi)")

        # ── 3) Öğrenci öneremez / öğretmen kuyruğu göremez ──
        r = await ac.post(f"/api/diagnostic/texts/{metin_id}/oneri", json=oneri_govde, headers=H_s)
        check(r.status_code == 403, f"öğrenci öneri gönderemez ({r.status_code})")
        r = await ac.get("/api/diagnostic/oneri-kuyrugu", headers=H_t)
        check(r.status_code == 403, f"öğretmen kuyruğu göremez ({r.status_code})")

        # ── 4) Admin kuyruğu görür ──
        r = await ac.get("/api/diagnostic/oneri-kuyrugu", headers=H_a)
        kuyruk = r.json()
        check(r.status_code == 200 and any(o["id"] == oneri_id for o in kuyruk), "admin kuyrukta öneriyi görüyor")
        o0 = next(o for o in kuyruk if o["id"] == oneri_id)
        check(o0.get("metin_degisti") is True and o0.get("soru_eklendi") is True, "öneri düzeltme+soru olarak etiketli")

        # ── 5) Onayla → uygulanır + normalize + XP ──
        puan_once = await puan()
        r = await ac.post(f"/api/diagnostic/oneri/{oneri_id}/karar", json={"karar": "onayla"}, headers=H_a)
        check(r.status_code == 200 and r.json().get("durum") == "onaylandi", f"öneri onaylandı ({r.status_code})")
        m = await server.db.analiz_metinler.find_one({"id": metin_id})
        check(m["baslik"] == "Yeni Başlık", "onay sonrası başlık güncellendi (canlı)")
        check(len(m["acik_sorular"]) == 2, "yeni Bloom sorusu havuza eklendi")
        yeni_q = next((q for q in m["acik_sorular"] if q.get("no") == 2), None)
        check(yeni_q is not None and yeni_q.get("kategori") == "Yaratma", f"Bloom kategori normalize edildi (sentez→Yaratma: {yeni_q and yeni_q.get('kategori')})")
        puan_sonra = await puan()
        check(puan_sonra - puan_once == 4, f"öneren XP kazandı (+4 = düzeltme+soru, gerçek: {puan_sonra - puan_once})")

        # ── 6) Aynı öneri ikinci kez karar → 400 ──
        r = await ac.post(f"/api/diagnostic/oneri/{oneri_id}/karar", json={"karar": "onayla"}, headers=H_a)
        check(r.status_code == 400, f"sonuçlanmış öneri tekrar kararlanamaz ({r.status_code})")

        # ── 7) Reddet akışı: yeni öneri → reddet → uygulanmaz ──
        r = await ac.post(f"/api/diagnostic/texts/{metin_id}/oneri", json={"baslik": "Reddedilecek"}, headers=H_t)
        red_id = r.json().get("id")
        r = await ac.post(f"/api/diagnostic/oneri/{red_id}/karar", json={"karar": "reddet"}, headers=H_a)
        check(r.status_code == 200 and r.json().get("durum") == "reddedildi", "öneri reddedildi")
        m = await server.db.analiz_metinler.find_one({"id": metin_id})
        check(m["baslik"] == "Yeni Başlık", "reddedilen öneri canlıya uygulanmadı")

        # ── 8) REGRESYON (madde 4): anlama'da sayısal genel_yuzde → 422 VERMEZ ──
        oturum_id = str(uuid.uuid4())
        await server.db.diagnostic_oturumlar.insert_one({
            "id": oturum_id, "ogrenci_id": stu_rec, "ogretmen_id": teacher_id,
            "metin_id": metin_id, "durum": "tamamlandi", "olusturma_tarihi": "2026-01-01T00:00:00"})
        rapor_govde = {
            "oturum_id": oturum_id,
            "anlama": {"cumle_anlama": "iyi", "genel_yuzde": 0},   # int değer — eskiden 422
            "prozodik": {"vurgu": 3, "tonlama": 4},
            "ogretmen_notu": "test",
        }
        r = await ac.post("/api/diagnostic/rapor", json=rapor_govde, headers=H_t)
        check(r.status_code != 422, f"karışık tipli anlama 422 VERMİYOR (status: {r.status_code})")
        check(r.status_code == 200 and r.json().get("id"), f"rapor gerçekten oluştu ({r.status_code})")

    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    await server.client.drop_database(TEST_DB)
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
