// Büyüyen Şekiller serisi — Altıgen / Daire / Dikdörtgen / Elips / Kare.
// Şekil merkezden dışa doğru halkalar hâlinde büyür; kullanıcı gözünü
// oynatmadan tüm kenarları görmeye çalışır → görme alanı genişletme.
import React, { useState } from "react";
import { CanvasSahne, KontrolBar, Slider, Sahne, Ipucu, useEgzersizOturum } from "./ortak";

const SEKILLER = {
  altigen:    { ad: "Büyüyen Altıgen",    renk: "56,189,248" },  // sky
  daire:      { ad: "Büyüyen Daire",      renk: "16,185,129" },  // emerald
  dikdortgen: { ad: "Büyüyen Dikdörtgen", renk: "249,115,22" },  // orange
  elips:      { ad: "Büyüyen Elips",      renk: "168,85,247" },  // purple
  kare:       { ad: "Büyüyen Kare",       renk: "236,72,153" },  // pink
};

// Bir şekil kenarını (cx,cy) merkezli, r ölçekli çizer.
function sekilCiz(ctx, tip, cx, cy, r) {
  ctx.beginPath();
  if (tip === "daire") {
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
  } else if (tip === "elips") {
    ctx.ellipse(cx, cy, r * 1.35, r * 0.75, 0, 0, Math.PI * 2);
  } else if (tip === "kare") {
    ctx.rect(cx - r, cy - r, r * 2, r * 2);
  } else if (tip === "dikdortgen") {
    ctx.rect(cx - r * 1.4, cy - r * 0.7, r * 2.8, r * 1.4);
  } else if (tip === "altigen") {
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i - Math.PI / 2;
      const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath();
  }
  ctx.stroke();
}

export default function BuyuyenSekil({ tip = "daire", onTamamla }) {
  const meta = SEKILLER[tip] || SEKILLER.daire;
  const [hiz, setHiz] = useState(1.5);
  const [halka, setHalka] = useState(4);
  const [sure, setSure] = useState(30);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });

  const ciz = (ctx, W, H, t) => {
    const cx = W / 2, cy = H / 2;
    const rMax = Math.min(W, H) / 2 - 12;
    ctx.lineWidth = 3;
    for (let i = 0; i < halka; i++) {
      const p = ((t * 0.12 + i / halka) % 1);
      const r = 10 + p * (rMax - 10);
      const alpha = Math.max(0, 1 - p);
      ctx.strokeStyle = `rgba(${meta.renk},${alpha})`;
      sekilCiz(ctx, tip, cx, cy, r);
    }
    // Merkez odak noktası
    ctx.beginPath();
    ctx.arc(cx, cy, 7, 0, Math.PI * 2);
    ctx.fillStyle = "#ef4444";
    ctx.fill();
  };

  return (
    <div>
      <KontrolBar calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}>
        <Slider etiket="Hız" deger={hiz} min={0.5} max={4} step={0.5} birim="x" onChange={setHiz} />
        <Slider etiket="Halka Sayısı" deger={halka} min={2} max={8} onChange={setHalka} />
        <Slider etiket="Süre" deger={sure} min={10} max={120} step={10} birim="sn" onChange={setSure} />
      </KontrolBar>
      <Sahne>
        <CanvasSahne ciz={ciz} calisiyor={calisiyor} hiz={hiz} />
      </Sahne>
      <Ipucu>Merkezdeki kırmızı noktaya sabit bakın; gözünüzü oynatmadan büyüyen {meta.ad.toLowerCase().replace("büyüyen ", "")}in tüm kenarlarını görmeye çalışın.</Ipucu>
    </div>
  );
}
