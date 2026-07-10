"""Sınav Modülü smoke testi.

İki aşama:
  1) Saf parser (DB gerektirmez): a_2026_sozel.pdf → 40 soru (İng hariç), her
     soruda bölge görseli + doğru cevap, 0 uyarı.
  2) API/DB akışı (izole test DB'sine karşı): yukle → taslaklar → soru → gorsel
     → PUT → yayinla → grup-yayinla → istatistik → sil.

Çalıştırma:
  cd appbackend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_sinav_smoke.py
"""
import asyncio
import io
import os
import sys

# İzole test DB (production'a ASLA dokunma) — import ÖNCESİ ayarlanır;
# core.config load_dotenv(override=False) olduğu için bu değerler kazanır.
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = "oba_test_sinav_smoke"
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Python 3.14: motor GridFS bucket import anında event loop ister.
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

from starlette.datastructures import UploadFile  # noqa: E402
from starlette.responses import Response  # noqa: E402

from core.db import db  # noqa: E402
import modules.sinav as sinav  # noqa: E402
from modules.sinav_parser import parse_sinav_pdf  # noqa: E402

PDF_YOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "a_2026_sozel.pdf")
MOCK_ADMIN = {"id": "admin-test", "role": "admin", "ad": "Test", "soyad": "Yönetici"}

_gecti = 0
_kaldi = 0


def kontrol(kosul: bool, ad: str):
    global _gecti, _kaldi
    if kosul:
        _gecti += 1
        print(f"  [GECTI] {ad}")
    else:
        _kaldi += 1
        print(f"  [KALDI] {ad}")


async def faz1_parser():
    print("\n== FAZ 1: Parser (DB'siz) ==")
    if not os.path.exists(PDF_YOL):
        print(f"  [ATLA] örnek PDF yok: {PDF_YOL}")
        return
    r = parse_sinav_pdf(open(PDF_YOL, "rb").read())
    sorular = r["sorular"]
    kontrol(len(sorular) == 40, f"40 soru (bulunan: {len(sorular)})")
    kontrol(all(s["soruBolgeGorseli_b64"] for s in sorular), "hepsinde bölge görseli")
    kontrol(all(s["dogruCevap"] in ("A", "B", "C", "D") for s in sorular), "hepsinde doğru cevap")
    kontrol(len(r["uyarilar"]) == 0, f"0 uyarı (bulunan: {len(r['uyarilar'])})")
    kontrol(all(s["ders"] != "ingilizce" for s in sorular), "İngilizce atlandı")


async def faz2_api():
    print("\n== FAZ 2: API/DB akışı (izole test DB) ==")
    if not os.path.exists(PDF_YOL):
        print("  [ATLA] örnek PDF yok")
        return
    # temiz başla
    await db.client.drop_database("oba_test_sinav_smoke")

    # 1) yukle
    pdf_bytes = open(PDF_YOL, "rb").read()
    uf = UploadFile(io.BytesIO(pdf_bytes), filename="a_2026_sozel.pdf")
    r1 = await sinav.sinav_yukle(dosya=uf, sinavTuru="LGS", yil=2026, sinifSeviyesi=8, current_user=MOCK_ADMIN)
    kontrol(r1["olusturulan"] == 40, f"yukle → 40 taslak (bulunan: {r1['olusturulan']})")
    grup = r1["grup_id"]

    # 2) taslaklar (hafif — görsel sızmamalı)
    r2 = await sinav.sinav_taslaklar(grup_id=grup, ders=None, durum=None, sayfa=1, limit=200, current_user=MOCK_ADMIN)
    kontrol(r2["toplam"] == 40, f"taslaklar → 40 (bulunan: {r2['toplam']})")
    kontrol(all("soruBolgeGorseli_b64" not in s for s in r2["sorular"]), "liste görseli sızdırmıyor")

    # 3) tek soru + görsel
    t3 = next(s for s in r2["sorular"] if s["ders"] == "turkce" and s["soruNo"] == 3)
    d = await sinav.sinav_soru_getir(soru_id=t3["id"], current_user=MOCK_ADMIN)
    kontrol(d["dogruCevap"] == "D", f"turkce-3 doğru cevap D (bulunan: {d['dogruCevap']})")
    resp = await sinav.sinav_soru_gorsel(soru_id=t3["id"], current_user=MOCK_ADMIN)
    kontrol(isinstance(resp, Response) and len(resp.body) > 1000, f"görsel PNG döndü ({len(resp.body)}B)")
    kontrol(resp.media_type == "image/png", "görsel mime image/png")

    # 4) PUT düzenle
    await sinav.sinav_soru_guncelle(
        soru_id=t3["id"],
        data={"konu": "Cümlede Anlam", "zorluk": "orta", "cozumTaktigi": "Önce altı çizili sözcüğe bak."},
        current_user=MOCK_ADMIN,
    )
    d2 = await sinav.sinav_soru_getir(soru_id=t3["id"], current_user=MOCK_ADMIN)
    kontrol(d2["konu"] == "Cümlede Anlam" and d2["zorluk"] == "orta", "PUT konu/zorluk yansıdı")
    kontrol(bool(d2["cozumTaktigi"]), "cozumTaktigi yazıldı")

    # 5) yayinla (tek)
    ry = await sinav.sinav_soru_yayinla(soru_id=t3["id"], current_user=MOCK_ADMIN)
    kontrol(ry["durum"] == "yayinda", "tek soru yayınlandı")

    # 6) grup toplu yayinla (kalan doğru-cevaplı taslaklar)
    rg = await sinav.sinav_grup_yayinla(grup_id=grup, current_user=MOCK_ADMIN)
    kontrol(rg["yayinlanan"] >= 38, f"grup toplu yayın (yayınlanan: {rg['yayinlanan']})")

    # 7) istatistik
    ist = await sinav.sinav_istatistik(current_user=MOCK_ADMIN)
    kontrol(ist["toplam_yayinda"] == 40, f"istatistik yayında 40 (bulunan: {ist['toplam_yayinda']})")

    # 8) soft-delete
    await sinav.sinav_soru_sil(soru_id=t3["id"], current_user=MOCK_ADMIN)
    r_after = await sinav.sinav_taslaklar(grup_id=grup, ders=None, durum=None, sayfa=1, limit=200, current_user=MOCK_ADMIN)
    kontrol(r_after["toplam"] == 39, f"soft-delete sonrası 39 (bulunan: {r_after['toplam']})")

    # temizlik
    await db.client.drop_database("oba_test_sinav_smoke")


async def main():
    await faz1_parser()
    try:
        await faz2_api()
    except Exception as ex:
        global _kaldi
        _kaldi += 1
        print(f"  [KALDI] FAZ 2 istisna: {ex}")
        try:
            await db.client.drop_database("oba_test_sinav_smoke")
        except Exception:
            pass
    print(f"\n=== SONUÇ: {_gecti} geçti, {_kaldi} kaldı ===")
    return 0 if _kaldi == 0 else 1


if __name__ == "__main__":
    sys.exit(_loop.run_until_complete(main()))
