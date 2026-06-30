import React from "react";
import SecmeliRender from "./SecmeliRender";

/**
 * Anlam Haritası render bileşeni.
 * İçerik şeması: { merkez: "okul", sorular: [{ soru, secenekler, dogru }] }
 *
 * Üstte merkez kelime bir baloncuk olarak gösterilir; öğrenci merkez kelimeyle
 * ilişkili kavramları çoktan seçmeli olarak belirler.
 *
 * Render sözleşmesi: { icerik, onCevap, soruNo }
 */
export default function AnlamHaritasiRender({ icerik, onCevap, soruNo }) {
  const merkez = icerik?.merkez;
  return (
    <div className="space-y-3">
      {merkez && (
        <div className="bg-teal-50 border border-teal-200 rounded-2xl p-4 flex flex-col items-center">
          <div className="text-xs font-semibold text-teal-500 uppercase tracking-wide mb-2">🕸️ Anlam Haritası — Merkez Kelime</div>
          <div className="px-6 py-3 rounded-full bg-teal-500 text-white text-xl font-extrabold shadow-md">
            {merkez}
          </div>
          <div className="text-[11px] text-teal-600 mt-2">Bu kelimeyle ilişkili olanı seç.</div>
        </div>
      )}
      <SecmeliRender icerik={icerik} onCevap={onCevap} soruNo={soruNo} />
    </div>
  );
}
