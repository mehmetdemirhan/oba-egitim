"""Yeni Ne Var otomasyon ajanı.

Her 24 saatte bir (mevcut throttle_gunluk mekanizması + token'lı cron ucu) production
git geçmişini tarar, SALT TEKNİK commit'leri ayıklar, kullanıcıya görünür yenilik/
düzeltmeleri AI ile sade Türkçe changelog'a çevirir ve db.duyuru_taslak'a ONAY BEKLEYEN
taslak olarak yazar. Admin onaylayınca db.duyurular'a (Yeni Ne Var) yayınlanır — mevcut
onay-kuyruğu deseniyle (metin öneri kuyruğu) tutarlı. Yeni bir sistem icat edilmez:
- Zamanlama: core.temizlik.throttle_gunluk (analiz/TIMI temizliğiyle aynı)
- Yayın hedefi: db.duyurular (mevcut duyuru.py)
- Git erişimi: GitHub REST API (yedekleme.py deseni; yerel git yok)
"""
import asyncio
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Body

from core.db import db
from core.auth import require_role, UserRole, get_current_user
from core.zaman import iso, simdi
from core.config import GITHUB_REPO_OWNER, GITHUB_REPO_NAME, GITHUB_TOKEN, PUSH_CRON_TOKEN
from core.ai import call_claude
from core.temizlik import throttle_gunluk
from core.audit import islem_kaydet

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN)

# Salt teknik / kullanıcının fark etmeyeceği commit'ler — changelog'a GİRMEZ
_TEKNIK_IZ = [
    "merge", "registry", "smoke", "regres", "refactor", "test ", "tests", "chore", "wip",
    "typo", "lint", "format", "gitignore", "bump", "revert", "rebase", "cleanup", "route_snapshot",
    "route snapshot", "ci:", "co-authored", "backfill", "migration", "migrate", "import düzelt",
]


# Repo bilgisi env'de yoksa BİLİNEN public repo'ya düş — public repo token'sız da okunur.
# (Eski hata: env boşken _commitleri_cek [] dönüyordu → tarama daima 0 sonuç.)
_REPO_OWNER = GITHUB_REPO_OWNER or "mehmetdemirhan"
_REPO_NAME = GITHUB_REPO_NAME or "oba-egitim"


async def _commitleri_cek(limit: int = 40):
    """Son N production commit'ini çeker → (liste, hata). Hata None ise başarılı."""
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    base = f"https://api.github.com/repos/{_REPO_OWNER}/{_REPO_NAME}"
    out = []
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(f"{base}/commits", params={"per_page": limit, "sha": "production"}, headers=headers)
            if r.status_code != 200:   # production yoksa varsayılan dala düş
                r = await c.get(f"{base}/commits", params={"per_page": limit}, headers=headers)
            if r.status_code != 200:
                return [], f"GitHub {r.status_code}"
            for it in r.json():
                msg = (it.get("commit", {}).get("message", "") or "").split("\n")[0]
                out.append({"sha": it.get("sha"), "mesaj": msg,
                            "tarih": it.get("commit", {}).get("committer", {}).get("date", "")})
    except Exception as e:
        return [], f"istisna: {str(e)[:120]}"
    return out, None


def _teknik_mi(mesaj: str) -> bool:
    """SADECE ilk satıra bakar (Co-Authored-By vb. alt satırlar sayılmaz)."""
    m = (mesaj or "").lower()
    return any(iz in m for iz in _TEKNIK_IZ)


async def _islenen_shalar() -> set:
    """Baseline: daha önce taslağa dönüştürülmüş/atlanmış (yayınlanmış dahil) commit SHA'ları.
    Fragile 'son_sha pointer' YERİNE — başarısız taramada commit kaybolmaz, tekrar denenir."""
    seen = set()
    async for d in db.changelog_islenen.find({}, {"_id": 0, "sha": 1}):
        if d.get("sha"):
            seen.add(d["sha"])
    # Yayınlanmış/bekleyen taslakların kaynak SHA'ları da baseline (çift teklif olmasın)
    async for t in db.duyuru_taslak.find({"kaynak_shalar": {"$exists": True}}, {"_id": 0, "kaynak_shalar": 1}):
        for s in (t.get("kaynak_shalar") or []):
            seen.add(s)
    return seen


