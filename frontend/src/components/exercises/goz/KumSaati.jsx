// Kum Saati Egzersizi (Elina) — X desenli iki üçgen (kum saati); kollar
// boyunca çevresel harfler dizilir. Kullanıcı merkeze bakıp gözünü oynatmadan
// uçlardaki harfleri okur. Çevresel görüşü ve görme alanını genişletir.
import React, { useRef, useState } from "react";
import { CanvasSahne, KontrolBar, Slider, Sahne, Ipucu, TR_HARFLER, useEgzersizOturum } from "./ortak";

export default function KumSaati({ onTamamla }) {
  const [seviye, setSeviye] = useState(4);  // her kolda harf sayısı
  const [tempo, setTempo] = useState(1.2);  // harf yenileme hızı
  const [sure, setSure] = useState(40);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });

  const donguRef = useRef(-1);
  const harflerRef = useRef([]);

  const ciz = (ctx, W, H, t) => {
    const cx = W / 2, cy = H / 2;
    const kolUzun = Math.min(W, H) / 2 - 30;
    const acilim = 0.55; // X kollarının yatay açıklığı

    // Harfleri periyodik yenile
    const dongu = Math.floor(t * 0.25 * tempo);
    if (dongu !== donguRef.current) {
      donguRef.current = dongu;
      harflerRef.current = Array.from({ length: 4 * seviye }, () =>
        TR_HARFLER[Math.floor(Math.random() * TR_HARFLER.length)]);
    }
    const harfler = harflerRef.current;

    // Kum saati çerçevesi (X): 4 kol
    const uc = [
      [cx - acilim * kolUzun, cy - kolUzun], // sol üst
      [cx + acilim * kolUzun, cy - kolUzun], // sağ üst
      [cx + acilim * kolUzun, cy + kolUzun], // sağ alt
      [cx - acilim * kolUzun, cy + kolUzun], // sol alt
    ];
    ctx.strokeStyle = "rgba(148,163,184,0.4)"; ctx.lineWidth = 2;
    uc.forEach(([x, y]) => { ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(x, y); ctx.stroke(); });

    // Kollar boyunca harfler
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    uc.forEach(([ux, uy], k) => {
      for (let i = 0; i < seviye; i++) {
        const f = (i + 1) / seviye;
        const x = cx + (ux - cx) * f, y = cy + (uy - cy) * f;
        const boyut = 16 + f * 12;
        ctx.font = `bold ${boyut}px sans-serif`;
        ctx.fillStyle = `rgba(30,64,175,${0.55 + f * 0.4})`;
        ctx.fillText(harfler[k * seviye + i] || "", x, y);
      }
    });

    // Merkez odak
    ctx.beginPath(); ctx.arc(cx, cy, 8, 0, Math.PI * 2);
    ctx.fillStyle = "#ef4444"; ctx.fill();
  };

  return (
    <div>
      <KontrolBar calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}>
        <Slider etiket="Seviye (harf/kol)" deger={seviye} min={2} max={7} onChange={setSeviye} />
        <Slider etiket="Yenileme Hızı" deger={tempo} min={0.5} max={3} step={0.5} birim="x" onChange={setTempo} />
        <Slider etiket="Süre" deger={sure} min={10} max={120} step={10} birim="sn" onChange={setSure} />
      </KontrolBar>
      <Sahne koyu={false}>
        <CanvasSahne ciz={ciz} calisiyor={calisiyor} hiz={1} />
      </Sahne>
      <Ipucu>Merkezdeki kırmızı noktaya sabit bakın; başınızı oynatmadan kum saati kollarındaki harfleri okumaya çalışın.</Ipucu>
    </div>
  );
}
