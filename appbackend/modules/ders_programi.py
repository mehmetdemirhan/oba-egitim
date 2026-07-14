"""Ders Programı (takvim) modülü — haftalık tekrar eden ders serileri + tek tek
ders oturumları.

Mimari karar (DB şişmesini önlemek için):
  - Seri oluşturulduğunda ileri haftalar için oturum ÜRETİLMEZ.
  - `ders_serileri` (haftalık şablon) + `ders_oturumlari` (gerçekleşen/taşınan/
    yoklama girilen tekil günler) birlikte sorgulanır.
  - Program listesi, istenen tarih aralığında:
      a) ders_oturumlari kayıtlarını (gerçek) çeker,
      b) seri kurallarından BEKLENEN ("planlı") oturumları hesaplar,
      c) ikisini birleştirir. Bir slot materyalize edilmişse planlı kopyası gizlenir.
  - Bir oturum yalnızca öğretmen "taşı / yoklama gir / iptal" dediğinde
    ders_oturumlari'na yazılır (materyalizasyon).

Bu modül BAĞIMSIZDIR: muhasebe/CRM/egzersiz modüllerine bağlı değildir.
Bildirim için yalnızca bildirim.bildirim_olustur kullanılır.
"""
import uuid
import logging
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from core.db import db
from core.auth import require_role, UserRole

router = APIRouter()

GUN_ADLARI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

_DERS_YETKI = require_role(UserRole.ADMIN, UserRole.COORDINATOR, UserRole.TEACHER)
_ADMIN_YETKI = require_role(UserRole.ADMIN, UserRole.COORDINATOR)


# ─────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────
def _temizle(doc):
    if doc:
        doc.pop("_id", None)
    return doc


def _ad(user: dict) -> str:
    return (f"{user.get('ad', '')} {user.get('soyad', '')}".strip()
            or user.get("ad") or "Kullanıcı")


def _ogretmen_kimlik(user: dict) -> str:
    """Öğretmenin ders/öğrenci eşlemesinde kullanılan kimliği (linked_id veya id)."""
    return user.get("linked_id") or user.get("id")


async def _ogretmen_ad(ogretmen_id: str) -> str:
    t = await db.teachers.find_one({"id": ogretmen_id})
    if t:
        return f"{t.get('ad', '')} {t.get('soyad', '')}".strip() or "Öğretmen"
    u = await db.users.find_one({"id": ogretmen_id})
    if u:
        return f"{u.get('ad', '')} {u.get('soyad', '')}".strip() or "Öğretmen"
    return "Öğretmen"


async def _ogrenci_ad(ogrenci_id: str) -> str:
    s = await db.students.find_one({"id": ogrenci_id})
    if s:
        return f"{s.get('ad', '')} {s.get('soyad', '')}".strip() or "Öğrenci"
    return "Öğrenci"


def _saat_gecerli(s: str) -> bool:
    try:
        ss, dd = s.split(":")
        return len(s) == 5 and 0 <= int(ss) <= 23 and 0 <= int(dd) <= 59
    except Exception:
        return False


def _saat_dogrula(bas: str, bit: str):
    if not (_saat_gecerli(bas) and _saat_gecerli(bit)):
        raise HTTPException(status_code=400, detail="Saat formatı geçersiz (ör. 15:00).")
    if not (bas < bit):  # "HH:MM" sıfır dolgulu → sözlüksel sıralama doğru çalışır
        raise HTTPException(status_code=400, detail="Bitiş saati başlangıçtan sonra olmalı.")


def _gun_dogrula(gun):
    if not isinstance(gun, int) or not (0 <= gun <= 6):
        raise HTTPException(status_code=400, detail="Gün 0 (Pazartesi) ile 6 (Pazar) arasında olmalı.")


def _tarih_dogrula(t: str) -> str:
    try:
        return date.fromisoformat(t[:10]).isoformat()
    except Exception:
        raise HTTPException(status_code=400, detail=f"Tarih formatı geçersiz: {t} (YYYY-MM-DD).")


def _saat_cakisir(b1, e1, b2, e2) -> bool:
    return b1 < e2 and b2 < e1


def _tarih_araligi_cakisir(a_bas, a_bit, b_bas, b_bit) -> bool:
    """Açık uçlu (None = süresiz) iki tarih aralığı kesişiyor mu?"""
    if a_bit and a_bit < b_bas:
        return False
    if b_bit and b_bit < a_bas:
        return False
    return True


