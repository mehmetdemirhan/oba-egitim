"""Mesaj kanalı soyutlaması — veli mesaj funnel'ı.

MesajKanali arayüzü: `kurulu`, `gonder(telefon, metin)`, `durum_sorgula(id)`.
Uygulamalar:
  - NetgsmSMS       (FAZ 1 — TR SMS, REST). Kimlik env'den (NETGSM_*).
  - WhatsAppCloudAPI(FAZ 2 — şablon gönderimi + durum webhook'u). Kimlik env'den
                    (WHATSAPP_*); boşken kurulu=False (UI'da "kurulmadı").

Kanal kimliği env'de TANIMLI değilse `kurulu=False` → gönderim yapılmaz, UI'da
"kurulmadı" görünür. `KANALLAR` registry'si testte MOCK ile değiştirilebilir
(gerçek SMS gönderilmez).

NOT (Netgsm): REST uç/parametre ayrıntıları varsayımsaldır; gerçek hesap + API
anahtarı geldiğinde `NetgsmSMS._istek` gövdesi teyit edilmeli.
"""
import logging

from core.db import db
from core.config import (
    NETGSM_USERNAME, NETGSM_PASSWORD, NETGSM_HEADER, NETGSM_BASE_URL,
    NETGSM_IYS_FILTER, NETGSM_PARTNER_CODE,
    SMS_BIRIM_UCRET, WHATSAPP_BIRIM_UCRET,
    WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_BASE_URL,
    WHATSAPP_DEFAULT_TEMPLATE, WHATSAPP_DEFAULT_LANG, WHATSAPP_WEBHOOK_VERIFY_TOKEN,
)


# ── Kanal kimlik ayarları: DB (admin panelinden) > env fallback ──
# Kimlik bilgileri db.sistem_ayarlari'da saklanır; admin panelinden düzenlenir.
# env değerleri yalnız DB boşsa kullanılır. Kanal, kimlik DOLUysa "kurulu" olur.
async def sms_config() -> dict:
    d = ((await db.sistem_ayarlari.find_one({"tip": "mesaj_sms"})) or {}).get("degerler", {}) or {}
    username = (d.get("username") or NETGSM_USERNAME or "").strip()
    password = d.get("password") or NETGSM_PASSWORD or ""
    return {
        "username": username, "password": password,
        "header": (d.get("header") or NETGSM_HEADER or "").strip(),
        "base_url": (d.get("base_url") or NETGSM_BASE_URL).rstrip("/"),
        "iys_filter": d.get("iys_filter") if d.get("iys_filter") not in (None, "") else NETGSM_IYS_FILTER,
        "partner_code": (d.get("partner_code") or NETGSM_PARTNER_CODE or "").strip(),
        "enabled": bool(username and password),
    }


async def whatsapp_config() -> dict:
    d = ((await db.sistem_ayarlari.find_one({"tip": "mesaj_whatsapp"})) or {}).get("degerler", {}) or {}
    token = d.get("token") or WHATSAPP_TOKEN or ""
    phone_id = (d.get("phone_id") or WHATSAPP_PHONE_ID or "").strip()
    return {
        "token": token, "phone_id": phone_id,
        "base_url": (d.get("base_url") or WHATSAPP_BASE_URL).rstrip("/"),
        "default_template": (d.get("default_template") or WHATSAPP_DEFAULT_TEMPLATE or "").strip(),
        "default_lang": (d.get("default_lang") or WHATSAPP_DEFAULT_LANG or "tr").strip(),
        "webhook_verify_token": d.get("webhook_verify_token") or WHATSAPP_WEBHOOK_VERIFY_TOKEN or "",
        "enabled": bool(token and phone_id),
    }


class KanalSonuc:
    """Tek gönderimin sonucu."""
    def __init__(self, ok: bool, saglayici_id: str = None, durum: str = None,
                 hata: str = None, ham=None):
        self.ok = ok
        self.saglayici_id = saglayici_id          # kanalın döndürdüğü mesaj id
        self.durum = durum or ("gonderildi" if ok else "hata")
        self.hata = hata
        self.ham = ham

    def to_dict(self):
        return {"ok": self.ok, "saglayici_id": self.saglayici_id,
                "durum": self.durum, "hata": self.hata}


