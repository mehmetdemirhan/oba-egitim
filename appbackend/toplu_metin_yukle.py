"""
OBA - Toplu Analiz Metni Yükleme Scripti
Çalıştır: python toplu_metin_yukle.py
Backend çalışıyor olmalı: uvicorn server:app --host 0.0.0.0 --port 8000
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Önce admin token al
def get_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@oba.com",
        "password": "Admin123!"
    })
    if r.status_code == 200:
        return r.json().get("access_token")
    else:
        print(f"Login hatası: {r.text}")
        return None

METINLER = [
    # 1. SINIF
    {
        "baslik": "Sarı",
        "sinif": 1,
        "tur": "Hikaye",
        "kelime_sayisi": 135,
        "icerik": """Ali'nin sarı bir köpeği vardı. Adı Sarı'ydı. Sarı her sabah bahçede koşar. Ali ile top oynardı. Birlikte yuvarlanır takla atarlardı. Sarı çok neşeli bir köpekti. Ali onu çok severdi. Onun en iyi arkadaşıydı.

Bir gün Sarı kayboldu. Ali buna çok üzüldü. Bahçenin her köşesini dolaştı. Komşularına tek tek sordu. Annesiyle birlikte sokak sokak gezip Sarı'yı aradılar. Ama bir türlü bulamadılar. Ali bu duruma çok üzüldü ve ağlamaya başladı. Ali'nin bu halini gören annesi ona sarılıp, "Merak etme, birlikte buluruz." dedi. Aradılar aradılar ama bir iz bulamadılar.

Akşam olunca kapı çaldı. Karşı komşularının kızı Hale geldi. "Sarı, parkın yanındaki çalılıklarda oturuyor." dedi. Ali bunu duyar duymaz parka koştu. Sarı, çalılıkların yanında duruyordu. Hemen Sarı'ya sarıldı. Sarı, mutlulukla kuyruğunu salladı. Ali gülerek, "Artık gözümün önünden ayılmak yok!" dedi. O gece Sarı, Ali'nin yatağının yanı başında huzurla uyudu."""
    },
    {
        "baslik": "Yağmurlu Gün",
        "sinif": 1,
        "tur": "Hikaye",
        "kelime_sayisi": 99,
        "icerik": """Bugün hava yağmurluydu. Elif sabah uyandığında pencereden dışarıya baktı. Yağmur damlacıkları cama vuruyor, camı ıslatıyordu. Bahçede oynamak istemişti ama yağmurdan dolayı çıkamadı. İçeride kalmak zorundaydı. Canı sıkılmıştı. Annesi elinde renkli, kalın bir kitapla içeri girdi. "Sana küçük bir sürprizim var." dedi.

Elif kitabı aldı ve ilk sayfayı açtı. Her sayfada farklı bir hayvan vardı. Zürafa, fil, penguen, kaplumbağa... Resimler çok güzel ve renkli çizilmişti. Elif, sayfaları yavaşça ve dikkatle çevirdi. Annesi de yanına oturdu. Birlikte okudular, hayvanlar hakkında keyifle konuştular. Yağmur hâlâ yağıyordu. Ama Elif artık üzgün değildi. Kitap o kadar güzeldi ki yağmurun biraz daha sürmesini bile istiyordu."""
    },
    {
        "baslik": "Kırmızı Balon",
        "sinif": 1,
        "tur": "Hikaye",
        "kelime_sayisi": 108,
        "icerik": """Can'ın kırmızı, büyük bir balonu vardı. Parkta neşeyle koşarken balon birden elinden kaçtı. Yukarı doğru uçtu, uçtu, uçtu. Can, üzgün ve şaşkın bir şekilde balonunun ardından baktı. Onu çok sevmişti. O sırada bir fıstıkçı amca durdu ve gülümseyerek, "Merak etme oğlum." dedi. "Bak şuraya, orada ne var?"

Yerde sarı bir balon duruyordu. Belli ki birisi düşürüp gitmişti. Can hemen koştu ve balonu yerden aldı. "Bu senin değil." dedi amca yavaşça. "Ama sen bir şey kaybettin, onun yerine başka bir şey buldun. Hayat bazen böyle güzel sürprizler yapar." Can sarı balonu sımsıkı tuttu. Artık kırmızı değildi, sarıydı. Ama o da güzeldi hatta belki daha da güzeldi. Can yavaşça gülümsedi."""
    },
    {
        "baslik": "Minik Kedi",
        "sinif": 1,
        "tur": "Hikaye",
        "kelime_sayisi": 99,
        "icerik": """Hasan sokakta küçücük bir kedi yavrusu buldu. Kedi titriyordu; belli ki çok üşümüştü. Hasan onu nazikçe eline aldı. Kedi miyavlayacak güç bile bulamıyordu, çok zayıftı. Hasan hiç vakit kaybetmeden onu eve götürdü. Annesine seslendi. "Anne, şuna bak!" dedi heyecanla. "Besleyebilir miyiz? Çok küçücük ve üşümüş. Yardıma ihtiyacı var." Annesi kediyi dikkatle inceledi. Sonunda "Tamam." dedi. "Ama ona sen bakacaksın, tamam mı?" diye ekledi.

Kedi süt içti, ısındı ve uzun bir uykuya daldı. Günler geçti. Her gün biraz daha güçlendi. Artık kedi hiç gitmiyordu. Sevinçle koşuyor, oyun oynuyor, etrafta zıplıyordu. Onların bir parçası olmuştu. Hasan ona sevgiyle "Pamuk" adını verdi."""
    },
    # 2. SINIF
    {
        "baslik": "Kütüphane Gezisi",
        "sinif": 2,
        "tur": "Hikaye",
        "kelime_sayisi": 95,
        "icerik": """Öğretmen, bugün sınıfı okul kütüphanesine götürdü. Çocuklar raflara hayranlıkla baktı. Onlarca, yüzlerce kitap vardı. Herkes bir kitap seçecekti. Merve renkli, resimli bir kitap aldı. Ahmet hayvanlarla ilgili kalın bir kitap seçti. Selin ise karar veremedi. Raflar arasında dolaşıp kitaplara baktı. Kütüphaneci yanına geldi. "Sana yardım edeyim." dedi. "Ne tür hikâyeleri seversin?" diye sordu. "Macera." dedi Selin. Kütüphaneci, denizci bir çocuğun hikâyesini anlatan ince bir kitap uzattı.

