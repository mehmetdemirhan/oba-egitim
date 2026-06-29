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


@router.get("/admin/moduller/{ad}/versiyonlar")
async def modul_versiyonlar(ad: str, current_user=Depends(require_role(UserRole.ADMIN))):
    """Bir modülün arşivlenmiş geçmiş sürümleri (yeniden eskiye)."""
    if pm.manifest_oku(ad) is None and not (pm.VERSIONS_DIR / ad).exists():
        raise HTTPException(status_code=404, detail="Modül bulunamadı.")
    return pm.list_versions(ad)


@router.post("/admin/moduller/{ad}/geri-yukle/{etiket}")
async def modul_geri_yukle(ad: str, etiket: str, current_user=Depends(require_role(UserRole.ADMIN))):
    """Modülü arşivdeki bir sürüme geri döndürür."""
    sonuc = pm.restore_version(ad, etiket)
    if not sonuc["ok"]:
        raise HTTPException(status_code=400, detail={"mesaj": "Geri yükleme başarısız", **sonuc})
    return {
        "mesaj": f"'{ad}' '{etiket}' sürümüne geri yüklendi.",
        "restart_uyarisi": "Backend yeniden başlatılıyor. 10-15 saniye sonra hazır olacak.",
        **sonuc,
    }
