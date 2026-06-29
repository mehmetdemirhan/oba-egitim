# oba-egitim

OBA — FastAPI (backend, Render) + React (frontend, Vercel) + MongoDB Atlas.

## Admin paneli ortam değişkenleri

Yedekleme ve güncelleme özellikleri için backend'e (`appbackend/.env` lokalde / Render dashboard prod'da) eklenmesi gereken değişkenler:

| Var | Zorunlu | Açıklama |
|---|---|---|
| `APP_VERSION` | evet | Admin panelinde gösterilen sürüm. Her release'de elle bumplayın. Örn: `1.2.0`. |
| `GITHUB_REPO_OWNER` | güncelleme kontrolü için evet | GitHub repo owner. |
| `GITHUB_REPO_NAME` | güncelleme kontrolü için evet | GitHub repo adı. |
| `GITHUB_TOKEN` | opsiyonel | Private repo veya yüksek rate limit (60→5000/saat) için. |
| `RENDER_GIT_COMMIT` | Render otomatik | `/api/admin/version` çağrısının commit SHA değeri için. |

`GITHUB_REPO_*` boş bırakılırsa güncelleme sekmesi yapılandırılmadığını bildirir; backup özellikleri etkilenmez.
