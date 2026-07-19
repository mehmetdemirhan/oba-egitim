// Blok Okuma — metin, N kelimelik bloklar hâlinde ekranın ortasında tek tek ve
// belirlenen tempoda (blok/dk) gösterilir. Öğrenci her bloğa tek bakışta (göz
// sıçraması) odaklanır; geriye dönüş olmadan ileri okur. Tüm bloklar bitince puan.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { EgzersizDuzen, useEgzersizOturum, Slider } from "../goz/ortak";
import { useOkumaMetni, kelimelereBol, gruplara, MetinSecici } from "./ortak";

export default function BlokOkuma({ onTamamla }) {
  const { metin, liste, sec, yukleniyor, hata, yenile } = useOkumaMetni(40);
  const [blokBoyu, setBlokBoyu] = useState(3);   // blok başına kelime
  const [hiz, setHiz] = useState(120);           // blok / dakika
  const [index, setIndex] = useState(0);
  const [bitti, setBitti] = useState(false);
  const timerRef = useRef(null);

  const kelimeler = useMemo(() => kelimelereBol(metin?.icerik), [metin]);
  const bloklar = useMemo(() => gruplara(kelimeler, blokBoyu), [kelimeler, blokBoyu]);

  const { calisiyor, baslat: oturumBaslat, durdur: oturumDurdur, bitir } = useEgzersizOturum({ sure: 0, onTamamla });

  const temizle = () => { if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; } };

  const baslat = () => {
    if (!bloklar.length) return;
    setIndex(0); setBitti(false);
    oturumBaslat();
    temizle();
    const ms = Math.max(200, 60000 / hiz);
    timerRef.current = setInterval(() => {
      setIndex((i) => {
        if (i + 1 >= bloklar.length) { temizle(); setBitti(true); oturumDurdur(); bitir(); return i; }
        return i + 1;
      });
    }, ms);
  };

  const durdur = () => { temizle(); oturumDurdur(); };
  useEffect(() => () => temizle(), []);
  // Ayar değişince akan gösterimi durdur (tutarlılık).
  useEffect(() => { temizle(); setIndex(0); setBitti(false); if (calisiyor) oturumDurdur(); /* eslint-disable-next-line */ }, [blokBoyu, hiz, metin]);

  const ayarlar = (
    <>
      <Slider etiket="Blok Başına Kelime" deger={blokBoyu} min={1} max={5} onChange={setBlokBoyu} />
      <Slider etiket="Hız (blok/dakika)" deger={hiz} min={40} max={400} step={10} birim=" blok/dk" onChange={setHiz} />
      <div>
        <label className="block text-xs text-gray-500 mb-1">Metin seç (onaylı havuz)</label>
        <MetinSecici liste={liste} metin={metin} sec={sec} yenile={yenile} />
      </div>
    </>
  );
  const aciklama = "Metin, blok blok (birkaç kelime) ekranın ortasında hızla gösterilir. Her bloğa tek bakışta odaklanın, geri dönmeden ileri okuyun. Blok boyutunu ve hızı ayarlardan değiştirebilirsiniz.";

  const dakikaTahmini = kelimeler.length && hiz ? Math.round((bloklar.length / hiz) * 60) : 0;

  return (
    <EgzersizDuzen calisiyor={calisiyor} baslat={baslat} durdur={durdur} ayarlar={ayarlar} aciklama={aciklama} koyu>
      <div className="h-full flex flex-col items-center justify-center text-center px-6 relative">
        {yukleniyor ? (
          <div className="text-gray-400">Metin yükleniyor…</div>
        ) : hata ? (
          <div className="text-red-400 max-w-md">{hata}</div>
        ) : (
          <>
            <div className="absolute top-3 left-4 text-xs text-gray-500 truncate max-w-[70%]">📖 {metin?.baslik} • {metin?.kelime_sayisi || kelimeler.length} kelime</div>
            <div className="absolute top-3 right-4 text-xs text-gray-500">Blok {Math.min(index + 1, bloklar.length)} / {bloklar.length}{dakikaTahmini ? ` • ~${dakikaTahmini}s` : ""}</div>
            <div className="text-white font-bold leading-snug" style={{ fontSize: "clamp(1.8rem, 5vw, 3.4rem)" }}>
              {(bloklar[index] || []).join(" ") || (calisiyor ? "" : "Başlamak için ▶ Başlat")}
            </div>
            {/* İlerleme çizgisi */}
            <div className="absolute bottom-5 left-0 right-0 px-8">
              <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-500 transition-all" style={{ width: bloklar.length ? `${((index + 1) / bloklar.length) * 100}%` : "0%" }} />
              </div>
            </div>
            {bitti && <div className="absolute bottom-10 left-0 right-0 text-green-400 font-bold text-sm">✓ Metin bitti — puan işlendi.</div>}
          </>
        )}
      </div>
    </EgzersizDuzen>
  );
}
