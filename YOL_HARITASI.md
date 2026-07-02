# OBA Eğitim — Geliştirme Yol Haritası

> Hedef: (1) Öğrencinin kendi seviyesindeki Türkçe kelimeleri öğrenmesi ve okuma
> becerisini artırması, (2) öğretmenin bu süreçleri kolay/verimli yönetmesi,
> (3) öğrencilerin **kur** artırarak ilerlemesi, (4) yöneticinin öğretmen/öğrenci
> yönetiminin kolay olması.
>
> Bu belge, sistemin baştan aşağı taranmasıyla (backend + frontend) çıkarılan
> mevcut durum ve öncelikli geliştirme planıdır. Her görevde somut dosya/endpoint
> referansı, kabul kriteri ve kaba efor tahmini vardır.

---

## Mevcut Durum — Teşhis

**Güçlü yapı taşları (korunacak):** 34 tipli veri-güdümlü egzersiz motoru
(`core/egzersiz_tipleri.py`), Leitner aralıklı tekrar (`modules/ai_kelime.py` +
`kelime_tekrar`), 7 boyutlu Okuma DNA (`ai_kocluk.py`), diagnostic/WPM ölçümü
(`diagnostic.py`), AI kitap→kelime çıkarma (`ai_bilgi_tabani.py`, Türkçe stemming
boru hattı), oyunlaştırma (`ai_oyunlastirma.py`), merkezî+deflasyonlu puan ekonomisi
(`core/sistem.py`).

**Üç yapısal kopukluk (bu yol haritasının odağı):**
1. **Kur mekaniği kırık** — sizin ilerleme ekseniniz en zayıf halka (Faz 1).
2. **Kapalı adaptif döngü yok** — ölçüm (DNA/WPM) içerik zorluğunu/kelime seçimini
   otomatik ayarlamıyor; kelime havuzu ↔ Leitner ↔ egzersiz sonuçları üç ayrı silo (Faz 3).
3. **Yönetim sürtünmesi** — çift veri modeli (`users` vs `teachers/students`),
   toplu işlem yok, kur/kelime araçları UI'ya bağlı değil (Faz 2, 4).

---

## Öncelik Özeti

| Faz | Başlık | Neden | Efor |
|---|---|---|---|
| **0** | Güvenlik & hijyen | 🔴 Auth'suz CRUD endpoint'leri | S |
| **1** | Kur sistemini onar (çekirdek) | İlerleme ekseni; backend %70 hazır | M |
| **2** | Admin yönetim kolaylığı | En büyük yönetim sürtünmesi | M |
| **3** | Öğrenme kapalı döngüsü | Öğrenme kalitesi (kelime+okuma) | M–L |
| **4** | Öğretmen verimliliği | Günlük iş akışı | M |
| **5** | Altyapı / teknik borç | Güven & ölçek | L |

S=küçük (1-2 gün), M=orta (3-7 gün), L=büyük (1-2+ hafta). Fazlar sırayla; içindeki
görevler çoğunlukla bağımsız.

---

## FAZ 0 — Güvenlik & Hijyen (🔴 önce bu)

### 0.1 — Auth'suz CRM/dashboard endpoint'lerini koru
- **Sorun:** `modules/crm.py` içinde `create_teacher` (:181), `get_teachers` (:187),
  `update_teacher` (:214), `delete_teacher` (:225), `create_course` (:343) ve
  `modules/dashboard.py` `/dashboard` (:39) `Depends(...)` **içermiyor** → kimlik
  doğrulamasız çağrılabiliyor (öğretmen oluştur/sil, mali özet oku).
- **Yapılacak:** Bu uçlara `Depends(require_role(...))` / `Depends(get_current_user)`
  ekle (öğrenci uçlarındaki desenle aynı). Yazma uçları admin/coordinator,
  dashboard en az giriş yapmış kullanıcı.
- **Kabul:** Token'sız çağrı 401/403; ilgili smoke testleri güncellenip yeşil.
- **Efor:** S

### 0.2 — Şifre sıfırlama borcunu kapat (kalan iş)
- `auth_api.py` forgot-password prod'da e-posta/SMS göndermiyor (bkz. `ILERLEME.md`
  teknik borç). Faz 2.3 (admin şifre sıfırlama) ile birlikte ele alınacak.

---

## FAZ 1 — Kur Sistemini Onar (çekirdek ilerleme ekseni)

