// Egzersiz tip render kayıt defteri.
// Yeni tip eklemek = burada 1 satır + types/ altında 1 küçük render komponenti.
// Motor (ExerciseEngine) bu haritadan tipe uygun komponenti seçer.
import DemoRender from "./DemoRender";

const RENDER_MAP = {
  demo: DemoRender,
};

export function getRenderComponent(tip) {
  return RENDER_MAP[tip] || null;
}

export default RENDER_MAP;
