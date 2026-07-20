// Metin Arama — uzun bir metin içinde hedef kelimenin tüm geçtiği yerleri bul.
// Kullanıcı metni hızlıca tarayıp hedef kelimenin her kopyasına tıklar.
// Hızlı tarama (skimming) ve seçici dikkat becerisini geliştirir.
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  EgzersizDuzen, Slider, Skor, rastgele, dogruSes, yanlisSes, useEgzersizOturum, useKelimeHavuzu,
  useSkorKayit, RekorRozeti, useZorluk, ZorlukKontrol,
} from "./ortak";

const TIP = "metin_arama";

// Hedefe BENZER çeldiriciler: aynı uzunluk ya da aynı ilk iki harf (göz yanıltıcı).
function benzerKelimeler(hedef, havuz, adet) {
  const benzer = havuz.filter((w) => w !== hedef && (w.length === hedef.length || (w[0] === hedef[0] && w[1] === hedef[1])));
  const kaynak = benzer.length >= 3 ? benzer : havuz;
  return Array.from({ length: Math.max(0, adet) }, () => rastgele(kaynak));
}

// Zorluk arttıkça metnin daha büyük kısmı hedefe benzer çeldiricilerden oluşur
// (z1≈%20 → z5≈%60), böylece hedefi ayırt etmek zorlaşır.
function metinUret(kelimeSayi, hedef, gecis, havuz, zorluk) {
  const dizi = Array.from({ length: kelimeSayi }, () => rastgele(havuz));
  const benzerAdet = Math.round(kelimeSayi * (0.1 + 0.1 * zorluk));
  benzerKelimeler(hedef, havuz, benzerAdet).forEach((bw) => { dizi[Math.floor(Math.random() * kelimeSayi)] = bw; });
  const konumlar = new Set();
  while (konumlar.size < gecis) konumlar.add(Math.floor(Math.random() * kelimeSayi));
  konumlar.forEach((k) => (dizi[k] = hedef));
  return dizi;
}

export default function MetinArama({ onTamamla }) {
  const [uzunluk, setUzunluk] = useState(140); // kelime sayısı
  const [sure, setSure] = useState(90);
  const [tur, setTur] = useState(0);
  const [bulunan, setBulunan] = useState(new Set());
  const [skor, setSkor] = useState(0);
  const havuz = useKelimeHavuzu();
  const { rekor, sonSonuc, kaydet } = useSkorKayit(TIP);
  const { zorluk, taban, setTaban, min, max, bildirSonuc, sifirla } = useZorluk(TIP);

  const dogruRef = useRef(0), yanlisRef = useRef(0), zorlukRef = useRef(zorluk);
  useEffect(() => { zorlukRef.current = zorluk; }, [zorluk]);
  const bitince = () => {
    kaydet({ dogru: dogruRef.current, yanlis: yanlisRef.current, sure_sn: sure, zorluk: zorlukRef.current });
    onTamamla?.();
  };
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla: bitince });

  const { hedef, dizi, toplam } = useMemo(() => {
    // Zorlukta hedef daha uzun seçilir (taraması güç). z1..5 → min uzunluk 3..7.
    const uygun = havuz.filter((k) => k.length >= 2 + zorluk);
    const h = rastgele(uygun.length >= 3 ? uygun : havuz);
    const g = 3 + Math.floor(Math.random() * 4); // 3-6 kopya
    const d = metinUret(uzunluk, h, g, havuz, zorluk);
    const t = d.filter((w) => w === h).length;
    return { hedef: h, dizi: d, toplam: t };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uzunluk, tur, havuz]);

  useEffect(() => { setBulunan(new Set()); }, [tur, uzunluk]);
  useEffect(() => {
    if (!calisiyor) { setSkor(0); setTur(0); setBulunan(new Set()); dogruRef.current = 0; yanlisRef.current = 0; sifirla(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calisiyor]);

  const tikla = (i, kelime) => {
    if (!calisiyor || bulunan.has(i)) return;
    if (kelime === hedef) {
      const yeni = new Set(bulunan); yeni.add(i); setBulunan(yeni);
      setSkor((s) => s + 1); dogruRef.current += 1; bildirSonuc(true); dogruSes();
      if (yeni.size >= toplam) setTimeout(() => setTur((t) => t + 1), 800);
    } else {
      yanlisRef.current += 1; bildirSonuc(false); yanlisSes();
    }
  };

  return (
    <EgzersizDuzen calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur} koyu={false}
      aciklama="Metni satır satır hızlıca tarayın; hedef kelimeyi gördüğünüzde üstüne tıklayın. Zorluk arttıkça metinde hedefe benzeyen çeldiriciler çoğalır."
      ayarlar={<>
        <ZorlukKontrol taban={taban} setTaban={setTaban} min={min} max={max} efektif={zorluk} />
        <Slider etiket="Metin Uzunluğu" deger={uzunluk} min={60} max={260} step={20} onChange={setUzunluk} />
        <Slider etiket="Süre" deger={sure} min={30} max={180} step={10} birim="sn" onChange={setSure} />
      </>}>
      <div className="h-full overflow-auto p-4">
        {!calisiyor ? (
          <div className="h-[380px] flex flex-col items-center justify-center text-gray-400 text-sm text-center px-6">
            <div>▶ Başlat'a basın. Metinde belirtilen hedef kelimenin tüm geçtiği yerleri bulup tıklayın.</div>
            <div className="mt-3"><ZorlukKontrol taban={taban} setTaban={setTaban} min={min} max={max} efektif={zorluk} /></div>
            <RekorRozeti rekor={rekor} sonSonuc={sonSonuc} />
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
    </EgzersizDuzen>
  );
}