> Şu anki durum: `students.kur` **serbest metin** ("Kur 2"); iki kopuk yol —
> diagnostic (`diagnostic.py:335-386`) kur'u yazar ama `kur_atlamalari`'na
> KAYIT ATMAZ; manuel `/kur/atla` (`ilerleme.py:190-217`) `kur_atlamalari`'na yazar
> ama **frontend hiç çağırmaz**. Kriterler (`/kur/kontrol` `ilerleme.py:142-186`:
> 12 görev, %75 anlama, 4 kitap, 10 streak) tanımlı ama **zorlanmıyor**. Kur ↔
> kelime bağı **yok** (`kelime_secici.py` sadece `sinif`). `server.py:167-168`
> `_original_kur_atla = None # placeholder`.

### 1.1 — Kur'u yapılandırılmış ve tek-kaynağa indir
- **Yapılacak:** `students.kur`'u **tam sayı** (1..N) olarak normalize et (mevcut
  "Kur N" stringlerini migrasyonla int'e çevir). Tüm kur yazımı TEK fonksiyondan
  geçsin (`ilerleme.py` içinde `_kur_guncelle(ogrenci_id, yeni_kur, kaynak,
  ogretmen_id)`): hem `students.kur`'u günceller hem `kur_atlamalari`'na kayıt atar.
- **Dosyalar:** `ilerleme.py`, `diagnostic.py:376`, migrasyon script'i (mevcut
  `migrate_puan_deflasyon.py` deseni).
- **Kabul:** Kur yalnızca artabilir; her değişiklik `kur_atlamalari`'nda; smoke.
- **Efor:** M

### 1.2 — İki yolu birleştir (diagnostic → kur_atlamalari)
- **Yapılacak:** `diagnostic.py` complete akışı kur değiştirdiğinde `_kur_guncelle`'yi
  çağırsın → öğretmen kur puanı/rozeti (`kur_ilk/kur_20...`, ağırlık `kur_basi`)
  gerçek kullanımda **birikir** (şu an sadece seed verisiyle görünüyor).
- **Kabul:** Diagnostic'te kur atlayınca `/ogretmen/basarilarim` kur sayısı artar.
- **Efor:** S (1.1 sonrası)

### 1.3 — Öğretmen paneline "Kur Atlat" ekranı
- **Yapılacak:** Öğrenci detayında (`App.js:4006-4181`) **Kur Hazırlık kartı**:
  `GET /kur/kontrol/{id}` kriterlerini checklist göster (12 görev, %75 anlama,
  4 kitap, 10 streak — ✓/✗ + mevcut değer). Kriterler tamamsa (veya öğretmen
  override) **"Kur Atlat" butonu** → `POST /kur/atla`.
- **Dosyalar:** `frontend/src/App.js` (öğrenci detay), backend hazır.
- **Kabul:** Öğretmen UI'dan kur atlatabiliyor; kriterler görünüyor.
- **Efor:** M

### 1.4 — Kur'u kelime seçimine bağla (★ "kendi seviyesinde kelime")
- **Yapılacak:** `core/kelime_secici.py`'ye kur parametresi ekle; kelime `zorluk`
  ve/veya sınıf kademesi öğrencinin kuruna göre filtrelensin (düşük kur → kolay
  kelime, yüksek kur → zor). Şu an seçim yalnız `sinif` + kelime `zorluk`'a bakıyor.
- **Kabul:** Aynı sınıfta farklı kurdaki iki öğrenci farklı zorlukta kelime alıyor.
- **Efor:** M

### 1.5 — Kur tavanını aç ve şemasını tanımla
- **Yapılacak:** Diagnostic önerisi "Kur 3"te tıkanıyor (`diagnostic.py:57-64`);
  kur kademelerini (1..N) ve her kademenin kelime/okuma hedefini `sistem_ayarlari`'na
  taşı (admin ayarlanabilir). Sabit eşikleri koddan çıkar.
- **Efor:** M

---

## FAZ 2 — Admin Yönetim Kolaylığı

> Şu anki durum: Her kişi için **iki ayrı kayıt** — giriş hesabı (`users`,
> `auth_api.py`) ve CRM kaydı (`teachers`/`students`, `crm.py`) — iki farklı
> sekmede, iki formla. `linked_id` bağı `App.js:48` state'te var ama **formda
> input yok**; bağ pratikte seed'e bağımlı.

