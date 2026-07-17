"""Kutulu Okuma egzersizi — metin seçim endpoint'i.

Öğrencinin SINIF'ına ve KUR'una (→ zorluk) uygun bir metni `analiz_metinler`
havuzundan (durum="havuzda") seçip döner. Kutulama/grid render frontend'de
yapılır; burada yalnız ham metin döner.

Eşleşme yoksa kademeli fallback: sınıf+zorluk → sınıf → herhangi havuz metni.
"""
import re
import random

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import get_current_user

router = APIRouter()


def _kur_to_zorluk(kur: str) -> str:
    """Öğrencinin kur'unu zorluğa eşler: 1→kolay, 2→orta, ≥3→zor, yoksa orta."""
    if not kur:
        return "orta"
    m = re.search(r"\d+", str(kur))
    if not m:
        return "orta"
    n = int(m.group())
    if n <= 1:
        return "kolay"
    if n == 2:
        return "orta"
    return "zor"


async def _ogrenci_sinif_kur(current_user: dict):
    """Öğrenci ise (linked_id → students) sınıf ve kur'unu döner, yoksa (None, None)."""
    linked_id = current_user.get("linked_id")
    if linked_id:
        st = await db.students.find_one({"id": linked_id})
        if st:
            return str(st.get("sinif", "") or ""), st.get("kur", "") or ""
    return None, None


def _metin_ozet(m: dict) -> dict:
    return {
        "id": m.get("id"),
        "baslik": m.get("baslik", ""),
        "icerik": m.get("icerik", ""),
        "sinif": m.get("sinif_seviyesi", ""),
        "zorluk": m.get("zorluk", ""),
        "kelime_sayisi": m.get("kelime_sayisi", 0),
        # Yüklenmiş görsel varsa öğrenciye metinle birlikte gösterilir
        # (ham base64 değil; /diagnostic/texts/{id}/gorsel'den çekilir).
        # gorsel_prompt ASLA dönmez.
        "gorsel_var": bool(m.get("gorsel")),
    }


@router.get("/kutulu-okuma/metin")
async def kutulu_okuma_metin(
    sinif: str = None,
    zorluk: str = None,
    current_user=Depends(get_current_user),
):
    """Öğrencinin sınıf+kur'una (veya query override'ına) uygun havuz metni döner.

    - Öğrenci: kendi sinif + kur→zorluk (query verilmezse).
    - Eğitici/önizleme: query ile sinif/zorluk verebilir; verilmezse herhangi metin.
    Kademeli fallback ile havuzda en az bir metin varsa daima sonuç döner.
    """
    ogr_sinif, ogr_kur = await _ogrenci_sinif_kur(current_user)
    # Hedef sınıf/zorluk: query öncelikli, yoksa öğrencinin değerleri
    hedef_sinif = sinif or ogr_sinif
    if hedef_sinif:
        m = re.search(r"\d+", str(hedef_sinif))
        hedef_sinif = m.group() if m else None
    hedef_zorluk = zorluk or (_kur_to_zorluk(ogr_kur) if ogr_kur is not None else None)

    async def _sec(query: dict):
        # TEK KAYNAK: yalnız 150'lik Akıcı Okuma havuzundan (bolum=analiz) seç
        query = {"bolum": "analiz", **query}
        adaylar = await db.analiz_metinler.find(query).to_list(length=None)
        return random.choice(adaylar) if adaylar else None

    secilen = None
    eslesme = "yok"
    # 1) sınıf + zorluk
    if hedef_sinif and hedef_zorluk:
        secilen = await _sec({"durum": "havuzda", "sinif_seviyesi": hedef_sinif, "zorluk": hedef_zorluk})
        if secilen:
            eslesme = "sinif_zorluk"
    # 2) sınıf-only fallback
    if not secilen and hedef_sinif:
        secilen = await _sec({"durum": "havuzda", "sinif_seviyesi": hedef_sinif})
        if secilen:
            eslesme = "sinif"
    # 3) herhangi havuz metni
    if not secilen:
        secilen = await _sec({"durum": "havuzda"})
        if secilen:
            eslesme = "herhangi"

    if not secilen:
        raise HTTPException(status_code=404, detail="Havuzda uygun metin bulunamadı")

    sonuc = _metin_ozet(secilen)
    sonuc["eslesme"] = eslesme  # sinif_zorluk | sinif | herhangi (bilgi amaçlı)
    sonuc["hedef_sinif"] = hedef_sinif
    sonuc["hedef_zorluk"] = hedef_zorluk
    return sonuc