def _yetki_kontrol(doc_ogretmen_id: str, current_user: dict):
    rol = current_user.get("role")
    if rol in ("admin", "coordinator"):
        return
    if rol == "teacher" and doc_ogretmen_id == _ogretmen_kimlik(current_user):
        return
    raise HTTPException(status_code=403, detail="Bu ders üzerinde yetkiniz yok.")


async def _degisiklik_logla(tip, ogretmen_id, ogretmen_ad, ogrenci_id, ogrenci_ad,
                            eski, yeni, sebep, yapan, seri_id=None, oturum_id=None):
    await db.ders_degisiklikleri.insert_one({
        "id": str(uuid.uuid4()),
        "tip": tip,
        "ogretmen_id": ogretmen_id, "ogretmen_ad": ogretmen_ad,
        "ogrenci_id": ogrenci_id, "ogrenci_ad": ogrenci_ad,
        "eski": eski, "yeni": yeni, "sebep": sebep or "",
        "yapan_id": yapan.get("id"), "yapan_ad": _ad(yapan),
        "seri_id": seri_id, "oturum_id": oturum_id,
        "tarih": datetime.utcnow().isoformat(),
    })


async def _bildir(ogrenci_id, mesaj, ilgili_id, yapan):
    """İlgili öğrenci + velisi + yöneticilere bildirim (best-effort, akışı bloklamaz)."""
    try:
        from modules.bildirim import bildirim_olustur
        await bildirim_olustur(ogrenci_id, "ders_degisiklik", mesaj, ilgili_id)
        st = await db.students.find_one({"id": ogrenci_id})
        if st and st.get("veli_id"):
            await bildirim_olustur(st["veli_id"], "ders_degisiklik", mesaj, ilgili_id)
        adminler = await db.users.find({"role": {"$in": ["admin", "coordinator"]}}).to_list(length=50)
        for adm in adminler:
            await bildirim_olustur(adm["id"], "ders_degisiklik", f"{_ad(yapan)}: {mesaj}", ilgili_id)
    except Exception as ex:
        logging.warning(f"[ders_programi] bildirim hatası: {ex}")


# ── Çakışma kontrolü ──────────────────────────────────────────
async def _oturum_cakismasi(ogretmen_id, ogrenci_id, tarih, bas, bit,
                            haric_oturum_id=None, haric_seri_id=None):
    """Belirli bir tarih+saat diliminde öğretmen ya da öğrenci için çakışma var mı?
    Hem materyalize oturumları hem de serilerden hesaplanan planlıları kontrol eder.
    Çakışan kayıt döner, yoksa None."""
    gun = date.fromisoformat(tarih).weekday()

    # 1) Materyalize oturumlar (iptal hariç)
    otus = await db.ders_oturumlari.find({"tarih": tarih, "yoklama": {"$ne": "iptal"}}).to_list(length=500)
    for o in otus:
        if haric_oturum_id and o["id"] == haric_oturum_id:
            continue
        if (o["ogretmen_id"] == ogretmen_id or o["ogrenci_id"] == ogrenci_id) \
                and _saat_cakisir(bas, bit, o["baslangic_saati"], o["bitis_saati"]):
            return o

    # 2) O gün için materyalize edilmiş seri slotları (çift sayma engeli)
    iliskili = await db.ders_oturumlari.find(
        {"$or": [{"tarih": tarih}, {"orijinal_tarih": tarih}]}).to_list(length=500)
    bloke_seri = set()
    for o in iliskili:
        if o.get("seri_id"):
            slot = (o.get("orijinal_tarih") or o.get("tarih"))[:10]
            if slot == tarih:
                bloke_seri.add(o["seri_id"])

    # 3) Serilerden hesaplanan planlı oturumlar
    seriler = await db.ders_serileri.find({"durum": "aktif", "gun": gun}).to_list(length=1000)
    for s in seriler:
        if haric_seri_id and s["id"] == haric_seri_id:
            continue
        if s["id"] in bloke_seri:
            continue
        if not (s["ogretmen_id"] == ogretmen_id or s["ogrenci_id"] == ogrenci_id):
            continue
        s_bas = s["baslangic_tarihi"][:10]
        s_bit = (s.get("bitis_tarihi") or None)
        if tarih < s_bas:
            continue
        if s_bit and tarih > s_bit[:10]:
            continue
        if _saat_cakisir(bas, bit, s["baslangic_saati"], s["bitis_saati"]):
            return s
    return None