### 2.1 — Tek adımda "öğretmen/öğrenci ekle"
- **Yapılacak:** Tek formdan hem `users` hesabı hem CRM kaydı oluşturan bir akış
  (backend'de birleşik endpoint veya frontend'de iki çağrı + `linked_id` otomatik
  bağlama). `linked_id` alanını UI'da yönet.
- **Dosyalar:** `auth_api.py`, `crm.py`, `App.js` (UserManagement `:45`, öğrenci/
  öğretmen formları).
- **Kabul:** Tek formla giriş yapabilen + CRM'de görünen öğretmen/öğrenci oluşuyor.
- **Efor:** M

### 2.2 — Toplu içe aktarma (CSV/Excel import)
- **Yapılacak:** Öğretmen/öğrenci için CSV/XLSX yükleyip toplu hesap+CRM oluşturma
  endpoint'i + UI. (Şu an hiç yok; sınıf başında yüzlerce kayıt elle giriliyor.)
- **Dosyalar:** yeni `POST /admin/import/{tip}`, `App.js` admin.
- **Kabul:** 50 satırlık CSV tek tıkla içe aktarılıyor; hata raporu dönüyor.
- **Efor:** M

### 2.3 — Kullanıcı düzenleme + admin şifre sıfırlama
- **Yapılacak:** `PUT /auth/users/{id}` (ad/e-posta/telefon/rol düzenleme — şu an
  **yok**, sadece sil-yeniden oluştur) + `POST /auth/users/{id}/sifre-sifirla`
  (admin başka kullanıcının şifresini set edebilsin — şu an yok). Faz 0.2 borcunu
  da kapatır.
- **Kabul:** Admin hesabı düzenleyebiliyor ve şifre sıfırlayabiliyor; 403 korumalı.
- **Efor:** M

### 2.4 — Toplu öğretmen-atama + arama/filtre
- **Yapılacak:** `POST /students/toplu-atama` (öğretmen ayrılınca öğrencileri toplu
  taşı — şu an tek tek). Kullanıcı/öğrenci/öğretmen listelerine isim/e-posta arama
  + öğretmene göre filtre (şu an yok, sadece arşiv toggle).
- **Kabul:** Bir öğretmenin tüm öğrencileri tek işlemle başka öğretmene taşınıyor.
- **Efor:** M

---

## FAZ 3 — Öğrenme Kapalı Döngüsü (kelime + okuma kalitesi)

> Şu anki durum: Kelime seçimi (`kelime_secici.py`) öğrencinin Leitner geçmişini
> kullanmıyor; egzersiz/oyun sonuçları `kelime_tekrar`'ı **beslemiyor**;
> `kelime_bankasi` koleksiyonu **ölü** (`ai_kocluk.py:61` okur ama kimse yazmaz);
> `zorluk_toleransi` sabit 50 (`ai_kocluk.py:81`); iki WPM ölçümü (diagnostic +
> `ai_speech`) entegre değil; `reading_logs` öz-beyan.

### 3.1 — Üç siloyu bağla (kelime ↔ Leitner ↔ egzersiz)
- **Yapılacak:** (a) Egzersiz/oyunda **yanlış yapılan kelime** otomatik `kelime_tekrar`
  Leitner'a kutu 1'de düşsün (`egzersiz_motoro.py` bitir akışı → `ai_kelime.py`).
  (b) `kelime_secici` seçimde Leitner'daki **zayıf/vadesi gelen** kelimeleri
  önceliklendirsin. (c) `kelime_bankasi`'nı ya doldur ya kaldır.
- **Kabul:** Yanlış yapılan kelime sonraki gün tekrarda çıkıyor; seçim geçmişe duyarlı.
- **Efor:** M

### 3.2 — Kapalı adaptif zorluk döngüsü
- **Yapılacak:** DNA/WPM ölçümü sonraki içeriğin zorluğunu ve kelime kademesini
  otomatik ayarlasın (şu an ölçüyor ama **uygulamıyor** — öneri üretip bırakıyor).
  `zorluk_toleransi`'nı gerçek veriden hesapla (sabit 50'yi kaldır).
- **Kabul:** Yüksek başarı → bir sonraki oturum daha zor; düşük → daha kolay.
- **Efor:** L

### 3.3 — Okuma ölçümünü birleştir + öz-beyanı doğrula
- **Yapılacak:** İki WPM kaynağını (diagnostic + `ai_speech`) tek "okuma seviyesi"
  metriğinde birleştir. `reading_logs` öz-beyanına hafif doğrulama (ör. sesli okuma
  / kısa kontrol sorusu ile teyit) — lig/streak bunun üzerine kurulu.
