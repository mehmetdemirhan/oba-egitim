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


# ─────────────────────────────────────────────────────────────
# Tier 2: Okuduğunu anlama (FAZ 2)
# Ortak şema: {"metin": "kısa paragraf", "sorular": [{soru, secenekler, dogru}]}
# puanlama = "secmeli"; render metni bir kez üstte gösterir.
# ─────────────────────────────────────────────────────────────

def _metinli_user(odak):
    """Belirli bir okuduğunu anlama odağı için metin+seçmeli prompt üretici."""
    def fn(sinif, konu, soru_sayisi, zorluk):
        konu_str = konu or "günlük hayattan bir olay"
        return (
            f"Sınıf {sinif} seviyesine uygun, '{konu_str}' hakkında 3-5 cümlelik kısa bir "
            f"Türkçe paragraf yaz. Zorluk: {zorluk or 'orta'}. Ardından bu paragrafa dayalı, "
            f"{odak} ölçen {soru_sayisi} adet çoktan seçmeli soru üret. Her sorunun 4 seçeneği "
            "olsun ve doğru seçeneğin indeksini (0-3) belirt.\n"
            "JSON şeması: "
            '{"metin": "kısa paragraf", "sorular": [{"soru": "...", "secenekler": ["a","b","c","d"], "dogru": 0}]}'
            + _JSON_KURAL
        )
    return fn


def _metinli_mock_fabrika(metin, sorular):
    def fn(sinif, konu, soru_sayisi):
        return {"metin": metin, "sorular": sorular[: max(1, min(soru_sayisi, len(sorular)))]}
    return fn


_5N1K_METIN = (
    "Ayşe, cumartesi sabahı erkenden kalktı. Annesiyle birlikte pazara gitti ve "
    "taze sebze aldılar. Eve dönünce birlikte çorba yaptılar."
)
_5n1k_mock = _metinli_mock_fabrika(_5N1K_METIN, [
    {"soru": "Pazara kim gitti?", "secenekler": ["Ayşe ve annesi", "Ayşe ve babası", "Sadece annesi", "Komşular"], "dogru": 0},
    {"soru": "Ayşe ne zaman kalktı?", "secenekler": ["Cumartesi sabahı", "Pazar akşamı", "Hafta içi", "Gece"], "dogru": 0},
    {"soru": "Pazardan ne aldılar?", "secenekler": ["Taze sebze", "Oyuncak", "Kitap", "Giysi"], "dogru": 0},
    {"soru": "Eve dönünce ne yaptılar?", "secenekler": ["Çorba yaptılar", "Uyudular", "Dışarı çıktılar", "Televizyon izlediler"], "dogru": 0},
])

_ANA_FIKIR_METIN = (
    "Ormanlar, dünyamız için çok önemlidir. Havayı temizler, birçok canlıya ev sahipliği "
    "yapar ve toprağı korur. Bu yüzden ağaçları korumalı ve yenilerini dikmeliyiz."
)
_ana_fikir_mock = _metinli_mock_fabrika(_ANA_FIKIR_METIN, [
    {"soru": "Metnin ana fikri nedir?", "secenekler": ["Ormanları korumalıyız", "Ağaçlar uzundur", "Hayvanlar koşar", "Yaz sıcaktır"], "dogru": 0},
    {"soru": "Ormanlar havaya ne yapar?", "secenekler": ["Temizler", "Kirletir", "Isıtır", "Hiçbir şey"], "dogru": 0},
    {"soru": "Metne göre ne yapmalıyız?", "secenekler": ["Yeni ağaçlar dikmeliyiz", "Ağaçları kesmeliyiz", "Ormanı yakmalıyız", "Hiçbir şey yapmamalıyız"], "dogru": 0},
    {"soru": "Ormanlar kimlere ev olur?", "secenekler": ["Birçok canlıya", "Sadece kuşlara", "Sadece insanlara", "Hiç kimseye"], "dogru": 0},
])

_CIKARIM_METIN = (
    "Ali sabah pencereden dışarı baktı. Yerler ıslaktı ve insanlar şemsiyelerini "
    "kapatıyordu. Gökyüzü yavaş yavaş açılıyordu."
)
_cikarim_mock = _metinli_mock_fabrika(_CIKARIM_METIN, [
    {"soru": "Az önce ne olmuş olabilir?", "secenekler": ["Yağmur yağmış", "Kar yağmış", "Çok sıcak olmuş", "Fırtına çıkmış"], "dogru": 0},
    {"soru": "Hava şu an nasıl?", "secenekler": ["Açılıyor", "Karlı", "Sisli", "Çok karanlık"], "dogru": 0},
    {"soru": "İnsanlar neden şemsiye taşıyordu?", "secenekler": ["Yağmur yağdığı için", "Güneş için", "Süs için", "Rüzgâr için"], "dogru": 0},
    {"soru": "Yerlerin ıslak olması neyi gösterir?", "secenekler": ["Yağış olduğunu", "Sıcak olduğunu", "Gece olduğunu", "Kuru olduğunu"], "dogru": 0},
])