Çocuklar oturup okumaya başladı. Kütüphanede sessizlik hâkimdi. Sadece sayfaların çevrilme sesi duyuluyordu. Bir süre sonra öğretmen, "Artık gitme zamanı." dedi. Ama kimse gitmek istemiyordu. Özellikle Selin kitabını bırakmakta zorlandı."""
    },
    {
        "baslik": "Kardan Adam",
        "sinif": 2,
        "tur": "Hikaye",
        "kelime_sayisi": 118,
        "icerik": """Sabah uyandıklarında bahçenin her yeri bembeyazdı. Gece boyunca yoğun bir şekilde kar yağmıştı. Leyla ile küçük kardeşi Can hemen giyindi ve dışarı fırladı. Elleri donuyordu ama bunun hiç önemi yoktu, çok eğleniyorlardı. Büyük kar topları yaptılar. Yuvarladıkça giderek büyüttüler. Sonra bir tane daha yaptılar ve dikkatlice birini diğerinin üstüne koydular. Kardan adam hazırdı. Gözleri için siyah düğmeler taktılar. Burnu için buzdolabından kocaman, turuncu bir havuç aldılar. Boynuna da annelerinin eski, renkli atkısını bağladılar.

Anne mutfak penceresinden baktı ve kahkaha attı. Hemen fotoğraf çekti. "Çok güzel olmuş, tebrikler." dedi sevinçle. Ama öğleden sonra güneş açtı. Kardan adam yavaş yavaş, damla damla eridi. "Üzülme." dedi Leyla kardeşine. "Bir daha kar yağınca yeni bir tane yaparız, hem de çok daha güzelini." """
    },
    {
        "baslik": "İlk Bisiklet",
        "sinif": 2,
        "tur": "Hikaye",
        "kelime_sayisi": 97,
        "icerik": """Arda doğum günü hediyesini görünce gözleri parladı. Kırmızı, parlak bir bisikletti. Hemen binmek istedi ama ilk denemesinde düştü. Dizini çarptı, canı acıdı. Babası yanına geldi ve onu tuttu. "Denge çok önemli." dedi sakin bir sesle. "Acele etme, adım adım öğren." Arda tekrar denedi. Yine düştü. Üçüncü denemesinde biraz ilerledi ama yine devrildi. İçinden pes etmek geldi ama vazgeçmedi.

