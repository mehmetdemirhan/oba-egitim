import React, { useMemo, useState } from "react";
import RozetKarti from "./RozetKarti";
import RozetDetayPopup from "./RozetDetayPopup";

/**
 * RozetGrid — rozet tanımlarını ızgara olarak gösterir (kazanılan/kilitli).
 * App.js'te öğrenci + öğretmen + veli + admin görünümlerinde tekrar kullanılır
 * (önceden iki ayrı yerde kopyalanan grid'in tek kaynağı).
 *
 * Props:
 *   tanimlar     — [{kod, ad, ikon, seviye, kategori, kosul, ...}]
 *   kazanilanlar — [{rozet_kodu, kazanma_tarihi}]
 *   kategoriFiltre (ops.) — string | null
 *   onRozetKlik  (ops.)   — (tanim) => void  (admin: düzenlemeye açar)
 *   adminMi      (ops.)   — bool  (true ise tümü açık gösterilir, detay yerine onRozetKlik)
 *   baslik       (ops.)   — string
 */
export default function RozetGrid({ tanimlar = [], kazanilanlar = [], kategoriFiltre = null, onRozetKlik, adminMi = false, baslik }) {
  const [secili, setSecili] = useState(null);

  const kazanmaHaritasi = useMemo(() => {
    const m = {};
    (kazanilanlar || []).forEach((k) => { m[k.rozet_kodu] = k.kazanma_tarihi || true; });
    return m;
  }, [kazanilanlar]);

  const gosterilecek = useMemo(
    () => (kategoriFiltre ? tanimlar.filter((t) => t.kategori === kategoriFiltre) : tanimlar),
    [tanimlar, kategoriFiltre]
  );

  const kazanilanSayi = tanimlar.filter((t) => kazanmaHaritasi[t.kod]).length;

  const tikla = (t) => {
    if (adminMi && onRozetKlik) return onRozetKlik(t);
    setSecili((prev) => (prev?.kod === t.kod && prev?.rol === t.rol ? null : t));
    if (onRozetKlik) onRozetKlik(t);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-bold text-sm text-gray-900">{baslik || "🏅 Rozetler"}</h3>
        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
          {adminMi ? `${tanimlar.length} tanım` : `${kazanilanSayi} / ${tanimlar.length}`}
        </span>
      </div>

      <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-1.5">
        {gosterilecek.map((t) => (
          <RozetKarti
            key={`${t.rol || ""}_${t.kod}`}
            tanim={t}
            kazanildi={adminMi ? true : !!kazanmaHaritasi[t.kod]}
            secili={secili?.kod === t.kod && secili?.rol === t.rol}
            onKlik={() => tikla(t)}
          />
        ))}
        {gosterilecek.length === 0 && (
          <div className="col-span-full text-center text-xs text-gray-400 py-4">Rozet yok</div>
        )}
      </div>

      {!adminMi && secili && (
        <div className="mt-2">
          <RozetDetayPopup
            rozet={secili}
            kazanildi={!!kazanmaHaritasi[secili.kod]}
            kazanmaTarihi={kazanmaHaritasi[secili.kod]}
            onKapat={() => setSecili(null)}
          />
        </div>
      )}
    </div>
  );
}
