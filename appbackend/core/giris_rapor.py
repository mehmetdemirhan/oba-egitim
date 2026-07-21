"""Giriş Analizi Raporu — etiket haritaları, sınıf-kategori yapılandırması ve
kural-tabanlı "Sonuç ve Genel Yorum" metin bankası.

Tasarım ilkeleri:
- AI ORİJİNAL METİN ÜRETMEZ. Sonuç paragrafı, önceden yazılmış ve admin/koordinatör
  tarafından düzenlenebilir bir metin bankasından, ölçüm bantlarına (okuma hızı düzeyi
  × doğruluk × anlama % × prozodik) göre DETERMİNİSTİK birleştirilir (TIMI deseni).
- Ham enum/kod (örn. "olcum", "harf_atlama") kullanıcıya asla gösterilmez; buradaki
  haritalardan okunabilir Türkçe karşılıkları çekilir.
"""
from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════
# B) METİN TÜRÜ etiketleri — ham enum → okunabilir Türkçe
# ═══════════════════════════════════════════════════════════════════
METIN_TURU_ETIKET = {
    "olcum": "Ölçüm Metni",
    "analiz": "Okuma Metni",
    "okuma_parcalari": "Okuma Parçası",
    "hikaye": "Hikâye",
    "bilgilendirici": "Bilgilendirici Metin",
    "bilgi": "Bilgilendirici Metin",
    "siir": "Şiir",
    "deneme": "Deneme",
    "masal": "Masal",
    "ani": "Anı",
    "akici_okuma": "Okuma Metni",
}


# ═══════════════════════════════════════════════════════════════════
# OKUMA HIZI MAKUL ARALIK KONTROLÜ (v2 #1) — bozuk/ölçülemeyen veriyi veliye
# "672 kelime/dk, İleri Düzey" gibi yanlış güvenle sunmayı engelle.
# İnsan okuma hızı en hızlı okuyucularda bile ~400 kelime/dk altındadır; 1. sınıf
# alt sınırı ~20. Aralık dışı → rapor "anomali" işaretlenir, uyarı gösterilir.
# ═══════════════════════════════════════════════════════════════════
WPM_MAKUL_MIN = 20
WPM_MAKUL_MAX = 400
SURE_MIN_SANIYE = 10   # 30+ kelimelik metinde <10 sn = kronometre gerçek okumayı ölçmemiş


def wpm_anomali(wpm, sure_saniye=None, kelime_sayisi=None) -> tuple:
    """(anomali: bool, sebep: str). Okuma hızı/süre olağandışıysa anomali işaretler."""
    try:
        w = float(wpm or 0)
    except Exception:
        return True, "Okuma hızı hesaplanamadı — veri kontrol edilmeli."
    if w <= 0:
        return True, "Okuma hızı ölçülemedi (0) — süre/kelime verisi kontrol edilmeli."
    if w > WPM_MAKUL_MAX:
        return True, (f"Okuma hızı olağandışı YÜKSEK ({int(w)} kelime/dk) — okuma süresi çok "
                      "kısa görünüyor; kronometre gerçek okuma süresini yansıtmıyor olabilir.")
    if w < WPM_MAKUL_MIN:
        return True, (f"Okuma hızı olağandışı DÜŞÜK ({int(w)} kelime/dk) — süre/kelime ölçümü "
                      "kontrol edilmeli.")
    try:
        s = float(sure_saniye) if sure_saniye is not None else None
    except Exception:
        s = None
    if s is not None and 0 < s < SURE_MIN_SANIYE and (kelime_sayisi or 0) > 30:
        return True, (f"Okuma süresi çok kısa ({int(s)} sn) — kronometre gerçek okuma süresini "
                      "yansıtmıyor olabilir.")
    return False, ""


def metin_turu_ad(deger: str | None) -> str:
    """Ham metin türü kodunu okunabilir Türkçe etikete çevirir (ham kodu asla gösterme)."""
    if not deger:
        return "Okuma Metni"
    v = str(deger).strip().lower()
    if v in METIN_TURU_ETIKET:
        return METIN_TURU_ETIKET[v]
    # Zaten insan-okunur (boşluk/büyük harf içeriyor) ise olduğu gibi bırak
    if " " in deger or deger[:1].isupper():
        return deger
    return deger.replace("_", " ").title()