_SEBEP_SONUC_METIN = (
    "Murat ödevini zamanında yapmadı. Bu yüzden öğretmeni ona ek ödev verdi. "
    "Murat o akşam parka gidemedi."
)
_sebep_sonuc_mock = _metinli_mock_fabrika(_SEBEP_SONUC_METIN, [
    {"soru": "Murat neden ek ödev aldı?", "secenekler": ["Ödevini yapmadığı için", "Hasta olduğu için", "Geç kaldığı için", "Konuştuğu için"], "dogru": 0},
    {"soru": "Murat neden parka gidemedi?", "secenekler": ["Ek ödevi olduğu için", "Hava kötü olduğu için", "Yorgun olduğu için", "Para olmadığı için"], "dogru": 0},
    {"soru": "Ödevi zamanında yapsaydı ne olurdu?", "secenekler": ["Ek ödev almazdı", "Yine ceza alırdı", "Okula gitmezdi", "Uyuyamazdı"], "dogru": 0},
    {"soru": "Olayın sonucu nedir?", "secenekler": ["Parka gidememesi", "Hasta olması", "Ödül alması", "Tatile çıkması"], "dogru": 0},
])

_TAHMIN_METIN = (
    "Elif yeni bir tohum ekti ve her gün düzenli olarak suladı. Birkaç gün sonra "
    "topraktan küçük yeşil bir filiz çıkmaya başladı."
)
_tahmin_mock = _metinli_mock_fabrika(_TAHMIN_METIN, [
    {"soru": "Bundan sonra ne olması beklenir?", "secenekler": ["Filiz büyüyüp bitki olur", "Tohum kaybolur", "Toprak donar", "Filiz küçülür"], "dogru": 0},
    {"soru": "Elif bitkinin büyümesi için ne yapmalı?", "secenekler": ["Sulamaya devam etmeli", "Suyu kesmeli", "Tohumu çıkarmalı", "Karanlığa koymalı"], "dogru": 0},
    {"soru": "Filizin çıkması neyi gösterir?", "secenekler": ["Tohumun canlandığını", "Tohumun kuruduğunu", "Toprağın bozulduğunu", "Suyun bittiğini"], "dogru": 0},
    {"soru": "Zamanla bitki ne verebilir?", "secenekler": ["Çiçek veya meyve", "Taş", "Kar", "Hiçbir şey"], "dogru": 0},
])


# ─────────────────────────────────────────────────────────────
# Tier 3: Kelime oyunları (FAZ 3)
# ─────────────────────────────────────────────────────────────

# 1) Anagram — puanlama: serbest → {"kelime","karisik","ipucu"} (istemci puanlar)
def _anagram_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "günlük hayat"
    return (
        f"Sınıf {sinif} seviyesine uygun, '{konu_str}' temasında Türkçe tek bir kelime seç "
        f"(4-7 harf). Zorluk: {zorluk or 'orta'}. Kelimeyi 'kelime' alanında ver; 'karisik' "
        "alanında harflerini karışık sırayla tire ile ayırarak ver; 'ipucu' alanında kelimenin "
        "anlamına dair kısa bir ipucu yaz.\n"
        "JSON şeması: "
        '{"kelime": "kalem", "karisik": "m-l-a-e-k", "ipucu": "Yazı yazmaya yarayan araç"}'
        + _JSON_KURAL
    )


def _anagram_mock(sinif, konu, soru_sayisi):
    return {"kelime": "kalem", "karisik": "m-l-a-e-k", "ipucu": "Yazı yazmaya yarayan araç"}


# 2) Kelime Bulmaca — puanlama: serbest → {"kelimeler":[{ipucu,cevap}]} (ipucu → kelime)
def _bulmaca_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "günlük hayat"
    return (
        f"Sınıf {sinif} seviyesine uygun, '{konu_str}' temasında ipucu-kelime biçiminde 4 adet "
        f"bulmaca öğesi üret. Zorluk: {zorluk or 'orta'}. Her öğede kısa bir 'ipucu' ve bu "
        "ipucunun yanıtı olan tek kelimelik 'cevap' bulunsun.\n"
        "JSON şeması: "
        '{"kelimeler": [{"ipucu": "Gökyüzünde uçan tüylü canlı", "cevap": "kuş"}]}'
        + _JSON_KURAL
    )


def _bulmaca_mock(sinif, konu, soru_sayisi):
    return {"kelimeler": [
        {"ipucu": "Gökyüzünde uçan tüylü canlı", "cevap": "kuş"},
        {"ipucu": "Yazı yazmaya yarayan araç", "cevap": "kalem"},
        {"ipucu": "Geceleri gökyüzünde parlar", "cevap": "yıldız"},
        {"ipucu": "Süt veren evcil hayvan", "cevap": "inek"},
    ]}


# 3) Hafıza Kartları — puanlama: serbest → {"ciftler":[{sol,sag}]} (eşleştirme oyunu)
def _hafiza_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "günlük hayat"
    return (
        f"Sınıf {sinif} seviyesine uygun, '{konu_str}' temasında 4-6 adet kelime ve kısa anlamı "
        f"üret. Zorluk: {zorluk or 'orta'}. Hafıza oyununda kelime-anlam çiftleri eşleştirilecek.\n"
        "JSON şeması: "
        '{"ciftler": [{"sol": "cömert", "sag": "Eli açık"}]}'
        + _JSON_KURAL
    )


def _hafiza_mock(sinif, konu, soru_sayisi):
    return {"ciftler": [
        {"sol": "cömert", "sag": "Eli açık"},
        {"sol": "çevik", "sag": "Hızlı hareket eden"},
        {"sol": "dürüst", "sag": "Doğru sözlü"},
        {"sol": "sabırlı", "sag": "Acele etmeyen"},
    ]}


