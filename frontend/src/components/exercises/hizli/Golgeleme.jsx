// Gölgeleme — metnin tamamı görünür; hareketli bir vurgu (gölge) kelime kelime
// belirlenen tempoda (kelime/dk) metnin üzerinde ilerler. Öğrenci vurguya yetişerek
// tempoyu bozmadan okur; okunan kelimeler soluklaşır. Metin bitince puan.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { EgzersizDuzen, useEgzersizOturum, Slider } from "../goz/ortak";
import { useOkumaMetni, kelimelereBol, MetinSecici } from "./ortak";

export default function Golgeleme({ onTamamla }) {
  const { metin, liste, sec, yukleniyor, hata, yenile } = useOkumaMetni(40);
  const [wpm, setWpm] = useState(220);           // kelime / dakika
  const [aktif, setAktif] = useState(-1);
  const [bitti, setBitti] = useState(false);
  const timerRef = useRef(null);
  const aktifRef = useRef(null);

  const kelimeler = useMemo(() => kelimelereBol(metin?.icerik), [metin]);
  const { calisiyor, baslat: oturumBaslat, durdur: oturumDurdur, bitir } = useEgzersizOturum({ sure: 0, onTamamla });

  const temizle = () => { if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; } };

  const baslat = () => {
    if (!kelimeler.length) return;
    setAktif(0); setBitti(false);
    oturumBaslat();
    temizle();
    const ms = Math.max(120, 60000 / wpm);
    timerRef.current = setInterval(() => {
      setAktif((i) => {
        if (i + 1 >= kelimeler.length) { temizle(); setBitti(true); oturumDurdur(); bitir(); return i; }
        return i + 1;
      });
    }, ms);
  };

  const durdur = () => { temizle(); oturumDurdur(); };
  useEffect(() => () => temizle(), []);
  useEffect(() => { temizle(); setAktif(-1); setBitti(false); if (calisiyor) oturumDurdur(); /* eslint-disable-next-line */ }, [wpm, metin]);

  // Aktif kelimeyi görünür tut (uzun metinde otomatik kaydır).
  useEffect(() => { if (aktifRef.current) aktifRef.current.scrollIntoView({ block: "center", behavior: "smooth" }); }, [aktif]);

  const ayarlar = (
    <>
      <Slider etiket="Hız (kelime/dakika)" deger={wpm} min={80} max={700} step={10} birim=" k/dk" onChange={setWpm} />
      <div>
        <label className="block text-xs text-gray-500 mb-1">Metin seç (onaylı havuz)</label>
        <MetinSecici liste={liste} metin={metin} sec={sec} yenile={yenile} />
      </div>
    </>
  );
  const aciklama = "Metnin tamamı görünür; hareketli vurgu kelime kelime ilerler. Vurguya yetişerek, tempoyu bozmadan ve geri dönmeden okuyun. Hızı (kelime/dakika) ayarlardan değiştirin.";

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
              <span>{wpm} k/dk • {aktif >= 0 ? Math.min(aktif + 1, kelimeler.length) : 0} / {kelimeler.length}</span>
            </div>
            <div className="flex-1 overflow-y-auto rounded-xl bg-white border border-gray-200 px-5 py-4"
              style={{ fontSize: "1.5rem", lineHeight: 2.1 }}>
              {kelimeler.map((w, i) => (
                <span key={i} ref={i === aktif ? aktifRef : null}
                  className={`transition-colors duration-100 ${
                    i === aktif ? "bg-indigo-500 text-white rounded px-0.5"
                    : i < aktif ? "text-gray-300" : "text-gray-800"}`}>{w}{" "}</span>
              ))}
            </div>
            {bitti && <div className="mt-2 text-center text-sm font-bold text-green-600">✓ Metin bitti — puan işlendi.</div>}
          </>
        )}
      </div>
    </EgzersizDuzen>
  );
}
