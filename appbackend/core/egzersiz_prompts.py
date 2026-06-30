"""Egzersiz Motoru — tip başına AI prompt + mock fallback kütüphanesi.

Her tip için:
  - system: AI sistem yönergesi (Türkçe çıktı ister, "Sadece JSON döndür" ile biter)
  - user(sinif, konu, soru_sayisi, zorluk) -> kullanıcı mesajı
  - mock(sinif, konu, soru_sayisi) -> AI başarısız olursa kullanılacak örnek içerik

Motor bu fonksiyonları çağırır; tip başına özel kod yazılmaz.
Yeni tip eklemek = buraya bir kayıt + core/egzersiz_tipleri.py'ye bir satır.
"""

# Tüm promptların sonuna eklenen ortak kural
_JSON_KURAL = (
    "\n\nÇIKTI KURALI: Yanıtın SADECE geçerli bir JSON nesnesi olsun. "
    "Markdown, kod bloğu işareti (```), açıklama veya başka metin EKLEME. "
    "Tüm metinler Türkçe olsun."
)


def _demo_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "genel kültür"
    return (
        f"Sınıf {sinif} seviyesine uygun, '{konu_str}' konusunda {soru_sayisi} adet "
        f"çoktan seçmeli soru üret. Zorluk: {zorluk or 'orta'}. "
        "Her sorunun 4 seçeneği olsun ve doğru cevabın indeksini (0-3) belirt.\n"
        "JSON şeması: "
        '{"sorular": [{"soru": "...", "secenekler": ["a","b","c","d"], "dogru": 0}]}'
        + _JSON_KURAL
    )


def _demo_mock(sinif, konu, soru_sayisi):
    sorular = []
    for i in range(max(1, soru_sayisi)):
        sorular.append({
            "soru": f"Örnek soru {i + 1} (sınıf {sinif})",
            "secenekler": ["Birinci", "İkinci", "Üçüncü", "Dördüncü"],
            "dogru": i % 4,
        })
    return {"sorular": sorular}


# ─────────────────────────────────────────────────────────────
# Tier 1: 5 temel egzersiz (FAZ 1)
# ─────────────────────────────────────────────────────────────

# Tüm seçmeli tipler için ortak sistem yönergesi
_SISTEM_TR = "Sen ilkokul/ortaokul Türkçe dersi için içerik üreten bir öğretmen asistanısın."


# 1) Kelime-Anlam Eşleştirme — puanlama: eslesme → {"ciftler": [{"sol","sag"}]}
def _eslestirme_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "günlük hayat"
    return (
        f"Sınıf {sinif} seviyesine uygun, '{konu_str}' temasında {soru_sayisi} adet "
        f"kelime ve bu kelimelerin kısa anlamını üret. Zorluk: {zorluk or 'orta'}.\n"
        "JSON şeması: "
        '{"ciftler": [{"sol": "kelime", "sag": "kısa anlamı"}]}'
        + _JSON_KURAL
    )


def _eslestirme_mock(sinif, konu, soru_sayisi):
    havuz = [
        {"sol": "cömert", "sag": "Eli açık, paylaşmayı seven"},
        {"sol": "mütevazı", "sag": "Alçakgönüllü"},
        {"sol": "çevik", "sag": "Hızlı ve atik hareket eden"},
        {"sol": "sabırlı", "sag": "Aceleci olmayan, dayanıklı"},
        {"sol": "dürüst", "sag": "Doğru sözlü, güvenilir"},
        {"sol": "meraklı", "sag": "Öğrenmeye istekli"},
    ]
    return {"ciftler": havuz[: max(2, min(soru_sayisi, len(havuz)))]}


# 2) Boşluk Doldurma (Cloze) — puanlama: secmeli
def _cloze_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "günlük hayat"
    return (
        f"Sınıf {sinif} seviyesine uygun, '{konu_str}' temasında {soru_sayisi} adet "
        f"boşluk doldurma cümlesi üret. Zorluk: {zorluk or 'orta'}. Her cümlede tek bir "
        "boşluk '___' ile gösterilsin; 4 seçenek ver ve doğru seçeneğin indeksini (0-3) belirt.\n"
        "JSON şeması: "
        '{"sorular": [{"soru": "Kuşlar gökyüzünde ___.", "secenekler": ["uçar","yüzer","kazar","erir"], "dogru": 0}]}'
        + _JSON_KURAL
    )


def _cloze_mock(sinif, konu, soru_sayisi):
    havuz = [
        {"soru": "Kuşlar gökyüzünde ___.", "secenekler": ["uçar", "yüzer", "kazar", "erir"], "dogru": 0},
        {"soru": "Balıklar suda ___.", "secenekler": ["koşar", "yüzer", "uçar", "yürür"], "dogru": 1},
        {"soru": "Güneş sabah ___.", "secenekler": ["batar", "söner", "doğar", "kaçar"], "dogru": 2},
        {"soru": "Kar kışın ___.", "secenekler": ["yağar", "biter", "kurur", "akar"], "dogru": 0},
        {"soru": "Arılar bal ___.", "secenekler": ["yer", "yapar", "satar", "atar"], "dogru": 1},
    ]
    return {"sorular": havuz[: max(1, min(soru_sayisi, len(havuz)))]}


# 3) Eş ve Karşıt Anlamlılar — puanlama: secmeli
def _es_karsit_user(sinif, konu, soru_sayisi, zorluk):
    return (
        f"Sınıf {sinif} seviyesine uygun {soru_sayisi} adet eş/karşıt anlamlı kelime sorusu "
        f"üret. Zorluk: {zorluk or 'orta'}. Soru, bir kelimenin eş veya karşıt anlamlısını "
        "sorsun; 4 seçenek ver ve doğru indeksini (0-3) belirt.\n"
        "JSON şeması: "
        '{"sorular": [{"soru": "\'büyük\' kelimesinin karşıt anlamlısı hangisidir?", '
        '"secenekler": ["geniş","küçük","uzun","kalın"], "dogru": 1}]}'
        + _JSON_KURAL
    )


