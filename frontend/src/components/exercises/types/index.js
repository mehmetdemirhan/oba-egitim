// Egzersiz tip render kayıt defteri.
// Yeni tip eklemek = burada 1 satır + types/ altında 1 küçük render komponenti.
// Motor (ExerciseEngine) bu haritadan tipe uygun komponenti seçer.
import DemoRender from "./DemoRender";
import EslestirmeRender from "./EslestirmeRender";
import ClozeRender from "./ClozeRender";
import EsKarsitRender from "./EsKarsitRender";
import CumleSiralamaRender from "./CumleSiralamaRender";
import OlaySiralamaRender from "./OlaySiralamaRender";
// Tier 2 (FAZ 2)
import BesNBirKRender from "./BesNBirKRender";
import AnaFikirRender from "./AnaFikirRender";
import CikarimRender from "./CikarimRender";
import SebepSonucRender from "./SebepSonucRender";
import TahminEtRender from "./TahminEtRender";
// Tier 3 (FAZ 3)
import SecmeliRender from "./SecmeliRender";
import AnagramRender from "./AnagramRender";
import BulmacaRender from "./BulmacaRender";
import HafizaKartiRender from "./HafizaKartiRender";
import KelimeYagmuruRender from "./KelimeYagmuruRender";
// Tier 4 (FAZ 4)
import FrayerRender from "./FrayerRender";
import AnlamHaritasiRender from "./AnlamHaritasiRender";
import VennRender from "./VennRender";
import TekerlemeRender from "./TekerlemeRender";
import DiyalogRender from "./DiyalogRender";
// FAZ 5: Fonolojik farkındalık
import FonolojiRender from "./FonolojiRender";

const RENDER_MAP = {
  demo: DemoRender,
  // Tier 1 (FAZ 1)
  kelime_anlam_eslestirme: EslestirmeRender,
  cloze_bosluk_doldurma: ClozeRender,
  es_karsit_anlamli: EsKarsitRender,
  karisik_cumle_siralama: CumleSiralamaRender,
  hikaye_olay_siralama: OlaySiralamaRender,
  // Tier 2 (FAZ 2)
  bes_n_bir_k: BesNBirKRender,
  ana_fikir: AnaFikirRender,
  cikarim: CikarimRender,
  sebep_sonuc: SebepSonucRender,
  tahmin_et: TahminEtRender,
  // Tier 3 (FAZ 3)
  anagram: AnagramRender,
  bulmaca: BulmacaRender,
  hafiza_karti: HafizaKartiRender,
  kelime_yagmuru: KelimeYagmuruRender,
  kelime_merdiveni: SecmeliRender,   // standart çoktan seçmeli
  baglam_ipucu: SecmeliRender,       // standart çoktan seçmeli
  // Tier 4 (FAZ 4)
  frayer: FrayerRender,
  anlam_haritasi: AnlamHaritasiRender,
  venn: VennRender,
  tekerleme: TekerlemeRender,
  sight_words: SecmeliRender,        // standart çoktan seçmeli
  diyalog: DiyalogRender,
  // FAZ 5: Fonolojik farkındalık (hepsi Web Speech destekli tek render)
  hece_sayma: FonolojiRender,
  hece_birlestirme: FonolojiRender,
  ilk_ses: FonolojiRender,
  son_ses: FonolojiRender,
  kafiye: FonolojiRender,
  ses_birlestirme: FonolojiRender,
  ses_cikarma: FonolojiRender,
};

export function getRenderComponent(tip) {
  return RENDER_MAP[tip] || null;
}

export default RENDER_MAP;
