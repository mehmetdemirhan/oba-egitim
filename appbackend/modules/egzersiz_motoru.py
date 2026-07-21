"""Egzersiz Motoru — jenerik egzersiz üretim, oturum ve puanlama motoru.

Tek bir motor, çok sayıda egzersiz tipini yönetir. Tip başına özel endpoint
YOKTUR; tip tanımları core/egzersiz_tipleri.py ve core/egzersiz_prompts.py
içinde config olarak durur.

Endpoint'ler (hepsi /api/egzersiz/ önekinde):
  GET  /egzersiz/tipler                  → tip listesi (opsiyonel ?sinif=)
  POST /egzersiz/uret                    → AI ile içerik üretir + cache'ler
  POST /egzersiz/oturum                  → yeni oturum başlatır
  POST /egzersiz/oturum/{id}/cevap       → tek soru doğruluğu
  POST /egzersiz/oturum/{id}/bitir       → puanlama + XP + kayıt
  GET  /egzersiz/gecmis/{ogrenci_id}     → oturum geçmişi
  GET  /egzersiz/icerikler               → cache'lenmiş içerikler (öğretmen)

NOT: Mevcut egzersiz/Leitner/Sokratik/Sesli modüllerine DOKUNULMAZ; bu motor
yalnızca yeni egzersiz tiplerini yönetir.
"""
import uuid
import random
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from core.db import db
from core.auth import get_current_user, require_role, UserRole
from core.ai import call_claude
from core.sistem import get_xp_tablosu
from core.egzersiz_tipleri import tip_var_mi, tip_meta, tip_listesi
from core.egzersiz_prompts import prompt_uret, mock_uret
from core.bulmaca_olusturucu import bulmaca_uret, kelime_dogrula
from core.kelime_durum import kelime_karsilasma

router = APIRouter()

# Bir içerik bu kadar kez kullanılınca (havuzdaki en az kullanılan bile) arka
# planda taze içerik üretilir — kullanıcı beklemeden çeşitlilik korunur.
YENILEME_ESIGI = 20
KUTUPHANE_KAP = 100   # (tip, sınıf) başına azami özgün içerik — dolunca AI üretimi DURUR

# Aynı (tip, sınıf) için aynı anda birden fazla arka plan üretimi tetiklenmesin.
_yenileme_aktif: set = set()

# Kelime-odaklı egzersiz tipleri: AI içeriğinde MEB müfredat kelimelerine öncelik ver.
_MEB_KELIME_TIPLERI = {
    "kelime_anlam_eslestirme", "es_karsit_anlamli", "anagram", "bulmaca",
    "kelime_yagmuru", "kelime_merdiveni", "baglam_ipucu", "frayer",
    "anlam_haritasi", "sight_words", "hafiza_karti",
}

# Deyim/atasözü/tekerleme egzersizleri: AI içeriğine db.deyim_atasozu havuzunu enjekte et.
# NOT: deyim_bosluk / atasozu_bosluk AI KULLANMAZ — aşağıdaki _POOL_DEYIM_BOSLUK ile
# havuzdaki öğenin KENDİ metninden bir kelime boşluğa çevrilir (uydurma cümle yok).
_DEYIM_TIPLERI = {"deyim_eslestirme", "tekerleme_okuma"}

# Deyim/Atasözü Boşluk Doldurma: AI'sız, db.deyim_atasozu havuzundan üretilir.
# Boşluk, deyimin/atasözünün KENDİ metnindeki bir kelimeye konur; çeldiriciler
# diğer havuz öğelerinin kelimelerinden gelir. Zorluk = hangi kelimenin boşaltıldığı.
_POOL_DEYIM_BOSLUK = {"deyim_bosluk", "atasozu_bosluk"}

# Kelime-anlam ÇİFTİ tabanlı tipler: AI'a GEREK YOK — onaylı MEB havuzundaki
# kelime+anlam çiftlerinden yerel ve HER SEFERİNDE TAZE üretilir (aynı içerik
# tekrarı sorununu kökten çözer; AI metin üretmekte zorlanınca da çalışır).
_POOL_CIFTLER_TIPLERI = {"kelime_anlam_eslestirme", "hafiza_karti"}


def _kisa_anlam(anlam: str, uzunluk: int = 60) -> str:
    """Uzun sözlük anlamını eşleştirme kartına sığacak kısa ifadeye indir."""
    a = (anlam or "").strip()
    # İlk cümle/madde ayır (";", " / ", "." öncesi)
    for ayirac in (";", " / ", ". "):
        if ayirac in a:
            a = a.split(ayirac)[0].strip()
            break
    return a[:uzunluk].strip() if len(a) > uzunluk else a


async def _meb_kelime_anlam_ciftleri(sinif: int, limit: int = 80) -> list[dict]:
    """Onaylı MEB havuzundan (anlamı dolu) kelime-anlam çiftleri: [{kelime, anlam}]."""
    try:
        from core.kelime_secici import meb_kelime_kayitlari
        docs = await meb_kelime_kayitlari(sinif, sadece_anlamli=True, limit=limit)
        ciftler = []
        for d in docs:
            k = str(d.get("kelime", "")).strip()
            a = str(d.get("anlam", "")).strip()
            if k and a:
                ciftler.append({"kelime": k, "anlam": a})
        return ciftler
    except Exception as ex:
        logging.warning(f"[egzersiz_motoru] kelime-anlam havuzu hatası: {ex}")
        return []


def _pool_ciftler_uret(havuz: list[dict], soru_sayisi: int, zorluk: str | None) -> dict | None:
    """Kelime-anlam eşleştirme / hafıza kartı içeriğini havuzdan üretir (AI'sız, taze).
    Zorluk arttıkça daha çok çift (ayırt etmesi güç). Rastgele seçim → her tur farklı."""
    if not havuz or len(havuz) < 3:
        return None
    z = {"kolay": 1, "orta": 2, "zor": 3}.get((zorluk or "orta").lower(), 2)
    adet = min(len(havuz), max(soru_sayisi, 2 + z + 1))  # kolay~4, orta~5, zor~6
    secilen = random.sample(havuz, adet)
    return {"ciftler": [{"sol": c["kelime"], "sag": _kisa_anlam(c["anlam"])} for c in secilen]}


# ── Cloze (boşluk doldurma) — ONAYLI OKUMA METİNLERİNDEN ─────────────────────
# AI metin üretemese bile: analiz_metinler havuzundaki gerçek okuma metinlerinden
# içerik kelimeleri boşluğa çevrilir, çeldiriciler onaylı kelime havuzundan gelir.
_POOL_CLOZE_TIPLERI = {"cloze_bosluk_doldurma"}

# Okuma-anlama / yorumlama tipleri: paragraf AI'a UYDURTULMAZ; onaylı okuma metni
# ({metin, sorular} şeması) kaynak olarak verilir, AI yalnız soru üretir.
_METINLI_ANLAMA_TIPLERI = {"bes_n_bir_k", "ana_fikir", "cikarim", "sebep_sonuc", "tahmin_et", "diyalog"}
_DURAK_KELIMELER = {
    "ve", "ile", "ama", "fakat", "çünkü", "gibi", "için", "bir", "bu", "şu", "onu", "ona",
    "da", "de", "ki", "mi", "ne", "çok", "daha", "en", "her", "hiç", "ya", "veya", "ancak",
    "yani", "ise", "göre", "kadar", "sonra", "önce", "ben", "sen", "biz", "siz", "onlar",
}

# AI'sız, onaylı havuzdan üretilen tüm tipler (kap dolana dek her oturumda taze).
_POOL_TIPLERI = _POOL_CIFTLER_TIPLERI | _POOL_CLOZE_TIPLERI | _POOL_DEYIM_BOSLUK

