// Egzersiz tip render kayıt defteri.
// Yeni tip eklemek = burada 1 satır + types/ altında 1 küçük render komponenti.
// Motor (ExerciseEngine) bu haritadan tipe uygun komponenti seçer.
import DemoRender from "./DemoRender";
import EslestirmeRender from "./EslestirmeRender";
import ClozeRender from "./ClozeRender";
import EsKarsitRender from "./EsKarsitRender";
import CumleSiralamaRender from "./CumleSiralamaRender";
import OlaySiralamaRender from "./OlaySiralamaRender";

const RENDER_MAP = {
  demo: DemoRender,
  // Tier 1 (FAZ 1)
  kelime_anlam_eslestirme: EslestirmeRender,
  cloze_bosluk_doldurma: ClozeRender,
  es_karsit_anlamli: EsKarsitRender,
  karisik_cumle_siralama: CumleSiralamaRender,
  hikaye_olay_siralama: OlaySiralamaRender,
};

export function getRenderComponent(tip) {
  return RENDER_MAP[tip] || null;
}

export default RENDER_MAP;
