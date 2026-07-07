"""Metin havuzu katkı akışları smoke testi.

Kapsar (Akıcı Okuma içe aktarım özelliklerinin backend'i):
- gorsel_prompt HİÇBİR role dönmez (öğretmen + öğrenci).
- Öğrenciye MCQ doğru cevabı ve iç bayraklar (guven/kontrol) sızmaz.
- Kelime sayısı (seviye) aralık filtresi: min_kelime/max_kelime.
- MCQ doğru cevap düzeltme: İLK düzeltmede +XP, tekrarında ödül YOK,
  kontrol_gerekli düşer, kaynak "manuel" olur.
- Görsel ekleme: İLK eklemede +XP, tekrarında ödül YOK; GET binary döner;
  listede gorsel_var=True, gorsel base64 taşınmaz.

İzole test DB'sine karşı çalışır (oba_test_metin_katki). Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_metin_havuzu_katki_smoke.py
"""
import asyncio
import base64
import os
import sys
import uuid

TEST_DB = "oba_test_metin_katki"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = 0
_kalan = 0

# 1x1 şeffaf PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


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

    # ── Havuz metni (akıcı okuma tarzı: sorular + gorsel_prompt) ──
    metin_id = str(uuid.uuid4())
    soru1 = "s1-" + uuid.uuid4().hex[:8]
    soru2 = "s2-" + uuid.uuid4().hex[:8]
    await server.db.analiz_metinler.insert_one({
        "id": metin_id, "baslik": "Sarı Köpek", "icerik": "Ali koştu top attı.",
        "kelime_sayisi": 40, "seviye": 40, "sinif_seviyesi": None, "tur": "akici_okuma",
        "zorluk": "kolay", "durum": "havuzda", "kaynak": "akici_okuma",
        "gorsel_prompt": "GIZLI PROMPT — asla görünmemeli", "gorsel": None,
        "gorsel_ilk_ekleyen_id": None,
        "sorular": [
            {"id": soru1, "soru": "Ne yaptı?", "secenekler": {"A": "koştu", "B": "uyudu", "C": "yedi", "D": "gitti"},
             "dogru_cevap": "B", "dogru_cevap_kaynak": "otomatik", "guven": "low",
             "kontrol_gerekli": True, "ilk_duzelten_id": None, "son_duzelten_id": None, "son_duzelten_tarih": None},
            {"id": soru2, "soru": "Kim?", "secenekler": {"A": "Ali", "B": "Ayşe", "C": "Can", "D": "Ece"},
             "dogru_cevap": "A", "dogru_cevap_kaynak": "otomatik", "guven": "high",
             "kontrol_gerekli": False, "ilk_duzelten_id": None, "son_duzelten_id": None, "son_duzelten_tarih": None},
        ],
        "acik_sorular": [
            {"id": "a1", "no": 1, "kategori": "Analiz", "kategori_ham": "Analiz",
             "soru": "Ali neden koştu?", "model_cevap": "Topu yakalamak için.", "subjektif": False},
            {"id": "a2", "no": 2, "kategori": "Uygulama", "kategori_ham": "Uygulama",
             "soru": "Sen olsan ne yapardın?", "model_cevap": "su, top", "subjektif": True},
        ],
        "olusturma_tarihi": "2026-01-01T00:00:00",
    })
    # Farklı seviye (kelime sayısı) metinler — aralık filtresi için
    for wc in (35, 120, 300):
        await server.db.analiz_metinler.insert_one({
            "id": str(uuid.uuid4()), "baslik": f"M{wc}", "icerik": "x " * wc,
            "kelime_sayisi": wc, "durum": "havuzda", "tur": "akici_okuma",
            "olusturma_tarihi": "2026-01-01T00:00:00"})

    teacher_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": teacher_id, "role": "teacher", "ad": "Ög", "soyad": "Retmen", "puan": 0})
    H_t = {"Authorization": f"Bearer {create_access_token({'sub': teacher_id})}"}

    stu_rec = str(uuid.uuid4()); stu_user = str(uuid.uuid4())
    await server.db.students.insert_one({"id": stu_rec, "ad": "Ö", "soyad": "Ğ", "sinif": "4", "kur": "Kur 1"})
    await server.db.users.insert_one({"id": stu_user, "role": "student", "linked_id": stu_rec})
    H_s = {"Authorization": f"Bearer {create_access_token({'sub': stu_user})}"}

    async def puan():
        u = await server.db.users.find_one({"id": teacher_id})
        return u.get("puan", 0)

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── 1) gorsel_prompt sızmıyor (öğretmen) ──
        r = await ac.get("/api/diagnostic/texts", headers=H_t)
        metinler = r.json()
        hedef = next((m for m in metinler if m["id"] == metin_id), None)
        check(hedef is not None, "öğretmen havuzdaki metni görüyor")
        check("gorsel_prompt" not in hedef, "gorsel_prompt öğretmene DÖNMÜYOR")
        check(len(hedef.get("sorular", [])) == 2 and hedef["sorular"][0].get("dogru_cevap") == "B",
              "öğretmen sorularda doğru cevabı görüyor")

        # ── 2) Öğrenciye doğru cevap + iç bayraklar sızmıyor ──
        r = await ac.get("/api/diagnostic/texts", headers=H_s)
        hedef_s = next((m for m in r.json() if m["id"] == metin_id), None)
        s0 = hedef_s["sorular"][0]
        check("gorsel_prompt" not in hedef_s, "gorsel_prompt öğrenciye DÖNMÜYOR")
        check("dogru_cevap" not in s0 and "guven" not in s0 and "kontrol_gerekli" not in s0,
              "öğrenciye doğru cevap/iç bayraklar sızmıyor")
        check("secenekler" in s0 and "soru" in s0, "öğrenci soru metnini/şıkları görüyor")
        # Açık uçlu: öğrenciye model_cevap SIZMAZ ama soru/kategori görünür
        a_s = hedef_s.get("acik_sorular", [])
        check(len(a_s) == 2 and all("model_cevap" not in q for q in a_s),
              "öğrenciye açık uçlu model_cevap sızmıyor")
        check(a_s[0].get("kategori") == "Analiz" and a_s[0].get("soru"),
              "öğrenci açık uçlu soru + Bloom kategorisini görüyor")

        # ── 2b) Öğretmen açık uçlu model cevabı + subjektif bayrağını görüyor ──
        a_t = hedef.get("acik_sorular", [])
        check(a_t[0].get("model_cevap") == "Topu yakalamak için." and a_t[0].get("subjektif") is False,
              "öğretmen model cevabı görüyor (objektif soru)")
        check(a_t[1].get("subjektif") is True, "subjektif soru bayraklı (öğretmen)")

        # ── 3) Kelime sayısı (seviye) aralık filtresi ──
        r = await ac.get("/api/diagnostic/texts?min_kelime=100&max_kelime=200", headers=H_t)
        wcs = [m["kelime_sayisi"] for m in r.json()]
        check(all(100 <= w <= 200 for w in wcs) and 120 in wcs and 40 not in wcs,
              f"aralık filtresi 100-200 çalışıyor ({sorted(wcs)})")

        # ── 3b) Sınıf filtresi null-sinif havuz metnini GİZLEMEZ ──
        # Sınıf 5 etiketli bir metin ekle; sinif=4 ile filtrele → sınıf-5 gelmez ama
        # null-sinif havuz metni (metin_id) yine gelir.
        s5_id = str(uuid.uuid4())
        await server.db.analiz_metinler.insert_one({
            "id": s5_id, "baslik": "Sınıf5 Metni", "icerik": "beş", "kelime_sayisi": 40,
            "sinif_seviyesi": "5", "durum": "havuzda", "tur": "hikaye",
            "olusturma_tarihi": "2026-01-01T00:00:00"})
        r = await ac.get("/api/diagnostic/texts?sinif_seviyesi=4", headers=H_t)
        idler = {m["id"] for m in r.json()}
        check(metin_id in idler, "sınıf=4 filtresinde null-sinif havuz metni GÖRÜNÜYOR")
        check(s5_id not in idler, "sınıf=4 filtresinde sınıf-5 etiketli metin gizli")

        # ── 4) MCQ doğru cevap düzeltme + İLK ödül ──
        p0 = await puan()
        r = await ac.patch(f"/api/diagnostic/texts/{metin_id}/soru/{soru1}", headers=H_t, json={"dogru_cevap": "A"})
        check(r.status_code == 200, f"cevap düzeltme 200 (status={r.status_code})")
        j = r.json()
        check(j["soru"]["dogru_cevap"] == "A" and j["soru"]["dogru_cevap_kaynak"] == "manuel",
              "doğru cevap A + kaynak manuel")
        check(j["soru"]["kontrol_gerekli"] is False, "kontrol_gerekli bayrağı düştü")
        check(j["ilk_defa"] is True and j["odul"] == 2, f"ilk düzeltme +2 XP (odul={j['odul']})")
        check(await puan() == p0 + 2, "öğretmen puanı +2 arttı")

        # ── 5) Aynı soruyu tekrar düzelt → ödül YOK ──
        p1 = await puan()
        r = await ac.patch(f"/api/diagnostic/texts/{metin_id}/soru/{soru1}", headers=H_t, json={"dogru_cevap": "C"})
        check(r.json()["odul"] == 0 and await puan() == p1, "tekrar düzeltme ödül vermiyor (anti-farm)")

        # ── 6) Geçersiz şık reddediliyor ──
        r = await ac.patch(f"/api/diagnostic/texts/{metin_id}/soru/{soru1}", headers=H_t, json={"dogru_cevap": "Z"})
        check(r.status_code == 400, "geçersiz şık 400")

        # ── 7) Öğrenci düzeltemez ──
        r = await ac.patch(f"/api/diagnostic/texts/{metin_id}/soru/{soru2}", headers=H_s, json={"dogru_cevap": "B"})
        check(r.status_code == 403, "öğrenci cevap düzeltemez (403)")

        # ── 8) Görsel ekleme + İLK ödül ──
        p2 = await puan()
        r = await ac.post(f"/api/diagnostic/texts/{metin_id}/gorsel", headers=H_t,
                          files={"dosya": ("g.png", _PNG, "image/png")})
        check(r.status_code == 200 and r.json()["ilk_defa"] and r.json()["odul"] == 2, "görsel ilk ekleme +2 XP")
        check(await puan() == p2 + 2, "görsel için öğretmen puanı +2")

        # GET binary döner
        r = await ac.get(f"/api/diagnostic/texts/{metin_id}/gorsel", headers=H_s)
        check(r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"),
              "görsel binary olarak dönüyor")
        # Listede gorsel_var True, base64 taşınmıyor
        r = await ac.get("/api/diagnostic/texts", headers=H_t)
        hedef = next((m for m in r.json() if m["id"] == metin_id), None)
        check(hedef.get("gorsel_var") is True and "gorsel" not in hedef, "listede gorsel_var=True, base64 taşınmıyor")

        # ── 9) Görsel değiştir → ödül YOK ──
        p3 = await puan()
        r = await ac.post(f"/api/diagnostic/texts/{metin_id}/gorsel", headers=H_t,
                          files={"dosya": ("g2.png", _PNG, "image/png")})
        check(r.json()["odul"] == 0 and await puan() == p3, "görsel değiştirme ödül vermiyor")

        # ── 10) Geçersiz tip reddi ──
        r = await ac.post(f"/api/diagnostic/texts/{metin_id}/gorsel", headers=H_t,
                          files={"dosya": ("x.txt", b"merhaba", "text/plain")})
        check(r.status_code == 400, "PNG/JPG olmayan dosya 400")

        # ── 11) PUT tam düzenleme ──
        # Not: soru1'in ilk_duzelten_id'si (4. adımda set edildi) korunmalı.
        db_metin = await server.db.analiz_metinler.find_one({"id": metin_id})
        ilk_duzelten_onceki = db_metin["sorular"][0].get("ilk_duzelten_id")
        r = await ac.put(f"/api/diagnostic/texts/{metin_id}", headers=H_t, json={
            "baslik": "Yeni Başlık", "icerik": "bir iki üç dört beş", "tur": "hikaye", "zorluk": "zor",
            "sinif_seviyesi": None,
            "sorular": [
                {"id": soru1, "soru": "Değişti mi?", "secenekler": {"A": "koştu", "B": "uçtu", "C": "yedi", "D": "gitti"}, "dogru_cevap": "D"},
                {"id": None, "soru": "Yeni MCQ", "secenekler": {"A": "x", "B": "y", "C": "z", "D": "t"}, "dogru_cevap": "A"},
            ],
            "acik_sorular": [
                {"id": "a1", "no": 1, "kategori": "Bilgi/Hatırlama", "soru": "Ne oldu?", "model_cevap": "Bir şey.", "subjektif": False},
                {"id": None, "no": 2, "kategori": "Analiz", "soru": "Neden?", "model_cevap": "(farklı görüşler kabul edilir)", "subjektif": True},
            ],
        })
        check(r.status_code == 200, f"PUT 200 (status={r.status_code})")
        pj = r.json()
        check(pj["baslik"] == "Yeni Başlık" and pj["kelime_sayisi"] == 5 and pj.get("seviye") == 5,
              "başlık + kelime_sayisi(=seviye) güncellendi")
        check(pj["zorluk"] == "zor" and pj["tur"] == "hikaye", "zorluk/tür güncellendi")
        db_metin = await server.db.analiz_metinler.find_one({"id": metin_id})
        s1 = next(s for s in db_metin["sorular"] if s["id"] == soru1)
        check(s1["soru"] == "Değişti mi?" and s1["dogru_cevap"] == "D" and s1["secenekler"]["B"] == "uçtu",
              "MCQ soru metni/şık/doğru cevap güncellendi")
        check(s1.get("ilk_duzelten_id") == ilk_duzelten_onceki and ilk_duzelten_onceki is not None,
              "XP anti-farm meta (ilk_duzelten_id) KORUNDU")
        check(len(db_metin["sorular"]) == 2 and any(s["soru"] == "Yeni MCQ" for s in db_metin["sorular"]),
              "yeni MCQ eklendi + id atandı")
        check(len(db_metin["acik_sorular"]) == 2, "açık uçlu liste güncellendi")
        check(db_metin["acik_sorular"][0]["kategori"] == "Hatırlama", "açık uçlu Bloom normalize edildi (PUT)")
        check(db_metin["acik_sorular"][1]["subjektif"] is True, "açık uçlu subjektif bayrağı korundu (PUT)")
        # Görsel PUT'tan etkilenmedi
        check(db_metin.get("gorsel") is not None and db_metin.get("gorsel_prompt") == "GIZLI PROMPT — asla görünmemeli",
              "PUT görsel/gorsel_prompt'a dokunmadı")

        # ── 12) Öğrenci PUT edemez ──
        r = await ac.put(f"/api/diagnostic/texts/{metin_id}", headers=H_s, json={"baslik": "hack"})
        check(r.status_code == 403, "öğrenci PUT edemez (403)")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
