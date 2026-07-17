"""AI CEO — Öğretmen Sistem-Deneyim Görevleri (S2): XP'li keşif yolu.

Gerçek özelliklerden görevler; tamamlama OTOMATİK algılanır (eylem gerçekleşince kapanır —
"yaptım" butonu yok). Geriye dönük: zaten yapılmış eylemler tamamlanmış sayılır (migration).
Aşamalı: sıradaki görev "Sistem Danışmanı Miran" tarafından sunulur. Admin görev listesini
(ekle/çıkar/sırala/XP) Ayarlar'dan yönetir; değerler sistem_ayarlari'nda saklanır.

XP: her görevin XP'si admin ayarından; kazanım ai_ceo_deneyim_tamamlanan'da (idempotent).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole, get_current_user
from core.zaman import iso

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
AYAR_TIP = "ogretmen_deneyim_gorevleri"

# Varsayılan görev kataloğu (koşul = otomatik algılama anahtarı; GOREV_KOSULLARI'na bakar)
# hedef = öğretmen panelindeki sekme id'si (tıkla → git). Admin görev eklerken hedef seçer.
VARSAYILAN_GOREVLER = [
    {"id": "ilk_ogrenci", "baslik": "İlk öğrencini ekle", "aciklama": "Sana atanmış en az bir öğrenci olsun.", "xp": 50, "sira": 1, "aktif": True, "hedef": "ogrencilerim"},
    {"id": "profil_tamam", "baslik": "Profilini tamamla", "aciklama": "İl/ilçe + mezuniyet bilgini gir.", "xp": 40, "sira": 2, "aktif": True, "hedef": "profilim"},
    {"id": "ders_plani", "baslik": "Haftalık ders planı gir", "aciklama": "Ders programına bir plan ekle.", "xp": 60, "sira": 3, "aktif": True, "hedef": "program"},
    {"id": "timi_uygula", "baslik": "Bir TIMI envanteri uygula", "aciklama": "Bir öğrencine TIMI uygula.", "xp": 70, "sira": 4, "aktif": True, "hedef": "giris-analizi"},
    {"id": "sinav_ata", "baslik": "Öğrencine sınav görevi ata", "aciklama": "Bir sınav/ödev ata.", "xp": 60, "sira": 5, "aktif": True, "hedef": "gorevler"},
    {"id": "miran_geri_bildirim", "baslik": "Miran'ın önerisini değerlendir", "aciklama": "Bir koçluk önerisini faydalı/faydasız işaretle.", "xp": 30, "sira": 6, "aktif": True, "hedef": "kocum-miran"},
    {"id": "sss_bak", "baslik": "SSS'ye göz at", "aciklama": "Yardım/SSS bölümünü ziyaret et.", "xp": 20, "sira": 7, "aktif": True, "ziyaret": True, "hedef": "sss"},
]


# ── Otomatik algılama koşulları (öğretmen id + teacher doc → bool) ──
async def _k_ilk_ogrenci(tid, t):
    if (t.get("atanan_ogrenciler") or []):
        return True
    return await db.students.count_documents({"ogretmen_id": tid, "arsivli": {"$ne": True}}) > 0


async def _k_profil(tid, t):
    return bool((t.get("il") or "").strip() and (t.get("ilce") or "").strip()
                and ((t.get("universite") or "").strip() or (t.get("bolum") or "").strip()))


async def _say(koleksiyonlar, filtreler):
    for koll in koleksiyonlar:
        for f in filtreler:
            try:
                if await db[koll].count_documents(f) > 0:
                    return True
            except Exception:
                continue
    return False


async def _k_ders_plani(tid, t):
    return await _say(["ders_programi", "ders_programlari"],
                      [{"ogretmen_id": tid}, {"olusturan": tid}, {"ogretmen": tid}])


async def _k_timi(tid, t):
    return await _say(["timi", "timi_sonuclari", "timi_uygulamalari"],
                      [{"ogretmen_id": tid}, {"uygulayan": tid}])


async def _k_sinav(tid, t):
    return await _say(["sinav_odevleri", "odevler", "sinav_atamalari", "sinavlar"],
                      [{"ogretmen_id": tid}, {"atayan": tid}, {"olusturan": tid}])


async def _k_miran_gb(tid, t):
    return await db.ai_ceo_miran_geribildirim.count_documents({"ogretmen_id": tid}) > 0


async def _k_ziyaret(tid, t, gorev_id):
    return await db.ai_ceo_deneyim_ziyaret.count_documents({"ogretmen_id": tid, "gorev_id": gorev_id}) > 0


GOREV_KOSULLARI = {
    "ilk_ogrenci": _k_ilk_ogrenci, "profil_tamam": _k_profil, "ders_plani": _k_ders_plani,
    "timi_uygula": _k_timi, "sinav_ata": _k_sinav, "miran_geri_bildirim": _k_miran_gb,
}


async def _tanimlar() -> list:
    doc = await db.sistem_ayarlari.find_one({"tip": AYAR_TIP})
    gorevler = (doc or {}).get("gorevler") or VARSAYILAN_GOREVLER
    return sorted([g for g in gorevler if g.get("aktif", True)], key=lambda g: g.get("sira", 99))


async def _tamamlandi_mi(g, tid, t) -> bool:
    if g.get("ziyaret"):
        return await _k_ziyaret(tid, t, g["id"])
    fn = GOREV_KOSULLARI.get(g["id"])
    if not fn:
        return False
    try:
        return await fn(tid, t)
    except Exception:
        return False


async def _degerlendir(tid: str) -> dict:
    t = await db.teachers.find_one({"id": tid}, {"_id": 0}) or {}
    tanimlar = await _tanimlar()
    kazanilmis = {k["gorev_id"] async for k in db.ai_ceo_deneyim_tamamlanan.find({"ogretmen_id": tid}, {"_id": 0, "gorev_id": 1})}
    sonuc = []
    yeni_kazanim = []
    for g in tanimlar:
        bitti = await _tamamlandi_mi(g, tid, t)
        if bitti and g["id"] not in kazanilmis:
            # XP kazanımı (idempotent, geriye dönük dahil)
            await db.ai_ceo_deneyim_tamamlanan.insert_one(
                {"ogretmen_id": tid, "gorev_id": g["id"], "xp": g.get("xp", 0), "tarih": iso()})
            kazanilmis.add(g["id"])
            yeni_kazanim.append(g)
        sonuc.append({**g, "tamamlandi": bitti})
    # Yeni tamamlananlar için bildirim (aşamalı: sıradaki hazır)
    if yeni_kazanim:
        try:
            from modules.bildirim import bildirim_olustur
            await bildirim_olustur(tid, "ai_ceo_miran",
                                   f"🎯 '{yeni_kazanim[-1]['baslik']}' tamamlandı! Sıradaki adımın hazır.", None)
        except Exception:
            pass
    toplam = len(sonuc)
    biten = sum(1 for s in sonuc if s["tamamlandi"])
    siradaki = next((s for s in sonuc if not s["tamamlandi"]), None)
    _xp_kayit = await db.ai_ceo_deneyim_tamamlanan.find({"ogretmen_id": tid}, {"_id": 0, "xp": 1}).to_list(length=1000)
    kazanilan_xp = sum(k.get("xp", 0) for k in _xp_kayit)
    return {"gorevler": sonuc, "toplam": toplam, "biten": biten,
            "ilerleme_yuzde": round(biten * 100 / toplam, 0) if toplam else 0,
            "siradaki": siradaki, "kazanilan_xp": kazanilan_xp}


# ── Öğretmen uçları ──
@router.get("/ai/ceo/deneyim/benim")
async def deneyim_benim(current_user=Depends(get_current_user)):
    if current_user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Bu görevler öğretmenler içindir.")
    tid = current_user.get("linked_id") or current_user.get("id")
    return {"deneyim": await _degerlendir(tid)}


@router.post("/ai/ceo/deneyim/ziyaret/{gorev_id}")
async def deneyim_ziyaret(gorev_id: str, current_user=Depends(get_current_user)):
    """Ziyaret-tipi görevler için otomatik işaret (sayfayı açınca; 'yaptım' butonu değil)."""
    if current_user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Yetkisiz")
    tid = current_user.get("linked_id") or current_user.get("id")
    await db.ai_ceo_deneyim_ziyaret.update_one(
        {"ogretmen_id": tid, "gorev_id": gorev_id},
        {"$set": {"ogretmen_id": tid, "gorev_id": gorev_id, "tarih": iso()}}, upsert=True)
    return {"ok": True}


# ── Admin ayar uçları ──
@router.get("/ai/ceo/deneyim/tanimlar")
async def deneyim_tanimlar(current_user=Depends(_ADMIN)):
    doc = await db.sistem_ayarlari.find_one({"tip": AYAR_TIP}, {"_id": 0})
    return {"gorevler": (doc or {}).get("gorevler") or VARSAYILAN_GOREVLER}


@router.put("/ai/ceo/deneyim/tanimlar")
async def deneyim_tanimlar_guncelle(govde: dict, current_user=Depends(_ADMIN)):
    gorevler = govde.get("gorevler")
    if not isinstance(gorevler, list):
        raise HTTPException(status_code=400, detail="gorevler (liste) gerekli")
    await db.sistem_ayarlari.update_one({"tip": AYAR_TIP},
                                        {"$set": {"tip": AYAR_TIP, "gorevler": gorevler}}, upsert=True)
    return {"ok": True}
