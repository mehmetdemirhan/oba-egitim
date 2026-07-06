"""Geriye dönük (backfill) reconcile — users ↔ teachers köprüsünü onarır.

Entegrasyon (core/hesap.ogretmen_kaydi_olustur) yazılmadan ÖNCE oluşturulmuş
öğretmen/koordinatör/yönetici kullanıcılarının `teachers` koleksiyonunda kaydı
YOKTUR; bu yüzden Öğretmenler sayfası ve öğrenci-atama dropdown'ı boş görünür.
Bu script o kayıtları geriye dönük açar ve iki yönlü köprüyü kurar:
    users.linked_id  ⇄  teachers.id
    teachers.user_id ==  users.id

Yaptıkları (HEPSİ idempotent — tekrar çalıştırmak güvenlidir, çift kayıt açmaz):
  - role ∈ {teacher, coordinator, admin} olan her kullanıcı için:
      • linked_id var + teachers kaydı var  → yalnız back-ref (user_id) garanti edilir
      • linked_id var ama teachers kaydı YOK → bayat linked_id temizlenir, yeni açılır
      • linked_id yok ama user_id ile eşleşen teachers var → RELINK (linked_id yazılır)
      • aynı ad+soyad'lı, user_id'siz teachers varsa → o kayda BAĞLANIR (çift açmaz)
      • hiçbiri yoksa → yeni teachers kaydı açılır (canlı koddaki şemayla birebir)

VARSAYILAN MOD = DRY-RUN (hiçbir şey yazmaz, yalnız ne yapacağını raporlar).
Gerçekten uygulamak için:  --apply

Çalıştırma (appbackend dizininden; MONGO_URL/DB_NAME ortamdan okunur):
  Önizleme (güvenli):  .venv/Scripts/python.exe scripts/reconcile_ogretmen.py
  Uygula:              .venv/Scripts/python.exe scripts/reconcile_ogretmen.py --apply

Render production shell'de: aynı komut, `python` ile (env'ler zaten Atlas'a bakar).
Türkçe çıktı için Windows'ta: set PYTHONIOENCODING=utf-8
"""
import sys
import asyncio
from pathlib import Path

# appbackend kökünü path'e ekle (core.* importları için)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

APPLY = "--apply" in sys.argv  # bayrak yoksa dry-run

# core.hesap ile birebir aynı roller — kaynak tek yerde kalsın diye oradan alınır.
# (import event loop gerektirmez ama tutarlılık için main içinde import ediyoruz.)


async def main():
    from core.db import db
    from core.hesap import OGRETMEN_ROLLERI, ogretmen_kaydi_olustur

    mod = "UYGULA (--apply)" if APPLY else "DRY-RUN (önizleme — hiçbir şey yazılmaz)"
    print("═══ users ↔ teachers RECONCILE ═══")
    print(f"  Mod: {mod}")
    print(f"  Roller: {sorted(OGRETMEN_ROLLERI)}\n")

    kullanicilar = await db.users.find(
        {"role": {"$in": list(OGRETMEN_ROLLERI)}}
    ).to_list(length=None)
    print(f"  Uygun kullanıcı sayısı: {len(kullanicilar)}\n")

    sayac = {"OK": 0, "BACKREF": 0, "RELINK": 0, "NAME_LINK": 0,
             "RECREATE": 0, "CREATE": 0}

    for u in kullanicilar:
        ad = f"{u.get('ad','')} {u.get('soyad','')}".strip() or "(isimsiz)"
        etiket = f"{ad} [{u.get('role')}] user_id={u.get('id')}"
        lid = u.get("linked_id")

        # 1) linked_id var → teachers kaydı gerçekten var mı?
        if lid:
            t = await db.teachers.find_one({"id": lid})
            if t:
                if t.get("user_id") == u.get("id"):
                    print(f"  ✓ OK        {etiket}  (zaten bağlı: teacher={lid})")
                    sayac["OK"] += 1
                else:
                    print(f"  → BACKREF   {etiket}  teachers.user_id yazılacak (teacher={lid})")
                    if APPLY:
                        await db.teachers.update_one(
                            {"id": lid}, {"$set": {"user_id": u["id"]}})
                    sayac["BACKREF"] += 1
                continue
            else:
                # bayat linked_id — işaret ettiği teachers kaydı yok
                print(f"  → RECREATE  {etiket}  bayat linked_id={lid} (teacher yok) → temizle+yeniden aç")
                if APPLY:
                    await db.users.update_one({"id": u["id"]}, {"$unset": {"linked_id": ""}})
                    u = await db.users.find_one({"id": u["id"]})  # güncel doc
                    yeni = await ogretmen_kaydi_olustur(u)
                    print(f"               → yeni teacher={yeni}")
                sayac["RECREATE"] += 1
                continue

        # 2) linked_id yok — user_id ile eşleşen teachers var mı? (RELINK)
        t = await db.teachers.find_one({"user_id": u.get("id")})
        if t:
            print(f"  → RELINK    {etiket}  users.linked_id yazılacak (teacher={t['id']})")
            if APPLY:
                await db.users.update_one({"id": u["id"]}, {"$set": {"linked_id": t["id"]}})
            sayac["RELINK"] += 1
            continue

        # 3) linked_id yok — aynı ad+soyad'lı, user_id'siz teachers var mı? (çift açma!)
        eslesen = await db.teachers.find_one({
            "ad": u.get("ad", ""), "soyad": u.get("soyad", ""),
            "$or": [{"user_id": {"$exists": False}}, {"user_id": None}, {"user_id": ""}],
        })
        if eslesen:
            print(f"  → NAME_LINK {etiket}  mevcut teachers'a bağlanacak (teacher={eslesen['id']}, ad eşleşti)")
            if APPLY:
                await db.teachers.update_one({"id": eslesen["id"]}, {"$set": {"user_id": u["id"]}})
                await db.users.update_one({"id": u["id"]}, {"$set": {"linked_id": eslesen["id"]}})
            sayac["NAME_LINK"] += 1
            continue

        # 4) hiçbir eşleşme yok — yeni teachers kaydı aç (canlı kodla birebir)
        print(f"  → CREATE    {etiket}  yeni teachers kaydı açılacak")
        if APPLY:
            yeni = await ogretmen_kaydi_olustur(u)
            print(f"               → yeni teacher={yeni}")
        sayac["CREATE"] += 1

    print("\n─── ÖZET ───")
    for k, v in sayac.items():
        print(f"  {k:10s}: {v}")
    toplam_degisiklik = sum(v for k, v in sayac.items() if k != "OK")
    print(f"  Değişecek/değişen kayıt: {toplam_degisiklik}")

    # Doğrulama: kaç öğretmen rolü kullanıcı hâlâ teachers'sız?
    eksik = 0
    for u in await db.users.find({"role": {"$in": list(OGRETMEN_ROLLERI)}}).to_list(None):
        lid = u.get("linked_id")
        if not lid or not await db.teachers.find_one({"id": lid}):
            eksik += 1
    print(f"  Doğrulama — teachers kaydı hâlâ eksik olan: {eksik} (uygulandıysa 0 olmalı)")

    if not APPLY:
        print("\n  ⚠  DRY-RUN: hiçbir şey yazılmadı. Uygulamak için: --apply")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