# 4) Kelime Yağmuru — puanlama: serbest → {"hedef","dogrular","yanlislar"} (zamana karşı)
def _yagmur_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "meyveler"
    return (
        f"Sınıf {sinif} seviyesine uygun bir kategori seç (örn. '{konu_str}'). "
        f"Zorluk: {zorluk or 'orta'}. 'hedef' alanında oyuncudan hangi kelimeleri yakalamasını "
        "istediğini kısaca açıkla; 'dogrular' alanında kategoriye uyan 6 kelime, 'yanlislar' "
        "alanında uymayan 6 kelime ver.\n"
        "JSON şeması: "
        '{"hedef": "Meyve isimlerini yakala", "dogrular": ["elma","armut"], "yanlislar": ["masa","kalem"]}'
        + _JSON_KURAL
    )


def _yagmur_mock(sinif, konu, soru_sayisi):
    return {
        "hedef": "Meyve isimlerini yakala",
        "dogrular": ["elma", "armut", "kiraz", "muz", "üzüm", "çilek"],
        "yanlislar": ["masa", "kalem", "araba", "kapı", "taş", "defter"],
    }


# 5) Kelime Merdiveni — puanlama: secmeli (tek harf değişimi)
def _merdiven_user(sinif, konu, soru_sayisi, zorluk):
    return (
        f"Sınıf {sinif} seviyesine uygun {soru_sayisi} adet 'kelime merdiveni' sorusu üret. "
        f"Zorluk: {zorluk or 'orta'}. Her soruda bir kelimenin tek bir harfini değiştirerek elde "
        "edilen yeni anlamlı kelimeyi sor; 4 seçenek ver ve doğru indeksini (0-3) belirt.\n"
        "JSON şeması: "
        '{"sorular": [{"soru": "\'kar\' kelimesinin ilk harfini değiştirerek hangi kelimeyi elde edersin?", '
        '"secenekler": ["bar","göl","taş","el"], "dogru": 0}]}'
        + _JSON_KURAL
    )


def _merdiven_mock(sinif, konu, soru_sayisi):
    havuz = [
        {"soru": "'kar' kelimesinin ilk harfini değiştirerek hangi kelimeyi elde edersin?",
         "secenekler": ["bar", "göl", "taş", "el"], "dogru": 0},
        {"soru": "'taş' kelimesinin ilk harfini değiştirerek hangi kelimeyi elde edersin?",
         "secenekler": ["kuş", "baş", "göz", "el"], "dogru": 1},
        {"soru": "'kol' kelimesinin son harfini değiştirerek hangi kelimeyi elde edersin?",
         "secenekler": ["kel", "koş", "kor", "yol"], "dogru": 2},
        {"soru": "'el' kelimesinin başına bir harf ekleyerek hangi kelimeyi elde edersin?",
         "secenekler": ["bel", "araba", "kalem", "masa"], "dogru": 0},
    ]
    return {"sorular": havuz[: max(1, min(soru_sayisi, len(havuz)))]}


# 6) Bağlam İpucu — puanlama: secmeli (cümle ipuçlarından anlam)
def _baglam_user(sinif, konu, soru_sayisi, zorluk):
    return (
        f"Sınıf {sinif} seviyesine uygun {soru_sayisi} adet 'bağlam ipucu' sorusu üret. "
        f"Zorluk: {zorluk or 'orta'}. Her soruda içinde az bilinen bir kelimenin (*yıldız* içinde) "
        "geçtiği bir cümle ver ve cümledeki ipuçlarından o kelimenin anlamını sor; 4 seçenek ver "
        "ve doğru indeksini (0-3) belirt.\n"
        "JSON şeması: "
        '{"sorular": [{"soru": "\'Hava çok *puslu* olduğu için karşıyı zor görüyorduk.\' '
        'Buradaki *puslu* ne demektir?", "secenekler": ["sisli","güneşli","sıcak","renkli"], "dogru": 0}]}'
        + _JSON_KURAL
    )


def _baglam_mock(sinif, konu, soru_sayisi):
    havuz = [
        {"soru": "'Hava çok *puslu* olduğu için karşıyı zor görüyorduk.' Buradaki *puslu* ne demektir?",
         "secenekler": ["sisli", "güneşli", "sıcak", "renkli"], "dogru": 0},
        {"soru": "'Çocuk çok *müteşekkir* görünüyordu, sürekli teşekkür ediyordu.' Buradaki *müteşekkir* ne demektir?",
         "secenekler": ["teşekkür eden", "kızgın", "üzgün", "yorgun"], "dogru": 0},
        {"soru": "'Yolcular *meşakkatli* bir tırmanıştan sonra zirveye ulaştı.' Buradaki *meşakkatli* ne demektir?",
         "secenekler": ["yorucu", "kolay", "kısa", "neşeli"], "dogru": 0},
        {"soru": "'Bahçe rengârenk çiçeklerle *bezenmiş*ti.' Buradaki *bezenmiş* ne demektir?",
         "secenekler": ["süslenmiş", "kurumuş", "boşalmış", "kararmış"], "dogru": 0},
    ]
    return {"sorular": havuz[: max(1, min(soru_sayisi, len(havuz)))]}


# ─────────────────────────────────────────────────────────────
# Tier 4: Gelişmiş beceriler (FAZ 4) — hepsi çoktan seçmeli
# ─────────────────────────────────────────────────────────────

