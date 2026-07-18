"""Ayaz v1.5 (GÜVENLİ) — Doğal dil → kod taslağı + risk analizi + statik güvenlik + insan onaylı deploy.

TASARIM İLKESİ (kasıtlı sınırlar):
- AI'nin ürettiği kod SÜREÇ İÇİNDE exec/eval EDİLMEZ. (Kara-liste tabanlı AST sandbox aşılabilir;
  güvenilmez kodu canlı süreçte çalıştırmak RCE'dir.) Bunun yerine yalnız STATİK tarama yapılır:
  core.patch_security.scan_python_source (projenin gerçek AST tarayıcısı) + compile denemesi.
- OTOMATİK canlıya alma YOKTUR. Yönetici paneldeki GERÇEK kodu görür; canlıya alma ayrı, admin
  onaylı bir adımdır ve MEVCUT patch_manager.install_patch pipeline'ından geçer (tekrar AST taraması
  + path/core koruması + sürüm arşivi + rollback). Yani "admin modül yükler" ile aynı risk zarfı.
- Böylece 570 route / Faz kararlılığı ve KVKK güvenceleri korunur.

Yollar /ai/ayaz/* — ai_ceo paketine dahildir (registry.json 'ai_ceo' yükler)."""
import hashlib
import io
import json
import re
import uuid
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Body

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso
from core.audit import islem_kaydet
from core.ai import call_claude
from core import patch_security, patch_manager
from .ayaz_semalar import AyazTaskRequest, AyazTaskResponse

router = APIRouter()
_ISTEYEN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
_ADMIN = require_role(UserRole.ADMIN)

_SISTEM_PROMPT = (
    "Sen OBA Eğitim projesinin kod asistanı 'Ayaz'sın. Yöneticinin doğal dil isteğini alıp "
    "SELF-CONTAINED bir FastAPI backend modülü üretirsin. KATI KURALLAR:\n"
    "- Yalnız SALT-OKUNUR / raporlama endpoint'leri üret. VERİ SİLME/DEĞİŞTİRME (delete/drop/update/"
    "insert) ÜRETME.\n"
    "- Sadece şu katmanları içe aktar: fastapi, core.db (db), core.auth (require_role/UserRole), "
    "core.zaman. os/sys/subprocess/socket/requests/httpx/eval/exec/__import__ KULLANMA.\n"
    "- Modül `router = APIRouter()` ihraç etsin; endpoint'ler `/api` altında anlamlı yollar tanımlasın.\n"
    "- Yorumlar Türkçe. Tarih üretimi yalnız core.zaman ile.\n"
    "YALNIZCA geçerli JSON döndür (markdown/açıklama yok). Şema:\n"
    '{"kod": "<python>", "aciklama": "<kısa>", "degisen_dosyalar": ["modules/..."], '
    '"risk_seviyesi": "dusuk|orta|yuksek", "etki_alani": "<alan>", "tahmini_sure_dk": 15}'
)


def _parse_ai(res) -> dict | None:
    if not isinstance(res, dict) or res.get("error"):
        return None
    parsed = res.get("parsed")
    if isinstance(parsed, dict):
        return parsed
    txt = res.get("text") or ""
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _modul_adi(task_id: str) -> str:
    ham = "ayaz_" + re.sub(r"[^a-zA-Z0-9_]", "", task_id.replace("task_", ""))
    return ham[:40] or "ayaz_modul"


# ─────────────── Kriptografik hash-chain append-only audit trail ───────────────
# Her Ayaz olayı sha256 ile bir öncekine zincirlenir; bir kayıt sonradan değişirse zincir kırılır.
_GENESIS = "0" * 64


def _kanonik(metadata: dict) -> str:
    try:
        return json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return "{}"


def _olay_hash(task_id, seq, prev_hash, actor, action, ts, metadata) -> str:
    ham = f"{task_id}|{seq}|{prev_hash}|{actor}|{action}|{ts}|{_kanonik(metadata)}"
    return hashlib.sha256(ham.encode("utf-8")).hexdigest()


async def _audit_ekle(task_id: str, actor: str, action: str, metadata: dict = None) -> str:
    """Görevin audit zincirine yeni olay ekler (append-only). Dönen: event_hash."""
    son = await db.ayaz_audit.find_one({"task_id": task_id}, sort=[("seq", -1)])
    seq = (son["seq"] + 1) if son else 0
    prev = son["event_hash"] if son else _GENESIS
    ts = iso()
    h = _olay_hash(task_id, seq, prev, actor or "sistem", action, ts, metadata or {})
    await db.ayaz_audit.insert_one({
        "event_id": str(uuid.uuid4()), "task_id": task_id, "seq": seq, "previous_hash": prev,
        "event_hash": h, "actor": actor or "sistem", "action": action, "timestamp": ts, "metadata": metadata or {}})
    return h


