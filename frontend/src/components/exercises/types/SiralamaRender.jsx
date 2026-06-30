import React, { useState, useEffect } from "react";

/**
 * Ortak sıralama (sira) render bileşeni.
 *
 * Hem "karışık cümle sıralama" hem "hikâye olay sıralama" tipleri bunu kullanır.
 * Öğrenci parçalara sırayla tıklayarak diziyi kurar; "Kontrol Et" ile gönderir.
 * Motor puanlama="sira" olduğundan tek gönderim yapılır; cevap, parçaların
 * seçilen sırasındaki orijinal indeks dizisidir ve icerik["dogru_sira"] ile
 * karşılaştırılır.
 *
 * props: { ogeler: string[], onCevap, etiket }
 *   onCevap(seciliSira) -> Promise<{dogru, dogru_cevap}>
 */
export default function SiralamaRender({ ogeler = [], onCevap, etiket }) {
  const [sira, setSira] = useState([]); // seçilen orijinal indeksler
  const [sonuc, setSonuc] = useState(null);
  const [bekliyor, setBekliyor] = useState(false);

  useEffect(() => {
    setSira([]);
    setSonuc(null);
  }, [ogeler]);

  const secili = (i) => sira.includes(i);
  const tamam = sira.length === ogeler.length && ogeler.length > 0;

  const tikla = (i) => {
    if (sonuc || secili(i)) return;
    setSira((s) => [...s, i]);
  };

  const geriAl = () => {
    if (sonuc) return;
    setSira((s) => s.slice(0, -1));
  };

  const sifirla = () => {
    if (sonuc) return;
    setSira([]);
  };

  const gonder = async () => {
    if (!tamam || bekliyor) return;
    setBekliyor(true);
    const r = await onCevap(sira);
    setSonuc(r);
    setBekliyor(false);
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        {etiket && <div className="text-sm text-gray-500 mb-3">{etiket}</div>}

        {/* Seçilen sıra */}
        <div className="min-h-[3rem] flex flex-wrap gap-2 p-3 rounded-xl bg-indigo-50/60 border border-dashed border-indigo-200 mb-4">
          {sira.length === 0 && (
            <span className="text-sm text-gray-400 self-center">Parçalara sırayla tıkla…</span>
          )}
          {sira.map((idx, pos) => (
            <span key={pos} className="px-3 py-1.5 rounded-lg bg-white border border-indigo-200 text-sm font-semibold text-indigo-700 shadow-sm">
              <span className="text-indigo-400 mr-1">{pos + 1}.</span>{ogeler[idx]}
            </span>
          ))}
        </div>

        {/* Parça havuzu */}
        <div className="flex flex-wrap gap-2">
          {ogeler.map((o, i) => (
            <button
              key={i}
              onClick={() => tikla(i)}
              disabled={secili(i) || !!sonuc}
              className={`px-3 py-2 rounded-lg border text-sm font-medium transition-all ${
                secili(i)
                  ? "border-gray-200 bg-gray-100 text-gray-300"
                  : "border-gray-200 bg-white text-gray-800 hover:bg-gray-50"
              }`}>
              {o}
            </button>
          ))}
        </div>

        {/* Eylemler */}
        {!sonuc && (
          <div className="flex items-center gap-2 mt-4">
            <button
              onClick={gonder}
              disabled={!tamam || bekliyor}
              className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold disabled:opacity-40 hover:bg-indigo-700 transition">
              Kontrol Et
            </button>
            <button onClick={geriAl} disabled={!sira.length}
              className="px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600 disabled:opacity-40">
              Geri Al
            </button>
            <button onClick={sifirla} disabled={!sira.length}
              className="px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600 disabled:opacity-40">
              Sıfırla
            </button>
          </div>
        )}

        {/* Sonuç */}
        {sonuc && (
          <div className={`mt-4 px-4 py-3 rounded-xl text-sm font-medium ${
            sonuc.dogru ? "bg-green-50 text-green-700 border border-green-200"
                        : "bg-red-50 text-red-700 border border-red-200"}`}>
            {sonuc.dogru ? "✓ Doğru sıraladın!" : "✗ Doğru sıra: "}
            {!sonuc.dogru && (sonuc.dogru_cevap || []).map((idx, p) => (
              <span key={p} className="font-semibold">{p > 0 ? " → " : ""}{ogeler[idx]}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