async def _seri_cakismasi(ogretmen_id, ogrenci_id, gun, bas, bit, bas_tarih, bit_tarih, haric_seri_id=None):
    """Yeni/güncellenen seri, mevcut aktif serilerle (aynı gün, kesişen tarih+saat,
    aynı öğretmen ya da öğrenci) çakışıyor mu?"""
    seriler = await db.ders_serileri.find({"durum": "aktif", "gun": gun}).to_list(length=1000)
    for s in seriler:
        if haric_seri_id and s["id"] == haric_seri_id:
            continue
        if not (s["ogretmen_id"] == ogretmen_id or s["ogrenci_id"] == ogrenci_id):
            continue
        if not _saat_cakisir(bas, bit, s["baslangic_saati"], s["bitis_saati"]):
            continue
        if _tarih_araligi_cakisir(bas_tarih, bit_tarih,
                                  s["baslangic_tarihi"][:10],
                                  (s.get("bitis_tarihi") or None) and s["bitis_tarihi"][:10]):
            return s
    return None


# ── Oturum kaydı / materyalizasyon ────────────────────────────
def _oturum_kayit(o: dict) -> dict:
    return {
        "id": o["id"],
        "seri_id": o.get("seri_id"),
        "ogretmen_id": o["ogretmen_id"], "ogretmen_ad": o.get("ogretmen_ad", ""),
        "ogrenci_id": o["ogrenci_id"], "ogrenci_ad": o.get("ogrenci_ad", ""),
        "tarih": o["tarih"][:10],
        "baslangic_saati": o["baslangic_saati"], "bitis_saati": o["bitis_saati"],
        "yoklama": o.get("yoklama") or "planli",
        "durum": o.get("yoklama") or "planli",
        "tasima_sebebi": o.get("tasima_sebebi"),
        "orijinal_tarih": o.get("orijinal_tarih"),
        "yoklama_notu": o.get("yoklama_notu"),
        "planli_mi": False,
        "not": o.get("not"),
    }


def _planli_kayit(seri: dict, d: date) -> dict:
    return {
        "id": f"seri:{seri['id']}:{d.isoformat()}",  # sanal id (henüz DB'de yok)
        "seri_id": seri["id"],
        "ogretmen_id": seri["ogretmen_id"], "ogretmen_ad": seri.get("ogretmen_ad", ""),
        "ogrenci_id": seri["ogrenci_id"], "ogrenci_ad": seri.get("ogrenci_ad", ""),
        "tarih": d.isoformat(),
        "baslangic_saati": seri["baslangic_saati"], "bitis_saati": seri["bitis_saati"],
        "yoklama": "planli", "durum": "planli",
        "tasima_sebebi": None, "orijinal_tarih": None, "yoklama_notu": None,
        "planli_mi": True,
        "not": seri.get("not"),
    }


def _seri_planli_uret(seri: dict, b_date: date, e_date: date, bloke: set) -> list:
    """Seriden [b_date, e_date] aralığındaki planlı oturumları üretir (bloke slotlar hariç)."""
    if seri.get("durum") != "aktif":
        return []
    gun = seri["gun"]
    s_bas = date.fromisoformat(seri["baslangic_tarihi"][:10])
    s_bit = date.fromisoformat(seri["bitis_tarihi"][:10]) if seri.get("bitis_tarihi") else None
    out = []
    d = b_date
    while d <= e_date:
        if d.weekday() == gun and d >= s_bas and (s_bit is None or d <= s_bit):
            if (seri["id"], d.isoformat()) not in bloke:
                out.append(_planli_kayit(seri, d))
        d += timedelta(days=1)
    return out


