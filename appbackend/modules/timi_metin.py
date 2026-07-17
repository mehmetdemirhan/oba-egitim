"""TIMI Rapor Metin Bankası + deterministik anlatı üretimi.

Rapor, AI çağrısı OLMADAN öğrencinin gerçek kategori puanlarından derlenir: her zeka
alanı × seviye (baskın / orta / düşük) için hazır uzman metin blokları + genel değerlendirme
ve sonuç kalıpları. Tutarlı, ucuz ve pedagojik olarak kontrollü. Metin bankası
db.sistem_ayarlari'nda ("timi_rapor_metinleri") tutulur; DB boşsa buradaki VARSAYILAN'a
düşülür (admin/koordinatör Ayarlar'dan düzenleyebilir).

Seviye kuralı (referans forma kalibre): en_yuksek = max puan; düşük ⇔ puan ≤ en_yuksek/2;
baskın ⇔ puan == en_yuksek; orta ⇔ arası. (Örn. max=6 → baskın=6, orta=4-5, düşük≤3.)
"""
from datetime import datetime, timezone

# Kategori sırası + Türkçe etiketler timi.py ile aynı; döngüsel importtan kaçınmak için
# burada da sabit tutulur (timi.TIMI_KATEGORILER ile eşleşir).
_SIRA = ["dilsel", "mantiksal_matematiksel", "mekansal", "muziksel", "bedensel", "kisisel", "kisilerarasi"]
_TR = {
    "dilsel": "Dilsel Zekâ",
    "mantiksal_matematiksel": "Mantıksal-Matematiksel Zekâ",
    "mekansal": "Görsel-Mekânsal Zekâ",
    "muziksel": "Müziksel Zekâ",
    "bedensel": "Bedensel-Kinestetik Zekâ",
    "kisisel": "Kişisel (İçsel) Zekâ",
    "kisilerarasi": "Kişilerarası (Sosyal) Zekâ",
}

