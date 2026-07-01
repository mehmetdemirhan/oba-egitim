// Dikey Zikzak Göz Egzersizi — top yukarıdan aşağıya zikzak çizerek iner.
// Sütunlar arası dikey tarama ve satır geçiş becerisini geliştirir.
import React, { useState } from "react";
import { CanvasSahne, KontrolBar, Slider, Sahne, Ipucu, useEgzersizOturum } from "./ortak";

export default function DikeyZikzak({ onTamamla }) {
  const [hiz, setHiz] = useState(1.5);
  const [kolon, setKolon] = useState(4);   // dikey zikzak sütun sayısı
  const [sure, setSure] = useState(30);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });

  const ciz = (ctx, W, H, t) => {
    const marj = 24;
    const cols = kolon;
    // Zigzag izi: her sütun tepeden dibe/dipten tepeye, aralarında yatay geçiş
    ctx.beginPath();
    ctx.strokeStyle = "rgba(139,92,246,0.18)";
    ctx.lineWidth = 2;
    for (let c = 0; c < cols; c++) {
      const x = marj + (c / (cols - 1)) * (W - 2 * marj);
      const ust = c % 2 === 0 ? marj : H - marj;
      const alt = c % 2 === 0 ? H - marj : marj;
      ctx.moveTo(x, ust); ctx.lineTo(x, alt);
      if (c < cols - 1) {
        const nx = marj + ((c + 1) / (cols - 1)) * (W - 2 * marj);
        ctx.lineTo(nx, alt);
      }
    }
    ctx.stroke();

    // Hareketli top
    const toplam = cols; // segment sayısı (dikey inişler)
    const dongu = (t * 0.12) % 1;
    const seg = Math.floor(dongu * toplam);
    const segIci = (dongu * toplam) % 1;
    const x = marj + (seg / (cols - 1)) * (W - 2 * marj);
    const yBas = seg % 2 === 0 ? marj : H - marj;
    const yBit = seg % 2 === 0 ? H - marj : marj;
    const y = yBas + (yBit - yBas) * segIci;

    ctx.beginPath(); ctx.arc(x, y, 15, 0, Math.PI * 2);
    const g = ctx.createRadialGradient(x, y, 0, x, y, 15);
    g.addColorStop(0, "#c4b5fd"); g.addColorStop(1, "#7c3aed");
    ctx.fillStyle = g; ctx.fill();
  };

  return (
    <div>
      <KontrolBar calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}>
        <Slider etiket="Hız" deger={hiz} min={0.5} max={4} step={0.5} birim="x" onChange={setHiz} />
        <Slider etiket="Sütun" deger={kolon} min={2} max={6} onChange={setKolon} />
        <Slider etiket="Süre" deger={sure} min={10} max={120} step={10} birim="sn" onChange={setSure} />
      </KontrolBar>
      <Sahne>
        <CanvasSahne ciz={ciz} calisiyor={calisiyor} hiz={hiz} />
      </Sahne>
      <Ipucu>Topu dikey zikzak yol boyunca gözlerinizle takip edin. Başınızı sabit tutun.</Ipucu>
    </div>
  );
}
