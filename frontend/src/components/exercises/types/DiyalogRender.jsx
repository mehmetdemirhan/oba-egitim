import React, { useMemo } from "react";
import SecmeliRender from "./SecmeliRender";

/**
 * Diyalog Anlama render bileşeni.
 * İçerik şeması: { metin: "Ad: söz\nAd: söz", sorular: [{ soru, secenekler, dogru }] }
 *
 * Metin satırları "Ad: söz" biçiminde sohbet baloncuklarına dönüştürülür
 * (konuşmacıya göre sol/sağ hizalı); ardından anlama soruları çoktan seçmeli
 * akışıyla sorulur.
 *
 * Render sözleşmesi: { icerik, onCevap, soruNo }
 */
export default function DiyalogRender({ icerik, onCevap, soruNo }) {
  const satirlar = useMemo(() => {
    const metin = icerik?.metin || "";
    const adlar = [];
    return metin.split("\n").map((s) => s.trim()).filter(Boolean).map((satir) => {
      const idx = satir.indexOf(":");
      if (idx === -1) return { ad: "", soz: satir, sag: false };
      const ad = satir.slice(0, idx).trim();
      const soz = satir.slice(idx + 1).trim();
      if (!adlar.includes(ad)) adlar.push(ad);
      return { ad, soz, sag: adlar.indexOf(ad) % 2 === 1 };
    });
  }, [icerik]);

  return (
    <div className="space-y-3">
      {satirlar.length > 0 && (
        <div className="bg-sky-50 border border-sky-200 rounded-2xl p-4 space-y-2">
          <div className="text-xs font-semibold text-sky-500 mb-1 uppercase tracking-wide">💬 Diyalog</div>
          {satirlar.map((s, i) => (
            <div key={i} className={`flex ${s.sag ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                s.sag ? "bg-sky-500 text-white rounded-br-sm" : "bg-white border border-sky-100 text-gray-800 rounded-bl-sm"}`}>
                {s.ad && <div className={`text-[10px] font-semibold mb-0.5 ${s.sag ? "text-sky-100" : "text-sky-500"}`}>{s.ad}</div>}
                {s.soz}
              </div>
            </div>
          ))}
        </div>
      )}
      <SecmeliRender icerik={icerik} onCevap={onCevap} soruNo={soruNo} />
    </div>
  );
}
