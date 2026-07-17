"""AI CEO — Deniz bulguları için Çözüm Önerisi (Claude Code prompt / operasyonel adım) +
bulgu bazlı yeniden kontrol (Kontrol Et).

Çözüm ŞABLONdan üretilir (deterministik türlerde AI YOK). Kod düzeltmesi gerektirenler
kopyalanabilir Claude Code promptu; operasyonel işlemler "operasyonel adım" kartı.
AI-turu bulgularında Deniz'in iyileştirme adımı prompt formatına dönüştürülür.
"""
import json

from .fotograf import son_fotograf

_KAPANIS = "refactor/modular-server'da ilerle, standart akışla (main + production) deploy et."


def _prompt(sorun, kanit_ozet, beklenen, test):
    return (f"SORUN: {sorun}\n"
            f"KANIT: {kanit_ozet}\n"
            f"BEKLENEN DÜZELTME: {beklenen}\n"
            f"TEST ŞARTI: {test}\n"
            f"{_KAPANIS}")


# tip: "prompt" (kod) | "operasyonel" (insan işlemi)
COZUM_SABLONLARI = {
    "yetim_kayit": {
        "tip": "prompt", "oneri": "Öğrencisi olmayan (yetim) kur kayıtlarını temizle/ilişkilendir.",
        "beklenen": "kur_ucretleri'nde ogrenci_id'si db.students'ta bulunmayan kayıtları tespit eden bir temizlik/migration yaz; yetimleri raporla ve güvenli şekilde arşivle/sil.",
        "test": "Migration sonrası yetim kur sayısı 0; mevcut geçerli kayıtlar etkilenmez (smoke test).",
    },
    "negatif_kayit": {
        "tip": "prompt", "oneri": "Negatif tutarlı kayıtların kaynağını bul ve giriş doğrulaması ekle.",
        "beklenen": "tutar/yapilan_odeme < 0 olan kayıtları tespit et; giriş noktalarında negatif değeri engelleyen doğrulama ekle; mevcut bozuk kayıtları düzelt.",
        "test": "Negatif tutar reddedilir (400) + mevcut negatif kayıt kalmaz (smoke).",
    },
    "vergi_snapshot_eksik": {
        "tip": "operasyonel", "oneri": "Vergi backfill'ini çalıştır (vergi'siz ödemeleri geri-doldurur).",
        "adim": "Muhasebe: 'Vergi backfill' işlemini çalıştır (POST /muhasebe/gecis/vergi-backfill). Vergi'siz öğrenci ödemelerine güncel/kayıtlı oranla snapshot eklenir. Yeni ödemeler zaten tahsilat anındaki oranla vergilenir.",
    },
    "dogrulanamayan_sayi": {
        "tip": "prompt", "oneri": "Ayda öneri promptunu/dayanak doğrulamasını sıkılaştır.",
        "beklenen": "Analiz promptunda sayıların fotoğraf metrikleriyle bire bir olmasını zorla; üretim sonrası doğrulanamayan sayıları öneriden çıkar/işaretle.",
        "test": "Yeni analizde doğrulanamayan sayı oranı eşiğin altında (smoke).",
    },
    "arsivli_acik_alacak": {
        "tip": "operasyonel", "oneri": "Muhasebeci: arşivli öğrencilerdeki açık alacakları gözden geçirip kapat/sıfırla.",
        "adim": "Muhasebe → Öğrenci Ödemeleri'nde arşivli+borçlu kayıtları aç; tahsilat/mahsup uygula veya kaydı düzelt.",
    },
    "damgasiz_hakedis": {
        "tip": "operasyonel", "oneri": "Tamamlanmış kurların hakediş damgasını backfill ile tamamla.",
        "adim": "AI CEO/Muhasebe: 'ödeme-tarihi-backfill' işlemini çalıştır; tamamlanmış kurlara tamamlanma damgası konur.",
    },
    "maliyet_sicramasi": {
        "tip": "operasyonel", "oneri": "AI çağrı artışını incele (hangi özellik/tetik arttı?).",
        "adim": "Maliyet Denetimi tablosundan ay/model/özellik kırılımına bak; beklenmeyen tetikleyiciyi (ör. sık analiz koşumu) durdur.",
    },
    "tekrarlanan_oneri": {
        "tip": "operasyonel", "oneri": "Yinelenen açık önerileri tek örneğe indir (kök neden zaten engelli).",
        "adim": "'Kontrol Et'e bas: aynı başlıklı açık öneriler en yenisi kalacak şekilde birleştirilir "
                "(eskiler ertelenir). Analiz artık her koşuşunda aynı başlığı yeniden üretmiyor; bu, birikmiş "
                "kopyaların tek tıkla temizliğidir.",
    },
}


