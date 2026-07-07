"""Giriş Analizi rapor ölçütleri — varsayılanlar + DB getter'ları.

Koordinatör/Yönetici "Rapor Ölçütleri Yönetim Paneli"nden düzenlenebilen ayarlar.
Hepsi `db.sistem_ayarlari` koleksiyonunda `{tip: <tip>, ...}` dokümanı olarak
tutulur (mevcut `tip=okuma_hizi_normlari` deseniyle tutarlı). Getter önce DB'yi
okur, doküman yoksa buradaki varsayılana düşer.

Depolama anahtarı tip'e göre değişir (geriye dönük uyum):
  - okuma_hizi_normlari → "normlar"   (eski /diagnostic/normlar ile aynı)
  - diğer tipler        → "degerler"
"""
from core.db import db

# ── a) Okuma hızı normları (sınıf → düşük/orta/yeterli eşikleri, wpm) ──
VARSAYILAN_NORMLAR = {
    "1": {"dusuk": 25, "orta": 40, "yeterli": 60},
    "2": {"dusuk": 55, "orta": 75, "yeterli": 95},
    "3": {"dusuk": 65, "orta": 90, "yeterli": 115},
    "4": {"dusuk": 80, "orta": 110, "yeterli": 140},
    "5": {"dusuk": 90, "orta": 120, "yeterli": 150},
    "6": {"dusuk": 100, "orta": 135, "yeterli": 170},
    "7": {"dusuk": 110, "orta": 150, "yeterli": 185},
    "8": {"dusuk": 120, "orta": 160, "yeterli": 200},
}

# ── b) Doğru okuma oranı eşikleri (%) ──
# dogruluk >= iyi → "İyi"; >= gelistirilmeli → "Geliştirilmeli"; aksi "Yetersiz".
DOGRULUK_ESIKLERI_DEFAULT = {"iyi": 98, "gelistirilmeli": 90}

# Kur önerisi eşikleri (kur_onerisi_hesapla için — koda gömülü 97/93 buraya taşındı).
KUR_ONERISI_ESIKLERI_DEFAULT = {"kur3_dogruluk": 97, "kur2_dogruluk": 93}

# ── c) Anlama rubrik maddeleri (4 alt boyut; madde id'leri eski AnlamaVeri
#       alan adlarıyla aynı → geriye dönük uyum) ──
ANLAMA_RUBRIK_DEFAULT = [
    {"id": "sozcuk_duzeyi", "baslik": "Sözcük Düzeyinde Anlama", "maddeler": [
        {"id": "cumle_anlama", "etiket": "Cümle anlamını kavrama"},
        {"id": "bilinmeyen_sozcuk", "etiket": "Bilinmeyen sözcük tahmini"},
        {"id": "baglac_zamir", "etiket": "Bağlaç ve zamirleri anlama"},
    ]},
    {"id": "ana_yapi", "baslik": "Metnin Ana Yapısını Anlama", "maddeler": [
        {"id": "ana_fikir", "etiket": "Ana fikir"},
        {"id": "yardimci_fikir", "etiket": "Yardımcı fikir"},
        {"id": "konu", "etiket": "Metnin konusu"},
        {"id": "baslik_onerme", "etiket": "Başlık önerme"},
    ]},
    {"id": "derin_anlama", "baslik": "Metinler Arasılık ve Derin Anlama", "maddeler": [
        {"id": "neden_sonuc", "etiket": "Neden-sonuç"},
        {"id": "cikarim", "etiket": "Çıkarım"},
        {"id": "ipuclari", "etiket": "İpucu kullanma"},
        {"id": "yorumlama", "etiket": "Yorumlama"},
    ]},
    {"id": "elestirel", "baslik": "Eleştirel ve Yaratıcı Okuma", "maddeler": [
        {"id": "gorus_bildirme", "etiket": "Görüş bildirme"},
        {"id": "yazar_amaci", "etiket": "Yazarın amacını sezme"},
        {"id": "alternatif_fikir", "etiket": "Alternatif son/fikir"},
        {"id": "guncelle_hayat", "etiket": "Günlük hayatla ilişkilendirme"},
    ]},
]

# 4.5 Bloom soru performansı — ilk iterasyonda sabit 6 kategori (dinamik dışı).
BLOOM_KATEGORILERI = [
    {"id": "bilgi", "etiket": "Bilgi"},
    {"id": "kavrama", "etiket": "Kavrama"},
    {"id": "uygulama", "etiket": "Uygulama"},
    {"id": "analiz", "etiket": "Analiz"},
    {"id": "sentez", "etiket": "Sentez"},
    {"id": "degerlendirme", "etiket": "Değerlendirme"},
]

