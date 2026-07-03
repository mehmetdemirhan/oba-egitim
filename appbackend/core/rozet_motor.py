"""Rozet motoru — veri-odaklı, event-driven ödül değerlendirmesi.

FAZ 2. ilerleme.py:rozet_kontrol'ün sabit if-else mantığını, koşulları veri
olarak (db.rozetler koleksiyonu, yoksa core.rozet_kosullari fallback) okuyup
değerlendiren tek motora taşır.

Ana giriş noktaları:
  - rozet_degerlendir(user_id, tetikleyen_event=None) -> list[dict]
      Kullanıcının hak ettiği ama henüz almadığı rozetleri verir, bildirim
      gönderir, yeni kazanılanları döner.
  - metrik_hesapla(user_id, role, metrik) -> float
      Tek bir metriğin değerini döner (test/introspection için).
  - kullanici_metrikleri(user_id, role) -> dict
      Tüm metrikleri TEK geçişte hesaplar (motor bunu kullanır — N+1 yok).

Metrik hesapları ilerleme.py:rozet_kontrol ile BİREBİR aynıdır; davranış korunur.
"""
import logging
import uuid
from datetime import datetime, timedelta

from pymongo.errors import DuplicateKeyError

from core.db import db
from core.sistem import get_ogretmen_rozetleri, get_ogrenci_rozetleri
from core.rozet_helpers import _norm_rol, rozet_odul_puan, rozet_bildirim_gonder
from core.rozet_kosullari import OGRETMEN_KOSULLARI, OGRENCI_KOSULLARI, kosul_getir


# ─────────────────────────────────────────────
# OPERATÖR DEĞERLENDİRME
# ─────────────────────────────────────────────
def _op_uygula(deger, operator, esik) -> bool:
    if operator is None or esik is None:
        return False  # manuel / eksik koşul → otomatik verilmez
    try:
        d, e = float(deger), float(esik)
    except (TypeError, ValueError):
        return False
    if operator == ">=":
        return d >= e
    if operator == ">":
        return d > e
    if operator == "==":
        return d == e
    if operator == "<=":
        return d <= e
    if operator == "<":
        return d < e
    return False


def _kosul_saglandi(kosul: dict, metrikler: dict) -> bool:
    """Ana koşul + (varsa) 've' alt koşullarının tümü (AND) sağlanıyor mu?"""
    if not kosul:
        return False
    metrik = kosul.get("metrik")
    if metrik == "manuel" or metrik is None:
        return False
    if not _op_uygula(metrikler.get(metrik, 0), kosul.get("operator"), kosul.get("esik")):
        return False
    for alt in kosul.get("ve", []) or []:
        if not _op_uygula(metrikler.get(alt.get("metrik"), 0), alt.get("operator"), alt.get("esik")):
            return False
    return True


# ─────────────────────────────────────────────
# METRİK HESAPLAMA (tek geçiş)
# ─────────────────────────────────────────────
def _streak_hesapla(tarih_setleri, simdi=None) -> int:
    simdi = simdi or datetime.utcnow()
    st = 0
    for i in range(60):
        gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
        if gun in tarih_setleri:
            st += 1
        elif i > 0:
            break
    return st