_AI_SISTEM = (
    "Sen bir eğitim yazılımının changelog editörüsün. Verilen git commit mesajlarından "
    "SADECE son kullanıcıya (öğretmen/veli/öğrenci/yönetici) GÖRÜNÜR yenilik, iyileştirme "
    "veya hata düzeltmelerini seç. Salt teknik/iç/refactor değişiklikleri ATLA. Her seçtiğin "
    "için sade Türkçe bir başlık (kullanıcı faydası odaklı, örn. 'Artık ...') ve 1-2 cümlelik "
    "açıklama yaz. Ham commit dilini kullanma. Cömert davran — şüphedeysen DAHİL ET. "
    'YALNIZ JSON döndür: {"girisler":[{"baslik":"...","icerik":"..."}]}.'
)


async def _ai_changelog(adaylar: list):
    """(girisler | None, ai_durum). None → AI kullanılamadı (fallback gerekir)."""
    liste = "\n".join(f"- {c['mesaj']}" for c in adaylar)
    r = await call_claude(_AI_SISTEM, f"Commit mesajları:\n{liste}", ozellik="changelog_ajan", max_tokens=1800)
    if r.get("error"):
        return None, f"AI hata: {str(r['error'])[:80]}"
    parsed = r.get("parsed")
    if not isinstance(parsed, dict):
        return None, "AI yanıtı JSON değil"
    return (parsed.get("girisler") or []), "ok"


async def changelog_tara() -> dict:
    """Production git geçmişini tara → teknik-dışı YENİ commit'leri changelog taslağına çevir.
    Baseline = işlenmiş/yayınlanmış SHA'lar (değişmeyen pointer değil). AI yoksa ham fallback.
    Ayrıntılı tanı döner (neyin neden elendiği görünsün)."""
    commitler, hata = await _commitleri_cek()
    tani = {"taranan_commit": len(commitler), "onceden_islenmis": 0, "teknik_elenen": 0,
            "teknik_ornek": [], "aday": 0, "aday_ornek": [], "ai_durum": "-", "olusan_taslak": 0,
            "hata": hata, "repo": f"{_REPO_OWNER}/{_REPO_NAME}"}
    if hata:
        tani["not"] = f"GitHub'dan commit çekilemedi ({hata})"
        return tani
    if not commitler:
        tani["not"] = "Hiç commit dönmedi"
        return tani

    islenen = await _islenen_shalar()
    yeni = [c for c in commitler if c["sha"] not in islenen]
    tani["onceden_islenmis"] = len(commitler) - len(yeni)

    teknik = [c for c in yeni if _teknik_mi(c["mesaj"])]
    adaylar = [c for c in yeni if not _teknik_mi(c["mesaj"])]
    tani["teknik_elenen"] = len(teknik)
    tani["teknik_ornek"] = [c["mesaj"][:70] for c in teknik[:5]]
    tani["aday"] = len(adaylar)
    tani["aday_ornek"] = [c["mesaj"][:70] for c in adaylar[:8]]

    # Teknik olanları kalıcı işaretle (bir daha değerlendirme)
    for c in teknik:
        await db.changelog_islenen.update_one({"sha": c["sha"]},
            {"$set": {"sha": c["sha"], "tur": "teknik", "tarih": iso()}}, upsert=True)

    if not adaylar:
        tani["not"] = "Yeni (teknik olmayan) commit yok"
        return tani

    girisler, ai_durum = await _ai_changelog(adaylar[:25])
    if girisler is None:   # AI kullanılamadı → ham commit'ten taslak (admin düzenler)
        girisler = [{"baslik": c["mesaj"][:140],
                     "icerik": "(Otomatik taslak — commit mesajından üretildi; lütfen kullanıcı-dostu hale getirin.)"}
                    for c in adaylar[:12]]
        ai_durum = ai_durum + " → ham commit fallback"
    tani["ai_durum"] = ai_durum

    kaynak_shalar = [c["sha"] for c in adaylar]
    for g in girisler:
        baslik = (g.get("baslik") or "").strip()
        icerik = (g.get("icerik") or "").strip()
        if not (baslik or icerik):
            continue
        await db.duyuru_taslak.insert_one({
            "id": str(uuid.uuid4()), "baslik": baslik[:200], "icerik": icerik[:1200],
            "durum": "bekliyor", "kaynak": "ajan", "kaynak_shalar": kaynak_shalar,
            "olusturma": iso(), "tarih": simdi().date().isoformat(),
        })
        tani["olusan_taslak"] += 1

    # Aday commit'leri işlenmiş işaretle (tekrar önerilmez)
    for c in adaylar:
        await db.changelog_islenen.update_one({"sha": c["sha"]},
            {"$set": {"sha": c["sha"], "tur": "aday", "tarih": iso()}}, upsert=True)

    return tani


async def _arka_tara():
    try:
        await changelog_tara()
    except Exception:
        pass


