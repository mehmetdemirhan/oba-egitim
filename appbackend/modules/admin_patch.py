"""Modül Yöneticisi (yama sistemi) — ADMIN API endpoint'leri (/admin/moduller/*).

Tüm endpoint'ler require_role(UserRole.ADMIN) ile korunur; diğer roller 403 alır.
İş mantığı core.patch_manager içindedir; bu dosya yalnızca HTTP katmanıdır.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from core.auth import require_role, UserRole
from core import patch_manager as pm

router = APIRouter()


@router.get("/admin/moduller")
async def moduller_listele(current_user=Depends(require_role(UserRole.ADMIN))):
    """Kurulu tüm modüllerin manifest listesi (UI kartları için)."""
    return pm.list_modules()


@router.post("/admin/moduller/yukle")
async def modul_yukle(
    dosya: UploadFile = File(...),
    current_user=Depends(require_role(UserRole.ADMIN)),
):
    """ZIP yama yükle ve kur. Sonuç raporu döner."""
    if not dosya.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Yalnızca .zip dosyası kabul edilir.")
    data = await dosya.read()
    sonuc = pm.install_patch(data)
    if not sonuc["ok"]:
        raise HTTPException(status_code=400, detail={"mesaj": "Yükleme başarısız", **sonuc})
    return {
        "mesaj": f"'{sonuc['name']}' v{sonuc['version']} kuruldu.",
        "restart_uyarisi": "Backend yeniden başlatılıyor (uvicorn --reload). 10-15 saniye sonra hazır olacak.",
        **sonuc,
    }
