import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { ChevronRight } from "lucide-react";
import { PersonaBalon, PERSONA_UI } from "./Personalar";

/**
 * YoneticiAdimlar — admin dashboard'unun üstünde "Sıradaki Adımlar" kartı (AYDA'nın sesiyle).
 * İki kaynak: kurulum/deneyim görevleri (Yönetim Skoru puanı, oto-algılanır) + dinamik
 * bekleyen işler ("Gözden Kaçan Yok" ile aynı kaynak). Hepsi tıklanınca ilgili yere götürür.
 */
export default function YoneticiAdimlar({ apiBase, onNavigate }) {
  const [veri, setVeri] = useState(null);
  const p = PERSONA_UI.ayda;
  const api = (x) => `${apiBase}${x}`;

  const yukle = useCallback(async () => {
    try { const r = await axios.get(api("/ai/ceo/yonetici-adimlar")); setVeri(r.data); } catch (e) {}
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  if (!veri) return null;
  const acikKurulum = (veri.kurulum || []).filter(k => !k.tamamlandi);
  const dinamik = veri.dinamik || [];
  if (acikKurulum.length === 0 && dinamik.length === 0) return null;

  const git = async (hedef, gorev) => {
    if (gorev?.ziyaret) { try { await axios.post(api(`/ai/ceo/yonetici-adimlar/ziyaret/${gorev.id}`)); } catch (e) {} }
    if (onNavigate && hedef) onNavigate(hedef);
    setTimeout(yukle, 400);
  };

  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <PersonaBalon persona="ayda" mesaj={veri.mesaj} size={44} />
        {veri.kurulum_toplam > 0 && <span className="text-xs text-subtle shrink-0">Kurulum {veri.kurulum_biten}/{veri.kurulum_toplam}</span>}
      </div>
      <div className="grid grid-cols-1 gap-2 mt-2 max-h-64 overflow-auto">
        {dinamik.map((d, i) => (
          <button key={"d" + i} onClick={() => git(d.hedef)} className="flex items-center justify-between text-left rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 hover:ring-2 hover:ring-amber-200">
            <span className="text-sm text-amber-800">{d.baslik}</span><ChevronRight className="h-4 w-4 text-amber-500" />
          </button>
        ))}
        {acikKurulum.map(k => (
          <button key={k.id} onClick={() => git(k.hedef, k)} className="flex items-center justify-between text-left rounded-lg border border-line px-3 py-2 hover:bg-app">
            <span><span className="text-sm text-content">{k.baslik}</span><span className="text-[11px] text-subtle ml-1">+{k.puan} puan</span></span>
            <ChevronRight className="h-4 w-4 text-slate-400" />
          </button>
        ))}
      </div>
    </div>
  );
}
