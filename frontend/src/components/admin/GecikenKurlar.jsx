import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";

/**
 * GecikenKurlar — 35 günü (5 hafta) aşan aktif kurların sayacı + listesi. Admin
 * dashboard, admin Muhasebe ve muhasebe (accountant) panelinde paylaşılır. Görüntüleme
 * backend'de throttle'lı bildirim taramasını da tetikler. Props: apiBase, kompakt.
 */
export default function GecikenKurlar({ apiBase, kompakt = false }) {
  const [veri, setVeri] = useState(null);
  const [acik, setAcik] = useState(false);

  const yukle = useCallback(async () => {
    try {
      const r = await axios.get(`${apiBase}/muhasebe/geciken-kurlar`);
      setVeri(r.data);
    } catch { /* yetkisiz/sessiz */ }
  }, [apiBase]);

  useEffect(() => { yukle(); }, [yukle]);

  const sayi = veri?.sayi ?? 0;
  const kurlar = veri?.kurlar || [];
  const gun = (t) => { try { return new Date(t).toLocaleDateString("tr-TR"); } catch { return t; } };

  // Kompakt rozet (dashboard kartı içinde)
  if (kompakt) {
    return (
      <div className={`flex items-center gap-2 ${sayi > 0 ? "text-amber-700" : "text-subtle"}`}>
        <AlertTriangle className="h-4 w-4" />
        <span className="text-sm font-medium">Geciken Kur: <span className="tabular-nums font-bold">{sayi}</span></span>
      </div>
    );
  }

  return (
    <div className="border border-line rounded-2xl bg-surface shadow-sm overflow-hidden">
      <button onClick={() => setAcik(!acik)} className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-app transition-colors">
        <span className="font-semibold text-content flex items-center gap-2">
          <AlertTriangle className={`h-5 w-5 ${sayi > 0 ? "text-amber-600" : "text-subtle"}`} />
          Geciken Kurlar
          <span className={`text-xs px-2 py-0.5 rounded-full tabular-nums ${sayi > 0 ? "bg-amber-100 text-amber-800" : "bg-gray-100 text-gray-500"}`}>{sayi}</span>
        </span>
        {acik ? <ChevronDown className="h-5 w-5 text-subtle" /> : <ChevronRight className="h-5 w-5 text-subtle" />}
      </button>
      {acik && (
        <div className="border-t border-line overflow-x-auto">
          {kurlar.length === 0 ? (
            <div className="px-4 py-3 text-xs text-subtle">5 haftayı aşan aktif kur yok. 👍</div>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-subtle border-b border-line bg-app">
                  <th className="px-3 py-1.5">Öğrenci</th><th className="px-3 py-1.5">Kur</th>
                  <th className="px-3 py-1.5">Başlangıç</th><th className="px-3 py-1.5 text-right">Gün</th>
                </tr>
              </thead>
              <tbody>
                {kurlar.map((k) => (
                  <tr key={k.kur_ucreti_id} className="border-b border-line last:border-0">
                    <td className="px-3 py-1.5 text-content">{k.ogrenci_ad}</td>
                    <td className="px-3 py-1.5">{k.kur}. kur</td>
                    <td className="px-3 py-1.5 text-subtle whitespace-nowrap">{gun(k.baslangic)}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums font-medium text-amber-700">{k.gun} gün</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
