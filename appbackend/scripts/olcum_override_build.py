# -*- coding: utf-8 -*-
"""Alt-ajanların HATALI/eksik ürettiği 3 metni (çapraz doğrulama ile tespit
edildi) elle-doğrulanmış içerikle DÜZELTİR → data/olcum_override.json.

Hatalar (olcum_verify.py çıktısı):
  - Eşsiz Şehrin Yankıları : ajan Q1/Q3 soru + Q1/Q10 cevap UYDURDU (kaynak temiz).
  - DUVARLAR…              : ajan Q5-Q9'u boş bıraktı (kaynak tam).
  - İNSAN…                 : Q10 cevap paraphrase; Q3/Q4 cevabı KAYNAKTA YOK.

Tüm soru/cevap metni ilgili PDF'in ham metninden BİREBİR alınmıştır (yalnız PDF
bitişik-kelime birleşmeleri boşlukla ayrıldı). Kaynakta olmayan cevaplar (İNSAN
Q3/Q4) UYDURULMAZ → boş bırakılır; onay ekranından koordinatör tamamlayabilir.
"""
import json
import re
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
HAM = _DATA / "olcum_ham.json"
OUT = _DATA / "olcum_override.json"


def q(no, kat, kat_ham, soru, cevap, subj=False):
    return {"no": no, "kategori": kat, "kategori_ham": kat_ham,
            "soru": soru, "cevap": cevap, "subjektif": subj}