# Boşluk bırakıldığında cümleden kolay tahmin edilen bağlaç/edat/yardımcı sözcükler.
# Bunlardan biri boşaltılırsa soru KOLAY; uzun anahtar içerik sözcüğü boşaltılırsa ZOR.
_DEYIM_FONKSIYON = {
    "ve", "ile", "ama", "gibi", "için", "bir", "bu", "şu", "da", "de", "ki",
    "mi", "mı", "mu", "mü", "ne", "kadar", "daha", "çok", "her", "hiç", "ya",
    "veya", "göre", "ise", "değil", "olur", "olmaz", "var", "yok", "ile",
}


def _ic_kelime(w: str) -> str:
    return w.strip(".,;:!?\"'()[]…«»").lower()


def _cumlelere_bol(metin: str) -> list[str]:
    import re
    return [c.strip() for c in re.split(r"[.!?…]+", metin or "") if len(c.strip().split()) >= 4]


async def _analiz_metin_sec(sinif: int) -> dict | None:
    """Onaylı okuma metni havuzundan (durum=havuzda) rastgele yeterli uzunlukta bir metin."""
    try:
        sorgu = {"bolum": {"$in": ["analiz", "okuma_parcalari"]}, "durum": "havuzda",
                 "icerik": {"$nin": [None, ""]}}
        docs = await db.analiz_metinler.find(sorgu, {"icerik": 1, "baslik": 1}).to_list(length=300)
        docs = [d for d in docs if len((d.get("icerik") or "").split()) >= 30]
        return random.choice(docs) if docs else None
    except Exception as ex:
        logging.warning(f"[egzersiz_motoru] okuma metni seçme hatası: {ex}")
        return None


def _pool_cloze_uret(metin: str, soru_sayisi: int, zorluk: str | None, distraktor_havuz: list[str]) -> dict | None:
    """Okuma metninden boşluk-doldurma soruları üretir. Boşluğa uygun içerik
    kelimeleri (durak değil, yeterince uzun) seçilir; 4 seçenek = doğru + 3 çeldirici.
    Zorluk arttıkça daha uzun kelime boşluğu ve daha benzer çeldiriciler."""
    cumleler = _cumlelere_bol(metin)
    if len(cumleler) < 2 or len(distraktor_havuz) < 4:
        return None
    random.shuffle(cumleler)
    z = {"kolay": 1, "orta": 2, "zor": 3}.get((zorluk or "orta").lower(), 2)
    min_uzunluk = 3 + z  # kolay 4, orta 5, zor 6
    sorular, kullanilan = [], set()
    for c in cumleler:
        if len(sorular) >= soru_sayisi:
            break
        kelimeler = c.split()
        adaylar = [(i, w) for i, w in enumerate(kelimeler)
                   if _ic_kelime(w).isalpha() and len(_ic_kelime(w)) >= min_uzunluk
                   and _ic_kelime(w) not in _DURAK_KELIMELER and _ic_kelime(w) not in kullanilan]
        if not adaylar:
            continue
        idx, ham = random.choice(adaylar)
        dogru = _ic_kelime(ham)
        kaynak = [w for w in distraktor_havuz if w != dogru]
        benzer = [w for w in kaynak if abs(len(w) - len(dogru)) <= 1 or (z >= 3 and w[:1] == dogru[:1])]
        cel_havuz = benzer if len(benzer) >= 3 else kaynak
        if len(cel_havuz) < 3:
            continue
        cel = random.sample(cel_havuz, 3)
        secenekler = cel + [dogru]
        random.shuffle(secenekler)
        kelimeler[idx] = "___"
        sorular.append({"soru": " ".join(kelimeler), "secenekler": secenekler, "dogru": secenekler.index(dogru)})
        kullanilan.add(dogru)
    return {"sorular": sorular} if len(sorular) >= 2 else None