class MesajKanali:
    """Kanal arayüzü. Alt sınıflar `kurulu_mu` (async) + `gonder`."""
    ad = "base"
    birim_ucret = 0.0

    async def kurulu_mu(self) -> bool:
        return False

    async def gonder(self, telefon: str, metin: str, tur: str = "hizmet", meta: dict = None) -> KanalSonuc:
        """meta (opsiyonel): kanala özel ek bilgi (WhatsApp şablon adı/dil/parametreler).
        SMS gibi düz-metin kanalları meta'yı yok sayar."""
        raise NotImplementedError

    async def durum_sorgula(self, saglayici_id: str) -> str:
        return "bilinmiyor"


class NetgsmSMS(MesajKanali):
    """Netgsm SMS (FAZ 1). Kimlik DB/env'den; kurulu değilse gönderim reddedilir."""
    ad = "sms"
    birim_ucret = SMS_BIRIM_UCRET

    async def kurulu_mu(self) -> bool:
        return (await sms_config())["enabled"]

    async def gonder(self, telefon: str, metin: str, tur: str = "hizmet", meta: dict = None) -> KanalSonuc:
        cfg = await sms_config()
        if not cfg["enabled"]:
            return KanalSonuc(False, hata="SMS kanalı kurulmadı (kullanıcı adı/şifre girilmedi)")
        no = tr_gsm_no(telefon)
        if not no:
            # TR-dışı/geçersiz numara — Netgsm SMS gönderemez (hata DEĞİL, ayrı durum)
            return KanalSonuc(False, durum="yurtdisi",
                              hata="TR-dışı/geçersiz numara — Netgsm SMS gönderemez")
        try:
            return await self._istek(cfg, no, metin, tur)
        except Exception as ex:
            logging.warning(f"[netgsm] gönderim hatası: {ex}")
            return KanalSonuc(False, hata=str(ex))

    async def _istek(self, cfg: dict, no: str, metin: str, tur: str) -> KanalSonuc:
        # POST /sms/rest/v2/send, HTTP Basic (user:pass). Başarı: JSON code=="00", jobid.
        import httpx
        url = f"{cfg['base_url']}/sms/rest/v2/send"
        govde = {
            "msgheader": cfg["header"],
            "encoding": "TR",                       # Türkçe karakter desteği
            "messages": [{"msg": metin, "no": no}],  # no = 5XXXXXXXXX (0/+90 yok)
        }
        if tur == "pazarlama" and cfg["iys_filter"]:
            govde["iysfilter"] = cfg["iys_filter"]   # İYS 2. katman (yalnız pazarlama)
        if cfg["partner_code"]:
            govde["partnercode"] = cfg["partner_code"]
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(url, json=govde, auth=(cfg["username"], cfg["password"]),
                             headers={"Content-Type": "application/json"})
        try:
            data = r.json()
        except Exception:
            data = {}
        code = str(data.get("code", ""))
        ok = code == "00"
        return KanalSonuc(
            ok, saglayici_id=data.get("jobid"),
            hata=None if ok else (data.get("description") or f"Netgsm kod {code or r.status_code}"),
            ham=data)


