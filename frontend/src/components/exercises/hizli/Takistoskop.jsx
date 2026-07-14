// Takistoskop — ekranın ortasında bir kelime (veya küçük kelime grubu) çok kısa süre
// (ör. 250 ms) parlar, sonra kaybolur ve odak artısı (+) kalır; ardından yenisi gelir.
// Amaç: tek bakışta kelime/grup tanıma (algı genişliği + okuma hızı). Kelimeler
// öğrencinin MEB kelime havuzundan ve seçili okuma metninden karışık gelir. Süre
// dolunca puan.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { EgzersizDuzen, useEgzersizOturum, Slider, useKelimeHavuzu, karistir } from "../goz/ortak";
import { useOkumaMetni, kelimelereBol } from "./ortak";

export default function Takistoskop({ onTamamla }) {
  const { metin, yenile } = useOkumaMetni(30);
  const mebHavuz = useKelimeHavuzu();
  const [flashMs, setFlashMs] = useState(300);   // görünme süresi
  const [bosMs, setBosMs] = useState(700);       // boşluk (odak) süresi
  const [grupBoyu, setGrupBoyu] = useState(1);   // aynı anda kaç kelime
  const [sure, setSure] = useState(45);          // toplam süre (sn)
  const [gosterilen, setGosterilen] = useState("");
  const [aktifFlash, setAktifFlash] = useState(false);
  const [sayac, setSayac] = useState(0);
  const timerRef = useRef(null);
  const idxRef = useRef(0);

  // Kelime havuzu: metin kelimeleri + MEB havuzu (karışık, tekrarsız-ish).
  const havuz = useMemo(() => {
    const metinKel = kelimelereBol(metin?.icerik).filter((w) => w.length >= 2);
    const birlesik = [...metinKel, ...(mebHavuz || [])];
    return karistir(birlesik.length ? birlesik : (mebHavuz || ["okuma", "kitap", "hızlı"]));
  }, [metin, mebHavuz]);

  const { calisiyor, kalan, baslat: oturumBaslat, durdur: oturumDurdur } = useEgzersizOturum({
    sure, onTamamla,
  });

  const temizle = () => { if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; } };

  // Flash döngüsü: göster (flashMs) → boş (bosMs) → sonraki.
  const dongu = () => {
    if (!havuz.length) return;
    const kelime = havuz.slice(idxRef.current % havuz.length, (idxRef.current % havuz.length) + grupBoyu).join(" ")
      || havuz[idxRef.current % havuz.length];
    idxRef.current += grupBoyu;
    setGosterilen(kelime); setAktifFlash(true); setSayac((s) => s + 1);
    timerRef.current = setTimeout(() => {
      setAktifFlash(false);
      timerRef.current = setTimeout(() => { dongu(); }, bosMs);
    }, flashMs);
  };

  const baslat = () => {
    idxRef.current = 0; setSayac(0); setGosterilen("");
    oturumBaslat();
    temizle();
    dongu();
  };
  const durdur = () => { temizle(); setAktifFlash(false); oturumDurdur(); };

  // Süre dolunca oturum biter → flash döngüsünü de durdur.
  useEffect(() => { if (!calisiyor) temizle(); }, [calisiyor]);
  useEffect(() => () => temizle(), []);
  useEffect(() => { temizle(); setAktifFlash(false); setGosterilen(""); if (calisiyor) oturumDurdur(); /* eslint-disable-next-line */ }, [flashMs, bosMs, grupBoyu, sure]);

  const ayarlar = (
    <>
      <Slider etiket="Görünme Süresi" deger={flashMs} min={100} max={1000} step={50} birim=" ms" onChange={setFlashMs} />
      <Slider etiket="Boşluk (odak) Süresi" deger={bosMs} min={300} max={1500} step={100} birim=" ms" onChange={setBosMs} />
      <Slider etiket="Grup Başına Kelime" deger={grupBoyu} min={1} max={3} onChange={setGrupBoyu} />
      <Slider etiket="Toplam Süre" deger={sure} min={20} max={120} step={5} birim=" sn" onChange={setSure} />
      <button onClick={yenile} className="w-full py-1.5 rounded-lg text-sm font-semibold border border-gray-200 bg-white text-gray-600 hover:bg-gray-50">🔄 Yeni Metin</button>
    </>
  );
  const aciklama = "Ortada bir kelime/grup çok kısa süre parlar, sonra kaybolur; odak artısına (+) bakın ve bir sonrakini bekleyin. Kelimeyi tek bakışta yakalamaya çalışın. Görünme süresini kısalttıkça zorlaşır.";

  return (
    <EgzersizDuzen calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur} ayarlar={ayarlar} aciklama={aciklama} koyu>
      <div className="h-full flex flex-col items-center justify-center text-center relative">
        <div className="absolute top-3 left-4 text-xs text-gray-500">Gösterilen: {sayac}</div>
        {calisiyor ? (
          aktifFlash ? (
            <div className="text-white font-bold" style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>{gosterilen}</div>
          ) : (
            <div className="text-gray-600 font-bold" style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>+</div>
          )
        ) : (
          <div className="text-gray-400">Başlamak için ▶ Başlat</div>
        )}
      </div>
    </EgzersizDuzen>
  );
}