# ── VARSAYILAN METİN BANKASI ──
# Her alan için: profil (genel değerlendirmede baskınsa kullanılır), guclu[] (baskınsa),
# orta (orta düzeydeyse), dusuk (düşükse — nazik dil), oneri[] (eğitimsel öneriler).
TIMI_METIN_BANKASI = {
    "dilsel": {
        "profil": "kelimeler, okuma-yazma ve sözlü anlatım yoluyla düşünüp öğrenebilen",
        "guclu": [
            "Düşüncelerini sözlü ve yazılı olarak akıcı biçimde ifade edebilir.",
            "Okuma, hikâye anlatma ve kelime oyunlarından keyif alır, yeni kelimeleri kolay öğrenir.",
            "Anlatılanları dikkatle dinler ve dille ilgili görevlerde başarılıdır.",
        ],
        "orta": "Dil becerilerini işlevsel düzeyde kullanabilir; okuma ve yazılı anlatımı uygun etkinliklerle daha da gelişebilir.",
        "dusuk": "Düşüncelerini sözlü veya yazılı ifade etmede zaman zaman desteğe ihtiyaç duyabilir; okuma ve anlatım etkinlikleriyle desteklenmesi faydalı olacaktır.",
        "oneri": [
            "Kitap okuma, hikâye anlatma ve yaratıcı yazma çalışmalarıyla dilsel zekâ desteklenmelidir.",
            "Kelime dağarcığını genişleten oyunlar ve sözlü sunum fırsatları sunulmalıdır.",
        ],
    },
    "mantiksal_matematiksel": {
        "profil": "sayılar, örüntüler ve neden-sonuç ilişkileriyle mantıksal düşünebilen",
        "guclu": [
            "Problem çözme ve mantıksal akıl yürütme becerileri iyi düzeydedir.",
            "Örüntüleri, sayısal ilişkileri ve neden-sonuç bağlantılarını kolay fark eder.",
            "Sıralı, sistemli ve analitik düşünmeye yatkındır.",
        ],
        "orta": "Analitik düşünme becerilerini kullanabilir; sayısal ve mantıksal görevlerde uygun yönlendirmeyle gelişim gösterebilir.",
        "dusuk": "Soyut ve sayısal akıl yürütme gerektiren görevlerde zaman zaman desteğe ihtiyaç duyabilir; somut ve adım adım örneklerle desteklenmesi faydalı olacaktır.",
        "oneri": [
            "Bulmaca, strateji oyunları ve problem çözme etkinlikleriyle mantıksal beceriler pekiştirilebilir.",
            "Somut nesnelerle sayı, örüntü ve sınıflama çalışmaları yapılabilir.",
        ],
    },
    "mekansal": {
        "profil": "olayları zihninde canlandırabilen, görsel materyallerden etkili biçimde yararlanabilen",
        "guclu": [
            "Şekil, grafik, harita ve görseller üzerinden daha kolay öğrenir.",
            "Planlama, düzenleme ve ayrıntıları fark etme becerisi gelişmiştir.",
            "Zihninde canlandırma, tasarlama ve görsel ilişkileri kurma konusunda güçlüdür.",
        ],
        "orta": "Görsel materyallerden yararlanabilir; şema, harita ve çizim destekli çalışmalarla anlama düzeyi artabilir.",
        "dusuk": "Görsel-uzamsal ilişkileri kurmada zaman zaman desteğe ihtiyaç duyabilir; şema, model ve görsel örneklerle desteklenmesi faydalı olacaktır.",
        "oneri": [
            "Görsel materyaller, zihin haritaları, şemalar ve kavram haritaları kullanılmalıdır.",
            "Öğrendiklerini resim, çizim ve modeller oluşturarak ifade etmesi teşvik edilmelidir.",
        ],
    },
    "muziksel": {
        "profil": "ritim, melodi ve seslere duyarlı, işitsel örüntüleri kolay kavrayan",
        "guclu": [
            "Ritim, melodi ve seslere karşı duyarlıdır; işitsel örüntüleri kolay yakalar.",
            "Müzik, tekerleme ve ritim eşliğinde öğrenmekten keyif alır.",
            "Sesli tekrar ve ezgiyle bilgiyi kalıcı hâle getirebilir.",
        ],
        "orta": "Ritim ve ses temelli etkinliklerden yararlanabilir; müzikle desteklenen çalışmalarla öğrenmesi güçlenebilir.",
        "dusuk": "İşitsel ritim ve ses temelli görevlerde daha az istekli olabilir; müzikli etkinlikler kademeli olarak sunularak ilgisi geliştirilebilir.",
        "oneri": [
            "Ritim tutma, şarkı ve tekerlemelerle konu pekiştirme etkinlikleri yapılabilir.",
            "Öğrenilen bilgiler ezgi ve ritimle ilişkilendirilerek kalıcılık artırılabilir.",
        ],
    },
    "bedensel": {
        "profil": "hareket ederek, dokunarak ve yaparak öğrenmeye yatkın, el becerileri gelişmiş",
        "guclu": [
            "Hareket ederek, dokunarak ve uygulayarak öğrenmede başarılıdır.",
            "El becerileri, koordinasyon ve uygulamalı görevlerde yeteneklidir.",
            "Drama, spor ve yaparak-yaşayarak öğrenme etkinliklerinden keyif alır.",
        ],
        "orta": "Uygulamalı ve hareket içeren etkinliklerden yararlanabilir; yaparak öğrenme fırsatlarıyla gelişimi desteklenebilir.",
        "dusuk": "Hareket ve uygulama temelli öğrenmede daha az istekli olabilir; drama, oyun ve dokunsal etkinliklerle desteklenmesi faydalı olacaktır.",
        "oneri": [
            "Drama, spor, oyun ve hareket içeren etkinliklerle bedensel zekâ geliştirilmelidir.",
            "Öğrenilenler el işi, model yapımı ve uygulamalı görevlerle pekiştirilebilir.",
        ],
    },
    "kisisel": {
        "profil": "kendini tanıma, duygu ve düşüncelerini analiz etme konusunda güçlü, bağımsız çalışabilen",
        "guclu": [
            "Kendi güçlü ve gelişime açık yönlerinin farkındadır.",
            "Bağımsız çalışmalarda başarılı olabilir, sorumluluk alır.",
            "Duygu ve düşüncelerini analiz edebilir, hedef belirleyip üzerine düşünebilir.",
        ],
        "orta": "Öz farkındalığını kullanabilir; öz değerlendirme ve hedef belirleme çalışmalarıyla gelişimi desteklenebilir.",
        "dusuk": "Kendi öğrenme sürecini değerlendirmede zaman zaman desteğe ihtiyaç duyabilir; öz değerlendirme ve yansıtma etkinlikleriyle desteklenmesi faydalı olacaktır.",
        "oneri": [
            "Günlük tutma, öz değerlendirme çalışmaları ve hedef belirleme etkinlikleri yapılabilir.",
            "Bağımsız araştırma ve üzerine düşünme (yansıtma) fırsatları sunulmalıdır.",
        ],
    },
    "kisilerarasi": {
        "profil": "başkalarını anlama ve onlarla iş birliği yapma konusunda güçlü, sosyal etkileşime yatkın",
        "guclu": [
            "Grup çalışmalarına uyum sağlar ve iş birliğinde başarılıdır.",
            "Başkalarının duygularını anlar, iletişimi ve paylaşımı güçlüdür.",
            "Sosyal etkileşim gerektiren görevlerde etkin rol alır.",
        ],
        "orta": "Grup çalışmalarına uyum sağlayabilir; iş birlikçi etkinliklerle sosyal becerileri daha da gelişebilir.",
        "dusuk": "Grup içi etkileşim ve iş birliği gerektiren görevlerde zaman zaman desteğe ihtiyaç duyabilir; küçük grup ve eşli çalışmalarla desteklenmesi faydalı olacaktır.",
        "oneri": [
            "Grup çalışmaları ve problem çözme etkinlikleriyle sosyal beceriler pekiştirilebilir.",
            "Eşli görevler ve paylaşım temelli etkinliklerle iş birliği desteklenebilir.",
        ],
    },
}