async def _audit_dogrula(task_id: str) -> dict:
    """Zinciri baştan yeniden hesaplayıp kurcalanmadığını ispatlar."""
    olaylar = await db.ayaz_audit.find({"task_id": task_id}, {"_id": 0}).sort("seq", 1).to_list(length=1000)
    prev = _GENESIS
    for i, e in enumerate(olaylar):
        if e.get("seq") != i:
            return {"gecerli": False, "kirilma_seq": e.get("seq"), "neden": "seq boşluğu/atlaması", "olay_sayisi": len(olaylar)}
        if e.get("previous_hash") != prev:
            return {"gecerli": False, "kirilma_seq": e.get("seq"), "neden": "previous_hash zinciri kopuk", "olay_sayisi": len(olaylar)}
        beklenen = _olay_hash(e["task_id"], e["seq"], e["previous_hash"], e["actor"], e["action"], e["timestamp"], e.get("metadata"))
        if beklenen != e.get("event_hash"):
            return {"gecerli": False, "kirilma_seq": e.get("seq"), "neden": "event_hash yeniden hesaplamayla uyuşmuyor (kayıt değiştirilmiş)", "olay_sayisi": len(olaylar)}
        prev = e["event_hash"]
    return {"gecerli": True, "kirilma_seq": None, "olay_sayisi": len(olaylar)}


@router.post("/ai/ayaz/talep-uret")
async def ayaz_talep_uret(govde: AyazTaskRequest, current_user=Depends(_ISTEYEN)):
    """Doğal dil talebi → kod taslağı + analiz + STATİK güvenlik taraması. exec/deploy YOK.
    Durum: 'incelemede' (güvenli) | 'guvenlik_reddetti' (statik tarama hatası)."""
    res = await call_claude(_SISTEM_PROMPT, govde.talep, max_tokens=3500, ozellik="ayaz_v1")
    ai = _parse_ai(res)
    if ai is None:
        raise HTTPException(status_code=502, detail="Kod üretilemedi (AI yanıtı ayrıştırılamadı).")
    try:
        gecerli = AyazTaskResponse(**ai)
    except Exception:
        raise HTTPException(status_code=422, detail="Üretilen kod beklenen şemayı karşılamadı.")

    # STATİK güvenlik: projenin gerçek AST tarayıcısı + compile (SÜREÇTE ÇALIŞTIRMADAN)
    tarama = patch_security.scan_python_source(gecerli.kod, "ayaz.py")
    try:
        compile(gecerli.kod, "ayaz.py", "exec")
        derleme_hatasi = None
    except SyntaxError as e:
        derleme_hatasi = str(e)
    guvenli = not tarama["errors"] and derleme_hatasi is None

    task = {
        "id": f"task_{str(uuid.uuid4())[:8]}", "tarih": iso(), "talep_sahibi": current_user.get("id"),
        "kullanici_talebi": govde.talep, "uretilen_kod": gecerli.kod, "aciklama": gecerli.aciklama,
        "etki_analizi": {"degisen_dosyalar": gecerli.degisen_dosyalar, "risk_seviyesi": gecerli.risk_seviyesi,
                         "etki_alani": gecerli.etki_alani, "tahmini_sure_dk": gecerli.tahmini_sure_dk},
        "guvenlik": {"errors": tarama["errors"], "warnings": tarama["warnings"], "derleme_hatasi": derleme_hatasi},
        "durum": "incelemede" if guvenli else "guvenlik_reddetti",
        "kurulum": None, "canliya_alan": None, "canliya_alinma_tarihi": None,
    }
    await db.ai_programmer_tasks.insert_one({**task})
    task.pop("_id", None)
    await _audit_ekle(task["id"], current_user.get("id"), f"talep_uret:{task['durum']}",
                      {"risk": gecerli.risk_seviyesi, "guvenlik_hata": len(tarama["errors"]), "kod_sha256": hashlib.sha256(gecerli.kod.encode("utf-8")).hexdigest()})
    await islem_kaydet(current_user, "ayaz", "talep_uret", "ayaz_task", task["id"], None, None, task["durum"])
    return {"ok": True, "task": task}


@router.get("/ai/ayaz/gorevler")
async def ayaz_gorevler(current_user=Depends(_ISTEYEN)):
    items = await db.ai_programmer_tasks.find({}, {"_id": 0}).sort("tarih", -1).to_list(length=500)
    return {"tasks": items}


