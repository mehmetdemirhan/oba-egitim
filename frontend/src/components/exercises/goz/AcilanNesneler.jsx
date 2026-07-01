// Açılan Nesneler — Dikey / Yatay.
// İki nesne (harf/sayı çifti) merkezden başlar, eksende birbirinden uzaklaşarak
// "açılır". Kullanıcı merkeze bakarken çevresel görüşle iki nesneyi de okur.
// Algı genişliğini (görme açıklığı) artırır.
import React, { useRef, useState } from "react";
import { CanvasSahne, KontrolBar, Slider, Sahne, Ipucu, TR_HARFLER, useEgzersizOturum } from "./ortak";

function rastgeleJeton() {
  // Yarı sayı yarı harf çifti üret.
  if (Math.random() < 0.5) {
    const n = Math.floor(Math.random() * 90 + 10);
    return String(n);
  }
  const h = TR_HARFLER[Math.floor(Math.random() * TR_HARFLER.length)];
  const h2 = TR_HARFLER[Math.floor(Math.random() * TR_HARFLER.length)];
  return h + h2;
}

export default function AcilanNesneler({ yon = "dikey", onTamamla }) {
  const dikey = yon === "dikey";
  const [hiz, setHiz] = useState(1.2);
  const [mesafe, setMesafe] = useState(70); // maksimum açılma (%)
  const [sure, setSure] = useState(30);
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla });

  const donguRef = useRef(-1);
  const jetonRef = useRef([rastgeleJeton(), rastgeleJeton()]);

  const ciz = (ctx, W, H, t) => {
    const cx = W / 2, cy = H / 2;
    const eksen = dikey ? (H / 2 - 30) : (W / 2 - 30);
    const dongu = Math.floor(t * 0.3);
    if (dongu !== donguRef.current) {
      donguRef.current = dongu;
      jetonRef.current = [rastgeleJeton(), rastgeleJeton()];
    }
    const p = (t * 0.3) % 1;             // 0..1 açılma ilerlemesi
    const d = 20 + p * (mesafe / 100) * eksen;

    // Merkez odak noktası
    ctx.beginPath(); ctx.arc(cx, cy, 6, 0, Math.PI * 2);
    ctx.fillStyle = "#ef4444"; ctx.fill();

    ctx.font = "bold 44px sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillStyle = `rgba(37,99,235,${1 - p * 0.3})`;
    const [j1, j2] = jetonRef.current;
    if (dikey) {
      ctx.fillText(j1, cx, cy - d);
      ctx.fillText(j2, cx, cy + d);
    } else {
      ctx.fillText(j1, cx - d, cy);
      ctx.fillText(j2, cx + d, cy);
    }
  };

  return (
    <div>
      <KontrolBar calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur}>
        <Slider etiket="Hız" deger={hiz} min={0.5} max={3} step={0.5} birim="x" onChange={setHiz} />
        <Slider etiket="Açılma" deger={mesafe} min={30} max={100} step={5} birim="%" onChange={setMesafe} />
        <Slider etiket="Süre" deger={sure} min={10} max={120} step={10} birim="sn" onChange={setSure} />
      </KontrolBar>
      <Sahne koyu={false}>
        <CanvasSahne ciz={ciz} calisiyor={calisiyor} hiz={hiz} />
      </Sahne>
      <Ipucu>Merkezdeki kırmızı noktaya bakın; gözünüzü oynatmadan {dikey ? "yukarı ve aşağı" : "sağ ve sol"} açılan iki nesneyi de okumaya çalışın.</Ipucu>
    </div>
  );
}
