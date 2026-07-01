// Metin Arama — uzun bir metin içinde hedef kelimenin tüm geçtiği yerleri bul.
// Kullanıcı metni hızlıca tarayıp hedef kelimenin her kopyasına tıklar.
// Hızlı tarama (skimming) ve seçici dikkat becerisini geliştirir.
import React, { useEffect, useMemo, useState } from "react";
import { KontrolBar, Slider, Ipucu, Skor, TR_KELIMELER, rastgele, dogruSes, yanlisSes, useEgzersizOturum } from "./ortak";

function metinUret(kelimeSayi, hedef, gecis) {
  const dizi = Array.from({ length: kelimeSayi }, () => rastgele(TR_KELIMELER));
  // Hedef kelimeyi rastgele konumlara serpiştir
  const konumlar = new Set();
  while (konumlar.size < gecis) konumlar.add(Math.floor(Math.random() * kelimeSayi));
  konumlar.forEach((k) => (dizi[k] = hedef));
  return dizi;
}

export default function MetinArama({ onTamamla }) {
  const [uzunluk, setUzunluk] = useState(140); // kelime sayısı
  const [sure, setSure] = useState(90);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });
  const [tur, setTur] = useState(0);
  const [bulunan, setBulunan] = useState(new Set());
  const [skor, setSkor] = useState(0);

  const { hedef, dizi, toplam } = useMemo(() => {
    const h = rastgele(TR_KELIMELER);
    const g = 3 + Math.floor(Math.random() * 4); // 3-6 kopya
    const d = metinUret(uzunluk, h, g);
    const t = d.filter((w) => w === h).length;
    return { hedef: h, dizi: d, toplam: t };
  }, [uzunluk, tur]);

  useEffect(() => { setBulunan(new Set()); }, [tur, uzunluk]);
  useEffect(() => { if (!calisiyor) { setSkor(0); setTur(0); setBulunan(new Set()); } }, [calisiyor]);

  const tikla = (i, kelime) => {
    if (!calisiyor || bulunan.has(i)) return;
    if (kelime === hedef) {
      const yeni = new Set(bulunan); yeni.add(i); setBulunan(yeni);
      setSkor((s) => s + 1); dogruSes();
      if (yeni.size >= toplam) setTimeout(() => setTur((t) => t + 1), 800);
    } else {
      yanlisSes();
    }
  };

  return (
    <div>
      <KontrolBar calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}>
        <Slider etiket="Metin Uzunluğu" deger={uzunluk} min={60} max={260} step={20} onChange={setUzunluk} />
        <Slider etiket="Süre" deger={sure} min={30} max={180} step={10} birim="sn" onChange={setSure} />
      </KontrolBar>
      <div className="rounded-2xl border border-gray-200 bg-white p-4" style={{ minHeight: 420 }}>
        {!calisiyor ? (
          <div className="h-[380px] flex items-center justify-center text-gray-400 text-sm text-center px-6">
            ▶ Başlat'a basın. Metinde belirtilen hedef kelimenin tüm geçtiği yerleri bulup tıklayın.
          </div>
        ) : (
          <>
            <div className="text-center mb-3">
              <span className="text-sm text-gray-500">Hedef kelime: </span>
              <span className="text-xl font-black text-sky-600 bg-sky-50 px-3 py-1 rounded-lg">{hedef}</span>
              <span className="ml-3 text-sm text-green-600 font-bold">{bulunan.size}/{toplam}</span>
            </div>
            <div className="leading-8 text-gray-700 text-sm sm:text-base">
              {dizi.map((w, i) => (
                <React.Fragment key={i}>
                  <span onClick={() => tikla(i, w)}
                    className={`cursor-pointer px-0.5 rounded ${bulunan.has(i) ? "bg-green-500 text-white" : "hover:bg-sky-100"}`}>
                    {w}
                  </span>{" "}
                </React.Fragment>
              ))}
            </div>
            <Skor deger={skor} />
          </>
        )}
      </div>
      <Ipucu>Metni satır satır hızlıca tarayın; hedef kelimeyi gördüğünüzde üstüne tıklayın.</Ipucu>
    </div>
  );
}
