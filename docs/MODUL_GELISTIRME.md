# Modül Geliştirme Rehberi (Yama Sistemi)

OBA backend'i **modüler**dir: her özellik `appbackend/modules/<ad>.py` içinde bir
`APIRouter` olarak yaşar ve `modules/registry.json` sırasına göre dinamik yüklenir.
Admin panelindeki **Modüller** sekmesi (Joomla benzeri) modülleri ZIP olarak
yükleme / güncelleme / açma-kapama / silme / eski sürüme dönme imkânı verir.

> Yetki: tüm modül işlemleri **yalnızca admin** (`require_role(UserRole.ADMIN)`).
> Diğer roller `403` alır.

---

## 1. Bir modül neye benzer?

```python
# modules/ornek_modul.py
"""Tek satırlık açıklama (manifest'te 'description' yoksa buradan alınır)."""
from fastapi import APIRouter, Depends
from core.db import db                 # DB erişimi SADECE core üzerinden
from core.auth import get_current_user # kimlik SADECE core üzerinden

router = APIRouter()                    # ZORUNLU: 'router' adında olmalı

@router.get("/ornek/selam")
async def selam():
    return {"mesaj": "Merhaba"}
```

Kurallar:
- Modül **`router` adında bir `APIRouter` ihraç etmek zorundadır** (yoksa yüklenmez).
- DB / kimlik / ayar / AI erişimini **yalnızca `core.*`** üzerinden yapın
  (`core.db`, `core.auth`, `core.sistem`, `core.ai`). **`server.py`'den import etmeyin.**
- Yol (path) çakışması olmamalı; mevcut yolları `appbackend/tests/route_snapshot.py`
  ile listeleyebilirsiniz.

---

## 2. manifest.json (zorunlu alanlar)

```json
{
  "name": "ornek_modul",
  "version": "1.0.0",
  "description": "Modülün ne yaptığı.",
  "author": "Adınız",
  "type": "backend",
  "core": false
}
```

| Alan | Zorunlu | Açıklama |
|---|---|---|
| `name` | ✔ | Modül adı = dosya adı (`<name>.py`). Küçük harf + alt çizgi. |
| `version` | ✔ | Semantik sürüm (`1.0.0`). Güncellemede artırın. |
| `description` | ✔ | Kart üzerinde gösterilir. |
| `author` | ✔ | — |
| `type` | ✔ | `backend` \| `frontend` \| `both`. |
| `core` | ✖ | `true` ise modül **kapatılamaz/silinemez** (çekirdek koruması). Varsayılan `false`. |

> Not: Yüklenirken `name`, `version`, `installed_at`, `backend_files`,
> `frontend_files`, `active` alanları sistem tarafından zenginleştirilip
> `modules/manifests/<name>.json` olarak saklanır.

---

## 3. ZIP paketi nasıl hazırlanır?

ZIP **kök dizininde** şunlar olmalı:

```
ornek_modul.zip
├── manifest.json          (zorunlu)
├── ornek_modul.py         (backend → modules/ altına gider)
└── (opsiyonel) *.jsx      (frontend → frontend/src/modules/ altına gider)
```

Komut satırından:

```bash
cd docs/ornek_modul
zip -r ../ornek_modul.zip manifest.json ornek_modul.py
# veya Python:
python -c "import zipfile,glob; z=zipfile.ZipFile('../ornek_modul.zip','w'); [z.write(f,f) for f in ['manifest.json','ornek_modul.py']]; z.close()"
```

Hazır referans paket: **`docs/ornek_modul.zip`** (kaynak: `docs/ornek_modul/`).
Admin panel → **Modüller** → **Yeni Modül Yükle** ile bu dosyayı deneyebilirsiniz.

---

## 4. Güvenlik (otomatik AST taraması)

Yüklenen her `.py` Python AST ile taranır. **Reddedilen** (hata) kalıplar:

- `os.system`, `os.popen`, `subprocess.*`, `os.remove`, `os.unlink`, `shutil.rmtree`
- `eval`, `exec`, `compile`, `__import__`
- `socket`, `ctypes`, `urllib`, `http.client`, `ftplib`, `importlib`, `subprocess` importları
- `__init__.py` veya `core/` hedefleyen dosyalar (yasak)

**Uyarı** (kurulur ama raporlanır): `requests`, `httpx`, `aiohttp`, `pickle`, `marshal`.
`.jsx` için `dangerouslySetInnerHTML`, `eval`, `innerHTML`, `document.write` uyarı üretir.

Dış API çağrısı gerekiyorsa `httpx` yerine **`core.ai`** yardımcılarını kullanın.

---

## 5. Sürüm yönetimi, geri alma, yeniden başlatma

- **Sürüm arşivi:** Bir modül güncellenince eski sürümü
  `appbackend/eski_versiyonlar/<ad>/<versiyon>/` altına yedeklenir. **Son 3** sürüm
  saklanır; 4. yüklemede en eski otomatik silinir.
- **Otomatik rollback:** Yükleme sonrası syntax + import kontrolü yapılır. Hata
  varsa **eski sürüme otomatik dönülür** ve ayrıntılı hata raporu gösterilir.
  (Yeni kurulum hatalıysa dosyalar tamamen kaldırılır.)
- **Yeniden başlatma:** Dosyalar değişince `uvicorn --reload` backend'i yeniden
  başlatır; UI "Backend yeniden başlatılıyor, 10-15 sn" uyarısı gösterir. Frontend
  için React HMR devrededir.
- **Açma/Kapama:** Pasif modüller `registry.json`'da `active:false` olur ve
  **backend'de hiç import edilmez** (route tablosuna girmez). Çekirdek (`core:true`)
  modüller kapatılamaz: `yedekleme, auth_api, dashboard, bildirim, admin_patch, seed`.

---

## 6. Admin API uçları

| Metot | Yol | İş |
|---|---|---|
| `GET` | `/api/admin/moduller` | Tüm modüller (manifest + aktiflik). |
| `POST` | `/api/admin/moduller/yukle` | ZIP yükle (kur/güncelle). `dosya` (multipart). |
| `PUT` | `/api/admin/moduller/{ad}/durum` | Aç/kapat. Gövde: `{"active": true|false}`. |
| `DELETE` | `/api/admin/moduller/{ad}` | Modülü tamamen kaldır. |
| `GET` | `/api/admin/moduller/{ad}/versiyonlar` | Arşivlenmiş sürümler. |
| `POST` | `/api/admin/moduller/{ad}/geri-yukle/{etiket}` | Sürüme dön. |

---

## 7. Bilinen sınırlamalar

- `uvicorn --reload` üretim (Render) ortamında kapalıysa değişiklikler ancak
  servis yeniden deploy/başlatılınca etkin olur.
- Sürüm arşivi **dosya sistemindedir** (`eski_versiyonlar/`, git'te yoksayılır);
  kalıcı disk yoksa restart'ta kaybolabilir.
- AST taraması statiktir; gizlenmiş (örn. `getattr` ile dinamik) tehlikeli çağrıları
  yakalamayabilir. Yine de yükleyenin **admin** olması gerekir.
- Frontend modülleri için dinamik `import` kayıt mekanizması temel düzeydedir;
  karmaşık bağımlılıklar elle entegrasyon isteyebilir.
