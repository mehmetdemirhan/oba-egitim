"""AI CEO — Deniz Güçlendirme Paketi (S9). Deterministik denetim mekanizmaları.

9b veri kalitesi · 9c sayı doğrulama · 9d ret otopsisi · 9e insan çıktı örneklemi (guard) ·
9f maliyet denetimi · 9g bağımsız ikinci göz · 9a sınav (deniz.py'de endpoint).
Tümü deterministik kaynaklardan; bulgu şekli deniz.py ile aynı (tur/onem/ozet/kanit).
"""
import re

from core.db import db
from core.zaman import simdi, aware as _aware

from .fotograf import son_fotograf, ai_payload, _num
from .analiz import _duz_degerler, _sayisal_kume
from .ortak import metrik_al, KATEGORI_METRIK
from .personalar import MIRAN_YASAK_ORUNTULER, MIRAN_PARA_ORUNTULER, MIRAN_PEDAGOJIK_ORUNTULER


# ─────────────────────── 9b: Veri Kalitesi Denetimi ───────────────────────
async def veri_kalitesi_kontrol() -> list:
    b = []
    students = await db.students.find({}, {"_id": 0, "id": 1, "arsivli": 1, "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1}).to_list(length=100000)
    ogr_ids = {s["id"] for s in students}
    kurlar = await db.kur_ucretleri.find({}, {"_id": 0}).to_list(length=50000)

    yetim = [k for k in kurlar if k.get("ogrenci_id") not in ogr_ids]
    if yetim:
        b.append({"tur": "yetim_kayit", "onem": "kritik", "ozet": f"{len(yetim)} yetim kur kaydı (öğrencisi yok).",
                  "kanit": {"sayi": len(yetim), "ornekler": [{"tip": "kur", "kur_id": k.get("id"), "ogrenci_id": k.get("ogrenci_id")} for k in yetim[:10]]}})
    neg = [k for k in kurlar if _num(k.get("tutar")) < 0 or _num(k.get("yapilan_odeme")) < 0]
    neg += [s for s in students if _num(s.get("yapilan_odeme")) < 0]
    if neg:
        b.append({"tur": "negatif_kayit", "onem": "kritik", "ozet": f"{len(neg)} negatif tutarlı kayıt.",
                  "kanit": {"sayi": len(neg), "ornekler": [{"tip": "kayit", "id": r.get("id")} for r in neg[:10]]}})
    ars_borc = [s for s in students if s.get("arsivli") and (_num(s.get("yapilmasi_gereken_odeme")) - _num(s.get("yapilan_odeme"))) > 0.01]
    if ars_borc:
        b.append({"tur": "arsivli_acik_alacak", "onem": "orta", "ozet": f"{len(ars_borc)} arşivli öğrencide açık alacak.",
                  "kanit": {"sayi": len(ars_borc), "ornekler": [{"tip": "ogrenci", "ogrenci_id": s.get("id"),
                            "kalan": round(_num(s.get("yapilmasi_gereken_odeme")) - _num(s.get("yapilan_odeme")), 2)} for s in ars_borc[:10]]}})
    # KALİBRE: Hakediş öğretmenin "yeni kur / eğitim tamamlandı" işaretiyle (durum=tamamlandi)
    # + ödemenin bitmesiyle (kalan≈0) oluşur. Yalnız ödeme bitmesi ya da yalnız eğitim
    # tamamlanması (biri eksik) NORMAL bekleme durumudur → hata DEĞİL. Sadece İKİSİ de olduğu
    # halde damga (odeme_tamamlanma_tarihi) yoksa gerçek eksiktir (backfill ile giderilir).
    damgasiz = [k for k in kurlar if k.get("durum") == "tamamlandi"
                and (_num(k.get("tutar")) - _num(k.get("yapilan_odeme"))) <= 0.01
                and not k.get("odeme_tamamlanma_tarihi")]
    if damgasiz:
        b.append({"tur": "damgasiz_hakedis", "onem": "orta", "ozet": f"{len(damgasiz)} tamamlanmış+ödemesi biten kurda hakediş damgası eksik.",
                  "kanit": {"sayi": len(damgasiz), "ornekler": [{"tip": "kur", "kur_id": k.get("id"), "ogrenci_id": k.get("ogrenci_id")} for k in damgasiz[:10]]}})
    try:
        pay_novergi = await db.payments.count_documents({"tip": "ogrenci", "vergi": {"$in": [None]}})
        if pay_novergi > 0:
            b.append({"tur": "vergi_snapshot_eksik", "onem": "dusuk", "ozet": f"{pay_novergi} ödemede vergi snapshot'ı yok.", "kanit": {"sayi": pay_novergi}})
    except Exception:
        pass
    return b


# ─────────────────────── 9c: Sayı Doğrulama ───────────────────────
async def sayi_dogrulama_kontrol(fotograf: dict) -> tuple:
    """Son önerilerdeki sayıları fotoğrafla karşılaştırır. (bulgular, dogrulanamayan_oran)."""
    duz = _duz_degerler(ai_payload(fotograf or {}))
    sayilar = _sayisal_kume(duz)
    oneriler = await db.ai_ceo_oneriler.find({}, {"_id": 0, "id": 1, "ozet": 1, "beklenen_etki": 1}).sort("tarih", -1).to_list(length=100)
    toplam = dogrulanamayan = 0
    ornekler = []
    for o in oneriler:
        metin = f"{o.get('ozet','')} {o.get('beklenen_etki','')}"
        for ham in re.findall(r"\d+[.,]?\d*", metin):
            try:
                n = round(float(ham.replace(",", ".")), 2)
            except ValueError:
                continue
            if n < 5:
                continue
            toplam += 1
            if not any(abs(n - x) <= max(0.5, abs(x) * 0.02) for x in sayilar):
                dogrulanamayan += 1
                if len(ornekler) < 10:
                    ornekler.append({"tip": "oneri", "oneri_id": o.get("id"), "sayi": n, "cumle": metin.strip()[:160]})
    oran = round(dogrulanamayan * 100 / toplam, 1) if toplam else 0.0
    b = []
    if toplam >= 5 and oran > 30:
        b.append({"tur": "dogrulanamayan_sayi", "onem": "orta",
                  "ozet": f"Ayda metinlerindeki sayıların %{oran}'i fotoğrafla eşleşmiyor.",
                  "kanit": {"dogrulanamayan": dogrulanamayan, "toplam": toplam, "ornekler": ornekler}})
    return b, oran


# ─────────────────────── 9e: İnsana Giden Çıktı Örneklemi (guard) ───────────────────────
async def insan_ciktisi_ornek() -> list:
    b = []
    yasak = MIRAN_YASAK_ORUNTULER
    # Öğretmen Miran'ı: kıyas/ceza + tutar sızıntısı yasak
    ogr = await db.ai_ceo_miran.find({"ogretmen_id": {"$ne": "_muhasebe"}}, {"_id": 0, "icerik": 1}).sort("tarih", -1).to_list(length=20)
    for m in ogr:
        blob = str(m.get("icerik", "")).lower()
        ihlal = next((p for p in yasak + MIRAN_PARA_ORUNTULER if p in blob), None)
        if ihlal:
            b.append({"tur": "ciktı_ihlali", "onem": "kritik", "ozet": f"Öğretmen Miran çıktısında yasaklı ifade: '{ihlal}' — guard güçlendirilmeli.", "kanit": {"ihlal": ihlal}})
            break
    # Muhasebe Miran'ı: kıyas/ceza + pedagojik sızıntı yasak (tutar serbest)
    muh = await db.ai_ceo_miran.find({"ogretmen_id": "_muhasebe"}, {"_id": 0, "icerik": 1}).sort("tarih", -1).to_list(length=20)
    for m in muh:
        blob = str(m.get("icerik", "")).lower()
        ihlal = next((p for p in yasak + MIRAN_PEDAGOJIK_ORUNTULER if p in blob), None)
        if ihlal:
            b.append({"tur": "ciktı_ihlali", "onem": "kritik", "ozet": f"Muhasebe Miran çıktısında sızıntı: '{ihlal}' — guard güçlendirilmeli.", "kanit": {"ihlal": ihlal}})
            break
    return b


# ─────────────────────── 9f: Maliyet Denetimi ───────────────────────
async def maliyet_ozet() -> dict:
    loglar = await db.ai_request_log.find({}, {"_id": 0, "model": 1, "tarih": 1, "grounded": 1, "ozellik": 1}).to_list(length=200000)
    ay_say = {}
    model_say = {}
    ozellik_say = {}  # özellik-bazlı çağrı kırılımı (merkezi sayaç etiketinden)
    grounded = 0
    for l in loglar:
        ay = str(l.get("tarih", ""))[:7]
        if ay:
            ay_say[ay] = ay_say.get(ay, 0) + 1
        model_say[l.get("model", "?")] = model_say.get(l.get("model", "?"), 0) + 1
        oz = l.get("ozellik") or "etiketsiz"  # eski loglarda etiket yok
        ozellik_say[oz] = ozellik_say.get(oz, 0) + 1
        if l.get("grounded"):
            grounded += 1
    aylar = sorted(ay_say.items())
    sicrama = None
    if len(aylar) >= 2 and aylar[-2][1] > 0:
        artis = (aylar[-1][1] - aylar[-2][1]) * 100 / aylar[-2][1]
        if artis >= 100:
            sicrama = round(artis, 0)
    ozellik_dagilimi = dict(sorted(ozellik_say.items(), key=lambda x: -x[1]))
    return {"toplam_cagri": len(loglar), "ay_dagilimi": dict(aylar[-6:]), "model_dagilimi": model_say,
            "ozellik_dagilimi": ozellik_dagilimi, "grounded_cagri": grounded, "anormal_sicrama_yuzde": sicrama}


async def maliyet_bulgu() -> list:
    m = await maliyet_ozet()
    if m.get("anormal_sicrama_yuzde"):
        return [{"tur": "maliyet_sicramasi", "onem": "orta",
                 "ozet": f"AI çağrı sayısı son ay %{m['anormal_sicrama_yuzde']:.0f} arttı.",
                 "kanit": {"ay_dagilimi": m["ay_dagilimi"], "ozellik_dagilimi": m.get("ozellik_dagilimi", {})}}]
    return []


# ─────────────────────── 9g: Bağımsız İkinci Göz ───────────────────────
# Deniz'in KENDİ (daha sıkı) eşikleri — Ayda/anomali kod yolundan bağımsız
DENIZ_ESIK = {"konsantrasyon": 20.0, "geciken_kur": 5, "nps": 10}


async def ikinci_goz(fotograf: dict) -> list:
    """Deniz'in kendi eşikleriyle çapraz kontrol → Ayda/anomali'nin kaçırdıkları."""
    b = []
    kons = metrik_al(fotograf, "konsantrasyon.en_buyuk_ogretmen_ogrenci_payi", 0) or 0
    if kons > DENIZ_ESIK["konsantrasyon"]:
        # Ayda anomalisi %25 eşik; Deniz %20 → aradaki bant "kaçırılan"
        if kons <= 25:
            b.append({"tur": "ikinci_goz_konsantrasyon", "onem": "dusuk",
                      "ozet": f"Konsantrasyon %{kons} — Deniz eşiğini (%20) aşıyor ama Ayda eşiğinin (%25) altında (erken uyarı).",
                      "kanit": {"deger": kons}})
    gec = metrik_al(fotograf, "ogretmen.geciken_kur_sayisi", 0) or 0
    if DENIZ_ESIK["geciken_kur"] <= gec < 10:
        b.append({"tur": "ikinci_goz_gecikme", "onem": "dusuk",
                  "ozet": f"{gec} geciken kur — Deniz eşiği (5) aşıldı, Ayda eşiği (10) altında.",
                  "kanit": {"deger": gec}})
    return b


# ─────────────────────── 9d: Ret Otopsisi ───────────────────────
async def ret_otopsisi() -> dict:
    """Reddedilen öneriler 30+ gün sonra yeniden değerlendirilir (çift yönlü kalibrasyon)."""
    son_foto = await son_fotograf()
    reddedilenler = await db.ai_ceo_oneriler.find({"durum": "reddedildi"}, {"_id": 0}).to_list(length=1000)
    now = simdi()
    hakli_cikti = isabetliydi = beklemede = 0
    for o in reddedilenler:
        d = _aware(o.get("durum_tarih") or o.get("tarih"))
        if not d or (now - d).days < 30:
            beklemede += 1
            continue
        yol, yon = KATEGORI_METRIK.get(o.get("kategori"), (None, "artis"))
        if not yol:
            beklemede += 1
            continue
        simdiki = metrik_al(son_foto or {}, yol)
        try:
            simdiki = float(simdiki)
        except (TypeError, ValueError):
            beklemede += 1
            continue
        # İlgili metrik reddedilenden bu yana KÖTÜLEŞTİYSE → "ret sonrası haklı çıktı" (öneri işe yarardı)
        onceki = o.get("_karar_ani_metrik")
        if onceki is None:
            beklemede += 1
            continue
        kotulesti = (simdiki < onceki) if yon == "artis" else (simdiki > onceki)
        if kotulesti:
            hakli_cikti += 1
        else:
            isabetliydi += 1
    return {"reddedilen": len(reddedilenler), "ret_sonrasi_hakli_cikti": hakli_cikti,
            "ret_isabetliydi": isabetliydi, "beklemede": beklemede}
