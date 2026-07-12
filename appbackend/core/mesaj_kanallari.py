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

    async def gonder(self, telefon: str, metin: str) -> KanalSonuc:
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

    async def gonder(self, telefon: str, metin: str) -> KanalSonuc:
        if not self.kurulu:
            return KanalSonuc(False, hata="SMS kanalı kurulmadı (NETGSM_* env eksik)")
        try:
            return await self._istek(telefon, metin)
        except Exception as ex:
            logging.warning(f"[netgsm] gönderim hatası: {ex}")
            return KanalSonuc(False, hata=str(ex))

    async def _istek(self, telefon: str, metin: str) -> KanalSonuc:
        # Netgsm REST v2 (varsayımsal — hesap gelince teyit edilecek).
        import httpx
        url = f"{NETGSM_BASE_URL}/sms/rest/v2/send"
        govde = {
            "msgheader": NETGSM_HEADER,
            "messages": [{"msg": metin, "no": _tr_telefon(telefon)}],
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(url, json=govde, auth=(NETGSM_USERNAME, NETGSM_PASSWORD))
        ok = r.status_code == 200 and str(r.text)[:2] in ("00", "01", "02")
        # Netgsm başarı kodları 00/01/02 ile başlar; jobid döner.
        jobid = r.text.strip().split()[-1] if ok else None
        return KanalSonuc(ok, saglayici_id=jobid,
                          hata=None if ok else f"Netgsm yanıtı: {r.text[:120]}", ham=r.text[:200])


class WhatsAppCloudAPI(MesajKanali):
    """WhatsApp Cloud API (FAZ 2 — İSKELET). Henüz aktif değil; şablon mesaj +
    webhook durum takibi sonraki fazda. Kurulu olsa bile gönderim reddeder."""
    ad = "whatsapp"
    birim_ucret = WHATSAPP_BIRIM_UCRET

    @property
    def kurulu(self) -> bool:
        return WHATSAPP_ENABLED

    async def gonder(self, telefon: str, metin: str) -> KanalSonuc:
        # FAZ 2: graph.facebook.com/{phone_id}/messages şablon gönderimi burada olacak.
        return KanalSonuc(False, hata="WhatsApp kanalı Faz 2'de aktifleşecek (iskelet)")


def _tr_telefon(tel: str) -> str:
    """TR telefonu sadeleştir: rakamları al, 0/90 önekini normalize et → 5XXXXXXXXX."""
    rak = "".join(ch for ch in str(tel or "") if ch.isdigit())
    if rak.startswith("90"):
        rak = rak[2:]
    if rak.startswith("0"):
        rak = rak[1:]
    return rak


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
