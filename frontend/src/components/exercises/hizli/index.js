// Hızlı Okuma egzersizleri kayıt defteri.
// EgzersizlerModul (App.js) bu listeyi kendi `egzersizler` dizisine ekler; aktif
// egzersiz buradansa HIZLI_OKUMA_RENDER[id](onTamamla) ile bileşeni çizer.
// m5bilisim.com/tr/hizli-okuma'daki davranış taklit edilir (kod kopyalanmaz).
import React from "react";
import BlokOkuma from "./BlokOkuma";
import Golgeleme from "./Golgeleme";
import Gruplama from "./Gruplama";
import Takistoskop from "./Takistoskop";

export const HIZLI_OKUMA_EGZERSIZLER = [
  { id: "blok-okuma",  baslik: "Blok Okuma",  icon: "🧱", aciklama: "Metin, birkaç kelimelik bloklar hâlinde ortada hızla gösterilir; her bloğa tek bakışta odaklan.", renk: "from-indigo-500 to-blue-600",   kat: "hizli-okuma", render: (t) => <BlokOkuma onTamamla={t} /> },
  { id: "golgeleme",   baslik: "Gölgeleme",   icon: "🌗", aciklama: "Hareketli vurgu metin üzerinde kelime kelime ilerler; vurguya yetişerek tempolu oku.",        renk: "from-violet-500 to-purple-600", kat: "hizli-okuma", render: (t) => <Golgeleme onTamamla={t} /> },
  { id: "gruplama",    baslik: "Gruplama",    icon: "🔗", aciklama: "Metin anlam gruplarına ayrılır; grup grup okuyarak göz sıçramasını azalt.",                    renk: "from-teal-500 to-emerald-600",  kat: "hizli-okuma", render: (t) => <Gruplama onTamamla={t} /> },
  { id: "takistoskop", baslik: "Takistoskop", icon: "⚡", aciklama: "Kelime/grup çok kısa süre parlar; tek bakışta tanı. Algı genişliğini ve hızı artırır.",         renk: "from-amber-500 to-orange-600",  kat: "hizli-okuma", render: (t) => <Takistoskop onTamamla={t} /> },
];

export const HIZLI_OKUMA_RENDER = Object.fromEntries(
  HIZLI_OKUMA_EGZERSIZLER.map((e) => [e.id, e.render])
);
