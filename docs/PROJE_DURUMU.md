# OBA Eğitim — Proje Durumu Raporu (AI/Yeni Oturum Devir Dosyası)

> Bu dosya, projeyi hiç görmemiş bir yapay zekanın (veya yeni oturumun) sıfırdan anlaması
> için hazırlandı. Her iddia kod tabanından doğrulandı; emin olunamayan yerler **TEYİT
> EDİLEMEDİ** olarak işaretlendi. Son güncelleme: 2026-07-18. Kanıt kaynağı: `main` @ `769c7bf`.
>
> İlk okumada ayrıca oku: kök `CLAUDE.md`, `docs/MODUL_GELISTIRME.md`, ve Claude auto-memory
> (`.claude/projects/.../memory/MEMORY.md`).

---

## 1. Proje Özeti

**OBA**, bir okuma becerileri eğitim kurumu için **eğitim + öğrenci/veli CRM + muhasebe + AI
destekli analiz** yönetim sistemidir. Öğrencilerin okuma hızı/anlama/prozodi gelişimini ölçer
(diagnostic/TIMI), egzersizlerle çalıştırır, öğretmen hakedişini ve veli ödemelerini takip eder.

**Roller** (`core/auth.py` `UserRole`): `admin` (yönetici), `coordinator` (koordinatör),
`teacher` (öğretmen), `student` (öğrenci), `parent` (veli), `accountant` (muhasebe). Rol
ayrımı `require_role(...)` bağımlılığıyla uçlarda zorlanır.

**İş modeli:** Kur-bazlı eğitim. Her öğrenci bir "kur" alır (`db.kur_ucretleri`), kur bittikçe
üst kura geçer (kur geçişi). Öğretmen hakedişi **ayın 15'i dönem sistemiyle** işler: veli
ödemesi tamamlanınca (`odeme_tamamlanma_tarihi` damgası) kurun `ogretmen_pay`'ı o dönemin
hakedişine girer; dönem ödemesi yapılınca (`ogretmen_donem_ode`) kur `odendi_donem` ile
mühürlenir. (Ayrıntı: bölüm 7 — Muhasebe.)

---

## 2. Mimari

### Backend — FastAPI + MongoDB (Motor/async)
- Giriş noktası: `appbackend/server.py`. Global router `APIRouter(prefix="/api")`
  (`server.py:131`). Toplam **557 route** (`tests/route_snapshot.py`).
- **Modül-registry mimarisi (kritik):** `server.py` modülleri elle include ETMEZ.
  `core/registry.py:register_routers` (`server.py:311-313`), `modules/registry.json`'daki
  **aktif modülleri SIRASIYLA** dinamik yükler. Her modül `router = APIRouter()` ihraç eder.
  **Sıra önemlidir** — catch-all / duplike yollar için route eşleşmesini etkiler; bozmayın.
- **Korumalı modüller** (kapatılamaz/silinemez, `core/registry.py:17`):
  `{yedekleme, auth_api, dashboard, bildirim, admin_patch, seed}`.
- Açılış olayları (`server.py:144-150`): `create_default_admin`, `ensure_indexes`,
  `duyurulari_seed` (hepsi tek-seferlik seed/index; zamanlanmış görev DEĞİL).
- **Yama/Modül sistemi:** admin panelinden ZIP ile modül yükle/güncelle/aç-kapa/sil/sürüme dön
  (`core/patch_manager.py`, `core/patch_security.py` [AST güvenlik], `modules/admin_patch.py`).

### Frontend — React (CRA/react-scripts), monolitik
- `frontend/src/App.js` **~14.000 satırlık tek dosya** (tüm ekranlar inline). Ayrı bileşenler
  `frontend/src/components/` altında (ör. `OdemeTablosu.jsx`, `MuhasebePaneli.jsx`,
  `admin/*`, `aiceo/*`, `exercises/*`).
- Build: `cd frontend && CI=false npm run build` (react-scripts; Tailwind CRA yerleşik
  desteğiyle `tailwind.config.js`. **craco KULLANILMIYOR, `cdn.tailwindcss.com` YOK**).
- API tabanı: `const API = \`${process.env.REACT_APP_BACKEND_URL}/api\`` (`App.js:76-78`).

### `core/` katmanı (30+ dosya) — çekirdek servisler
DB/kimlik/ayar/AI erişimi **daima core üzerinden**. Öne çıkanlar:
- `config.py` — tüm env değişkenleri (bölüm 3). `db.py` — Mongo client + `db` + **lazy
  GridFS** (bölüm 3, açılış çökmesi). `auth.py` — JWT + `require_role`/`get_current_user`.