# ═══════════════════════════════════════════════════════════════════
# C) HATA TÜRÜ etiketleri — 18 tür, 4 kategori (kaynak: "Hata Çeşitleri.docx")
# ═══════════════════════════════════════════════════════════════════
HATA_TURU_ETIKET = {
    # Atlama
    "harf_atlama": "Harf Atlama", "hece_atlama": "Hece Atlama",
    "kelime_atlama": "Kelime Atlama", "satir_atlama": "Satır Atlama",
    # Ekleme
    "harf_ekleme": "Harf Ekleme", "hece_ekleme": "Hece Ekleme",
    "kelime_ekleme": "Kelime Ekleme", "satir_ekleme": "Satır Ekleme",
    # Yer değiştirme / ters çevirme
    "tersten_okuma": "Tersten Okuma", "harf_sira_degistirme": "Harflerin Sırasını Değiştirme",
    "kelime_sira_degistirme": "Kelimelerin Sırasını Değiştirme",
    "harf_uzamsal_ters": "Harfleri Uzamsal Olarak Ters Çevirme",
    # Diğer
    "tekrar_etme": "Tekrar Etme", "duraklama": "Duraklama",
    "yanlis_heceleme": "Hecelerine Yanlış Ayırma", "akici_okuyamama": "Akıcı Okuyamama",
    "kendi_kendine_duzeltme": "Kendi Kendine Düzeltme", "yanlis_okuma": "Yanlış Okuma",
    # Eski/kısa anahtarlar (geriye dönük)
    "atlama": "Atlama", "ekleme": "Ekleme", "yanlis": "Yanlış Okuma",
    "takilma": "Takılma", "tekrar": "Tekrar Etme",
}

HATA_TURU_ACIKLAMA = {
    "harf_atlama": "Kelimedeki bir harfi okumadan geçme",
    "hece_atlama": "Bir heceyi atlayarak okuma",
    "kelime_atlama": "Bir kelimeyi okumadan geçme",
    "satir_atlama": "Bir satırı atlayarak okuma",
    "harf_ekleme": "Kelimeye olmayan bir harf ekleme",
    "hece_ekleme": "Kelimeye fazladan hece ekleme",
    "kelime_ekleme": "Metinde olmayan kelime ekleme",
    "satir_ekleme": "Aynı satırı yeniden okuma",
    "tersten_okuma": "Kelimeyi/harfleri tersten okuma",
    "harf_sira_degistirme": "Harflerin yerini değiştirerek okuma",
    "kelime_sira_degistirme": "Kelimelerin sırasını değiştirme",
    "harf_uzamsal_ters": "Benzer harfleri (b/d, m/n) karıştırma",
    "tekrar_etme": "Aynı kelimeyi tekrar okuma",
    "duraklama": "Kelimede duraksama",
    "yanlis_heceleme": "Kelimeyi hecelerine yanlış ayırma",
    "akici_okuyamama": "Kesik kesik, akıcı olmayan okuma",
    "kendi_kendine_duzeltme": "Hatayı fark edip düzeltme",
    "yanlis_okuma": "Kelimeyi farklı okuma",
    "atlama": "Kelime veya satır atlama", "takilma": "Kelimede duraksama",
    "yanlis": "Kelimeyi farklı okuma", "tekrar": "Aynı kelimeyi tekrar okuma",
}


def hata_turu_ad(anahtar: str) -> str:
    """Ham hata türü anahtarını okunabilir Türkçe etikete çevirir (tutarlı, C maddesi)."""
    if not anahtar:
        return "-"
    a = str(anahtar).strip()
    if a in HATA_TURU_ETIKET:
        return HATA_TURU_ETIKET[a]
    if a.lower() in HATA_TURU_ETIKET:
        return HATA_TURU_ETIKET[a.lower()]
    if " " in a or a[:1].isupper():   # zaten insan-okunur
        return a
    return a.replace("_", " ").title()


def hata_turu_aciklama(anahtar: str) -> str:
    a = str(anahtar or "").strip().lower()
    return HATA_TURU_ACIKLAMA.get(a, "")


# ═══════════════════════════════════════════════════════════════════
# EK) SINIF SEVİYESİNE GÖRE ÖLÇÜM KATEGORİLERİ (4.1–4.4 aktif/pasif)
# 4.5 (Soru Performans Analizi) her zaman aktiftir (kapsam dışı).
# Varsayılan: 1. sınıf → 4.1–4.4 pasif; diğer tüm sınıflar → hepsi aktif.
# ═══════════════════════════════════════════════════════════════════
ANLAMA_GRUP_ANAHTARLARI = ["4.1", "4.2", "4.3", "4.4"]   # 4.5 dâhil değil (hep aktif)

