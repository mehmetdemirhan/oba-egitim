"""Yedekleme (backup/restore) + sürüm/güncelleme kontrolü — ADMIN endpoint'leri.

server.py'dan birebir taşındı. Endpoint gövdeleri, yollar ve yanıt formatları
değişmedi; yalnızca route'lar `api_router` yerine modül-yerel `router` üzerine
kaydedilir ve server.py bu router'ı `api_router.include_router(router)` ile dahil eder.
Nihai yollar aynıdır: /api/admin/backup, /api/admin/backups, ... /api/admin/updates/check
"""
import io
import os
import uuid
import logging
from datetime import datetime, timezone

import httpx
from bson import json_util, ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.db import db, backup_fs
from core.zaman import aware as _zaman_aware
from core.auth import require_role, UserRole
from core.config import (
    APP_VERSION,
    BACKUP_COLLECTION_DENYLIST,
    MAX_MANUAL_BACKUPS_TO_RETAIN,
    MAX_AUTO_PRE_RESTORE_BACKUPS_TO_RETAIN,
    GITHUB_REPO_OWNER,
    GITHUB_REPO_NAME,
    GITHUB_TOKEN,
    UPDATE_CHECK_MIN_INTERVAL_SECONDS,
)

router = APIRouter()


def _backup_history_public(doc: dict) -> dict:
    """Strip Mongo's _id so the doc can be sent over the wire."""
    out = dict(doc)
    out.pop("_id", None)
    return out


async def _prune_backups_by_label(etiket: str, keep: int):
    """Keep the newest `keep` rows for this label; delete older rows + their GridFS files."""
    rows = await db.backup_history.find({"etiket": etiket}).sort("olusturma_tarihi", -1).to_list(length=None)
    for row in rows[keep:]:
        gridfs_id = row.get("gridfs_id")
        if gridfs_id:
            try:
                await backup_fs.delete(ObjectId(gridfs_id))
            except Exception as e:
                logging.warning(f"[BACKUP] GridFS delete failed for {gridfs_id}: {e}")
        await db.backup_history.delete_one({"id": row["id"]})


async def _snapshot_db(current_user: dict, etiket: str) -> dict:
    """Full DB snapshot → GridFS → backup_history row → per-label retention. Returns the row."""
    olusturma = datetime.now(timezone.utc).isoformat()
    names = await db.list_collection_names()
    names = [n for n in names if n not in BACKUP_COLLECTION_DENYLIST and not n.startswith("system.")]

    data = {}
    doc_counts = {}
    for name in names:
        docs = await db[name].find().to_list(length=None)
        data[name] = docs
        doc_counts[name] = len(docs)

    payload = {
        "meta": {
            "created_at": olusturma,
            "app_version": APP_VERSION,
            "etiket": etiket,
        },
        "doc_counts": doc_counts,
        "data": data,
    }
    blob = json_util.dumps(payload).encode("utf-8")

    safe_ts = olusturma.replace(":", "-")
    dosya_adi = f"oba_backup_{etiket}_{safe_ts}.json"
    gridfs_id = await backup_fs.upload_from_stream(
        dosya_adi,
        io.BytesIO(blob),
        metadata={"etiket": etiket, "app_version": APP_VERSION, "olusturan_id": current_user.get("id")},
    )

    row = {
        "id": str(uuid.uuid4()),
        "etiket": etiket,
        "olusturma_tarihi": olusturma,
        "olusturan_id": current_user.get("id"),
        "olusturan_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip(),
        "app_version": APP_VERSION,
        "boyut_bytes": len(blob),
        "koleksiyon_sayisi": len(names),
        "toplam_kayit": sum(doc_counts.values()),
        "gridfs_id": str(gridfs_id),
        "dosya_adi": dosya_adi,
    }
    await db.backup_history.insert_one(row.copy())

    keep = MAX_AUTO_PRE_RESTORE_BACKUPS_TO_RETAIN if etiket == "auto-pre-restore" else MAX_MANUAL_BACKUPS_TO_RETAIN
    await _prune_backups_by_label(etiket, keep)

    return row


