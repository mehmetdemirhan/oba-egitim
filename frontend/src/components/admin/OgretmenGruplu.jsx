import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { ChevronDown, ChevronRight, Users } from "lucide-react";

/**
 * OgretmenGruplu — SPEC B: öğrenci ödemelerinin öğretmene göre gruplu görünümü.
 * Öğretmen satırı: öğrenci sayısı, toplam beklenen/ödenen/kalan, bu dönem hakedişi.
 * Tıklayınca altında öğrencileri açılır. Arama öğretmen + öğrenci adında çalışır.
 * Props: apiBase.
 */
const TL = (v) => `₺${Number(v || 0).toLocaleString("tr-TR")}`;

export default function OgretmenGruplu({ apiBase }) {
  const { toast } = useToast();
  const [gruplar, setGruplar] = useState([]);
  const [donem, setDonem] = useState("");
  const [ara, setAra] = useState("");
  const [acik, setAcik] = useState({});
  const [yukleniyor, setYukleniyor] = useState(true);

  useEffect(() => {
    axios.get(`${apiBase}/muhasebe/ogretmen-gruplu`)
      .then((r) => { setGruplar(r.data?.gruplar || []); setDonem(r.data?.donem || ""); })
      .catch(() => toast({ title: "Gruplu görünüm yüklenemedi", variant: "destructive" }))
      .finally(() => setYukleniyor(false));
  }, [apiBase, toast]);

  const filtreli = useMemo(() => {
    const q = ara.trim().toLocaleLowerCase("tr");
    if (!q) return gruplar;
    return gruplar
      .map((g) => {
        const ogrMatch = (g.ogretmen_ad || "").toLocaleLowerCase("tr").includes(q);
        const cocuklar = (g.ogrenciler || []).filter((o) => (o.ad || "").toLocaleLowerCase("tr").includes(q));
        if (ogrMatch) return g;
        if (cocuklar.length) return { ...g, ogrenciler: cocuklar, _acik: true };
        return null;
      })
      .filter(Boolean);
  }, [gruplar, ara]);

  if (yukleniyor) return <p className="text-subtle text-sm py-4">Yükleniyor…</p>;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <input type="text" value={ara} onChange={(e) => setAra(e.target.value)}
               placeholder="Öğretmen veya öğrenci ara…"
               className="border border-line rounded-lg px-3 py-2 text-sm bg-surface flex-1 min-w-[200px]" />
        {donem && <span className="text-xs text-subtle">Dönem: {donem}</span>}
      </div>

      <div className="space-y-2">
        {filtreli.length === 0 && <p className="text-subtle text-sm">Kayıt yok.</p>}
        {filtreli.map((g) => {
          const key = g.ogretmen_id || "_atanmamis";
          const goster = acik[key] || g._acik;
          return (
            <div key={key} className="bg-surface border border-line rounded-2xl shadow-sm overflow-hidden">
              <button onClick={() => setAcik((o) => ({ ...o, [key]: !goster }))}
                      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-app text-left">
                {goster ? <ChevronDown className="h-4 w-4 text-subtle shrink-0" /> : <ChevronRight className="h-4 w-4 text-subtle shrink-0" />}
                <Users className="h-4 w-4 text-subtle shrink-0" />
                <span className="font-semibold text-content flex-1 min-w-0 truncate">{g.ogretmen_ad || "Atanmamış"}</span>
                <span className="text-xs text-subtle whitespace-nowrap">{g.ogrenci_sayisi} öğr.</span>
                <span className="hidden sm:inline text-xs text-subtle whitespace-nowrap">Beklenen {TL(g.beklenen)}</span>
                <span className="hidden md:inline text-xs text-emerald-600 whitespace-nowrap">Ödenen {TL(g.odenen)}</span>
                <span className={`text-xs whitespace-nowrap ${g.kalan > 0 ? "text-red-600 font-semibold" : "text-subtle"}`}>Kalan {TL(g.kalan)}</span>
                <span className="text-xs bg-indigo-50 text-indigo-700 rounded-full px-2 py-0.5 whitespace-nowrap font-medium" title="Bu dönem hakedişi">
                  Hakediş {TL(g.bu_donem_hakedis)}
                </span>
              </button>
              {goster && (
                <div className="border-t border-line overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-subtle bg-app">
                        <th className="px-4 py-2">Öğrenci</th>
                        <th className="px-3 py-2 text-right">Beklenen</th>
                        <th className="px-3 py-2 text-right">Ödenen</th>
                        <th className="px-3 py-2 text-right">Kalan</th>
                        <th className="px-3 py-2">Durum</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(g.ogrenciler || []).map((o) => (
                        <tr key={o.id} className="border-t border-line">
                          <td className="px-4 py-2 text-content">{o.ad}</td>
                          <td className="px-3 py-2 text-right tabular-nums text-subtle">{TL(o.beklenen)}</td>
                          <td className="px-3 py-2 text-right tabular-nums text-emerald-600">{TL(o.odenen)}</td>
                          <td className={`px-3 py-2 text-right tabular-nums ${o.kalan > 0 ? "text-red-600 font-semibold" : "text-subtle"}`}>{TL(o.kalan)}</td>
                          <td className="px-3 py-2">
                            {o.mezun_borclu ? <span className="text-[11px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium">eğitimi bitti, borcu var</span>
                              : o.mezun ? <span className="text-[11px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">mezun</span>
                              : <span className="text-[11px] text-subtle">aktif</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
