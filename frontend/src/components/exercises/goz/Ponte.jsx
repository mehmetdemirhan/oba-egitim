// PONTE: Dairesel/Sinüs Göz Egzersizi — dikey sinüs dalgası boyunca aşağı
// yukarı hareket eden nokta. Yumuşak takip (pursuit) becerisini geliştirir.
import React, { useState } from "react";
import { CanvasSahne, KontrolBar, Slider, Sahne, Ipucu, useEgzersizOturum } from "./ortak";

export default function Ponte({ onTamamla }) {
  const [hiz, setHiz] = useState(1.5);
  const [genlik, setGenlik] = useState(40); // % genişlik
  const [sure, setSure] = useState(30);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });

  const ciz = (ctx, W, H, t) => {
    const marj = 40;
    const amp = (genlik / 100) * (W / 2 - marj);
    const cx = W / 2;
    const dalgaSayi = 3; // dikey boyunca kaç sinüs dalgası
    // Sinüs yolunu çiz (dikey: y tepeden aşağı, x = sin)
    ctx.beginPath();
    ctx.strokeStyle = "rgba(96,165,250,0.25)";
    ctx.lineWidth = 3;
    for (let y = marj; y <= H - marj; y += 4) {
      const fy = (y - marj) / (H - 2 * marj);
      const x = cx + Math.sin(fy * Math.PI * 2 * dalgaSayi) * amp;
      y === marj ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
    // Hareketli nokta (git-gel)
    const ilerleme = (Math.sin(t * 0.5) * 0.5 + 0.5); // 0..1..0
    const y = marj + ilerleme * (H - 2 * marj);
    const fy = (y - marj) / (H - 2 * marj);
    const x = cx + Math.sin(fy * Math.PI * 2 * dalgaSayi) * amp;
    ctx.beginPath(); ctx.arc(x, y, 16, 0, Math.PI * 2);
    const g = ctx.createRadialGradient(x, y, 0, x, y, 16);
    g.addColorStop(0, "#67e8f9"); g.addColorStop(1, "#0891b2");
    ctx.fillStyle = g; ctx.fill();
  };

  return (
    <div>
      <KontrolBar calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}>
        <Slider etiket="Hız" deger={hiz} min={0.5} max={4} step={0.5} birim="x" onChange={setHiz} />
        <Slider etiket="Genişlik" deger={genlik} min={20} max={80} step={5} birim="%" onChange={setGenlik} />
        <Slider etiket="Süre" deger={sure} min={10} max={120} step={10} birim="sn" onChange={setSure} />
      </KontrolBar>
      <Sahne>
        <CanvasSahne ciz={ciz} calisiyor={calisiyor} hiz={hiz} />
      </Sahne>
      <Ipucu>Noktayı sinüs dalgası boyunca yumuşakça takip edin; başınızı sabit tutun.</Ipucu>
    </div>
  );
}
