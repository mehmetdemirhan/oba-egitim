/**
 * grafikAciklamalari — Dashboard + Muhasebe grafik/kart açıklamaları (tek kaynak).
 *
 * Her giriş: { nasil: "...", ne: "..." }
 *   nasil = "Nasıl hesaplanır" → verinin kaynağı + hesap kuralı (KODLA BİREBİR).
 *   ne    = "Ne işe yarar"     → yöneticinin bu grafikten okuyacağı karar (1-2 cümle).
 *
 * ÖNEMLİ: nasil metinleri backend hesap mantığıyla (dashboard.py / muhasebe.py /
 * kullanici.py) birebir tutarlı olmalı. Kuralı değiştirirsen metni de güncelle.
 */
const grafikAciklamalari = {
  // ── Ana Dashboard ──
  risk: {
    nasil: "Öğrencinin son okuma etkinliğine göre risk skoru üretilir. 'North Star' = son 7 günde en az 4 gün okuyan aktif öğrenci sayısı.",
    ne: "Hangi öğrencilerin ilgi kaybettiğini erken görüp temas kurman için. Yüksek risk arttıysa müdahale zamanı.",
  },
  sayilar: {
    nasil: "Arşivlenmemiş kayıtların anlık toplamı: toplam öğrenci, öğretmen ve kurs sayısı.",
    ne: "Kurumun büyüklüğünü ve büyüme/erime eğilimini tek bakışta görmek için.",
  },
  bu_ay: {
    nasil: "Koordinatör: bu ay olusturma_tarihi bu aya düşen yeni öğrenci sayısı. Admin: bu ay tahsil edilen ödeme toplamı.",
    ne: "Ayın büyüme (yeni kayıt) veya nakit (tahsilat) performansını anlık takip için.",
  },
  finansal_durum: {
    nasil: "Öğrencilerden alınacak toplam alacak (yapılması gereken − yapılan) ile öğretmenlere ödenecek toplam borç yan yana.",
    ne: "Alacak/borç dengesini görüp nakit ihtiyacını öngörmek için.",
  },
  aylik_istatistik: {
    nasil: "Ay bazında yeni öğrenci sayısı (olusturma_tarihi) ve o ayın geliri (tahsilat).",
    ne: "Mevsimsellik ve büyüme trendini görüp kampanya/kapasite planlamak için.",
  },
  yeni_vs_kuratlayan: {
    nasil: "Bu ay yeni kayıt olan öğrenci sayısı ile bu ay bir üst kura geçen (kur atlayan) öğrenci sayısı.",
    ne: "Büyümenin yeni müşteriden mi yoksa mevcutların ilerlemesinden mi geldiğini ayırt etmek için.",
  },
  huni: {
    nasil: "Her öğrencinin tamamladığı kurlar tarih sırasına dizilir. N. basamak = N. kuru tamamlayan öğrenci sayısı. Geçiş oku = bir sonraki kura da başlayanlar. 'Beklemede' = kuru bitireli 30 günden az olan, henüz sonraki kura geçmemiş öğrenciler. Geçiş oranı = geçen ÷ (tamamlayan − beklemede) × 100 (bekleme penceresindekiler paydadan düşülür).",
    ne: "Hangi kur geçişinde öğrenci kaybı yaşandığını görüp o basamağa yenileme kampanyası kurgulamak için.",
  },
  yenileme_trend: {
    nasil: "Ay bazında yenileme oranı: o ay bir kuru tamamlayanların, 30 günlük bekleme penceresi düşülerek, bir sonraki kura geçme yüzdesi.",
    ne: "Yenileme performansının aydan aya iyileşip iyileşmediğini izlemek için.",
  },
  satis_basarisi: {
    nasil: "Aylık satılan kur = o ay yeni kayıt olan öğrenci + o ay kur atlama (kur_gecis/manuel) sayısı. Yenileme oranı huni geçiş oranıyla aynı kuralla; beklenen gelir = satılan kur × genel kur ücreti.",
    ne: "Toplam satış hacmini (yeni + yenileme) ve tahmini geliri birlikte görüp hedefle karşılaştırmak için.",
  },
  nakit_akisi: {
    nasil: "Ay bazında tahsilat, tahsilattan hesaplanan vergi, öğretmenlere yapılan ödeme; net = tahsilat − vergi − öğretmen ödemesi.",
    ne: "Kasaya giren-çıkan parayı ay ay görüp likidite yönetmek için.",
  },
  yaslandirma: {
    nasil: "Açık (borçlu) kurların yaşı = kur başlangıç tarihinden bugüne geçen gün. 0-30 / 31-60 / 60+ gün kovalarına ayrılır.",
    ne: "Eskiyen (60+ gün) alacakları görüp tahsilat önceliği vermek için.",
  },
  ogretmen_performans: {
    nasil: "Öğretmen başına aktif öğrenci (arşivsiz), geciken kur (35 günden eski açık kur) ve yenileme oranı. Tamamlanan kur 3'ten azsa oran 'yetersiz veri' sayılır.",
    ne: "Öğretmenleri yenileme ve geciken tahsilat açısından kıyaslayıp destek/geri bildirim vermek için.",
  },
  egitim_turu_dagilimi: {
    nasil: "Aktif öğrenciler (arşivli + mezun hariç), kayıttaki 'aldığı eğitim' türüne göre gruplanır; en çoktan aza sıralı ilk türler gösterilir.",
    ne: "Hangi programların büyümeyi taşıdığını görüp kapasite ve tanıtımı buna göre yönlendirmek için.",
  },
  rozet_durumu: {
    nasil: "Her öğretmenin kazandığı öğretmen rozeti sayısı / tanımlı toplam rozet sayısı. Rozet koşulları sistem ayarlarından yönetilir.",
    ne: "Öğretmenlerin platform hedeflerine ne kadar ulaştığını görüp tanıma/teşvik için.",
  },
  veli_degerlendirme: {
    nasil: "Öğretmene bağlı öğrencilerin velilerinin doldurduğu anketlerin ortalama puanı (5 üzerinden) ve tavsiye oranı; anket sayısı parantezde.",
    ne: "Veli memnuniyetini öğretmen bazında görüp düşük memnuniyette destek/geri bildirim vermek için.",
  },
  sinif_dagilimi: {
    nasil: "Aktif öğrenciler (arşivli ve mezun HARİÇ) sınıf seviyesine göre sayılır. 1-8. sınıf ayrı; sınıfı boş/aralık dışı olanlar 'Belirsiz' kovasında. Yüzde = kova ÷ toplam.",
    ne: "Hangi sınıf seviyesinde yoğunlaştığını görüp içerik ve kampanyaları o kitleye göre planlamak için.",
  },

  // ── TR Harita ──
  harita_ogrenci: {
    nasil: "Arşivsiz öğrenciler il bazında sayılır (kimlik dönmez, yalnız agregat sayı). İli boş olanlar hariç.",
    ne: "Öğrenci yoğunluğunun coğrafi dağılımını görüp bölgesel büyüme/tanıtım kararı almak için.",
  },
  harita_ogretmen: {
    nasil: "Arşivsiz öğretmenler il bazında sayılır (kimlik dönmez, yalnız agregat sayı). İli boş olanlar hariç.",
    ne: "Öğretmen kapasitesinin coğrafi dağılımını görüp eksik bölgelerde öğretmen kazanımı planlamak için.",
  },

  // ── Muhasebe KPI ──
  m_alinmayan: {
    nasil: "Görünür (gizlenmemiş) kur satırlarında kalan > 0 olan kayıtların sayısı ve toplam kalan tutarı. Tamamlanıp tümü ödenen kurlar sayılmaz.",
    ne: "Bekleyen tahsilatın kaç öğrencide ve ne kadar olduğunu görüp takip için.",
  },
  m_beklenen: {
    nasil: "Tüm öğrencilerin 'yapılması gereken ödeme' toplamı.",
    ne: "Dönemin toplam beklenen tahsilat hedefini görmek için.",
  },
  m_tahsil: {
    nasil: "Tüm öğrencilerin 'yapılan ödeme' (brüt) toplamı.",
    ne: "Şu ana kadar toplanan brüt tutarı görmek için.",
  },
  m_vergi: {
    nasil: "Öğrenci ödemelerinden hesaplanan vergi toplamı: kayıtlı vergi varsa o, yoksa miktar × güncel vergi oranı.",
    ne: "Devlete gidecek vergiyi ayırıp net kasayı doğru okumak için.",
  },
  m_bekleyen: {
    nasil: "Beklenen tahsilat − tahsil edilen (negatifse 0).",
    ne: "Henüz toplanmamış tahsilatın büyüklüğünü görmek için.",
  },
  m_ogretmene_odenecek: {
    nasil: "Tüm öğretmenlerin 'yapılması gereken ödeme' toplamı.",
    ne: "Öğretmenlere olan toplam yükümlülüğü görmek için.",
  },
  m_ogretmene_odenen: {
    nasil: "Tüm öğretmenlere 'yapılan ödeme' toplamı.",
    ne: "Öğretmenlere şu ana kadar ödenen tutarı görmek için.",
  },
  m_net_kasa: {
    nasil: "Net tahsilat (brüt tahsilat − vergi) − öğretmenlere yapılan ödeme.",
    ne: "Vergi ve öğretmen ödemesi düşüldükten sonra kasada gerçekten kalan parayı görmek için.",
  },
};

export default grafikAciklamalari;
