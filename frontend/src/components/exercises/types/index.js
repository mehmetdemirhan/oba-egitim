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
};

export function getRenderComponent(tip) {
  return RENDER_MAP[tip] || null;
}

export default RENDER_MAP;
