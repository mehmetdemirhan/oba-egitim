// Gruplama — metin, N kelimelik anlam gruplarına ayrılmış olarak (aralarında ayraç)
// gösterilir; hareketli vurgu grup grup, belirlenen tempoda (grup/dk) ilerler.
// Amaç: kelime kelime değil, grup grup (anlam öbeği) okuma alışkanlığı. Bitince puan.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { EgzersizDuzen, useEgzersizOturum, Slider } from "../goz/ortak";
import { useOkumaMetni, kelimelereBol, gruplara } from "./ortak";

export default function Gruplama({ onTamamla }) {
  const { metin, yukleniyor, hata, yenile } = useOkumaMetni(40);
  const [grupBoyu, setGrupBoyu] = useState(3);   // grup başına kelime
  const [hiz, setHiz] = useState(90);            // grup / dakika
  const [aktif, setAktif] = useState(-1);
  const [bitti, setBitti] = useState(false);
  const timerRef = useRef(null);
  const aktifRef = useRef(null);

  const kelimeler = useMemo(() => kelimelereBol(metin?.icerik), [metin]);
  const gruplar = useMemo(() => gruplara(kelimeler, grupBoyu), [kelimeler, grupBoyu]);
  const { calisiyor, baslat: oturumBaslat, durdur: oturumDurdur, bitir } = useEgzersizOturum({ sure: 0, onTamamla });

  const temizle = () => { if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; } };

  const baslat = () => {
    if (!gruplar.length) return;
    setAktif(0); setBitti(false);
    oturumBaslat();
    temizle();
    const ms = Math.max(300, 60000 / hiz);
    timerRef.current = setInterval(() => {
      setAktif((i) => {
        if (i + 1 >= gruplar.length) { temizle(); setBitti(true); oturumDurdur(); bitir(); return i; }
        return i + 1;
      });
    }, ms);
  };

  const durdur = () => { temizle(); oturumDurdur(); };
  useEffect(() => () => temizle(), []);
  useEffect(() => { temizle(); setAktif(-1); setBitti(false); if (calisiyor) oturumDurdur(); /* eslint-disable-next-line */ }, [grupBoyu, hiz, metin]);
  useEffect(() => { if (aktifRef.current) aktifRef.current.scrollIntoView({ block: "center", behavior: "smooth" }); }, [aktif]);

  const ayarlar = (
    <>
      <Slider etiket="Grup Başına Kelime" deger={grupBoyu} min={2} max={5} onChange={setGrupBoyu} />
      <Slider etiket="Hız (grup/dakika)" deger={hiz} min={30} max={240} step={10} birim=" grup/dk" onChange={setHiz} />
      <button onClick={yenile} className="w-full py-1.5 rounded-lg text-sm font-semibold border border-gray-200 bg-white text-gray-600 hover:bg-gray-50">🔄 Yeni Metin</button>
    </>
  );
  const aciklama = "Metin anlam gruplarına (öbeklerine) ayrılmış gösterilir; vurgu grup grup ilerler. Gözünüzü tek tek kelimelere değil, gruba bütün olarak odaklayın. Grup boyutu ve hızı ayarlanabilir.";

  return (
    <EgzersizDuzen calisiyor={calisiyor} baslat={baslat} durdur={durdur} ayarlar={ayarlar} aciklama={aciklama} koyu={false}>
      <div className="h-full flex flex-col p-4">
        {yukleniyor ? (
          <div className="flex-1 flex items-center justify-center text-gray-400">Metin yükleniyor…</div>
        ) : hata ? (
          <div className="flex-1 flex items-center justify-center text-center text-red-500 px-4">{hata}</div>
        ) : (
          <>
            <div className="flex items-center justify-between text-xs text-gray-500 mb-2 flex-wrap gap-2">
              <span className="font-semibold text-gray-700 truncate">📖 {metin?.baslik}</span>
              <span>{aktif >= 0 ? Math.min(aktif + 1, gruplar.length) : 0} / {gruplar.length} grup</span>
            </div>
            <div className="flex-1 overflow-y-auto rounded-xl bg-white border border-gray-200 px-5 py-4 flex flex-wrap gap-x-1 gap-y-2 content-start"
              style={{ fontSize: "1.4rem", lineHeight: 1.9 }}>
              {gruplar.map((g, i) => (
                <span key={i} ref={i === aktif ? aktifRef : null}
                  className={`inline-flex items-center rounded-lg px-2 py-0.5 border transition-colors duration-100 ${
                    i === aktif ? "bg-indigo-500 text-white border-indigo-500"
                    : i < aktif ? "text-gray-300 border-transparent" : "text-gray-800 border-gray-200 bg-gray-50/60"}`}>
                  {g.join(" ")}
                </span>
              ))}
            </div>
            {bitti && <div className="mt-2 text-center text-sm font-bold text-green-600">✓ Metin bitti — puan işlendi.</div>}
          </>
        )}
      </div>
    </EgzersizDuzen>
  );
}
