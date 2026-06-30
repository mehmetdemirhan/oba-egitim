import React, { useState, useEffect } from "react";

/**
 * Kelime Bulmaca render bileşeni (puanlama = serbest, istemci tarafı puanlar).
 * İçerik şeması: { kelimeler: [{ ipucu: "...", cevap: "kuş" }] }
 *
 * Her ipucu için öğrenci cevabı yazar; "Kontrol Et" ile hepsi Türkçe küçük harf
 * normalizasyonuyla karşılaştırılır. Tümü doğruysa onCevap(true), aksi halde
 * onCevap(false) ile motora tek seferde bildirilir (doğru sayısı ekranda gösterilir).
 *
 * Render sözleşmesi: { icerik, onCevap }
 */
const trKucuk = (s) => (s || "").toLocaleLowerCase("tr").trim().replace(/\s+/g, " ");

export default function BulmacaRender({ icerik, onCevap }) {
  const kelimeler = icerik?.kelimeler || [];
  const [cevaplar, setCevaplar] = useState({});
  const [sonuc, setSonuc] = useState(null); // {dogru, dogruSayisi, toplam, durum:[bool]}

  useEffect(() => {
    setCevaplar({});
    setSonuc(null);
  }, [icerik]);

  const yaz = (i, v) => {
    if (sonuc) return;
    setCevaplar((c) => ({ ...c, [i]: v }));
  };

  const dolu = kelimeler.length > 0 &&
    kelimeler.every((_, i) => (cevaplar[i] || "").trim().length > 0);

  const gonder = async () => {
    if (!dolu || sonuc) return;
    const durum = kelimeler.map((k, i) => trKucuk(cevaplar[i]) === trKucuk(k.cevap));
    const dogruSayisi = durum.filter(Boolean).length;
    const hepsi = dogruSayisi === kelimeler.length;
    const r = await onCevap(hepsi);
    setSonuc({ dogru: hepsi, dogruSayisi, toplam: kelimeler.length, durum, ...(r || {}) });
  };

  const renk = (i) => {
    if (!sonuc) return "border-gray-200 focus:border-indigo-400";
    return sonuc.durum[i] ? "border-green-400 bg-green-50" : "border-red-400 bg-red-50";
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm space-y-3">
        <div className="text-sm text-gray-500">İpuçlarına göre doğru kelimeleri yaz:</div>
        {kelimeler.map((k, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="w-6 h-6 flex-shrink-0 flex items-center justify-center rounded-lg bg-gray-100 text-gray-600 text-xs font-bold">
              {i + 1}
            </span>
            <span className="flex-1 text-sm text-gray-700">{k.ipucu}</span>
            <input
              value={cevaplar[i] || ""}
              onChange={(e) => yaz(i, e.target.value)}
              disabled={!!sonuc}
              placeholder="cevap"
              className={`w-32 px-3 py-1.5 rounded-lg border text-sm outline-none transition ${renk(i)}`} />
          </div>
        ))}

        {!sonuc && (
          <button onClick={gonder} disabled={!dolu}
            className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold disabled:opacity-40 hover:bg-indigo-700 transition">
            Kontrol Et
          </button>
        )}

        {sonuc && (
          <div className={`px-4 py-3 rounded-xl text-sm font-medium ${
            sonuc.dogru ? "bg-green-50 text-green-700 border border-green-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"}`}>
            {sonuc.dogru ? "🎉 Hepsini doğru bildin!" : `${sonuc.dogruSayisi}/${sonuc.toplam} doğru.`}
            {!sonuc.dogru && (
              <div className="mt-2 text-xs text-gray-600">
                Doğru cevaplar: {kelimeler.map((k) => k.cevap).join(", ")}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
