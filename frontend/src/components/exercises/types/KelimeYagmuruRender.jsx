import React, { useMemo, useState, useEffect, useRef } from "react";

/**
 * Kelime Yağmuru render bileşeni (puanlama = serbest, istemci tarafı puanlar).
 * İçerik şeması: { hedef: "...", dogrular: [...], yanlislar: [...] }
 *
 * Süre dolmadan hedefe uyan ("doğru") kelimeleri yakalamaya çalışılır. Doğru
 * kelimeye dokunmak +1, yanlışa dokunmak ceza. Süre bitince ya da tüm doğrular
 * yakalanınca oyun biter; başarı (tümü ya da %60+) onCevap(basari) ile bildirilir.
 *
 * Render sözleşmesi: { icerik, onCevap }
 */
const SURE = 25;

export default function KelimeYagmuruRender({ icerik, onCevap }) {
  const hedef = icerik?.hedef || "Doğru kelimeleri yakala";
  const dogrular = icerik?.dogrular || [];
  const yanlislar = icerik?.yanlislar || [];

  // Karışık kelime taşları (deterministik) — her biri doğru/yanlış işaretli.
  const taslar = useMemo(() => {
    const arr = [
      ...dogrular.map((k) => ({ k, dogruMu: true })),
      ...yanlislar.map((k) => ({ k, dogruMu: false })),
    ].map((o, i) => ({ ...o, id: i }));
    const n = Math.max(1, arr.length);
    return arr
      .map((o, i) => ({ o, s: (i * 7 + 5) % n }))
      .sort((x, y) => x.s - y.s)
      .map((x) => x.o);
  }, [dogrular, yanlislar]);

  const hedefSayi = dogrular.length;
  const [sure, setSure] = useState(SURE);
  const [yakalanan, setYakalanan] = useState([]); // doğru tıklanan id'ler
  const [yanlisTik, setYanlisTik] = useState([]); // yanlış tıklanan id'ler
  const [bitti, setBitti] = useState(false);
  const [sonuc, setSonuc] = useState(null);
  const bildirildi = useRef(false);

  const bitir = (yakalananSay, yanlisSay) => {
    if (bildirildi.current) return;
    bildirildi.current = true;
    const basari = hedefSayi > 0 &&
      (yakalananSay === hedefSayi ||
        (yakalananSay >= Math.ceil(hedefSayi * 0.6) && yanlisSay <= 2));
    setBitti(true);
    onCevap(basari);
    setSonuc({ dogru: basari, yakalanan: yakalananSay, hedef: hedefSayi });
  };

  // Geri sayım
  useEffect(() => {
    if (bitti) return;
    if (sure <= 0) { bitir(yakalanan.length, yanlisTik.length); return; }
    const t = setTimeout(() => setSure((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [sure, bitti]); // eslint-disable-line react-hooks/exhaustive-deps

  const tikla = (tas) => {
    if (bitti || yakalanan.includes(tas.id) || yanlisTik.includes(tas.id)) return;
    if (tas.dogruMu) {
      const yeni = [...yakalanan, tas.id];
      setYakalanan(yeni);
      if (yeni.length === hedefSayi) bitir(yeni.length, yanlisTik.length);
    } else {
      setYanlisTik((y) => [...y, tas.id]);
    }
  };

  const renk = (tas) => {
    if (yakalanan.includes(tas.id)) return "border-green-400 bg-green-50 text-green-700";
    if (yanlisTik.includes(tas.id)) return "border-red-300 bg-red-50 text-red-400 line-through";
    return "border-gray-200 bg-white text-gray-800 hover:bg-indigo-50 hover:border-indigo-200";
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-indigo-700">🌧️ {hedef}</span>
          <span className={`text-sm font-bold px-2 py-0.5 rounded-lg ${sure <= 5 ? "bg-red-100 text-red-600" : "bg-gray-100 text-gray-600"}`}>
            ⏱ {sure}s
          </span>
        </div>

        <div className="text-xs text-gray-400 mb-3">
          Yakalanan: {yakalanan.length}/{hedefSayi}
        </div>

        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {taslar.map((tas) => (
            <button
              key={tas.id}
              onClick={() => tikla(tas)}
              disabled={bitti || yakalanan.includes(tas.id) || yanlisTik.includes(tas.id)}
              className={`py-3 px-2 rounded-xl border text-sm font-medium transition-all animate-bounce ${renk(tas)}`}
              style={{ animationDuration: `${1.6 + (tas.id % 5) * 0.25}s` }}>
              {tas.k}
            </button>
          ))}
        </div>

        {sonuc && (
          <div className={`mt-4 px-4 py-3 rounded-xl text-sm font-medium ${
            sonuc.dogru ? "bg-green-50 text-green-700 border border-green-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"}`}>
            {sonuc.dogru
              ? `🎉 Harika! ${sonuc.yakalanan}/${sonuc.hedef} doğru kelimeyi yakaladın.`
              : `Süre doldu — ${sonuc.yakalanan}/${sonuc.hedef} yakaladın. Tekrar dene!`}
          </div>
        )}
      </div>
    </div>
  );
}
