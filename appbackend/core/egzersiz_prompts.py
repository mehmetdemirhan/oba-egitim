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


# Tip -> {system, user, mock}
PROMPTLAR = {
    "demo": {
        "system": "Sen Türkçe eğitim içeriği üreten bir asistansın.",
        "user": _demo_user,
        "mock": _demo_mock,
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
