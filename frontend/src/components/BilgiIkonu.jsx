import React, { useState } from "react";
import { Info } from "lucide-react";
import grafikAciklamalari from "../data/grafikAciklamalari";

/**
 * BilgiIkonu — grafik/kart köşesine küçük (i) ikonu. Tıklayınca "Nasıl hesaplanır"
 * + "Ne işe yarar" bölümlü bir popover açılır. İçerik tek kaynaktan (grafikAciklamalari).
 *
 * Kullanım:  <BilgiIkonu k="huni" />           (sözlükten)
 *            <BilgiIkonu nasil="..." ne="..." /> (doğrudan)
 * konum: "tr" (top-right, vars.) | "tl" | "br" | "bl" — popover açılış yönü.
 */
export default function BilgiIkonu({ k, nasil, ne, baslik, konum = "tr" }) {
  const [acik, setAcik] = useState(false);
  const veri = k ? grafikAciklamalari[k] : null;
  const nasilMetin = nasil ?? veri?.nasil;
  const neMetin = ne ?? veri?.ne;
  if (!nasilMetin && !neMetin) return null;

  const yonSinif = {
    tr: "right-0 top-6",
    tl: "left-0 top-6",
    br: "right-0 bottom-6",
    bl: "left-0 bottom-6",
  }[konum] || "right-0 top-6";

  return (
    <span className="relative inline-flex align-middle">
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setAcik((v) => !v); }}
        aria-label="Nasıl hesaplanır?"
        title="Nasıl hesaplanır?"
        className="text-slate-400 hover:text-blue-600 transition-colors focus:outline-none"
      >
        <Info className="h-4 w-4" />
      </button>
      {acik && (
        <>
          {/* Dışarı tıkla → kapat */}
          <div className="fixed inset-0 z-40" onClick={(e) => { e.stopPropagation(); setAcik(false); }} />
          <div
            onClick={(e) => e.stopPropagation()}
            className={`absolute z-50 ${yonSinif} w-72 max-w-[80vw] rounded-xl border border-line bg-surface shadow-xl p-3 text-left`}
          >
            {baslik && <div className="text-sm font-semibold text-content mb-1.5">{baslik}</div>}
            {nasilMetin && (
              <div className="mb-2">
                <div className="text-[11px] font-bold uppercase tracking-wide text-blue-600 mb-0.5">Nasıl hesaplanır</div>
                <div className="text-xs text-subtle leading-relaxed">{nasilMetin}</div>
              </div>
            )}
            {neMetin && (
              <div>
                <div className="text-[11px] font-bold uppercase tracking-wide text-emerald-600 mb-0.5">Ne işe yarar</div>
                <div className="text-xs text-subtle leading-relaxed">{neMetin}</div>
              </div>
            )}
          </div>
        </>
      )}
    </span>
  );
}
