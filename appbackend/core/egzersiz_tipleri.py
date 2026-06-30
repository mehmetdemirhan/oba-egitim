"""Egzersiz Motoru — tip kayıt defteri (registry) ve meta bilgiler.

Her egzersiz tipi burada TEK bir kayıtla tanımlanır. Yeni tip eklemek için:
  1. Buraya bir kayıt ekle (EGZERSIZ_TIPLERI)
  2. core/egzersiz_prompts.py içine prompt + mock ekle
  3. frontend/src/components/exercises/types/ içine küçük bir render komponenti ekle

Motor (modules/egzersiz_motoru.py) bu kayıtları okur; tip başına özel kod YAZILMAZ.

Puanlama stratejileri (jenerik grader bunları kullanır):
  - "secmeli"  → icerik["sorular"][soru_no]["dogru"] ile karşılaştır
  - "sira"     → icerik["dogru_sira"] dizisi ile karşılaştır (tek soruluk)
  - "eslesme"  → icerik["ciftler"] eşleştirmesi; cevap {sol, sag}
  - "serbest"  → grader cevabı doğru kabul eder (telaffuz/ses gibi dış puanlama)
"""

# Kategori okunabilir etiketleri (frontend gruplama için)
KATEGORILER = {
    "test": "Test",
    "kelime": "Kelime Çalışması",
    "anlama": "Okuduğunu Anlama",
    "oyun": "Kelime Oyunları",
    "gelismis": "Gelişmiş Beceriler",
    "fonoloji": "Fonolojik Farkındalık",
}

# Tip kayıtları — id (snake_case) → meta
# Not: FAZ 0'da yalnızca motor testi için "demo" tipi vardır.
# FAZ 1 (Tier 1) ile 5 temel egzersiz tipi eklendi.
# Tier 2-4 ve fonoloji tipleri sonraki fazlarda eklenecektir.
EGZERSIZ_TIPLERI = {
    "demo": {
        "ad": "Demo Egzersiz",
        "aciklama": "Egzersiz motorunu test etmek için örnek çoktan seçmeli egzersiz.",
        "sinif_min": 1,
        "sinif_max": 8,
        "kategori": "test",
        "puanlama": "secmeli",
        "soru_sayisi": 3,
        "ikon": "🧪",
    },
    # ── Tier 1: 5 temel egzersiz (FAZ 1) ──────────────────────────
    "kelime_anlam_eslestirme": {
        "ad": "Kelime-Anlam Eşleştirme",
        "aciklama": "Verilen kelimeleri doğru anlamlarıyla eşleştir.",
        "sinif_min": 1,
        "sinif_max": 8,
        "kategori": "kelime",
        "puanlama": "eslesme",
        "soru_sayisi": 5,
        "ikon": "🔗",
    },
    "cloze_bosluk_doldurma": {
        "ad": "Boşluk Doldurma",
        "aciklama": "Cümledeki boşluğa en uygun kelimeyi seç.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "anlama",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "✏️",
    },
    "es_karsit_anlamli": {
        "ad": "Eş ve Karşıt Anlamlılar",
        "aciklama": "Kelimenin eş veya karşıt anlamlısını bul.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "kelime",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "↔️",
    },
    "karisik_cumle_siralama": {
        "ad": "Karışık Cümle Sıralama",
        "aciklama": "Karışık verilen kelimeleri sıralayarak anlamlı cümle oluştur.",
        "sinif_min": 1,
        "sinif_max": 8,
        "kategori": "gelismis",
        "puanlama": "sira",
        "soru_sayisi": 5,
        "ikon": "🔀",
    },
    "hikaye_olay_siralama": {
        "ad": "Hikâye Olay Sıralama",
        "aciklama": "Hikâyedeki olayları doğru sıraya koy.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "anlama",
        "puanlama": "sira",
        "soru_sayisi": 5,
        "ikon": "📖",
    },
}


def tip_var_mi(tip: str) -> bool:
    return tip in EGZERSIZ_TIPLERI


def tip_meta(tip: str) -> dict | None:
    meta = EGZERSIZ_TIPLERI.get(tip)
    if meta is None:
        return None
    return {"id": tip, **meta}


def tip_listesi(sinif: int | None = None) -> list:
    """Tüm tipleri (opsiyonel sınıf filtresiyle) döndürür."""
    out = []
    for tid, meta in EGZERSIZ_TIPLERI.items():
        if sinif is not None and not (meta["sinif_min"] <= sinif <= meta["sinif_max"]):
            continue
        out.append({
            "id": tid,
            "ad": meta["ad"],
            "aciklama": meta["aciklama"],
            "sinif_min": meta["sinif_min"],
            "sinif_max": meta["sinif_max"],
            "kategori": meta["kategori"],
            "kategori_ad": KATEGORILER.get(meta["kategori"], meta["kategori"]),
            "ikon": meta.get("ikon", "📝"),
            "soru_sayisi": meta.get("soru_sayisi", 5),
        })
    return out
