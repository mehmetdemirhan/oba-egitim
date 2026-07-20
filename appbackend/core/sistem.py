"""Sistem ayarları çekirdeği — XP, lig, rozet ve anket varsayılanları + getter'lar.

server.py'daki orijinal tanımların BİREBİR aynısıdır (sadece konum değişti).
Hem server.py hem modüller (xp, rozetler, anketler, kitap, kitap-dersleri,
gelisim...) bu dosyadan import eder. Böylece her modül DB'ye yalnızca core
üzerinden erişir ve bağımsız olarak güncellenebilir (yama sistemi uyumu).
"""
from core.db import db

# ─────────────────────────────────────────────
# XP + LİG + KUR SİSTEMİ varsayılanları
# ─────────────────────────────────────────────

XP_TABLOSU_DEFAULT = {
    "okuma_gorevi": 3, "anlama_testi": 4, "kelime_gorevi": 3,
    "gunluk_streak": 2, "kitap_bitirme": 6, "yazili_ozet": 5,
    "egzersiz": 2, "gelisim_tamamla": 2, "gorev_tamamla": 3,
}

LIG_ESIKLERI_DEFAULT = {
    "bronz": 0, "gumus": 20, "altin": 50, "elmas": 100,
}

LIG_SIRA = ["bronz", "gumus", "altin", "elmas"]

OGRETMEN_ROZETLERI_DEFAULT = [
    # İçerik Katkısı
    {"kod": "icerik_ilk", "ad": "İlk Adım", "ikon": "🌱", "kategori": "icerik", "seviye": "bronz", "odul_puan":2},
    {"kod": "icerik_5", "ad": "İçerik Üreticisi", "ikon": "✍️", "kategori": "icerik", "seviye": "gumus", "odul_puan":3},
    {"kod": "icerik_20", "ad": "Kütüphane Kurucusu", "ikon": "📚", "kategori": "icerik", "seviye": "altin", "odul_puan":5},
    {"kod": "icerik_50", "ad": "Bilgi Kaynağı", "ikon": "🏛️", "kategori": "icerik", "seviye": "elmas", "odul_puan":7},
    # Kalite Kontrol
    {"kod": "oy_ilk", "ad": "İlk Oy", "ikon": "🗳️", "kategori": "kalite", "seviye": "bronz", "odul_puan":2},
    {"kod": "oy_20", "ad": "Kalite Bekçisi", "ikon": "🛡️", "kategori": "kalite", "seviye": "gumus", "odul_puan":3},
    {"kod": "oy_50", "ad": "Baş Editör", "ikon": "📋", "kategori": "kalite", "seviye": "altin", "odul_puan":5},
    # Eğitimci
    {"kod": "gorev_ilk", "ad": "İlk Görev", "ikon": "📌", "kategori": "egitimci", "seviye": "bronz", "odul_puan":2},
    {"kod": "gorev_20", "ad": "Aktif Eğitimci", "ikon": "🎯", "kategori": "egitimci", "seviye": "gumus", "odul_puan":4},
    {"kod": "ilham_veren", "ad": "İlham Veren", "ikon": "💡", "kategori": "egitimci", "seviye": "altin", "odul_puan":5},
    {"kod": "yildiz_egitimci", "ad": "Yıldız Eğitimci", "ikon": "⭐", "kategori": "egitimci", "seviye": "elmas", "odul_puan":7},
    # Kur Atlama
    {"kod": "kur_ilk", "ad": "İlk Kur Atlatan", "ikon": "🎓", "kategori": "kur", "seviye": "bronz", "odul_puan":3},
    {"kod": "kur_20", "ad": "Kur Ustası", "ikon": "🏅", "kategori": "kur", "seviye": "gumus", "odul_puan":5},
    {"kod": "kur_30", "ad": "Seviye Atlatan", "ikon": "🚀", "kategori": "kur", "seviye": "altin", "odul_puan":7},
    {"kod": "kur_50", "ad": "Süper Eğitimci", "ikon": "🦸", "kategori": "kur", "seviye": "platin", "odul_puan":8},
    {"kod": "kur_100", "ad": "Dönüşüm Lideri", "ikon": "👑", "kategori": "kur", "seviye": "elmas", "odul_puan":9},
    # Veli Değerlendirme
    {"kod": "veli_ilk", "ad": "İlk Beğeni", "ikon": "👍", "kategori": "veli", "seviye": "bronz", "odul_puan":2},
    {"kod": "veli_20", "ad": "Veli Favorisi", "ikon": "💜", "kategori": "veli", "seviye": "gumus", "odul_puan":5},
    {"kod": "veli_30", "ad": "Ailelerin Güveni", "ikon": "🏠", "kategori": "veli", "seviye": "altin", "odul_puan":6},
    {"kod": "veli_100", "ad": "Efsane Öğretmen", "ikon": "🌟", "kategori": "veli", "seviye": "elmas", "odul_puan":9},
    # Gelişim + İletişim + Egzersiz
    {"kod": "gelisim_ilk", "ad": "Meraklı Öğretmen", "ikon": "🔍", "kategori": "gelisim", "seviye": "bronz", "odul_puan":2},
    {"kod": "gelisim_10", "ad": "Sürekli Öğrenen", "ikon": "📖", "kategori": "gelisim", "seviye": "gumus", "odul_puan":4},
    {"kod": "gelisim_uzman", "ad": "Uzman Öğretmen", "ikon": "🎓", "kategori": "gelisim", "seviye": "elmas", "odul_puan":7},
    {"kod": "mesaj_ilk", "ad": "İlk Mesaj", "ikon": "💬", "kategori": "iletisim", "seviye": "bronz", "odul_puan":1},
    {"kod": "kopru_kurucu", "ad": "Köprü Kurucu", "ikon": "🌉", "kategori": "iletisim", "seviye": "altin", "odul_puan":4},
    {"kod": "egz_ilk", "ad": "İlk Egzersiz", "ikon": "👁️", "kategori": "egzersiz", "seviye": "bronz", "odul_puan":1},
    {"kod": "egz_tamset", "ad": "Tam Set", "ikon": "🎖️", "kategori": "egzersiz", "seviye": "altin", "odul_puan":5},
    # NOT (FAZ 1): ai_ilk/ai_5/ai_20/ai_50 rozetleri kaldırıldı — tanımlıydı ama
    # rozet_kontrol koşul listesinde yer almadığı için hiçbir zaman verilmiyordu
    # ("ölü rozet"). Bir metrik (ai_egitim_katkisi) tanımlanınca yeniden eklenebilir.
]

