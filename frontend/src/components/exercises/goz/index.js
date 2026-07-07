// Yeni göz/görme/tarama egzersizleri kayıt defteri.
// EgzersizlerModul (App.js) bu listeyi kendi `egzersizler` dizisine ekler ve
// aktif egzersiz buradan ise `render(onTamamla)` ile bileşeni çizer.
//
// Her kayıt: { id, baslik, icon, aciklama, renk, kat, render }
//   kat: 'goz' (göz hareketi) | 'gorme' (görme alanı) | 'okuma' (tarama) | 'dikkat'
import React from "react";
import BuyuyenSekil from "./BuyuyenSekil";
import Nokta13 from "./Nokta13";
import Ponte from "./Ponte";
import DikeyZikzak from "./DikeyZikzak";
import DairesalGoz from "./DairesalGoz";
import Kolonlar from "./Kolonlar";
import AcilanNesneler from "./AcilanNesneler";
import KumSaati from "./KumSaati";
import KarelKareGorme from "./KarelKareGorme";
import BenzerKelimeler from "./BenzerKelimeler";
import KelimeArama from "./KelimeArama";
import MetinArama from "./MetinArama";
import TekMiCiftMi from "./TekMiCiftMi";
import KutuluOkuma from "./KutuluOkuma";

export const GOZ_YENI_EGZERSIZLER = [
  // ── Büyüyen Şekiller serisi (görme alanı) ──
  { id: "buyuyen-altigen",    baslik: "Büyüyen Altıgen",    icon: "⬡", aciklama: "Merkezden dışa büyüyen altıgen; görme alanını genişletir.",    renk: "from-sky-500 to-blue-600",       kat: "gorme", render: (t) => <BuyuyenSekil tip="altigen" onTamamla={t} /> },
  { id: "buyuyen-daire",      baslik: "Büyüyen Daire",      icon: "⭕", aciklama: "Merkezden dışa büyüyen daire halkaları.",                       renk: "from-emerald-500 to-green-600",  kat: "gorme", render: (t) => <BuyuyenSekil tip="daire" onTamamla={t} /> },
  { id: "buyuyen-dikdortgen", baslik: "Büyüyen Dikdörtgen", icon: "▭", aciklama: "Merkezden dışa büyüyen dikdörtgen; yatay görme açıklığı.",       renk: "from-orange-500 to-red-500",     kat: "gorme", render: (t) => <BuyuyenSekil tip="dikdortgen" onTamamla={t} /> },
  { id: "buyuyen-elips",      baslik: "Büyüyen Elips",      icon: "⬮", aciklama: "Merkezden dışa büyüyen elips halkaları.",                       renk: "from-purple-500 to-fuchsia-600", kat: "gorme", render: (t) => <BuyuyenSekil tip="elips" onTamamla={t} /> },
  { id: "buyuyen-kare",       baslik: "Büyüyen Kare",       icon: "⬜", aciklama: "Merkezden dışa büyüyen kare halkaları.",                        renk: "from-pink-500 to-rose-600",      kat: "gorme", render: (t) => <BuyuyenSekil tip="kare" onTamamla={t} /> },

  // ── Göz hareketi ──
  { id: "nokta-13",       baslik: "13 Nokta Göz Egzersizi", icon: "✨", aciklama: "Yıldız deseninde 13 nokta arasında metronomlu göz sıçraması.", renk: "from-amber-500 to-yellow-600",   kat: "goz", render: (t) => <Nokta13 onTamamla={t} /> },
  { id: "ponte",          baslik: "PONTE: Sinüs Takip",     icon: "〰️", aciklama: "Dikey sinüs dalgası boyunca yumuşak nokta takibi.",           renk: "from-cyan-500 to-sky-600",       kat: "goz", render: (t) => <Ponte onTamamla={t} /> },
  { id: "dikey-zikzak",   baslik: "Dikey Zikzak",           icon: "⚡", aciklama: "Top yukarıdan aşağıya zikzak çizerek iner.",                  renk: "from-violet-500 to-purple-600",  kat: "goz", render: (t) => <DikeyZikzak onTamamla={t} /> },
  { id: "dairesel-goz",   baslik: "Dairesel Göz",           icon: "🔵", aciklama: "Nokta yumuşak dairesel yörüngede döner.",                     renk: "from-teal-500 to-cyan-600",      kat: "goz", render: (t) => <DairesalGoz onTamamla={t} /> },
  { id: "kolonlar",       baslik: "Kolonlar",               icon: "📊", aciklama: "Kolonlar arası ritmik göz hareketiyle okuma temposu.",       renk: "from-indigo-500 to-blue-600",    kat: "goz", render: (t) => <Kolonlar onTamamla={t} /> },
  { id: "acilan-dikey",   baslik: "Açılan Nesneler: Dikey", icon: "↕️", aciklama: "Nesneler merkezden dikey açılır; algı genişliği artar.",      renk: "from-blue-500 to-indigo-600",    kat: "goz", render: (t) => <AcilanNesneler yon="dikey" onTamamla={t} /> },
  { id: "acilan-yatay",   baslik: "Açılan Nesneler: Yatay", icon: "↔️", aciklama: "Nesneler merkezden yatay açılır; algı genişliği artar.",      renk: "from-blue-500 to-indigo-600",    kat: "goz", render: (t) => <AcilanNesneler yon="yatay" onTamamla={t} /> },

  // ── Görme alanı / odaklanma ──
  { id: "kum-saati",      baslik: "Kum Saati (Elina)",      icon: "⏳", aciklama: "X desenli kollarda çevresel harfleri merkeze bakarak oku.",  renk: "from-amber-500 to-orange-600",   kat: "gorme", render: (t) => <KumSaati onTamamla={t} /> },
  { id: "karel-kare",     baslik: "KAREL: Kare Görme",      icon: "🔤", aciklama: "Harf gridinde işaretli harf merkezle aynı mı? Yanıtla.",      renk: "from-lime-500 to-green-600",     kat: "gorme", render: (t) => <KarelKareGorme onTamamla={t} /> },

  // ── Kelime / metin arama ──
  { id: "kutulu-okuma",     baslik: "Kutulu Okuma",         icon: "📦", aciklama: "Akan metinde sağ/sol ok ile ilerledikçe kutular birikir; okunan kelimeler kutulu kalır. Metin sınıf+seviyene göre otomatik gelir.", renk: "from-indigo-500 to-violet-600", kat: "okuma", render: (t) => <KutuluOkuma onTamamla={t} /> },
  { id: "benzer-kelimeler", baslik: "Benzer Kelimeler",     icon: "🔎", aciklama: "4 kutudan iki kelimesi farklı olanı bul.",                    renk: "from-rose-500 to-pink-600",      kat: "okuma", render: (t) => <BenzerKelimeler onTamamla={t} /> },
  { id: "kelime-arama",     baslik: "Kelime Arama",         icon: "🧩", aciklama: "Harf gridinde gizli kelimeleri bul.",                         renk: "from-fuchsia-500 to-purple-600", kat: "okuma", render: (t) => <KelimeArama onTamamla={t} /> },
  { id: "metin-arama",      baslik: "Metin Arama",          icon: "📄", aciklama: "Uzun metinde hedef kelimeyi hızlıca tara ve bul.",            renk: "from-sky-500 to-blue-600",       kat: "okuma", render: (t) => <MetinArama onTamamla={t} /> },

  // ── Dikkat / ayırt etme ──
  { id: "tek-cift",         baslik: "Tek mi? Çift mi?",     icon: "🔢", aciklama: "Rakam gridinde tüm çift sayıları işaretle.",                  renk: "from-slate-500 to-gray-600",     kat: "dikkat", render: (t) => <TekMiCiftMi onTamamla={t} /> },
];

// id → render fonksiyonu hızlı erişim.
export const GOZ_YENI_RENDER = Object.fromEntries(
  GOZ_YENI_EGZERSIZLER.map((e) => [e.id, e.render])
);
