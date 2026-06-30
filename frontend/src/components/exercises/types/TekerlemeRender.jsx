import React from "react";
import SecmeliRender from "./SecmeliRender";

/**
 * Tekerleme render bileşeni.
 * İçerik şeması: { metin: "tekerleme (çok satırlı)", sorular: [{ soru, secenekler, dogru }] }
 *
 * Tekerleme metni satırları korunarak üstte gösterilir; ardından uyak/eksik
 * kelime/ses tekrarı soruları çoktan seçmeli akışıyla sorulur.
 *
 * Render sözleşmesi: { icerik, onCevap, soruNo }
 */
export default function TekerlemeRender({ icerik, onCevap, soruNo }) {
  const metin = icerik?.metin;
  return (
    <div className="space-y-3">
      {metin && (
        <div className="bg-pink-50 border border-pink-200 rounded-2xl p-4">
          <div className="text-xs font-semibold text-pink-500 mb-2 uppercase tracking-wide">🎵 Tekerleme</div>
          <div className="text-[15px] leading-relaxed text-gray-800 whitespace-pre-line font-medium">{metin}</div>
        </div>
      )}
      <SecmeliRender icerik={icerik} onCevap={onCevap} soruNo={soruNo} />
    </div>
  );
}