# ── Deyim / Atasözü Boşluk Doldurma (AI'sız, havuzdan) ───────────────────────
def _bosluk_soru_uret(icerik: str, anlam: str, zorluk: str | None,
                      distraktor_havuz: list[str]) -> dict | None:
    """Tek bir deyim/atasözünün KENDİ metninden bir kelime boşluğa çevrilir.

    Zorluk = hangi kelimenin boşaltıldığı: 'kolay' → en tahmin edilebilir (kısa/
    bağlaç) kelime; 'zor' → en anahtar (uzun, içerik) kelime; 'orta' → aradaki.
    Çeldiriciler DİĞER havuz öğelerinin kelimelerinden (benzer uzunlukta) gelir —
    hiçbir kelime UYDURULMAZ. Örn. 'Dereyi görmeden paçaları sıvama' → boşluk
    'paçaları'.
    """
    tokens = (icerik or "").split()
    if len(tokens) < 2:
        return None
    adaylar = [(i, _ic_kelime(w)) for i, w in enumerate(tokens)
               if _ic_kelime(w).isalpha() and len(_ic_kelime(w)) >= 3]
    if not adaylar:
        return None

    def anahtarlik(item):
        _, c = item
        s = len(c)
        if c in _DEYIM_FONKSIYON:
            s -= 5   # bağlaç/edat → daha az anahtar (tahmin edilebilir)
        return s

    adaylar.sort(key=anahtarlik)   # baş: tahmin edilebilir, son: anahtar
    z = {"kolay": 1, "orta": 2, "zor": 3}.get((zorluk or "orta").lower(), 2)
    if z <= 1:
        idx, dogru = adaylar[0]
    elif z >= 3:
        idx, dogru = adaylar[-1]
    else:
        idx, dogru = adaylar[len(adaylar) // 2]

    kaynak = [w for w in distraktor_havuz if w != dogru and abs(len(w) - len(dogru)) <= 2]
    if len(kaynak) < 3:
        kaynak = [w for w in distraktor_havuz if w != dogru]
    if len(kaynak) < 3:
        return None
    cel = random.sample(kaynak, 3)
    secenekler = cel + [dogru]
    random.shuffle(secenekler)

    kelimeler = list(tokens)
    kelimeler[idx] = "____"
    soru_metni = " ".join(kelimeler)
    if anlam:
        soru_metni += f"\n(İpucu: {anlam})"
    return {
        "soru": soru_metni,
        "secenekler": secenekler,
        "dogru": secenekler.index(dogru),
        "tam": icerik,          # geri bildirim için tam metin
        "_dogru_kelime": dogru,  # tekrarsızlık kontrolü (kullanımdan önce çıkarılır)
    }


def _pool_deyim_bosluk_uret(ogeler: list[dict], soru_sayisi: int,
                            zorluk: str | None) -> dict | None:
    """db.deyim_atasozu havuzundan boşluk-doldurma içeriği üretir (AI'sız, taze).
    Her soru bir öğenin kendi metninden; çeldiriciler tüm havuzun kelimelerinden."""
    if not ogeler or len(ogeler) < 4:
        return None
    havuz = set()
    for o in ogeler:
        for w in (o.get("icerik") or "").split():
            c = _ic_kelime(w)
            if c.isalpha() and len(c) >= 3:
                havuz.add(c)
    havuz = list(havuz)
    if len(havuz) < 4:
        return None

    secilen = random.sample(ogeler, min(len(ogeler), max(soru_sayisi * 3, soru_sayisi)))
    sorular, kullanilan = [], set()
    for o in secilen:
        if len(sorular) >= soru_sayisi:
            break
        s = _bosluk_soru_uret(o.get("icerik", ""), o.get("anlam", ""), zorluk, havuz)
        if not s:
            continue
        dk = s.pop("_dogru_kelime")
        if dk in kullanilan:
            continue
        kullanilan.add(dk)
        sorular.append(s)
    return {"sorular": sorular} if len(sorular) >= 2 else None


# ─────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────
def _temizle(doc: dict) -> dict:
    if doc:
        doc.pop("_id", None)
    return doc


async def _meb_kelimeler(sinif: int, sadece_anlamli: bool = False, limit: int = 500) -> list[str]:
    """MEB müfredat kelimelerini güvenli biçimde getirir (hata → boş liste)."""
    try:
        from core.kelime_secici import meb_kelime_stringleri
        return await meb_kelime_stringleri(sinif, sadece_anlamli=sadece_anlamli, limit=limit)
    except Exception as ex:
        logging.warning(f"[egzersiz_motoru] MEB kelime getirme hatası: {ex}")
        return []


async def _ogrenci_meb_kelimeler(ogrenci_id: str, sinif: int, limit: int = 40) -> list[str]:
    """Öğrencinin HENÜZ ÖĞRENMEDİĞİ (kutu<4) MEB kelimeleri — adaptif üretim için.
    Öğrenilmiş kelimeler rotasyondan çıkarılır. Hata → genel MEB listesine düşer."""
    try:
        from core.kelime_durum import ogrenci_kelime_sec
        kayitlar = await ogrenci_kelime_sec(ogrenci_id, sinif, limit)
        return [k["kelime"] for k in kayitlar if k.get("kelime")]
    except Exception as ex:
        logging.warning(f"[egzersiz_motoru] öğrenci MEB kelime hatası: {ex}")
        return await _meb_kelimeler(sinif, sadece_anlamli=True, limit=limit)


def _icerik_hedef_kelimeler(icerik: dict) -> list[str]:
    """Kelime-anlam içeriğinden test edilen hedef kelime listesini (sırayla) çıkarır.
    Leitner güncellemesi için kullanılır."""
    out: list[str] = []
    if not isinstance(icerik, dict):
        return out
    if icerik.get("ciftler"):
        for c in icerik["ciftler"]:
            out.append(str(c.get("sol") or c.get("kelime") or "") if isinstance(c, dict) else str(c))
    elif icerik.get("kelimeler"):
        for k in icerik["kelimeler"]:
            out.append(str(k.get("kelime") or k.get("cevap") or "") if isinstance(k, dict) else str(k))
    elif icerik.get("kelime"):
        out.append(str(icerik["kelime"]))
    elif icerik.get("merkez"):
        out.append(str(icerik["merkez"]))
    elif icerik.get("hedef"):
        out.append(str(icerik["hedef"]))
    return [w for w in out if w and len(w.strip()) >= 2]


def _toplam_soru(meta: dict, icerik: dict) -> int:
    p = meta.get("puanlama", "secmeli")
    if p == "secmeli":
        return len(icerik.get("sorular", []))
    if p == "eslesme":
        return len(icerik.get("ciftler", []))
    # sira / serbest → tek puanlama
    return 1


# Zorluk etiketi → skor çarpanı için sayısal seviye (göz egzersizi ölçeğiyle uyumlu).
_ZORLUK_SEVIYE = {"kolay": 2, "orta": 3, "zor": 4}


def _egz_skor(dogru: int, yanlis: int, sure_sn: int, zorluk_num: int) -> int:
    """Egzersiz skoru — DOĞRULUK + SÜRE + ZORLUK (egzersiz.py._goz_skor ile AYNI formül).

      accuracy = dogru / (dogru + yanlis)
      hiz      = dogru / sure_sn
      skor = round( dogru*10 * (0.5+0.5*accuracy) * (1+min(1,hiz)) * (0.8+0.1*zorluk) )

    Hızlı ve doğru → yüksek skor; zor egzersiz daha çok puan. 'En Yüksek Skor'
    (kişisel rekor) bu değerin tip bazlı maksimumudur.
    """
    dogru = max(0, int(dogru or 0))
    yanlis = max(0, int(yanlis or 0))
    toplam = dogru + yanlis
    accuracy = (dogru / toplam) if toplam else 1.0
    sure_sn = max(1, int(sure_sn or 1))
    hiz = dogru / sure_sn
    z = min(5, max(1, int(zorluk_num or 1)))
    return round(dogru * 10 * (0.5 + 0.5 * accuracy) * (1 + min(1.0, hiz)) * (0.8 + 0.1 * z))


async def _icerik_uret(tip: str, sinif: int, konu: str | None, zorluk: str | None,
                       ogrenci_id: str | None = None) -> tuple[dict, bool]:
    """AI ile içerik üretir. Başarısızsa 1 kez retry, yine olmazsa mock döner.

    Dönüş: (icerik_dict, mock_mu)
    """
    meta = tip_meta(tip)
    soru_sayisi = meta.get("soru_sayisi", 5)

    # Kelime Gezmece (ve "bulmaca" üreticili tipler): içerik AI ile değil,
    # core/bulmaca_olusturucu.py ile yerel üretilir. Mock değildir.
    # MEB müfredat kelimeleri varsa bulmaca onların önceliğiyle kurulur.
    if meta.get("icerik_uretici") == "bulmaca":
        meb = await _meb_kelimeler(sinif)
        return bulmaca_uret(sinif, meb_kelimeler=meb or None), False

    # Kelime-anlam çifti tabanlı tipler: ONAYLI HAVUZDAN taze üret (AI'sız). AI metin
    # üretmekte zorlansa bile çalışır; her tur farklı kelime/anlam → tekrar sorunu yok.
    if tip in _POOL_CIFTLER_TIPLERI:
        havuz = await _meb_kelime_anlam_ciftleri(sinif, limit=80)
        pool_icerik = _pool_ciftler_uret(havuz, soru_sayisi, zorluk)
        if pool_icerik:
            return pool_icerik, False   # mock değil — onaylı havuzdan gerçek içerik
        # Havuz yetersizse (o sınıfta anlamlı kelime yok) AI/mock akışına düş.

    # Cloze (boşluk doldurma): onaylı okuma metninden + havuz çeldiricileriyle (AI'sız)
    if tip in _POOL_CLOZE_TIPLERI:
        metin_doc = await _analiz_metin_sec(sinif)
        if metin_doc:
            metin = metin_doc.get("icerik", "")
            meb = await _meb_kelimeler(sinif, limit=200) or []
            ic_kelimeler = list({_ic_kelime(w) for w in metin.split()
                                 if _ic_kelime(w).isalpha() and len(_ic_kelime(w)) >= 4})
            havuz = list({w.lower() for w in meb} | set(ic_kelimeler))
            cloze = _pool_cloze_uret(metin, soru_sayisi, zorluk, havuz)
            if cloze:
                return cloze, False
        # Uygun metin/kelime yoksa AI/mock akışına düş.

    # Deyim / Atasözü Boşluk Doldurma: havuz öğesinin KENDİ metninden boşluk (AI'sız).
    if tip in _POOL_DEYIM_BOSLUK:
        try:
            from modules.deyim_atasozu import deyim_ogeler
            turler = ["atasozu"] if tip == "atasozu_bosluk" else ["deyim"]
            ogeler = await deyim_ogeler(sinif, turler, limit=80)
        except Exception as ex:
            logging.warning(f"[egzersiz_motoru] deyim/atasözü havuzu hatası: {ex}")
            ogeler = []
        icerik = _pool_deyim_bosluk_uret(ogeler, soru_sayisi, zorluk)
        if icerik:
            return icerik, False
        # Havuz henüz seed edilmemişse güvenli mock'a düş.
        return mock_uret("deyim_bosluk", sinif, konu, soru_sayisi), True

    system, user_msg = prompt_uret(tip, sinif, konu, soru_sayisi, zorluk)
    if not user_msg:
        return mock_uret(tip, sinif, konu, soru_sayisi), True

    # MEB/kitap önceliği: kelime-odaklı tiplerde AI'a bu kelimelerden üretmesini söyle.
    # (Liste, köprü sayesinde müfredat + AI Eğit ile yüklenen kitap kelimelerini içerir.)
    if tip in _MEB_KELIME_TIPLERI:
        # Öğrenci belliyse ÖĞRENMEDİĞİ (kutu<4) kelimelere öncelik ver (adaptif);
        # yoksa (arka plan/öğretmen üretimi) genel MEB listesi.
        if ogrenci_id:
            meb = await _ogrenci_meb_kelimeler(ogrenci_id, sinif, limit=60)
        else:
            meb = await _meb_kelimeler(sinif, sadece_anlamli=True, limit=60)
        if meb:
            user_msg += ("\n\nZORUNLU KAYNAK: Bu egzersizi ÖNCELİKLE aşağıdaki kelimelerden üret "
                         "(öğrencinin okulda/kitaplarında öğrendiği kelimeler). Mümkün olduğunca "
                         f"YALNIZCA bu listeden seç:\n{', '.join(meb[:40])}.")

    if tip in _DEYIM_TIPLERI:
        # db.deyim_atasozu havuzundan öğeleri prompt'a enjekte et (varsa AI onları kullanır).
        try:
            from modules.deyim_atasozu import deyim_ogeler
            turler = ["tekerleme"] if tip == "tekerleme_okuma" else ["deyim", "atasozu"]
            ogeler = await deyim_ogeler(sinif, turler, limit=20)
        except Exception as ex:
            logging.warning(f"[egzersiz_motoru] deyim havuzu hatası: {ex}")
            ogeler = []
        if ogeler:
            if tip == "tekerleme_okuma":
                secilen = random.choice(ogeler)
                user_msg += ("\n\nZORUNLU: Aşağıdaki tekerlemeyi AYNEN kullan (metin alanına koy, "
                             f"değiştirme):\n{secilen['icerik']}")
            else:
                liste = "; ".join(f"{o['icerik']} = {o.get('anlam','')}" for o in ogeler[:12] if o.get('anlam'))
                if liste:
                    user_msg += ("\n\nZORUNLU KAYNAK: Bu egzersizi ÖNCELİKLE aşağıdaki "
                                 "öğretmenin girdiği deyim/atasözü havuzundan üret:\n" + liste)

    # Okuma-ANLAMA/YORUMLAMA tipleri: onaylı okuma metnini KAYNAK olarak enjekte et.
    # AI metin UYDURMAZ; yalnız verilen gerçek metne dayalı soru üretir (havuz temelli).
    _grounded_metin = None
    if tip in _METINLI_ANLAMA_TIPLERI:
        _md = await _analiz_metin_sec(sinif)
        if _md and _md.get("icerik"):
            _grounded_metin = str(_md["icerik"]).strip()
            user_msg += ("\n\nZORUNLU KAYNAK METİN: Aşağıdaki metni AYNEN kullan; YENİ metin/olay "
                         "UYDURMA. Tüm soruları SADECE bu metne dayandır ve 'metin' alanına bu metni koy:\n"
                         f'"""\n{_grounded_metin}\n"""')

    for deneme in range(2):
        try:
            res = await call_claude(system, user_msg, max_tokens=3000)
            parsed = res.get("parsed")
            if isinstance(parsed, dict) and parsed:
                if _grounded_metin:
                    parsed["metin"] = _grounded_metin   # gösterilen paragraf onaylı havuzdan
                return parsed, False
        except Exception as ex:
            logging.warning(f"[egzersiz_motoru] AI üretim hatası ({tip}, deneme {deneme}): {ex}")
    # Fallback — mock içerik. Anlama tipinde metni yine de onaylı havuzdan göster.
    logging.info(f"[egzersiz_motoru] '{tip}' için mock içerik kullanılıyor")
    _mock = mock_uret(tip, sinif, konu, soru_sayisi)
    if _grounded_metin and isinstance(_mock, dict) and "metin" in _mock:
        _mock["metin"] = _grounded_metin
    return _mock, True


async def _icerik_kaydet(tip: str, sinif: int, konu: str | None, zorluk: str | None,
                         icerik: dict, ekleyen_id: str, mock: bool,
                         kaynak: str = "ai_uretim", olusturan: dict | None = None,
                         varyant_grubu: str | None = None) -> dict:
    """İçeriği kalıcı kütüphaneye kaydeder.

    Kütüphane şeması (eski kayıtlar bu alanlar olmadan da çalışır; sorgular
    eksik `durum`'u "aktif" kabul eder):
      - durum: "aktif" | "arsivli"
      - varyant_grubu: orijinal içeriğin id'si (orijinal ise kendi id'si)
      - kaynak: "ai_uretim" | "manuel" | "prewarm"
      - olusturan_id / olusturan_ad / olusturan_rol
      - son_kullanim_tarihi
    """
    yeni_id = str(uuid.uuid4())
    olusturan = olusturan or {}
    doc = {
        "id": yeni_id,
        "tip": tip,
        "sinif": sinif,
        "konu": konu or "",
        "zorluk": zorluk or "orta",
        "icerik": icerik,
        "mock": bool(mock),
        "durum": "aktif",
        # Orijinal içerik kendi id'sini grup yapar; varyantlar orijinalin grubunu paylaşır.
        "varyant_grubu": varyant_grubu or yeni_id,
        "kaynak": kaynak,
        "olusturan_id": olusturan.get("id") or ekleyen_id,
        "olusturan_ad": olusturan.get("ad", ""),
        "olusturan_rol": olusturan.get("rol", ""),
        "olusturma_tarihi": datetime.utcnow().isoformat(),
        "ekleyen_id": ekleyen_id,
        "kullanim_sayisi": 0,
        "son_kullanim_tarihi": None,
    }
    await db.egzersiz_icerikler.insert_one(dict(doc))
    return doc


async def _arka_plan_uret(tip: str, sinif: int, ekleyen_id: str):
    """Sıcak (çok kullanılan) bir tip için arka planda yeni içerik üretip cache'ler.

    Yalnızca GERÇEK (mock olmayan) içerik eklenir; kullanıcı akışını bloklamaz.
    Aynı (tip, sınıf) için eşzamanlı tekrar tetiklenmeyi `_yenileme_aktif` engeller.
    """
    anahtar = (tip, sinif)
    if anahtar in _yenileme_aktif:
        return
    _yenileme_aktif.add(anahtar)
    try:
        icerik, mock = await _icerik_uret(tip, sinif, None, None)
        if not mock:
            await _icerik_kaydet(tip, sinif, None, None, icerik, ekleyen_id, mock)
            logging.info(f"[egzersiz_motoru] arka plan içerik üretildi: {tip} s{sinif}")
    except Exception as ex:
        logging.warning(f"[egzersiz_motoru] arka plan üretim hatası ({tip} s{sinif}): {ex}")
    finally:
        _yenileme_aktif.discard(anahtar)


# Eski kayıtlarda `durum` alanı yoksa "aktif" kabul edilir (migration gerekmez).
_AKTIF = {"$or": [{"durum": "aktif"}, {"durum": {"$exists": False}}]}


def _aktif_sorgu(tip: str, sinif: int) -> dict:
    return {"tip": tip, "sinif": sinif, **_AKTIF}


async def _ogrenci_gorulen_icerik(ogrenci_id: str | None, tip: str) -> dict:
    """Öğrencinin bu tipte gördüğü {icerik_id: en_son_görülme_tarihi} eşlemesi
    (öğrenci bazlı tekrarsızlık için). Öğrenci yoksa boş döner."""
    if not ogrenci_id:
        return {}
    kayitlar = await db.egzersiz_oturumlari.find(
        {"ogrenci_id": ogrenci_id, "tip": tip, "icerik_id": {"$ne": None}},
        {"icerik_id": 1, "baslama_t": 1},
    ).to_list(length=5000)
    gorulen = {}
    for k in kayitlar:
        iid = k.get("icerik_id"); t = k.get("baslama_t") or ""
        if iid and (iid not in gorulen or t > gorulen[iid]):
            gorulen[iid] = t
    return gorulen


async def _zorluk_belirle(ogrenci_id: str | None, tip: str,
                          manuel: str | None = None) -> str:
    """Adaptif zorluk: manuel verildiyse (öğretmen/öğrenci seçimi) o kullanılır;
    yoksa öğrencinin son oturumlarının başarısına göre KADEMELİ belirlenir.

    - <2 oturum → 'kolay' (yeni başlayan).
    - son ~5 oturumun ortalama doğruluk oranı: >=0.8 → 'zor', >=0.5 → 'orta',
      aksi → 'kolay'. Başarı arttıkça zorluk otomatik yükselir.
    """
    if manuel in ("kolay", "orta", "zor"):
        return manuel
    if not ogrenci_id:
        return "orta"
    try:
        kayitlar = await db.egzersiz_oturumlari.find(
            {"ogrenci_id": ogrenci_id, "tip": tip, "durum": "tamamlandi"},
            {"dogru_sayisi": 1, "toplam_soru": 1},
        ).sort("bitis_t", -1).limit(5).to_list(5)
        if len(kayitlar) < 2:
            return "kolay"
        oranlar = [k.get("dogru_sayisi", 0) / max(1, k.get("toplam_soru", 1)) for k in kayitlar]
        ort = sum(oranlar) / len(oranlar)
        if ort >= 0.8:
            return "zor"
        if ort >= 0.5:
            return "orta"
        return "kolay"
    except Exception as ex:
        logging.warning(f"[egzersiz_motoru] adaptif zorluk hatası: {ex}")
        return "orta"


async def _icerik_sec_veya_uret(tip: str, sinif: int, ekleyen_id: str,
                                ogrenci_id: str | None = None,
                                manuel_zorluk: str | None = None) -> dict:
    """Oturum için kalıcı kütüphaneden içerik seçer — KÜTÜPHANE KAPI + TEKRARSIZLIK.

    1. Öğrencinin bu tipte GÖRMEDİĞİ, en az kullanılan aktif içeriklerden RASTGELE
       seçilir (çeşitlilik). Aynı öğrenciye aynı içerik ikinci kez gösterilmez.
    2. Öğrenci tüm havuzu gördüyse ya da havuz boşsa: kütüphane KUTUPHANE_KAP'ın
       altındaysa AI ile taze içerik üretilir (hem havuz büyür hem öğrenci yeni görür).
    3. Kütüphane DOLUYSA (KUTUPHANE_KAP) yeni AI üretimi YAPILMAZ (maliyet sınırı);
       öğrencinin en ESKİ gördüğü içerik yeniden gösterilir — tüm havuz döndükten
       sonra makul bir aralıkla tekrar (spaced) demektir.
    """
    # Pool tabanlı tipler (kelime-anlam eşleştirme / hafıza kartı / cloze): AI'sız +
    # ucuz → kap dolana kadar HER oturumda TAZE üret (bayat mock'lar yerine hep
    # farklı içerik). Kap dolunca aşağıdaki tekrarsız/en-eski akışına düşer.
    if tip in _POOL_TIPLERI:
        # Deyim/Atasözü boşluk tiplerinde adaptif/manuel zorluk uygulanır;
        # diğer havuz tiplerinde zorluk üreticinin kendi mantığına bırakılır.
        z = None
        if tip in _POOL_DEYIM_BOSLUK:
            z = await _zorluk_belirle(ogrenci_id, tip, manuel_zorluk)
        mevcut = await db.egzersiz_icerikler.count_documents(_aktif_sorgu(tip, sinif))
        if mevcut < KUTUPHANE_KAP:
            icerik, mock = await _icerik_uret(tip, sinif, None, z, ogrenci_id)
            if not mock and (icerik.get("ciftler") or icerik.get("sorular")):
                return await _icerik_kaydet(tip, sinif, None, z, icerik, ekleyen_id, mock, kaynak="havuz_uretim")

    adaylar = await db.egzersiz_icerikler.find(_aktif_sorgu(tip, sinif)).sort(
        [("kullanim_sayisi", 1), ("son_kullanim_tarihi", 1)]
    ).to_list(length=KUTUPHANE_KAP + 30)
    aktif_sayi = len(adaylar)
    gorulen = await _ogrenci_gorulen_icerik(ogrenci_id, tip)

    # 1) Öğrencinin görmediği (en az kullanılan bantından rastgele)
    gorulmeyen = [a for a in adaylar if a["id"] not in gorulen]
    if gorulmeyen:
        en_az = gorulmeyen[0].get("kullanim_sayisi", 0)
        havuz = [a for a in gorulmeyen if a.get("kullanim_sayisi", 0) <= en_az + 2]
        secilen = random.choice(havuz)
        # Havuz "sıcak" ve kap dolmadıysa arka planda büyütmeyi sıraya koy
        if aktif_sayi and adaylar[0].get("kullanim_sayisi", 0) >= YENILEME_ESIGI and aktif_sayi < KUTUPHANE_KAP:
            asyncio.create_task(_arka_plan_uret(tip, sinif, ekleyen_id))
        return secilen

    # 2) Öğrenci hepsini görmüş / havuz boş → kap dolmadıysa taze üret
    if aktif_sayi < KUTUPHANE_KAP:
        icerik, mock = await _icerik_uret(tip, sinif, None, None, ogrenci_id)
        return await _icerik_kaydet(tip, sinif, None, None, icerik, ekleyen_id, mock,
                                    kaynak="ai_uretim")

    # 3) Kap dolu + öğrenci hepsini görmüş → en ESKİ görüleni tekrar göster (üretim yok)
    adaylar.sort(key=lambda a: gorulen.get(a["id"], ""))
    return adaylar[0]


# ─────────────────────────────────────────────
# Kütüphane yardımcıları
# ─────────────────────────────────────────────
def _kullanici_ad(user: dict) -> str:
    ad = f"{user.get('ad', '')} {user.get('soyad', '')}".strip()
    return ad or user.get("ad") or "Kullanıcı"


def _icerik_ozet(icerik: dict, uzunluk: int = 100) -> str:
    """İçeriğin insan-okur kısa özetini (ilk ~100 karakter) üretir."""
    if not isinstance(icerik, dict):
        return ""
    parca = ""
    if icerik.get("metin"):
        parca = str(icerik["metin"])
    elif icerik.get("sorular"):
        ilk = icerik["sorular"][0] if icerik["sorular"] else {}
        parca = str(ilk.get("soru", ""))
    elif icerik.get("ciftler"):
        parca = ", ".join(f"{c.get('sol', '')}={c.get('sag', '')}" for c in icerik["ciftler"][:4])
    elif icerik.get("kelimeler"):
        parca = ", ".join(str(k.get("cevap", k)) for k in icerik["kelimeler"][:6])
    elif icerik.get("kelime"):
        parca = str(icerik["kelime"])
    elif icerik.get("parcalar"):
        parca = " ".join(map(str, icerik["parcalar"]))
    elif icerik.get("olaylar"):
        parca = " / ".join(map(str, icerik["olaylar"][:3]))
    elif icerik.get("hedef"):
        parca = str(icerik["hedef"])
    parca = " ".join(parca.split())
    return parca[:uzunluk] + ("…" if len(parca) > uzunluk else "")


def _ozet_kayit(d: dict) -> dict:
    """Kütüphane listesi için tek içeriğin özet kaydı."""
    meta = tip_meta(d.get("tip", "")) or {}
    return {
        "id": d.get("id"),
        "tip": d.get("tip"),
        "tip_ad": meta.get("ad", d.get("tip")),
        "ikon": meta.get("ikon", "📝"),
        "sinif": d.get("sinif"),
        "ozet": _icerik_ozet(d.get("icerik", {})),
        "olusturan_ad": d.get("olusturan_ad") or "—",
        "olusturan_rol": d.get("olusturan_rol") or "",
        "kaynak": d.get("kaynak", "ai_uretim"),
        "durum": d.get("durum", "aktif"),
        "kullanim_sayisi": d.get("kullanim_sayisi", 0),
        "varyant_grubu": d.get("varyant_grubu") or d.get("id"),
        "son_kullanim_tarihi": d.get("son_kullanim_tarihi"),
        "olusturma_tarihi": d.get("olusturma_tarihi"),
        "mock": d.get("mock", False),
    }


def _kontrol(meta: dict, icerik: dict, soru_no: int, cevap) -> tuple[bool, object]:
    """Jenerik cevap kontrolü — puanlama stratejisine göre.

    Dönüş: (dogru_mu, dogru_cevap)
    """
    p = meta.get("puanlama", "secmeli")
    try:
        if p == "secmeli":
            sorular = icerik.get("sorular", [])
            if 0 <= soru_no < len(sorular):
                dogru = sorular[soru_no].get("dogru")
                return (cevap == dogru), dogru
            return False, None
        if p == "sira":
            dogru_sira = icerik.get("dogru_sira", [])
            return (list(cevap) == list(dogru_sira)), dogru_sira
        if p == "eslesme":
            ciftler = icerik.get("ciftler", [])
            # cevap: {"sol": index, "sag": eşleştirilen değer}
            if isinstance(cevap, dict):
                idx = cevap.get("sol")
                if isinstance(idx, int) and 0 <= idx < len(ciftler):
                    beklenen = list(ciftler[idx].values())
                    return (cevap.get("sag") in beklenen), ciftler[idx]
            return False, None
        # serbest → dış puanlama (ör. telaffuz); cevap doğru kabul edilir
        return bool(cevap), cevap
    except Exception as ex:
        logging.warning(f"[egzersiz_motoru] kontrol hatası: {ex}")
        return False, None


def _ogrenci_id(current_user: dict) -> str:
    return current_user.get("linked_id") or current_user.get("id")


# ─────────────────────────────────────────────
# Endpoint'ler
# ─────────────────────────────────────────────
@router.get("/egzersiz/tipler")
async def egzersiz_tipler(sinif: int | None = Query(None)):
    """Kayıtlı tüm egzersiz tiplerini (opsiyonel sınıf filtresiyle) döndürür."""
    return {"tipler": tip_listesi(sinif)}


@router.post("/egzersiz/uret")
async def egzersiz_uret(data: dict, current_user=Depends(get_current_user)):
    """AI ile yeni içerik üretir ve cache'ler."""
    tip = data.get("tip", "")
    sinif = int(data.get("sinif", 3))
    konu = data.get("konu")
    zorluk = data.get("zorluk")
    if not tip_var_mi(tip):
        raise HTTPException(status_code=400, detail=f"Bilinmeyen egzersiz tipi: {tip}")
    icerik, mock = await _icerik_uret(tip, sinif, konu, zorluk)
    doc = await _icerik_kaydet(tip, sinif, konu, zorluk, icerik, current_user.get("id"), mock)
    return _temizle(doc)


@router.post("/egzersiz/oturum")
async def egzersiz_oturum_baslat(data: dict, current_user=Depends(get_current_user)):
    """Yeni oturum başlatır. icerik_id verilmezse cache/AI'dan içerik seçilir."""
    tip = data.get("tip", "")
    sinif = int(data.get("sinif", 3))
    icerik_id = data.get("icerik_id")
    if not tip_var_mi(tip):
        raise HTTPException(status_code=400, detail=f"Bilinmeyen egzersiz tipi: {tip}")
    meta = tip_meta(tip)

    if icerik_id:
        icerik_doc = await db.egzersiz_icerikler.find_one({"id": icerik_id})
        if not icerik_doc:
            raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    else:
        # Öğretmen/öğrenci manuel zorluk seçebilir (kolay/orta/zor); yoksa adaptif.
        manuel_zorluk = data.get("zorluk")
        icerik_doc = await _icerik_sec_veya_uret(tip, sinif, current_user.get("id"),
                                                 ogrenci_id=_ogrenci_id(current_user),
                                                 manuel_zorluk=manuel_zorluk)

    await db.egzersiz_icerikler.update_one(
        {"id": icerik_doc["id"]},
        {"$inc": {"kullanim_sayisi": 1},
         "$set": {"son_kullanim_tarihi": datetime.utcnow().isoformat()}},
    )

    oturum = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": _ogrenci_id(current_user),
        "tip": tip,
        "icerik_id": icerik_doc["id"],
        "cevaplar": [],
        "dogru_sayisi": 0,
        "toplam_soru": _toplam_soru(meta, icerik_doc.get("icerik", {})),
        "sure_sn": 0,
        "puan": 0,
        "xp": 0,
        "durum": "devam",
        "baslama_t": datetime.utcnow().isoformat(),
        "bitis_t": None,
    }
    await db.egzersiz_oturumlari.insert_one(dict(oturum))
    return {
        "oturum_id": oturum["id"],
        "tip": tip,
        "toplam_soru": oturum["toplam_soru"],
        "icerik_id": icerik_doc["id"],
        "icerik": icerik_doc.get("icerik", {}),
        "mock": icerik_doc.get("mock", False),
    }


