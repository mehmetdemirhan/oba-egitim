// Benzer Kelimeler — 4 kutuda ikişer kelime bulunur. Üç kutuda kelime çifti
// birebir aynıdır; bir kutuda çift birbirinden (tek harf) farklıdır.
// Kullanıcı FARKLI olan kutuyu bulur. Hızlı ayırt etme ve tarama becerisi.
import React, { useEffect, useMemo, useState } from "react";
import { EgzersizDuzen, Slider, Skor, TR_HARFLER, rastgele, dogruSes, yanlisSes, useEgzersizOturum, useKelimeHavuzu } from "./ortak";

// Bir kelimeyi tek harf değiştirerek "benzer ama farklı" üret.
function benzerYap(kelime) {
  if (kelime.length < 2) return kelime + "n";
  const idx = Math.floor(Math.random() * kelime.length);
  let yeni;
  do { yeni = TR_HARFLER[Math.floor(Math.random() * TR_HARFLER.length)].toLocaleLowerCase("tr"); }
  while (yeni === kelime[idx]);
  return kelime.slice(0, idx) + yeni + kelime.slice(idx + 1);
}

export default function BenzerKelimeler({ onTamamla }) {
  const [sure, setSure] = useState(60);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });
  const [skor, setSkor] = useState(0);
  const [tur, setTur] = useState(0);
  const [geri, setGeri] = useState(null);
  const havuz = useKelimeHavuzu();

  const soru = useMemo(() => {
    const farkliIdx = Math.floor(Math.random() * 4);
    const kutular = Array.from({ length: 4 }, (_, i) => {
      const k = rastgele(havuz);
      return i === farkliIdx ? [k, benzerYap(k)] : [k, k];
    });
    return { kutular, farkliIdx };
  }, [tur, havuz]);

  useEffect(() => { if (!calisiyor) { setSkor(0); setTur(0); setGeri(null); } }, [calisiyor]);

  const sec = (i) => {
    if (!calisiyor || geri) return;
    const dogru = i === soru.farkliIdx;
    if (dogru) { setSkor((s) => s + 1); dogruSes(); } else { yanlisSes(); }
    setGeri({ dogru, secilen: i });
    setTimeout(() => { setGeri(null); setTur((t) => t + 1); }, 700);
  };

  return (
    <EgzersizDuzen calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur} koyu={false}
      aciklama="Kutulardaki kelime çiftlerini hızlıca karşılaştırın; harfleri farklı olan çifti seçin."
      ayarlar={<>
        <Slider etiket="Süre" deger={sure} min={20} max={120} step={10} birim="sn" onChange={setSure} />
      </>}>
      <div className="h-full overflow-auto p-4 flex flex-col items-center justify-center">
        {!calisiyor ? (
          <div className="text-gray-400 text-sm text-center px-6">▶ Başlat'a basın. İki kelimesi <strong>farklı</strong> olan kutuyu bulun.</div>
        ) : (
          <>
            <div className="text-sm text-gray-500 mb-4">İki kelimesi <strong>aynı olmayan</strong> kutuya tıklayın</div>
            <div className="grid grid-cols-2 gap-4 w-full max-w-md">
              {soru.kutular.map((k, i) => {
                const isSecilen = geri && geri.secilen === i;
                const stil = isSecilen
                  ? (geri.dogru ? "border-green-500 bg-green-50" : "border-red-500 bg-red-50")
                  : (geri && i === soru.farkliIdx ? "border-green-400 bg-green-50" : "border-gray-200 hover:border-indigo-400 hover:bg-indigo-50");
                return (
                  <button key={i} onClick={() => sec(i)}
                    className={`rounded-xl border-2 p-4 transition-all active:scale-95 ${stil}`}>
                    <div className="text-lg font-bold text-gray-800">{k[0]}</div>
                    <div className="text-lg font-bold text-gray-800">{k[1]}</div>
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