def _es_karsit_mock(sinif, konu, soru_sayisi):
    havuz = [
        {"soru": "'büyük' kelimesinin karşıt anlamlısı hangisidir?",
         "secenekler": ["geniş", "küçük", "uzun", "kalın"], "dogru": 1},
        {"soru": "'mutlu' kelimesinin eş anlamlısı hangisidir?",
         "secenekler": ["sevinçli", "üzgün", "yorgun", "kızgın"], "dogru": 0},
        {"soru": "'açık' kelimesinin karşıt anlamlısı hangisidir?",
         "secenekler": ["temiz", "kapalı", "geniş", "renkli"], "dogru": 1},
        {"soru": "'hızlı' kelimesinin eş anlamlısı hangisidir?",
         "secenekler": ["yavaş", "süratli", "ağır", "sessiz"], "dogru": 1},
        {"soru": "'sıcak' kelimesinin karşıt anlamlısı hangisidir?",
         "secenekler": ["soğuk", "ılık", "yumuşak", "parlak"], "dogru": 0},
    ]
    return {"sorular": havuz[: max(1, min(soru_sayisi, len(havuz)))]}


# 4) Karışık Cümle Sıralama — puanlama: sira → {"parcalar":[...], "dogru_sira":[...]}
def _cumle_siralama_user(sinif, konu, soru_sayisi, zorluk):
    return (
        f"Sınıf {sinif} seviyesine uygun, {soru_sayisi} kelimeden oluşan anlamlı bir Türkçe "
        f"cümle seç. Zorluk: {zorluk or 'orta'}. Kelimeleri karışık sırayla 'parcalar' dizisinde "
        "ver; 'dogru_sira' ise bu parçaların doğru cümleyi oluşturan indeks sırası olsun.\n"
        "JSON şeması: "
        '{"parcalar": ["okula","Ben","gidiyorum"], "dogru_sira": [1,0,2]}'
        + _JSON_KURAL
    )


def _cumle_siralama_mock(sinif, konu, soru_sayisi):
    # "Ben her sabah okula gidiyorum" — karışık parçalar + doğru sıra
    return {
        "parcalar": ["okula", "Ben", "gidiyorum", "her", "sabah"],
        "dogru_sira": [1, 3, 4, 0, 2],
        "cumle": "Ben her sabah okula gidiyorum",
    }


# 5) Hikâye Olay Sıralama — puanlama: sira → {"olaylar":[...], "dogru_sira":[...]}
def _olay_siralama_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "kısa bir hikâye"
    return (
        f"Sınıf {sinif} seviyesine uygun, '{konu_str}' hakkında {soru_sayisi} olaydan oluşan "
        f"kısa bir hikâye kur. Zorluk: {zorluk or 'orta'}. Olayları karışık sırayla 'olaylar' "
        "dizisinde ver; 'dogru_sira' ise olayların gerçekleşme sırasına göre indeksleri olsun.\n"
        "JSON şeması: "
        '{"olaylar": ["Ali uyandı.","Ali kahvaltı yaptı.","Ali okula gitti."], "dogru_sira": [0,1,2]}'
        + _JSON_KURAL
    )


def _olay_siralama_mock(sinif, konu, soru_sayisi):
    return {
        "olaylar": [
            "Tohum toprağa düştü.",
            "Çiçek açtı.",
            "Filiz topraktan çıktı.",
            "Yağmur yağdı.",
        ],
        "dogru_sira": [0, 3, 2, 1],
    }


# Tip -> {system, user, mock}
PROMPTLAR = {
    "demo": {
        "system": "Sen Türkçe eğitim içeriği üreten bir asistansın.",
        "user": _demo_user,
        "mock": _demo_mock,
    },
    "kelime_anlam_eslestirme": {
        "system": _SISTEM_TR,
        "user": _eslestirme_user,
        "mock": _eslestirme_mock,
    },
    "cloze_bosluk_doldurma": {
        "system": _SISTEM_TR,
        "user": _cloze_user,
        "mock": _cloze_mock,
    },
    "es_karsit_anlamli": {
        "system": _SISTEM_TR,
        "user": _es_karsit_user,
        "mock": _es_karsit_mock,
    },
    "karisik_cumle_siralama": {
        "system": _SISTEM_TR,
        "user": _cumle_siralama_user,
        "mock": _cumle_siralama_mock,
    },
    "hikaye_olay_siralama": {
        "system": _SISTEM_TR,
        "user": _olay_siralama_user,
        "mock": _olay_siralama_mock,
    },
}


def prompt_var_mi(tip: str) -> bool:
    return tip in PROMPTLAR


def prompt_uret(tip: str, sinif: int, konu: str | None, soru_sayisi: int, zorluk: str | None):
    """(system, user_message) ikilisini döndürür. Bilinmeyen tip → (None, None)."""
    p = PROMPTLAR.get(tip)
    if not p:
        return None, None
    return p["system"], p["user"](sinif, konu, soru_sayisi, zorluk)


def mock_uret(tip: str, sinif: int, konu: str | None, soru_sayisi: int) -> dict:
    """AI başarısız olduğunda kullanılacak örnek içerik."""
    p = PROMPTLAR.get(tip)
    if not p:
        return {"sorular": []}
    return p["mock"](sinif, konu, soru_sayisi)
