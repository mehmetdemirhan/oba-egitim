// 13 Nokta Göz Egzersizi — yıldız deseninde 13 nokta arasında göz sıçraması
// (saccade). İşaretçi noktadan noktaya zıplar; her sıçramada metronom sesi
// (opsiyonel). Göz kaslarını ve sıçrama hızını güçlendirir.
import React, { useRef, useState } from "react";
import { CanvasSahne, KontrolBar, Slider, SesToggle, Sahne, Ipucu, bipCal, useEgzersizOturum } from "./ortak";

// Yıldız/tarama deseni oluşturan sıçrama sırası (normalize -1..1).
const NOKTALAR = [
  [0, -0.85], [0, 0.85], [-0.85, -0.55], [0.85, 0.55],
  [-0.85, 0.55], [0.85, -0.55], [-0.85, 0], [0.85, 0],
  [0, 0], [-0.5, -0.5], [0.5, 0.5], [0.5, -0.5], [-0.5, 0.5],
];

export default function Nokta13({ onTamamla }) {
  const [tempo, setTempo] = useState(90);   // sıçrama/dakika (bpm)
  const [sure, setSure] = useState(30);
  const [ses, setSes] = useState(true);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });
  const sonIdxRef = useRef(-1);

  const ciz = (ctx, W, H, t) => {
    const cx = W / 2, cy = H / 2;
    const R = Math.min(W, H) / 2 - 30;
    const konum = (p) => [cx + p[0] * R, cy + p[1] * R];
    // İşaretçi indeksi: tempo → saniyede sıçrama sayısı. t ≈ 0.02*hiz artışlı
    // olduğundan gerçek zamanı Date yerine kare sayacından türetiriz.
    const gecen = t / 0.02; // ~kare
    const sicramaBasi = Math.max(1, Math.round(3600 / tempo)); // kare/sıçrama (~60fps)
    const idx = Math.floor(gecen / sicramaBasi) % NOKTALAR.length;

    if (idx !== sonIdxRef.current) {
      if (ses && sonIdxRef.current !== -1) bipCal(880, 0.06, 0.14);
      sonIdxRef.current = idx;
    }

    // Sabit noktalar
    NOKTALAR.forEach((p, i) => {
      const [x, y] = konum(p);
      ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2);
      ctx.fillStyle = i === idx ? "rgba(0,0,0,0)" : "rgba(148,163,184,0.35)";
      ctx.fill();
    });
    // Aktif işaretçi
    const [ax, ay] = konum(NOKTALAR[idx]);
    ctx.beginPath(); ctx.arc(ax, ay, 18, 0, Math.PI * 2);
    const g = ctx.createRadialGradient(ax, ay, 0, ax, ay, 18);
    g.addColorStop(0, "#fde047"); g.addColorStop(1, "#f59e0b");
    ctx.fillStyle = g; ctx.fill();
    ctx.strokeStyle = "#b45309"; ctx.lineWidth = 2; ctx.stroke();
  };

  return (
    <div>
      <KontrolBar calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}>
        <Slider etiket="Tempo (bpm)" deger={tempo} min={40} max={200} step={10} onChange={setTempo} />
        <Slider etiket="Süre" deger={sure} min={10} max={120} step={10} birim="sn" onChange={setSure} />
        <SesToggle acik={ses} onChange={setSes} />
      </KontrolBar>
      <Sahne>
        <CanvasSahne ciz={ciz} calisiyor={calisiyor} hiz={1} />
      </Sahne>
      <Ipucu>Sarı işaretçiyi başınızı oynatmadan yalnızca gözlerinizle takip edin. Her sıçramada bir vuruş duyulur.</Ipucu>
    </div>
  );
}