async def _oturum_getir_veya_olustur(oturum_id: str, current_user: dict) -> dict:
    """Gerçek oturum id'si ise kaydı döner; "seri:{id}:{tarih}" sanal id'si ise
    seriden materyalize edip (DB'ye yazıp) döner. Yetki kontrolü yapar."""
    if oturum_id.startswith("seri:"):
        try:
            _, seri_id, tarih = oturum_id.split(":", 2)
            tarih = date.fromisoformat(tarih).isoformat()
        except Exception:
            raise HTTPException(status_code=400, detail="Geçersiz oturum referansı.")
        # Bu slot zaten materyalize edilmiş mi?
        var = await db.ders_oturumlari.find_one(
            {"seri_id": seri_id, "$or": [{"tarih": tarih}, {"orijinal_tarih": tarih}]})
        if var:
            _yetki_kontrol(var["ogretmen_id"], current_user)
            return var
        seri = await db.ders_serileri.find_one({"id": seri_id})
        if not seri:
            raise HTTPException(status_code=404, detail="Ders serisi bulunamadı.")
        _yetki_kontrol(seri["ogretmen_id"], current_user)
        doc = {
            "id": str(uuid.uuid4()),
            "seri_id": seri_id,
            "ogretmen_id": seri["ogretmen_id"], "ogretmen_ad": seri.get("ogretmen_ad", ""),
            "ogrenci_id": seri["ogrenci_id"], "ogrenci_ad": seri.get("ogrenci_ad", ""),
            "tarih": tarih,
            "baslangic_saati": seri["baslangic_saati"], "bitis_saati": seri["bitis_saati"],
            "orijinal_tarih": None, "orijinal_saat": None,
            "tasima_sebebi": None,
            "yoklama": "planli", "yoklama_notu": None, "yoklama_tarihi": None,
            "olusturan_id": current_user.get("id"),
            "olusturma_tarihi": datetime.utcnow().isoformat(),
        }
        await db.ders_oturumlari.insert_one(dict(doc))
        return doc

    o = await db.ders_oturumlari.find_one({"id": oturum_id})
    if not o:
        raise HTTPException(status_code=404, detail="Ders oturumu bulunamadı.")
    _yetki_kontrol(o["ogretmen_id"], current_user)
    return o


async def _ogretmen_coz(data: dict, current_user: dict) -> str:
    """Body + role'e göre hedef öğretmen kimliğini çözer."""
    if current_user.get("role") == "teacher":
        return _ogretmen_kimlik(current_user)
    ogretmen_id = data.get("ogretmen_id")
    if not ogretmen_id:
        raise HTTPException(status_code=400, detail="ogretmen_id gerekli.")
    return ogretmen_id


# ─────────────────────────────────────────────
# Seri endpoint'leri
# ─────────────────────────────────────────────
@router.post("/ders/seri")
async def seri_olustur(data: dict, current_user=Depends(_DERS_YETKI)):
    ogrenci_id = data.get("ogrenci_id")
    if not ogrenci_id:
        raise HTTPException(status_code=400, detail="ogrenci_id gerekli.")
    gun = data.get("gun")
    _gun_dogrula(gun)
    bas = data.get("baslangic_saati", "")
    bit = data.get("bitis_saati", "")
    _saat_dogrula(bas, bit)
    bas_tarih = _tarih_dogrula(data.get("baslangic_tarihi", ""))
    bit_tarih = _tarih_dogrula(data["bitis_tarihi"]) if data.get("bitis_tarihi") else None
    ogretmen_id = await _ogretmen_coz(data, current_user)

    cakisan = await _seri_cakismasi(ogretmen_id, ogrenci_id, gun, bas, bit, bas_tarih, bit_tarih)
    if cakisan:
        raise HTTPException(status_code=409, detail=f"Çakışma: {GUN_ADLARI[gun]} {bas} için bu öğretmen ya da öğrencinin başka bir dersi var.")

    doc = {
        "id": str(uuid.uuid4()),
        "ogretmen_id": ogretmen_id, "ogretmen_ad": await _ogretmen_ad(ogretmen_id),
        "ogrenci_id": ogrenci_id, "ogrenci_ad": await _ogrenci_ad(ogrenci_id),
        "gun": gun,
        "baslangic_saati": bas, "bitis_saati": bit,
        "baslangic_tarihi": bas_tarih, "bitis_tarihi": bit_tarih,
        "durum": "aktif",
        "olusturan_id": current_user.get("id"),
        "olusturma_tarihi": datetime.utcnow().isoformat(),
        "not": data.get("not", ""),
    }
    await db.ders_serileri.insert_one(dict(doc))
    return _temizle(doc)


@router.get("/ders/serilerim")
async def serilerim(ogretmen_id: str = Query(None), ogrenci_id: str = Query(None),
                    current_user=Depends(_DERS_YETKI)):
    sorgu = {}
    if current_user.get("role") == "teacher":
        sorgu["ogretmen_id"] = _ogretmen_kimlik(current_user)
    else:
        if ogretmen_id:
            sorgu["ogretmen_id"] = ogretmen_id
        if ogrenci_id:
            sorgu["ogrenci_id"] = ogrenci_id
    seriler = await db.ders_serileri.find(sorgu).sort("olusturma_tarihi", -1).to_list(length=500)
    for s in seriler:
        s.pop("_id", None)
    return {"seriler": seriler}


