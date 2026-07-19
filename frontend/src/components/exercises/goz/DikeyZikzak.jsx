// Dikey Zikzak Göz Egzersizi — top yukarıdan aşağıya zikzak çizerek iner.
// Sütunlar arası dikey tarama ve satır geçiş becerisini geliştirir.
import React, { useState } from "react";
import { CanvasSahne, EgzersizDuzen, Slider, SesToggle, useEgzersizOturum, useMetronom } from "./ortak";

export default function DikeyZikzak({ onTamamla }) {
  const [bpm, setBpm] = useState(100);      // tempo (metronom + görsel hız)
  const [metronom, setMetronom] = useState(false);
  const [kolon, setKolon] = useState(4);   // dikey zikzak sütun sayısı
  const [sure, setSure] = useState(30);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });
  useMetronom(bpm, metronom, calisiyor);   // BPM'e göre metronom vuruşu

  const ciz = (ctx, W, H, t) => {
    const marj = 24;
    const n = kolon; // dönüş noktası sayısı
    // Aşağı inen ÇAPRAZ zikzak: her dönüşte sol/sağ kenar alternatif.
    // Eski hâlde dikey iniş + yatay geçiş = iki 90° keskin köşe vardı; artık
    // her dönüş TEK, çapraz (~45°) köşe → küçük yaş grubu için daha yumuşak takip.
    const pts = [];
    for (let r = 0; r < n; r++) {
      const y = marj + (r / (n - 1)) * (H - 2 * marj);
      const x = r % 2 === 0 ? marj : W - marj;
      pts.push([x, y]);
    }

    // İz
    ctx.beginPath();
    ctx.strokeStyle = "rgba(139,92,246,0.18)";
    ctx.lineWidth = 2;
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < n; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.stroke();

    // Hareketli top — çapraz segmentler boyunca sürekli
    const toplam = n - 1;
    const dongu = (t * 0.12) % 1;
    const seg = Math.min(Math.floor(dongu * toplam), toplam - 1);
    const segIci = dongu * toplam - seg;
    const [x0, y0] = pts[seg];
    const [x1, y1] = pts[seg + 1];
    const x = x0 + (x1 - x0) * segIci;
    const y = y0 + (y1 - y0) * segIci;

    ctx.beginPath(); ctx.arc(x, y, 15, 0, Math.PI * 2);
    const g = ctx.createRadialGradient(x, y, 0, x, y, 15);
    g.addColorStop(0, "#c4b5fd"); g.addColorStop(1, "#7c3aed");
    ctx.fillStyle = g; ctx.fill();
  };

  return (
    <EgzersizDuzen calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}
      aciklama="Topu çapraz zikzak yol boyunca gözlerinizle takip edin. Başınızı sabit tutun."
      ayarlar={<>
        <Slider etiket="Hız (tempo)" deger={bpm} min={40} max={160} step={5} birim=" bpm" onChange={setBpm} />
        <Slider etiket="Dönüş" deger={kolon} min={2} max={6} onChange={setKolon} />
        <Slider etiket="Süre" deger={sure} min={10} max={120} step={10} birim="sn" onChange={setSure} />
        <SesToggle acik={metronom} onChange={setMetronom} />
      </>}>
      <CanvasSahne ciz={ciz} calisiyor={calisiyor} hiz={bpm / 60} />
    </EgzersizDuzen>
  );
}
