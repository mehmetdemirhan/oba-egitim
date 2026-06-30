import React, { useMemo, useState, useEffect } from "react";

/**
 * Kelime-Anlam Eşleştirme render bileşeni.
 * İçerik şeması: { ciftler: [{ sol: "kelime", sag: "anlam" }] }
 *
 * Motor her çifti ayrı bir "soru" sayar (puanlama="eslesme"); aktif kelime
 * ciftler[soruNo].sol'dur. Öğrenci sağdaki anlamlardan doğru olanı seçer ve
 * cevap {sol: soruNo, sag: secilenAnlam} olarak gönderilir.
 *
 * Render sözleşmesi: { icerik, onCevap, soruNo }
 *   onCevap(cevap) -> Promise<{dogru, dogru_cevap}>
 */
export default function EslestirmeRender({ icerik, onCevap, soruNo }) {
  const ciftler = icerik?.ciftler || [];
  const cift = ciftler[soruNo];
  const [secili, setSecili] = useState(null);
  const [sonuc, setSonuc] = useState(null);

  // Sağ taraf seçenekleri: tüm anlamlar, sabit (karıştırılmış) sırayla
  const secenekler = useMemo(() => {
    const anlamlar = ciftler.map((c) => c.sag);
    // Deterministik basit karıştırma (içerik sabit kaldıkça aynı sıra)
    return anlamlar
      .map((a, i) => ({ a, k: (i * 7 + 3) % Math.max(1, anlamlar.length) }))
      .sort((x, y) => x.k - y.k)
      .map((o) => o.a);
  }, [ciftler]);

  useEffect(() => {
    setSecili(null);
    setSonuc(null);
  }, [soruNo]);

  if (!cift) return null;

  const tikla = async (anlam) => {
    if (secili !== null) return;
    setSecili(anlam);
    const r = await onCevap({ sol: soruNo, sag: anlam });
    setSonuc(r);
  };

  const renk = (anlam) => {
    if (secili === null) return "border-gray-200 bg-white hover:bg-gray-50";
    if (sonuc && anlam === cift.sag) return "border-green-400 bg-green-50";
    if (anlam === secili) return "border-red-400 bg-red-50";
    return "border-gray-200 bg-white opacity-60";
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        <div className="text-sm text-gray-500 mb-2">Bu kelimenin anlamını seç:</div>
        <div className="inline-block px-5 py-2 rounded-xl bg-indigo-50 text-indigo-700 text-xl font-extrabold mb-4">
          {cift.sol}
        </div>
        <div className="grid gap-2">
          {secenekler.map((anlam, i) => (
            <button
              key={i}
              onClick={() => tikla(anlam)}
              disabled={secili !== null}
              className={`px-4 py-3 rounded-xl border text-left text-sm font-medium transition-all ${renk(anlam)}`}>
              {anlam}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