@router.get("/ai/ayaz/gorev/{task_id}")
async def ayaz_gorev(task_id: str, current_user=Depends(_ISTEYEN)):
    t = await db.ai_programmer_tasks.find_one({"id": task_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    return t


@router.post("/ai/ayaz/gorev/{task_id}/reddet")
async def ayaz_reddet(task_id: str, current_user=Depends(_ADMIN)):
    r = await db.ai_programmer_tasks.update_one(
        {"id": task_id, "durum": {"$in": ["incelemede", "guvenlik_reddetti"]}}, {"$set": {"durum": "reddedildi"}})
    if r.matched_count == 0:
        raise HTTPException(status_code=400, detail="Yalnız incelemedeki/reddedilen görev reddedilir")
    await _audit_ekle(task_id, current_user.get("id"), "reddet", {})
    await islem_kaydet(current_user, "ayaz", "reddet", "ayaz_task", task_id, "durum", None, "reddedildi")
    return {"ok": True, "durum": "reddedildi"}


@router.post("/ai/ayaz/gorev/{task_id}/uygula")
async def ayaz_uygula(task_id: str, current_user=Depends(_ADMIN)):
    """İNSAN ONAYLI canlıya alma: yalnız 'incelemede' görev; admin kodu GÖRDÜKTEN sonra. Kod, MEVCUT
    patch_manager.install_patch pipeline'ından geçer (tekrar AST tarama + path/core koruması + sürüm
    arşivi + rollback). Süreç-içi exec yok; başarısızsa install_patch kendi rollback'ini yapar."""
    t = await db.ai_programmer_tasks.find_one({"id": task_id})
    if not t:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    if t.get("durum") != "incelemede":
        raise HTTPException(status_code=400, detail="Yalnız 'incelemede' (statik güvenlik geçmiş) görev uygulanır")

    modul = _modul_adi(task_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "a", zipfile.ZIP_DEFLATED, False) as zf:
        manifest = {"name": modul, "version": "1.0.0", "description": (t.get("aciklama") or "Ayaz modülü")[:200],
                    "author": "Ayaz v1.5", "type": "backend", "entry_point": f"{modul}.py"}
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr(f"{modul}.py", t["uretilen_kod"])
    sonuc = patch_manager.install_patch(buf.getvalue())  # scan_zip + classify + versiyon arşivi + install
    buf.close()

    if not sonuc.get("ok"):
        await db.ai_programmer_tasks.update_one({"id": task_id}, {"$set": {"durum": "kurulum_hatasi", "kurulum": sonuc}})
        await _audit_ekle(task_id, current_user.get("id"), "uygula:hata", {"errors": (sonuc.get("errors") or [])[:5]})
        await islem_kaydet(current_user, "ayaz", "uygula_hata", "ayaz_task", task_id, None, None, "; ".join(sonuc.get("errors", []))[:200])
        raise HTTPException(status_code=400, detail={"mesaj": "Kurulum reddedildi (güvenlik/doğrulama).", "sonuc": sonuc})

    await db.ai_programmer_tasks.update_one({"id": task_id}, {"$set": {
        "durum": "canlida", "kurulum": sonuc, "modul_adi": modul,
        "canliya_alan": current_user.get("id"), "canliya_alinma_tarihi": iso()}})
    await _audit_ekle(task_id, current_user.get("id"), "uygula:canlida", {"modul": modul, "version": sonuc.get("version")})
    await islem_kaydet(current_user, "ayaz", "uygula", "ayaz_task", task_id, "durum", "incelemede", f"canlida ({modul} v{sonuc.get('version')})")
    return {"ok": True, "durum": "canlida", "modul": modul, "kurulum": sonuc}


@router.post("/ai/ayaz/gorev/{task_id}/geri-al")
async def ayaz_geri_al(task_id: str, current_user=Depends(_ADMIN)):
    """Canlıya alınmış Ayaz modülünü mevcut patch_manager ile kaldırır (insan onaylı rollback)."""
    t = await db.ai_programmer_tasks.find_one({"id": task_id})
    if not t or t.get("durum") != "canlida" or not t.get("modul_adi"):
        raise HTTPException(status_code=400, detail="Yalnız canlıdaki Ayaz modülü geri alınır")
    sonuc = patch_manager.delete_module(t["modul_adi"])
    await db.ai_programmer_tasks.update_one({"id": task_id}, {"$set": {"durum": "geri_alindi", "geri_alma": sonuc}})
    await _audit_ekle(task_id, current_user.get("id"), "geri_al", {"modul": t.get("modul_adi")})
    await islem_kaydet(current_user, "ayaz", "geri_al", "ayaz_task", task_id, "durum", "canlida", "geri_alindi")
    return {"ok": True, "durum": "geri_alindi", "sonuc": sonuc}


@router.get("/ai/ayaz/gorev/{task_id}/audit")
async def ayaz_audit(task_id: str, current_user=Depends(_ISTEYEN)):
    """Görevin kriptografik hash-chain audit izini + zincir doğrulamasını döner (salt-okunur)."""
    olaylar = await db.ayaz_audit.find({"task_id": task_id}, {"_id": 0}).sort("seq", 1).to_list(length=1000)
    return {"olaylar": olaylar, "dogrulama": await _audit_dogrula(task_id)}
