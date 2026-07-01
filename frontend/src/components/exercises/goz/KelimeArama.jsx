// Kelime Arama — harf gridinde gizli kelimeleri bul. Kelimeler yatay veya
// dikey yerleştirilir; kullanıcı kelimenin ilk ve son harfine tıklayarak seçer.
// Görsel tarama hızını ve dikkati geliştirir.
import React, { useEffect, useMemo, useState } from "react";
import { KontrolBar, Slider, Ipucu, Skor, TR_HARFLER, dogruSes, yanlisSes, useEgzersizOturum } from "./ortak";

const HAVUZ = ["KİTAP", "OKUMA", "KALEM", "DEFTER", "HARF", "SAYFA", "METİN", "ANLAM", "MASA", "OKUL", "ÖĞRENCI", "SATIR"];
const yon = [[0, 1], [1, 0]]; // yatay, dikey

function gridUret(N, kelimeSayi) {
  const g = Array.from({ length: N }, () => Array(N).fill(null));
  const secili = [...HAVUZ].filter((w) => w.length <= N).sort(() => Math.random() - 0.5).slice(0, kelimeSayi);
  const yerlesen = [];
  for (const kelime of secili) {
    let konuldu = false;
    for (let deneme = 0; deneme < 40 && !konuldu; deneme++) {
      const [dr, dc] = yon[Math.floor(Math.random() * yon.length)];
      const r0 = Math.floor(Math.random() * N), c0 = Math.floor(Math.random() * N);
      const rEnd = r0 + dr * (kelime.length - 1), cEnd = c0 + dc * (kelime.length - 1);
      if (rEnd >= N || cEnd >= N) continue;
      let uyar = true;
      for (let i = 0; i < kelime.length; i++) {
        const cur = g[r0 + dr * i][c0 + dc * i];
        if (cur && cur !== kelime[i]) { uyar = false; break; }
      }
      if (!uyar) continue;
      for (let i = 0; i < kelime.length; i++) g[r0 + dr * i][c0 + dc * i] = kelime[i];
      yerlesen.push(kelime);
      konuldu = true;
    }
  }
  for (let r = 0; r < N; r++) for (let c = 0; c < N; c++)
    if (!g[r][c]) g[r][c] = TR_HARFLER[Math.floor(Math.random() * TR_HARFLER.length)];
  return { g, kelimeler: yerlesen };
}

export default function KelimeArama({ onTamamla }) {
  const [boyut, setBoyut] = useState(9);
  const [sure, setSure] = useState(90);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });
  const [tur, setTur] = useState(0);
  const [bulunan, setBulunan] = useState([]);
  const [secim, setSecim] = useState(null); // ilk tıklanan {r,c}
  const [skor, setSkor] = useState(0);

  const { g, kelimeler } = useMemo(() => gridUret(boyut, Math.min(6, boyut - 2)), [boyut, tur]);
  const [bulunanHucre, setBulunanHucre] = useState(new Set());

  useEffect(() => { setBulunan([]); setSecim(null); setBulunanHucre(new Set()); }, [tur, boyut]);
  useEffect(() => { if (!calisiyor) { setSkor(0); setTur(0); } }, [calisiyor]);

  const hatCiz = (a, b) => {
    // Aynı satır/sütun mu?
    if (a.r !== b.r && a.c !== b.c) return null;
    const dr = Math.sign(b.r - a.r), dc = Math.sign(b.c - a.c);
    const uzun = Math.max(Math.abs(b.r - a.r), Math.abs(b.c - a.c)) + 1;
    const hucreler = [];
    let harf = "";
    for (let i = 0; i < uzun; i++) {
      const r = a.r + dr * i, c = a.c + dc * i;
      hucreler.push(r * boyut + c);
      harf += g[r][c];
    }
    return { harf, hucreler };
  };

  const tikla = (r, c) => {
    if (!calisiyor) return;
    if (!secim) { setSecim({ r, c }); return; }
    const hat = hatCiz(secim, { r, c });
    setSecim(null);
    if (!hat) return;
    const ters = hat.harf.split("").reverse().join("");
    const eslesen = kelimeler.find((k) => (k === hat.harf || k === ters) && !bulunan.includes(k));
    if (eslesen) {
      setBulunan((b) => [...b, eslesen]);
      setBulunanHucre((s) => { const n = new Set(s); hat.hucreler.forEach((h) => n.add(h)); return n; });
      setSkor((s) => s + 1);
      dogruSes();
      if (bulunan.length + 1 >= kelimeler.length) setTimeout(() => setTur((t) => t + 1), 700);
    } else {
      yanlisSes();
    }
  };

  return (
    <div>
      <KontrolBar calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}>
        <Slider etiket="Grid Boyutu" deger={boyut} min={7} max={12} onChange={setBoyut} />
        <Slider etiket="Süre" deger={sure} min={30} max={180} step={10} birim="sn" onChange={setSure} />
      </KontrolBar>
      <div className="rounded-2xl border border-gray-200 bg-white p-4" style={{ minHeight: 420 }}>
        {!calisiyor ? (
          <div className="h-[380px] flex items-center justify-center text-gray-400 text-sm text-center px-6">
            ▶ Başlat'a basın. Gizli kelimenin <strong className="mx-1">ilk ve son harfine</strong> tıklayarak seçin (yatay/dikey).
          </div>
        ) : (
          <div className="flex flex-col md:flex-row gap-4 items-start justify-center">
            <div className="grid gap-0.5 mx-auto"
              style={{ gridTemplateColumns: `repeat(${boyut}, minmax(0, 1fr))`, maxWidth: 460 }}>
              {g.map((satir, r) => satir.map((h, c) => {
                const idx = r * boyut + c;
                const isSecim = secim && secim.r === r && secim.c === c;
                const isBulundu = bulunanHucre.has(idx);
                return (
                  <button key={idx} onClick={() => tikla(r, c)}
                    className={`aspect-square flex items-center justify-center rounded text-xs sm:text-sm font-mono font-bold transition-colors
                      ${isBulundu ? "bg-green-500 text-white" : isSecim ? "bg-indigo-500 text-white" : "bg-gray-50 text-gray-700 hover:bg-indigo-100"}`}>
                    {h}
                  </button>
                );
              }))}
            </div>
            <div className="min-w-[120px]">
              <div className="text-xs font-semibold text-gray-500 mb-2">Aranan kelimeler</div>
              <div className="flex flex-wrap gap-1.5">
                {kelimeler.map((k) => (
                  <span key={k} className={`text-xs px-2 py-1 rounded-full ${bulunan.includes(k) ? "bg-green-100 text-green-700 line-through" : "bg-gray-100 text-gray-600"}`}>{k}</span>
                ))}
              </div>
              <Skor deger={skor} />
            </div>
          </div>
        )}
      </div>
      <Ipucu>Kelimeleri gözünüzle tarayın; bulduğunuzda ilk ve son harfine tıklayın.</Ipucu>
    </div>
  );
}