OGRENCI_ROZETLERI_DEFAULT = [
    {"kod": "okuma_ilk", "ad": "İlk Sayfa", "ikon": "📖", "kategori": "okuma", "seviye": "bronz", "odul_puan":2},
    {"kod": "okuma_100", "ad": "Kitap Kurdu", "ikon": "🐛", "kategori": "okuma", "seviye": "gumus", "odul_puan":4},
    {"kod": "okuma_500", "ad": "Okuma Yıldızı", "ikon": "⭐", "kategori": "okuma", "seviye": "altin", "odul_puan":6},
    {"kod": "okuma_2000", "ad": "Okuma Efsanesi", "ikon": "🌟", "kategori": "okuma", "seviye": "elmas", "odul_puan":7},
    {"kod": "streak_3", "ad": "İlk Alışkanlık", "ikon": "🔥", "kategori": "streak", "seviye": "bronz", "odul_puan":2},
    {"kod": "streak_7", "ad": "Kararlı Okuyucu", "ikon": "💪", "kategori": "streak", "seviye": "gumus", "odul_puan":3},
    {"kod": "streak_21", "ad": "Demir İrade", "ikon": "🏔️", "kategori": "streak", "seviye": "altin", "odul_puan":5},
    {"kod": "streak_60", "ad": "Durdurulamaz", "ikon": "🚀", "kategori": "streak", "seviye": "elmas", "odul_puan":7},
    {"kod": "kitap_1", "ad": "İlk Kitap", "ikon": "📕", "kategori": "kitap", "seviye": "bronz", "odul_puan":2},
    {"kod": "kitap_5", "ad": "Kitap Kaşifi", "ikon": "🗺️", "kategori": "kitap", "seviye": "gumus", "odul_puan":4},
    {"kod": "kitap_15", "ad": "Kütüphane Dostu", "ikon": "📚", "kategori": "kitap", "seviye": "altin", "odul_puan":6},
    {"kod": "kitap_30", "ad": "Kitap Efsanesi", "ikon": "🏰", "kategori": "kitap", "seviye": "elmas", "odul_puan":7},
    {"kod": "gorev_ilk", "ad": "Görev Başlangıcı", "ikon": "✅", "kategori": "gorev", "seviye": "bronz", "odul_puan":2},
    {"kod": "gorev_10", "ad": "Görev Avcısı", "ikon": "🎯", "kategori": "gorev", "seviye": "gumus", "odul_puan":4},
    {"kod": "gorev_30", "ad": "Görev Ustası", "ikon": "🏹", "kategori": "gorev", "seviye": "altin", "odul_puan":6},
    {"kod": "gorev_100", "ad": "Görev Efsanesi", "ikon": "👑", "kategori": "gorev", "seviye": "elmas", "odul_puan":7},
    {"kod": "egz_ilk", "ad": "Göz Jimnastiği", "ikon": "👁️", "kategori": "egzersiz", "seviye": "bronz", "odul_puan":2},
    {"kod": "egz_20", "ad": "Egzersiz Yıldızı", "ikon": "💫", "kategori": "egzersiz", "seviye": "gumus", "odul_puan":3},
    {"kod": "egz_14", "ad": "Beyin Atleti", "ikon": "🧠", "kategori": "egzersiz", "seviye": "altin", "odul_puan":5},
    {"kod": "orman_ilk", "ad": "İlk Fidan", "ikon": "🌱", "kategori": "orman", "seviye": "bronz", "odul_puan":2},
    {"kod": "orman_50", "ad": "Küçük Orman", "ikon": "🌿", "kategori": "orman", "seviye": "gumus", "odul_puan":3},
    {"kod": "orman_200", "ad": "Orman Korucusu", "ikon": "🌳", "kategori": "orman", "seviye": "altin", "odul_puan":5},
    {"kod": "lig_gumus", "ad": "Gümüş Yolcusu", "ikon": "🥈", "kategori": "lig", "seviye": "gumus", "odul_puan":3},
    {"kod": "lig_altin", "ad": "Altın Savaşçısı", "ikon": "🥇", "kategori": "lig", "seviye": "altin", "odul_puan":5},
    {"kod": "lig_elmas", "ad": "Elmas Efsanesi", "ikon": "💎", "kategori": "lig", "seviye": "elmas", "odul_puan":7},
]

