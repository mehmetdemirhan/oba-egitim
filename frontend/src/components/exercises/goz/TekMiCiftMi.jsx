// Tek mi? Çift mi? — bir rakam gridinde ÇİFT sayıların tümünü bul ve işaretle.
// Hızlı sayısal ayırt etme, tarama ve dikkat becerisini geliştirir.
import React, { useEffect, useMemo, useState } from "react";
import { EgzersizDuzen, Slider, Skor, dogruSes, yanlisSes, useEgzersizOturum } from "./ortak";

function gridUret(adet) {
  return Array.from({ length: adet }, () => Math.floor(Math.random() * 90) + 10);
}

export default function TekMiCiftMi({ onTamamla }) {
  const [boyut, setBoyut] = useState(6);   // NxN
  const [sure, setSure] = useState(60);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });
  const [tur, setTur] = useState(0);
  const [isaretli, setIsaretli] = useState(new Set());
  const [yanlisFlash, setYanlisFlash] = useState(null);
  const [skor, setSkor] = useState(0);

  const sayilar = useMemo(() => gridUret(boyut * boyut), [boyut, tur]);
  const ciftSayisi = useMemo(() => sayilar.filter((n) => n % 2 === 0).length, [sayilar]);

  useEffect(() => { setIsaretli(new Set()); }, [tur, boyut]);
  useEffect(() => { if (!calisiyor) { setSkor(0); setTur(0); setIsaretli(new Set()); } }, [calisiyor]);

  const tikla = (i, n) => {
    if (!calisiyor || isaretli.has(i)) return;
    if (n % 2 === 0) {
      const yeni = new Set(isaretli); yeni.add(i); setIsaretli(yeni);
      setSkor((s) => s + 1); dogruSes();
      if (yeni.size >= ciftSayisi) setTimeout(() => setTur((t) => t + 1), 600);
    } else {
      setYanlisFlash(i); yanlisSes();
      setTimeout(() => setYanlisFlash(null), 350);
    }
  };

  return (
    <EgzersizDuzen calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur} koyu={false}
      aciklama="Gözünüzü satır satır gezdirerek çift sayıları hızlıca seçin; tek sayılara dokunmayın."
      ayarlar={<>
        <Slider etiket="Grid Boyutu" deger={boyut} min={4} max={8} onChange={setBoyut} />
        <Slider etiket="Süre" deger={sure} min={20} max={120} step={10} birim="sn" onChange={setSure} />
      </>}>
      <div className="h-full overflow-auto p-4 flex flex-col items-center">
        {!calisiyor ? (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm text-center px-6">
            ▶ Başlat'a basın. Griddeki tüm <strong className="mx-1">ÇİFT</strong> sayıları bulup tıklayın.
          </div>
        ) : (
          <>
            <div className="text-sm text-gray-500 mb-3">Tüm <strong>çift</strong> sayıları işaretleyin — {isaretli.size}/{ciftSayisi}</div>
            <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${boyut}, minmax(0, 1fr))`, maxWidth: 460 }}>
              {sayilar.map((n, i) => {
                const ok = isaretli.has(i);
                const kotu = yanlisFlash === i;
                return (
                  <button key={i} onClick={() => tikla(i, n)}
                    className={`w-12 h-12 sm:w-14 sm:h-14 rounded-lg text-base sm:text-lg font-bold transition-all
                      ${ok ? "bg-green-500 text-white" : kotu ? "bg-red-400 text-white" : "bg-gray-50 text-gray-700 hover:bg-indigo-100 active:scale-95"}`}>
                    {n}
                  </button>
                );
              })}
            </div>
            <Skor deger={skor} />
          </>
        )}
      </div>
    </EgzersizDuzen>
  );
}