@router.post("/egzersiz/oturum/{oturum_id}/cevap")
async def egzersiz_cevap(oturum_id: str, data: dict, current_user=Depends(get_current_user)):
    """Tek bir sorunun cevabını değerlendirir."""
    oturum = await db.egzersiz_oturumlari.find_one({"id": oturum_id})
    if not oturum:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    meta = tip_meta(oturum["tip"])
    icerik_doc = await db.egzersiz_icerikler.find_one({"id": oturum["icerik_id"]})
    icerik = icerik_doc.get("icerik", {}) if icerik_doc else {}

    soru_no = int(data.get("soru_no", 0))
    cevap = data.get("cevap")
    dogru, dogru_cevap = _kontrol(meta, icerik, soru_no, cevap)

    await db.egzersiz_oturumlari.update_one(
        {"id": oturum_id},
        {
            "$push": {"cevaplar": {"soru_no": soru_no, "cevap": cevap, "dogru": dogru}},
            "$inc": {"dogru_sayisi": 1 if dogru else 0},
        },
    )
    return {"dogru": dogru, "dogru_cevap": dogru_cevap}


@router.post("/egzersiz/oturum/{oturum_id}/bitir")
async def egzersiz_bitir(oturum_id: str, data: dict = None, current_user=Depends(get_current_user)):
    """Oturumu kapatır, puan + XP hesaplar ve kaydeder."""
    data = data or {}
    oturum = await db.egzersiz_oturumlari.find_one({"id": oturum_id})
    if not oturum:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    if oturum.get("durum") == "tamamlandi":
        return _temizle(oturum)

    toplam = oturum.get("toplam_soru", 0) or 1
    dogru_sayisi = oturum.get("dogru_sayisi", 0)
    sure_sn = int(data.get("sure_sn", 0))
    oran = dogru_sayisi / toplam if toplam else 0

    baz_xp = (await get_xp_tablosu()).get("egzersiz_motoru", 10)
    xp = round(baz_xp * oran)
    puan = dogru_sayisi * 2

    # ── Doğruluk + süre + zorluk bazlı SKOR + kişisel rekor ("En Yüksek Skor").
    #    İçeriğin zorluğu skoru etkiler; rekor tip bazlıdır (deyim_bosluk ile
    #    atasozu_bosluk ayrı rekorlar tutar). ──
    icerik_zorluk = "orta"
    try:
        _idoc = await db.egzersiz_icerikler.find_one(
            {"id": oturum.get("icerik_id")}, {"zorluk": 1})
        icerik_zorluk = (_idoc or {}).get("zorluk") or "orta"
    except Exception:
        pass
    zorluk_num = _ZORLUK_SEVIYE.get(str(icerik_zorluk).lower(), 3)
    yanlis = max(0, toplam - dogru_sayisi)
    skor = _egz_skor(dogru_sayisi, yanlis, sure_sn, zorluk_num)
    # Rekoru güncellemeden ÖNCE oku (bu oturum hariç önceki en yüksek).
    _onceki = await db.egzersiz_oturumlari.find(
        {"ogrenci_id": oturum.get("ogrenci_id"), "tip": oturum.get("tip"),
         "durum": "tamamlandi", "skor": {"$gt": 0}},
    ).sort("skor", -1).limit(1).to_list(1)
    onceki_rekor = _onceki[0]["skor"] if _onceki else 0

    # ── Kelime-anlam egzersizi tamamlandı → öğrenci kelime durumu (Leitner) güncelle.
    #    Cevaba göre (soru_no eşleşirse) kelime-başı doğruluk; yoksa genel oran. Böylece
    #    öğrenilen kelimeler (kutu>=4) sonraki üretim/seçimlerde rotasyondan çıkar. ──
    if oturum.get("tip") in _MEB_KELIME_TIPLERI:
        try:
            icerik_doc = await db.egzersiz_icerikler.find_one({"id": oturum.get("icerik_id")})
            hedefler = _icerik_hedef_kelimeler((icerik_doc or {}).get("icerik", {}))
            if hedefler:
                ogr = oturum.get("ogrenci_id") or _ogrenci_id(current_user)
                s = int((icerik_doc or {}).get("sinif", 3) or 3)
                cmap = {int(c.get("soru_no", -1)): bool(c.get("dogru"))
                        for c in oturum.get("cevaplar", [])}
                genel = oran >= 0.5
                for i, w in enumerate(hedefler):
                    await kelime_karsilasma(ogr, w, cmap.get(i, genel), s, xp_ver=False)
        except Exception as ex:
            logging.warning(f"[egzersiz_motoru] Leitner güncelleme hatası: {ex}")

    await db.egzersiz_oturumlari.update_one(
        {"id": oturum_id},
        {"$set": {
            "durum": "tamamlandi",
            "sure_sn": sure_sn,
            "puan": puan,
            "xp": xp,
            "skor": skor,
            "zorluk": icerik_zorluk,
            "bitis_t": datetime.utcnow().isoformat(),
        }},
    )

    # XP'yi öğrenciye ekle (kanonik desen: db.students + xp_logs)
    ogrenci_id = oturum.get("ogrenci_id")
    if xp > 0 and ogrenci_id:
        await db.students.update_one({"id": ogrenci_id}, {"$inc": {"toplam_xp": xp}})
        await db.xp_logs.insert_one({
            "id": str(uuid.uuid4()),
            "ogrenci_id": ogrenci_id,
            "eylem": f"egzersiz_{oturum['tip']}",
            "xp": xp,
            "tarih": datetime.utcnow().isoformat(),
        })

    return {
        "oturum_id": oturum_id,
        "dogru_sayisi": dogru_sayisi,
        "toplam_soru": toplam,
        "puan": puan,
        "xp": xp,
        "skor": skor,
        "rekor": max(skor, onceki_rekor),
        "yeni_rekor": skor > onceki_rekor,
        "zorluk": icerik_zorluk,
        "oran": round(oran * 100),
    }