SINIF_KATEGORI_VARSAYILAN = {
    # sınıf (str) → o sınıfta PASİF olan grup anahtarları
    "1": ["4.1", "4.2", "4.3", "4.4"],
}


def pasif_gruplar(cfg: dict | None, sinif) -> set:
    """Verilen sınıf için PASİF ölçüm gruplarını döner (yalnız 4.1–4.4 kısılabilir)."""
    cfg = cfg or SINIF_KATEGORI_VARSAYILAN
    s = str(sinif or "").strip()
    liste = cfg.get(s, [])
    return {g for g in liste if g in ANLAMA_GRUP_ANAHTARLARI}


def grup_aktif_mi(cfg: dict | None, sinif, grup_anahtar: str) -> bool:
    """'4.1'..'4.5' grubu bu sınıf için aktif mi? (4.5 her zaman aktif)"""
    if grup_anahtar == "4.5":
        return True
    return grup_anahtar not in pasif_gruplar(cfg, sinif)


def aktif_grup_anahtarlari(cfg: dict | None, sinif) -> list:
    """Bu sınıf için aktif grup anahtarları (4.5 dâhil, sıralı)."""
    pasif = pasif_gruplar(cfg, sinif)
    return [g for g in ANLAMA_GRUP_ANAHTARLARI if g not in pasif] + ["4.5"]


# Her ölçüm grubunun ölçüt (kriter) anahtarları — % hesabından pasif grupları
# çıkarmak için (EK #3). 4.5 Bloom soru performansı her zaman aktif.
ANLAMA_GRUP_OLCUTLERI = {
    "4.1": ["cumle_anlama", "bilinmeyen_sozcuk", "baglac_zamir"],
    "4.2": ["ana_fikir", "yardimci_fikir", "konu", "baslik_onerme"],
    "4.3": ["neden_sonuc", "cikarim", "ipuclari", "yorumlama"],
    "4.4": ["gorus_bildirme", "yazar_amaci", "alternatif_fikir", "guncelle_hayat"],
    "4.5": ["bilgi", "kavrama", "uygulama", "analiz", "sentez", "degerlendirme"],
}


def pasif_olcut_anahtarlari(cfg: dict | None, sinif) -> set:
    keys = set()
    for g in pasif_gruplar(cfg, sinif):
        keys.update(ANLAMA_GRUP_OLCUTLERI.get(g, []))
    return keys


def aktif_anlama_dict(anlama: dict | None, cfg: dict | None, sinif) -> dict:
    """Pasif grupların ölçütlerini anlama sözlüğünden ÇIKARIR — % orantısı yalnız
    mevcut (aktif) kategoriler üzerinden hesaplansın diye (EK #3, forma bağlı değil)."""
    pasif = pasif_olcut_anahtarlari(cfg, sinif)
    return {k: v for k, v in (anlama or {}).items() if k not in pasif}


# ═══════════════════════════════════════════════════════════════════
# A) "SONUÇ VE GENEL YORUM" METİN BANKASI (bantlı, deterministik, düzenlenebilir)
# ═══════════════════════════════════════════════════════════════════
# Bantlar:
#   hiz_duzey:  dusuk | orta | yeterli | ileri
#   dogruluk:   zayif (<85) | orta (85–94) | iyi (>=95)
#   anlama:     zayif (<70) | orta (70–84) | iyi (>=85)
#   prozodik:   gelistirilmeli (<10) | orta (10–13) | iyi (14–17) | cokiyi (>=18)
#   kapanis:    genel düzey → dusuk | orta | iyi
# {ad} yer tutucusu öğrenci adıyla değiştirilir.