ANKET_SORULARI_DEFAULT = [
    {"no": 1, "soru": "Öğretmenin çocuğunuzla iletişimi nasıl?", "tip": "puan", "kategori": "iletisim"},
    {"no": 2, "soru": "Görev ve ödevler düzenli veriliyor mu?", "tip": "puan", "kategori": "duzen"},
    {"no": 3, "soru": "Çocuğunuzun okuma alışkanlığında gelişme görüyor musunuz?", "tip": "puan", "kategori": "etki"},
    {"no": 4, "soru": "Öğretmen geri bildirimleri yeterli mi?", "tip": "puan", "kategori": "geri_bildirim"},
    {"no": 5, "soru": "Çocuğunuzun motivasyonu arttı mı?", "tip": "puan", "kategori": "motivasyon"},
    {"no": 6, "soru": "Öğretmenin egzersiz ve içerik çeşitliliği yeterli mi?", "tip": "puan", "kategori": "icerik"},
    {"no": 7, "soru": "Genel olarak öğretmenden memnun musunuz?", "tip": "puan", "kategori": "genel"},
    {"no": 8, "soru": "Bu öğretmeni başka velilere tavsiye eder misiniz?", "tip": "evet_hayir", "kategori": "tavsiye"},
    {"no": 9, "soru": "Eklemek istediğiniz not (opsiyonel)", "tip": "metin", "kategori": "not"},
]


async def get_xp_tablosu():
    doc = await db.sistem_ayarlari.find_one({"tip": "xp_tablosu"})
    return doc.get("degerler", XP_TABLOSU_DEFAULT) if doc else XP_TABLOSU_DEFAULT


async def get_lig_esikleri():
    doc = await db.sistem_ayarlari.find_one({"tip": "lig_esikleri"})
    return doc.get("degerler", LIG_ESIKLERI_DEFAULT) if doc else LIG_ESIKLERI_DEFAULT