# ── d) Prozodik okuma ölçütleri (id'ler eski ProzodikVeri alanlarıyla aynı) ──
PROZODIK_OLCUTLER_DEFAULT = [
    {"id": "noktalama", "etiket": "Noktalama ve duraklama", "capalar": {
        "1": "Noktalama işaretlerini dikkate almıyor", "2": "Bazen dikkate alıyor",
        "3": "Çoğunlukla uygun duraklıyor", "4": "Noktalamaya tam uygun"}},
    {"id": "vurgu", "etiket": "Vurgu", "capalar": {
        "1": "Tek düze", "2": "Yer yer vurgu", "3": "Anlama uygun", "4": "Etkili ve bilinçli"}},
    {"id": "tonlama", "etiket": "Tonlama", "capalar": {
        "1": "Tekdüze tonlama", "2": "Sınırlı tonlama", "3": "Anlama uygun tonlama", "4": "Etkili tonlama"}},
    {"id": "akicilik", "etiket": "Akıcılık", "capalar": {
        "1": "Kesik kesik", "2": "Sık duraksama", "3": "Genelde akıcı", "4": "Akıcı ve doğal"}},
    {"id": "anlamli_gruplama", "etiket": "Anlamlı Gruplama", "capalar": {
        "1": "Kelime kelime", "2": "Kısa gruplar", "3": "Anlamlı gruplar", "4": "Doğal anlam grupları"}},
]

# ── e) Gelişim raporu değişim eşikleri (metrik → anlamlı/gerileme sınırları) ──
# değişim >= anlamli → "Anlamlı Gelişim"; <= gerileme → "Gerileme"; aksi "Sabit/Sınırlı".
GELISIM_DEGISIM_ESIKLERI_DEFAULT = {
    "wpm": {"anlamli": 10, "gerileme": -5},
    "dogruluk": {"anlamli": 5, "gerileme": -2},
    "prozodik": {"anlamli": 3, "gerileme": -1},
    "anlama": {"anlamli": 10, "gerileme": -5},
}

# tip → varsayılan değer
RAPOR_AYAR_VARSAYILAN = {
    "okuma_hizi_normlari": VARSAYILAN_NORMLAR,
    "dogruluk_esikleri": DOGRULUK_ESIKLERI_DEFAULT,
    "kur_onerisi_esikleri": KUR_ONERISI_ESIKLERI_DEFAULT,
    "anlama_rubrik_maddeleri": ANLAMA_RUBRIK_DEFAULT,
    "prozodik_olcutler": PROZODIK_OLCUTLER_DEFAULT,
    "gelisim_degisim_esikleri": GELISIM_DEGISIM_ESIKLERI_DEFAULT,
}

# Panelden düzenlenebilen tipler (norm dahil). Bloom sabit → panel dışı.
DUZENLENEBILIR_TIPLER = tuple(RAPOR_AYAR_VARSAYILAN.keys())

# Depolama anahtarı (geriye dönük uyum)
_STORAGE_KEY = {"okuma_hizi_normlari": "normlar"}


def _storage_key(tip: str) -> str:
    return _STORAGE_KEY.get(tip, "degerler")


async def get_rapor_ayari(tip: str):
    """tip için ayarı DB'den okur, yoksa varsayılana düşer."""
    doc = await db.sistem_ayarlari.find_one({"tip": tip})
    key = _storage_key(tip)
    if doc and doc.get(key) is not None:
        return doc[key]
    return RAPOR_AYAR_VARSAYILAN.get(tip)


async def set_rapor_ayari(tip: str, degerler, guncelleyen: str = "") -> None:
    """tip için ayarı DB'ye yazar (upsert)."""
    from datetime import datetime, timezone
    key = _storage_key(tip)
    await db.sistem_ayarlari.update_one(
        {"tip": tip},
        {"$set": {"tip": tip, key: degerler,
                  "guncelleme_tarihi": datetime.now(timezone.utc).isoformat(),
                  "guncelleyen": guncelleyen}},
        upsert=True,
    )


# Anlama rubriğindeki TÜM madde id'lerini düz liste olarak döner (yüzde hesabı için).
def anlama_madde_idleri(rubrik) -> list:
    idler = []
    for boyut in rubrik or []:
        for m in boyut.get("maddeler", []):
            if m.get("id"):
                idler.append(m["id"])
    return idler