async def _gunluk_tetikle():
    """24 saatte bir arka planda tara (throttle en fazla 1/gün) — read endpoint'ten çağrılır.
    throttle_gunluk fn'i await ettiği için burada SADECE arka plan görevi planlanır (bloklamaz)."""
    async def _planla():
        asyncio.create_task(_arka_tara())   # fire-and-forget; GET beklemez
    await throttle_gunluk("changelog_ajan_gunluk", _planla)


# ── Admin: taslak kuyruğu (onay bekleyen) ──
@router.get("/duyuru-taslak")
async def taslaklar(current_user=Depends(_ADMIN)):
    """Onay bekleyen changelog taslakları. Ayrıca günlük taramayı (throttle) tetikler."""
    try:
        await _gunluk_tetikle()
    except Exception:
        pass
    liste = await db.duyuru_taslak.find({"durum": "bekliyor"}, {"_id": 0}).sort("olusturma", -1).to_list(length=200)
    return {"taslaklar": liste, "toplam": len(liste)}


@router.post("/duyuru-taslak/tara")
async def elle_tara(current_user=Depends(_ADMIN)):
    """Admin: 24 saatlik döngüyü beklemeden 'şimdi tara'."""
    sonuc = await changelog_tara()
    await islem_kaydet(current_user, "duyuru_ajan", "elle_tara", ekstra=sonuc)
    return {"ok": True, **sonuc}


@router.put("/duyuru-taslak/{taslak_id}")
async def taslak_duzenle(taslak_id: str, data: dict = Body(...), current_user=Depends(_ADMIN)):
    """Admin taslağı yayından önce düzenler."""
    guncelle = {}
    if "baslik" in data:
        guncelle["baslik"] = str(data["baslik"])[:200]
    if "icerik" in data:
        guncelle["icerik"] = str(data["icerik"])[:1200]
    if not guncelle:
        raise HTTPException(status_code=422, detail="Güncellenecek alan yok")
    r = await db.duyuru_taslak.update_one({"id": taslak_id}, {"$set": guncelle})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Taslak bulunamadı")
    return {"ok": True}


@router.post("/duyuru-taslak/{taslak_id}/onayla")
async def taslak_onayla(taslak_id: str, data: dict = Body(default={}), current_user=Depends(_ADMIN)):
    """Admin onayı → taslak 'Yeni Ne Var' (db.duyurular) bölümünde yayınlanır."""
    t = await db.duyuru_taslak.find_one({"id": taslak_id})
    if not t:
        raise HTTPException(status_code=404, detail="Taslak bulunamadı")
    if t.get("durum") != "bekliyor":
        raise HTTPException(status_code=400, detail="Bu taslak zaten sonuçlandı")
    baslik = str(data.get("baslik", t.get("baslik", "")))[:200]
    icerik = str(data.get("icerik", t.get("icerik", "")))[:1200]
    roller = data.get("roller") or ["herkes"]
    son = await db.duyurular.find_one(sort=[("sira", -1)])
    yeni_sira = int((son or {}).get("sira", 0)) + 1
    await db.duyurular.insert_one({
        "id": str(uuid.uuid4()), "baslik": baslik, "icerik": icerik, "roller": roller,
        "aktif": True, "sira": yeni_sira, "tarih": simdi().date().isoformat(), "olusturma": iso(),
    })
    await db.duyuru_taslak.update_one({"id": taslak_id},
        {"$set": {"durum": "onaylandi", "karar_tarihi": iso(), "karar_veren": current_user.get("id")}})
    await islem_kaydet(current_user, "duyuru_ajan", "onayla", hedef_tip="duyuru_taslak", hedef_id=taslak_id)
    return {"ok": True, "yayinlandi": True}


@router.post("/duyuru-taslak/{taslak_id}/reddet")
async def taslak_reddet(taslak_id: str, current_user=Depends(_ADMIN)):
    r = await db.duyuru_taslak.update_one({"id": taslak_id, "durum": "bekliyor"},
        {"$set": {"durum": "reddedildi", "karar_tarihi": iso(), "karar_veren": current_user.get("id")}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Taslak bulunamadı veya zaten sonuçlandı")
    await islem_kaydet(current_user, "duyuru_ajan", "reddet", hedef_tip="duyuru_taslak", hedef_id=taslak_id)
    return {"ok": True}


# ── Token'lı cron ucu (harici zamanlayıcı; temizlik uçlarıyla aynı desen) ──
@router.post("/duyuru-taslak/gunluk-tara")
async def gunluk_tara_cron(anahtar: str = ""):
    if not PUSH_CRON_TOKEN or anahtar != PUSH_CRON_TOKEN:
        raise HTTPException(status_code=403, detail="Geçersiz anahtar")
    return await changelog_tara()