def _kanit_ozet(kanit) -> str:
    if not kanit:
        return "—"
    if isinstance(kanit, dict):
        oz = {k: v for k, v in kanit.items() if k != "ornekler"}
        s = json.dumps(oz, ensure_ascii=False)
        ornek = kanit.get("ornekler")
        if ornek:
            s += f" · örnekler: {json.dumps(ornek[:5], ensure_ascii=False)}"
        return s[:500]
    return str(kanit)[:500]


def bulgu_cozum(bulgu: dict) -> dict:
    """Bulguya göre çözüm önerisi + (kod ise) kopyalanabilir Claude Code promptu üretir."""
    tur = bulgu.get("tur")
    kanit_ozet = _kanit_ozet(bulgu.get("kanit"))
    # AI-turu bulgusu → Deniz'in iyileştirme adımını prompt formatına çevir
    if bulgu.get("kaynak") == "ai":
        return {"tip": "prompt", "oneri": "Deniz'in iyileştirme adımını uygula.",
                "prompt": _prompt(bulgu.get("ozet", ""), kanit_ozet,
                                  "Deniz'in denetim bulgusunu giderecek düzeltmeyi uygula.",
                                  "Aynı denetim tekrar çalıştığında bu bulgu tekrar üretilmez.")}
    s = COZUM_SABLONLARI.get(tur)
    if not s:
        # jenerik prompt
        return {"tip": "prompt", "oneri": f"'{tur}' bulgusunu gider.",
                "prompt": _prompt(bulgu.get("ozet", ""), kanit_ozet,
                                  "Bulgunun kök nedenini gider.", "Bulgu tekrar üretilmez (smoke).")}
    if s["tip"] == "operasyonel":
        return {"tip": "operasyonel", "oneri": s["oneri"], "adim": s["adim"], "kanit_ozet": kanit_ozet}
    return {"tip": "prompt", "oneri": s["oneri"],
            "prompt": _prompt(bulgu.get("ozet", ""), kanit_ozet, s["beklenen"], s["test"])}


# ─────────────────────── Kontrol Et: bulgu bazlı yeniden kontrol ───────────────────────
_VERI_KALITESI = {"yetim_kayit", "negatif_kayit", "arsivli_acik_alacak", "damgasiz_hakedis", "vergi_snapshot_eksik"}


async def bulgu_yeniden_kontrol(bulgu: dict) -> tuple:
    """(durum, guncel_kanit): 'cozuldu' | 'devam' | 'sonraki_tur'. Yalnız o bulgunun
    deterministik kontrolü yeniden koşar (tam tur değil; AI çağrısı yok)."""
    from . import deniz_guc as G
    tur = bulgu.get("tur")
    if bulgu.get("kaynak") == "ai":
        return ("sonraki_tur", None)  # AI-turu → sonraki denetime işaretlenir
    guncel = []
    if tur in _VERI_KALITESI:
        guncel = await G.veri_kalitesi_kontrol()
    elif tur == "dogrulanamayan_sayi":
        guncel, _ = await G.sayi_dogrulama_kontrol(await son_fotograf() or {})
    elif tur == "maliyet_sicramasi":
        guncel = await G.maliyet_bulgu()
    elif str(tur).startswith("ikinci_goz"):
        guncel = await G.ikinci_goz(await son_fotograf() or {})
    elif tur == "tekrarlanan_oneri":
        # Kök neden temizliği: yinelenen açık önerileri birleştir, sonra yeniden denetle
        from .analiz import oneri_dedup
        await oneri_dedup()
        from .deniz import deterministik_kontroller
        guncel = await deterministik_kontroller()
    else:
        from .deniz import deterministik_kontroller
        guncel = await deterministik_kontroller()
    eslesen = next((g for g in guncel if g.get("tur") == tur), None)
    if eslesen is None:
        return ("cozuldu", None)
    return ("devam", eslesen.get("kanit"))
