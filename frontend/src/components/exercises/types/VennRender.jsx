import React from "react";
import SecmeliRender from "./SecmeliRender";

/**
 * Venn Şeması render bileşeni.
 * İçerik şeması: { a: "Kedi", b: "Balık", sorular: [{ soru, secenekler, dogru }] }
 *   secenekler genelde [a, b, "Her ikisi"].
 *
 * Üstte iki kavram, kesişen iki daire görseliyle gösterilir; öğrenci her
 * özelliğin yalnız A'ya, yalnız B'ye mi yoksa her ikisine mi ait olduğunu seçer.
 *
 * Render sözleşmesi: { icerik, onCevap, soruNo }
 */
export default function VennRender({ icerik, onCevap, soruNo }) {
  const a = icerik?.a;
  const b = icerik?.b;
  return (
    <div className="space-y-3">
      {(a || b) && (
        <div className="bg-rose-50 border border-rose-200 rounded-2xl p-4">
          <div className="text-xs font-semibold text-rose-500 uppercase tracking-wide mb-3 text-center">⭕ Venn Şeması — Karşılaştır</div>
          <div className="flex items-center justify-center gap-0">
            <div className="w-24 h-24 -mr-6 rounded-full bg-indigo-400/40 border-2 border-indigo-400 flex items-center justify-center text-sm font-bold text-indigo-800">
              {a}
            </div>
            <div className="w-24 h-24 -ml-6 rounded-full bg-rose-400/40 border-2 border-rose-400 flex items-center justify-center text-sm font-bold text-rose-800">
              {b}
            </div>
          </div>
        </div>
      )}
      <SecmeliRender icerik={icerik} onCevap={onCevap} soruNo={soruNo}
        soruGoster={(soru) => (
          <div className="mb-4">
            <div className="text-xs text-gray-400 mb-1">Bu özellik kime aittir?</div>
            <div className="text-lg font-bold text-gray-900">{soru.soru}</div>
          </div>
        )} />
    </div>
  );
}