# ── Eşsiz Şehrin Yankıları (8. sınıf) ────────────────────────────────
YANKILAR = [
    q(1, "Hatırlama", "Bilgi (Hatırlama)",
      "Kasabada yaşanan gizemli olayın adı nedir?",
      "Kasabada “kaybolan yankı” olayı yaşanmaktadır; yani kasabada hiçbir sesin yankılanmaması gizemli olay olarak anlatılmaktadır."),
    q(2, "Anlama", "Kavrama (Anlama)",
      "Yaşlı adamın anlattıklarına göre seslerin kaybolmasının nedeni ne olabilir?",
      "Yaşlı adam, vadide bir şeylerin değiştiğini ve seslerin eski yolunu bulamadığını söylemektedir. Bu da seslerin yönünü değiştiren veya engelleyen bir olay yaşandığını düşündürür."),
    q(3, "Uygulama", "Uygulama (Kullanma)",
      "Yaren’in bronz plakada okuduğu cümleden yola çıkarak sesin neden kasabaya geri dönemediğini kendi cümlelerinle açıklayın.",
      "Bronz plakadaki cümle sesin “yolunu kaybettiğini” ifade eder. Bu durum, vadideki doğal yapının değiştiğini, ses dalgalarının eski güzergâhını takip edemediğini ve bu yüzden kasabaya ulaşamadığını gösterir."),
    q(4, "Analiz", "Analiz (Çözümleme)",
      "Yaren’in vadide yaptığı gözlemlerden hangi ipuçları, seslerin yön değiştirdiğini anlamasını sağlamıştır? Metinden en az iki kanıt yazın.",
      "Vadide bazı kaya yüzeylerinin kırılmış veya yer değiştirmiş olduğunu fark etmesi, sesin çarpacağı yüzeylerin değiştiğini göstermiştir. Havanın bile alışılmadık şekilde sessiz olması, ses dalgalarının dağılması yerine başka bir yöne saptığını düşündürmüştür."),
    q(5, "Analiz", "Analiz (Karşılaştırma)",
      "Kasabanın olay öncesi durumu ile olay sonrası durumu arasında ne gibi farklar vardır? En az üç maddede karşılaştırın.",
      "Olay Öncesi: Kasaba canlı ve neşelidir; çocuklar oyun oynarken yankı oluşur; insanlar günlük yaşamlarını sorunsuz sürdürür. Olay Sonrası: Kasaba sessiz ve huzursuz hale gelir; hiçbir ses yankılanmaz; insanlar tedirgin olur ve çözüm aramaya başlar."),
    q(6, "Değerlendirme", "Değerlendirme (Yorumlama)",
      "Kasabalıların Yaren’e ilk başta güvenmemelerini nasıl değerlendirirsiniz? Bu tutumun nedenlerini tartışın.",
      "Kasabalıların temkinli davranması doğal görülebilir; çünkü gizemli bir durum yaşanmaktadır ve tanımadıkları birinin çözüm bulabileceğine dair şüphe duymaları normaldir. Ayrıca geçmişte başarısız denemeler olmuş olabilir. Ancak Yaren’in gözlemlerini ve çabasını görünce güvenmeleri doğru bir tutumdur."),
    q(7, "Değerlendirme", "Değerlendirme (Eleştirel Düşünme)",
      "Yaren’in sesleri geri getirmek için metal levhaları kullanma fikrini ne kadar bilimsel buluyorsunuz? Gerekçeleriyle açıklayın.",
      "Ses dalgalarının yüzeylerden yansıyabildiği bilinen bir fizik kuralıdır. Metal yüzeylerin sesi yönlendirmek için kullanılabilmesi bilimsel olarak mümkündür. Yaren’in fikri bu açıdan mantıklıdır. Ancak gerçek hayatta sesin doğru açıyla yönlendirilmesi için daha detaylı hesaplamalar gerekebilir."),
    q(8, "Yaratma", "Yaratma (Tahmin / Üretme)",
      "Eğer Yaren yanlış bir açıyla levha yerleştirseydi olay nasıl sonuçlanabilirdi? Olası bir senaryo yazın.",
      "Ses kasabaya geri dönmek yerine tamamen başka bir noktaya yönlenebilirdi. Sesin vadi içinde sıkışıp kalması, başka bir kasabada tuhaf bir yankı oluşması veya yankının daha da zayıflaması gibi sonuçlar ortaya çıkabilirdi.", True),
    q(9, "Yaratma", "Yaratma (Alternatif Çözüm)",
      "Yaren’in kullandığı yöntemin dışında kasabanın yankısını geri getirmek için başka hangi çözüm yolları denenebilirdi? En az iki farklı fikir üretin.",
      "Vadinin doğal yapısını inceleyerek çökmüş kayaların eski hâline getirilmesi; yankıyı güçlendirmek için ses yansıtıcı kuleler veya ahşap paneller yerleştirilmesi; sesin yönünü tespit etmek için basit bir akustik ölçüm cihazı yapılması.", True),
    q(10, "Yaratma", "Yaratma (Genelleme)",
      "Bu hikâyeden hareketle, “Küçük bir fikrin büyük bir değişime yol açması” temasını günümüzden bir örnekle açıklayın.",
      "Örneğin geri dönüşüm kutularının okullara yerleştirilmesi fikri küçük bir başlangıçtır; ancak zamanla bütün öğrencilerin bilinçlenmesine, atıkların azalmasına ve çevre farkındalığının artmasına yol açabilir. Küçük bir uygulama büyük bir sosyal etki oluşturur.", True),
]