@router.put("/ders/seri/{seri_id}")
async def seri_guncelle(seri_id: str, data: dict, current_user=Depends(_DERS_YETKI)):
    seri = await db.ders_serileri.find_one({"id": seri_id})
    if not seri:
        raise HTTPException(status_code=404, detail="Ders serisi bulunamadı.")
    _yetki_kontrol(seri["ogretmen_id"], current_user)

    sebep = (data.get("sebep") or "").strip()
    if not sebep:
        raise HTTPException(status_code=400, detail="Değişiklik için sebep zorunludur.")

    gun = data.get("gun", seri["gun"])
    _gun_dogrula(gun)
    bas = data.get("baslangic_saati", seri["baslangic_saati"])
    bit = data.get("bitis_saati", seri["bitis_saati"])
    _saat_dogrula(bas, bit)
    bit_tarih = seri.get("bitis_tarihi")
    if "bitis_tarihi" in data:
        bit_tarih = _tarih_dogrula(data["bitis_tarihi"]) if data["bitis_tarihi"] else None

    cakisan = await _seri_cakismasi(seri["ogretmen_id"], seri["ogrenci_id"], gun, bas, bit,
                                    seri["baslangic_tarihi"][:10], bit_tarih, haric_seri_id=seri_id)
    if cakisan:
        raise HTTPException(status_code=409, detail=f"Çakışma: {GUN_ADLARI[gun]} {bas} dolu.")

    # Öğrenci değiştirme (yanlış öğrenciye girilen program düzeltmesi)
    yeni_ogrenci_id = seri["ogrenci_id"]
    yeni_ogrenci_ad = seri["ogrenci_ad"]
    ogrenci_degisti = False
    if data.get("ogrenci_id") and data["ogrenci_id"] != seri["ogrenci_id"]:
        ogr = await db.students.find_one({"id": data["ogrenci_id"]})
        if not ogr:
            raise HTTPException(status_code=404, detail="Yeni öğrenci bulunamadı.")
        yeni_ogrenci_id = data["ogrenci_id"]
        yeni_ogrenci_ad = await _ogrenci_ad(yeni_ogrenci_id)
        ogrenci_degisti = True

    eski = f"{seri['ogrenci_ad']} — {GUN_ADLARI[seri['gun']]} {seri['baslangic_saati']}-{seri['bitis_saati']}"
    yeni = f"{yeni_ogrenci_ad} — {GUN_ADLARI[gun]} {bas}-{bit}"
    guncelle_set = {
        "gun": gun, "baslangic_saati": bas, "bitis_saati": bit, "bitis_tarihi": bit_tarih,
        "ogrenci_id": yeni_ogrenci_id, "ogrenci_ad": yeni_ogrenci_ad,
    }
    await db.ders_serileri.update_one({"id": seri_id}, {"$set": guncelle_set})
    if ogrenci_degisti:
        # Gelecek oturumları da yeni öğrenciye taşı.
        await db.ders_oturumlari.update_many(
            {"seri_id": seri_id},
            {"$set": {"ogrenci_id": yeni_ogrenci_id, "ogrenci_ad": yeni_ogrenci_ad}})
    await _degisiklik_logla("seri_guncelle", seri["ogretmen_id"], seri["ogretmen_ad"],
                            yeni_ogrenci_id, yeni_ogrenci_ad, eski, yeni, sebep,
                            current_user, seri_id=seri_id)
    # Güncel (yeni) öğrenciye bildir. Öğrenci değiştiyse eski öğrenciye de bilgi ver.
    await _bildir(yeni_ogrenci_id, f"Ders programınız güncellendi: {yeni}. Sebep: {sebep}",
                  seri_id, current_user)
    if ogrenci_degisti:
        await _bildir(seri["ogrenci_id"], f"Bir ders programı sizden {yeni_ogrenci_ad} adlı öğrenciye taşındı. Sebep: {sebep}",
                      seri_id, current_user)
    guncel = await db.ders_serileri.find_one({"id": seri_id})
    return _temizle(guncel)