# 1) Frayer Modeli — {"kelime", sorular:[{soru, secenekler, dogru}]}
def _frayer_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "bir kavram"
    return (
        f"Sınıf {sinif} seviyesine uygun, '{konu_str}' ile ilgili bir kelime seç. "
        f"Zorluk: {zorluk or 'orta'}. Kelimeyi 'kelime' alanında ver. Ardından {soru_sayisi} adet "
        "ifade üret; her ifade için öğrenci ifadenin Frayer modelindeki hangi bölgeye ait "
        "olduğunu seçecek. Seçenekler her soruda aynı olsun: "
        '["Tanım","Özellik","Örnek","Örnek Değil"]. Doğru bölgenin indeksini (0-3) belirt.\n'
        "JSON şeması: "
        '{"kelime": "meyve", "sorular": [{"soru": "Elma bir meyvedir.", '
        '"secenekler": ["Tanım","Özellik","Örnek","Örnek Değil"], "dogru": 2}]}'
        + _JSON_KURAL
    )


def _frayer_mock(sinif, konu, soru_sayisi):
    se = ["Tanım", "Özellik", "Örnek", "Örnek Değil"]
    havuz = [
        {"soru": "Ağaçlarda yetişen, yenilebilen bitkisel besindir.", "secenekler": se, "dogru": 0},
        {"soru": "Genellikle tatlı veya ekşi olur, vitamin içerir.", "secenekler": se, "dogru": 1},
        {"soru": "Elma, armut ve kiraz birer örnektir.", "secenekler": se, "dogru": 2},
        {"soru": "Masa bir meyve değildir.", "secenekler": se, "dogru": 3},
    ]
    return {"kelime": "meyve", "sorular": havuz[: max(1, min(soru_sayisi, len(havuz)))]}


# 2) Anlam Haritası — {"merkez", sorular:[...]}
def _anlam_haritasi_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "okul"
    return (
        f"Sınıf {sinif} seviyesine uygun bir merkez kelime seç (örn. '{konu_str}'). "
        f"Zorluk: {zorluk or 'orta'}. Kelimeyi 'merkez' alanında ver. {soru_sayisi} adet çoktan "
        "seçmeli soru üret; her soru merkez kelimeyle ilişkili olanı sorsun. 4 seçenek ve doğru "
        "indeksi (0-3).\n"
        "JSON şeması: "
        '{"merkez": "okul", "sorular": [{"soru": "Hangisi okul ile ilişkilidir?", '
        '"secenekler": ["öğretmen","balina","gemi","çöl"], "dogru": 0}]}'
        + _JSON_KURAL
    )


def _anlam_haritasi_mock(sinif, konu, soru_sayisi):
    havuz = [
        {"soru": "Hangisi okul ile ilişkilidir?", "secenekler": ["öğretmen", "balina", "gemi", "çöl"], "dogru": 0},
        {"soru": "Okulda hangisini kullanırız?", "secenekler": ["defter", "çapa", "yelken", "olta"], "dogru": 0},
        {"soru": "Hangisi okulda olan bir kişidir?", "secenekler": ["öğrenci", "kaptan", "çiftçi", "pilot"], "dogru": 0},
        {"soru": "Okulda hangi etkinlik yapılır?", "secenekler": ["ders", "avlanma", "denizcilik", "madencilik"], "dogru": 0},
    ]
    return {"merkez": "okul", "sorular": havuz[: max(1, min(soru_sayisi, len(havuz)))]}


# 3) Venn Şeması — {"a","b", sorular:[{soru, secenekler:[a,b,"Her ikisi"], dogru}]}
def _venn_user(sinif, konu, soru_sayisi, zorluk):
    return (
        f"Sınıf {sinif} seviyesine uygun, karşılaştırılabilecek iki kavram seç ('a' ve 'b'). "
        f"Zorluk: {zorluk or 'orta'}. {soru_sayisi} adet özellik üret; her özellik için öğrenci "
        "özelliğin yalnız a'ya mı, yalnız b'ye mi yoksa her ikisine mi ait olduğunu seçecek. "
        'Seçenekler: [a, b, "Her ikisi"]. Doğru indeksi (0-2) belirt.\n'
        "JSON şeması: "
        '{"a": "Kedi", "b": "Balık", "sorular": [{"soru": "Suda yaşar.", '
        '"secenekler": ["Kedi","Balık","Her ikisi"], "dogru": 1}]}'
        + _JSON_KURAL
    )


def _venn_mock(sinif, konu, soru_sayisi):
    a, b = "Kedi", "Balık"
    se = [a, b, "Her ikisi"]
    havuz = [
        {"soru": "Suda yaşar.", "secenekler": se, "dogru": 1},
        {"soru": "Tüyleri vardır.", "secenekler": se, "dogru": 0},
        {"soru": "Bir canlıdır.", "secenekler": se, "dogru": 2},
        {"soru": "Karada yürür.", "secenekler": se, "dogru": 0},
    ]
    return {"a": a, "b": b, "sorular": havuz[: max(1, min(soru_sayisi, len(havuz)))]}