async def get_ogretmen_rozetleri():
    doc = await db.sistem_ayarlari.find_one({"tip": "ogretmen_rozetleri"})
    return doc.get("degerler", OGRETMEN_ROZETLERI_DEFAULT) if doc else OGRETMEN_ROZETLERI_DEFAULT


async def get_ogrenci_rozetleri():
    doc = await db.sistem_ayarlari.find_one({"tip": "ogrenci_rozetleri"})
    return doc.get("degerler", OGRENCI_ROZETLERI_DEFAULT) if doc else OGRENCI_ROZETLERI_DEFAULT


async def get_anket_sorulari():
    doc = await db.sistem_ayarlari.find_one({"tip": "anket_sorulari"})
    return doc.get("degerler", ANKET_SORULARI_DEFAULT) if doc else ANKET_SORULARI_DEFAULT


# ── Puan Ayarları (içerik katkı puanları) ──
VARSAYILAN_PUANLAR = {
    "metin_ekleme": 2,
    "oylama_katilim": 1,
    "metin_havuza_girme": 3,
    "icerik_ekleme": 2,
    "icerik_oylama": 1,
    "ai_kitap_yukleme": 5,
    "ai_ders_kitabi_yukleme": 7,
    "ai_kitap_onaylandi": 4,
    # İçerik ekleme ek bonusları (önceden koda gömülüydü → merkezîleştirildi)
    "neden_bonus": 1,          # "neden bu içerik?" açıklaması (>=20 karakter)
    "test_soru_basi": 1,       # eklenen test sorusu başına
    "test_soru_max": 3,        # test sorusu bonus tavanı
    "icerik_tamamla_max": 5,   # içerik tamamlama ödülü tavanı (test başarısına göre)
    # Metin havuzu katkıları (öğretmen/koordinatör/yönetici) — yalnız İLK katkı ödüllendirilir
    "cevap_duzeltme": 2,       # bir MCQ'nun doğru cevabını ilk kez düzelten
    "gorsel_ekleme": 2,        # bir metne ilk kez görsel ekleyen
    "metin_kalite_geri_bildirim": 3,  # bir metne İLK kez kalite puanı veren (metin başına anti-farm)
    # Öneri kuyruğu (öğretmen düzenleme/soru önerisi ONAYLANINCA ödüllendirilir)
    "metin_duzeltme": 2,       # onaylanan metin düzeltme önerisi başına
    "soru_ekleme": 2,          # onaylanan yeni soru (MCQ/açık uçlu) önerisi başına
}


async def get_puan_ayarlari():
    doc = await db.sistem_ayarlari.find_one({"tip": "puan_ayarlari"})
    if doc:
        return doc.get("puanlar", VARSAYILAN_PUANLAR)
    return VARSAYILAN_PUANLAR


# ── Vergi ayarları (velilerden alınan tahsilatlara devlet vergisi kesintisi) ──
# Oran YÜZDE olarak tutulur (15 = %15). Admin generic /ayarlar/vergi_ayarlari ile
# değiştirir; değer "degerler" altında saklanır (generic PUT deseni).
VERGI_AYARLARI_DEFAULT = {"vergi_orani": 15}


async def get_vergi_ayarlari():
    doc = await db.sistem_ayarlari.find_one({"tip": "vergi_ayarlari"})
    if doc:
        return doc.get("degerler", VERGI_AYARLARI_DEFAULT)
    return VERGI_AYARLARI_DEFAULT


async def get_vergi_orani() -> float:
    """Güncel vergi oranını yüzde olarak döndürür (varsayılan 15)."""
    try:
        return float((await get_vergi_ayarlari()).get("vergi_orani", 15))
    except Exception:
        return 15.0


# ── Kur ücretleri (varsayılan alacak tutarları) ──
# Kur geçişinde açılan yeni alacak satırının beklenen tutarı buradan gelir.
# Eğitim türü bazlı tanımlanabilir; tanımsız türde "genel" varsayılan kullanılır.
# Değer generic /ayarlar/kur_ucretleri ile "degerler" altında saklanır:
#   {"genel": 1000, "turler": {"Hızlı Okuma": 1500, ...}}
KUR_UCRETLERI_DEFAULT = {"genel": 14400, "turler": {}}


