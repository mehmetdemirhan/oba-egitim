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
    "okuma_gorevi": 10, "anlama_testi": 15, "kelime_gorevi": 8,
    "gunluk_streak": 5, "kitap_bitirme": 30, "yazili_ozet": 20,
    "egzersiz": 5, "gelisim_tamamla": 5, "gorev_tamamla": 10,
}

LIG_ESIKLERI_DEFAULT = {
    "bronz": 0, "gumus": 200, "altin": 500, "elmas": 1000,
}

LIG_SIRA = ["bronz", "gumus", "altin", "elmas"]

OGRETMEN_ROZETLERI_DEFAULT = [
    # İçerik Katkısı
    {"kod": "icerik_ilk", "ad": "İlk Adım", "ikon": "🌱", "kategori": "icerik", "seviye": "bronz", "puan": 5},
    {"kod": "icerik_5", "ad": "İçerik Üreticisi", "ikon": "✍️", "kategori": "icerik", "seviye": "gumus", "puan": 10},
    {"kod": "icerik_20", "ad": "Kütüphane Kurucusu", "ikon": "📚", "kategori": "icerik", "seviye": "altin", "puan": 25},
    {"kod": "icerik_50", "ad": "Bilgi Kaynağı", "ikon": "🏛️", "kategori": "icerik", "seviye": "elmas", "puan": 50},
    # Kalite Kontrol
    {"kod": "oy_ilk", "ad": "İlk Oy", "ikon": "🗳️", "kategori": "kalite", "seviye": "bronz", "puan": 3},
    {"kod": "oy_20", "ad": "Kalite Bekçisi", "ikon": "🛡️", "kategori": "kalite", "seviye": "gumus", "puan": 10},
    {"kod": "oy_50", "ad": "Baş Editör", "ikon": "📋", "kategori": "kalite", "seviye": "altin", "puan": 25},
    # Eğitimci
    {"kod": "gorev_ilk", "ad": "İlk Görev", "ikon": "📌", "kategori": "egitimci", "seviye": "bronz", "puan": 3},
    {"kod": "gorev_20", "ad": "Aktif Eğitimci", "ikon": "🎯", "kategori": "egitimci", "seviye": "gumus", "puan": 15},
    {"kod": "ilham_veren", "ad": "İlham Veren", "ikon": "💡", "kategori": "egitimci", "seviye": "altin", "puan": 20},
    {"kod": "yildiz_egitimci", "ad": "Yıldız Eğitimci", "ikon": "⭐", "kategori": "egitimci", "seviye": "elmas", "puan": 40},
    # Kur Atlama
    {"kod": "kur_ilk", "ad": "İlk Kur Atlatan", "ikon": "🎓", "kategori": "kur", "seviye": "bronz", "puan": 10},
    {"kod": "kur_20", "ad": "Kur Ustası", "ikon": "🏅", "kategori": "kur", "seviye": "gumus", "puan": 25},
    {"kod": "kur_30", "ad": "Seviye Atlatan", "ikon": "🚀", "kategori": "kur", "seviye": "altin", "puan": 40},
    {"kod": "kur_50", "ad": "Süper Eğitimci", "ikon": "🦸", "kategori": "kur", "seviye": "platin", "puan": 75},
    {"kod": "kur_100", "ad": "Dönüşüm Lideri", "ikon": "👑", "kategori": "kur", "seviye": "elmas", "puan": 100},
    # Veli Değerlendirme
    {"kod": "veli_ilk", "ad": "İlk Beğeni", "ikon": "👍", "kategori": "veli", "seviye": "bronz", "puan": 5},
    {"kod": "veli_20", "ad": "Veli Favorisi", "ikon": "💜", "kategori": "veli", "seviye": "gumus", "puan": 20},
    {"kod": "veli_30", "ad": "Ailelerin Güveni", "ikon": "🏠", "kategori": "veli", "seviye": "altin", "puan": 35},
    {"kod": "veli_100", "ad": "Efsane Öğretmen", "ikon": "🌟", "kategori": "veli", "seviye": "elmas", "puan": 100},
    # Gelişim + İletişim + Egzersiz
    {"kod": "gelisim_ilk", "ad": "Meraklı Öğretmen", "ikon": "🔍", "kategori": "gelisim", "seviye": "bronz", "puan": 3},
    {"kod": "gelisim_10", "ad": "Sürekli Öğrenen", "ikon": "📖", "kategori": "gelisim", "seviye": "gumus", "puan": 15},
    {"kod": "gelisim_uzman", "ad": "Uzman Öğretmen", "ikon": "🎓", "kategori": "gelisim", "seviye": "elmas", "puan": 50},
    {"kod": "mesaj_ilk", "ad": "İlk Mesaj", "ikon": "💬", "kategori": "iletisim", "seviye": "bronz", "puan": 2},
    {"kod": "kopru_kurucu", "ad": "Köprü Kurucu", "ikon": "🌉", "kategori": "iletisim", "seviye": "altin", "puan": 15},
    {"kod": "egz_ilk", "ad": "İlk Egzersiz", "ikon": "👁️", "kategori": "egzersiz", "seviye": "bronz", "puan": 2},
    {"kod": "egz_tamset", "ad": "Tam Set", "ikon": "🎖️", "kategori": "egzersiz", "seviye": "altin", "puan": 20},
    # AI Eğitim Katkısı
    {"kod": "ai_ilk", "ad": "AI Eğitimcisi", "ikon": "🧠", "kategori": "ai_egitim", "seviye": "bronz", "puan": 5},
    {"kod": "ai_5", "ad": "Veri Kaşifi", "ikon": "📊", "kategori": "ai_egitim", "seviye": "gumus", "puan": 15},
    {"kod": "ai_20", "ad": "AI Ustası", "ikon": "🤖", "kategori": "ai_egitim", "seviye": "altin", "puan": 30},
    {"kod": "ai_50", "ad": "Bilgi Mimarı", "ikon": "🏗️", "kategori": "ai_egitim", "seviye": "elmas", "puan": 75},
]

