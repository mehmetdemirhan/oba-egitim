"""FAZ 1 rozet smoke testi.

Doğrulananlar:
  - Ölü AI rozetleri (ai_*) tanımlardan kaldırıldı
  - Tüm rozet tanımlarında tek 'odul_puan' alanı var (puan/xp yok)
  - kazanilan_rozetler unique index (kullanici_id, rozet_kodu) duplike engelliyor
  - POST /rozetler/kontrol yeni rozet verince 'rozet_kazandi' bildirimi tetikliyor
  - kontrol idempotent (ikinci çağrı duplike üretmiyor)
  - core.rozet_helpers.kullanici_toplam_odul_puan doğru topluyor

    cd appbackend
    .venv/Scripts/python.exe tests/test_rozet_faz1_smoke.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime

TEST_DB = "oba_test_rozet_faz1_smoke"
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
    from core.db import ensure_indexes
    from core.sistem import get_ogretmen_rozetleri, get_ogrenci_rozetleri
    from core.rozet_helpers import kullanici_toplam_odul_puan, rozet_odul_puan
    from pymongo.errors import DuplicateKeyError
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    now = datetime.utcnow()

    # ── 1. Tanım temizliği ──
    ogr = await get_ogretmen_rozetleri()
    ogn = await get_ogrenci_rozetleri()
    tum = ogr + ogn
    olu = [r for r in ogr if r["kod"] in ("ai_ilk", "ai_5", "ai_20", "ai_50")]
    check(len(olu) == 0, f"ölü AI rozeti tanımı yok (gelen {len(olu)})")

    # ── 2. Alan adı tutarlılığı ──
    puanli = [r for r in tum if "odul_puan" in r]
    check(len(puanli) == len(tum), f"tüm tanımlarda odul_puan var ({len(puanli)}/{len(tum)})")
    eski_alan = [r for r in tum if "puan" in r or "xp" in r]
    check(len(eski_alan) == 0, f"eski puan/xp alanı kalmadı (gelen {len(eski_alan)})")
    check(all(rozet_odul_puan(r) > 0 for r in tum), "her rozetin ödül puanı > 0")

    # ── 3. Unique index ──
    await ensure_indexes()
    su = str(uuid.uuid4())
    s1 = str(uuid.uuid4())
    await server.db.kazanilan_rozetler.insert_one(
        {"id": str(uuid.uuid4()), "kullanici_id": su, "rozet_kodu": "test_kod", "kazanma_tarihi": now.isoformat()})
    dup_hata = False
    try:
        await server.db.kazanilan_rozetler.insert_one(
            {"id": str(uuid.uuid4()), "kullanici_id": su, "rozet_kodu": "test_kod", "kazanma_tarihi": now.isoformat()})
    except DuplicateKeyError:
        dup_hata = True
    check(dup_hata, "aynı (kullanici_id, rozet_kodu) ikinci kez eklenemedi (unique index çalışıyor)")
    await server.db.kazanilan_rozetler.delete_many({"kullanici_id": su})

    # ── 4. Öğrenci senaryosu: rozet kazanımı + bildirim ──
    await server.db.users.insert_one({"id": su, "ad": "Ali", "soyad": "Yılmaz", "role": "student", "linked_id": s1})
    await server.db.students.insert_one({"id": s1, "ad": "Ali", "soyad": "Yılmaz", "toplam_xp": 0})
    # 120 dk okuma + kitap → okuma_ilk, okuma_100, kitap_1 gibi rozetler
    await server.db.reading_logs.insert_one(
        {"id": str(uuid.uuid4()), "ogrenci_id": s1, "tarih": now.isoformat(), "sure_dakika": 120, "kitap_adi": "Küçük Prens"})

    HS = {"Authorization": f"Bearer {create_access_token({'sub': su})}"}
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/rozetler/kontrol", headers=HS)
        check(r.status_code == 200, f"kontrol 200 (status={r.status_code})")
        d = r.json()
        yeni = d.get("yeni_rozetler", [])
        check(len(yeni) >= 2, f"en az 2 yeni rozet kazanıldı (gelen {len(yeni)})")
        kodlar = {y["rozet_kodu"] for y in yeni}
        check("okuma_ilk" in kodlar and "okuma_100" in kodlar, f"okuma_ilk + okuma_100 kazanıldı (gelen {kodlar})")

        # Bildirim tetiklendi mi?
        bildirimler = await server.db.bildirimler.find({"alici_id": su, "tur": "rozet_kazandi"}).to_list(length=None)
        check(len(bildirimler) == len(yeni), f"her yeni rozet için 1 bildirim ({len(bildirimler)} bildirim / {len(yeni)} rozet)")
        check(all("Yeni rozet" in b["icerik"] for b in bildirimler), "bildirim içeriği doğru formatta")

        # ── 5. Idempotent: ikinci kontrol yeni rozet üretmemeli ──
        r2 = await ac.post("/api/rozetler/kontrol", headers=HS)
        check(r2.status_code == 200, f"ikinci kontrol 200 (status={r2.status_code})")
        check(len(r2.json().get("yeni_rozetler", [])) == 0, "ikinci kontrol 0 yeni rozet (idempotent)")
        toplam_kayit = await server.db.kazanilan_rozetler.count_documents({"kullanici_id": su})
        check(toplam_kayit == len(yeni), f"duplike kayıt yok ({toplam_kayit} kayıt = {len(yeni)} rozet)")

    # ── 6. Helper: toplam ödül puanı ──
    beklenen = 0
    ogn_map = {r["kod"]: rozet_odul_puan(r) for r in ogn}
    async for kr in server.db.kazanilan_rozetler.find({"kullanici_id": su}):
        beklenen += ogn_map.get(kr["rozet_kodu"], 0)
    hesaplanan = await kullanici_toplam_odul_puan(su, "student")
    check(hesaplanan == beklenen and hesaplanan > 0, f"kullanici_toplam_odul_puan doğru (gelen {hesaplanan}, beklenen {beklenen})")

    await server.client.drop_database(TEST_DB)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
