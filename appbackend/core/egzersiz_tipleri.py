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
    "deyim": "Deyim & Atasözü",
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
    # ── Tier 2: Okuduğunu anlama / üst düzey beceriler (FAZ 2) ────
    # Hepsi kısa bir metin + çoktan seçmeli sorular (puanlama="secmeli").
    "bes_n_bir_k": {
        "ad": "5N1K Soruları",
        "aciklama": "Metni oku; kim, ne, nerede, ne zaman, neden ve nasıl sorularını yanıtla.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "anlama",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "❓",
    },
    "ana_fikir": {
        "ad": "Ana Fikir Bulma",
        "aciklama": "Metnin ana fikrini ve yardımcı düşüncelerini belirle.",
        "sinif_min": 3,
        "sinif_max": 8,
        "kategori": "anlama",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "💡",
    },
    "cikarim": {
        "ad": "Çıkarım Yapma",
        "aciklama": "Metinde doğrudan söylenmeyeni, ipuçlarından çıkar.",
        "sinif_min": 3,
        "sinif_max": 8,
        "kategori": "anlama",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "🔎",
    },
    "sebep_sonuc": {
        "ad": "Sebep-Sonuç İlişkisi",
        "aciklama": "Olaylar arasındaki sebep-sonuç bağlantısını bul.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "anlama",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "🔗",
    },
    "tahmin_et": {
        "ad": "Tahmin Et",
        "aciklama": "Metnin nasıl devam edeceğini ipuçlarına göre tahmin et.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "anlama",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "🔮",
    },
    # ── Tier 3: Kelime oyunları (FAZ 3) ──────────────────────────
    "anagram": {
        "ad": "Anagram",
        "aciklama": "Karışık harfleri sıralayarak gizli kelimeyi bul.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "oyun",
        "puanlama": "serbest",
        "soru_sayisi": 1,
        "ikon": "🔤",
    },
    "bulmaca": {
        "ad": "Kelime Bulmaca",
        "aciklama": "İpucuna göre harfleri sıralayıp doğru kelimeyi oluştur.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "oyun",
        "puanlama": "serbest",
        "soru_sayisi": 1,
        "ikon": "🧩",
    },
    "hafiza_karti": {
        "ad": "Hafıza Kartları",
        "aciklama": "Kapalı kartları çevirerek kelime-anlam çiftlerini eşle.",
        "sinif_min": 1,
        "sinif_max": 8,
        "kategori": "oyun",
        "puanlama": "serbest",
        "soru_sayisi": 1,
        "ikon": "🃏",
    },
    "kelime_yagmuru": {
        "ad": "Kelime Yağmuru",
        "aciklama": "Süre dolmadan istenen özellikteki kelimeleri yakala.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "oyun",
        "puanlama": "serbest",
        "soru_sayisi": 1,
        "ikon": "🌧️",
    },
    "kelime_merdiveni": {
        "ad": "Kelime Merdiveni",
        "aciklama": "Bir harfini değiştirerek yeni kelimeye basamak basamak ulaş.",
        "sinif_min": 3,
        "sinif_max": 8,
        "kategori": "oyun",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "🪜",
    },
    "baglam_ipucu": {
        "ad": "Bağlam İpucu",
        "aciklama": "Cümledeki ipuçlarından bilinmeyen kelimenin anlamını çöz.",
        "sinif_min": 3,
        "sinif_max": 8,
        "kategori": "kelime",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "🧭",
    },
    # ── Tier 4: Gelişmiş beceriler (FAZ 4) ───────────────────────
    # Hepsi çoktan seçmeli (puanlama="secmeli"); özel görseller render katmanında.
    "frayer": {
        "ad": "Frayer Modeli",
        "aciklama": "Bir kelimeyi tanım, özellik, örnek ve örnek-değil olarak çözümle.",
        "sinif_min": 3,
        "sinif_max": 8,
        "kategori": "gelismis",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "🗂️",
    },
    "anlam_haritasi": {
        "ad": "Anlam Haritası",
        "aciklama": "Merkez kelimeyle ilişkili kavramları belirle.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "gelismis",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "🕸️",
    },
    "venn": {
        "ad": "Venn Şeması",
        "aciklama": "İki kavramı karşılaştır; özellikleri doğru bölgeye yerleştir.",
        "sinif_min": 3,
        "sinif_max": 8,
        "kategori": "gelismis",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "⭕",
    },
    "tekerleme": {
        "ad": "Tekerleme",
        "aciklama": "Tekerlemeyi oku ve eksik/uyaklı kelimeyi bul.",
        "sinif_min": 1,
        "sinif_max": 5,
        "kategori": "gelismis",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "🎵",
    },
    "sight_words": {
        "ad": "Sık Kullanılan Kelimeler",
        "aciklama": "Sık geçen kelimeleri hızlıca tanı ve doğru olanı seç.",
        "sinif_min": 1,
        "sinif_max": 4,
        "kategori": "gelismis",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "👀",
    },
    "diyalog": {
        "ad": "Diyalog Anlama",
        "aciklama": "Konuşmayı oku; uygun yanıtı ya da anlamı seç.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "anlama",
        "puanlama": "secmeli",
        "soru_sayisi": 4,
        "ikon": "💬",
    },
    # ── FAZ 5: Fonolojik farkındalık (1-2. sınıf) ────────────────
    # Hepsi çoktan seçmeli; render katmanı Web Speech API ile sesli okur.
    "hece_sayma": {
        "ad": "Hece Sayma",
        "aciklama": "Kelimeyi dinle, kaç heceli olduğunu bul.",
        "sinif_min": 1,
        "sinif_max": 3,
        "kategori": "fonoloji",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "🔢",
    },
    "hece_birlestirme": {
        "ad": "Hece Birleştirme",
        "aciklama": "Heceleri birleştir, hangi kelime olduğunu bul.",
        "sinif_min": 1,
        "sinif_max": 3,
        "kategori": "fonoloji",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "🧩",
    },
    "ilk_ses": {
        "ad": "İlk Ses",
        "aciklama": "Kelimenin hangi sesle başladığını bul.",
        "sinif_min": 1,
        "sinif_max": 2,
        "kategori": "fonoloji",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "🅰️",
    },
    "son_ses": {
        "ad": "Son Ses",
        "aciklama": "Kelimenin hangi sesle bittiğini bul.",
        "sinif_min": 1,
        "sinif_max": 2,
        "kategori": "fonoloji",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "🔚",
    },
    "kafiye": {
        "ad": "Kafiyeli Kelimeler",
        "aciklama": "Verilen kelimeyle kafiyeli (uyaklı) olanı bul.",
        "sinif_min": 1,
        "sinif_max": 3,
        "kategori": "fonoloji",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "🎶",
    },
    "ses_birlestirme": {
        "ad": "Ses Birleştirme",
        "aciklama": "Sesleri birleştir, hangi kelime olduğunu bul.",
        "sinif_min": 1,
        "sinif_max": 2,
        "kategori": "fonoloji",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "🔤",
    },
    "ses_cikarma": {
        "ad": "Ses/Hece Çıkarma",
        "aciklama": "Kelimeden bir hece/ses atınca ne kaldığını bul.",
        "sinif_min": 2,
        "sinif_max": 3,
        "kategori": "fonoloji",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "✂️",
    },
    # ── Kelime Gezmece (çapraz bulmaca harf oyunu) ───────────────
    # İçerik AI ile DEĞİL, core/bulmaca_olusturucu.py ile üretilir
    # (icerik_uretici="bulmaca"). Puanlama "serbest"; oyun kendi akışını
    # yönetir, tamamlanınca tek seferde başarı bildirir. Özel puanlama
    # (grid +10 / bonus +15) /egzersiz/kelime-gezmece/dogrula ile yapılır.
    "kelime_gezmece": {
        "ad": "Kelime Gezmece",
        "aciklama": "Harfleri birleştirerek çapraz bulmacadaki gizli kelimeleri bul.",
        "sinif_min": 1,
        "sinif_max": 8,
        "kategori": "oyun",
        "puanlama": "serbest",
        "soru_sayisi": 1,
        "ikon": "🧩",
        "icerik_uretici": "bulmaca",
    },
    # ── Deyim / Atasözü / Tekerleme (FAZ 4) ──────────────────────
    # Kaynak: db.deyim_atasozu havuzu (yönetici girer). İçerik AI ile üretilir;
    # havuz öğeleri prompt'a enjekte edilir (egzersiz_motoru _DEYIM_TIPLERI).
    "deyim_eslestirme": {
        "ad": "Deyim-Atasözü Eşleştirme",
        "aciklama": "Deyim/atasözünü doğru anlamıyla eşleştir.",
        "sinif_min": 2,
        "sinif_max": 8,
        "kategori": "deyim",
        "puanlama": "eslesme",
        "soru_sayisi": 5,
        "ikon": "🧩",
    },
    "deyim_bosluk": {
        "ad": "Deyim Boşluk Doldurma",
        "aciklama": "Deyimin içindeki eksik kelimeyi bul.",
        "sinif_min": 3,
        "sinif_max": 8,
        "kategori": "deyim",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "✏️",
    },
    "atasozu_bosluk": {
        "ad": "Atasözü Boşluk Doldurma",
        "aciklama": "Atasözünün içindeki eksik kelimeyi bul.",
        "sinif_min": 3,
        "sinif_max": 8,
        "kategori": "deyim",
        "puanlama": "secmeli",
        "soru_sayisi": 5,
        "ikon": "🗣️",
    },
    "tekerleme_okuma": {
        "ad": "Tekerleme Okuma",
        "aciklama": "Tekerlemeyi akıcı ve hızlı bir şekilde oku.",
        "sinif_min": 1,
        "sinif_max": 5,
        "kategori": "fonoloji",
        "puanlama": "serbest",
        "soru_sayisi": 1,
        "ikon": "🎵",
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
            "puanlama": meta.get("puanlama", "secmeli"),
        })
    return out
