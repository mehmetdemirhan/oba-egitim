"""WhatsApp Cloud API (Faz 2) smoke — şablon gönderimi + durum webhook'u.

CANLI ÇAĞRI YOK: httpx mock'lanır. Doğrular: şablon payload'ı (template + body
parametreleri) doğru kurulur; başarı saglayici_id (wamid) döndürür; kanal kurulu
değilse 'kurulmadı'; webhook doğrulama (verify token eşleşme/uyuşmazlık); durum
webhook'u sent→gonderildi/delivered→iletildi/read→okundu/failed→hata, out-of-order
geri almaz; funnel'da İYS/onaysız alıcıya WhatsApp gönderilmez.
İzole DB (oba_test_whatsapp). Gerçek DB'ye / ağa dokunmaz.
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_whatsapp"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1; print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1; print(f"  [KALDI] {mesaj}")


class _FakeResp:
    def __init__(self, status, data):
        self.status_code = status; self._d = data
    def json(self):
        return self._d


class _FakeClient:
    son = {}
    yanit = None
    def __init__(self, *a, **k):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *a):
        return False
    async def post(self, url, json=None, headers=None, **k):
        _FakeClient.son = {"url": url, "json": json, "headers": headers}
        return _FakeClient.yanit or _FakeResp(200, {"messages": [{"id": "wamid.TEST123"}]})


async def run():
    import uuid
    import httpx
    import server
    import core.mesaj_kanallari as mk
    import modules.mesaj_funnel as mf
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    httpx.AsyncClient = _FakeClient  # canlı çağrı yok

    # Kanalı test için AÇ: env fallback (config) sabitlerini modülde doldur — DB boş,
    # whatsapp_config() bu fallback'i okur. Canlı kimlik yok.
    mk.WHATSAPP_TOKEN = "TESTTOKEN"
    mk.WHATSAPP_PHONE_ID = "PHONE123"
    mk.WHATSAPP_BASE_URL = "https://graph.facebook.com/v20.0"
    mk.WHATSAPP_DEFAULT_TEMPLATE = "bilgilendirme"
    mk.WHATSAPP_DEFAULT_LANG = "tr"
    mk.WHATSAPP_WEBHOOK_VERIFY_TOKEN = "verify-secret"

    wa = mk.KANALLAR["whatsapp"]

    # ── 1) Kanal gönderimi (enabled + mock) ──
    _FakeClient.yanit = _FakeResp(200, {"messages": [{"id": "wamid.ABC"}]})
    sonuc = await wa.gonder("0555 111 2233", "Merhaba Ayşe, kur yenileme zamanı.", "pazarlama",
                            meta={"sablon_adi": "yenileme", "dil": "tr", "parametreler": ["Ayşe", "3"]})
    check(sonuc.ok and sonuc.saglayici_id == "wamid.ABC", f"gönderim ok + wamid ({sonuc.saglayici_id})")
    g = _FakeClient.son.get("json", {})
    check(g.get("type") == "template" and g.get("to") == "905551112233",
          f"payload template + uluslararası no ({g.get('to')})")
    tpl = g.get("template", {})
    check(tpl.get("name") == "yenileme" and tpl.get("language", {}).get("code") == "tr",
          "şablon adı + dil doğru")
    params = (tpl.get("components", [{}])[0] or {}).get("parameters", [])
    check([p.get("text") for p in params] == ["Ayşe", "3"], f"değişken parametreler ({[p.get('text') for p in params]})")
    check(_FakeClient.son["headers"].get("Authorization") == "Bearer TESTTOKEN", "Bearer token header'da")

    # ── 2) Hata yanıtı ──
    _FakeClient.yanit = _FakeResp(400, {"error": {"message": "Invalid recipient"}})
    s2 = await wa.gonder("05551112233", "x", "hizmet")
    check(not s2.ok and "Invalid recipient" in (s2.hata or ""), "API hatası yakalandı")
    _FakeClient.yanit = None  # başarıya dön

    # ── 3) Kurulmadı (kimlik boş) → gönderim reddedilir ──
    _tok = mk.WHATSAPP_TOKEN
    mk.WHATSAPP_TOKEN = ""  # kimlik boş → whatsapp_config enabled=False
    s3 = await wa.gonder("05551112233", "x", "hizmet")
    check(not s3.ok and "kurulmadı" in (s3.hata or ""), "kurulmadı → gönderim reddedildi")
    bilgi = await mk.kanallar_bilgi()
    check(any(b["ad"] == "whatsapp" and b["kurulu"] is False for b in bilgi),
          "UI: whatsapp 'kurulmadı' gösterir")
    mk.WHATSAPP_TOKEN = _tok  # tekrar aç

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── 4) Webhook doğrulama ──
        r = await ac.get("/api/funnel/whatsapp/webhook",
                         params={"hub.mode": "subscribe", "hub.verify_token": "verify-secret", "hub.challenge": "42"})
        check(r.status_code == 200 and r.text == "42", f"verify token eşleşince challenge döner ({r.text})")
        r = await ac.get("/api/funnel/whatsapp/webhook",
                         params={"hub.mode": "subscribe", "hub.verify_token": "YANLIS", "hub.challenge": "42"})
        check(r.status_code == 403, "yanlış verify token → 403")

        # ── 5) Durum webhook'u: gönderim kaydı + ilerleme ──
        gid = str(uuid.uuid4())
        await server.db.mesaj_gonderimleri.insert_one({
            "id": gid, "kanal": "whatsapp", "durum": "tamamlandi",
            "alicilar": [
                {"ogrenci_id": "o1", "telefon": "0555", "mesaj": "m", "durum": "gonderildi", "saglayici_id": "wamid.1"},
                {"ogrenci_id": "o2", "telefon": "0556", "mesaj": "m", "durum": "gonderildi", "saglayici_id": "wamid.2"},
            ],
            "ozet": {"toplam": 2, "gonderildi": 2}})

        async def wh(status, wamid, errors=None):
            body = {"entry": [{"changes": [{"value": {"statuses": [
                {"id": wamid, "status": status, **({"errors": errors} if errors else {})}]}}]}]}
            return await ac.post("/api/funnel/whatsapp/webhook", json=body)

        await wh("delivered", "wamid.1")
        await wh("read", "wamid.1")
        await wh("failed", "wamid.2", errors=[{"title": "Undeliverable"}])
        doc = await server.db.mesaj_gonderimleri.find_one({"id": gid})
        d = {a["saglayici_id"]: a for a in doc["alicilar"]}
        check(d["wamid.1"]["durum"] == "okundu", "wamid.1: delivered→read = okundu")
        check(d["wamid.2"]["durum"] == "hata" and "Undeliverable" in (d["wamid.2"].get("hata") or ""), "wamid.2: failed = hata")
        check(doc["ozet"].get("okundu") == 1 and doc["ozet"].get("hata") == 1, "özet sayaçları güncellendi")

        # out-of-order: okundu'dan sonra delivered → geri almaz
        await wh("delivered", "wamid.1")
        doc2 = await server.db.mesaj_gonderimleri.find_one({"id": gid})
        d2 = {a["saglayici_id"]: a for a in doc2["alicilar"]}
        check(d2["wamid.1"]["durum"] == "okundu", "out-of-order delivered okundu'yu geri almadı")

        # ── 6) Funnel'da İYS/onay: WhatsApp da onaysız veliye PAZARLAMA göndermez ──
        admin_id = str(uuid.uuid4())
        await server.db.users.insert_one({"id": admin_id, "ad": "Y", "soyad": "E", "role": "admin"})
        H = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
        sablon = {"id": str(uuid.uuid4()), "ad": "WA Yenileme", "kanal": "whatsapp", "tur": "pazarlama",
                  "metin": "Merhaba {ad}", "durum": "aktif", "wa_sablon_adi": "yenileme", "wa_dil": "tr"}
        await server.db.mesaj_sablonlari.insert_one(dict(sablon))
        sid = str(uuid.uuid4())
        await server.db.students.insert_one({"id": sid, "ad": "Can", "soyad": "Y", "veli_telefon": "05559998877",
                                             "aldigi_egitim": "Genel"})
        # onay YOK → pazarlama gönderilemez
        r = await ac.post("/api/funnel/gonderim", headers=H,
                         json={"segment": "elle", "sablon_id": sablon["id"], "elle_ogrenci_ids": [sid]})
        if r.status_code == 200:
            alicilar = r.json().get("alicilar", [])
            hedef = next((a for a in alicilar if a.get("ogrenci_id") == sid), None)
            check(hedef is not None and hedef["durum"] == "onaysiz",
                  f"onaysız veliye WhatsApp PAZARLAMA 'onaysiz' (gönderilmez) — {hedef and hedef['durum']}")
        else:
            check(False, f"funnel gönderim oluşturulamadı ({r.status_code})")

        # ── 7) Kanal ayarları admin panelinden (DB) — env fallback boşken ──
        mk.WHATSAPP_TOKEN = ""; mk.WHATSAPP_PHONE_ID = ""  # env boş → DB'siz kurulmadı
        acc2 = str(uuid.uuid4())
        await server.db.users.insert_one({"id": acc2, "ad": "M", "soyad": "A", "role": "accountant"})
        Hacc = {"Authorization": f"Bearer {create_access_token({'sub': acc2})}"}
        check((await ac.get("/api/funnel/ayarlar", headers=Hacc)).status_code == 403,
              "kanal ayarları yalnız admin (accountant 403)")
        a0 = (await ac.get("/api/funnel/ayarlar", headers=H)).json()
        check(a0["whatsapp"]["kurulu"] is False and a0["whatsapp"]["token_dolu"] is False,
              "başta whatsapp kurulmadı (env+DB boş)")
        # WhatsApp kimliğini admin panelinden kaydet
        r = await ac.put("/api/funnel/ayarlar/whatsapp", headers=H,
                         json={"token": "DB_TOKEN_XYZ", "phone_id": "PH_DB", "webhook_verify_token": "vt-db"})
        check(r.status_code == 200 and r.json()["whatsapp"]["kurulu"] is True, "kimlik kaydedilince whatsapp kuruldu")
        check("DB_TOKEN_XYZ" not in str(r.json()) and r.json()["whatsapp"]["token_dolu"] is True,
              "token yanıtta MASKELİ (değer sızmıyor, yalnız 'dolu')")
        # DB config kanalı gerçekten açtı mı (kanallar_bilgi + gönderim)
        bilgi2 = await mk.kanallar_bilgi()
        check(any(b["ad"] == "whatsapp" and b["kurulu"] for b in bilgi2), "kanallar_bilgi: whatsapp artık kurulu (DB'den)")
        _FakeClient.yanit = _FakeResp(200, {"messages": [{"id": "wamid.DB"}]})
        sdb = await wa.gonder("05551112233", "test", "hizmet")
        check(sdb.ok and _FakeClient.son["headers"]["Authorization"] == "Bearer DB_TOKEN_XYZ",
              "gönderim DB'deki token'ı kullandı")
        # Boş token ile PUT → mevcut korunur (silinmez)
        await ac.put("/api/funnel/ayarlar/whatsapp", headers=H, json={"phone_id": "PH_DB2"})
        a1 = (await ac.get("/api/funnel/ayarlar", headers=H)).json()
        check(a1["whatsapp"]["token_dolu"] is True and a1["whatsapp"]["phone_id"] == "PH_DB2",
              "boş token gönderilince mevcut token korundu")
        # Webhook verify artık DB token'ıyla çalışır
        rv = await ac.get("/api/funnel/whatsapp/webhook",
                         params={"hub.mode": "subscribe", "hub.verify_token": "vt-db", "hub.challenge": "7"})
        check(rv.status_code == 200 and rv.text == "7", "webhook verify DB'deki token ile doğrular")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
