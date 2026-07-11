"""Admin migration altyapısı — /admin/migrations (yalnız admin).

Genel, tekrar kullanılabilir yol: kayıtlı veri migration'larını LİSTELER ve
ÇALIŞTIRIR. Her migration İDEMPOTENT olmalı ve `dry_run` desteklemeli (hiçbir şey
yazmadan ne yapacağını raporlar). Çalıştırma islem_log'a düşer.

Yeni migration eklemek: `@migration_kaydet(ad, aciklama)` ile JSON-serileştirilebilir
sonuç dönen bir `async def fn(dry_run: bool) -> dict` yaz. Frontend'de buton GEREKMEZ;
admin token'la POST /admin/migrations/{ad} çağrısı yeter.
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.audit import islem_kaydet
from modules.crm import _kur_no  # kur numarası parse (kanonik kaynak)

router = APIRouter()

# ── Migration kayıt defteri: ad -> {aciklama, fn} ──
MIGRATIONLAR: dict = {}


def migration_kaydet(ad: str, aciklama: str):
    def dekorator(fn):
        MIGRATIONLAR[ad] = {"aciklama": aciklama, "fn": fn}
        return fn
    return dekorator


@migration_kaydet(
    "ust-kur-xp",
    "Mevcut kur>1 öğrenciler için geriye dönük 'üst kur' XP kaydı "
    "(öğrenci+kur başına tek kayıt, idempotent).",
)
async def _migrate_ust_kur_xp(dry_run: bool) -> dict:
    """Kur>1 öğrenciler için (kaynak!=manuel) kur_atlamalari kaydı yoksa oluşturur.
    ogretmen_id=teachers.id, tarih=öğrencinin kayıt tarihi. Gerçek çalıştırmada
    etkilenen öğretmenlerin rozet/seviyesini yeniden değerlendirir."""
    from core.rozet_motor import rozet_degerlendir

    olusturulan = 0
    zaten_var = 0
    etkilenen: dict = {}   # teachers.id -> kayıt sayısı
    ornekler: list = []

    students = await db.students.find(
        {}, {"_id": 0, "id": 1, "ad": 1, "soyad": 1, "kur": 1, "ogretmen_id": 1, "olusturma_tarihi": 1}
    ).to_list(length=None)
    for s in students:
        kn = _kur_no(s.get("kur"))
        tid = s.get("ogretmen_id")
        if kn is None or kn <= 1 or not tid:
            continue  # kur<=1 (yeni kayıt) veya öğretmensiz → atla
        # İdempotent: bu öğrenci+kur için XP'ye sayılan kayıt zaten var mı?
        var = False
        async for k in db.kur_atlamalari.find(
                {"ogrenci_id": s["id"], "kaynak": {"$ne": "manuel"}},
                {"_id": 0, "yeni_kur": 1, "yeni_kur_no": 1}):
            n = k.get("yeni_kur_no")
            if n is None:
                n = _kur_no(k.get("yeni_kur"))
            if n == kn:
                var = True
                break
        if var:
            zaten_var += 1
            continue
        olusturulan += 1
        etkilenen[tid] = etkilenen.get(tid, 0) + 1
        if len(ornekler) < 10:
            ornekler.append({
                "ogrenci": f"{s.get('ad', '')} {s.get('soyad', '')}".strip(),
                "kur": s.get("kur"), "kur_no": kn, "ogretmen_id": tid,
            })
        if not dry_run:
            await db.kur_atlamalari.insert_one({
                "id": str(uuid.uuid4()),
                "ogrenci_id": s["id"],
                "ogretmen_id": tid,
                "eski_kur": "",
                "yeni_kur": str(s.get("kur")),
                "yeni_kur_no": kn,
                "kaynak": "migrasyon",  # != "manuel" → XP'ye sayılır
                "tarih": s.get("olusturma_tarihi") or datetime.now(timezone.utc).isoformat(),
            })

    # Rozet/seviye yeniden değerlendir (yalnız GERÇEK çalıştırmada)
    rozet_verilen = 0
    if not dry_run:
        for tid in etkilenen:
            u = await db.users.find_one({"linked_id": tid}, {"_id": 0, "id": 1})
            if u and u.get("id"):
                try:
                    rozet_verilen += len(await rozet_degerlendir(u["id"], "kur_atlama") or [])
                except Exception as ex:
                    logging.warning(f"[migration ust-kur-xp] rozet: {ex}")

    # Etkilenen öğretmen adları (rapor için)
    etkilenen_ogretmenler = []
    for tid, c in etkilenen.items():
        t = await db.teachers.find_one({"id": tid}, {"_id": 0, "ad": 1, "soyad": 1})
        etkilenen_ogretmenler.append({
            "ogretmen_id": tid,
            "ad": (f"{(t or {}).get('ad', '')} {(t or {}).get('soyad', '')}".strip() or None),
            "kayit_sayisi": c,
        })

    return {
        "olusturulan": olusturulan,
        "zaten_var": zaten_var,
        "etkilenen_ogretmen_sayisi": len(etkilenen),
        "etkilenen_ogretmenler": etkilenen_ogretmenler,
        "rozet_verilen": rozet_verilen,
        "ornekler": ornekler,
    }


@router.get("/admin/migrations")
async def migration_listele(current_user=Depends(require_role(UserRole.ADMIN))):
    """Kayıtlı migration'ları listeler (yalnız admin)."""
    return {"migrationlar": [{"ad": ad, "aciklama": m["aciklama"]} for ad, m in MIGRATIONLAR.items()]}


@router.post("/admin/migrations/{ad}")
async def migration_calistir(ad: str, dry_run: bool = False,
                             current_user=Depends(require_role(UserRole.ADMIN))):
    """Kayıtlı bir migration'ı çalıştırır (yalnız admin).

    - dry_run=true → hiçbir şey YAZMADAN ne yapacağını raporlar.
    - Migration idempotent; iki kez çağrılsa da mükerrer üretmez.
    - İşlem islem_log'a kaydedilir (kim / ne zaman / sonuç özeti).
    """
    m = MIGRATIONLAR.get(ad)
    if not m:
        raise HTTPException(status_code=404, detail=f"Bilinmeyen migration: {ad}")
    sonuc = await m["fn"](bool(dry_run))
    await islem_kaydet(
        current_user, "admin_migration", ("dry_run" if dry_run else "calistir"),
        "migration", ad,
        ekstra={"dry_run": bool(dry_run), "olusturulan": sonuc.get("olusturulan"),
                "zaten_var": sonuc.get("zaten_var"),
                "etkilenen_ogretmen_sayisi": sonuc.get("etkilenen_ogretmen_sayisi")})
    return {"ad": ad, "dry_run": bool(dry_run), "sonuc": sonuc}