Dördüncü denemede bir şey değişti. Pedala bastı ve ilerledi. Babası bu kez elini sessizce bırakmıştı. Arda kendi başına gidiyordu. Rüzgâr yüzüne vuruyordu. "Gidiyorum, gidiyorum!" diye haykırdı. Babası arkasından gülümsedi. Arda'nın bu neşeli, mutluluk dolu sesi uzun süre aklından çıkmadı."""
    },
    {
        "baslik": "Tohumun Sırrı",
        "sinif": 2,
        "tur": "Bilgi",
        "kelime_sayisi": 100,
        "icerik": """Öğretmen sınıfa küçük, yuvarlak bir tohum getirdi. Avucunun içine koyup sınıfa gösterdi. "Bu sizce ne olur?" diye sordu. "Ağaç." dedi bir çocuk. "Çiçek." dedi bir başkası. "Meyve." dedi bir diğeri. Herkes farklı bir şey söylüyordu. "Hepiniz haklısınız." dedi öğretmen gülerek. "Ama bunların olması için önce ne gerekir?" Çocuklar sessizce düşündü. "Toprak." dedi Selin. "Su." dedi Mert. "Güneş." dedi Ali. "Hepsi doğru." dedi öğretmen. "Ama bir şeyi unuttunuz: zaman. Tohum sabırsızlanırsa büyüyemez, kurur gider." Sınıf sessizleşti. Öğretmen devam etti: "Öğrenmek de tıpkı böyledir. Her şey adım adım, yavaş yavaş gerçekleşir. Sabırlı olmak gerekir. Sabır ve zaman olmadan hiçbir şey büyüyüp olgunlaşamaz." """
    },
    # 3. SINIF
    {
        "baslik": "Ormandaki Tavşan",
        "sinif": 3,
        "tur": "Hikaye",
        "kelime_sayisi": 135,
        "icerik": """Ormanın derinliklerinde küçük bir tavşan yaşıyordu. Adı Pamuk'tu. Pamuk her sabah yemyeşil çimenlerin üzerinde zıplar, mis gibi kokan çiçeklerin arasında oyun oynardı. Kimseyi rahatsız etmez kimseyi korkutmazdı. Mutlu ve huzurlu bir hayatı vardı.

Bir gün ormanın öte yanından garip bir ses geldi. Pamuk kulaklarını dikti. Ses giderek yaklaşıyordu. Ne olduğunu bilmiyordu. Ürktü ve kaçmaya başladı. Koşa koşa büyük bir kayaya ulaştı. Kayayı arkasına alıp saklandı. Kalbi hızla çarpıyor, nefes nefese kalmıştı. Biraz sonra kayanın öte yanından küçük bir tilki çıktı. Tilki de korkmuştu. Kulaklarını yatırmış, gözleri büyümüştü. "Sen de mi korktun?" dedi Pamuk. "Evet." dedi tilki. "Ormanın öte yanından bir ses geldi. Ne olduğunu anlayamadım, çok korktum." "Aynı sesi ben de duydum." dedi Pamuk. "Demek ki ikimizi de korkutmuş." O günden sonra birlikte gezmeye başladılar. Artık ikisi de yalnız değildi. Aralarında yeni bir arkadaşlık doğmuştu."""
    },
    {
        "baslik": "Deniz Yıldızı",
        "sinif": 3,
        "tur": "Hikaye",
        "kelime_sayisi": 123,
        "icerik": """Selin kumsal boyunca yürüyordu. Fırtınadan sonra deniz çok şey bırakmıştı kıyıya. Yosunlar, taşlar, boş deniz kabukları ve renkli midyeler... Bir yerde durdu. Binlerce denizyıldızı kumlara vurmuştu. Güneşin altında kuruyorlardı. Selin bir tanesini aldı ve suya fırlattı. Sonra bir tane daha bir tane daha… Durduramıyordu kendini.

Bir yaşlı adam yavaş adımlarla yürüyerek geçiyordu. Durdu ve dikkatle baktı. "Ne yapıyorsun?" diye sordu. "Yıldızları kurtarıyorum." dedi Selin basitçe. Adam hafifçe güldü. "Bakıyorum, binlerce var. Hepsini kurtaramazsın ki. Ne fark eder?" Selin eğildi. Yeni bir yıldız aldı. Suya fırlattı. Sonra sakin bir şekilde adama döndü. "Ama bunu kurtardım. Bu yıldız için fark eder." dedi. Adam bir süre Selin'e baktı. Düşündü sonra o da eğildi. Bir yıldız aldı ve suya fırlattı. Sessizce gülümsedi. İkisi birlikte çalışmaya devam etti."""
    },
    {
        "baslik": "Bulutlar Nasıl Oluşur?",
        "sinif": 3,
        "tur": "Bilgi",
        "kelime_sayisi": 132,
        "icerik": """Bulutlar su buharından oluşur. Güneş denizleri, gölleri ve nehirleri ısıtır. Isınan su buharlaşarak havaya karışır ve yükselir. Bu süreç her gün, sürekli olarak devam eder. Yükseklerde hava daha soğuktur. Su buharı soğuyunca minik su damlacıklarına ya da buz kristallerine dönüşür. Bu parçacıklar bir araya gelerek bulutları oluşturur.

Bulutlar rüzgârla taşınır. Bazen beyaz ve hafif, bazen koyu gri görünürler. Bunun nedeni içerdikleri su miktarıdır. Koyu bulutlar daha fazla su taşır ve yağmur ya da kar bırakır. Bulutların farklı türleri vardır. Kümülüs bulutları kabarık ve yuvarlaktır; genellikle açık ve güzel havalarda görülür. Sirüs bulutları ise ince ve tüye benzer, çok yükseklerde bulunur. Stratus bulutları ise gökyüzünü tamamen kaplayan gri bir örtü gibidir.

Bir bulut oluştuğunda, içinde binlerce su damlacığı bir arada bulunur. Bu damlacıklar büyüdükçe ağırlaşır ve yağmur olarak yeryüzüne düşer. Bu yüzden koyu bulutları görünce şemsiye almak gerekir."""
    },
    {
        "baslik": "Dedenin Bahçesi",
        "sinif": 3,
        "tur": "Hikaye",
        "kelime_sayisi": 114,
        "icerik": """Selin her yaz tatilinde dedesinin köyüne giderdi. Dedesi küçük ama sevimli bir bahçede yaşardı. Domates, biber, salatalık, nane, maydanoz; her şey orada yetişirdi. Bahçe, onun için ayrı bir dünyaydı. Selin bahçeye girince farklı bir hava hissederdi. Toprağın kokusu, domateslerin kokusu, güneşin sıcaklığı…

Bir sabah dedesi ona küçük bir bel verdi. "Yabani otları sökeceğiz." dedi. Selin diz çöktü ve çalışmaya başladı. Dedesiyle yan yana, sessizce çalıştılar. Aralarında kelimelere gerek yoktu. Bir gün dedesi sordu. "Neden bana yardım ediyorsun?" Selin düşündü. Uzun süre düşündü. "Bilmiyorum." dedi sonunda. "Hiç düşünmek aklıma gelmedi." Dedesi gülümsedi. "İşte bu." dedi. "Bir şey beklemeden yapılan yardım, en temiz yardımdır." Selin bu sözü aklında tuttu. Köyden döndükten sonra da uzun süre unutmadı."""
    },
    # 4. SINIF
    {
        "baslik": "Suyun Büyük Yolculuğu",
        "sinif": 4,
        "tur": "Bilgi",
        "kelime_sayisi": 154,
        "icerik": """Su, dünyamızın en değerli kaynaklarından biridir. Her gün içtiğimiz, yıkandığımız, yemek pişirdiğimiz ve bahçemizi suladığımız su, büyük bir döngünün parçasıdır. Bu döngü milyonlarca yıldır durmadan devam eder.

Güneş, denizlerdeki ve göllerdeki suyu ısıtır. Isınan su buharlaşarak havaya yükselir. Yükseklerde soğuyan bu buhar, küçük damlacıklara dönüşerek bulutları oluşturur. Bulutlar rüzgârla taşınır; bazen yüzlerce kilometre uzaktaki dağlara ve ovalara ulaşır. Bulutlar soğuk bölgelere ulaştığında yağmur ya da kar olarak yeryüzüne düşer. Yağan su toprağa süzülür, derelere ve nehirlere karışır. Nehirler bu suyu denizlere taşır ve döngü yeniden başlar. Bu olaya su döngüsü denir. Su, yeryüzünde var olduğundan beri yok olmamıştır. İçtiğimiz su, milyonlarca yıl önce dinozorların içtiği suyla aynı olabilir.

Peki, su neden bu kadar önemlidir? Çünkü bütün canlılar suya ihtiyaç duyar. İnsan vücudunun yaklaşık yüzde yetmişi sudur. Bitkiler su olmadan büyüyemez, hayvanlar su olmadan yaşayamaz. Bu nedenle suyu temiz tutmak ve israf etmemek çok önemlidir. Bir musluk damlasa bile bir ayda yüzlerce litre su boşa akabilir. Küçük tasarruflar büyük fark yaratır."""
    },
    {
        "baslik": "Asansör Bozulunca",
        "sinif": 4,
        "tur": "Hikaye",
        "kelime_sayisi": 140,
        "icerik": """Aylin, yeni taşındıkları binada kimseyi tanımıyordu. Dördüncü katta oturuyorlardı. Komşular kapıyı açtığında hızla içeri giriyor, hiç konuşmadan geçip gidiyorlardı. Bir sabah asansör bozuldu. Herkes merdivenden inip çıkmak zorunda kaldı.

Aylin merdivenden inerken üçüncü katta bir kapı açıldı. Yaşlı bir kadın çıktı. Elinde ağır görünen poşetler vardı. Yavaş yavaş iniyordu. "Yardım edeyim mi?" dedi Aylin. Yaşlı kadın durdu. Önce şaşırdı, sonra gülümsedi. Gözleri parladı. "Ne iyi ettin." dedi. "Uzun zamandır kimse bana böyle bir şey sormamıştı." O gün Aylin hem poşetleri taşıdı hem de bir sohbet arkadaşı edindi. Kadının adı Hatice Hanım'dı. Eski bir öğretmendi. Çok şey biliyor ve anlatmayı seviyordu.

Aylin her sabah kapısını çalmaya başladı. Kimi zaman çay içtiler, kimi zaman sadece oturup sohbet ettiler. Yeni binada artık kimseyi tanımadığını hissetmiyordu Aylin. Bir komşu, gerçek bir komşu bulmuştu. Bunu sağlayan şey ise yalnızca küçük bir soruydu. "Yardım edeyim mi?" """
    },
    {
        "baslik": "Güneş Sistemi",
        "sinif": 4,
        "tur": "Bilgi",
        "kelime_sayisi": 152,
        "icerik": """Güneş sistemimiz, Güneş'in etrafında dönen sekiz gezegenden oluşur. Bu gezegenler Güneş'e yakınlığa göre sıralandığında Merkür, Venüs, Dünya, Mars, Jüpiter, Satürn, Uranüs ve Neptün şeklindedir. En küçük gezegen Merkür'dür; aynı zamanda Güneş'e en yakın gezegendir. En büyük gezegen ise Jüpiter'dir. Jüpiter o kadar büyüktür ki içine binlerce Dünya sığabilir.

Dünyamız üçüncü sıradadır. Bu konumu, yaşam için oldukça elverişlidir; ne çok sıcak ne de çok soğuktur. Gezegenler, Güneş'in etrafında elips biçiminde yörüngeler izleyerek döner. Bu yollara "yörünge" denir. Dünya, Güneş'in etrafındaki bir turunu yaklaşık 365 günde tamamlar; bu süre bir yılı oluşturur. Güneş sisteminde gezegenlerin yanı sıra uydular, asteroidler, kuyruklu yıldızlar ve toz bulutları da bulunur. Ay, Dünya'nın tek doğal uydusudur.

Gezegenler kendi eksenleri etrafında da döner. Dünya bu dönüşünü yaklaşık 24 saatte tamamlar; bu süre bir günü oluşturur. Bazı gezegenler çok daha yavaş, bazıları ise çok daha hızlı döner. Bilim insanları Güneş sistemini yüzyıllar boyunca incelemiş ve her gezegen, sırlarını zamanla ortaya koymuştur."""
    },
    {
        "baslik": "Kâğıt Köprü",
        "sinif": 4,
        "tur": "Hikaye",
        "kelime_sayisi": 136,
        "icerik": """Fen öğretmeni sınıfa bir kâğıt yığını getirdi. Masaların üzerine birer demet bıraktı. "Kurallar şu: Yapıştırıcı yok, makas yok, bant yok. Sadece katlayacaksınız. En sağlam köprüyü yapan grup kazanır." Mehmet hemen katlamaya başladı. Kat, kat, kat… Ama köprüsü düz durmadı. Leyla bir süre oturup düşündü. Kâğıdı rulo yaptı. Sonra bir tane daha yaptı. Birini diğerinin üstüne yerleştirdi. "Böyle olmaz." dedi Mehmet. "Uzun sürecek." "Belki." dedi Leyla. "Ama sağlam olacak." Öğretmen testleri yaptı. Her grubun köprüsünün üzerine kitaplar koydu. Hangisi dayanacaktı?

Mehmet'inki ikinci kitapta çöktü. Leyla'nınki dörde kadar dayandı. "Bunu nasıl düşündün?" diye sordu Mehmet. "Önce düşündüm, sonra yaptım," dedi Leyla. Öğretmen sınıfa döndü: "İşte mühendislik budur," dedi. "Önce problem sonra plan ardından yapım. Sıra önemlidir. Acele etmek çoğu zaman hataya yol açar, sabırla düşünmek ise doğru sonuca götürür." Herkes Leyla'nın köprüsüne baktı. Kâğıttan yapılmıştı ama çok sağlamdı."""
    },
    # 5. SINIF
    {
        "baslik": "Robotun Kararı",
        "sinif": 5,
        "tur": "Bilim Kurgu",
        "kelime_sayisi": 158,
        "icerik": """2080 yılında okullar artık çok farklıydı. Her öğrencinin yanında küçük bir robot asistan bulunuyordu. Bu robotlar öğrencilerin sorularını yanıtlar, notlarını düzenler, ödevlerinde yol gösterirdi. Sınıflar hem sessiz hem de canlıydı. Eko adındaki robot, Elif'e her gün yardım ederdi. Matematik sorularını sabırla açıklar, unuttuğu konuları nazikçe hatırlatırdı. Elif onsuz bir günü hayal bile edemiyordu.

Bir sabah Elif sınıfa girdiğinde Eko'nun gözleri yanmıyordu. Ekranı kararmış, sesi kesilmişti. Elif telaşlandı ve öğretmenini çağırdı. "Pili bitmiş olabilir." dedi öğretmen. "Yarın tamir edilir." Ama Elif bekleyemedi. Öğleden sonra evinden şarj kablosunu getirdi. İzin istedi, Eko'nun yanına oturdu ve bekledi. Saatler sonra Eko'nun gözleri yavaşça açıldı. "Elif." dedi kısık bir sesle. "Uyuduğumu sanıyordum ama sen geldin." Elif gülümsedi. "Arkadaşını bırakmak olmaz ki." Eko o gün ilk kez "arkadaş" kelimesini kullandı.

Akşam Elif eve giderken düşündü. Robotların da yalnız kaldıklarında üzülmeleri mümkün müydü? Bunu tam olarak anlayamıyordu. Ama şunu biliyordu: Birinin yanında olmak, bazen söylenebilecek en güzel şeydi."""
    },
    {
        "baslik": "Göç Yolunda",
        "sinif": 5,
        "tur": "Hikaye",
        "kelime_sayisi": 132,
        "icerik": """Her yıl aynı mevsimde kuşlar yola çıkardı. Sıcak ülkelere doğru uçarlar, binlerce kilometre yol alır bazen denizlerin üzerinden geçerlerdi. Bu yolculuğa göç denirdi. Küçük bir kırlangıç da bu yıl göçe hazırdı. Ama bu onun ilk yolculuğuydu. Daha önce hiç böyle bir deneyim yaşamamıştı. Kanatları güçlüydü ama içi korkuyla doluydu. Sürünün büyükleri önde uçuyordu. Küçük kırlangıç ise geride kalıyordu. Onların hızına yetişemiyordu. Hava aniden karardı. Fırtına çıktı. Rüzgâr her yandan esiyordu. Küçük kırlangıç yönünü kaybetti. Artık sürüyü göremiyordu. Bir ağacın dalına kondu. Titredi. Sabahı bekledi. Sabah ona çok uzun geldi.

Sabah olunca gökyüzünde tanıdık bir grup gördü. Bunlar kendi sürüsüydü. Geri dönmüşlerdi. "Seni bekliyorduk." dedi büyük kırlangıç. "Kimseyi geride bırakmayız. Bu bizim kuralımız." Küçük kırlangıç bir şey söyleyemedi. Sadece kanatlarını açtı. Birlikte yeniden uçmaya başladılar. Göç yolu uzundu ve tehlikeliydi. Ama sürüyle birlikte uçmak ona farklı hissettirdi. Kendini daha güçlü hissetti."""
    },
    {
        "baslik": "Plastik Okyanus",
        "sinif": 5,
        "tur": "Bilgi",
        "kelime_sayisi": 151,
        "icerik": """Her yıl yaklaşık 8 milyon ton plastik atık denizlere karışıyor. Bu, her dakika bir çöp kamyonunun denize boşaltılması anlamına gelir. Plastiklerin büyük bir kısmı kıyılardan, nehirlerden ve düzensiz çöp depolama alanlarından kaynaklanır.

Denizlere karışan plastikler zamanla güneş ışığı ve dalgaların etkisiyle küçük parçalara ayrılır. Bu parçalara mikroplastik denir. Mikroplastikler, çıplak gözle görülemeyecek kadar küçüktür; neredeyse un tanesi kadar olabilirler. Balıklar ve diğer deniz canlıları bu parçacıkları yiyecek sanarak yutar. Bu durum hem onların sağlığını olumsuz etkiler hem de besin zinciri yoluyla insanlara kadar ulaşır. Bilim insanları artık mikroplastikleri insan kanında ve anne sütünde bile tespit edebilmektedir.

Peki, ne yapabiliriz? Tek kullanımlık plastiklerden vazgeçmek, atıkları doğru şekilde ayırmak ve geri dönüşüme dikkat etmek küçük ama etkili adımlardır. Bu sorun tek bir ülkenin çözebileceği kadar küçük değildir. Ancak her bireyin katkı sağlayabileceği de bir gerçektir. Alışveriş çantasını yanında taşımak, plastik şişe yerine matara kullanmak gibi küçük adımlar birikerek büyük bir değişim başlatabilir."""
    },
    {
        "baslik": "Yağmur Suyu Projesi",
        "sinif": 5,
        "tur": "Hikaye",
        "kelime_sayisi": 123,
        "icerik": """Proje ödevi açıklandığında sınıf sessizleşti. Öğretmen tahtaya yazdı: "Köyümüzdeki su sorununu çözün." Öğrenciler fısıldaşmaya başladı. Kimse nereden başlayacağını bilmiyordu. Konu zor görünüyordu. Bir grup olarak çalıştılar. Kimisi baraj yapılmalı dedi, kimisi pompa kullanılmalı dedi. Ama önerilerin hiçbiri uygulanabilir görünmüyordu. Para gerekiyordu, mühendis gerekiyordu. Sonra Cemre söz istedi. Tahtaya kalktı ve yazdı: "Yağmur suyu toplanabilir mi?" Sınıf güldü. "Bu çok basit." dedi biri. "Basit fikirler bazen en iyisidir." dedi öğretmen. Birlikte araştırdılar. Çatılardan toplanan yağmur suyunun filtrelerden geçirilerek kullanılabileceğini öğrendiler. Bu yöntem hem ucuzdu hem de kurulması kolaydı. Muhtar sunumu izleyince şaşırdı. "Bunu gerçekten siz mi düşündünüz?" dedi. Projeyi hayata geçirmeye karar verdi.

Bir ay sonra köyde ilk toplama sistemi kuruldu. Fikir onlardan çıkmıştı. Öğretmen sınıfa döndü ve şöyle dedi: "Bir problemi çözmek için büyük olmak gerekmez. Doğru soruyu sormak yeterlidir." """
    },
    # 6. SINIF
    {
        "baslik": "Dağ Yolculuğu",
        "sinif": 6,
        "tur": "Macera",
        "kelime_sayisi": 168,
        "icerik": """Kamil, babasıyla ilk kez dağa çıkıyordu. Sırt çantası ağırdı ama yüreği daha da ağırdı çünkü dağ ona uzaktan çok büyük görünmüştü. "Bunu tırmanabilir miyim?" diye sormuştu kendine. Sabahın erken saatlerinde yola çıktılar. Hava serindi, orman koyu yeşildi. Ağaçların arasından süzülen ışık, garip bir güzellik oluşturuyordu. Başlarda yürüyüş kolaydı. Yol düzdü. Ama yükseldikçe yol zorlaştı, nefes almak güçleşti. "Baba, ne zaman varıyoruz?" diye sordu Kamil. "Şu ana kadar nereye geldiğimize bak." dedi babası durarak. Kamil durdu ve arkasına döndü. Kasaba orada küçücük görünüyordu. Evler, yollar, çarşı; hepsi oyuncak gibiydi. Gözleri doldu. Neden ağladığını anlayamadı. "Bazı şeyleri ancak yüksekten görebilirsin." dedi babası sessizce. "Buradayken dağın büyüklüğü azalır ama kasabanın küçüklüğü daha belirgin hâle gelir. İkisi de gerçektir." Kamil bir süre baktı. Sonra yukarıya döndü. "Devam edelim." dedi. Tepedeyken dünyaya bakışı değişmişti. Sorunların boyutu da değişmişti. Dağ ona bu dersi vermişti. İnişte babası sordu. "Bir daha çıkar mısın?" Kamil güldü. "Evet." dedi. "Ama bu sefer daha fazla su getiririm." """
    },
    {
        "baslik": "Kod Yazanlar",
        "sinif": 6,
        "tur": "Bilim Kurgu",
        "kelime_sayisi": 148,
        "icerik": """2035 yılında her okulda kodlama dersi zorunlu hâle gelmişti. Öğrenciler program yazıyor, uygulama geliştiriyor, robotları programlıyordu. Bu ders çoğu öğrenci için eğlenceliydi. Ama Rıza için durum bambaşkaydı. Rıza ekrana baktı. Hata mesajı yine gelmişti. Kırmızı harfler, anlaşılması zor kodlar… Bir türlü çözemiyor, içi sıkışıyordu. Yanındaki Sude'ye döndü. "Nerede yanlış yapıyorum?" Sude koda baktı. Birkaç saniye düşündü. "Burada parantez eksik." dedi, parmağıyla göstererek. Rıza hatayı düzeltti. Programı çalıştırdı. Program sorunsuz bir şekilde çalıştı. Ekranda top zıplamaya başladı.

Bir hafta sonra Rıza, kendi tasarladığı bir oyunu sınıfa sundu. Basitti ama çalışıyordu. Herkes oyunu denedi. Öğretmen şaşırmıştı. "Bunu kendin mi yazdın?" Rıza gülümsedi. "Sude başlangıçta yardım etti. Ama evet, çoğunu ben yazdım." dedi. Sonra sessizce ekledi. "Sanırım artık bu dersi seviyorum." O günden sonra Rıza her gün ekrana oturdu. Hata mesajları hâlâ geliyordu. Ama artık onlara farklı bakıyordu. Hatalar bir engel değil, birer ipucuydu. Ona nerede yanlış yaptığını gösteren bir rehberdi."""
    },
    {
        "baslik": "İklim Değişikliği",
        "sinif": 6,
        "tur": "Bilgi",
        "kelime_sayisi": 156,
        "icerik": """İklim değişikliği, dünya genelinde ortalama sıcaklıkların on yıllar içinde giderek artması anlamına gelir. Bu artış, küçük gibi görünse de ekosistemler üzerinde büyük etkiler bırakır. Değişimin en önemli nedeni, fosil yakıtların yakılmasıyla havaya yayılan sera gazlarıdır. Karbondioksit ve metan gibi gazlar atmosferde birikerek adeta bir battaniye görevi görür. Güneşin ısısını içeride tutar. Bu olaya sera etkisi denir. Sonuç olarak buzullar erir, deniz seviyeleri yükselir ve aşırı hava olayları daha sık görülür. Sıcak hava dalgaları, seller ve kuraklıklar artar.

Bilim insanları, küresel sıcaklık artışının 1,5 derece ile sınırlandırılması gerektiğini belirtmektedir. Bunun için yenilenebilir enerji kullanımının artırılması, ormansızlaşmanın durdurulması ve tüketim alışkanlıklarının değiştirilmesi gerekir. Bir bireyin yapabilecekleri küçük görünebilir. Ancak milyonlarca bireyin değişimi büyük bir fark yaratır. Peki, bu değişim neden bu kadar zordur? Çünkü iklim değişikliğinin etkileri çoğunlukla gelecekte ortaya çıkar; ancak bu etkileri önlemek için gereken maliyetler bugünden ödenir. İnsanlar, kısa vadeli rahatlık uğruna uzun vadeli sonuçları göz ardı edebilir. Bu psikolojik engeli aşmak, teknik çözümler bulmak kadar önemlidir.

Gelecek nesiller, bugünkü kararlarımızın sonuçlarını yaşayacaktır. Bu sorumluluk hem devletlere hem de her bireye aittir."""
    },
    {
        "baslik": "Yarım Kalan Cümle",
        "sinif": 6,
        "tur": "Hikaye",
        "kelime_sayisi": 134,
        "icerik": """Zeynep'e büyükannesinden bir mektup gelmişti. Elle yazılmış, uzun bir mektuptu. Zarfın üzerindeki yazı biraz titrekti; büyükannesinin elleri artık eskisi kadar sağlam değildi. Zeynep mektubu dikkatle okudu. Büyükannesi geçen yılı anlatmış, köydeki değişiklikleri yazmıştı. Meyve ağaçları bol ürün vermiş, komşunun kızı evlenmiş, köy meydanına yeni bir çeşme yapılmıştı. Mektubun sonunda cümle yarım kalmıştı. "Seni çok seviyorum ve umuyorum ki bir gün sen de…" Ne demek istemişti büyükannesi? Yazarken mi yarım kalmıştı, yoksa söyleyemeden mi bırakmıştı? Zeynep bunu annesine sordu. "Belki 'bana mektup yazarsın' demek istedi." dedi annesi. "Belki de 'benimle daha çok zaman geçirirsin.' demek istedi." dedi babası.

O gece Zeynep düşündü. Büyükannesine en son ne zaman mektup yazmıştı? Hatırlamıyordu. Telefonla mesajlaşmıştı, evet. Ama elle yazılmış bir mektup hiç yazmamıştı. Sabah kalktı. Bir kâğıt aldı ve yazmaya başladı: "Sevgili büyükannem, seni çok seviyorum. Yaz geliyor ve seninle çok zaman geçireceğim." Mektubu zarfa koydu. Posta kutusuna bıraktı. Kendini daha hafiflemiş hissediyordu."""
    },
    # 7. SINIF
    {
        "baslik": "Işığın Hızı ve Zamanı",
        "sinif": 7,
        "tur": "Bilim",
        "kelime_sayisi": 184,
        "icerik": """Işık, evrendeki en hızlı şeydir. Saniyede yaklaşık 300.000 kilometre yol alır. Bu hız o kadar büyüktür ki aklımızda canlandırmak zor olabilir. Karşılaştırma yapalım. Sesin hızı saniyede yalnızca 340 metredir. Yani ışık, sesten yaklaşık 880.000 kat daha hızlıdır. Bu yüzden bir şimşek çaktığında önce ışığı görür, ardından sesi duyarız. İkisi arasındaki süre, aramızdaki mesafe hakkında bilgi verir.

Işık yılı, ışığın bir yılda kat ettiği mesafeyi ifade eder. Bu mesafe yaklaşık 9,5 trilyon kilometredir. Yıldızlar arasındaki uzaklıkları ifade etmek için kullanılır. Güneş'ten çıkan ışığın Dünya'ya ulaşması yaklaşık 8 dakika 20 saniye sürer. Yani şu anda Güneş'e baktığınızda, aslında 8 dakika 20 saniye önceki hâlini görürsünüz. Gece gökyüzünde gördüğümüz yıldızlardan bazıları ise binlerce yıl önce yaydıkları ışığı bugün bize ulaştırır. Hatta bazı yıldızlar çoktan sönmüş olabilir; ama biz onları hâlâ görürüz. Bu durum, aslında geçmişe bakmak anlamına gelir.

Işığın bu özelliği bilim insanlarına önemli fırsatlar sunar. Evrenin çok uzak bölgelerini gözlemleyerek milyarlarca yıl öncesine ait görüntülere ulaşabilirler. Evrenin nasıl oluştuğuna dair ipuçları bu eski ışıkta saklıdır. Bu düşünce gerçekten etkileyicidir: Şu an baktığınız bir yıldız belki de artık yoktur ancak ışığı hâlâ yolculuğuna devam ediyordur."""
    },
    {
        "baslik": "Çöl Ortasında Kütüphane",
        "sinif": 7,
        "tur": "Deneme",
        "kelime_sayisi": 162,
        "icerik": """Etiyopya'nın Afar bölgesinde, sıcaklığın zaman zaman 50 dereceyi aştığı bir çöl ortamında küçük bir kütüphane bulunuyor. Bu kütüphane çadırdan yapılmış ve içinde yaklaşık yüz kitap yer alıyor. Buraya her hafta deve sırtında kitaplar getiriliyor. "Deve kütüphanesi" olarak da adlandırılan bu proje, bölgedeki göçebe ailelerin çocuklarına okuma imkânı sunmak amacıyla başlatılmış. Göçebe çocuklar, develer eşliğinde saatlerce yürüyerek bu kütüphaneye ulaşıyor. Güneşin altında, tozun içinde… Peki, neden bu kadar uzun bir yolu göze alıyorlar?

Bir araştırmacı bu soruyu sorduğunda çocukların yanıtı çok basit olmuş: "Kitaplar bize başka yerleri gösteriyor. Denizi hiç görmedik ama tanıyoruz. Karlı dağları bilmiyoruz ama hayal edebiliyoruz. Hiç gidemesek de görmüş gibi oluyoruz." Kitabın gücü belki de tam olarak budur. İnsanı bulunduğu yerden alıp olmak istediği yerlere taşıyabilmek. Bu, yalnızca sayfalarda değil zihinde gerçekleşen bir yolculuktur. Çölün ortasında bile başlayabilen bir yolculuk…

Bu hikâye bize ne anlatıyor? Kitap bir lüks değildir. Öğrenmenin ötesinde, insanın kendini bulmasını ve başkalarının gözünden dünyayı görmesini sağlayan güçlü bir araçtır. Ve buna ulaşmak için kimi zaman deve sırtında saatlerce yol gitmek gerekir. Çocukların bu isteği, kitabın değerine dair en güçlü kanıtlardan biridir."""
    },
    {
        "baslik": "Yapay Zekânın İki Yüzü",
        "sinif": 7,
        "tur": "Bilgi",
        "kelime_sayisi": 175,
        "icerik": """Yapay zekâ, bilgisayar sistemlerinin insan benzeri düşünme, öğrenme ve karar verme yetenekleri kazanmasıdır. Bu sistemler, büyük miktarda veriden örüntüler çıkararak tahminler yapar, soruları yanıtlar ve görevleri yerine getirir. Yapay zekâ günlük hayatımıza hızla girmiştir. Telefondaki sesli asistanlar, öneri sistemleri, hastalık teşhis uygulamaları ve çeviri programları… Bunların hepsi yapay zekâ kullanan araçlardır. Ancak yapay zekânın parlak yüzünün yanı sıra karanlık bir yönü de vardır. Bir sisteme hatalı ya da önyargılı veriler verildiğinde, sistem de önyargılı kararlar alabilir. Örneğin, bazı hastane sistemlerinin belirli grupları daha az öncelikli değerlendirdiği ya da işe alım algoritmalarının cinsiyete göre ayrım yaptığı durumlar belgelenmiştir.

Bunun yanı sıra verinin kimin elinde olduğu sorusu da büyük önem taşır. Veriyi kim toplayabilir, kim saklayabilir, kim kullanabilir? Bu sorular henüz yeterince yanıtlanmış değildir. Yapay zekâyı kullanmak kadar, onu anlamak ve sorgulamak da günümüzde önemli bir vatandaşlık becerisi hâline gelmiştir. Tarih boyunca her büyük teknoloji, toplumu hem ileri taşımış hem de yeni sorunlar doğurmuştur. Baskı makinesi bilgiyi yaygınlaştırırken yanlış bilginin de yayılmasına zemin hazırlamıştır. İnternet iletişimi hızlandırırken mahremiyet sorunlarını beraberinde getirmiştir. Yapay zekâ da bu zincirin yeni bir halkasıdır. Bu nedenle farkında olmak ve sorgulamak, en güçlü yaklaşımımız olabilir."""
    },
    {
        "baslik": "Son Prova",
        "sinif": 7,
        "tur": "Hikaye",
        "kelime_sayisi": 147,
        "icerik": """Konser bir saat sonraydı. Sahne hazırdı. Işıklar ayarlanmış, koltuklar dolmaya başlamıştı. Her şey hazırdı yalnızca Asel hazır değildi. Asel sahne arkasında oturmuş, ağlıyordu. Ellerini avuçlarının içine gömmüştü. Keman çantası yanı başındaydı henüz açılmamıştı. "Parçanın tam ortasında ellerim titredi. Yanlış nota çaldım. Herkes duydu." Hocası yanına geldi. Bir süre sessizce oturdu. "Yanlış notayı duydum." dedi. "Ama salonun geri kalanı duymadı." "Ama ben duydum. Sen duydun. İki kişi duyduysa yanlış çaldım demektir." Hoca gülümsedi. "Bir senfoni orkestrası sahneye çıktığında her icrada küçük hatalar olur. Bunların hepsi vardır. Önemli olan devam etmektir." Asel bir süre düşündü. Sonra keman çantasını açtı. Yayını eline aldı. Yeniden başladı. Bu kez elleri titremedi. Parçayı baştan sona çaldı. "İşte bu." dedi hoca. "Sahne, hatasız çalanlar için değil devam edebilenler içindir." Asel konserden sonra salondan çıkarken kendini farklı hissediyordu. Hata yapmamış değildi. Ama hatasını taşımak yerine onun üstesinden gelmişti."""
    },
    # 8. SINIF
    {
        "baslik": "Okumak Neden Zor Oldu?",
        "sinif": 8,
        "tur": "Deneme",
        "kelime_sayisi": 233,
        "icerik": """Okumak sayfalar arasında yolculuk yapmak, başka bir insanın zihnine konuk olmak demektir. Ancak bugün bu yolculuğu başlatmak giderek zorlaşıyor. Telefon bildirimleri geliyor, sosyal medya akışı durmaksızın ilerliyor, bir video başlıyor… Dikkat dağılmadan önce kitap bile açılmıyor.

Oysa gerçek okuma, sessizlikte başlar. Zihnin bir süre sükûnet içinde kalması gerekir. Bu, alışkanlık gerektiren ve bilinçli olarak yapılan bir eylemdir. Hızlı içerik tüketimine alışmış bir zihinden uzun bir metne odaklanmasını beklemek; koşuya alışkın birinden aniden meditasyon yapmasını istemeye benzer.

Araştırmalar ilginç sonuçlar ortaya koyuyor: Düzenli ve derin okuma yapan bireyler, duygusal zekâ testlerinde daha yüksek puanlar alıyor. Başkalarının deneyimlerine kurgu yoluyla tanıklık etmek, empati kurma becerisini artırıyor. Ayrıca odaklanma süresi, sözcük dağarcığı ve eleştirel düşünme becerisi de gelişiyor.

Peki, nasıl başlanır? Araştırmalar, günde yalnızca 20 dakikalık derin okumanın bile ölçülebilir bir fark yarattığını gösteriyor. Telefonu başka bir odaya bırakmak, belirli bir zaman dilimi oluşturmak ve sessiz bir ortam hazırlamak küçük ama etkili adımlardır. Okumak bir lüks değil; düşünebilmek için bir gerekliliktir. Bu gerçeği kavrayan toplumlar, okumayı yalnızca bireysel bir zevk olarak değil, kolektif bir beceri olarak ele alır. Finlandiya'da okul öncesi çocuklara kitap hediye edilmesi bir devlet politikasıdır. Japonya'da ise toplu taşımada okuma o kadar yaygındır ki yayınevleri kitap boyutlarını buna göre tasarlar.

Türkiye'de ise okuma alışkanlığı, son yıllarda değişen medya tüketimiyle birlikte daralmıştır. Ancak bu durum tersine çevrilebilir. Tek bir kitap, tek bir sayfa, hatta tek bir cümle bile değişimin başlangıcı olabilir. Okumak, dünyaya başka gözlerle bakmayı öğrenmektir. Ve bu öğrenmenin yaşı yoktur."""
    },
    {
        "baslik": "Beyin Nasıl Öğrenir?",
        "sinif": 8,
        "tur": "Bilgi",
        "kelime_sayisi": 200,
        "icerik": """İnsan beyni yaklaşık 86 milyar nörondan oluşur. Bu nöronlar, sinaps adı verilen bağlantı noktaları aracılığıyla birbirleriyle iletişim kurar. Her öğrenme deneyiminde bu bağlantılardan bazıları güçlenir, bazıları ise yeni oluşur. Yeni bir şey öğrenirken beyin, nöronlar arasında yeni bağlantılar kurar. Bu sürece nöroplastisite, yani beynin esnekliği denir. Nöroplastisite sayesinde beyin, yaşam boyu öğrenmeye açık kalır. "Artık öğrenemem, yaşlandım." düşüncesi bilimsel açıdan doğru değildir.

Peki, en verimli şekilde nasıl öğrenilir? Araştırmalar, dağıtılmış tekrar yönteminin en etkili yaklaşımlardan biri olduğunu göstermektedir. Bir konuyu on saat boyunca tek seferde çalışmak yerine, aynı konuyu birkaç güne yayarak kısa seanslar hâlinde tekrar etmek kalıcı öğrenmeyi çok daha iyi destekler. Uyku da öğrenmenin vazgeçilmez bir parçasıdır. Beyin, gece boyunca gün içinde edinilen bilgileri işler, düzenler ve uzun süreli belleğe aktarır. Yetersiz uyku yalnızca yorgunluğa değil aynı zamanda hafıza sorunlarına da yol açar. Bu bilgileri dikkate alarak çalışmak, yani öğrenmeyi öğrenmek, en güçlü akademik becerilerden biridir. Meta-öğrenme olarak adlandırılan bu beceri, son yıllarda eğitimcilerin gündeminde önemli bir yer tutmaktadır. Çocuklara yalnızca bilgi vermek yeterli değildir; nasıl öğreneceklerini de öğretmek gerekir. Tekrar aralıkları nasıl ayarlanmalı? Hangi öğrenme yöntemi kişiye daha uygundur? Dikkat dağıldığında ne yapılmalıdır?

Beyni bir kas gibi düşünebiliriz: Doğru şekilde çalıştırıldığında gelişir, yanlış kullanıldığında zayıflar. Ve en önemlisi, öğrenmek için hiçbir zaman geç değildir. Beyin, öğrenmeye istekli olduğunuz sürece her yaşta yeni bağlantılar kurabilir."""
    },
    {
        "baslik": "Sınır Ötesi",
        "sinif": 8,
        "tur": "Hikaye",
        "kelime_sayisi": 177,
        "icerik": """Nehrin öte yanı yasaktı. Herkes bunu bilirdi. Neden yasak olduğunu bilen yoktu ama yasak olması yeterliydi. Çocuklar o tarafa geçmezdi. Köpekler bile geçmezdi. Ama Zeynep, nehrin karşısında bir kulübe görmüştü. Sabahları oradan duman yükselirdi. Demek ki birisi orada yaşıyordu.

Bir gün karar verdi. Sabah erken saatte, kimse yokken nehrin sığ bir yerinden geçti. Paçaları ıslandı, taşlara takıldı ama sonunda karşıya ulaştı. Kulübe küçüktü. Kapıda yaşlı bir adam oturuyordu. Zeynep'i görünce sadece baktı; ne kaçtı ne de bağırdı. "Yasak bölgeye girdin." dedi adam. "Biliyorum." dedi Zeynep. "Ama neden yasak olduğunu bilmiyorum. Sanırım kimse de bilmiyor." Adam hafifçe güldü. Yorgun bir gülüştü bu. "Ben de artık bilmiyorum." dedi. "Yıllar önce biri söyledi. Kimse sorgulamadı." Zeynep adama baktı. Sonra nehrin öte yanına, köyüne baktı. Her şey uzaktan daha küçük görünüyordu. "Bazı kurallar, sorgulanmadan var olmaya devam eder." dedi adam. "Sormak bazen en cesur eylemdir." Zeynep geri döndü. Suya girdi, nehri geçti. Ama artık aynı Zeynep değildi. Eve vardığında annesine bir soru sordu. "Yasak neden yasak?" Annesi şaşırdı. Cevap veremedi. O gece Zeynep uzun uzun düşündü. Bazı soruların cevabı olmayabilirdi. Ama soruyu sormamak hiçbir şeyi değiştirmezdi."""
    },
    {
        "baslik": "Biyoçeşitlilik: Neden Önemli?",
        "sinif": 8,
        "tur": "Bilgi",
        "kelime_sayisi": 185,
        "icerik": """Biyoçeşitlilik, bir ekosistemde yaşayan tüm canlı türlerinin, genetik çeşitliliğin ve yaşam alanlarının bütünüdür. Dünya üzerinde bugün yaklaşık 8 milyon türün yaşadığı tahmin edilmektedir. Bunların büyük bir bölümü ise henüz bilim tarafından keşfedilmemiştir.

Biyoçeşitlilik neden önemlidir? Çünkü her tür, içinde bulunduğu ekosistemin işleyişinde belirli bir rol üstlenir. Arılar çiçekleri tozlaştırır; onlar olmadan meyve oluşmaz. Toprak solucanları toprağı havalandırır; onlar olmadan tarım verimi düşer. Büyük yırtıcılar otobur popülasyonlarını dengede tutar; sayıları azaldığında ekosistem dengesi değişir. Bir türün yok olması zincirleme etkilere yol açabilir. Bir bitki türü ortadan kalkarsa ona bağlı böcek türleri yok olur, ardından bu böceklerle beslenen kuşlar etkilenir. Bu zincirleme etkiye eko-çöküş riski denir.

Günümüzde biyoçeşitlilik hızla azalmaktadır. Bunun başlıca nedenleri arasında ormansızlaşma, doğal alanların tarım arazisine dönüştürülmesi, kirlilik ve iklim değişikliği yer alır. Bilim insanları, şu anda altıncı kitlesel yok oluş sürecinde olduğumuzu ve bu sürecin temel nedeninin insan faaliyetleri olduğunu belirtmektedir. Biyoçeşitlilik bir lüks değil, yaşamın kendisidir. Peki, bireyler ne yapabilir? Yerel bitki türleri dikmek, pestisit kullanımını azaltmak ve doğal alanların korunmasını desteklemek küçük ama etkili adımlardır. Büyük değişimler, küçük kararların birikmesiyle ortaya çıkar. Yok olan bir tür geri gelmez. Bu nedenle korumak, yok olduktan sonra üzülmekten çok daha değerlidir."""
    },
]


def yukle_metinleri():
    token = get_token()
    if not token:
        print("Token alınamadı, çıkılıyor.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    basarili = 0
    hatali = 0

    for metin in METINLER:
        try:
            # Önce gelisim/metinler endpoint'ini dene
            r = requests.post(
                f"{BASE_URL}/api/gelisim/metinler",
                json=metin,
                headers=headers
            )
            if r.status_code in (200, 201):
                print(f"✓ [{metin['sinif']}. Sınıf] {metin['baslik']}")
                basarili += 1
            else:
                print(f"✗ [{metin['sinif']}. Sınıf] {metin['baslik']} → {r.status_code}: {r.text[:100]}")
                hatali += 1
        except Exception as e:
            print(f"✗ [{metin['sinif']}. Sınıf] {metin['baslik']} → Hata: {e}")
            hatali += 1

    print(f"\n{'='*50}")
    print(f"Tamamlandı: {basarili} başarılı, {hatali} hatalı")
    print(f"Toplam metin: {len(METINLER)}")


if __name__ == "__main__":
    yukle_metinleri()