@router.delete("/ders/seri/{seri_id}")
async def seri_sonlandir(seri_id: str, sebep: str = Query(""), kalici: bool = Query(False),
                         current_user=Depends(_DERS_YETKI)):
    seri = await db.ders_serileri.find_one({"id": seri_id})
    if not seri:
        raise HTTPException(status_code=404, detail="Ders serisi bulunamadı.")
    _yetki_kontrol(seri["ogretmen_id"], current_user)
    # Kalıcı sil (yanlış girilen program): seriyi ve tüm oturumlarını tamamen kaldırır,
    # öğrenciye bildirim GÖNDERMEZ (hatalı kayıt). Sebep zorunlu değildir.
    if kalici:
        await db.ders_serileri.delete_one({"id": seri_id})
        silinen_oturum = await db.ders_oturumlari.delete_many({"seri_id": seri_id})
        await _degisiklik_logla("seri_kalici_sil", seri["ogretmen_id"], seri["ogretmen_ad"],
                                seri["ogrenci_id"], seri["ogrenci_ad"],
                                f"{GUN_ADLARI[seri['gun']]} {seri['baslangic_saati']}-{seri['bitis_saati']}",
                                "Kalıcı silindi (yanlış giriş)", (sebep or "Yanlış giriş"),
                                current_user, seri_id=seri_id)
        return {"id": seri_id, "durum": "silindi", "silinen_oturum": silinen_oturum.deleted_count}
    sebep = (sebep or "").strip()
    if not sebep:
        raise HTTPException(status_code=400, detail="Seriyi sonlandırmak için sebep zorunludur.")
    await db.ders_serileri.update_one({"id": seri_id}, {"$set": {"durum": "iptal"}})
    eski = f"{GUN_ADLARI[seri['gun']]} {seri['baslangic_saati']}-{seri['bitis_saati']}"
    await _degisiklik_logla("seri_iptal", seri["ogretmen_id"], seri["ogretmen_ad"],
                            seri["ogrenci_id"], seri["ogrenci_ad"], eski, "İptal", sebep,
                            current_user, seri_id=seri_id)
    await _bildir(seri["ogrenci_id"], f"Haftalık dersiniz ({eski}) sonlandırıldı. Sebep: {sebep}",
                  seri_id, current_user)
    return {"id": seri_id, "durum": "iptal"}


@router.post("/ders/seri/{seri_id}/durakla")
async def seri_durakla(seri_id: str, current_user=Depends(_DERS_YETKI)):
    seri = await db.ders_serileri.find_one({"id": seri_id})
    if not seri:
        raise HTTPException(status_code=404, detail="Ders serisi bulunamadı.")
    _yetki_kontrol(seri["ogretmen_id"], current_user)
    await db.ders_serileri.update_one({"id": seri_id}, {"$set": {"durum": "duraklatildi"}})
    return {"id": seri_id, "durum": "duraklatildi"}


@router.post("/ders/seri/{seri_id}/devam")
async def seri_devam(seri_id: str, current_user=Depends(_DERS_YETKI)):
    seri = await db.ders_serileri.find_one({"id": seri_id})
    if not seri:
        raise HTTPException(status_code=404, detail="Ders serisi bulunamadı.")
    _yetki_kontrol(seri["ogretmen_id"], current_user)
    await db.ders_serileri.update_one({"id": seri_id}, {"$set": {"durum": "aktif"}})
    return {"id": seri_id, "durum": "aktif"}


# ─────────────────────────────────────────────
# Tek ders oturumu endpoint'leri
# ─────────────────────────────────────────────
@router.post("/ders/oturum")
async def oturum_olustur(data: dict, current_user=Depends(_DERS_YETKI)):
    """Seriye bağlı olmayan tek seferlik ders."""
    ogrenci_id = data.get("ogrenci_id")
    if not ogrenci_id:
        raise HTTPException(status_code=400, detail="ogrenci_id gerekli.")
    tarih = _tarih_dogrula(data.get("tarih", ""))
    bas = data.get("baslangic_saati", "")
    bit = data.get("bitis_saati", "")
    _saat_dogrula(bas, bit)
    ogretmen_id = await _ogretmen_coz(data, current_user)

    cakisan = await _oturum_cakismasi(ogretmen_id, ogrenci_id, tarih, bas, bit)
    if cakisan:
        raise HTTPException(status_code=409, detail="Çakışma: bu tarih/saatte öğretmen ya da öğrencinin başka dersi var.")

    doc = {
        "id": str(uuid.uuid4()),
        "seri_id": None,
        "ogretmen_id": ogretmen_id, "ogretmen_ad": await _ogretmen_ad(ogretmen_id),
        "ogrenci_id": ogrenci_id, "ogrenci_ad": await _ogrenci_ad(ogrenci_id),
        "tarih": tarih, "baslangic_saati": bas, "bitis_saati": bit,
        "orijinal_tarih": None, "orijinal_saat": None, "tasima_sebebi": None,
        "yoklama": "planli", "yoklama_notu": None, "yoklama_tarihi": None,
        "olusturan_id": current_user.get("id"),
        "olusturma_tarihi": datetime.utcnow().isoformat(),
        "not": data.get("not", ""),
    }
    await db.ders_oturumlari.insert_one(dict(doc))
    return _temizle(doc)


