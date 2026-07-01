// Dairesel Göz Egzersizi — nokta yumuşak dairesel yörüngede döner.
// Göz kaslarının döngüsel koordinasyonunu ve yumuşak takibi geliştirir.
import React, { useState } from "react";
import { CanvasSahne, KontrolBar, Slider, Sahne, Ipucu, useEgzersizOturum } from "./ortak";

export default function DairesalGoz({ onTamamla }) {
  const [hiz, setHiz] = useState(1.5);
  const [cap, setCap] = useState(70);       // yörünge çapı (%)
  const [yon, setYon] = useState(1);        // 1: saat yönü, -1: ters
  const [sure, setSure] = useState(30);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });

  const ciz = (ctx, W, H, t) => {
    const cx = W / 2, cy = H / 2;
    const R = (cap / 100) * (Math.min(W, H) / 2 - 20);
    // Yörünge halkası
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(45,212,191,0.22)"; ctx.lineWidth = 3; ctx.stroke();
    // Merkez referans
    ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(148,163,184,0.5)"; ctx.fill();
    // Dönen nokta
    const a = t * yon;
    const x = cx + Math.cos(a) * R, y = cy + Math.sin(a) * R;
    ctx.beginPath(); ctx.arc(x, y, 16, 0, Math.PI * 2);
    const g = ctx.createRadialGradient(x, y, 0, x, y, 16);
    g.addColorStop(0, "#5eead4"); g.addColorStop(1, "#0d9488");
    ctx.fillStyle = g; ctx.fill();
  };

  return (
    <div>
      <KontrolBar calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}>
        <Slider etiket="Hız" deger={hiz} min={0.5} max={4} step={0.5} birim="x" onChange={setHiz} />
        <Slider etiket="Çap" deger={cap} min={30} max={95} step={5} birim="%" onChange={setCap} />
        <Slider etiket="Süre" deger={sure} min={10} max={120} step={10} birim="sn" onChange={setSure} />
        <div>
          <label className="text-xs text-gray-500 block mb-1">Yön</label>
          <button onClick={() => setYon((y) => -y)}
            className="px-3 py-1 rounded-lg border border-gray-200 text-sm font-medium hover:bg-gray-50">
            {yon === 1 ? "↻ Saat yönü" : "↺ Ters yön"}
          </button>
        </div>
      </KontrolBar>
      <Sahne>
        <CanvasSahne ciz={ciz} calisiyor={calisiyor} hiz={hiz} />
      </Sahne>
      <Ipucu>Noktayı dairesel yörünge boyunca yumuşakça takip edin; başınızı oynatmayın.</Ipucu>
    </div>
  );
}
