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

## Modül Yönetimi (Yama Sistemi)

Backend modülerdir; her özellik `appbackend/modules/<ad>.py` içinde bir `APIRouter`
olarak yaşar ve `modules/registry.json` sırasına göre dinamik yüklenir. Admin
panelindeki **Modüller** sekmesinden ZIP ile modül yükleme / güncelleme /
açma-kapama / silme / eski sürüme dönme yapılabilir (AST güvenlik taraması +
otomatik rollback + son 3 sürüm arşivi ile).

Ayrıntılı geliştirme rehberi, manifest şeması ve örnek paket:
**[docs/MODUL_GELISTIRME.md](docs/MODUL_GELISTIRME.md)** · örnek: `docs/ornek_modul.zip`

## Rozet Sistemi (v2 — Veri-Odaklı)

Rozet tanımları `rozetler` koleksiyonunda **veri** olarak durur; koşullar
`metrik / operator / eşik` üçlüsüyle yönetilir. Ödüller hem **event-driven**
(okuma kaydı, görev tamamlama, kur atlatma) hem de pull (`POST /rozetler/kontrol`,
dashboard) yoluyla verilir ve kazanımda **bildirim** gönderilir. Admin panelindeki
**🏅 Rozetler** sekmesinden tam CRUD, manuel ödül, kazananlar, istatistik ve
JSON içe/dışa aktarma yapılabilir. Öğrenci, öğretmen ve **veli** (çocuğunun
rozetleri) görünümleri paylaşılan `RozetGrid` bileşenini kullanır.

Mimari, event akışı, yeni metrik ekleme, API referansı ve üretim migrasyonu:
**[docs/ROZET_SISTEMI.md](docs/ROZET_SISTEMI.md)**