class WhatsAppCloudAPI(MesajKanali):
    """WhatsApp Cloud API (FAZ 2). ONAYLI ŞABLON mesajı gönderir
    (graph.facebook.com/{phone_id}/messages, type=template + body parametreleri).
    Durum güncellemeleri (iletildi/okundu/hata) Meta webhook'undan gelir.
    Kimlik env'de yoksa kurulu=False → gönderim reddedilir, UI'da 'kurulmadı'."""
    ad = "whatsapp"
    birim_ucret = WHATSAPP_BIRIM_UCRET

    async def kurulu_mu(self) -> bool:
        return (await whatsapp_config())["enabled"]

    async def gonder(self, telefon: str, metin: str, tur: str = "hizmet", meta: dict = None) -> KanalSonuc:
        cfg = await whatsapp_config()
        if not cfg["enabled"]:
            return KanalSonuc(False, hata="WhatsApp kanalı kurulmadı (token/telefon id girilmedi)")
        no = wa_no(telefon)
        if not no:
            return KanalSonuc(False, durum="gecersiz", hata="Geçersiz telefon numarası")
        meta = meta or {}
        sablon = meta.get("sablon_adi") or cfg["default_template"]
        dil = meta.get("dil") or cfg["default_lang"]
        # Değişken parametreler: verilmezse tüm metin tek {{1}} body parametresi olur.
        parametreler = meta.get("parametreler")
        if not parametreler:
            parametreler = [metin]
        try:
            return await self._istek(cfg, no, sablon, dil, parametreler)
        except Exception as ex:
            logging.warning(f"[whatsapp] gönderim hatası: {ex}")
            return KanalSonuc(False, hata=str(ex))

    async def _istek(self, cfg: dict, no: str, sablon: str, dil: str, parametreler: list) -> KanalSonuc:
        """POST /{phone_id}/messages — type=template. Başarı: messages[0].id (wamid)."""
        import httpx
        url = f"{cfg['base_url']}/{cfg['phone_id']}/messages"
        components = []
        if parametreler:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(p)} for p in parametreler],
            })
        govde = {
            "messaging_product": "whatsapp",
            "to": no,
            "type": "template",
            "template": {"name": sablon, "language": {"code": dil}, "components": components},
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(url, json=govde,
                             headers={"Authorization": f"Bearer {cfg['token']}",
                                      "Content-Type": "application/json"})
        try:
            data = r.json()
        except Exception:
            data = {}
        mesajlar = data.get("messages") or []
        if r.status_code < 300 and mesajlar:
            return KanalSonuc(True, saglayici_id=mesajlar[0].get("id"), durum="gonderildi", ham=data)
        hata = ((data.get("error") or {}).get("message")) or f"WhatsApp HTTP {r.status_code}"
        return KanalSonuc(False, hata=hata, ham=data)


# WhatsApp webhook durum kodu → iç durum (ilerleme sırası: gonderildi<iletildi<okundu)
WHATSAPP_DURUM_ESLE = {"sent": "gonderildi", "delivered": "iletildi", "read": "okundu", "failed": "hata"}
_DURUM_RANK = {"gonderildi": 1, "iletildi": 2, "okundu": 3}


def whatsapp_durum_esle(wa_status: str) -> str:
    return WHATSAPP_DURUM_ESLE.get(str(wa_status or "").lower(), "")


def _tr_telefon(tel: str) -> str:
    """Rakamları al, 0/90/+90 önekini soy → gövde (onay anahtarı/dedup için)."""
    rak = "".join(ch for ch in str(tel or "") if ch.isdigit())
    if rak.startswith("90"):
        rak = rak[2:]
    elif rak.startswith("0"):
        rak = rak[1:]
    return rak


def tr_gsm_no(tel: str):
    """Geçerli TR cep no ise '5XXXXXXXXX' (10 hane, 5 ile başlar) döner; değilse None.
    TR-dışı (ABD/Almanya vb.) veya geçersiz → None (Netgsm SMS gönderemez)."""
    rak = _tr_telefon(tel)
    return rak if (len(rak) == 10 and rak.startswith("5")) else None


def wa_no(tel: str):
    """WhatsApp için ülke-kodlu uluslararası numara (+ ve boşluk yok). TR cep →
    '905XXXXXXXXX'. Zaten ülke kodlu görünen numaralar (11-15 hane) olduğu gibi
    döner. Geçersiz → None. (WhatsApp TR-dışını da gönderebilir; SMS'ten farkı bu.)"""
    tr = tr_gsm_no(tel)
    if tr:
        return "90" + tr
    rak = "".join(ch for ch in str(tel or "") if ch.isdigit())
    if rak.startswith("0"):
        rak = rak[1:]
    return rak if 10 <= len(rak) <= 15 else None


def sms_parca_sayisi(metin: str) -> int:
    """Netgsm 'TR' encoding'de mesaj kaç SMS'e bölünür. Türkçe/unicode karakter varsa
    segment kısalır (70/67); yoksa GSM (160/153). Maliyet tahmini için."""
    import math
    s = str(metin or "")
    turkce = set("çğıöşüÇĞİÖŞÜ")
    if any((ch in turkce) or (ord(ch) > 127) for ch in s):
        tek, coklu = 70, 67
    else:
        tek, coklu = 160, 153
    n = len(s)
    return 1 if n <= tek else math.ceil(n / coklu)


# Kanal registry — testte MOCK ile değiştirilebilir (gerçek gönderim yapılmaz).
KANALLAR = {
    "sms": NetgsmSMS(),
    "whatsapp": WhatsAppCloudAPI(),
}


def kanal_al(ad: str) -> MesajKanali:
    return KANALLAR.get(ad)


async def kanallar_bilgi() -> list:
    """UI için: hangi kanal kurulu/kurulmadı (kimlik DB/env'den, çalışma-zamanı)."""
    return [{"ad": k.ad, "kurulu": await k.kurulu_mu(), "birim_ucret": k.birim_ucret}
            for k in KANALLAR.values()]
