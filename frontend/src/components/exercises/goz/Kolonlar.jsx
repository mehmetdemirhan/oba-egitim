// Göz Egzersizleri: Kolonlar — metin kolonlara bölünür, vurgu kutusu her
// kolonda yukarıdan aşağıya iner. Kolonlar arası ritmik göz hareketiyle
// okuma temposunu ve satır atlama becerisini geliştirir.
import React, { useEffect, useMemo, useState } from "react";
import { EgzersizDuzen, Slider, rastgele, TR_KELIMELER, useEgzersizOturum } from "./ortak";

const SATIR = 10; // her kolonda satır sayısı

export default function Kolonlar({ onTamamla }) {
  const [kolon, setKolon] = useState(3);
  const [tempo, setTempo] = useState(120); // hücre/dakika
  const [sure, setSure] = useState(40);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });
  const [aktif, setAktif] = useState(0); // aktif hücre sırası (kolon-öncelikli)

  // Kelime tablosu (kolon değişince yenile)
  const tablo = useMemo(
    () => Array.from({ length: kolon * SATIR }, () => rastgele(TR_KELIMELER)),
    [kolon]
  );
  const toplam = kolon * SATIR;

  useEffect(() => {
    if (!calisiyor) { setAktif(0); return; }
    const ms = Math.max(120, 60000 / tempo);
    const id = setInterval(() => setAktif((a) => (a + 1) % toplam), ms);
    return () => clearInterval(id);
  }, [calisiyor, tempo, toplam]);

  // Kolon-öncelikli sıra: önce 0. kolon yukarıdan aşağı, sonra 1. kolon...
  const aktifKolon = Math.floor(aktif / SATIR);
  const aktifSatir = aktif % SATIR;

  return (
    <EgzersizDuzen calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur} koyu={false}
      aciklama="Vurgulanan kelimeye odaklanın; kolon bitince gözünüzü hızla bir sonraki kolonun başına atlatın."
      ayarlar={<>
        <Slider etiket="Kolon" deger={kolon} min={2} max={4} onChange={setKolon} />
        <Slider etiket="Tempo (hücre/dk)" deger={tempo} min={40} max={300} step={10} onChange={setTempo} />
        <Slider etiket="Süre" deger={sure} min={10} max={120} step={10} birim="sn" onChange={setSure} />
      </>}>
      <div className="h-full overflow-auto p-4">
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