# 4) Tekerleme — {"metin", sorular:[...]}  (metin+secmeli)
def _tekerleme_user(sinif, konu, soru_sayisi, zorluk):
    return (
        f"Sınıf {sinif} seviyesine uygun, kısa ve eğlenceli bir Türkçe tekerleme yaz "
        f"(2-4 satır). Zorluk: {zorluk or 'kolay'}. Tekerlemeyi 'metin' alanında ver. Ardından "
        f"{soru_sayisi} adet çoktan seçmeli soru üret (uyaklı kelime, eksik kelime veya ses "
        "tekrarı hakkında). 4 seçenek ve doğru indeksi (0-3).\n"
        "JSON şeması: "
        '{"metin": "Dağda davul çalınır...", "sorular": [{"soru": "...", '
        '"secenekler": ["a","b","c","d"], "dogru": 0}]}'
        + _JSON_KURAL
    )


_TEKERLEME_METIN = (
    "Komşunun kuru kuyusu,\n"
    "Kara kazan kapkara.\n"
    "Bir berber bir berbere,\n"
    "Gel beraber bir berber dükkânı açalım dedi."
)


def _tekerleme_mock_fn(sinif, konu, soru_sayisi):
    havuz = [
        {"soru": "Tekerlemede hangi ses sık tekrar ediyor?", "secenekler": ["b", "z", "f", "ç"], "dogru": 0},
        {"soru": "'berber' kelimesiyle uyaklı olan hangisidir?", "secenekler": ["beraber", "kalem", "deniz", "okul"], "dogru": 0},
        {"soru": "'Kara kazan ___' boşluğa hangisi gelir?", "secenekler": ["kapkara", "bembeyaz", "sapsarı", "yemyeşil"], "dogru": 0},
        {"soru": "Tekerleme neyle ilgilidir?", "secenekler": ["berber dükkânı", "uçak", "deniz", "orman"], "dogru": 0},
    ]
    return {"metin": _TEKERLEME_METIN, "sorular": havuz[: max(1, min(soru_sayisi, len(havuz)))]}


# 5) Sight Words (sık kullanılan kelimeler) — {"sorular":[...]}
def _sight_user(sinif, konu, soru_sayisi, zorluk):
    return (
        f"Sınıf {sinif} seviyesine uygun, Türkçede sık kullanılan kelimelerle {soru_sayisi} adet "
        f"hızlı tanıma sorusu üret. Zorluk: {zorluk or 'kolay'}. Soru, bir kelimeyi doğru "
        "yazımıyla tanımayı ölçsün; 4 seçenek (biri doğru yazım) ver, doğru indeksi (0-3).\n"
        "JSON şeması: "
        '{"sorular": [{"soru": "Hangisi doğru yazılmıştır?", '
        '"secenekler": ["geliyor","geliyo","gliyor","gelior"], "dogru": 0}]}'
        + _JSON_KURAL
    )


def _sight_mock(sinif, konu, soru_sayisi):
    havuz = [
        {"soru": "Hangisi doğru yazılmıştır?", "secenekler": ["geliyor", "geliyo", "gliyor", "gelior"], "dogru": 0},
        {"soru": "Hangisi doğru yazılmıştır?", "secenekler": ["çünkü", "çünki", "çünkü̇", "cunku"], "dogru": 0},
        {"soru": "Hangisi doğru yazılmıştır?", "secenekler": ["birçok", "bir cok", "birçoğ", "birçokk"], "dogru": 0},
        {"soru": "Hangisi doğru yazılmıştır?", "secenekler": ["şöyle", "şöle", "şuyle", "soyle"], "dogru": 0},
        {"soru": "Hangisi doğru yazılmıştır?", "secenekler": ["herkes", "herkez", "herkeş", "her kez"], "dogru": 0},
    ]
    return {"sorular": havuz[: max(1, min(soru_sayisi, len(havuz)))]}


# 6) Diyalog — {"metin", sorular:[...]}  (konuşma + secmeli)
def _diyalog_user(sinif, konu, soru_sayisi, zorluk):
    konu_str = konu or "günlük bir konuşma"
    return (
        f"Sınıf {sinif} seviyesine uygun, '{konu_str}' hakkında iki kişi arasında kısa bir diyalog "
        f"yaz (her satır 'Ad: söz' biçiminde). Zorluk: {zorluk or 'orta'}. Diyaloğu 'metin' "
        f"alanında ver. Ardından {soru_sayisi} adet çoktan seçmeli soru üret (konuşmanın anlamı, "
        "uygun yanıt veya duygu hakkında). 4 seçenek ve doğru indeksi (0-3).\n"
        "JSON şeması: "
        '{"metin": "Ali: Merhaba!\\nAyşe: Merhaba, nasılsın?", "sorular": [{"soru": "...", '
        '"secenekler": ["a","b","c","d"], "dogru": 0}]}'
        + _JSON_KURAL
    )


_DIYALOG_METIN = (
    "Ali: Merhaba Ayşe, bugün parka gelecek misin?\n"
    "Ayşe: Merhaba Ali! Çok isterdim ama ödevimi bitirmem gerek.\n"
    "Ali: O zaman ödevini bitirince beni ara, birlikte gideriz.\n"
    "Ayşe: Tamam, anlaştık!"
)
_diyalog_mock = _metinli_mock_fabrika(_DIYALOG_METIN, [
    {"soru": "Ali, Ayşe'yi nereye davet ediyor?", "secenekler": ["Parka", "Sinemaya", "Okula", "Markete"], "dogru": 0},
    {"soru": "Ayşe neden hemen gelemiyor?", "secenekler": ["Ödevi olduğu için", "Hasta olduğu için", "Yorgun olduğu için", "Uzakta olduğu için"], "dogru": 0},
    {"soru": "Ayşe ödevini bitirince ne yapacak?", "secenekler": ["Ali'yi arayacak", "Uyuyacak", "Markete gidecek", "Televizyon izleyecek"], "dogru": 0},
    {"soru": "Konuşmanın sonunda ne oldu?", "secenekler": ["Anlaştılar", "Tartıştılar", "Vazgeçtiler", "Küstüler"], "dogru": 0},
])


