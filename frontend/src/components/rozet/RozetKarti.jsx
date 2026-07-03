import React from "react";

/**
 * RozetKarti — tek bir rozet kartı (kazanıldı/kilitli).
 * Öğrenci, öğretmen, admin ve veli görünümlerinde ortak kullanılır.
 *
 * Props:
 *   tanim        — {kod, ad, ikon, seviye, odul_puan, ...}
 *   kazanildi    — bool
 *   secili       — bool (vurgu halkası)
 *   onKlik       — () => void
 */
export const SEVIYE_RENK = {
  bronz: "bg-orange-100 text-orange-700 border-orange-200",
  gumus: "bg-gray-100 text-gray-700 border-gray-200",
  altin: "bg-yellow-100 text-yellow-700 border-yellow-200",
  platin: "bg-cyan-100 text-cyan-700 border-cyan-200",
  elmas: "bg-purple-100 text-purple-700 border-purple-200",
};

export function rozetPuan(t) {
  if (!t) return 0;
  return t.odul_puan ?? t.puan ?? t.xp ?? 0;
}

export default function RozetKarti({ tanim, kazanildi, secili, onKlik }) {
  return (
    <div
      onClick={onKlik}
      title={tanim.ad}
      className={`text-center p-1.5 rounded-lg cursor-pointer transition-all hover:scale-105 ${
        kazanildi ? "bg-orange-50 border border-orange-200" : "opacity-25 hover:opacity-50"
      } ${secili ? "ring-2 ring-blue-400 scale-105" : ""}`}
    >
      <div className="text-2xl leading-none">{kazanildi ? tanim.ikon : "🔒"}</div>
      <div className="mt-1 text-[10px] font-medium text-gray-700 truncate">{tanim.ad}</div>
      <span
        className={`inline-block mt-0.5 text-[9px] px-1 py-0.5 rounded-full border ${
          SEVIYE_RENK[tanim.seviye] || "bg-gray-100 text-gray-600"
        }`}
      >
        {tanim.seviye}
      </span>
    </div>
  );
}
