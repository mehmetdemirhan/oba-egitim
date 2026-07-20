// Göz Egzersizleri: Kolonlar — metin kolonlara bölünür, vurgu kutusu her
// kolonda yukarıdan aşağıya iner. Kolonlar arası ritmik göz hareketiyle
// okuma temposunu ve satır atlama becerisini geliştirir.
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  EgzersizDuzen, Slider, rastgele, useEgzersizOturum, useKelimeHavuzu,
  useSkorKayit, RekorRozeti, useZorluk, ZorlukKontrol,
} from "./ortak";

const TIP = "kolonlar";
const SATIR = 10; // her kolonda satır sayısı

export default function Kolonlar({ onTamamla }) {
  const [kolon, setKolon] = useState(3);
  const [tempo, setTempo] = useState(120); // hücre/dakika
  const [sure, setSure] = useState(40);
  const [aktif, setAktif] = useState(0); // aktif hücre sırası (kolon-öncelikli)
  const havuz = useKelimeHavuzu();
  const { rekor, sonSonuc, kaydet } = useSkorKayit(TIP);
  const { zorluk, taban, setTaban, min, max } = useZorluk(TIP);

  // Pasif izleme egzersizi: "doğruluk" yok → skor tamamlanan (taranan) hücre
  // sayısı × hız × zorluk üzerinden hesaplanır (accuracy=1). Ne kadar çok/hızlı
  // hücre tararsan o kadar yüksek.
  const tarananRef = useRef(0);
  const bitince = () => {
    kaydet({ dogru: tarananRef.current, yanlis: 0, sure_sn: sure, zorluk });
    onTamamla?.();
  };
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla: bitince });

  // Zorluk arttıkça daha uzun kelimeler (taranması güç). 1..5 → min uzunluk 3..7.
  const minUzunluk = 2 + zorluk;
  const tablo = useMemo(() => {
    const uygun = havuz.filter((k) => k.length >= minUzunluk);
    const kaynak = uygun.length >= 8 ? uygun : havuz;
    return Array.from({ length: kolon * SATIR }, () => rastgele(kaynak));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kolon, havuz, minUzunluk]);
  const toplam = kolon * SATIR;

  useEffect(() => {
    if (!calisiyor) { setAktif(0); tarananRef.current = 0; return; }
    const ms = Math.max(120, 60000 / tempo);
    const id = setInterval(() => { tarananRef.current += 1; setAktif((a) => (a + 1) % toplam); }, ms);
    return () => clearInterval(id);
  }, [calisiyor, tempo, toplam]);

  const aktifKolon = Math.floor(aktif / SATIR);
  const aktifSatir = aktif % SATIR;

  return (
    <EgzersizDuzen calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur} koyu={false}
      aciklama="Vurgulanan kelimeye odaklanın; kolon bitince gözünüzü hızla bir sonraki kolonun başına atlatın. Zorluk arttıkça kelimeler uzar."
      ayarlar={<>
        <ZorlukKontrol taban={taban} setTaban={setTaban} min={min} max={max} efektif={zorluk} />
        <Slider etiket="Kolon" deger={kolon} min={2} max={4} onChange={setKolon} />
        <Slider etiket="Tempo (hücre/dk)" deger={tempo} min={40} max={300} step={10} onChange={setTempo} />
        <Slider etiket="Süre" deger={sure} min={10} max={120} step={10} birim="sn" onChange={setSure} />
      </>}>
      <div className="h-full overflow-auto p-4">
        {!calisiyor && (
          <div className="mb-2 flex flex-col items-center">
            <ZorlukKontrol taban={taban} setTaban={setTaban} min={min} max={max} efektif={zorluk} />
            <RekorRozeti rekor={rekor} sonSonuc={sonSonuc} />
          </div>
        )}
        <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${kolon}, 1fr)` }}>
          {Array.from({ length: kolon }).map((_, c) => (
            <div key={c} className="flex flex-col gap-1">
              {Array.from({ length: SATIR }).map((_, r) => {
                const secili = calisiyor && c === aktifKolon && r === aktifSatir;
                return (
                  <div key={r}
                    className={`text-center py-1.5 rounded-lg text-sm md:text-base transition-colors ${secili ? "bg-indigo-600 text-white font-bold scale-105" : "text-gray-700"}`}>
                    {tablo[c * SATIR + r]}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </EgzersizDuzen>
  );
}