# ─────────────────────────────────────────────────────────────
# FAZ 5: Fonolojik farkındalık (1-2. sınıf) — hepsi çoktan seçmeli
# Şema: {"sorular":[{soru, secenekler, dogru, seslendir}]}
# 'seslendir' = render katmanında Web Speech API ile okunacak metin.
# ─────────────────────────────────────────────────────────────

_SISTEM_FONOLOJI = (
    "Sen 1-2. sınıf öğrencileri için fonolojik farkındalık (ses ve hece) "
    "etkinlikleri hazırlayan bir öğretmen asistanısın. Dil sade ve kısa olsun."
)


def _fonoloji_user(odak, ornek):
    """Belirli bir fonolojik odak için çoktan seçmeli prompt üretici."""
    def fn(sinif, konu, soru_sayisi, zorluk):
        konu_str = konu or "basit kelimeler"
        return (
            f"1-2. sınıf seviyesine uygun, '{konu_str}' temasında {soru_sayisi} adet soru üret: "
            f"{odak} Her soruda 4 seçenek ve doğru indeksi (0-3) bulunsun. Ayrıca her soru için "
            "'seslendir' alanında sesli okunacak metni (kelime veya heceler) ver; küçük yaş için "
            "kısa ve net olsun.\n"
            "JSON şeması: " + ornek + _JSON_KURAL
        )
    return fn


def _fon_mock(havuz):
    def fn(sinif, konu, soru_sayisi):
        return {"sorular": havuz[: max(1, min(soru_sayisi, len(havuz)))]}
    return fn


_hece_sayma_mock = _fon_mock([
    {"soru": "'kelebek' kelimesi kaç hecelidir?", "secenekler": ["2", "3", "4", "5"], "dogru": 1, "seslendir": "kelebek"},
    {"soru": "'ev' kelimesi kaç hecelidir?", "secenekler": ["1", "2", "3", "4"], "dogru": 0, "seslendir": "ev"},
    {"soru": "'masa' kelimesi kaç hecelidir?", "secenekler": ["1", "2", "3", "4"], "dogru": 1, "seslendir": "masa"},
    {"soru": "'okul' kelimesi kaç hecelidir?", "secenekler": ["1", "2", "3", "4"], "dogru": 1, "seslendir": "okul"},
    {"soru": "'araba' kelimesi kaç hecelidir?", "secenekler": ["2", "3", "4", "5"], "dogru": 1, "seslendir": "araba"},
])

_hece_birlestirme_mock = _fon_mock([
    {"soru": "ki + tap heceleri hangi kelimeyi oluşturur?", "secenekler": ["kitap", "kapı", "tapu", "kütük"], "dogru": 0, "seslendir": "ki, tap"},
    {"soru": "ka + lem heceleri hangi kelimeyi oluşturur?", "secenekler": ["kalem", "kale", "lema", "mekal"], "dogru": 0, "seslendir": "ka, lem"},
    {"soru": "el + ma heceleri hangi kelimeyi oluşturur?", "secenekler": ["elma", "mela", "emal", "alem"], "dogru": 0, "seslendir": "el, ma"},
    {"soru": "ka + pı heceleri hangi kelimeyi oluşturur?", "secenekler": ["kapı", "pıka", "akıp", "paki"], "dogru": 0, "seslendir": "ka, pı"},
    {"soru": "ta + vuk heceleri hangi kelimeyi oluşturur?", "secenekler": ["tavuk", "vukta", "kutav", "vakti"], "dogru": 0, "seslendir": "ta, vuk"},
])

_ilk_ses_mock = _fon_mock([
    {"soru": "'elma' kelimesi hangi sesle başlar?", "secenekler": ["e", "a", "l", "m"], "dogru": 0, "seslendir": "elma"},
    {"soru": "'kapı' kelimesi hangi sesle başlar?", "secenekler": ["k", "a", "p", "ı"], "dogru": 0, "seslendir": "kapı"},
    {"soru": "'top' kelimesi hangi sesle başlar?", "secenekler": ["t", "o", "p", "s"], "dogru": 0, "seslendir": "top"},
    {"soru": "'armut' kelimesi hangi sesle başlar?", "secenekler": ["a", "r", "m", "u"], "dogru": 0, "seslendir": "armut"},
    {"soru": "'balık' kelimesi hangi sesle başlar?", "secenekler": ["b", "a", "l", "k"], "dogru": 0, "seslendir": "balık"},
])

_son_ses_mock = _fon_mock([
    {"soru": "'kalem' kelimesi hangi sesle biter?", "secenekler": ["m", "k", "e", "l"], "dogru": 0, "seslendir": "kalem"},
    {"soru": "'top' kelimesi hangi sesle biter?", "secenekler": ["p", "t", "o", "s"], "dogru": 0, "seslendir": "top"},
    {"soru": "'kapı' kelimesi hangi sesle biter?", "secenekler": ["ı", "k", "a", "p"], "dogru": 0, "seslendir": "kapı"},
    {"soru": "'armut' kelimesi hangi sesle biter?", "secenekler": ["t", "a", "r", "u"], "dogru": 0, "seslendir": "armut"},
    {"soru": "'elma' kelimesi hangi sesle biter?", "secenekler": ["a", "e", "l", "m"], "dogru": 0, "seslendir": "elma"},
])