GIRIS_RAPOR_METIN_VARSAYILAN = {
    "giris": "{ad}, giriş analizinde okuma becerileri dört boyutta değerlendirilmiştir. "
             "Aşağıda mevcut durumu, güçlü yönleri ve gelişime açık alanları özetlenmiştir.",
    "hiz": {
        "dusuk": "Okuma hızı sınıf düzeyi normlarının altındadır; bu, okuma otomatikliğinin "
                 "henüz gelişmekte olduğunu gösterir. Düzenli sesli okuma ve tekrarlı okuma "
                 "çalışmaları hızın artmasına yardımcı olacaktır.",
        "orta": "Okuma hızı orta düzeydedir; temel okuma akıcılığı oluşmaya başlamıştır. "
                "Günlük kısa okuma seansları hızı istikrarlı biçimde yukarı taşıyacaktır.",
        "yeterli": "Okuma hızı sınıf düzeyi için yeterlidir; öğrenci metni rahat bir tempoda "
                   "okuyabilmektedir. Bu düzeyin korunması ve çeşitlendirilmesi önerilir.",
        "ileri": "Okuma hızı sınıf düzeyinin üzerindedir; okuma otomatikliği güçlüdür. "
                 "Daha zengin ve uzun metinlerle bu güç desteklenebilir.",
    },
    "dogruluk": {
        "zayif": "Doğru okuma oranı geliştirilmelidir; kelime tanıma ve dikkat çalışmaları "
                 "hata sayısını azaltacaktır.",
        "orta": "Doğru okuma oranı iyi seviyededir; birkaç türde hata dikkatle azaltılabilir.",
        "iyi": "Doğru okuma oranı çok iyidir; öğrenci metni yüksek doğrulukla okumaktadır.",
    },
    "anlama": {
        "zayif": "Okuduğunu anlama becerisi desteklenmelidir; okuma sonrası soru-cevap ve "
                 "özetleme çalışmaları anlamayı güçlendirecektir.",
        "orta": "Okuduğunu anlama orta düzeydedir; derinlemesine anlama etkinlikleriyle "
                "beceri üst seviyeye taşınabilir.",
        "iyi": "Okuduğunu anlama becerisi güçlüdür; öğrenci metnin anlamını başarıyla "
               "kavramaktadır.",
    },
    "prozodik": {
        "gelistirilmeli": "Prozodik okuma (vurgu, tonlama, noktalamaya uyum) geliştirilmelidir; "
                          "örnek okuma dinleme ve model okuma faydalı olacaktır.",
        "orta": "Prozodik okuma gelişmektedir; noktalama ve vurguya dikkat ederek okuma "
                "akıcılığı artırılabilir.",
        "iyi": "Prozodik okuma iyi düzeydedir; öğrenci metni anlamlı gruplara ayırarak "
               "okuyabilmektedir.",
        "cokiyi": "Prozodik okuma çok iyidir; öğrenci doğal ve etkileyici bir tonlamayla "
                  "okumaktadır.",
    },
    "kapanis": {
        "dusuk": "Genel olarak okuma becerilerinin temelleri atılmakta olup düzenli okuma "
                 "alışkanlığı ve öğretmen rehberliğinde çalışmalarla belirgin ilerleme "
                 "beklenmektedir. Önerilen adım: her gün 10–15 dakikalık sesli okuma.",
        "orta": "Genel olarak okuma becerileri gelişim yolundadır; güçlü yönler korunarak "
                "gelişime açık alanlara odaklanılması önerilir. Önerilen adım: seviyeye "
                "uygun metinlerle düzenli okuma ve anlama çalışmaları.",
        "iyi": "Genel olarak okuma becerileri sınıf düzeyi için güçlüdür; öğrenci okumaya "
               "hazır ve isteklidir. Önerilen adım: okuma çeşitliliğini artırarak bu "
               "başarının sürdürülmesi.",
    },
}


def _hiz_band(hiz_deger: str) -> str:
    v = (hiz_deger or "").strip().lower()
    return v if v in ("dusuk", "orta", "yeterli", "ileri") else "orta"


def _uc_band(pct: float, dusuk_esik: float, iyi_esik: float) -> str:
    if pct >= iyi_esik:
        return "iyi"
    if pct >= dusuk_esik:
        return "orta"
    return "zayif"


def _prozodik_band(toplam: float) -> str:
    if toplam >= 18:
        return "cokiyi"
    if toplam >= 14:
        return "iyi"
    if toplam >= 10:
        return "orta"
    return "gelistirilmeli"


def _kapanis_band(hiz_deger: str, dogruluk: float, anlama: float, proz: float, anlama_var: bool) -> str:
    """Genel düzey → dusuk/orta/iyi. Pasif kategorili sınıfta anlama hesaba katılmaz."""
    puan = 0
    puan += {"dusuk": 0, "orta": 1, "yeterli": 2, "ileri": 3}.get(_hiz_band(hiz_deger), 1)
    puan += {"zayif": 0, "orta": 1, "iyi": 2}.get(_uc_band(dogruluk, 85, 95), 1)
    puan += {"gelistirilmeli": 0, "orta": 1, "iyi": 2, "cokiyi": 3}.get(_prozodik_band(proz), 1)
    bolen = 8.0
    if anlama_var:
        puan += {"zayif": 0, "orta": 1, "iyi": 2}.get(_uc_band(anlama, 70, 85), 1)
        bolen = 10.0
    oran = puan / bolen
    if oran >= 0.66:
        return "iyi"
    if oran >= 0.33:
        return "orta"
    return "dusuk"


