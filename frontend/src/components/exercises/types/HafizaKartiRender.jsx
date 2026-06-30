import React, { useMemo, useState, useEffect, useRef } from "react";

/**
 * Hafıza Kartları render bileşeni (puanlama = serbest, istemci tarafı puanlar).
 * İçerik şeması: { ciftler: [{ sol: "kelime", sag: "anlam" }] }
 *
 * Her çift iki kapalı kart üretir (kelime + anlamı). Öğrenci iki kartı açar;
 * aynı çiftse açık kalır, değilse kapanır. Tüm kartlar eşleşince oyun biter ve
 * onCevap(true) ile motora bildirilir.
 *
 * Render sözleşmesi: { icerik, onCevap }
 */
export default function HafizaKartiRender({ icerik, onCevap }) {
  const ciftler = icerik?.ciftler || [];

  // Deste: her çift → 2 kart; deterministik karıştırma (içerik sabit kaldıkça aynı).
  const deste = useMemo(() => {
    const kartlar = [];
    ciftler.forEach((c, i) => {
      kartlar.push({ id: `${i}-s`, cift: i, metin: c.sol, tur: "sol" });
      kartlar.push({ id: `${i}-a`, cift: i, metin: c.sag, tur: "sag" });
    });
    const n = Math.max(1, kartlar.length);
    return kartlar
      .map((k, i) => ({ k, s: (i * 5 + 2) % n }))
      .sort((x, y) => x.s - y.s)
      .map((o) => o.k);
  }, [ciftler]);

  const [acik, setAcik] = useState([]);       // bu turda açık kart id'leri (max 2)
  const [eslesen, setEslesen] = useState([]); // eşleşmiş kart id'leri
  const [hamle, setHamle] = useState(0);
  const [bitti, setBitti] = useState(false);
  const kilit = useRef(false);

  useEffect(() => {
    setAcik([]); setEslesen([]); setHamle(0); setBitti(false);
    kilit.current = false;
  }, [deste]);

  // Tüm kartlar eşleşti mi?
  useEffect(() => {
    if (deste.length > 0 && eslesen.length === deste.length && !bitti) {
      setBitti(true);
      onCevap(true);
    }
  }, [eslesen, deste, bitti, onCevap]);

  const tikla = (kart) => {
    if (kilit.current || bitti) return;
    if (acik.includes(kart.id) || eslesen.includes(kart.id)) return;
    const yeni = [...acik, kart.id];
    setAcik(yeni);
    if (yeni.length === 2) {
      setHamle((h) => h + 1);
      const [a, b] = yeni.map((id) => deste.find((k) => k.id === id));
      if (a.cift === b.cift) {
        setEslesen((e) => [...e, a.id, b.id]);
        setAcik([]);
      } else {
        kilit.current = true;
        setTimeout(() => { setAcik([]); kilit.current = false; }, 900);
      }
    }
  };

  const gorunur = (kart) => acik.includes(kart.id) || eslesen.includes(kart.id);
  const eslesti = (kart) => eslesen.includes(kart.id);

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-gray-500">Eşleşen kelime-anlam çiftlerini bul:</span>
          <span className="text-xs text-gray-400">Hamle: {hamle}</span>
        </div>

        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {deste.map((kart) => (
            <button
              key={kart.id}
              onClick={() => tikla(kart)}
              disabled={gorunur(kart) || bitti}
              className={`h-20 rounded-xl border text-xs sm:text-sm font-medium p-2 flex items-center justify-center text-center transition-all ${
                eslesti(kart)
                  ? "border-green-300 bg-green-50 text-green-700"
                  : gorunur(kart)
                    ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                    : "border-gray-200 bg-gradient-to-br from-indigo-500 to-purple-500 text-white"
              }`}>
              {gorunur(kart) ? kart.metin : "❓"}
            </button>
          ))}
        </div>

        {bitti && (
          <div className="mt-4 px-4 py-3 rounded-xl text-sm font-medium bg-green-50 text-green-700 border border-green-200">
            🎉 Tüm kartları eşleştirdin! ({hamle} hamle)
          </div>
        )}
      </div>
    </div>
  );
}