@router.put("/ders/oturum/{oturum_id}/tasi")
async def oturum_tasi(oturum_id: str, data: dict, current_user=Depends(_DERS_YETKI)):
    """Tek bir oturumu farklı tarih/saate taşır — sebep zorunlu."""
    sebep = (data.get("sebep") or "").strip()
    if not sebep:
        raise HTTPException(status_code=400, detail="Taşıma için sebep zorunludur.")
    yeni_tarih = _tarih_dogrula(data.get("tarih", ""))
    yeni_bas = data.get("baslangic_saati", "")
    yeni_bit = data.get("bitis_saati", "")
    _saat_dogrula(yeni_bas, yeni_bit)

    o = await _oturum_getir_veya_olustur(oturum_id, current_user)

    cakisan = await _oturum_cakismasi(o["ogretmen_id"], o["ogrenci_id"], yeni_tarih, yeni_bas, yeni_bit,
                                      haric_oturum_id=o["id"], haric_seri_id=o.get("seri_id"))
    if cakisan:
        raise HTTPException(status_code=409, detail="Çakışma: yeni tarih/saatte başka ders var.")

    eski_tarih = o["tarih"][:10]
    eski = f"{eski_tarih} {o['baslangic_saati']}-{o['bitis_saati']}"
    yeni = f"{yeni_tarih} {yeni_bas}-{yeni_bit}"
    await db.ders_oturumlari.update_one({"id": o["id"]}, {"$set": {
        "tarih": yeni_tarih, "baslangic_saati": yeni_bas, "bitis_saati": yeni_bit,
        "orijinal_tarih": o.get("orijinal_tarih") or eski_tarih,
        "orijinal_saat": o.get("orijinal_saat") or f"{o['baslangic_saati']}-{o['bitis_saati']}",
        "tasima_sebebi": sebep,
    }})
    await _degisiklik_logla("oturum_tasi", o["ogretmen_id"], o.get("ogretmen_ad", ""),
                            o["ogrenci_id"], o.get("ogrenci_ad", ""), eski, yeni, sebep,
                            current_user, seri_id=o.get("seri_id"), oturum_id=o["id"])
    await _bildir(o["ogrenci_id"], f"Dersiniz taşındı: {eski} → {yeni}. Sebep: {sebep}",
                  o["id"], current_user)
    guncel = await db.ders_oturumlari.find_one({"id": o["id"]})
    return _temizle(guncel)


@router.post("/ders/oturum/{oturum_id}/yoklama")
async def oturum_yoklama(oturum_id: str, data: dict, current_user=Depends(_DERS_YETKI)):
    durum = data.get("durum")
    if durum not in ("katildi", "katilmadi", "iptal"):
        raise HTTPException(status_code=400, detail="Yoklama durumu: katildi | katilmadi | iptal.")
    o = await _oturum_getir_veya_olustur(oturum_id, current_user)
    await db.ders_oturumlari.update_one({"id": o["id"]}, {"$set": {
        "yoklama": durum,
        "yoklama_notu": data.get("not", ""),
        "yoklama_tarihi": datetime.utcnow().isoformat(),
    }})
    if durum == "iptal":
        await _degisiklik_logla("oturum_iptal", o["ogretmen_id"], o.get("ogretmen_ad", ""),
                                o["ogrenci_id"], o.get("ogrenci_ad", ""),
                                f"{o['tarih'][:10]} {o['baslangic_saati']}", "İptal",
                                data.get("not", ""), current_user,
                                seri_id=o.get("seri_id"), oturum_id=o["id"])
        await _bildir(o["ogrenci_id"], f"{o['tarih'][:10]} tarihli dersiniz iptal edildi.",
                      o["id"], current_user)
    guncel = await db.ders_oturumlari.find_one({"id": o["id"]})
    return _temizle(guncel)