def sonuc_paragrafi_uret(rapor: dict, metinler: dict | None = None, anlama_var: bool = True) -> list:
    """Metin bankasından deterministik olarak birleştirilmiş sonuç cümleleri (liste).
    `anlama_var=False` ise (ör. 1. sınıf) anlama cümlesi eklenmez."""
    m = {**GIRIS_RAPOR_METIN_VARSAYILAN, **(metinler or {})}
    ad = (rapor.get("ogrenci_ad") or "Öğrenci").strip()
    hiz = _hiz_band(rapor.get("hiz_deger", ""))
    dogruluk = float(rapor.get("dogruluk_yuzde") or 0)
    anlama_pct = float(rapor.get("anlama_yuzde") or 0)
    proz = float(rapor.get("prozodik_toplam") or 0)

    cumleler = [m["giris"].replace("{ad}", ad)]
    cumleler.append(m["hiz"].get(hiz, ""))
    cumleler.append(m["dogruluk"].get(_uc_band(dogruluk, 85, 95), ""))
    if anlama_var:
        cumleler.append(m["anlama"].get(_uc_band(anlama_pct, 70, 85), ""))
    cumleler.append(m["prozodik"].get(_prozodik_band(proz), ""))
    kb = _kapanis_band(rapor.get("hiz_deger", ""), dogruluk, anlama_pct, proz, anlama_var)
    cumleler.append(m["kapanis"].get(kb, ""))
    return [c.replace("{ad}", ad) for c in cumleler if c and c.strip()]


# ═══════════════════════════════════════════════════════════════════
# Kalıcı ayar erişimi (db.sistem_ayarlari) — admin/koordinatör düzenler
# ═══════════════════════════════════════════════════════════════════
def _derin_birlestir(varsayilan: dict, ustune: dict) -> dict:
    """Varsayılanı korur, kaydedilen değerlerle üzerine yazar (yeni anahtarlar hep var)."""
    out = dict(varsayilan)
    for k, v in (ustune or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _derin_birlestir(out[k], v)
        else:
            out[k] = v
    return out


async def get_giris_rapor_metinleri(db) -> tuple:
    """(metinler, guncelleme_tarihi) — kayıt yoksa varsayılan bankayı döner."""
    doc = await db.sistem_ayarlari.find_one({"tip": "giris_rapor_metinleri"})
    if doc and isinstance(doc.get("degerler"), dict):
        return _derin_birlestir(GIRIS_RAPOR_METIN_VARSAYILAN, doc["degerler"]), doc.get("guncelleme_tarihi")
    return dict(GIRIS_RAPOR_METIN_VARSAYILAN), None


async def set_giris_rapor_metinleri(db, degerler: dict, guncelleyen: str = "") -> str:
    from core.zaman import iso
    tarih = iso()
    await db.sistem_ayarlari.update_one(
        {"tip": "giris_rapor_metinleri"},
        {"$set": {"degerler": degerler, "guncelleyen": guncelleyen, "guncelleme_tarihi": tarih}},
        upsert=True)
    return tarih


async def get_sinif_kategorileri(db) -> dict:
    """Sınıf → pasif ölçüm grupları eşlemesi (kayıt yoksa varsayılan: 1. sınıf pasif)."""
    doc = await db.sistem_ayarlari.find_one({"tip": "sinif_olcum_kategorileri"})
    if doc and isinstance(doc.get("degerler"), dict):
        return doc["degerler"]
    return dict(SINIF_KATEGORI_VARSAYILAN)


async def set_sinif_kategorileri(db, degerler: dict, guncelleyen: str = "") -> str:
    from core.zaman import iso
    tarih = iso()
    await db.sistem_ayarlari.update_one(
        {"tip": "sinif_olcum_kategorileri"},
        {"$set": {"degerler": degerler, "guncelleyen": guncelleyen, "guncelleme_tarihi": tarih}},
        upsert=True)
    return tarih
