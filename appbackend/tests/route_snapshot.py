"""Route snapshot aracı — refactoring regresyon kapısı.

Uygulamanın TÜM route'larını (HTTP method + path) deterministik olarak listeler.
Refactoring öncesi/sonrası bu çıktı diff'lenir; tek satır fark = davranış değişti.

Kullanım:
    python tests/route_snapshot.py            # route listesini stdout'a yaz
    python tests/route_snapshot.py > routes.txt

NOT: server.py import sırasında GridFS bir event loop ister; bu yüzden import
asyncio.run içinde yapılır. DB'ye bağlanmaz, sadece route tablosunu okur.
"""
import asyncio
import os
import sys

# Gerçek DB'ye dokunmamak için izole isim (import sadece route okur, bağlanmaz).
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "oba_route_snapshot_dummy")

# server.py'yi paket dışından da import edebilmek için dizini path'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def _collect():
    import server
    satirlar = []
    for r in server.app.routes:
        methods = ",".join(sorted(getattr(r, "methods", []) or []))
        path = getattr(r, "path", "")
        satirlar.append(f"{methods}\t{path}")
    satirlar.sort()
    return satirlar


def main():
    satirlar = asyncio.run(_collect())
    for s in satirlar:
        print(s)
    print(f"# TOPLAM: {len(satirlar)}", file=sys.stderr)


if __name__ == "__main__":
    main()