async def _ogretmen_metrikleri(user_id: str, user: dict) -> dict:
    ogretmen_id = user.get("linked_id") or user_id
    simdi = datetime.utcnow()

    icerikler = await db.gelisim_icerik.count_documents({"ekleyen_id": user_id, "durum": "yayinda"})
    tum_icerikler = await db.gelisim_icerik.find({"durum": {"$in": ["yayinda", "oylama"]}}).to_list(length=None)
    oy_sayisi = sum(1 for ic in tum_icerikler if user_id in (ic.get("oylar") or {}))

    gorevler = await db.gorevler.find({"atayan_id": user_id}).to_list(length=None)
    gorev_sayisi = len(gorevler)
    tamamlanan_gorev = len([g for g in gorevler if g.get("durum") == "tamamlandi"])

    ogrenciler = await db.students.find({"ogretmen_id": ogretmen_id, "arsivli": {"$ne": True}}).to_list(length=None)
    streakler = []
    for s in ogrenciler:
        logs = await db.reading_logs.find({"ogrenci_id": s["id"]}).to_list(length=None)
        tarihler = set(l.get("tarih", "")[:10] for l in logs)
        streakler.append(_streak_hesapla(tarihler, simdi))
    ort_streak = sum(streakler) / max(len(streakler), 1)

    kur_sayisi = await db.kur_atlamalari.count_documents({"ogretmen_id": ogretmen_id})
    gelisim_tam = await db.gelisim_tamamlama.count_documents({"kullanici_id": user_id})

    mesajlar = await db.mesajlar.find({"gonderen_id": user_id}).to_list(length=None)
    mesaj_roller = set(m.get("alici_rol", "") for m in mesajlar)

    egz_tam = await db.egzersiz_tamamlama.find({"kullanici_id": user_id}).to_list(length=None)
    egz_turler = set(e.get("egzersiz_id", "") for e in egz_tam)

    anketler = await db.veli_anketleri.find({"ogretmen_id": ogretmen_id}).to_list(length=None)
    anket_sayisi = len(anketler)
    anket_ort = 0.0
    tavsiye_oran = 0.0
    if anket_sayisi > 0:
        puanlar, tavsiyeler = [], 0
        for a in anketler:
            py = [y.get("puan", 0) for y in a.get("yanitlar", []) if y.get("puan")]
            if py:
                puanlar.append(sum(py) / len(py))
            if a.get("tavsiye"):
                tavsiyeler += 1
        anket_ort = sum(puanlar) / max(len(puanlar), 1)
        tavsiye_oran = (tavsiyeler / anket_sayisi) * 100

    return {
        "icerik_sayisi": icerikler,
        "kalite_oyu": oy_sayisi,
        "gorev_atama_sayisi": gorev_sayisi,
        "gorev_tamamlanan": tamamlanan_gorev,
        "ogrenci_ort_streak": ort_streak,
        "kur_atlama_sayisi": kur_sayisi,
        "gelisim_tamamlama": gelisim_tam,
        "mesaj_sayisi": len(mesajlar),
        "mesaj_ogrenci_veli_kopru": 1 if ("student" in mesaj_roller and "parent" in mesaj_roller) else 0,
        "egzersiz_tur_sayisi": len(egz_turler),
        "veli_anket_sayisi": anket_sayisi,
        "veli_anket_ort": anket_ort,
        "veli_tavsiye_orani": tavsiye_oran,
    }


async def _ogrenci_metrikleri(user_id: str, user: dict) -> dict:
    ogrenci_id = user.get("linked_id") or user_id
    simdi = datetime.utcnow()

    logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).to_list(length=None)
    toplam_dk = sum(l.get("sure_dakika", 0) for l in logs)
    kitaplar = set(l.get("kitap_adi", "") for l in logs if l.get("kitap_adi"))
    tarihler = set(l.get("tarih", "")[:10] for l in logs)
    streak = _streak_hesapla(tarihler, simdi)

    gorevler_tam = await db.gorevler.count_documents({"hedef_id": ogrenci_id, "durum": "tamamlandi"})
    egz_tam = await db.egzersiz_tamamlama.find({"kullanici_id": user_id}).to_list(length=None)
    egz_turler = set(e.get("egzersiz_id", "") for e in egz_tam)

    student = await db.students.find_one({"id": ogrenci_id})
    toplam_xp = student.get("toplam_xp", 0) if student else 0

    return {
        "okuma_kayit_sayisi": len(logs),
        "okuma_dakikasi": toplam_dk,
        "giris_serisi": streak,
        "kitap_sayisi": len(kitaplar),
        "gorev_tamamlama": gorevler_tam,
        "egzersiz_sayisi": len(egz_tam),
        "egzersiz_tur_sayisi": len(egz_turler),
        "orman_agac_sayisi": toplam_dk,  # 1 dk = 1 ağaç
        "lig_xp": toplam_xp,
    }


async def kullanici_metrikleri(user_id: str, role: str, user: dict = None) -> dict:
    """Kullanıcının tüm rozet metriklerini TEK geçişte döner."""
    role = _norm_rol(role)
    if user is None:
        user = await db.users.find_one({"id": user_id})
    if not user:
        return {}
    if role == "teacher":
        return await _ogretmen_metrikleri(user_id, user)
    if role == "student":
        return await _ogrenci_metrikleri(user_id, user)
    return {}