class RestoreRequest(BaseModel):
    onay: str


@router.post("/admin/backup")
async def admin_create_backup(current_user=Depends(require_role(UserRole.ADMIN))):
    row = await _snapshot_db(current_user, etiket="manual")
    return _backup_history_public(row)


@router.get("/admin/backups")
async def admin_list_backups(current_user=Depends(require_role(UserRole.ADMIN))):
    rows = await db.backup_history.find().sort("olusturma_tarihi", -1).to_list(length=None)
    return [_backup_history_public(r) for r in rows]


@router.get("/admin/backups/{backup_id}/download")
async def admin_download_backup(backup_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    row = await db.backup_history.find_one({"id": backup_id})
    if not row:
        raise HTTPException(status_code=404, detail="Yedek bulunamadı")
    try:
        stream = await backup_fs.open_download_stream(ObjectId(row["gridfs_id"]))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GridFS okuma hatası: {e}")

    async def chunk_gen():
        while True:
            chunk = await stream.readchunk()
            if not chunk:
                break
            yield chunk

    headers = {"Content-Disposition": f'attachment; filename="{row["dosya_adi"]}"'}
    return StreamingResponse(chunk_gen(), media_type="application/json", headers=headers)


@router.delete("/admin/backups/{backup_id}")
async def admin_delete_backup(backup_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    row = await db.backup_history.find_one({"id": backup_id})
    if not row:
        raise HTTPException(status_code=404, detail="Yedek bulunamadı")
    gridfs_id = row.get("gridfs_id")
    if gridfs_id:
        try:
            await backup_fs.delete(ObjectId(gridfs_id))
        except Exception as e:
            logging.warning(f"[BACKUP] GridFS delete failed for {gridfs_id}: {e}")
    await db.backup_history.delete_one({"id": backup_id})
    return {"ok": True}


@router.post("/admin/backups/{backup_id}/restore")
async def admin_restore_backup(
    backup_id: str,
    body: RestoreRequest,
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    if body.onay != "GERI YUKLE":
        raise HTTPException(status_code=403, detail="Onay metni hatalı. Lütfen tam olarak 'GERI YUKLE' yazın.")

    row = await db.backup_history.find_one({"id": backup_id})
    if not row:
        raise HTTPException(status_code=404, detail="Yedek bulunamadı")

    # 1) Auto pre-restore safety snapshot
    try:
        pre = await _snapshot_db(current_user, etiket="auto-pre-restore")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Güvenlik yedeği alınamadı, restore iptal: {e}")

    # 2) Snapshot ALL admin users (preserve through wipe + merge back after)
    mevcut_adminler = await db.users.find({"role": "admin"}).to_list(length=None)
    for a in mevcut_adminler:
        a.pop("_id", None)

    # 3) Load target backup payload
    try:
        target_stream = await backup_fs.open_download_stream(ObjectId(row["gridfs_id"]))
        buf = bytearray()
        while True:
            chunk = await target_stream.readchunk()
            if not chunk:
                break
            buf.extend(chunk)
        payload = json_util.loads(bytes(buf).decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Yedek okunamadı: {e}")

    data = payload.get("data", {})
    report = {}

    # 4) Per-collection wipe + insert
    for name, docs in data.items():
        if name in BACKUP_COLLECTION_DENYLIST or name.startswith("system."):
            continue
        try:
            await db[name].delete_many({})
            if docs:
                await db[name].insert_many(docs)
            report[name] = {"ok": True, "count": len(docs)}
        except Exception as e:
            report[name] = {"ok": False, "error": str(e)[:300]}

    # 5) Admin merge — current admins win, and ones missing from backup are re-inserted
    merged_admins = []
    for admin in mevcut_adminler:
        try:
            await db.users.update_one({"id": admin["id"]}, {"$set": admin}, upsert=True)
            merged_admins.append(admin["id"])
        except Exception as e:
            logging.warning(f"[RESTORE] Admin merge failed for {admin.get('id')}: {e}")

    return {
        "ok": True,
        "report": report,
        "merged_admin_count": len(merged_admins),
        "merged_admins": merged_admins,
        "pre_restore_backup_id": pre["id"],
    }


@router.get("/admin/version")
async def admin_version(current_user=Depends(require_role(UserRole.ADMIN))):
    commit_sha = os.environ.get("RENDER_GIT_COMMIT", "") or os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")
    return {
        "version": APP_VERSION,
        "commit_sha": commit_sha,
        "deployed_at": os.environ.get("RENDER_GIT_COMMIT_DATE", ""),
    }


@router.get("/admin/updates/check")
async def admin_updates_check(
    force: bool = False,
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    if not GITHUB_REPO_OWNER or not GITHUB_REPO_NAME:
        return {
            "configured": False,
            "message": "GITHUB_REPO_OWNER ve GITHUB_REPO_NAME ortam değişkenleri tanımlı değil.",
            "current_version": APP_VERSION,
        }

    now = datetime.now(timezone.utc)
    cache = await db.sistem_ayarlari.find_one({"tip": "updates_check_cache"})
    if not force and cache and cache.get("checked_at"):
        try:
            checked_at = _zaman_aware(cache["checked_at"])  # naive/aware normalize
            if checked_at and (now - checked_at).total_seconds() < UPDATE_CHECK_MIN_INTERVAL_SECONDS:
                cached_payload = cache.get("payload", {})
                cached_payload["from_cache"] = True
                return cached_payload
        except Exception:
            pass

    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    base = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
    latest_release_tag = None
    latest_release_url = None
    latest_release_published_at = None
    latest_commit_sha = None
    latest_commit_date = None
    latest_commit_message = None
    ahead_by = 0
    behind_by = 0
    errors = []

    async with httpx.AsyncClient(timeout=15.0) as c:
        try:
            r = await c.get(f"{base}/releases/latest", headers=headers)
            if r.status_code == 200:
                rj = r.json()
                latest_release_tag = rj.get("tag_name")
                latest_release_url = rj.get("html_url")
                latest_release_published_at = rj.get("published_at")
            elif r.status_code != 404:
                errors.append(f"releases/latest: {r.status_code}")
        except Exception as e:
            errors.append(f"releases/latest exception: {str(e)[:120]}")

        try:
            r = await c.get(f"{base}/commits", params={"per_page": 1}, headers=headers)
            if r.status_code == 200:
                cj = r.json()
                if cj:
                    latest_commit_sha = cj[0].get("sha")
                    commit = cj[0].get("commit", {})
                    latest_commit_date = commit.get("committer", {}).get("date")
                    latest_commit_message = commit.get("message", "").split("\n")[0][:200]
            else:
                errors.append(f"commits: {r.status_code}")
        except Exception as e:
            errors.append(f"commits exception: {str(e)[:120]}")

        try:
            r = await c.get(f"{base}/compare/{APP_VERSION}...HEAD", headers=headers)
            if r.status_code == 200:
                cmp = r.json()
                ahead_by = cmp.get("ahead_by", 0) or 0
                behind_by = cmp.get("behind_by", 0) or 0
        except Exception:
            pass

    update_available = bool(
        (latest_release_tag and latest_release_tag != APP_VERSION) or (ahead_by > 0)
    )

    payload = {
        "configured": True,
        "current_version": APP_VERSION,
        "latest_release_tag": latest_release_tag,
        "latest_release_url": latest_release_url,
        "latest_release_published_at": latest_release_published_at,
        "latest_commit_sha": latest_commit_sha,
        "latest_commit_date": latest_commit_date,
        "latest_commit_message": latest_commit_message,
        "ahead_by": ahead_by,
        "behind_by": behind_by,
        "update_available": update_available,
        "checked_at": now.isoformat(),
        "errors": errors,
        "from_cache": False,
    }

    await db.sistem_ayarlari.update_one(
        {"tip": "updates_check_cache"},
        {"$set": {"tip": "updates_check_cache", "checked_at": now.isoformat(), "payload": payload}},
        upsert=True,
    )

    return payload