@router.post("/egzersiz/kelime-gezmece/dogrula")
async def kelime_gezmece_dogrula(data: dict, current_user=Depends(get_current_user)):
    """Kelime Gezmece — oyuncunun oluşturduğu kelimeyi doğrular.

    Body: { icerik_id, harf_sirasi: ["e","l","m","a"] }
    Yanıt: { kelime, durum: "grid"|"bonus"|"gecersiz", puan_kazanildi }

    Puanlama (KELIME_GEZMECE özel kuralı): grid kelimesi +10, bonus kelime +15.
    Kelime havuzunun tamamı istemciye verilmez; doğrulama burada yapılır.
    Yetki: giriş yapmış herhangi bir kullanıcı (öğrenci/öğretmen/admin).
    """
    icerik_id = data.get("icerik_id")
    harf_sirasi = data.get("harf_sirasi") or []
    if not icerik_id:
        raise HTTPException(status_code=400, detail="icerik_id gerekli")
    if not isinstance(harf_sirasi, list) or not harf_sirasi:
        raise HTTPException(status_code=400, detail="harf_sirasi (liste) gerekli")

    icerik_doc = await db.egzersiz_icerikler.find_one({"id": icerik_id})
    if not icerik_doc:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    if icerik_doc.get("tip") != "kelime_gezmece":
        raise HTTPException(status_code=400, detail="İçerik Kelime Gezmece türünde değil")

    icerik = icerik_doc.get("icerik", {})
    sinif = int(icerik_doc.get("sinif", 3))
    kelime = "".join(str(h) for h in harf_sirasi)
    durum, puan = kelime_dogrula(icerik, kelime, sinif)
    return {"kelime": kelime, "durum": durum, "puan_kazanildi": puan}