@router.delete("/ders/oturum/{oturum_id}")
async def oturum_iptal(oturum_id: str, sebep: str = Query(""), current_user=Depends(_DERS_YETKI)):
    """Oturumu iptal eder (yoklama=iptal). Kayıt silinmez, geçmiş korunur."""
    o = await _oturum_getir_veya_olustur(oturum_id, current_user)
    await db.ders_oturumlari.update_one({"id": o["id"]}, {"$set": {
        "yoklama": "iptal", "yoklama_notu": sebep or "",
        "yoklama_tarihi": datetime.utcnow().isoformat(),
    }})
    await _degisiklik_logla("oturum_iptal", o["ogretmen_id"], o.get("ogretmen_ad", ""),
                            o["ogrenci_id"], o.get("ogrenci_ad", ""),
                            f"{o['tarih'][:10]} {o['baslangic_saati']}", "İptal",
                            sebep or "", current_user, seri_id=o.get("seri_id"), oturum_id=o["id"])
    await _bildir(o["ogrenci_id"], f"{o['tarih'][:10]} tarihli dersiniz iptal edildi.",
                  o["id"], current_user)
    return {"id": o["id"], "yoklama": "iptal"}


# ─────────────────────────────────────────────
# Program (takvim) + değişiklik geçmişi
# ─────────────────────────────────────────────
@router.get("/ders/program")
async def ders_program(baslangic: str = Query(...), bitis: str = Query(...),
                       ogretmen_id: str = Query(None), ogrenci_id: str = Query(None),
                       current_user=Depends(_DERS_YETKI)):
    b = _tarih_dogrula(baslangic)
    e = _tarih_dogrula(bitis)
    b_date = date.fromisoformat(b)
    e_date = date.fromisoformat(e)

    seri_sorgu, otu_sorgu = {}, {}
    if current_user.get("role") == "teacher":
        oid = _ogretmen_kimlik(current_user)
        seri_sorgu["ogretmen_id"] = oid
        otu_sorgu["ogretmen_id"] = oid
    else:
        if ogretmen_id:
            seri_sorgu["ogretmen_id"] = ogretmen_id
            otu_sorgu["ogretmen_id"] = ogretmen_id
        if ogrenci_id:
            seri_sorgu["ogrenci_id"] = ogrenci_id
            otu_sorgu["ogrenci_id"] = ogrenci_id

    # Gerçek oturumlar: tarih aralıkta VEYA orijinal_tarih aralıkta (taşınanları yakala)
    otu_list = await db.ders_oturumlari.find({**otu_sorgu, "$or": [
        {"tarih": {"$gte": b, "$lte": e}},
        {"orijinal_tarih": {"$gte": b, "$lte": e}},
    ]}).to_list(length=3000)

    bloke = set()
    goster = []
    for o in otu_list:
        if o.get("seri_id"):
            slot = (o.get("orijinal_tarih") or o.get("tarih"))[:10]
            bloke.add((o["seri_id"], slot))
        if b <= o.get("tarih", "")[:10] <= e:
            goster.append(_oturum_kayit(o))

    seriler = await db.ders_serileri.find({**seri_sorgu, "durum": "aktif"}).to_list(length=2000)
    for s in seriler:
        goster.extend(_seri_planli_uret(s, b_date, e_date, bloke))

    goster.sort(key=lambda r: (r["tarih"], r["baslangic_saati"]))
    return {"dersler": goster}


@router.get("/ders/degisiklikler")
async def ders_degisiklikler(baslangic: str = Query(None), bitis: str = Query(None),
                             ogretmen_id: str = Query(None), current_user=Depends(_ADMIN_YETKI)):
    sorgu = {}
    if baslangic and bitis:
        b = _tarih_dogrula(baslangic)
        e = _tarih_dogrula(bitis)
        # tarih ISO datetime; gün bazlı kapsama için bitişe gün sonu ekle
        sorgu["tarih"] = {"$gte": b, "$lte": e + "T23:59:59"}
    if ogretmen_id:
        sorgu["ogretmen_id"] = ogretmen_id
    kayitlar = await db.ders_degisiklikleri.find(sorgu).sort("tarih", -1).to_list(length=1000)
    for k in kayitlar:
        k.pop("_id", None)
    return {"degisiklikler": kayitlar}