async def get_kur_ucretleri_ayarlari():
    doc = await db.sistem_ayarlari.find_one({"tip": "kur_ucretleri"})
    return doc.get("degerler", KUR_UCRETLERI_DEFAULT) if doc else KUR_UCRETLERI_DEFAULT


async def get_kur_ucreti(egitim_turu: str = None) -> float:
    """Eğitim türü bazlı varsayılan kur ücreti; tanımsızsa genel varsayılan (0)."""
    try:
        ayar = await get_kur_ucretleri_ayarlari()
        turler = ayar.get("turler", {}) or {}
        if egitim_turu and egitim_turu in turler and turler[egitim_turu] not in (None, ""):
            return round(float(turler[egitim_turu]), 2)
        return round(float(ayar.get("genel", 0) or 0), 2)
    except Exception:
        return 0.0


# ── Öğretmen payı (kur tamamlanınca öğretmene ödenecek pay) ──
# Kur ücretlerine PARALEL: genel varsayılan + eğitim türü bazlı. Dönem bazlı öğretmen
# ödemesinde (ayın 15'i) tamamlanan her kur için bu pay hesaplanır.
# Generic /muhasebe/ayarlar üzerinden saklanır: {"genel": 500, "turler": {...}}
OGRETMEN_PAYLARI_DEFAULT = {"genel": 3000, "turler": {}}


async def get_ogretmen_paylari_ayarlari():
    doc = await db.sistem_ayarlari.find_one({"tip": "ogretmen_paylari"})
    return doc.get("degerler", OGRETMEN_PAYLARI_DEFAULT) if doc else OGRETMEN_PAYLARI_DEFAULT


async def get_ogretmen_payi(egitim_turu: str = None) -> float:
    """Eğitim türü bazlı öğretmen payı; tanımsızsa genel varsayılan (0)."""
    try:
        ayar = await get_ogretmen_paylari_ayarlari()
        turler = ayar.get("turler", {}) or {}
        if egitim_turu and egitim_turu in turler and turler[egitim_turu] not in (None, ""):
            return round(float(turler[egitim_turu]), 2)
        return round(float(ayar.get("genel", 0) or 0), 2)
    except Exception:
        return 0.0


# ── Kutulu Okuma egzersizi ayarları ──
# kutu_basi_kelime: bir kutuda kaç kelime gösterilsin (genel varsayılan; egzersiz
# ayar çekmecesinden her açılışta 1/2/3 olarak değiştirilebilir).
KUTULU_OKUMA_DEFAULT = {"kutu_basi_kelime": 1}


async def get_kutulu_okuma_ayarlari():
    doc = await db.sistem_ayarlari.find_one({"tip": "kutulu_okuma"})
    return doc.get("degerler", KUTULU_OKUMA_DEFAULT) if doc else KUTULU_OKUMA_DEFAULT


# ── Öğretmen XP bileşen ağırlıkları (öğrenci / kur / veli çıktıları) ──
OGRETMEN_PUAN_AGIRLIKLARI_DEFAULT = {
    "ogrenci_basi": 5,    # alınan her öğrenci başına puan
    "kur_basi": 7,        # her kur atlatma olayı başına puan
    "veli_yildiz": 2,     # veli anketinde ortalama yıldız başına puan (5★ = +10/anket)
}


async def get_ogretmen_puan_agirliklari():
    doc = await db.sistem_ayarlari.find_one({"tip": "ogretmen_puan_agirliklari"})
    degerler = doc.get("degerler", {}) if doc else {}
    # Eksik anahtarları varsayılanla tamamla
    return {**OGRETMEN_PUAN_AGIRLIKLARI_DEFAULT, **(degerler or {})}