_kafiye_mock = _fon_mock([
    {"soru": "'top' ile kafiyeli olan hangisidir?", "secenekler": ["hop", "kedi", "araba", "masa"], "dogru": 0, "seslendir": "top"},
    {"soru": "'kar' ile kafiyeli olan hangisidir?", "secenekler": ["nar", "ev", "göl", "su"], "dogru": 0, "seslendir": "kar"},
    {"soru": "'masa' ile kafiyeli olan hangisidir?", "secenekler": ["kasa", "kalem", "deniz", "okul"], "dogru": 0, "seslendir": "masa"},
    {"soru": "'el' ile kafiyeli olan hangisidir?", "secenekler": ["bel", "kapı", "araba", "kuş"], "dogru": 0, "seslendir": "el"},
    {"soru": "'kale' ile kafiyeli olan hangisidir?", "secenekler": ["lale", "kitap", "deniz", "top"], "dogru": 0, "seslendir": "kale"},
])

_ses_birlestirme_mock = _fon_mock([
    {"soru": "k - e - d - i sesleri hangi kelimeyi oluşturur?", "secenekler": ["kedi", "deri", "kalem", "dere"], "dogru": 0, "seslendir": "k, e, d, i"},
    {"soru": "e - l sesleri hangi kelimeyi oluşturur?", "secenekler": ["el", "le", "al", "ol"], "dogru": 0, "seslendir": "e, l"},
    {"soru": "t - o - p sesleri hangi kelimeyi oluşturur?", "secenekler": ["top", "pot", "opt", "tos"], "dogru": 0, "seslendir": "t, o, p"},
    {"soru": "a - r - ı sesleri hangi kelimeyi oluşturur?", "secenekler": ["arı", "ıra", "rai", "ira"], "dogru": 0, "seslendir": "a, r, ı"},
    {"soru": "s - u sesleri hangi kelimeyi oluşturur?", "secenekler": ["su", "us", "as", "os"], "dogru": 0, "seslendir": "s, u"},
])

_ses_cikarma_mock = _fon_mock([
    {"soru": "'kitap' kelimesinden 'ki' hecesi atılırsa ne kalır?", "secenekler": ["tap", "ki", "kit", "pat"], "dogru": 0, "seslendir": "kitap"},
    {"soru": "'kalem' kelimesinden 'ka' hecesi atılırsa ne kalır?", "secenekler": ["lem", "ka", "kal", "mek"], "dogru": 0, "seslendir": "kalem"},
    {"soru": "'armut' kelimesinden 'ar' hecesi atılırsa ne kalır?", "secenekler": ["mut", "ar", "arm", "tum"], "dogru": 0, "seslendir": "armut"},
    {"soru": "'elma' kelimesinden 'el' hecesi atılırsa ne kalır?", "secenekler": ["ma", "el", "elm", "ame"], "dogru": 0, "seslendir": "elma"},
    {"soru": "'masa' kelimesinden 'ma' hecesi atılırsa ne kalır?", "secenekler": ["sa", "ma", "mas", "sam"], "dogru": 0, "seslendir": "masa"},
])


# ─────────────────────────────────────────────────────────────
# Kelime Gezmece (çapraz bulmaca) — AI KULLANILMAZ.
# İçerik core/bulmaca_olusturucu.py ile yerel üretilir. Motor (egzersiz_motoru)
# bu tip için _icerik_uret içinde doğrudan bulmaca_uret çağırır; AI prompt'u
# devreye girmez. Yine de jenerik mock akışı (ve öğretmen önizlemesi) için
# buraya bir "mock" üretici bağlanır: user=None → motor mock'a düşse bile
# gerçek bir bulmaca döner.
# ─────────────────────────────────────────────────────────────
def _kelime_gezmece_user(sinif, konu, soru_sayisi, zorluk):
    return None  # AI istenmez


