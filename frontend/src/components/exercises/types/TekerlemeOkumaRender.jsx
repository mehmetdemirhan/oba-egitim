import React, { useState } from "react";
import { Music, Check } from "lucide-react";

/**
 * Tekerleme Okuma render'ı (akıcı okuma, "serbest" puanlama).
 * İçerik: { metin, baslik }. Öğrenci tekerlemeyi yüksek sesle okur, sonra
 * "Okudum" ile işaretler → onCevap(true) (serbest puanlama doğru kabul eder).
 *
 * Sözleşme: props { icerik, onCevap, soruNo, ilerleme }
 */
export default function TekerlemeOkumaRender({ icerik, onCevap }) {
  const [bitti, setBitti] = useState(false);
  const metin = icerik?.metin || "";
  const baslik = icerik?.baslik || "Tekerleme";

  const tamamla = async () => {
    if (bitti) return;
    setBitti(true);
    await onCevap(true);
  };

  if (!metin) return null;

  return (
    <div className="space-y-4">
      <div className="bg-surface rounded-2xl border border-line p-6 shadow-sm text-center">
        <div className="inline-flex items-center gap-1.5 text-xs font-medium text-primary mb-3">
          <Music className="h-4 w-4" />{baslik}
        </div>
        <p className="text-xl md:text-2xl font-semibold text-content leading-relaxed">{metin}</p>
        <p className="text-sm text-subtle mt-4">Tekerlemeyi yüksek sesle, akıcı ve hızlı bir şekilde oku.</p>
      </div>
      <button
        onClick={tamamla}
        disabled={bitti}
        className="w-full inline-flex items-center justify-center gap-2 bg-primary hover:bg-primary-hover text-white font-medium py-3 rounded-2xl disabled:opacity-50">
        <Check className="h-5 w-5" />{bitti ? "Tamamlandı" : "Okudum"}
      </button>
    </div>
  );
}