@router.post("/egzersiz/kelime-gezmece/seviye")
async def kelime_gezmece_seviye(data: dict, current_user=Depends(get_current_user)):
    """Kelime Gezmece — belirli sınıf/seviye için bulmaca getirir veya üretir.

    Body: { sinif, seviye_no }
    Yanıt: { icerik_id, icerik, seviye_no }

    Cache: (sinif, seviye_no) kombinasyonu daha önce üretildiyse aynı içerik
    kullanılır (kullanim_sayisi += 1); yoksa bulmaca_olusturucu ile üretilip
    egzersiz_icerikler koleksiyonuna kaydedilir (kaynak="otomatik_uretim").
    """
    sinif = max(1, min(8, int(data.get("sinif", 3))))
    seviye_no = max(1, int(data.get("seviye_no", 1)))

    mevcut = await db.egzersiz_icerikler.find_one({
        "tip": "kelime_gezmece", "sinif": sinif,
        "icerik.seviye_no": seviye_no, **_AKTIF,
    })
    if mevcut:
        await db.egzersiz_icerikler.update_one(
            {"id": mevcut["id"]},
            {"$inc": {"kullanim_sayisi": 1},
             "$set": {"son_kullanim_tarihi": datetime.utcnow().isoformat()}},
        )
        return {"icerik_id": mevcut["id"], "icerik": mevcut.get("icerik", {}),
                "seviye_no": seviye_no}

    meb = await _meb_kelimeler(sinif)
    icerik = bulmaca_uret(sinif, seviye_no, meb_kelimeler=meb or None)
    olusturan = {
        "id": current_user.get("id"),
        "ad": _kullanici_ad(current_user),
        "rol": current_user.get("role", ""),
    }
    doc = await _icerik_kaydet("kelime_gezmece", sinif, None, None, icerik,
                              current_user.get("id"), False,
                              kaynak="otomatik_uretim", olusturan=olusturan)
    return {"icerik_id": doc["id"], "icerik": icerik, "seviye_no": seviye_no}