def _kelime_gezmece_mock(sinif, konu, soru_sayisi):
    # Geç içe aktarım: core katmanında döngüsel bağımlılığı önler.
    from core.bulmaca_olusturucu import bulmaca_uret
    return bulmaca_uret(sinif)


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
    # ── Tier 2 (FAZ 2) ──────────────────────────────────────────
    "bes_n_bir_k": {
        "system": _SISTEM_TR,
        "user": _metinli_user("metnin temel bilgilerini (kim, ne, nerede, ne zaman, neden, nasıl)"),
        "mock": _5n1k_mock,
    },
    "ana_fikir": {
        "system": _SISTEM_TR,
        "user": _metinli_user("ana fikri ve yardımcı düşünceleri"),
        "mock": _ana_fikir_mock,
    },
    "cikarim": {
        "system": _SISTEM_TR,
        "user": _metinli_user("doğrudan söylenmeyeni ipuçlarından çıkarmayı (çıkarım)"),
        "mock": _cikarim_mock,
    },
    "sebep_sonuc": {
        "system": _SISTEM_TR,
        "user": _metinli_user("olaylar arasındaki sebep-sonuç ilişkisini"),
        "mock": _sebep_sonuc_mock,
    },
    "tahmin_et": {
        "system": _SISTEM_TR,
        "user": _metinli_user("metnin nasıl devam edeceğine dair tahmini"),
        "mock": _tahmin_mock,
    },
    # ── Tier 3 (FAZ 3) ──────────────────────────────────────────
    "anagram": {
        "system": _SISTEM_TR,
        "user": _anagram_user,
        "mock": _anagram_mock,
    },
    "bulmaca": {
        "system": _SISTEM_TR,
        "user": _bulmaca_user,
        "mock": _bulmaca_mock,
    },
    "hafiza_karti": {
        "system": _SISTEM_TR,
        "user": _hafiza_user,
        "mock": _hafiza_mock,
    },
    "kelime_yagmuru": {
        "system": _SISTEM_TR,
        "user": _yagmur_user,
        "mock": _yagmur_mock,
    },
    "kelime_merdiveni": {
        "system": _SISTEM_TR,
        "user": _merdiven_user,
        "mock": _merdiven_mock,
    },
    "baglam_ipucu": {
        "system": _SISTEM_TR,
        "user": _baglam_user,
        "mock": _baglam_mock,
    },
    # ── Tier 4 (FAZ 4) ──────────────────────────────────────────
    "frayer": {
        "system": _SISTEM_TR,
        "user": _frayer_user,
        "mock": _frayer_mock,
    },
    "anlam_haritasi": {
        "system": _SISTEM_TR,
        "user": _anlam_haritasi_user,
        "mock": _anlam_haritasi_mock,
    },
    "venn": {
        "system": _SISTEM_TR,
        "user": _venn_user,
        "mock": _venn_mock,
    },
    "tekerleme": {
        "system": _SISTEM_TR,
        "user": _tekerleme_user,
        "mock": _tekerleme_mock_fn,
    },
    "sight_words": {
        "system": _SISTEM_TR,
        "user": _sight_user,
        "mock": _sight_mock,
    },
    "diyalog": {
        "system": _SISTEM_TR,
        "user": _diyalog_user,
        "mock": _diyalog_mock,
    },
    # ── FAZ 5: Fonolojik farkındalık ────────────────────────────
    "hece_sayma": {
        "system": _SISTEM_FONOLOJI,
        "user": _fonoloji_user(
            "kelimenin kaç heceli olduğunu sor.",
            '{"sorular": [{"soru": "\'kelebek\' kaç hecelidir?", "secenekler": ["2","3","4","5"], "dogru": 1, "seslendir": "kelebek"}]}'),
        "mock": _hece_sayma_mock,
    },
    "hece_birlestirme": {
        "system": _SISTEM_FONOLOJI,
        "user": _fonoloji_user(
            "verilen heceleri birleştirince hangi kelimenin oluştuğunu sor.",
            '{"sorular": [{"soru": "ki + tap hangi kelimedir?", "secenekler": ["kitap","kapı","tapu","kütük"], "dogru": 0, "seslendir": "ki, tap"}]}'),
        "mock": _hece_birlestirme_mock,
    },
    "ilk_ses": {
        "system": _SISTEM_FONOLOJI,
        "user": _fonoloji_user(
            "kelimenin hangi sesle başladığını sor.",
            '{"sorular": [{"soru": "\'elma\' hangi sesle başlar?", "secenekler": ["e","a","l","m"], "dogru": 0, "seslendir": "elma"}]}'),
        "mock": _ilk_ses_mock,
    },
    "son_ses": {
        "system": _SISTEM_FONOLOJI,
        "user": _fonoloji_user(
            "kelimenin hangi sesle bittiğini sor.",
            '{"sorular": [{"soru": "\'kalem\' hangi sesle biter?", "secenekler": ["m","k","e","l"], "dogru": 0, "seslendir": "kalem"}]}'),
        "mock": _son_ses_mock,
    },
    "kafiye": {
        "system": _SISTEM_FONOLOJI,
        "user": _fonoloji_user(
            "verilen kelimeyle kafiyeli (uyaklı) kelimeyi sor.",
            '{"sorular": [{"soru": "\'top\' ile kafiyeli olan?", "secenekler": ["hop","kedi","araba","masa"], "dogru": 0, "seslendir": "top"}]}'),
        "mock": _kafiye_mock,
    },
    "ses_birlestirme": {
        "system": _SISTEM_FONOLOJI,
        "user": _fonoloji_user(
            "tek tek söylenen sesleri birleştirince hangi kelimenin oluştuğunu sor.",
            '{"sorular": [{"soru": "k - e - d - i hangi kelimedir?", "secenekler": ["kedi","deri","kalem","dere"], "dogru": 0, "seslendir": "k, e, d, i"}]}'),
        "mock": _ses_birlestirme_mock,
    },
    "ses_cikarma": {
        "system": _SISTEM_FONOLOJI,
        "user": _fonoloji_user(
            "kelimeden bir hece/ses çıkarılınca ne kaldığını sor.",
            '{"sorular": [{"soru": "\'kitap\'tan \'ki\' atılırsa ne kalır?", "secenekler": ["tap","ki","kit","pat"], "dogru": 0, "seslendir": "kitap"}]}'),
        "mock": _ses_cikarma_mock,
    },
    # ── Kelime Gezmece — yerel bulmaca üretimi (AI yok) ──────────
    "kelime_gezmece": {
        "system": _SISTEM_TR,
        "user": _kelime_gezmece_user,
        "mock": _kelime_gezmece_mock,
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