# Genel değerlendirme / sonuç kalıpları ({...} yer tutucuları çalışma zamanında doldurulur)
TIMI_KALIPLAR = {
    "genel": ("Uygulanan TIMI Çoklu Zekâ Envanteri sonuçlarına göre bireyin en baskın zekâ "
              "alan{ek} {baskin} olarak belirlenmiştir. Birey, {profil} özellikler göstermektedir."),
    "genel_dengeli": ("Uygulanan TIMI Çoklu Zekâ Envanteri sonuçlarına göre bireyin zekâ alanları "
                      "birbirine yakın ve dengeli bir dağılım göstermektedir; belirgin biçimde öne "
                      "çıkan bir alan yerine çok yönlü bir profil söz konusudur."),
    "orta_giris": "{alanlar} alan{ek} orta düzeydedir.",
    "dusuk_giris": "{alanlar} alan{ek}nda gelişim desteklenebilir.",
    "sonuc": ("Birey, özellikle {baskin} alan{ek}nda güçlü bir potansiyele sahiptir. Eğitim sürecinde "
              "bu güçlü alanlara dayalı öğretim yöntemlerinin kullanılması öğrenme verimini artıracaktır."
              "{destek} Böylece bireyin çok yönlü gelişimine katkı sağlanacaktır."),
    "sonuc_destek": (" Bunun yanında {alanlar} alan{ek}na yönelik çalışmaların planlı biçimde "
                     "desteklenmesi de önemlidir."),
}

TIMI_RAPOR_METIN_TIP = "timi_rapor_metinleri"


# ─────────────────────────── yardımcılar ───────────────────────────
def _tr_liste(adlar: list) -> str:
    """['A','B','C'] → 'A, B ile C'."""
    adlar = [a for a in adlar if a]
    if not adlar:
        return ""
    if len(adlar) == 1:
        return adlar[0]
    return ", ".join(adlar[:-1]) + " ile " + adlar[-1]


def _ek(cogul: bool) -> str:
    return "ları" if cogul else "ı"


def seviyele(kategori_puanlari: dict) -> dict:
    """Puan dağılımını baskın/orta/düşük gruplarına ayırır (anahtar sırasını korur)."""
    puan = {k: int(kategori_puanlari.get(k, 0) or 0) for k in _SIRA}
    en_yuksek = max(puan.values()) if puan else 0
    if en_yuksek <= 0:
        return {"baskin": [], "orta": [], "dusuk": list(_SIRA), "puan": puan, "en_yuksek": 0}
    esik = en_yuksek / 2.0
    baskin, orta, dusuk = [], [], []
    for k in _SIRA:
        p = puan[k]
        if p == en_yuksek:
            baskin.append(k)
        elif p <= esik:
            dusuk.append(k)
        else:
            orta.append(k)
    return {"baskin": baskin, "orta": orta, "dusuk": dusuk, "puan": puan, "en_yuksek": en_yuksek}


def _bank(metinler: dict, key: str, alan: str):
    """metinler[key][alan] — kullanıcı bankası eksikse VARSAYILAN'a düşer."""
    m = (metinler or {}).get(key) or {}
    if alan in m and m[alan]:
        return m[alan]
    return (TIMI_METIN_BANKASI.get(key) or {}).get(alan)