async def metrik_hesapla(user_id: str, role: str, metrik: str) -> float:
    """Tek bir metriğin değerini döner (test/introspection). Motor toplu
    kullanici_metrikleri'ni tercih eder; bu ince sarmalayıcıdır."""
    metrikler = await kullanici_metrikleri(user_id, role)
    return float(metrikler.get(metrik, 0) or 0)


# ─────────────────────────────────────────────
# TANIM KAYNAĞI (db.rozetler → yoksa kod fallback)
# ─────────────────────────────────────────────
async def _kod_fallback_tanimlar(role: str) -> list:
    """db.rozetler boşsa: core.sistem DEFAULT'ları + rozet_kosullari'ndan
    tam tanım listesi (kosul dahil) üretir. Migration çalışmasa bile motor çalışır."""
    if role == "teacher":
        temel = await get_ogretmen_rozetleri()
        kosullar = OGRETMEN_KOSULLARI
    else:
        temel = await get_ogrenci_rozetleri()
        kosullar = OGRENCI_KOSULLARI
    out = []
    for t in temel:
        kod = t.get("kod")
        out.append({**t, "rol": role, "aktif": True,
                    "kosul": kosullar.get(kod, kosul_getir(role, kod))})
    return out


async def aktif_tanimlar(role: str) -> list:
    """Rol için aktif rozet tanımlarını döner (önce db.rozetler, yoksa fallback)."""
    role = _norm_rol(role)
    if role not in ("teacher", "student"):
        return []
    docs = await db.rozetler.find({"rol": role, "aktif": True}).to_list(length=None)
    if docs:
        for d in docs:
            d.pop("_id", None)
        return docs
    return await _kod_fallback_tanimlar(role)


# ─────────────────────────────────────────────
# ANA DEĞERLENDİRME
# ─────────────────────────────────────────────
async def rozet_degerlendir(user_id: str, tetikleyen_event: str = None) -> list:
    """Kullanıcının hak ettiği yeni rozetleri verir + bildirim gönderir.

    Fire-and-forget event tetikleyicilerinden veya /rozetler/kontrol'den çağrılır.
    Hata olsa bile (event bağlamında) sessizce loglanır, akışı kesmez.
    """
    try:
        user = await db.users.find_one({"id": user_id})
        if not user:
            return []
        role = _norm_rol(user.get("role", ""))
        if role not in ("teacher", "student"):
            return []

        mevcut = await db.kazanilan_rozetler.find({"kullanici_id": user_id}).to_list(length=None)
        mevcut_kodlar = set(r["rozet_kodu"] for r in mevcut)

        tanimlar = await aktif_tanimlar(role)
        metrikler = await kullanici_metrikleri(user_id, role, user)

        yeni_rozetler = []
        for tanim in tanimlar:
            kod = tanim.get("kod")
            if not kod or kod in mevcut_kodlar:
                continue
            if not _kosul_saglandi(tanim.get("kosul") or {}, metrikler):
                continue
            doc = {"id": str(uuid.uuid4()), "kullanici_id": user_id,
                   "rozet_kodu": kod, "kazanma_tarihi": datetime.utcnow().isoformat()}
            try:
                await db.kazanilan_rozetler.insert_one(doc)
            except DuplicateKeyError:
                continue  # yarış: zaten eklenmiş
            doc.pop("_id", None)
            await rozet_bildirim_gonder(user_id, tanim)
            yeni_rozetler.append({**doc, "rozet": tanim})
        if yeni_rozetler and tetikleyen_event:
            logging.info(f"[rozet_motor] {user_id} +{len(yeni_rozetler)} rozet (event={tetikleyen_event})")
        return yeni_rozetler
    except Exception as ex:
        logging.warning(f"[rozet_motor] degerlendirme hatası (user={user_id}, event={tetikleyen_event}): {ex}")
        return []


async def rozet_tetikle(user_id: str, tetikleyen_event: str = None):
    """Event tetikleyicileri için fire-and-forget sarmalayıcı. HTTP yanıtını
    geciktirmeden arka planda çalıştırılmak üzere asyncio.create_task ile çağrılır."""
    await rozet_degerlendir(user_id, tetikleyen_event)