- `ai.py` — Gemini çağrı sarmalayıcısı (`call_claude`, `gemini_grounded_call`, `_gemini_call`;
  3 anahtar rotasyonu; `ai_request_log`'a özellik-etiketli sayaç). `audit.py` — `islem_kaydet`
  → `db.islem_log`. `giris_log.py` → `db.giris_log`. `zaman.py` — tarih standardı (aşağıda).
- `temizlik.py` — **ortak "yarım kalan kayıt" temizleyici** (`yarim_kayit_temizle`,
  `throttle_gunluk`, `yas_gun`); TIMI taslakları + analiz oturumları bunu kullanır.
- Diğer: `registry.py`, `patch_manager/patch_security`, `bakim.py` (bakım modu),
  `mail.py`/`mesaj_kanallari.py` (SMTP/SMS/WhatsApp), `metin_zorluk.py`, `acik_soru.py`,
  `rozet_motor/rozet_kosullari/rozet_helpers`, `kelime_secici/kelime_durum/turkce_kelime_havuzu`,
  `egzersiz_prompts/egzersiz_tipleri`, `bulmaca_olusturucu.py`, `rapor_ayarlari.py`,
  `hesap.py`, `kayit_normalize.py`, `sistem.py`, `tema_varsayilan.py`.

### CLAUDE.md kuralları (özet — tam metin kökte)
- **Tarih/zaman (KURAL):** tarih üretimi **yalnız `core.zaman`** — `simdi()` (aware UTC),
  `iso()` (aware UTC ISO). **`datetime.utcnow()` YASAK** (naive üretir → "can't compare
  offset-naive and offset-aware datetimes"). Karşılaştırmadan önce `core.zaman.aware(x)` ile
  normalize et. `parse_from_mongo` okunan tarihleri zaten aware UTC'ye çevirir. (`core/zaman.py`)
- **Modül sırası:** `modules/registry.json` sırası kritik (catch-all/duplike). Bozmayın.
- **Dil:** kod/yorum **Türkçe** (mevcut dosyalardaki gibi).
- **Commit:** her büyük adımdan sonra, Türkçe açıklayıcı mesaj.
- **Test:** smoke testleri `appbackend/tests/test_*_smoke.py`, Windows'ta
  `PYTHONIOENCODING=utf-8`. (Bölüm 9.)

---

## 3. Deploy / Altyapı — KRİTİK

### Canlı servisler
- **Backend = Render, servis adı `oba-backend-2026`** (GERÇEK canlı servis; **`production`
  branch'ini izler**). — *Kaynak: kullanıcı beyanı. Kod/repo'da Render servis adı geçmez
  (Procfile jeneriktir); repo düzeyinde TEYİT EDİLEMEDİ.*
- ⚠️ **KARIŞIKLIK NOTU:** `oba-egitim-backend` adında **AYRI, kullanılmayan** bir Render
  servisi daha var. Deploy/log incelerken doğru servisin **`oba-backend-2026`** olduğunu
  unutmayın. *(Kullanıcı beyanı.)*
- **Frontend = Vercel** (CLAUDE.md: "Vercel'de deploy"; `main`/`production` push'unda otomatik
  build — hangi branch'i izlediği repo'da TEYİT EDİLEMEDİ, pratikte `main`).
- Başlatma: `Procfile` → `web: uvicorn server:app --host 0.0.0.0 --port $PORT`. **`runtime.txt`
  YOK** → Render varsayılan Python'unu kullanır (bkz. açılış çökmesi).

### Deploy akışı (standart)
`refactor/modular-server`'da geliştir → commit + push → `main`'e `--no-ff` merge → push →
`production`'a `--ff-only` → push. Render (`oba-backend-2026`) `production`'ı, Vercel `main`'i
otomatik deploy eder. (Şu an `main` = `production` = `769c7bf`; `refactor` topolojik olarak
merge commit'leri nedeniyle ayrı SHA'da olabilir — içerik aynı.)

### Bugün yaşanan olaylar + çözümleri (tekrarı önlemek için)
1. **Python 3.14 / GridFS açılış çökmesi ("Exited with status 3"):** `core/db.py` GridFS
   yedek bucket'ını (`AsyncIOMotorGridFSBucket`) **import anında** oluşturuyordu; bu
   `get_event_loop()` çağırır. uvicorn app'i çalışan loop OLMADAN import ettiğinden Python
   3.14'te `RuntimeError: no current event loop` → açılışta çöküş. Eski Python otomatik loop
   oluşturup bu gizli hatayı maskeliyordu; Render'ın Python'u 3.14'e geçince ortaya çıktı.
   **Çözüm:** `core/db.py`'de `backup_fs` **tembel (`_LazyGridFS`)** yapıldı — bucket ilk
   KULLANIMDA (async endpoint içinde, loop hazırken) oluşturulur; import loop gerektirmez.
   Doğrulama: `import server` OK + "uvicorn Application startup complete".
2. **Mongo Atlas kimlik doğrulama sorunu:** *Kullanıcı bugün bundan bahsetti; kod tarafında
   doğrudan bir düzeltme kanıtı YOK (bu bir env/kimlik-bilgisi sorunudur, Render env düzeyinde
   çözülür).* **TEYİT EDİLEMEDİ (kod düzeyi).** Not: kimlik bilgisi rotasyonu gerekirse
   `MONGO_URL`'in **Render env'inde** güncellenmesi yeterli (kodda gömülü değil).

### Env değişkenleri (yalnız İSİMLER — hepsi `core/config.py`'de `os.environ`'dan; değerler
Render/Vercel env'inde, repo'da DEĞİL)
- **DB:** `MONGO_URL`, `DB_NAME` (zorunlu — `os.environ[...]`, yoksa açılışta patlar).
- **AI:** `GEMINI_API_KEY` (+ `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3` rotasyon —
  `core/ai.py`), `ANTHROPIC_API_KEY`, `AI_DEFAULT_MODEL`, `AI_MAX_DAILY_REQUESTS`,
  `AI_CACHE_HOURS`.
- **E-posta:** `SMTP_HOST/PORT/USER/PASSWORD/FROM/TLS`.
- **SMS (Netgsm):** `NETGSM_USERNAME/PASSWORD/HEADER/BASE_URL/PARTNER_CODE/IYS_FILTER`,
  `SMS_BIRIM_UCRET`.
- **WhatsApp:** `WHATSAPP_TOKEN/PHONE_ID/BASE_URL/WEBHOOK_VERIFY_TOKEN/DEFAULT_TEMPLATE/
  DEFAULT_LANG`, `WHATSAPP_BIRIM_UCRET`.
- **Web Push (VAPID):** `VAPID_PUBLIC_KEY/PRIVATE_KEY/SUBJECT`, `PUSH_CRON_TOKEN`,
  `PUSH_HATIRLATMA_DK`, `PUSH_TZ_OFFSET_SAAT`.
- **Diğer:** `GITHUB_TOKEN/REPO_OWNER/REPO_NAME` (altyapı), `YANDEX_DISK_TOKEN` (yedek),
  `FRONTEND_URL`, `APP_VERSION`, `SIFRE_RESET_TOKEN_DK`.
- **Cron:** temizlik uçları (`/timi/gunluk-temizlik`, `/diagnostic/gunluk-temizlik`)
  `PUSH_CRON_TOKEN` ile korunur; harici cron yoksa ilgili GET uçları günde-bir throttle ile
  tetikler.

---

## 4. Modül Envanteri (`appbackend/modules/*.py` — docstring'lerden doğrulandı)

| Modül | Ne yapar (özet) |
|---|---|
| `auth_api` | Kimlik/oturum `/auth/*` (login, refresh, şifre reset). **Korumalı.** |
| `dashboard` | `/dashboard`, `/stats/*` — özet/istatistik + onay bekleyen kuyruk. **Korumalı.** |
| `crm` | Öğrenci/öğretmen/veli CRUD, kur atama; `students`/`teachers`. |
| `yedekleme` | Yedek/geri yükleme (GridFS + Yandex Disk), ADMIN. **Korumalı.** |
| `diagnostic` | Okuma analizi `/diagnostic/*` — oturum (Hata Takibi/Anlama/Prozodik), rapor PDF, **metin havuzu (`analiz_metinler`) + onay** + AI cevap + yedek/temizle. |
| `timi` / `timi_metin` | TIMI Çoklu Zeka Envanteri `/timi/*` + deterministik rapor metin bankası. |
| `sinav` / `sinav_parser` | LGS/Bursluluk soru bankası + PDF içe aktarım + admin onay (taslak→yayında) + AI taktik. |
| `ayarlar` | Sistem ayarları `/ayarlar/*` (puanlar, özellikler, tip-bazlı). |
| `egzersiz` / `egzersiz_motoru` | Egzersiz kayıtları + tip motoru (`egzersiz_icerikler`, AI üretimli tipler). |
| `kutulu_okuma` | Kutulu okuma egzersizi — metin `analiz_metinler` (bolum=analiz) havuzundan. |
| `kitap` / `kitap_dersleri` | Kitap havuzu + kitap-bilgi çekme; kitap parça/soru. |
| `sorular` | Genel soru CRUD `/sorular/*`. |
| `admin_debug` | `/admin/fix-ids`, `/admin/gemini-*`, `/admin/debug-*` (ADMIN). |
| `admin_patch` | Modül yöneticisi (ZIP yama) `/admin/moduller/*` (ADMIN). **Korumalı.** |
| `admin_migrations` | Migration altyapısı `/admin/migrations` (ADMIN). |
| `gelisim` | Gelişim (kitap/film yansıtma) `/gelisim/*` + oylama/admin karar. |
| `ogrenci_panel` | Okuma kayıtları (`reading_logs`) + öğrenci paneli. |
| `risk` | Risk skoru `/risk-skor/*`. |
| `ilerleme` | XP/kur/rozet/sezon oyunlaştırma `/xp/*, /kur/*, /rozetler/*, /sezon/*`. |
| `rozet` | Rozet CRUD + istatistik `/rozet/*` (veri-odaklı; FAZ 3). |
| `tema` | Tema tanımları + kullanıcı tercihi `/tema/*` (FAZ 3 yönetim). |
| `push` | Web Push (VAPID) ders hatırlatma `/push/*`. |
| `anketler` | Veli/öğrenci anketleri `/anketler/*`. |
| `ai_kocluk` | AI koçluk + okuma DNA + motivasyon `/ai/dna, /ai/kocluk/*`. |
| `ai_uretim` | AI içerik üretimi (soru/hikaye/materyal/mini-oyun/okuma-parçaları). |
| `ai_bilgi_tabani` | AI bilgi tabanı + kitaptan parça/kelime çıkarma `/ai/bilgi-tabani/*`. |
| `ai_socratic` | AI sokratik diyalog `/ai/socratic-*`. |
| `ai_kelime` | AI kelime evrimi `/ai/kelime-evrimi/*`. |
| `ai_speech` | AI sesli okuma analizi `/ai/speech/*` — metin `analiz_metinler`'den. |
| `ai_kitap_zeka` | AI kitap zekası `/ai/kitap-zeka/*`. |
| `ai_oyunlastirma` | AI oyunlaştırma/evren/okuma-terapisi `/ai/evren/*`. |
| `ai_dikkat_arkadas` | AI dikkat takibi + arkadaş sohbeti `/ai/dikkat/*, /ai/arkadas/*`. ⚠️ **duplike route** (bölüm 8). |
| `hedef` / `gorev` | Hedefler `/hedefler/*` + görevler `/gorevler/*`. |
| `bildirim` | Bildirim `/bildirimler/*` + tür kayıtları. **Korumalı.** |
| `mesaj` / `mesaj_funnel` | Mesajlaşma `/mesajlar/*` + **veli mesaj funnel'ı** (SMS Faz 1 / WhatsApp Faz 2 iskelet, ONAYLI KUYRUK/KVKK). |
| `kullanici` | İl/harita `/kullanici/il-guncelle, /istatistik/turkiye-harita`. |
| `ders_programi` | Ders programı/serileri. |
| `ogretmen_profil` | Öğretmen profili (finansal alanlar öğrenci/veliye gizli). |
| `meb_kelime` | MEB kelime içe aktarım + AI zenginleştirme (taslak→onay). |
| `instagram_beslemesi` | Instagram beslemesi. |
| `ek_paneller` | Ek paneller. |
| `deyim_atasozu` | Deyim/atasözü havuzu. |
| `muhasebe` | Ödeme paneli + **hakediş/dönem/vergi/avans** (bölüm 7). ADMIN/ACCOUNTANT. |
| `toplu_kayit` | Excel/CSV toplu öğrenci-kur içe aktarımı (taslak→onay). |
| `egitim_turleri` | Eğitim türleri yönetimi. |
| `loglar` | İşlem/giriş logları görünümü (`islem_log`, `giris_log`). |
| `sss` | SSS/Yardım + kullanıcı soru kuyruğu. |
| `sistem` | Bakım modu + public durum ucu. |
| `duyuru` | "Yeni Ne Var" duyuruları. |
| `altyapi` | Altyapı/deploy paneli (GitHub/Vercel — best-effort). |
| `seed` | Başlangıç seed (varsayılan admin + sistem verisi). **Korumalı.** |
| `ai_ceo` | AI CEO paketi (bölüm 6). Alt-modüller: `analiz, miran, deniz, deniz_cozum, deniz_guc, fotograf, karne, kuyruk, mektup, nps, pazar, plan, raporlar, sohbet, yonetici, yonetim, deneyim, hedef, analitik, anomali, ortak, personalar`. |

*(55 modül + 22 ai_ceo alt-modülü. Tümü `registry.json`'da aktif.)*

---

## 5. Veri Modeli Özeti (ana koleksiyonlar — `db.<ad>` kullanımından)

**Kimlik/kişi:** `users` (rol, giriş), `students`, `teachers` — CRM'in üç ana varlığı.
`students.ogretmen_id → teachers.id`. `students.yapilan_odeme` (skaler), `teachers.yapilan_odeme`
("Ödenen" TEK KAYNAK skaleri).

**Muhasebe:** `kur_ucretleri` (kur kaydı: `tutar, ogretmen_pay, ogretmen_odenen` [avans],
`odeme_tamamlanma_tarihi`, `odendi_donem`, `durum`), `payments` (tip=ogrenci/ogretmen ödeme
satırları), `ogretmen_donem_odemeleri` (dönem hakediş ödeme kayıtları), `kur_atlamalari`.

**Analiz/okuma:** `analiz_metinler` (**tek kaynak** okuma metni havuzu; `bolum`=analiz/
okuma_parcalari, `durum`=beklemede/oylama/havuzda/reddedildi, gömülü `sorular`/`acik_sorular`),
`diagnostic_oturumlar` (analiz oturumu; `durum`=devam/tamamlandi, metin snapshot'lı),
`diagnostic_raporlar`, `timi_sonuclar`, `reading_logs`, `okuma_dna`.

**Egzersiz/içerik:** `egzersiz_icerikler`, `egzersiz_oturumlari`, `kelime_tekrar`,
`kelime_ogrenme`, `ai_okuma_parcalari`, `ai_uretilen_sorular`, `sinav_sorulari`,
`meb_kelimeleri`/`meb_kelime_haritasi`, `deyim_atasozu`, `kitaplar`/`kitap_havuzu`/
`kitap_sorulari`, `gelisim_icerik`.

**Oyunlaştırma:** `rozetler`/`kazanilan_rozetler`, `xp_logs`, `gorevler`, `hedefler`.

**AI CEO:** `ai_ceo_oneriler` (öneriler/kuyruk), `ai_ceo_deniz_bulgular` (denetim bulguları),
`ai_ceo_raporlar`, `ai_ceo_planlar`, `ai_ceo_miran`, `ai_ceo_mektuplar`, `ai_ceo_fotograflar`
(sistem anlık görüntüsü). `ai_request_log` (AI çağrı sayacı, özellik-etiketli).

**Sistem/audit:** `sistem_ayarlari` (ayar/toggle **tek kaynağı** — `tip` alanıyla çok amaçlı),
`islem_log` (audit — `core/audit.py:islem_kaydet`), `giris_log` (oturum audit),
`bildirimler`, `duyurular`, `theme_configs`, `backup_history`, `refresh_tokens`,
`push_abonelikleri`, `toplu_kayit_taslaklari`, `sss`/`sss_sorular`, `mesajlar`/
`mesaj_gonderimleri`/`mesaj_sablonlari`, `ai_yuklemeler`.

> Not: birçok "ayar" ayrı koleksiyon değil, `sistem_ayarlari` içinde `tip` ile tutulur
> (ör. `ogretmen_paylari`, `kur_ucretleri`[genel], `timi_puanlama_anahtari`,
> `timi_rapor_metinleri`, `yonetici_kurulum_gorevleri`, `*_temizlik_son`).

---

## 6. AI Katmanı — Ayda / Miran / Deniz (`modules/ai_ceo/`, sıra dışı mimari)

Üç **persona** var (`ai_ceo/personalar.py` — TEK KAYNAK; `gorunur_mu(anahtar, rol)`):

- **Ayda** — CEO / yönetim danışmanı. Görünürlük: **admin + coordinator** (`kapsam=yonetim`).
  Öğretmene görünmez. Deterministik metrik + stratejik analiz/öneri üretir
  (`ai_ceo/analiz.py`, `plan.py`, `raporlar.py`, `mektup.py`, `sohbet.py`).
- **Deniz** — bağımsız **denetçi/müfettiş**. Görünürlük: **yalnız admin** (Denetim sekmesi).
  Ayda'nın çıktılarını + veriyi denetler; **deterministik kontroller + (opsiyonel) AI ikinci
  göz**. **Kendi başına HİÇBİR ŞEY UYGULAMAZ** — bulgu üretir, admin karar verir. Çözüm
  promptları + "Kontrol Et" döngüsü (`deniz.py`, `deniz_cozum.py`, `deniz_guc.py`).
  Bulgular `ai_ceo_deniz_bulgular`.
- **Miran** — sistem danışmanı. Görünürlük: **teacher** (pedagojik) VEYA **accountant**
  (finansal) (`miran.py`). **Rol-bazlı sıkı guard:** teacher → tutar/para **YASAK**;
  accountant → pedagojik veri **YASAK** (`personalar.py:105-134` üslup/tutar sızıntı
  örüntüleri; çıktı bunlara karşı taranır).

**Kısıtlar (kritik):**
- **KVKK:** AI'ya kişisel veri gitmez; öğrenci **takma-ID** (`fotograf.takma_id`) ile
  temsil edilir, iletişim verisi paylaşılmaz.
- **Determinizm önce:** çoğu metrik AI'sız hesaplanır; "sayfa açılışında AI çağrısı yok".
  AI yalnız yorum/öneri/denetim katmanında ve seyrek.
- **Onay guard'ları:** Deniz/Ayda öneri üretir, uygulamaz; mektup/aksiyon ONAY ister.
- **Maliyet:** `core/ai.py` günlük istek limiti (`AI_MAX_DAILY_REQUESTS`), 3 anahtar
  rotasyonu, `ai_request_log`'a **özellik-bazlı** sayaç (Deniz maliyet denetimi bunu kırar).
- **Grounding:** Pazar araştırması (`pazar.py`) Gemini Google Search grounding (opsiyonel,
  kaynaklı, seyrek).

---

## 7. Tamamlanmış Büyük Özellikler (kategori bazlı)

- **Muhasebe — hakediş/dönem:** Veli ödemesi tamamlanınca kur `odeme_tamamlanma_tarihi`
  damgalanır (`_odeme_sonrasi_islem`); dönem hakedişi = damgalı+mühürsüz kurların
  `ogretmen_pay` toplamı (`_donem_kalemleri`); `ogretmen_donem_ode` mühürler +
  `teachers.yapilan_odeme += net`. Ayın 15'i dönem sınırı.
- **Muhasebe — avans ("Öğr. Ödenen"):** kur-bazlı erken ödeme (`kur_ucretleri.ogretmen_odenen`);
  `teachers.yapilan_odeme`'yi DELTA $inc eder (özet "Ödenen" tek kaynak, salt-okunur); hakediş
  tetiğinde avans paydan düşülür (mükerrer ödeme engeli). Kur-yok fallback öğrencide de
  girilebilir. (`PATCH /muhasebe/kur-ucreti/{id}/odenen`, `PATCH /muhasebe/ogrenci/{id}/ogretmen-odenen`.)
- **Muhasebe — vergi:** ödemede vergi/brut/net hesabı + `vergi-backfill` geçişi.
- **Kur geçişi/tamamlama:** üst kura geç (`crm.py`), eğitim-tamamla (mezun); önceki kur
  `durum=tamamlandi`. **Damgasız hakediş bulgusu kalibre edildi:** yalnız (durum=tamamlandi
  VE kalan≈0 VE damga yok) gerçek eksik sayılır (yanlış-pozitif giderildi).
- **Veli mesaj funnel'ı:** SMS (Netgsm) + WhatsApp iskelet, KVKK onaylı kuyruk, birim ücret.
- **Loglar:** `islem_log` (audit) + `giris_log` (oturum) + admin görünümü.
- **SSS/Yardım:** SSS CRUD + kullanıcı soru kuyruğu + admin yanıt.
- **Bakım modu:** `core/bakim.py` + `sistem.py` public durum ucu.
- **TIMI:** Çoklu Zeka Envanteri + deterministik anlatı rapor bankası + şık PDF/ekran + taslak
  yönetimi (rozet/sil/15-gün oto-temizlik) + öğrenci/Analiz görünürlüğü + Ayarlar metin editörü.
- **Hızlı okuma egzersizleri:** blok/gölgeleme/gruplama/takistoskop — ortak `useOkumaMetni`
  hook'u, metin `analiz_metinler` havuzundan.
- **Analiz metin havuzu tek kaynak:** 150 "Akıcı Okuma" metni (`bolum=analiz`); tüm
  egzersizler tek havuzdan; **admin/koordinatör onayı** (`admin-karar`, direkt→havuza /
  oylamaya); AI cevap üretimi + dayanak cümle + denetim örneklemi; yedek/temizle admin paneli.
- **Okuma analizi oturum yönetimi:** yarım (tamamlanmamış) analiz silme (başlatan öğretmen/
  admin) + 15 gün oto-temizlik (ortak `core/temizlik.py`) + Anlama sorularının metnin altına
  ferah yerleşimi.
- **AI CEO paketi (MEGA):** Ayda/Miran/Deniz personaları + karar kuyruğu + yönetim skoru +
  stratejik plan + kurul analitiği + NPS + öğretmen deneyim görevleri + pazar araştırması
  (grounding).
- **Datetime kök düzeltmesi:** naive/aware karışımı → tek aware-UTC standardı (`core/zaman.py`).
- **Rozet sistemi:** veri-odaklı rozet CRUD + emoji→ikon migrasyonu (Faz A+B tamam).

---

## 8. Bilinen Açık İşler / Yarım Kalanlar (kod + auto-memory taramasıyla)

1. **⚠️ `ai_dikkat_arkadas.py` — DUPLİKE/ölü route (DOĞRULANDI):** `POST /ai/dikkat/kaydet`
   **hem satır 193 hem 251**'de; `GET /ai/dikkat/gecmis/{ogrenci_id}` **hem 240 hem 355**'te
   tanımlı. FastAPI son tanımlananı kullanır → ilk implementasyonlar **ölü kod**. Hangisinin
   kanonik olduğu **kullanıcı kararı bekliyor, düzeltilmedi** (memory:
   `kitap-aidikkat-duplike-route-catismasi`).
2. **Funnel — canlı SMS bekliyor:** `mesaj_funnel.py` kod tamam + **mock test**. Canlı SMS
   için Netgsm hesabı + API anahtarı (`NETGSM_*` env) gerekli; REST detayları varsayımsal.
   WhatsApp "**Faz 2 iskelet**" (tam entegrasyon yok). (memory: `funnel-netgsm-gereksinim`).
3. **Analiz havuzu 4-adım runbook PROD'da çalıştırılmadı:** Ayarlar → "Analiz Havuzu Bakımı"
   panelinden **yedek → import → AI cevap üret → tam temizle** adımlarını **admin canlıda
   çalıştırmalı** (AI cevap adımı prod Gemini anahtarı gerektirir; local anahtar geçersizdi).
   (memory: `analiz-metin-havuzu-tek-kaynak`).
4. **Cron kurulumu opsiyonel:** `/timi/gunluk-temizlik` + `/diagnostic/gunluk-temizlik`
   token-korumalı; harici cron (cron-job.org) kurulmadıysa yalnız ilk-istek throttle çalışır.
5. **Rozet DB toplu temizliği:** emoji→ikon migrasyonunda eski DB kayıtlarının toplu temizliği
   **opsiyonel/reddedildi** (memory: `rozet-ikon-faz-b`).
6. **`admin-karar` `direkt` yeni davranışı:** `direkt=false → oylama` yeni eklendi; öğretmen
   oylama akışının (`texts/oy`, >%60) uçtan uca canlı testi **yapılmadı** (smoke var).
7. **"Faz 2/Faz 3" işaretli bloklar:** `rozet.py` (FAZ 3), `tema.py` (FAZ 3 yönetim),
   `mesaj_funnel.py` (Faz 2 WhatsApp) — kısmi/iskelet.
8. **`opsiyonel` işaretli AI tarama blokları:** `ai_bilgi_tabani.py:1256/1480` "tüm kelimeleri
   tara" opsiyonel yollar (maliyet nedeniyle kapalı olabilir).
9. **Genel:** TODO/FIXME işareti kod tabanında **bulunamadı** (grep temiz); açık işler
   çoğunlukla docstring "opsiyonel/Faz" notları + memory'de.

---

## 9. Test ve Doğrulama Konvansiyonları

- **Smoke testleri:** `appbackend/tests/test_*_smoke.py` (**88 test dosyası**). İzole test DB,
  kendi `check(...)` fonksiyonu, `SONUC: X/Y` + non-zero exit. Çalıştırma:
  ```
  cd appbackend
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_<ad>_smoke.py
  ```
  (Windows'ta `PYTHONIOENCODING=utf-8` **zorunlu** — Türkçe çıktı cp1254 hatası verir.)
- **Route regresyonu:** `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/route_snapshot.py`
  (toplam route sayısını verir — şu an **557**). Route sayısı beklenmedik düşerse regresyon.
- **Açılış doğrulaması:** `python -c "import server"` (loop'suz import — Python 3.14 tuzağını
  yakalar) + kısa `uvicorn server:app` boot ("Application startup complete").
- **Frontend build:** `cd frontend && CI=false npm run build` (temiz derleme = "Compiled
  successfully").
- **Para-akışı regresyon süiti (muhasebe değişikliğinde ZORUNLU):** `test_hakedis_odeme`,
  `test_muhasebe_odenen_duzelt`, `test_payments_hakedis`, `test_ogretmen_donem`, `test_muhasebe`,
  `test_ogretmen_odenen`, `test_ai_ceo_hakedis_kalibrasyon`, `test_ogretmen_detay`.
- **"Doğrulama turu" deseni:** kullanıcı bazen kanıt tablosuyla rapor ister — her madde için
  **Durum (TAM/KISMİ/EKSİK) | Kanıt (dosya:satır/route/test) | Eksik kalan**. İddiaları
  dosya/route/test ile doğrula, tahmin etme. Onay gerektiren adımlarda önce rapor, sonra "şimdi
  tamamlayayım mı?" diye sor.
- **Determinizm:** testler `Date.now()`/gerçek AI'ya bağlı olmasın; AI çağrıları mock'lanır
  (`call_claude` monkeypatch), `core.zaman` kullanılır.

---

## 10. Riskli / Kırılgan Noktalar

1. **İki Render servisi karışıklığı:** canlı = **`oba-backend-2026`** (production branch);
   `oba-egitim-backend` **kullanılmıyor**. Yanlış serviste log/deploy incelemek zaman kaybı
   yaratır. *(Kullanıcı beyanı.)*
2. **Mongo kimlik-bilgisi rotasyonu:** `MONGO_URL` kodda gömülü değil (Render env). Rotasyon
   gerekirse **hem doğru Render servisinin (oba-backend-2026) hem de** varsa yerel/başka
   ortamların env'i güncellenmeli; aksi halde Atlas auth hatası (bugün yaşanan tip).
3. **Python 3.14 import-anı loop tuzağı:** modül import'unda `get_event_loop()` çağıran her
   kod açılışı çökertir. `core/db.py` düzeltildi (lazy GridFS); benzer desen eklenmemeli.
   `runtime.txt` yok → Render Python'u sürpriz güncellenebilir.
4. **Modül sırası (`registry.json`):** catch-all/duplike route'lar sıraya duyarlı; yeni modül
   eklerken sırayı bilinçli seç. `ai_dikkat_arkadas.py`'deki duplike route buna örnek risk.
5. **`teachers.yapilan_odeme` çoklu yazar:** manuel PATCH + dönem-ödeme `$inc` + `payments
   tip=ogretmen` + kur-avans DELTA. Yeni "ödenen" kaynağı eklerken **mükerrer sayım** riski —
   avansta netleme buna göre kuruldu.
6. **`analiz_metinler` silme:** geçmiş ilerleme `diagnostic_oturumlar`/`diagnostic_raporlar`
   içinde **snapshot'lı** olduğu için silme geçmişi bozmaz; ama snapshot'sız yeni akış
   eklenirse bu güvence kaybolur.
7. **AI maliyet/limit:** toplu AI işleri (ör. 150 metnin cevap üretimi) `AI_MAX_DAILY_REQUESTS`
   + Render HTTP timeout'una takılabilir → parti/zaman-bütçeli tasarla.
8. **CLAUDE.md `datetime.utcnow()` yasağı:** ihlali sessiz yanlış hesap + "naive/aware" çökmesi
   üretir; yeni kodda **daima `core.zaman`**.
9. **Monolitik `App.js` (~14k satır):** düzenlemeler satır-kayması riski taşır; değişiklik
   öncesi grep ile güncel satır bul, küçük hedefli edit yap.

---

### Rapor durumu (kullanıcıya)
- **Satır sayısı:** bu dosya ~290 satır.
- **Tam/sağlam bölümler:** 1, 2, 4, 5, 6, 7, 8, 9, 10 (kod/route/koleksiyon/memory ile doğrulandı).
- **Kısa/zayıf kalan bölümler:** **Bölüm 3** — Render servis adları ve "Mongo Atlas auth
  sorunu" **kullanıcı beyanına** dayanıyor, repo'da doğrudan kanıt yok (TEYİT EDİLEMEDİ olarak
  işaretlendi). GridFS/Python 3.14 açılış düzeltmesi kod düzeyinde doğrulandı.
- **Ek doğrulama önerisi:** Vercel'in izlediği branch ve Render env değişkenlerinin gerçek
  değerleri yalnız hosting panelinden görülebilir (repo dışı).
