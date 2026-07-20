// Benzer Kelimeler — 4 kutuda ikişer kelime bulunur. Üç kutuda kelime çifti
// birebir aynıdır; bir kutuda çift birbirinden (tek harf) farklıdır.
// Kullanıcı FARKLI olan kutuyu bulur. Hızlı ayırt etme ve tarama becerisi.
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  EgzersizDuzen, Slider, TR_HARFLER, rastgele, dogruSes, yanlisSes,
  useEgzersizOturum, useKelimeHavuzu, useSkorKayit, RekorRozeti, useZorluk, ZorlukKontrol,
} from "./ortak";

const TIP = "benzer_kelimeler";

// Görsel/işitsel olarak karışan harf çiftleri — zor çeldiriciler (fark etmesi güç).
const KARISAN = { b: "d", d: "b", m: "n", n: "m", i: "ı", ı: "i", e: "a", a: "e",
  o: "ö", ö: "o", u: "ü", ü: "u", s: "ş", ş: "s", c: "ç", ç: "c", g: "ğ", ğ: "g", p: "b", t: "f", f: "t" };

// Bir kelimeyi tek harf değiştirerek "benzer ama farklı" üret.
// Zorluk arttıkça karışan-harf swap tercih edilir (belirgin değil, ayırt etmesi zor).
function benzerYap(kelime, zorluk) {
  if (kelime.length < 2) return kelime + "n";
  const idx = Math.floor(Math.random() * kelime.length);
  const ch = kelime[idx];
  let yeni;
  if (zorluk >= 3 && KARISAN[ch] && Math.random() < 0.4 + 0.12 * zorluk) {
    yeni = KARISAN[ch];
  } else {
    do { yeni = TR_HARFLER[Math.floor(Math.random() * TR_HARFLER.length)].toLocaleLowerCase("tr"); }
    while (yeni === ch);
  }
  return kelime.slice(0, idx) + yeni + kelime.slice(idx + 1);
}

export default function BenzerKelimeler({ onTamamla }) {
  const [sure, setSure] = useState(60);
  const [skor, setSkor] = useState(0);
  const [tur, setTur] = useState(0);
  const [geri, setGeri] = useState(null);
  const havuz = useKelimeHavuzu();
  const { rekor, sonSonuc, kaydet } = useSkorKayit(TIP);
  const { zorluk, taban, setTaban, min, max, bildirSonuc, sifirla } = useZorluk(TIP);

  // Skor için doğru/yanlış ve zorluğu ref'te tut (bitişte anlık değeri okumak için).
  const dogruRef = useRef(0), yanlisRef = useRef(0), zorlukRef = useRef(zorluk);
  useEffect(() => { zorlukRef.current = zorluk; }, [zorluk]);

  const bitince = () => {
    kaydet({ dogru: dogruRef.current, yanlis: yanlisRef.current, sure_sn: sure, zorluk: zorlukRef.current });
    onTamamla?.();
  };
  const { calisiyor, kalan, baslat, durdur } = useEgzersizOturum({ sure, onTamamla: bitince });

  // Zor kelime = daha uzun kelime. Zorluk 1..5 → min uzunluk 4..8.
  const minUzunluk = 3 + zorluk;
  const kelimeSec = () => {
    const uygun = havuz.filter((k) => k.length >= minUzunluk);
    return rastgele(uygun.length >= 4 ? uygun : havuz);
  };

  const soru = useMemo(() => {
    const farkliIdx = Math.floor(Math.random() * 4);
    const kutular = Array.from({ length: 4 }, (_, i) => {
      const k = kelimeSec();
      return i === farkliIdx ? [k, benzerYap(k, zorluk)] : [k, k];
    });
    return { kutular, farkliIdx };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tur, havuz]);

  useEffect(() => {
    if (!calisiyor) { setSkor(0); setTur(0); setGeri(null); dogruRef.current = 0; yanlisRef.current = 0; sifirla(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calisiyor]);

  const sec = (i) => {
    if (!calisiyor || geri) return;
    const dogru = i === soru.farkliIdx;
    if (dogru) { setSkor((s) => s + 1); dogruRef.current += 1; dogruSes(); }
    else { yanlisRef.current += 1; yanlisSes(); }
    bildirSonuc(dogru);
    setGeri({ dogru, secilen: i });
    setTimeout(() => { setGeri(null); setTur((t) => t + 1); }, 700);
  };

  return (
    <EgzersizDuzen calisiyor={calisiyor} kalan={kalan} sure={sure} baslat={baslat} durdur={durdur} koyu={false}
      aciklama="Kutulardaki kelime çiftlerini hızlıca karşılaştırın; harfleri farklı olan çifti seçin. Zorluk arttıkça kelimeler uzar ve fark daha küçülür."
      ayarlar={<>
        <ZorlukKontrol taban={taban} setTaban={setTaban} min={min} max={max} efektif={zorluk} />
        <Slider etiket="Süre" deger={sure} min={20} max={120} step={10} birim="sn" onChange={setSure} />
      </>}>
      <div className="h-full overflow-auto p-4 flex flex-col items-center justify-center">
        {!calisiyor ? (
          <div className="text-gray-400 text-sm text-center px-6">
            ▶ Başlat'a basın. İki kelimesi <strong>farklı</strong> olan kutuyu bulun.
            <div className="mt-3 flex flex-col items-center"><ZorlukKontrol taban={taban} setTaban={setTaban} min={min} max={max} efektif={zorluk} /></div>
            <RekorRozeti rekor={rekor} sonSonuc={sonSonuc} />
          </div>
        ) : (
          <>
            <div className="text-sm text-gray-500 mb-4">İki kelimesi <strong>aynı olmayan</strong> kutuya tıklayın</div>
            <div className="grid grid-cols-2 gap-4 w-full max-w-md">
              {soru.kutular.map((k, i) => {
                const isSecilen = geri && geri.secilen === i;
                const stil = isSecilen
                  ? (geri.dogru ? "border-green-500 bg-green-50" : "border-red-500 bg-red-50")
                  : (geri && i === soru.farkliIdx ? "border-green-400 bg-green-50" : "border-gray-200 hover:border-indigo-400 hover:bg-indigo-50");
                return (
                  <button key={i} onClick={() => sec(i)}
                    className={`rounded-xl border-2 p-4 transition-all active:scale-95 ${stil}`}>
                    <div className="text-lg font-bold text-gray-800">{k[0]}</div>
                    <div className="text-lg font-bold text-gray-800">{k[1]}</div>
                  </button>
                );
              })}
            </div>
            <div className="mt-3 text-center text-sm font-bold text-green-600">Skor: {skor}</div>
          </>
        )}
      </div>
    </EgzersizDuzen>
  );
}