def timi_rapor_uret(kategori_puanlari: dict, metinler: dict = None) -> dict:
    """Kategori puanlarından 6 bölümlü deterministik anlatı raporu üretir.

    Döner: {"bolumler": [{"baslik","tip","paragraf"?,"maddeler"?}, ...], "seviye": {...}}
    tip: "paragraf" | "liste". AI çağrısı YOK.
    """
    metinler = metinler or {}
    kaliplar = {**TIMI_KALIPLAR, **((metinler or {}).get("_kaliplar") or {})}
    s = seviyele(kategori_puanlari)
    baskin, orta, dusuk = s["baskin"], s["orta"], s["dusuk"]
    # Genel değerlendirmede en fazla 2 baskın alan gösterilir (kalanlar güçlü yönlerde yer alır)
    baskin_goster = baskin[:2]
    bolumler = []

    # a) GENEL DEĞERLENDİRME
    if not baskin or len(baskin) >= len(_SIRA):
        genel = kaliplar["genel_dengeli"]
    else:
        profil = _tr_liste([_bank(metinler, k, "profil") for k in baskin_goster])
        genel = kaliplar["genel"].format(
            ek=_ek(len(baskin_goster) > 1),
            baskin=_tr_liste([_TR[k] for k in baskin_goster]),
            profil=profil,
        )
    bolumler.append({"baslik": "Genel Değerlendirme", "tip": "paragraf", "paragraf": genel})

    # b) GÜÇLÜ YÖNLER (baskın alanların madde blokları; yoksa en yüksek alan)
    guclu_maddeler = []
    kaynak = baskin or ([max(s["puan"], key=s["puan"].get)] if s["en_yuksek"] > 0 else [])
    for k in kaynak:
        for m in (_bank(metinler, k, "guclu") or []):
            if m not in guclu_maddeler:
                guclu_maddeler.append(m)
    if guclu_maddeler:
        bolumler.append({"baslik": "Güçlü Yönler", "tip": "liste", "maddeler": guclu_maddeler})

    # c) ORTA DÜZEYDE GELİŞMİŞ ALANLAR
    if orta:
        giris = kaliplar["orta_giris"].format(alanlar=_tr_liste([_TR[k] for k in orta]), ek=_ek(len(orta) > 1))
        cumleler = " ".join(filter(None, [_bank(metinler, k, "orta") for k in orta]))
        bolumler.append({"baslik": "Orta Düzeyde Gelişmiş Alanlar", "tip": "paragraf",
                         "paragraf": (giris + " " + cumleler).strip()})

    # d) GELİŞTİRİLMESİ DESTEKLENEBİLECEK ALANLAR
    if dusuk:
        giris = kaliplar["dusuk_giris"].format(alanlar=_tr_liste([_TR[k] for k in dusuk]), ek=_ek(len(dusuk) > 1))
        cumleler = " ".join(filter(None, [_bank(metinler, k, "dusuk") for k in dusuk]))
        bolumler.append({"baslik": "Geliştirilmesi Desteklenebilecek Alanlar", "tip": "paragraf",
                         "paragraf": (giris + " " + cumleler).strip()})

    # e) EĞİTİMSEL ÖNERİLER (baskını değerlendir + düşüğü destekle)
    oneri_maddeler = []
    for k in (baskin + dusuk + orta):
        for m in (_bank(metinler, k, "oneri") or []):
            if m not in oneri_maddeler:
                oneri_maddeler.append(m)
    if oneri_maddeler:
        bolumler.append({"baslik": "Eğitimsel Öneriler", "tip": "liste", "maddeler": oneri_maddeler})

    # f) SONUÇ
    if baskin and len(baskin) < len(_SIRA):
        destek = ""
        if dusuk:
            destek = kaliplar["sonuc_destek"].format(alanlar=_tr_liste([_TR[k] for k in dusuk]), ek=_ek(len(dusuk) > 1))
        sonuc = kaliplar["sonuc"].format(
            baskin=_tr_liste([_TR[k] for k in baskin_goster]), ek=_ek(len(baskin_goster) > 1), destek=destek)
    else:
        sonuc = ("Bireyin dengeli zekâ profili, farklı öğretim yöntemlerinin bir arada kullanıldığı "
                 "çok yönlü bir öğrenme ortamından yararlanabileceğini göstermektedir.")
    bolumler.append({"baslik": "Sonuç", "tip": "paragraf", "paragraf": sonuc})

    return {"bolumler": bolumler, "seviye": {"baskin": baskin, "orta": orta, "dusuk": dusuk}}


# ─────────────────────────── metin bankası DB katmanı ───────────────────────────
async def get_rapor_metinleri(db):
    """(metinler, guncelleme_tarihi|None) — DB yoksa VARSAYILAN bankayı döndürür."""
    doc = await db.sistem_ayarlari.find_one({"tip": TIMI_RAPOR_METIN_TIP})
    if doc and doc.get("degerler"):
        return doc["degerler"], doc.get("guncelleme_tarihi")
    return _varsayilan_paket(), None


def _varsayilan_paket() -> dict:
    """VARSAYILAN metin bankası + kalıpları tek pakette (düzenleme UI'si için)."""
    paket = {k: dict(v) for k, v in TIMI_METIN_BANKASI.items()}
    paket["_kaliplar"] = dict(TIMI_KALIPLAR)
    return paket


async def set_rapor_metinleri(db, metinler: dict, guncelleyen: str = "") -> str:
    now = datetime.now(timezone.utc).isoformat()
    await db.sistem_ayarlari.update_one(
        {"tip": TIMI_RAPOR_METIN_TIP},
        {"$set": {"tip": TIMI_RAPOR_METIN_TIP, "degerler": metinler,
                  "guncelleme_tarihi": now, "guncelleyen": guncelleyen}},
        upsert=True)
    return now
