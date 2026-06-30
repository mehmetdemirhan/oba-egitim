import React from "react";
import SecmeliRender from "./SecmeliRender";

/**
 * Okuduğunu anlama (Tier 2) ortak render bileşeni.
 * İçerik şeması: { metin: "kısa paragraf", sorular: [{ soru, secenekler, dogru }] }
 *
 * Metni bir kez üstte (sabit) gösterir; gerisi ortak çoktan seçmeli akışıdır.
 * Tüm sorular boyunca aynı metin görünür kalır (icerik soru başına değişmez).
 *
 * Render sözleşmesi: { icerik, onCevap, soruNo }
 */
export default function OkumaSecmeliRender({ icerik, onCevap, soruNo }) {
  const metin = icerik?.metin;
  return (
    <div className="space-y-3">
      {metin && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-[15px] leading-relaxed text-gray-800">
          <div className="text-xs font-semibold text-amber-600 mb-1 uppercase tracking-wide">📄 Metin</div>
          {metin}
        </div>
      )}
      <SecmeliRender icerik={icerik} onCevap={onCevap} soruNo={soruNo} />
    </div>
  );
}