@router.post("/egzersiz/kelime-gezmece/tamamla")
async def kelime_gezmece_tamamla(data: dict, current_user=Depends(get_current_user)):
    """Kelime Gezmece — çok seviyeli oturumu bitirir, XP + puanı sıralamaya işler.

    Body: { sinif, seviye_sayisi, bonus_sayisi, toplam_puan, en_yuksek_seviye?, sure_sn? }
    XP kuralı: tamamlanan her seviye +50 XP, her bonus kelime +15 XP.
    (Yarım kalan seviye sayılmaz — frontend yalnızca tamamlanan seviyeleri iletir.)
    """
    sinif = max(1, min(8, int(data.get("sinif", 3))))
    seviye_sayisi = max(0, int(data.get("seviye_sayisi", 0)))
    bonus_sayisi = max(0, int(data.get("bonus_sayisi", 0)))
    toplam_puan = max(0, int(data.get("toplam_puan", 0)))
    en_yuksek_seviye = max(seviye_sayisi, int(data.get("en_yuksek_seviye", seviye_sayisi)))
    sure_sn = int(data.get("sure_sn", 0))

    xp = seviye_sayisi * 50 + bonus_sayisi * 15
    ogrenci_id = _ogrenci_id(current_user)
    now = datetime.utcnow().isoformat()

    oturum = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "tip": "kelime_gezmece",
        "icerik_id": None,
        "cevaplar": [],
        "dogru_sayisi": seviye_sayisi,
        "toplam_soru": max(1, seviye_sayisi),
        "seviye_sayisi": seviye_sayisi,
        "bonus_sayisi": bonus_sayisi,
        "en_yuksek_seviye": en_yuksek_seviye,
        "sure_sn": sure_sn,
        "puan": toplam_puan,
        "xp": xp,
        "durum": "tamamlandi",
        "baslama_t": now,
        "bitis_t": now,
    }
    await db.egzersiz_oturumlari.insert_one(dict(oturum))

    if xp > 0 and ogrenci_id:
        await db.students.update_one({"id": ogrenci_id}, {"$inc": {"toplam_xp": xp}})
        await db.xp_logs.insert_one({
            "id": str(uuid.uuid4()),
            "ogrenci_id": ogrenci_id,
            "eylem": "egzersiz_kelime_gezmece",
            "xp": xp,
            "tarih": now,
        })

    return {
        "xp": xp,
        "seviye_sayisi": seviye_sayisi,
        "bonus_sayisi": bonus_sayisi,
        "toplam_puan": toplam_puan,
        "en_yuksek_seviye": en_yuksek_seviye,
    }