OGRENCI_ROZETLERI_DEFAULT = [
    {"kod": "okuma_ilk", "ad": "İlk Sayfa", "ikon": "📖", "kategori": "okuma", "seviye": "bronz", "xp": 5},
    {"kod": "okuma_100", "ad": "Kitap Kurdu", "ikon": "🐛", "kategori": "okuma", "seviye": "gumus", "xp": 15},
    {"kod": "okuma_500", "ad": "Okuma Yıldızı", "ikon": "⭐", "kategori": "okuma", "seviye": "altin", "xp": 30},
    {"kod": "okuma_2000", "ad": "Okuma Efsanesi", "ikon": "🌟", "kategori": "okuma", "seviye": "elmas", "xp": 50},
    {"kod": "streak_3", "ad": "İlk Alışkanlık", "ikon": "🔥", "kategori": "streak", "seviye": "bronz", "xp": 5},
    {"kod": "streak_7", "ad": "Kararlı Okuyucu", "ikon": "💪", "kategori": "streak", "seviye": "gumus", "xp": 10},
    {"kod": "streak_21", "ad": "Demir İrade", "ikon": "🏔️", "kategori": "streak", "seviye": "altin", "xp": 25},
    {"kod": "streak_60", "ad": "Durdurulamaz", "ikon": "🚀", "kategori": "streak", "seviye": "elmas", "xp": 50},
    {"kod": "kitap_1", "ad": "İlk Kitap", "ikon": "📕", "kategori": "kitap", "seviye": "bronz", "xp": 5},
    {"kod": "kitap_5", "ad": "Kitap Kaşifi", "ikon": "🗺️", "kategori": "kitap", "seviye": "gumus", "xp": 15},
    {"kod": "kitap_15", "ad": "Kütüphane Dostu", "ikon": "📚", "kategori": "kitap", "seviye": "altin", "xp": 30},
    {"kod": "kitap_30", "ad": "Kitap Efsanesi", "ikon": "🏰", "kategori": "kitap", "seviye": "elmas", "xp": 50},
    {"kod": "gorev_ilk", "ad": "Görev Başlangıcı", "ikon": "✅", "kategori": "gorev", "seviye": "bronz", "xp": 5},
    {"kod": "gorev_10", "ad": "Görev Avcısı", "ikon": "🎯", "kategori": "gorev", "seviye": "gumus", "xp": 15},
    {"kod": "gorev_30", "ad": "Görev Ustası", "ikon": "🏹", "kategori": "gorev", "seviye": "altin", "xp": 30},
    {"kod": "gorev_100", "ad": "Görev Efsanesi", "ikon": "👑", "kategori": "gorev", "seviye": "elmas", "xp": 50},
    {"kod": "egz_ilk", "ad": "Göz Jimnastiği", "ikon": "👁️", "kategori": "egzersiz", "seviye": "bronz", "xp": 3},
    {"kod": "egz_20", "ad": "Egzersiz Yıldızı", "ikon": "💫", "kategori": "egzersiz", "seviye": "gumus", "xp": 10},
    {"kod": "egz_14", "ad": "Beyin Atleti", "ikon": "🧠", "kategori": "egzersiz", "seviye": "altin", "xp": 20},
    {"kod": "orman_ilk", "ad": "İlk Fidan", "ikon": "🌱", "kategori": "orman", "seviye": "bronz", "xp": 3},
    {"kod": "orman_50", "ad": "Küçük Orman", "ikon": "🌿", "kategori": "orman", "seviye": "gumus", "xp": 10},
    {"kod": "orman_200", "ad": "Orman Korucusu", "ikon": "🌳", "kategori": "orman", "seviye": "altin", "xp": 25},
    {"kod": "lig_gumus", "ad": "Gümüş Yolcusu", "ikon": "🥈", "kategori": "lig", "seviye": "gumus", "xp": 10},
    {"kod": "lig_altin", "ad": "Altın Savaşçısı", "ikon": "🥇", "kategori": "lig", "seviye": "altin", "xp": 20},
    {"kod": "lig_elmas", "ad": "Elmas Efsanesi", "ikon": "💎", "kategori": "lig", "seviye": "elmas", "xp": 50},
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
    "metin_ekleme": 5,
    "oylama_katilim": 2,
    "metin_havuza_girme": 10,
    "icerik_ekleme": 5,
    "icerik_oylama": 2,
    "ai_kitap_yukleme": 25,
    "ai_ders_kitabi_yukleme": 40,
    "ai_kitap_onaylandi": 15,
}


async def get_puan_ayarlari():
    doc = await db.sistem_ayarlari.find_one({"tip": "puan_ayarlari"})
    if doc:
        return doc.get("puanlar", VARSAYILAN_PUANLAR)
    return VARSAYILAN_PUANLAR
