"""AI CEO — dürüst öğrenme: RAG hafıza enjeksiyonu + ölçülebilir öğrenme metrikleri (FAZ 4, madde 13-14).

DÜRÜSTLÜK (kritik): Bu GERÇEK MODEL EĞİTİMİ DEĞİLDİR. Model ağırlıkları DEĞİŞMEZ. Yalnızca geçmiş
olumsuz geri bildirimler (+düzeltme metni) LLM çağrısından önce sistem promptuna BAĞLAM olarak
enjekte edilir (RAG tabanlı hafıza). Metrikler yalnız ölçülebilir/doğrulanabilir sayılardır;
veri <5 ise "—" döner, ASLA sahte yüzde üretilmez.

Uç: GET /ai/ceo/ogrenme/metrikler. Enjeksiyon: ogrenme_enjeksiyonu() (analiz/karar/persona_sohbet çağırır).
"""
from collections import defaultdict

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import aware

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

_ASGARI_VERI = 5      # bu sayının altında "henüz öğrenecek kadar veri yok"
_ENJEKSIYON_N = 5     # prompta enjekte edilen son ders sayısı


async def ogrenme_enjeksiyonu(ajan: str, kategori: str | None = None, n: int = _ENJEKSIYON_N) -> str:
    """İlgili ajanın SON N olumsuz+düzeltmeli geri bildirimini özetleyip prompt bağlamı üretir.
    Model eğitimi DEĞİL — yalnız bağlam enjeksiyonu (RAG hafıza). Ders yoksa boş string."""
    q = {"ajan": (ajan or "").lower(), "puan": "olumsuz", "duzeltme_metni": {"$nin": [None, ""]}}
    if kategori:
        q["kategori"] = kategori
    dersler = await db.ai_geri_bildirim.find(
        q, {"_id": 0, "kategori": 1, "duzeltme_metni": 1}).sort("tarih", -1).to_list(length=n)
    if not dersler:
        return ""
    satirlar = "\n".join(f"- [{d.get('kategori', ajan)}] {d.get('duzeltme_metni')}" for d in dersler)
    return ("\n\nGEÇMİŞ GERİ BİLDİRİM DERSLERİ (RAG hafıza — model ağırlıkları DEĞİŞMEZ, yalnız bağlam): "
            "Aşağıdaki türde çıktılar geçmişte şu sebeplerle reddedildi; bunlara DİKKAT ET, tekrarlama:\n"
            f"{satirlar}")


def _hafta(tarih) -> str | None:
    d = aware(tarih)
    if d is None:
        return None
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


@router.get("/ai/ceo/ogrenme/metrikler")
async def ogrenme_metrikleri(ajan: str = "", current_user=Depends(_KOORD)):
    """Öğrenme seviyesi metrikleri — SADECE ölçülebilir, uydurma YOK:
      a) ajan başına toplam geri bildirim
      b) onay/red oranı zaman serisi (haftalık)
      c) tekrarlayan hata oranı (aynı kategoride tekrar eden olumsuz) — düşüyorsa öğrenme sinyali
      d) aktif enjekte edilen "öğrenilmiş ders" sayısı
    Veri <5 → yeterli_veri=false ("henüz öğrenecek kadar veri yok")."""
    q = {}
    if ajan:
        q["ajan"] = ajan.strip().lower()
    kayitlar = await db.ai_geri_bildirim.find(q, {"_id": 0}).sort("tarih", 1).to_list(length=20000)
    toplam = len(kayitlar)

    # (a) ajan başına toplam + olumlu/olumsuz
    ajan_sayim = defaultdict(lambda: {"toplam": 0, "olumlu": 0, "olumsuz": 0})
    for k in kayitlar:
        a = k.get("ajan", "genel")
        ajan_sayim[a]["toplam"] += 1
        ajan_sayim[a][k.get("puan", "olumsuz")] = ajan_sayim[a].get(k.get("puan", "olumsuz"), 0) + 1

    # (b) haftalık onay oranı + (c) tekrarlayan hata (o hafta önceden görülmüş kategoride tekrar olumsuz)
    hafta = defaultdict(lambda: {"olumlu": 0, "olumsuz": 0, "tekrar_olumsuz": 0})
    gorulmus_kategori = set()
    for k in kayitlar:
        h = _hafta(k.get("tarih"))
        if not h:
            continue
        puan = k.get("puan", "olumsuz")
        hafta[h][puan] = hafta[h].get(puan, 0) + 1
        if puan == "olumsuz":
            kat = k.get("kategori", k.get("ajan", "genel"))
            if kat in gorulmus_kategori:
                hafta[h]["tekrar_olumsuz"] += 1
            gorulmus_kategori.add(kat)

    onay_serisi, tekrar_serisi = [], []
    for h in sorted(hafta):
        d = hafta[h]
        top = d["olumlu"] + d["olumsuz"]
        onay_serisi.append({"hafta": h, "onay_orani": round(d["olumlu"] * 100 / top) if top else None,
                            "olumlu": d["olumlu"], "olumsuz": d["olumsuz"]})
        tekrar_serisi.append({"hafta": h, "tekrar_olumsuz": d["tekrar_olumsuz"], "toplam_olumsuz": d["olumsuz"],
                              "tekrar_orani": round(d["tekrar_olumsuz"] * 100 / d["olumsuz"]) if d["olumsuz"] else None})

    # (d) aktif enjekte edilebilir ders sayısı (olumsuz + düzeltme metinli)
    enjekte_edilebilir = await db.ai_geri_bildirim.count_documents(
        {**q, "puan": "olumsuz", "duzeltme_metni": {"$nin": [None, ""]}})

    return {
        "yeterli_veri": toplam >= _ASGARI_VERI,
        "toplam_geri_bildirim": toplam,
        "ajan_sayim": dict(ajan_sayim),
        "onay_orani_serisi": onay_serisi,
        "tekrar_hata_serisi": tekrar_serisi,
        "enjekte_edilen_ders": enjekte_edilebilir,
        "not": "RAG tabanlı hafıza enjeksiyonu — model ağırlıkları değişmiyor. Metrikler yalnız gerçek sayımdır.",
    }
