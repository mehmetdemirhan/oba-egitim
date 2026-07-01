// KAREL: Kare Görme Alanı — harf gridi, ortada odak noktası. Her turda
// çevredeki işaretli harf gösterilir; kullanıcı gözünü merkeze sabitleyip
// işaretli harfin merkezdekiyle AYNI mı FARKLI mı olduğunu yanıtlar.
// Çevresel görüş ve görme alanı genişletme.
import React, { useEffect, useMemo, useState } from "react";
import { KontrolBar, Slider, Ipucu, Skor, TR_HARFLER, dogruSes, yanlisSes, useEgzersizOturum } from "./ortak";

export default function KarelKareGorme({ onTamamla }) {
  const [boyut, setBoyut] = useState(9);   // grid NxN (tek sayı)
  const [sure, setSure] = useState(60);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });
  const [skor, setSkor] = useState(0);
  const [tur, setTur] = useState(0);
  const [geri, setGeri] = useState(null);

  const merkez = Math.floor((boyut * boyut) / 2);

  // Her turda grid + işaretli hücre + doğru cevabı üret
  const soru = useMemo(() => {
    const n = boyut * boyut;
    const harfler = Array.from({ length: n }, () => TR_HARFLER[Math.floor(Math.random() * TR_HARFLER.length)]);
    let isaret = Math.floor(Math.random() * n);
    while (isaret === Math.floor(n / 2)) isaret = Math.floor(Math.random() * n);
    // %50 aynı olacak şekilde ayarla
    if (Math.random() < 0.5) harfler[isaret] = harfler[Math.floor(n / 2)];
    const ayni = harfler[isaret] === harfler[Math.floor(n / 2)];
    return { harfler, isaret, ayni };
  }, [boyut, tur]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (!calisiyor) { setSkor(0); setTur(0); setGeri(null); } }, [calisiyor]);

  const cevapla = (secim) => {
    if (!calisiyor || geri) return;
    const dogru = secim === soru.ayni;
    if (dogru) { setSkor((s) => s + 1); dogruSes(); } else { yanlisSes(); }
    setGeri(dogru ? "dogru" : "yanlis");
    setTimeout(() => { setGeri(null); setTur((t) => t + 1); }, 600);
  };

  return (
    <div>
      <KontrolBar calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}>
        <Slider etiket="Grid Boyutu" deger={boyut} min={5} max={11} step={2} birim="" onChange={setBoyut} />
        <Slider etiket="Süre" deger={sure} min={20} max={120} step={10} birim="sn" onChange={setSure} />
      </KontrolBar>
      <div className="rounded-2xl border border-gray-200 bg-white p-4 flex flex-col items-center" style={{ minHeight: 420 }}>
        {!calisiyor ? (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm text-center px-6">
            ▶ Başlat'a basın. Gözünüzü <strong className="mx-1">merkez kırmızı noktaya</strong> sabitleyin,
            çevredeki mavi işaretli harfin merkezdekiyle aynı olup olmadığını yanıtlayın.
          </div>
        ) : (
          <>
            <div className="grid gap-0.5 mb-4"
              style={{ gridTemplateColumns: `repeat(${boyut}, minmax(0, 1fr))`, maxWidth: 480 }}>
              {soru.harfler.map((h, i) => {
                const isMerkez = i === merkez;
                const isIsaret = i === soru.isaret;
                return (
                  <div key={i}
                    className={`aspect-square flex items-center justify-center rounded text-xs sm:text-sm font-mono font-semibold
                      ${isMerkez ? "text-red-600" : isIsaret ? "bg-blue-100 text-blue-700 ring-2 ring-blue-500" : "text-gray-500"}`}>
                    {isMerkez ? <span className="relative">{h}<span className="absolute -inset-2 rounded-full border-2 border-red-500" /></span> : h}
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => cevapla(true)}
                className="px-6 py-2 rounded-xl bg-green-500 text-white text-sm font-bold hover:bg-green-600">✓ Aynı</button>
              <button onClick={() => cevapla(false)}
                className="px-6 py-2 rounded-xl bg-orange-500 text-white text-sm font-bold hover:bg-orange-600">✗ Farklı</button>
            </div>
            {geri && <div className={`mt-2 text-lg font-bold ${geri === "dogru" ? "text-green-500" : "text-red-500"}`}>{geri === "dogru" ? "✅ Doğru" : "❌ Yanlış"}</div>}
            <Skor deger={skor} />
          </>
        )}
      </div>
      <Ipucu>Gözünüzü merkeze sabitleyip yalnızca çevresel görüşle işaretli harfi tanımaya çalışın — başınızı çevirmeyin.</Ipucu>
    </div>
  );
}