- **Kabul:** Tek birleşik okuma skoru; şişirilmiş dakika azalır.
- **Efor:** M–L

### 3.4 — Öğrenciye birleşik "kelime dağarcığım" göstergesi
- **Yapılacak:** Öğrenci panelinde (`App.js:4874`) öğrenilen kelime (Leitner kutu≥4)
  + okuma seviyesi + kur ilerlemesini tek "gelişim skoru" kartında göster.
- **Efor:** S–M

---

## FAZ 4 — Öğretmen Verimliliği

### 4.1 — MEB Kelime yönetimini öğretmene aç
- **Sorun:** `MebKelimeYonetimi` yalnız `user.role === "admin"` (`App.js:396`) →
  öğretmen kelime havuzunu göremiyor/yönetemiyor.
- **Yapılacak:** Öğretmene (en azından kendi sınıf/kelime kapsamında) okuma/ekleme
  yetkisi; feature-flag ile kontrollü.
- **Efor:** S–M

### 4.2 — Gelişim içeriğinden tek-tık görev ata
- **Yapılacak:** İçerik/kitap/kelime havuzundan "bunu görev olarak ata" kısayolu
  (öğretmen tarafı). Şu an `icerik_id`/link elle giriliyor; toplu atama zaten var
  (`gorev.py:98 /gorevler/toplu`).
- **Efor:** S–M

### 4.3 — AI materyal "üret → ata" akışı öğretmen panelinde
- **Yapılacak:** `ai_uretim.py` (materyal/scaffold/hikaye) çoğunlukla öğrenci
  panelinde tetikleniyor; öğretmenin öğrenci için üretip doğrudan atadığı akışı ekle.
- **Efor:** M

### 4.4 — Otomatik bildirim (cron)
- **Sorun:** Risk/streak/görev tetikleyicileri (`bildirim.py:197
  bildirim_risk_kontrol`) yalnız admin manuel `POST /bildirimler/kontrol` çağırınca
  çalışıyor — cron yok.
- **Yapılacak:** Zamanlanmış tetikleyici (Render cron / APScheduler) — günlük risk
  ve streak bildirimleri öğretmene otomatik gitsin.
- **Efor:** S–M

### 4.5 — Kur hazırlık göstergesi (Faz 1.3 ile birlikte)
- Öğrenci detayında anlama %, 4 kitap, 12 görev, 10 streak kriterlerini "kur
  hazırlık" olarak göster (kriterler hesaplanıyor ama görünmüyor).

---

## FAZ 5 — Altyapı / Teknik Borç

### 5.1 — Norm tablolarını tekilleştir
- Okuma hızı normları 3+ dosyada elle gömülü (`diagnostic.py`, `ai_speech.py`,
  `ai_kocluk.py`, `ai_dikkat_arkadas.py`). Tek kaynağa (`core/` veya
  `sistem_ayarlari`) taşı.
- **Efor:** S–M

### 5.2 — Öğretmen sorgularındaki N+1'leri düzelt
- `ilerleme.py:494-497`, `hedef.py:76` öğrenci başına ayrı `reading_logs` sorgusu;
  `/students` + `/risk-skor/toplu` tüm öğrenciyi çekip client-side filtreliyor
  (`App.js:3910`). Backend'de öğretmen filtresi + toplu aggregate.
- **Efor:** M

### 5.3 — `App.js` (13.544 satır) parçalanması
- Öğretmen paneli / öğrenci detayı / gelişim / analiz ayrı bileşenlere. Bakım ve
  ilk yükleme performansı için. Kademeli yapılabilir.
- **Efor:** L

### 5.4 — `/gelisim/puan-tablosu` rol ayrımı
- Öğretmen + öğrenciyi aynı listede sıralıyor (`gelisim.py:386`); role özgü
  sıralama ekranı.
- **Efor:** S

---

## Önerilen Başlangıç

1. **Faz 0** (güvenlik) — hızlı ve kritik, hemen.
2. **Faz 1** (kur onarımı) — çekirdek hedef, backend'in çoğu hazır, en yüksek getiri.
3. Sonra iş yüküne göre Faz 2 (admin) veya Faz 3 (öğrenme döngüsü).

Her faz sonunda `appbackend/tests/test_*_smoke.py` yeşil kalmalı ve route sayısı
(`tests/route_snapshot.py`) kontrol edilmeli. Büyük her adımdan sonra Türkçe,
açıklayıcı commit.