# ── DUVARLARIN ARASINDA BÜYÜYEN SES (Lise) ───────────────────────────
DUVARLAR = [
    q(1, "Hatırlama", "Hatırlama",
      "Arda’nın okul çıkışlarında kulaklık takmasının temel nedeni nedir?",
      "Arda, kulaklığı müzik dinlemek için değil, dış dünyayla arasına görünmez bir duvar örmek, insanlarla iletişim kurmak zorunda kalmamak ve kendini korumak için takmaktadır."),
    q(2, "Hatırlama", "Hatırlama",
      "Edebiyat öğretmeni öğrencilerden nasıl bir öykü yazmalarını istemiştir?",
      "Öğretmen, öğrencilerden kendilerini anlatan ancak bunu doğrudan değil, bir karakter üzerinden yapan bir öykü yazmalarını istemiştir."),
    q(3, "Anlama", "Anlama",
      "Metinde Arda’nın sessizliği nasıl bir “savunma biçimi” olarak açıklanmaktadır?",
      "Arda, söylediklerinin dikkate alınmayacağından ve havada kalacağından korktuğu için susmaktadır. Bu nedenle sessizlik, onun için reddedilme ve anlaşılmama korkusuna karşı geliştirdiği bir savunma biçimi hâline gelmiştir."),
    q(4, "Anlama", "Anlama",
      "Öğretmenin “Yazmak senin sesin olabilir.” sözü Arda için ne anlama gelmektedir? Açıklayınız.",
      "Bu söz, Arda’nın kendini sözlü olarak ifade edemediği duygularını yazı yoluyla ifade edebileceğini, yazının onun için bir iletişim ve kendini anlatma aracı olabileceğini fark etmesini sağlamıştır."),
    q(5, "Uygulama", "Uygulama",
      "Arda’nın yaşadığı duruma benzer bir durumda olan bir öğrencinin kendini ifade edebilmesi için metinden hareketle iki somut yol öneriniz.",
      "Duygu ve düşüncelerini yazı, günlük veya hikâye yoluyla ifade etmeye çalışmak; güvendiği bir öğretmen ya da arkadaşla düşüncelerini paylaşmak. Metnin temel düşüncesiyle uyumlu farklı somut öneriler de kabul edilir.", True),
    q(6, "Analiz", "Analiz",
      "Arda’nın konuşmak yerine yazmayı tercih etmesinin nedenlerini metne dayalı olarak analiz ediniz.",
      "Arda, konuşurken anlaşılmayacağını düşündüğü için yazmayı tercih etmektedir. Yazı, ona düşüncelerini düzenleme, duygularını daha rahat aktarma ve kendini güvende hissetme imkânı vermektedir. Bu nedenle yazmak, Arda için daha kontrollü ve güvenli bir ifade biçimidir."),
    q(7, "Analiz", "Analiz",
      "Metnin başındaki Arda ile metnin sonundaki Arda arasında hangi içsel değişimler vardır? Karşılaştırarak açıklayınız.",
      "Metnin başında Arda, sessizliğini bir kaçış ve zorunluluk olarak yaşarken; metnin sonunda sessizliğini bir özellik olarak kabul etmiş, istediğinde konuşabileceğini fark eden daha bilinçli ve özgüvenli bir birey hâline gelmiştir."),
    q(8, "Değerlendirme", "Değerlendirme",
      "Sizce Arda’nın sessizliğini bir eksiklik değil, bir özellik olarak görmesi doğru bir bakış açısı mıdır? Metne dayanarak görüşünüzü gerekçelendiriniz.",
      "Evet, doğru bir bakış açısıdır. Çünkü herkesin kendini ifade etme biçimi farklıdır. Sessizlik, Arda’nın değersiz olduğu anlamına gelmez; aksine onun kişiliğinin bir parçasıdır. Metinde bu farkındalık Arda’ya güç kazandırmıştır. Metne dayalı gerekçelendirme yapıldığı sürece farklı görüşler kabul edilebilir.", True),
    q(9, "Değerlendirme", "Değerlendirme",
      "Öğretmenin Arda’ya yaklaşımını eğitim açısından değerlendiriniz. Bu yaklaşımın Arda üzerindeki etkisi sizce yeterli midir?",
      "Öğretmenin yaklaşımı olumludur; çünkü Arda’yı yargılamadan, yeteneğini fark ederek desteklemiştir. Bu yaklaşım, Arda’nın kendini ifade etmesine ve özgüven kazanmasına katkı sağlamıştır."),
    q(10, "Yaratma", "Yaratma",
      "Bu öykünün temasını yansıtan yeni bir başlık öneriniz ya da Arda’nın hikâyesine 1 paragrafla alternatif bir son yazınız.",
      "Örnek başlık: “Sessizliğin İçindeki Güç”, “Kelimelere Dönüşen Sessizlik”. Alternatif son için ölçüt: Metnin ana temasına uygun olmalı; Arda’nın içsel gelişimini yansıtmalı; özgün olmalı. Öğrencinin metinle bağlantılı, yaratıcı ürünleri kabul edilir.", True),
]

