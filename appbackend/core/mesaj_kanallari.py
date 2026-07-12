"""Mesaj kanalı soyutlaması — veli mesaj funnel'ı.

MesajKanali arayüzü: `kurulu`, `gonder(telefon, metin)`, `durum_sorgula(id)`.
Uygulamalar:
  - NetgsmSMS       (FAZ 1 — TR SMS, REST). Kimlik env'den (NETGSM_*).
  - WhatsAppCloudAPI(FAZ 2 — iskelet; henüz aktif değil).

Kanal kimliği env'de TANIMLI değilse `kurulu=False` → gönderim yapılmaz, UI'da
"kurulmadı" görünür. `KANALLAR` registry'si testte MOCK ile değiştirilebilir
(gerçek SMS gönderilmez).

NOT (Netgsm): REST uç/parametre ayrıntıları varsayımsaldır; gerçek hesap + API
anahtarı geldiğinde `NetgsmSMS._istek` gövdesi teyit edilmeli.
"""
import logging

from core.config import (
    NETGSM_USERNAME, NETGSM_PASSWORD, NETGSM_HEADER, NETGSM_BASE_URL, NETGSM_ENABLED,
    NETGSM_IYS_FILTER, NETGSM_PARTNER_CODE,
    SMS_BIRIM_UCRET, WHATSAPP_ENABLED, WHATSAPP_BIRIM_UCRET,
)


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
    """Kanal arayüzü. Alt sınıflar `kurulu` + `gonder` (+ opsiyonel durum_sorgula)."""
    ad = "base"
    birim_ucret = 0.0

    @property
    def kurulu(self) -> bool:
        return False

    async def gonder(self, telefon: str, metin: str, tur: str = "hizmet") -> KanalSonuc:
        raise NotImplementedError

    async def durum_sorgula(self, saglayici_id: str) -> str:
        return "bilinmiyor"

    def bilgi(self) -> dict:
        return {"ad": self.ad, "kurulu": self.kurulu, "birim_ucret": self.birim_ucret}


class NetgsmSMS(MesajKanali):
    """Netgsm SMS (FAZ 1). Kurulu değilse gönderim reddedilir."""
    ad = "sms"
    birim_ucret = SMS_BIRIM_UCRET

    @property
    def kurulu(self) -> bool:
        return NETGSM_ENABLED

    async def gonder(self, telefon: str, metin: str, tur: str = "hizmet") -> KanalSonuc:
        if not self.kurulu:
            return KanalSonuc(False, hata="SMS kanalı kurulmadı (NETGSM_* env eksik)")
        no = tr_gsm_no(telefon)
        if not no:
            # TR-dışı/geçersiz numara — Netgsm SMS gönderemez (hata DEĞİL, ayrı durum)
            return KanalSonuc(False, durum="yurtdisi",
                              hata="TR-dışı/geçersiz numara — Netgsm SMS gönderemez")
        try:
            return await self._istek(no, metin, tur)
        except Exception as ex:
            logging.warning(f"[netgsm] gönderim hatası: {ex}")
            return KanalSonuc(False, hata=str(ex))

    async def _istek(self, no: str, metin: str, tur: str) -> KanalSonuc:
        # Resmî SDK (@netgsm/sms — src/netgsm.ts): POST /sms/rest/v2/send, HTTP Basic
        # (base64 user:pass), gövde {msgheader, encoding, messages:[{msg,no}],
        # iysfilter?, partnercode?}. Başarı: yanıt JSON code=="00", jobid döner.
        import httpx
        url = f"{NETGSM_BASE_URL}/sms/rest/v2/send"
        govde = {
            "msgheader": NETGSM_HEADER,
            "encoding": "TR",                       # Türkçe karakter desteği
            "messages": [{"msg": metin, "no": no}],  # no = 5XXXXXXXXX (0/+90 yok)
        }
        if tur == "pazarlama" and NETGSM_IYS_FILTER:
            govde["iysfilter"] = NETGSM_IYS_FILTER   # İYS 2. katman (yalnız pazarlama)
        if NETGSM_PARTNER_CODE:
            govde["partnercode"] = NETGSM_PARTNER_CODE
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(url, json=govde, auth=(NETGSM_USERNAME, NETGSM_PASSWORD),
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
    """WhatsApp Cloud API (FAZ 2 — İSKELET). Henüz aktif değil; şablon mesaj +
    webhook durum takibi sonraki fazda. Kurulu olsa bile gönderim reddeder."""
    ad = "whatsapp"
    birim_ucret = WHATSAPP_BIRIM_UCRET

    @property
    def kurulu(self) -> bool:
        return WHATSAPP_ENABLED

    async def gonder(self, telefon: str, metin: str, tur: str = "hizmet") -> KanalSonuc:
        # FAZ 2: graph.facebook.com/{phone_id}/messages şablon gönderimi burada olacak.
        return KanalSonuc(False, hata="WhatsApp kanalı Faz 2'de aktifleşecek (iskelet)")


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


def kanallar_bilgi() -> list:
    """UI için: hangi kanal kurulu/kurulmadı."""
    return [k.bilgi() for k in KANALLAR.values()]
