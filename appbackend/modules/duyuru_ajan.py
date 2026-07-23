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


async def _son_sha() -> str | None:
    doc = await db.sistem_ayarlari.find_one({"tip": "changelog_son_sha"})
    return (doc or {}).get("son_sha")


async def _commitleri_cek(son_sha: str | None, limit: int = 40) -> list:
    if not (GITHUB_REPO_OWNER and GITHUB_REPO_NAME):
        return []
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    base = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
    out = []
    async with httpx.AsyncClient(timeout=20.0) as c:
        r = await c.get(f"{base}/commits", params={"per_page": limit, "sha": "production"}, headers=headers)
        if r.status_code != 200:
            r = await c.get(f"{base}/commits", params={"per_page": limit}, headers=headers)
        if r.status_code == 200:
            for it in r.json():
                sha = it.get("sha")
                if son_sha and sha == son_sha:
                    break   # buradan öncesi zaten taranmış
                msg = (it.get("commit", {}).get("message", "") or "").split("\n")[0]
                out.append({"sha": sha, "mesaj": msg,
                            "tarih": it.get("commit", {}).get("committer", {}).get("date", "")})
    return out


def _teknik_mi(mesaj: str) -> bool:
    m = (mesaj or "").lower()
    return any(iz in m for iz in _TEKNIK_IZ)


async def changelog_tara() -> dict:
    """Commit'leri tara → teknik olmayanları AI ile changelog'a çevir → onay bekleyen taslak yaz."""
    son = await _son_sha()
    commitler = await _commitleri_cek(son)
    en_yeni = commitler[0]["sha"] if commitler else son
    adaylar = [c for c in commitler if not _teknik_mi(c["mesaj"])]
    olusan = 0
    if adaylar:
        liste = "\n".join(f"- {c['mesaj']}" for c in adaylar[:25])
        sistem = (
            "Sen bir eğitim yazılımının changelog editörüsün. Verilen git commit mesajlarından "
            "SADECE son kullanıcıya (öğretmen/veli/öğrenci/yönetici) GÖRÜNÜR, anlamlı yenilik, "
            "iyileştirme veya hata düzeltmelerini seç. Salt teknik/iç/refactor değişiklikleri ATLA. "
            "Her seçtiğin için sade, anlaşılır Türkçe bir başlık (kullanıcı faydası odaklı, örn. "
            "'Artık ...') ve 1-2 cümlelik açıklama yaz. Ham commit dilini kullanma. "
            'YALNIZ JSON döndür: {"girisler":[{"baslik":"...","icerik":"..."}]}. Uygun yoksa {"girisler":[]}.'
        )
        r = await call_claude(sistem, f"Commit mesajları:\n{liste}", ozellik="changelog_ajan", max_tokens=1500)
        girisler = (r.get("parsed") or {}).get("girisler") or []
        for g in girisler:
            baslik = (g.get("baslik") or "").strip()
            icerik = (g.get("icerik") or "").strip()
            if not (baslik or icerik):
                continue
            await db.duyuru_taslak.insert_one({
                "id": str(uuid.uuid4()), "baslik": baslik[:200], "icerik": icerik[:1200],
                "durum": "bekliyor", "kaynak": "ajan", "olusturma": iso(),
                "tarih": simdi().date().isoformat(),
            })
            olusan += 1
    if en_yeni:
        await db.sistem_ayarlari.update_one(
            {"tip": "changelog_son_sha"},
            {"$set": {"tip": "changelog_son_sha", "son_sha": en_yeni, "zaman": iso()}}, upsert=True)
    return {"taranan_commit": len(commitler), "aday": len(adaylar), "olusan_taslak": olusan}


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