@router.get("/egzersiz/gecmis/{ogrenci_id}")
async def egzersiz_gecmis(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin egzersiz oturum geçmişi (son 50)."""
    oturumlar = await db.egzersiz_oturumlari.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("baslama_t", -1).to_list(length=50)
    for o in oturumlar:
        o.pop("_id", None)
    return {"oturumlar": oturumlar}


@router.get("/egzersiz/rekorlar")
async def egzersiz_rekorlar(ogrenci_id: str | None = Query(None),
                            current_user=Depends(get_current_user)):
    """Öğrencinin tip bazlı kişisel rekorları ("En Yüksek Skor").

    Dönüş: {tip: {ad, rekor, oynanma}}. Her egzersiz tipi (örn. deyim_bosluk ve
    atasozu_bosluk) AYRI rekor tutar — karışmaz. ogrenci_id verilmezse aktif
    kullanıcının kendi rekorları döner.
    """
    oid = ogrenci_id or _ogrenci_id(current_user)
    cur = db.egzersiz_oturumlari.aggregate([
        {"$match": {"ogrenci_id": oid, "durum": "tamamlandi", "skor": {"$gt": 0}}},
        {"$group": {"_id": "$tip", "rekor": {"$max": "$skor"}, "oynanma": {"$sum": 1}}},
    ])
    out = {}
    async for r in cur:
        meta = tip_meta(r["_id"]) or {}
        out[r["_id"]] = {"ad": meta.get("ad", r["_id"]),
                         "rekor": r["rekor"], "oynanma": r["oynanma"]}
    return out


# ─────────────────────────────────────────────
# Kütüphane endpoint'leri (öğretmen/koordinatör/admin)
# ─────────────────────────────────────────────
_KUTUPHANE_YETKI = require_role(UserRole.ADMIN, UserRole.COORDINATOR, UserRole.TEACHER)


@router.get("/egzersiz/icerikler")
async def egzersiz_icerikler(
    tip: str | None = Query(None),
    sinif: int | None = Query(None),
    durum: str = Query("aktif"),
    sayfa: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(_KUTUPHANE_YETKI),
):
    """Kalıcı içerik kütüphanesi — sayfalı liste (öğretmen/koordinatör/admin).

    durum: "aktif" (varsayılan) | "arsivli" | "hepsi".
    """
    sorgu: dict = {}
    if tip:
        sorgu["tip"] = tip
    if sinif is not None:
        sorgu["sinif"] = sinif
    if durum == "aktif":
        sorgu.update(_AKTIF)
    elif durum and durum != "hepsi":
        sorgu["durum"] = durum

    toplam = await db.egzersiz_icerikler.count_documents(sorgu)
    atla = (sayfa - 1) * limit
    docs = await db.egzersiz_icerikler.find(sorgu).sort(
        "olusturma_tarihi", -1
    ).skip(atla).limit(limit).to_list(length=limit)

    return {
        "icerikler": [_ozet_kayit(d) for d in docs],
        "toplam": toplam,
        "sayfa": sayfa,
        "limit": limit,
        "sayfa_sayisi": max(1, -(-toplam // limit)),  # ceil
    }


@router.get("/egzersiz/icerik/{icerik_id}")
async def egzersiz_icerik_detay(icerik_id: str, current_user=Depends(_KUTUPHANE_YETKI)):
    """Tek içeriğin tam detayı + aynı varyant grubundaki kardeşleri (önizleme)."""
    doc = await db.egzersiz_icerikler.find_one({"id": icerik_id})
    if not doc:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")

    grup = doc.get("varyant_grubu") or doc["id"]
    kardesler = await db.egzersiz_icerikler.find(
        {"$or": [{"varyant_grubu": grup}, {"id": icerik_id}]}
    ).sort("olusturma_tarihi", -1).to_list(length=50)

    kardes_ozet = [{
        "id": k.get("id"),
        "ozet": _icerik_ozet(k.get("icerik", {})),
        "durum": k.get("durum", "aktif"),
        "kullanim_sayisi": k.get("kullanim_sayisi", 0),
        "olusturma_tarihi": k.get("olusturma_tarihi"),
        "kendisi": k.get("id") == icerik_id,
    } for k in kardesler]

    meta = tip_meta(doc.get("tip", "")) or {}
    return {
        **_temizle(doc),
        "tip_ad": meta.get("ad", doc.get("tip")),
        "ikon": meta.get("ikon", "📝"),
        "puanlama": meta.get("puanlama", "secmeli"),
        "varyant_sayisi": len(kardes_ozet),
        "kardesler": kardes_ozet,
    }


@router.post("/egzersiz/icerik/{icerik_id}/varyant-uret")
async def egzersiz_varyant_uret(icerik_id: str, current_user=Depends(_KUTUPHANE_YETKI)):
    """Mevcut içeriğin YENİ bir varyantını AI ile üretir.

    Eski içerik ARŞİVLENMEZ — "aktif" kalır. Yeni içerik aynı varyant grubuna
    eklenir; böylece kütüphanede gruplanır.
    """
    eski = await db.egzersiz_icerikler.find_one({"id": icerik_id})
    if not eski:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")

    tip = eski["tip"]
    sinif = int(eski.get("sinif", 3))
    konu = eski.get("konu") or None
    zorluk = eski.get("zorluk") or None
    grup = eski.get("varyant_grubu") or eski["id"]

    icerik, mock = await _icerik_uret(tip, sinif, konu, zorluk)
    olusturan = {
        "id": current_user.get("id"),
        "ad": _kullanici_ad(current_user),
        "rol": current_user.get("role", ""),
    }
    yeni = await _icerik_kaydet(tip, sinif, konu, zorluk, icerik, current_user.get("id"),
                                mock, kaynak="ai_uretim", olusturan=olusturan,
                                varyant_grubu=grup)
    return {**_temizle(yeni), "varyant_uretildi": True}


@router.patch("/egzersiz/icerik/{icerik_id}/arsivle")
async def egzersiz_arsivle(icerik_id: str, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """İçeriği arşivler (durum="arsivli"). Yalnızca admin. Kayıt DB'de kalır;
    oturum çekiminde artık gelmez."""
    res = await db.egzersiz_icerikler.update_one(
        {"id": icerik_id}, {"$set": {"durum": "arsivli"}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    return {"id": icerik_id, "durum": "arsivli"}


@router.delete("/egzersiz/icerik/{icerik_id}")
async def egzersiz_icerik_sil(icerik_id: str, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """İçeriği kalıcı siler (hard delete). Yalnızca admin; nadir kullanılır.
    Genelde arşivleme tercih edilmelidir."""
    res = await db.egzersiz_icerikler.delete_one({"id": icerik_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    return {"id": icerik_id, "silindi": True}