# ── İNSAN–DOĞA İLİŞKİSİNİN DÖNÜŞÜMÜ (Lise) ────────────────────────────
# NOT: Q3 ve Q4 (Anlama) cevapları KAYNAK PDF'de YOKTUR → boş bırakılır (uydurulmaz).
INSAN = [
    q(1, "Hatırlama", "Hatırlama",
      "Metne göre insan–doğa ilişkisinin dönüşümünde etkili olan üç temel tarihsel dönem hangileridir?",
      "Tarih öncesi dönem (avcılık–toplayıcılık); Tarım devrimi; Sanayi devrimi (ve modern dönemle birlikte küreselleşme)."),
    q(2, "Hatırlama", "Hatırlama",
      "Sanayi devriminin doğa üzerindeki etkilerinden metinde hangileri örnek olarak verilmiştir?",
      "Fosil yakıtların yaygın kullanımı; hava kirliliği; su kaynaklarının kirlenmesi; fabrikalaşma ve hızlı şehirleşme; tüketim alışkanlıklarının artması."),
    q(3, "Anlama", "Anlama",
      "Yazar, doğanın tarihsel süreçte “kaynak” olarak algılanmasının ne anlama geldiğini nasıl açıklamaktadır?",
      ""),   # Cevap kaynak PDF'de yok — koordinatör onay ekranından tamamlar.
    q(4, "Anlama", "Anlama",
      "Metne göre iklim değişikliğinin yalnızca çevresel değil, aynı zamanda toplumsal bir kriz olmasının nedeni nedir?",
      ""),   # Cevap kaynak PDF'de yok — koordinatör onay ekranından tamamlar.
    q(5, "Uygulama", "Uygulama",
      "Metinden yararlanarak, bir lise öğrencisinin günlük yaşamında doğa–insan dengesini korumaya yönelik uygulayabileceği iki somut davranış yazınız.",
      "Geri dönüşüme dikkat etmek ve atıkları ayrıştırmak; enerji tasarrufu yapmak (gereksiz ışıkları kapatmak, suyu bilinçli kullanmak). Metinle uyumlu farklı somut örnekler kabul edilir.", True),
    q(6, "Analiz", "Analiz",
      "Tarım devrimi ile sanayi devriminin insan–doğa ilişkisi üzerindeki etkilerini karşılaştırarak analiz ediniz.",
      "Tarım devrimi: Doğaya müdahale başlamış, insan yerleşik yaşama geçmiş ve üretici konuma gelmiştir. Sanayi devrimi: Doğa üzerindeki baskı çok artmış, kaynaklar hızla tüketilmiş ve çevresel bozulma büyük ölçekli hâle gelmiştir. Sanayi devriminin etkisi tarım devrimine göre daha yıkıcıdır."),
    q(7, "Analiz", "Analiz",
      "Metinde bireysel çabalar ile kamusal politikaların çevre sorunlarının çözümündeki rolü nasıl ilişkilendirilmiştir?",
      "Bireysel çabaların önemli olduğu ancak tek başına yeterli olmadığı, çevre sorunlarının çözümü için kamusal politikalar, eğitim sistemleri ve kurumsal sorumluluğun da gerekli olduğu belirtilmiştir."),
    q(8, "Değerlendirme", "Değerlendirme",
      "“İnsan doğayla uyum içinde yaşamadığı sürece çevresel krizler kaçınılmazdır.” görüşünü metne dayanarak değerlendiriniz.",
      "Metinde insanın doğaya aşırı müdahalesinin çevresel krizleri artırdığı açıkça belirtilmektedir. Doğayla uyum sağlanmadığında ekosistem dengesi bozulmaktadır. Metne dayalı gerekçelendirme yapıldığı sürece farklı görüşler kabul edilir.", True),
    q(9, "Değerlendirme", "Değerlendirme",
      "Yazarın sürdürülebilirlik kavramına verdiği önemi ne ölçüde haklı buluyorsunuz? Gerekçenizi belirtiniz.",
      "Yazarın sürdürülebilirliğe verdiği önem haklıdır; çünkü doğal kaynakların sınırlı olduğu ve gelecek kuşakların haklarının korunması gerektiği vurgulanmaktadır.", True),
    q(10, "Yaratma", "Yaratma",
      "Metinden hareketle, gençlere yönelik doğa bilinci kazandırmayı amaçlayan kısa bir paragraf, slogan ya da afiş metni yazınız.",
      "Doğa bilinci kazandırmayı amaçlayan paragraf/slogan değerlendirmesinde ölçüt: metnin ana düşüncesiyle uyum; çevre bilinci vurgusu; özgünlük. Öğrencinin metinle bağlantılı yaratıcı ürünleri kabul edilir.", True),
]


