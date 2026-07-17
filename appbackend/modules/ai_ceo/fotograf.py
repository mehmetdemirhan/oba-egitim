"""AI CEO — "Sistem Fotoğrafı" servisi (deterministik, AI'dan ÖNCE).

Sistemin agregat metriklerini tek bir tarihli JSON'da toplar. AI (Ayda) yalnız bu
fotoğrafa dayanır → halüsinasyon dayanak doğrulaması bu JSON'a karşı yapılır.

KVKK: fotoğraf YALNIZ agregat sayılar + dağılımlar içerir. Kişisel iletişim verisi
(telefon/adres/e-posta/kargo) HİÇBİR yere KONULMAZ. Öğrenci verileri birey düzeyinde
girmez (yalnız dağılım/sayı); girmesi gerekirse takma-ID ile girer ve gerçek-ID eşlemesi
`_takma_harita`'da tutulur — bu alan AI payload'ından ÇIKARILIR (ai_payload()).

OTONOM ENVANTER: tüm koleksiyonların jenerik özet istatistikleri (yalnız sayı + son
hareket) otomatik dahil → yeni bir modül/koleksiyon eklenince fotoğraf onu kendiliğinden
kapsar. Değer (string) taşımaz, yalnız sayısal özet.
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import simdi, aware as _aware

try:
    from core.kayit_normalize import normalize_sinif
except Exception:  # pragma: no cover
    def normalize_sinif(s):
        import re
        if s is None:
            return None
        m = re.search(r"\d+", str(s))
        return int(m.group()) if m and 1 <= int(m.group()) <= 12 else None

router = APIRouter()

_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
KUR_HEDEF_GUN = 35  # bir kurun tamamlanması için hedef süre

# Otonom envanterde ASLA değer örneklenmeyecek (yalnız bu koleksiyonlar için sayı) —
# ve genelde hiçbir koleksiyondan string DEĞER alınmaz; bu liste ekstra güvence.
_HASSAS_KOLEKSIYONLAR = {"users", "students", "teachers", "payments", "bildirimler"}


# ─────────────────────────── yardımcılar ───────────────────────────
def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _iso_parse(s):
    """ISO string/None → DAİMA aware UTC datetime (naive = UTC varsayılır) veya None.
    Böylece iki tarih arasındaki fark/karşılaştırma naive/aware karışsa da patlamaz."""
    return _aware(s)


def _gun_farki(iso_str, ref: datetime) -> float | None:
    d = _iso_parse(iso_str)
    if not d:
        return None
    return (_aware(ref) - d).total_seconds() / 86400.0


def takma_id(gercek_id: str) -> str:
    """Öğrenci gerçek-ID → stabil takma-ID (AI'a bu gider, UI gerçek ada çözer)."""
    h = hashlib.sha1(str(gercek_id).encode("utf-8")).hexdigest()[:8]
    return f"O-{h}"


# ─────────────────────────── metrik blokları ───────────────────────────
async def _ogretmen_metrikleri(ref: datetime) -> dict:
    teachers = await db.teachers.find({}, {"_id": 0}).to_list(length=5000)
    aktif = [t for t in teachers if not t.get("arsivli")]
    kurlar = await db.kur_ucretleri.find({}, {"_id": 0}).to_list(length=50000)

    # Ortalama tamamlanan kur süresi (gün) — hedef KUR_HEDEF_GUN
    sureler = []
    for k in kurlar:
        bit = k.get("tamamlanma_tarihi") or k.get("odeme_tamamlanma_tarihi")
        bas = k.get("baslangic_tarihi") or k.get("tarih")
        if bit and bas:
            d1, d2 = _iso_parse(bas), _iso_parse(bit)
            if d1 and d2 and d2 >= d1:
                sureler.append((d2 - d1).total_seconds() / 86400.0)
    ort_sure = round(sum(sureler) / len(sureler), 1) if sureler else None

    # Geciken kur: açık + 35 günden eski
    geciken = 0
    for k in kurlar:
        if k.get("durum") in (None, "acik", "aktif") and not (k.get("tamamlanma_tarihi") or k.get("odeme_tamamlanma_tarihi")):
            fark = _gun_farki(k.get("baslangic_tarihi") or k.get("tarih"), ref)
            if fark is not None and fark > KUR_HEDEF_GUN:
                geciken += 1

    # Sistem geneli yenileme oranı (huni mantığı, 30 gün beklemede paydadan düşülür)
    tamamlayan = gecen = beklemede = 0
    # öğrenci başına tamamlanan kur seviyeleri
    ogr_kur = {}
    for k in kurlar:
        oid = k.get("ogrenci_id")
        if not oid:
            continue
        ogr_kur.setdefault(oid, []).append(k)
    for oid, ks in ogr_kur.items():
        seviyeler = set()
        tamamlanma = {}
        for k in ks:
            n = normalize_sinif(k.get("kur_adi") or k.get("kur"))  # kur no genelde sayısal
            if n is None:
                n = normalize_sinif(k.get("kur_no"))
            bit = k.get("tamamlanma_tarihi") or k.get("odeme_tamamlanma_tarihi")
            if n:
                seviyeler.add(n)
                if bit:
                    tamamlanma[n] = bit
        for n, bit in tamamlanma.items():
            tamamlayan += 1
            if (n + 1) in seviyeler:
                gecen += 1
            else:
                fark = _gun_farki(bit, ref)
                if fark is not None and fark < 30:
                    beklemede += 1
    payda = tamamlayan - beklemede
    yenileme_orani = round(gecen * 100 / payda, 1) if payda > 0 else None

    # Veli memnuniyeti (anket ortalaması, 1-5)
    memnuniyet = None
    try:
        anketler = await db.veli_anketleri.find({}, {"_id": 0, "puan": 1, "genel_puan": 1}).to_list(length=20000)
        puanlar = [_num(a.get("puan") or a.get("genel_puan")) for a in anketler if (a.get("puan") or a.get("genel_puan"))]
        memnuniyet = round(sum(puanlar) / len(puanlar), 2) if puanlar else None
    except Exception:
        pass

    ogrenci_sayilari = [len(t.get("atanan_ogrenciler") or []) for t in aktif]
    return {
        "toplam": len(teachers),
        "aktif": len(aktif),
        "ort_kur_suresi_gun": ort_sure,
        "kur_hedef_gun": KUR_HEDEF_GUN,
        "yenileme_orani_yuzde": yenileme_orani,
        "geciken_kur_sayisi": geciken,
        "ort_aktif_ogrenci_per_ogretmen": round(sum(ogrenci_sayilari) / len(ogrenci_sayilari), 1) if ogrenci_sayilari else 0,
        "veli_memnuniyeti_5uzerinden": memnuniyet,
    }


async def _muhasebe_metrikleri(ref: datetime) -> dict:
    students = await db.students.find({}, {"_id": 0, "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1}).to_list(length=100000)
    beklenen = sum(_num(s.get("yapilmasi_gereken_odeme")) for s in students)
    tahsil = sum(_num(s.get("yapilan_odeme")) for s in students)

    teachers = await db.teachers.find({}, {"_id": 0, "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1}).to_list(length=5000)
    ogt_odenecek = sum(_num(t.get("yapilmasi_gereken_odeme")) for t in teachers)
    ogt_odenen = sum(_num(t.get("yapilan_odeme")) for t in teachers)

    # Vergi: ödemelerdeki kayıtlı vergi toplamı
    vergi = 0.0
    try:
        pays = await db.payments.find({"tip": "ogrenci"}, {"_id": 0, "vergi": 1}).to_list(length=200000)
        vergi = sum(_num(p.get("vergi")) for p in pays)
    except Exception:
        pass
    net_kasa = tahsil - vergi - ogt_odenen

    # Alacak yaşlandırma (açık kur yaşına göre)
    kurlar = await db.kur_ucretleri.find({}, {"_id": 0}).to_list(length=50000)
    yas = {"0-30": 0, "31-60": 0, "60+": 0}
    alinmayan_sayi = 0
    for k in kurlar:
        bit = k.get("tamamlanma_tarihi") or k.get("odeme_tamamlanma_tarihi")
        kalan = _num(k.get("tutar")) - _num(k.get("yapilan_odeme"))
        if bit or kalan <= 0.01:
            continue
        alinmayan_sayi += 1
        fark = _gun_farki(k.get("baslangic_tarihi") or k.get("tarih"), ref) or 0
        if fark <= 30:
            yas["0-30"] += 1
        elif fark <= 60:
            yas["31-60"] += 1
        else:
            yas["60+"] += 1

    # Tahsilat trendi (son 3 ay, ödeme miktarı)
    trend = {}
    try:
        pays = await db.payments.find({"tip": "ogrenci"}, {"_id": 0, "miktar": 1, "tarih": 1}).to_list(length=200000)
        for p in pays:
            d = _iso_parse(p.get("tarih"))
            if d:
                ay = d.strftime("%Y-%m")
                trend[ay] = trend.get(ay, 0) + _num(p.get("miktar"))
    except Exception:
        pass
    son_aylar = dict(sorted(trend.items())[-3:])

    return {
        "beklenen_tahsilat": round(beklenen, 2),
        "tahsil_edilen": round(tahsil, 2),
        "bekleyen_tahsilat": round(max(0.0, beklenen - tahsil), 2),
        "toplam_vergi": round(vergi, 2),
        "net_kasa": round(net_kasa, 2),
        "ogretmene_odenecek": round(ogt_odenecek, 2),
        "ogretmene_odenen": round(ogt_odenen, 2),
        "alacak_yaslandirma": yas,
        "alinmayan_odeme_sayisi": alinmayan_sayi,
        "tahsilat_trendi_son3ay": {k: round(v, 2) for k, v in son_aylar.items()},
    }


async def _konsantrasyon_metrikleri(ref: datetime) -> dict:
    """S6c: en büyük öğretmen/eğitim türü bağımlılığı — konsantrasyon riski."""
    students = await db.students.find(
        {"arsivli": {"$ne": True}}, {"_id": 0, "ogretmen_id": 1, "aldigi_egitim": 1, "yapilan_odeme": 1}).to_list(length=100000)
    toplam_ogr = len(students)
    ogr_say, gelir_say, tur_say = {}, {}, {}
    for s in students:
        oid = s.get("ogretmen_id") or "?"
        ogr_say[oid] = ogr_say.get(oid, 0) + 1
        gelir_say[oid] = gelir_say.get(oid, 0.0) + _num(s.get("yapilan_odeme"))
        tur = (s.get("aldigi_egitim") or "?").strip() or "?"
        tur_say[tur] = tur_say.get(tur, 0) + 1
    toplam_gelir = sum(gelir_say.values()) or 1

    def _pay(d, toplam, n=1):
        # Bilinmeyen ("?") atanmamış kayıtlar konsantrasyon riski sayılmaz → hariç
        vals = sorted((v for k, v in d.items() if k != "?"), reverse=True)
        return round(sum(vals[:n]) * 100 / (toplam or 1), 1) if vals else 0.0

    return {
        "en_buyuk_ogretmen_ogrenci_payi": _pay(ogr_say, toplam_ogr, 1),
        "ilk3_ogretmen_ogrenci_payi": _pay(ogr_say, toplam_ogr, 3),
        "en_buyuk_ogretmen_gelir_payi": _pay(gelir_say, toplam_gelir, 1),
        "en_buyuk_tur_payi": _pay(tur_say, toplam_ogr, 1),
        "tur_dagilimi": tur_say,
        "esik_yuzde": 25.0,
    }


async def _birim_ekonomi_metrikleri(ref: datetime) -> dict:
    """S6b: LTV + kur başına net marj (net = brüt tahsilat − vergi − öğretmen payı)."""
    students = await db.students.find({"arsivli": {"$ne": True}}, {"_id": 0, "yapilan_odeme": 1, "aldigi_egitim": 1}).to_list(length=100000)
    ogr_sayi = len(students) or 1
    brut = sum(_num(s.get("yapilan_odeme")) for s in students)
    vergi = 0.0
    try:
        pays = await db.payments.find({"tip": "ogrenci"}, {"_id": 0, "vergi": 1}).to_list(length=200000)
        vergi = sum(_num(p.get("vergi")) for p in pays)
    except Exception:
        pass
    ogt_odenen = 0.0
    for t in await db.teachers.find({}, {"_id": 0, "yapilan_odeme": 1}).to_list(length=5000):
        ogt_odenen += _num(t.get("yapilan_odeme"))
    net = brut - vergi - ogt_odenen
    kur_sayi = await db.kur_ucretleri.estimated_document_count() or 1
    # Tür kırılımı (net ∝ brüt payı — varsayım etiketli)
    tur_brut = {}
    for s in students:
        tur = (s.get("aldigi_egitim") or "?").strip() or "?"
        tur_brut[tur] = tur_brut.get(tur, 0.0) + _num(s.get("yapilan_odeme"))
    tur_net = {t: round(net * (b / (brut or 1)), 2) for t, b in tur_brut.items()}
    return {
        "ltv_ogrenci_basi_net": round(net / ogr_sayi, 2),
        "kur_basi_net_marj": round(net / kur_sayi, 2),
        "toplam_net": round(net, 2),
        "tur_net_kirilim": tur_net,
        "varsayim": "Tür net kırılımı brüt tahsilat oranına göre dağıtılmıştır (yaklaşık).",
    }


async def _kazanim_metrikleri(ref: datetime) -> dict:
    """S6a: öğrenme kazanımı — MEVCUT veriden türetilen proxy (kur ilerlemesi + kazanılan
    rozet). Gerçek okuma-hızı/anlama deltaları ayrı ölçüm gerektirir; burada dürüst bir
    proxy kullanılır ('yontem' etiketli)."""
    students = await db.students.find(
        {"arsivli": {"$ne": True}, "mezun": {"$ne": True}},
        {"_id": 0, "id": 1, "kur": 1, "ogretmen_id": 1, "aldigi_egitim": 1}).to_list(length=100000)
    if not students:
        return {"ort_kazanim": None, "yontem": "veri yok"}
    # Rozet sayıları (öğrenci bazında) — tek sorguda
    rozet_say = {}
    try:
        for r in await db.kazanilan_rozetler.find({}, {"_id": 0, "kullanici_id": 1}).to_list(length=200000):
            rozet_say[r.get("kullanici_id")] = rozet_say.get(r.get("kullanici_id"), 0) + 1
    except Exception:
        pass

    def _kur_no(k):
        import re
        m = re.search(r"\d+", str(k or ""))
        return int(m.group()) if m else 1

    per_ogretmen, per_tur, skorlar = {}, {}, []
    for s in students:
        kn = _kur_no(s.get("kur"))
        rz = rozet_say.get(s.get("id"), 0)
        skor = min(100.0, kn * 15 + rz * 5)  # proxy kazanım skoru
        skorlar.append(skor)
        oid = s.get("ogretmen_id") or "?"
        per_ogretmen.setdefault(oid, []).append(skor)
        tur = (s.get("aldigi_egitim") or "?").strip() or "?"
        per_tur.setdefault(tur, []).append(skor)
    ort = lambda lst: round(sum(lst) / len(lst), 1) if lst else 0
    return {
        "ort_kazanim": ort(skorlar),
        "ogretmen_kazanim": {k: ort(v) for k, v in per_ogretmen.items() if k != "?"},
        "tur_kazanim": {k: ort(v) for k, v in per_tur.items() if k != "?"},
        "yontem": "Proxy: kur ilerlemesi + kazanılan rozet (mevcut veriden türetildi).",
    }


async def _nps_metrikleri(ref: datetime) -> dict:
    """S6d: NPS özeti (sağlık skoru bileşeni)."""
    kayitlar = await db.ai_ceo_nps.find({}, {"_id": 0, "puan": 1}).to_list(length=50000)
    puanlar = [int(k["puan"]) for k in kayitlar if isinstance(k.get("puan"), (int, float))]
    n = len(puanlar)
    if n == 0:
        return {"nps": None, "sayi": 0}
    promoter = sum(1 for p in puanlar if p >= 9)
    detractor = sum(1 for p in puanlar if p <= 6)
    return {"nps": round((promoter - detractor) * 100 / n, 1), "sayi": n,
            "promoter": promoter, "detractor": detractor}


async def _ogrenci_metrikleri(ref: datetime) -> dict:
    students = await db.students.find(
        {}, {"_id": 0, "id": 1, "sinif": 1, "il": 1, "arsivli": 1, "mezun": 1}
    ).to_list(length=100000)
    aktif = [s for s in students if not s.get("arsivli") and not s.get("mezun")]

    sinif = {str(i): 0 for i in range(1, 9)}
    sinif["?"] = 0
    il = {}
    for s in aktif:
        n = normalize_sinif(s.get("sinif"))
        sinif[str(n) if isinstance(n, int) and 1 <= n <= 8 else "?"] += 1
        ilad = (s.get("il") or "").strip()
        if ilad:
            il[ilad] = il.get(ilad, 0) + 1

    # Risk dağılımı (risk koleksiyonu varsa)
    risk = {}
    try:
        for seviye in ("dusuk", "orta", "yuksek"):
            risk[seviye] = await db.ogrenci_riskleri.count_documents({"risk_seviyesi": seviye})
        if sum(risk.values()) == 0:
            risk = {}
    except Exception:
        risk = {}

    en_yogun_il = sorted(il.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        "toplam": len(students),
        "aktif": len(aktif),
        "sinif_dagilimi": sinif,
        "il_dagilimi_top5": [{"il": k, "sayi": v} for k, v in en_yogun_il],
        "risk_dagilimi": risk,
    }


async def _kullanim_metrikleri(ref: datetime) -> dict:
    otuz_gun = (ref - timedelta(days=30)).isoformat()
    # Görev tamamlama
    gorev_toplam = gorev_bitmis = 0
    try:
        gorev_toplam = await db.gorevler.count_documents({})
        gorev_bitmis = await db.gorevler.count_documents({"durum": "tamamlandi"})
    except Exception:
        pass
    # SSS temaları (kategori frekansı)
    sss_temalar = {}
    try:
        for koll in ("sss_sorular", "sss"):
            docs = await db[koll].find({}, {"_id": 0, "kategori": 1}).to_list(length=5000)
            for d in docs:
                kat = (d.get("kategori") or "genel").strip()
                sss_temalar[kat] = sss_temalar.get(kat, 0) + 1
            if sss_temalar:
                break
    except Exception:
        pass
    return {
        "gorev_tamamlama_yuzde": round(gorev_bitmis * 100 / gorev_toplam, 1) if gorev_toplam else None,
        "gorev_toplam": gorev_toplam,
        "sss_tema_dagilimi": dict(sorted(sss_temalar.items(), key=lambda x: x[1], reverse=True)[:8]),
        "son_30gun_esik": otuz_gun,
    }


# ─────────────────────────── otonom envanter ───────────────────────────
_ZAMAN_ALANLARI = ["tarih", "olusturma_tarihi", "created_at", "baslangic_tarihi",
                   "kayit_zamani", "guncelleme_tarihi", "zaman"]


async def _otonom_envanter(ref: datetime) -> dict:
    """Tüm koleksiyonların jenerik özeti (sayı + son 7/30 gün hareket). DEĞER taşımaz."""
    yedi = (ref - timedelta(days=7)).isoformat()
    otuz = (ref - timedelta(days=30)).isoformat()
    env = {}
    try:
        adlar = await db.list_collection_names()
    except Exception as e:
        logging.warning(f"[ai_ceo] envanter koleksiyon listesi alınamadı: {e}")
        return {}
    for ad in sorted(adlar):
        try:
            toplam = await db[ad].estimated_document_count()
            ozet = {"kayit": toplam}
            # Hangi zaman alanı mevcut? İlk dokümandan tespit
            ornek = await db[ad].find_one({}, {"_id": 0})
            zaman_alan = next((z for z in _ZAMAN_ALANLARI if ornek and z in ornek), None)
            if zaman_alan and toplam:
                ozet["son_7gun"] = await db[ad].count_documents({zaman_alan: {"$gte": yedi}})
                ozet["son_30gun"] = await db[ad].count_documents({zaman_alan: {"$gte": otuz}})
                ozet["zaman_alani"] = zaman_alan
            env[ad] = ozet
        except Exception:
            continue
    # Atıl özellik ipucu: son 30 günde hiç hareketi olmayan (zaman alanı olan) koleksiyonlar
    atil = [ad for ad, o in env.items()
            if o.get("zaman_alani") and o.get("kayit", 0) > 0 and o.get("son_30gun", 0) == 0]
    return {"koleksiyonlar": env, "atil_ozellik_adaylari": atil, "koleksiyon_sayisi": len(env)}


# ─────────────────────────── ana servis ───────────────────────────
async def sistem_fotografi() -> dict:
    """Deterministik sistem fotoğrafı (agregat, KVKK-güvenli). AI'dan önce çalışır."""
    ref = simdi()
    bloklar = {}
    for ad, fn in (("ogretmen", _ogretmen_metrikleri), ("muhasebe", _muhasebe_metrikleri),
                   ("ogrenci", _ogrenci_metrikleri), ("kullanim", _kullanim_metrikleri),
                   ("konsantrasyon", _konsantrasyon_metrikleri), ("birim_ekonomi", _birim_ekonomi_metrikleri),
                   ("kazanim", _kazanim_metrikleri), ("nps", _nps_metrikleri)):
        try:
            bloklar[ad] = await fn(ref)
        except Exception as e:
            logging.warning(f"[ai_ceo] fotoğraf blok '{ad}' hatası: {e}")
            bloklar[ad] = {"_hata": str(e)[:120]}
    try:
        bloklar["envanter"] = await _otonom_envanter(ref)
    except Exception as e:
        bloklar["envanter"] = {"_hata": str(e)[:120]}

    return {
        "id": str(uuid.uuid4()),
        "tarih": ref.isoformat(),
        "surum": 1,
        **bloklar,
    }


def ai_payload(fotograf: dict) -> dict:
    """Fotoğrafın AI'a gönderilecek KVKK-güvenli alt kümesi. İç kayıt alanlarını çıkarır."""
    return {k: v for k, v in (fotograf or {}).items()
            if k not in ("_id", "_takma_harita")}


async def fotograf_kaydet(fotograf: dict) -> dict:
    await db.ai_ceo_fotograflar.insert_one({**fotograf})
    fotograf.pop("_id", None)
    return fotograf


async def son_fotograf() -> dict | None:
    doc = await db.ai_ceo_fotograflar.find_one({}, sort=[("tarih", -1)])
    if doc:
        doc.pop("_id", None)
    return doc


# ─────────────────────────── endpointler ───────────────────────────
def saglik_skoru(fotograf: dict) -> dict:
    """Fotoğraftan 0-100 bileşenli genel sağlık skoru (deterministik, AI'sız)."""
    if not fotograf:
        return {"skor": None, "bilesenler": []}
    m = fotograf.get("muhasebe", {}) or {}
    o = fotograf.get("ogretmen", {}) or {}
    k = fotograf.get("kullanim", {}) or {}

    def _clamp(v):
        return max(0.0, min(100.0, v))

    bilesenler = []
    # 1) Tahsilat sağlığı = tahsil / beklenen
    bek = _num(m.get("beklenen_tahsilat")); tah = _num(m.get("tahsil_edilen"))
    tahsilat = _clamp(tah * 100 / bek) if bek > 0 else 100.0
    bilesenler.append({"ad": "Tahsilat", "puan": round(tahsilat, 0), "agirlik": 0.25})
    # 2) Yenileme oranı (0-100 zaten)
    yen = o.get("yenileme_orani_yuzde")
    if yen is not None:
        bilesenler.append({"ad": "Yenileme", "puan": round(_clamp(_num(yen)), 0), "agirlik": 0.25})
    # 3) Veli memnuniyeti (5 üzerinden → 100)
    mem = o.get("veli_memnuniyeti_5uzerinden")
    if mem is not None:
        bilesenler.append({"ad": "Memnuniyet", "puan": round(_clamp(_num(mem) * 20), 0), "agirlik": 0.25})
    # 4) Gecikme sağlığı (geciken kur ne kadar azsa o kadar iyi)
    gec = _num(o.get("geciken_kur_sayisi"))
    aktif_ogr = _num((fotograf.get("ogrenci", {}) or {}).get("aktif")) or 1
    gecikme = _clamp(100 - (gec * 100 / max(1, aktif_ogr)))
    bilesenler.append({"ad": "Zamanında Kur", "puan": round(gecikme, 0), "agirlik": 0.15})
    # 5) Görev tamamlama (kullanım)
    gt = k.get("gorev_tamamlama_yuzde")
    if gt is not None:
        bilesenler.append({"ad": "Katılım", "puan": round(_clamp(_num(gt)), 0), "agirlik": 0.10})
    # 6) NPS (S6d) — (-100..100) → (0..100)
    nps = (fotograf.get("nps", {}) or {}).get("nps")
    if nps is not None:
        bilesenler.append({"ad": "NPS", "puan": round(_clamp((_num(nps) + 100) / 2), 0), "agirlik": 0.15})

    tw = sum(b["agirlik"] for b in bilesenler) or 1
    skor = round(sum(b["puan"] * b["agirlik"] for b in bilesenler) / tw, 0)
    return {"skor": skor, "bilesenler": bilesenler}


@router.get("/ai/ceo/saglik")
async def saglik_endpoint(current_user=Depends(_ADMIN)):
    foto = await son_fotograf()
    return {"saglik": saglik_skoru(foto) if foto else {"skor": None, "bilesenler": []},
            "fotograf_tarih": foto.get("tarih") if foto else None}


@router.post("/ai/ceo/fotograf/cek")
async def fotograf_cek(current_user=Depends(_ADMIN)):
    foto = await sistem_fotografi()
    await fotograf_kaydet(foto)
    # S6c: konsantrasyon eşiği aşılırsa Ayda kuyruğuna risk azaltma görevi ekle
    try:
        from .anomali import konsantrasyon_gorevi
        await konsantrasyon_gorevi(foto)
    except Exception as e:
        logging.warning(f"[ai_ceo] konsantrasyon görevi hatası: {e}")
    return {"ok": True, "tarih": foto["tarih"], "fotograf": foto}


@router.get("/ai/ceo/fotograf/son")
async def fotograf_son(current_user=Depends(_ADMIN)):
    foto = await son_fotograf()
    return {"fotograf": foto}


@router.get("/ai/ceo/fotograf/gecmis")
async def fotograf_gecmis(current_user=Depends(_ADMIN)):
    docs = await db.ai_ceo_fotograflar.find({}, {"_id": 0, "id": 1, "tarih": 1}).sort("tarih", -1).to_list(length=60)
    return {"fotograflar": docs}