# ── Özellik (feature-flag) ayarları ──
OZELLIK_TANIMLARI = [
    # ── ÖĞRETMEN PANELİ ──
    {"id":"ogretmen_dashboard",     "label":"Öğretmen Dashboard",        "kategori":"ogretmen","ikon":"📊","aciklama":"Risk skorları, öğrenci özeti, genel istatistikler"},
    {"id":"ogretmen_giris_analizi", "label":"Giriş Analizi (Okuma)",      "kategori":"ogretmen","ikon":"🔬","aciklama":"Sesli okuma analizi, WPM, prozodik okuma ve rapor üretimi"},
    {"id":"ogretmen_timi",          "label":"TIMI - Çoklu Zeka Envanteri", "kategori":"ogretmen","ikon":"🧠","aciklama":"Teele Çoklu Zeka Envanteri: 28 kartlık zorlamalı-seçim, 7 zeka alanı profili ve rapor"},
    {"id":"ogretmen_gelisim",       "label":"Gelişim Alanı",              "kategori":"ogretmen","ikon":"🎓","aciklama":"İçerik ekleme, oylama, materyal yönetimi"},
    {"id":"ogretmen_gorevler",      "label":"Görev Atama",                "kategori":"ogretmen","ikon":"📌","aciklama":"Öğrencilere görev ve ödev atama sistemi"},
    {"id":"ogretmen_mesajlar",      "label":"Mesajlaşma",                 "kategori":"ogretmen","ikon":"✉️","aciklama":"Öğrenci ve velilerle mesajlaşma"},
    {"id":"ogretmen_ai_kocluk",     "label":"AI Koçluk Raporu",           "kategori":"ogretmen","ikon":"🧠","aciklama":"AI ile öğrenci analizi, DNA profili ve kişisel öneriler"},
    {"id":"ogretmen_ai_soru",       "label":"AI Soru Üretici",            "kategori":"ogretmen","ikon":"❓","aciklama":"Metin yükleyerek Bloom taksonomili soru üretme"},
    {"id":"ogretmen_ai_bilgi",      "label":"AI Bilgi Tabanı (PDF/Word)", "kategori":"ogretmen","ikon":"📚","aciklama":"Ders kitabı yükleme ve AI ile kelime/soru çıkarma"},
    {"id":"ogretmen_rozetler",      "label":"Rozet & Başarılar",          "kategori":"ogretmen","ikon":"🏅","aciklama":"Öğretmen rozet ve başarı sistemi"},
    {"id":"ogretmen_hedefler",      "label":"Hedef Sistemi",              "kategori":"ogretmen","ikon":"🎯","aciklama":"Öğretmenin kişisel hedef koyma ve takip sistemi"},
    {"id":"ogretmen_veli_anket",    "label":"Veli Anket Sonuçları",       "kategori":"ogretmen","ikon":"⭐","aciklama":"Velilerin öğretmeni değerlendirdiği anket sonuçları"},
    # ── ÖĞRENCİ PANELİ ──
    {"id":"ogrenci_okuma_kaydi",    "label":"Okuma Kaydı",                "kategori":"ogrenci","ikon":"📖","aciklama":"Ne okudum, okuma süresi ve sayfa takibi"},
    {"id":"ogrenci_gorevler",       "label":"Görevler",                   "kategori":"ogrenci","ikon":"✅","aciklama":"Öğretmenden gelen görevleri görme ve tamamlama"},
    {"id":"ogrenci_gelisim",        "label":"Gelişim Alanı",              "kategori":"ogrenci","ikon":"🎓","aciklama":"İçerik okuma, video izleme, egzersizler"},
    {"id":"ogrenci_egzersizler",    "label":"Göz ve Beyin Egzersizleri",  "kategori":"ogrenci","ikon":"👁️","aciklama":"Odak ve algı geliştirici egzersiz modülleri"},
    {"id":"ogrenci_xp_lig",         "label":"XP & Lig Sistemi",           "kategori":"ogrenci","ikon":"🏆","aciklama":"Puan kazanma, lig yükselme ve sıralama"},
    {"id":"ogrenci_rozetler",       "label":"Rozetler",                   "kategori":"ogrenci","ikon":"🎖️","aciklama":"Öğrenci başarı rozetleri"},
    {"id":"ogrenci_speech_ai",      "label":"Sesli Okuma Analizi (AI)",   "kategori":"ogrenci","ikon":"🎤","aciklama":"Mikrofona sesli okuma ve AI analizi"},
    {"id":"ogrenci_kelime_evrimi",  "label":"Kelime Evrimi (Kartlar)",    "kategori":"ogrenci","ikon":"🔤","aciklama":"Spaced repetition ile kelime öğrenme"},
    {"id":"ogrenci_mini_oyunlar",   "label":"Mini Oyunlar",               "kategori":"ogrenci","ikon":"🎮","aciklama":"Kelime avı, eşleştirme ve boşluk doldurma oyunları"},
    {"id":"ogrenci_scaffold",       "label":"Scaffold Okuma (Seviyeleme)","kategori":"ogrenci","ikon":"📐","aciklama":"DNA'ya göre kolay/orta/orijinal metin seviyeleme"},
    {"id":"ogrenci_materyal",       "label":"AI Materyal Üretici",        "kategori":"ogrenci","ikon":"🛠️","aciklama":"Kitaptan soru seti, kelime listesi, etkinlik üretme"},
    {"id":"ogrenci_hikaye",         "label":"Kişisel Hikaye (AI)",        "kategori":"ogrenci","ikon":"✨","aciklama":"İlgi alanına göre AI tarafından yazılan özel hikaye"},
    {"id":"ogrenci_ai_arkadas",     "label":"AI Okuma Arkadaşı",          "kategori":"ogrenci","ikon":"🤖","aciklama":"4 karakterli AI sohbet asistanı"},
    {"id":"ogrenci_orman",          "label":"Okuma Ormanı",               "kategori":"ogrenci","ikon":"🌲","aciklama":"Okuduğun dakika = Diktiğin ağaç gamification"},
    {"id":"ogrenci_mesajlar",       "label":"Mesajlaşma",                 "kategori":"ogrenci","ikon":"💬","aciklama":"Öğretmenle mesajlaşma"},
    {"id":"ogrenci_siralama",       "label":"Sıralama Tablosu",           "kategori":"ogrenci","ikon":"📈","aciklama":"Anonim okuma dakikası sıralaması"},
    # ── VELİ PANELİ ──
    {"id":"veli_dashboard",         "label":"Veli Dashboard",             "kategori":"veli","ikon":"🏠","aciklama":"Çocuğun okuma istatistikleri ve genel durumu"},
    {"id":"veli_gorev_takip",       "label":"Görev Takibi",               "kategori":"veli","ikon":"📋","aciklama":"Çocuğa atanan görevleri görme"},
    {"id":"veli_okuma_gecmisi",     "label":"Okuma Geçmişi",              "kategori":"veli","ikon":"📅","aciklama":"Haftalık/aylık okuma istatistikleri"},
    {"id":"veli_bildirimler",       "label":"Bildirimler",                "kategori":"veli","ikon":"🔔","aciklama":"Streak uyarısı, rapor bildirimleri"},
    {"id":"veli_anket",             "label":"Öğretmen Değerlendirme",     "kategori":"veli","ikon":"⭐","aciklama":"Öğretmeni değerlendirme anketi"},
    {"id":"veli_mesajlar",          "label":"Mesajlaşma",                 "kategori":"veli","ikon":"💬","aciklama":"Öğretmenle mesajlaşma"},
    {"id":"veli_rapor",             "label":"Giriş Analizi Raporları",    "kategori":"veli","ikon":"📄","aciklama":"Öğretmenin hazırladığı raporları görme"},
]

OZELLIK_VARSAYILAN = {
    f["id"]: {"aktif": True, "roller": {"ogretmen": True, "ogrenci": True, "veli": True}}
    for f in OZELLIK_TANIMLARI
}


async def get_ozellik_ayarlari() -> dict:
    doc = await db.sistem_ayarlari.find_one({"tip": "ozellik_ayarlari"})
    if doc and doc.get("degerler"):
        mevcut = doc["degerler"]
        for f in OZELLIK_TANIMLARI:
            if f["id"] not in mevcut:
                mevcut[f["id"]] = {"aktif": True, "roller": {"ogretmen": True, "ogrenci": True, "veli": True}}
        return mevcut
    return dict(OZELLIK_VARSAYILAN)






async def ozellik_aktif_mi(ozellik_id: str, rol: str) -> bool:
    """Verilen özelliğin belirtilen rol için aktif olup olmadığını döner."""
    ayarlar = await get_ozellik_ayarlari()
    ozellik = ayarlar.get(ozellik_id, {"aktif": True, "roller": {}})
    if not ozellik.get("aktif", True):
        return False
    return ozellik.get("roller", {}).get(rol, True)
