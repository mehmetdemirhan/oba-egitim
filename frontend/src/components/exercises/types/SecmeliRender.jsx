import React, { useState } from "react";

/**
 * Ortak çoktan seçmeli (secmeli) render bileşeni.
 *
 * Cloze (boşluk doldurma) ve Eş/Karşıt anlamlı tipleri bunu kullanır; tek fark
 * sorunun nasıl gösterildiğidir. `soruGoster` prop'u ile başlık özelleştirilebilir.
 *
 * Render sözleşmesi: { icerik, onCevap, soruNo }
 *   onCevap(secilenIndeks) -> Promise<{dogru, dogru_cevap}>
 */
export default function SecmeliRender({ icerik, onCevap, soruNo, soruGoster }) {
  const soru = (icerik?.sorular || [])[soruNo];
  const [secili, setSecili] = useState(null);
  const [sonuc, setSonuc] = useState(null);

  // Soru değişince yerel durumu sıfırla
  React.useEffect(() => {
    setSecili(null);
    setSonuc(null);
  }, [soruNo]);

  if (!soru) return null;

  const tikla = async (i) => {
    if (secili !== null) return; // bir kez cevapla
    setSecili(i);
    const r = await onCevap(i);
    setSonuc(r);
  };

  const renk = (i) => {
    if (secili === null) return "border-gray-200 bg-white hover:bg-gray-50";
    if (sonuc && i === sonuc.dogru_cevap) return "border-green-400 bg-green-50";
    if (i === secili) return "border-red-400 bg-red-50";
    return "border-gray-200 bg-white opacity-60";
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        {soruGoster ? soruGoster(soru) : (
          <div className="text-lg font-bold text-gray-900 mb-4 whitespace-pre-line">{soru.soru}</div>
        )}
        <div className="grid gap-2">
          {(soru.secenekler || []).map((s, i) => (
            <button
              key={i}
              onClick={() => tikla(i)}
              disabled={secili !== null}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl border text-left text-sm font-medium transition-all ${renk(i)}`}>
              <span className="w-6 h-6 flex items-center justify-center rounded-lg bg-gray-100 text-gray-600 text-xs font-bold">
                {String.fromCharCode(65 + i)}
              </span>
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
