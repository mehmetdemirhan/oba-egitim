"""Muhasebe listesi — tamamlanmış+ödenmiş kur satırının gizlenmesi + kur özeti.

Doğrular: bir öğrenci kur atlayıp önceki kuru TAMAMEN ödeyince o kur satırı ana
/muhasebe/kisiler listesinden düşer; ama /muhasebe/ogrenci/{id}/kur-ozet TÜM kurları
(gizli dahil) + toplamları döndürür. Önceki kurda BORÇ kalırsa satır listede kalır.
İzole DB (oba_test_kur_gizle). Gerçek DB'ye dokunmaz.
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_kur_gizle"
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


def _satirlar(kisiler_json, kisi_id):
    return [o for o in kisiler_json.get("ogrenciler", []) if o.get("kisi_id") == kisi_id]


async def run():
    import uuid
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    acc_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": acc_id, "ad": "Muh", "soyad": "Asebe", "role": "accountant"})
    H_acc = {"Authorization": f"Bearer {create_access_token({'sub': acc_id})}"}

    sid = str(uuid.uuid4())
    await server.db.students.insert_one({
        "id": sid, "ad": "Ali", "soyad": "Veli", "veli_ad": "Ayşe", "veli_soyad": "Veli",
        "veli_telefon": "5551112233", "kur": "2",
        "yapilmasi_gereken_odeme": 2500.0, "yapilan_odeme": 1000.0})  # FIFO: kur1(1000) tam ödendi
    # kur1: geçilmiş (tamamlandi), kur2: aktif (acik)
    await server.db.kur_ucretleri.insert_many([
        {"id": "k1", "ogrenci_id": sid, "kur_adi": "1", "tutar": 1000.0, "durum": "tamamlandi", "tarih": "2026-01-01T00:00:00"},
        {"id": "k2", "ogrenci_id": sid, "kur_adi": "2", "tutar": 1500.0, "durum": "acik", "tarih": "2026-06-01T00:00:00"},
    ])

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── A) kur1 tamamlanmış + tam ödenmiş → ana listede GİZLİ ──
        r = await ac.get("/api/muhasebe/kisiler", headers=H_acc)
        rows = _satirlar(r.json(), sid)
        kurlar_gorunen = sorted(x.get("kur") for x in rows)
        check(kurlar_gorunen == ["2"], f"ana listede yalnız aktif kur (2) görünüyor: {kurlar_gorunen}")
        check(all(x.get("kur") != "1" for x in rows), "tamamlanmış+ödenmiş kur (1) listede GİZLİ")

        # ── kur-ozet: TÜM kurlar (gizli dahil) + toplam ──
        r = await ac.get(f"/api/muhasebe/ogrenci/{sid}/kur-ozet", headers=H_acc)
        oz = r.json()
        check(r.status_code == 200 and len(oz.get("kurlar", [])) == 2, "kur-ozet 2 kuru da döndürüyor (gizli dahil)")
        k1 = next((c for c in oz["kurlar"] if c["kur"] == "1"), None)
        k2 = next((c for c in oz["kurlar"] if c["kur"] == "2"), None)
        check(k1 and k1["yapilan_odeme"] == 1000.0 and k1["kalan"] == 0.0, "kur1 tam ödenmiş görünüyor (özet)")
        check(k1 and k1.get("gizli") is True, "kur1 'gizli' işaretli (özet)")
        check(k2 and k2["kalan"] == 1500.0 and k2.get("gizli") is False, "kur2 aktif/borçlu, gizli değil")
        check(oz["toplam"]["beklenen"] == 2500.0 and oz["toplam"]["odenen"] == 1000.0 and oz["toplam"]["kalan"] == 1500.0,
              "kur-ozet toplamları doğru (2500/1000/1500)")

        # ── İŞ 4) Alınmayan ödeme sayacı (ozet): görünür kalan>0 kayıtlar ──
        o2 = (await ac.get("/api/muhasebe/ozet", headers=H_acc)).json()
        check(o2.get("alinmayan", {}).get("sayi") == 1, f"alınmayan sayacı=1 (yalnız kur2 borçlu) — {o2.get('alinmayan')}")
        check(o2.get("alinmayan", {}).get("toplam_kalan") == 1500.0, "alınmayan toplam kalan=1500")

        # ── B) kur1 BORÇLU kalırsa (tam ödenmemiş) → listede KALIR ──
        await server.db.students.update_one({"id": sid}, {"$set": {"yapilan_odeme": 500.0}})  # kur1 yarı ödendi
        r = await ac.get("/api/muhasebe/kisiler", headers=H_acc)
        rows = _satirlar(r.json(), sid)
        check(any(x.get("kur") == "1" for x in rows), "tamamlanmış ama BORÇLU kur (1) listede KALIYOR")
        k1row = next((x for x in rows if x.get("kur") == "1"), None)
        check(k1row and k1row["kalan"] == 500.0, f"kur1 kalan borç 500 gösteriliyor ({k1row and k1row['kalan']})")
        # Alınmayan sayacı artık 2 kayıt (kur1 500 + kur2 1500 = 2000)
        o3 = (await ac.get("/api/muhasebe/ozet", headers=H_acc)).json()
        check(o3.get("alinmayan", {}).get("sayi") == 2 and o3.get("alinmayan", {}).get("toplam_kalan") == 2000.0,
              f"alınmayan sayacı=2, toplam=2000 — {o3.get('alinmayan')}")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
