import React from "react";
import SecmeliRender from "./SecmeliRender";

/**
 * Frayer Modeli render bileşeni.
 * İçerik şeması: { kelime: "...", sorular: [{ soru, secenekler, dogru }] }
 *
 * Üstte hedef kelime ve Frayer'ın dört bölgesi (Tanım / Özellik / Örnek /
 * Örnek Değil) hatırlatıcı olarak gösterilir; öğrenci her ifadenin hangi bölgeye
 * ait olduğunu seçer (ortak çoktan seçmeli akış).
 *
 * Render sözleşmesi: { icerik, onCevap, soruNo }
 */
const BOLGELER = [
  { ad: "Tanım", ikon: "📖" },
  { ad: "Özellik", ikon: "✨" },
  { ad: "Örnek", ikon: "✅" },
  { ad: "Örnek Değil", ikon: "🚫" },
];

export default function FrayerRender({ icerik, onCevap, soruNo }) {
  const kelime = icerik?.kelime;
  return (
    <div className="space-y-3">
      {kelime && (
        <div className="bg-violet-50 border border-violet-200 rounded-2xl p-4 text-center">
          <div className="text-xs font-semibold text-violet-500 uppercase tracking-wide mb-1">🗂️ Frayer Modeli — Kelime</div>
          <div className="text-2xl font-extrabold text-violet-800 mb-3">{kelime}</div>
          <div className="grid grid-cols-2 gap-2">
            {BOLGELER.map((b) => (
              <div key={b.ad} className="rounded-xl bg-white border border-violet-100 py-2 text-xs font-semibold text-gray-600">
                {b.ikon} {b.ad}
              </div>
            ))}
          </div>
        </div>
      )}
      <SecmeliRender icerik={icerik} onCevap={onCevap} soruNo={soruNo}
        soruGoster={(soru) => (
          <div className="mb-4">
            <div className="text-xs text-gray-400 mb-1">Bu ifade hangi bölgeye aittir?</div>
            <div className="text-lg font-bold text-gray-900">{soru.soru}</div>
          </div>
        )} />
    </div>
  );
}