def _insan_govde(ham):
    """İNSAN gövdesini tam_ham'dan çıkar: (553) sonrası → 'Metne göre insan' öncesi."""
    t = ham["A. 4 İNSAN.pdf"]["tam_ham"]
    m = re.search(r"\(553\)", t)
    bas = m.end() if m else 0
    son = t.find("Metne göre insan")
    govde = t[bas:son if son > 0 else len(t)].strip()
    # PDF bitişik-kelime düzeltmeleri (yalnız boşluk; kelime değişmez)
    for a, b in [("birunsurdu", "bir unsurdu"), ("müdahalekapasitesi", "müdahale kapasitesi"),
                 ("vegürültülü", "ve gürültülü")]:
        govde = govde.replace(a, b)
    return govde


def main():
    ham = {x["dosya"]: x for x in json.load(open(HAM, encoding="utf-8"))}
    override = [
        {"dosya": "8 A.3 Eşsiz Şehrin Yankıları.pdf", "baslik": "Eşsiz Şehrin Yankıları",
         "sinif_seviyesi": 8, "kelime_sayisi": ham["8 A.3 Eşsiz Şehrin Yankıları.pdf"]["kelime_sayisi"],
         "govde_temiz": None, "sorular": YANKILAR,
         "notlar": "Ajan çıktısı hatalıydı (Q1/Q3 uydurma); kaynak temiz metinden birebir düzeltildi."},
        {"dosya": "A. 1 DUVARLARIN ARASINDA BÜYÜYEN SES.pdf", "baslik": "DUVARLARIN ARASINDA BÜYÜYEN SES",
         "sinif_seviyesi": "lise", "kelime_sayisi": ham["A. 1 DUVARLARIN ARASINDA BÜYÜYEN SES.pdf"]["kelime_sayisi"],
         "govde_temiz": None, "sorular": DUVARLAR,
         "notlar": "Ajan Q5-Q9'u boş bırakmıştı; kaynak tam metinden birebir düzeltildi."},
        {"dosya": "A. 4 İNSAN.pdf", "baslik": "İNSAN–DOĞA İLİŞKİSİNİN DÖNÜŞÜMÜ",
         "sinif_seviyesi": "lise", "kelime_sayisi": 553,
         "govde_temiz": _insan_govde(ham), "sorular": INSAN,
         "notlar": "Başlık düzeltildi, gövde tam_ham'dan çıkarıldı. Q3/Q4 (Anlama) cevapları KAYNAK PDF'de YOK → boş; koordinatör onayında tamamlanmalı."},
    ]
    json.dump(override, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✓ {len(override)} düzeltme yazıldı → {OUT}")
    for o in override:
        bos = [s["no"] for s in o["sorular"] if not s["cevap"] and not s["subjektif"]]
        print(f"  • {o['baslik'][:34]:34} soru={len(o['sorular'])} boş_cevap(objektif)={bos}")


if __name__ == "__main__":
    main()
