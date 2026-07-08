"""Açık uçlu soru (analiz_metinler.acik_sorular) yardımcıları.

Metin havuzundaki açık uçlu sorular tek tip NESNE listesi olarak saklanır:
    {
      "id":         str,        # metin içinde benzersiz soru id'si
      "no":         int|None,   # sıra numarası
      "kategori":     str|None, # normalize Bloom seviyesi (aşağıdaki 6 kanonik ad)
      "kategori_ham": str|None, # kaynak dosyadaki orijinal etiket (görüntü sadakati)
      "soru":       str,
      "model_cevap": str|None,  # hazır model cevap veya subjektif soruda örnek/yönlendirme
      "subjektif":  bool,       # True → otomatik doğru/yanlış YAPILMAZ (öğrenci cevabı)
    }

İki üretici:
  - acik_soru_nesnesi(...)   : yeni Bloom formatı (no/category/question/answer).
  - stringten_acik_soru(...) : eski 150 metin formatı (düz string open_question).
"""

# Kanonik Bloom seviyeleri (gruplama/filtre sırası)
BLOOM_SIRA = ["Hatırlama", "Anlama", "Uygulama", "Analiz", "Yaratma", "Değerlendirme"]

# Kaynak dosyalarda kategori adları tutarsız yazılıyor:
#   "Bilgi (Hatırlama)", "Bilgi/Hatırlama", "Hatırlama", "Sentez (Yaratma)",
#   "Sentez/Yaratma", "Yaratma" ... Hepsini 6 kanonik Bloom adına indir.
# (soldaki anahtar kelime metinde geçiyorsa → kanonik ad)
_KATEGORI_ANAHTAR = [
    ("değerlendirme", "Değerlendirme"),
    ("uygulama", "Uygulama"),
    ("analiz", "Analiz"),
    ("hatırlama", "Hatırlama"), ("bilgi", "Hatırlama"),
    ("kavrama", "Anlama"), ("anlama", "Anlama"),
    ("sentez", "Yaratma"), ("yaratma", "Yaratma"),
]


def normalize_kategori(ham):
    """Herhangi bir yazımı ('Bilgi/Hatırlama', 'Bilgi (Hatırlama)', 'Hatırlama'…)
    kanonik Bloom adına indirir. Anahtar kelime taramasıyla ayraç türünden
    bağımsızdır. Eşleşme yoksa orijinali (trim'li) döner."""
    if not ham:
        return None
    s = ham.strip().lower()
    for kw, kanonik in _KATEGORI_ANAHTAR:
        if kw in s:
            return kanonik
    return ham.strip()


def subjektif_isaret(a: str) -> bool:
    """Metin subjektif/açık uçlu olduğunu belirten bir işaret taşıyor mu?

    İki tür işaret:
      - "(Öğrenci cevabı ...)" ile başlama (önceki paketler).
      - "... farklı görüşler/öneriler/ürünler kabul edilir/edilebilir" gibi
        "kabul edil" notu (metne dayalı gerekçelendirmeyle farklı cevaplar geçerli).
    """
    if not a:
        return True
    alt = a.strip().lower()
    if alt.startswith("(öğrenci") or alt.startswith("(ogrenci"):
        return True
    if "kabul edil" in alt:   # kabul edilir / kabul edilebilir
        return True
    return False


def _cozumle_cevap(answer: str):
    """answer → (model_cevap, subjektif).

    - "(Öğrenci cevabı ...)": subjektif; içinde "örnek:" varsa örnek metni
      model_cevap olur, yoksa None.
    - "... kabul edilir/edilebilir" notu içeren: subjektif ama answer'ın kendisi
      örnek/yönlendirme model cevabı olarak korunur.
    - Aksi halde answer gerçek model cevaptır (subjektif=False).
    """
    a = (answer or "").strip()
    if not a:
        return None, True
    alt = a.lower()
    if alt.startswith("(öğrenci") or alt.startswith("(ogrenci"):
        if "örnek:" in alt:
            i = alt.index("örnek:") + len("örnek:")
            ornek = a[i:].strip().rstrip(")").strip()
            return (ornek or None), True
        return None, True
    if "kabul edil" in alt:
        # Model/örnek yönlendirme metni korunur, ama otomatik puanlanmaz
        return a, True
    return a, False


def acik_soru_nesnesi(sid: str, no, kategori_ham, soru, answer) -> dict:
    """Yeni Bloom formatındaki bir soruyu şema nesnesine çevirir."""
    model_cevap, subjektif = _cozumle_cevap(answer)
    return {
        "id": sid,
        "no": no,
        "kategori": normalize_kategori(kategori_ham),
        "kategori_ham": (kategori_ham or None),
        "soru": soru or "",
        "model_cevap": model_cevap,
        "subjektif": subjektif,
    }


def stringten_acik_soru(sid: str, no, soru_str: str) -> dict:
    """Eski 150 metin formatı: düz string open_question → şema nesnesi.

    Bu sorular yalnız yönlendirme metnidir (model cevap yok) → subjektif=True."""
    return {
        "id": sid,
        "no": no,
        "kategori": None,
        "kategori_ham": None,
        "soru": (soru_str or "").strip(),
        "model_cevap": None,
        "subjektif": True,
    }


def acik_soru_normalize_liste(acik_sorular, id_uret) -> list:
    """Bir dokümanın acik_sorular listesini NESNE listesine normalize eder.

    Zaten nesne olanları (dict) olduğu gibi bırakır; string olanları
    stringten_acik_soru ile çevirir. id_uret(i) → o indeks için soru id'si.
    Idempotent: tümü nesne ise değişmeden döner.
    """
    if not acik_sorular:
        return []
    cikti = []
    for i, s in enumerate(acik_sorular):
        if isinstance(s, dict):
            cikti.append(s)
        else:
            cikti.append(stringten_acik_soru(id_uret(i), i + 1, s))
    return cikti
