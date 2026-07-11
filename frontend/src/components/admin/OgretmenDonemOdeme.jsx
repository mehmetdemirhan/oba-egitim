import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { CalendarClock, ChevronLeft, ChevronRight, Users, CheckCircle2, History } from "lucide-react";

/**
 * OgretmenDonemOdeme — dönem bazlı (ayın 15'i) öğretmen ödemesi. Admin Muhasebe ve
 * muhasebe (accountant) panelinde paylaşılır. Dönem = önceki ayın 15'i (hariç) → bu
 * ayın 15'i (dahil); döneme tamamlanmış kurlar girer. "Ödemeyi Kaydet" ile kayda
 * geçer (idempotent — aynı kur iki dönemde ödenmez). Props: apiBase.
 */
const AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
const formatTL = (v) => new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 0 }).format(Number(v || 0));
const donemEtiket = (d) => { if (!d) return ""; const [y, m] = d.split("-"); return `${AYLAR[parseInt(m, 10) - 1]} ${y} — ${d.slice(8)}'i`; };
const gun = (t) => { try { return new Date(t).toLocaleDateString("tr-TR"); } catch { return "—"; } };

export default function OgretmenDonemOdeme({ apiBase }) {
  const { toast } = useToast();
  const [donem, setDonem] = useState("");
  const [data, setData] = useState(null);
  const [gecmis, setGecmis] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [odenen, setOdenen] = useState(null);
  const [gecmisAcik, setGecmisAcik] = useState(false);

  const yukle = useCallback(async (d) => {
    setYukleniyor(true);
    try {
      const r = await axios.get(`${apiBase}/muhasebe/ogretmen-donem`, { params: d ? { donem: d } : {} });
      setData(r.data); setDonem(r.data.donem);
    } catch { toast({ title: "Dönem verisi yüklenemedi", variant: "destructive" }); }
    finally { setYukleniyor(false); }
  }, [apiBase, toast]);

  const gecmisYukle = useCallback(async () => {
    try { const r = await axios.get(`${apiBase}/muhasebe/ogretmen-donem/gecmis`); setGecmis(r.data?.odemeler || []); } catch { /* sessiz */ }
  }, [apiBase]);

  useEffect(() => { yukle(); gecmisYukle(); }, [yukle, gecmisYukle]);

  const kaydir = (yon) => {
    if (!donem) return;
    const [y, m] = donem.split("-").map(Number);
    let ny = y, nm = m + yon;
    if (nm < 1) { nm = 12; ny -= 1; } else if (nm > 12) { nm = 1; ny += 1; }
    yukle(`${ny}-${String(nm).padStart(2, "0")}-15`);
  };

  const ode = async (ogretmen_id) => {
    setOdenen(ogretmen_id);
    try {
      const r = await axios.post(`${apiBase}/muhasebe/ogretmen-donem/ode`, { ogretmen_id, donem });
      toast({ title: "Dönem ödemesi kaydedildi", description: `${formatTL(r.data?.toplam)} • ${r.data?.kur_sayisi} kur` });
      yukle(donem); gecmisYukle();
    } catch (e) {
      toast({ title: "Ödenemedi", description: e?.response?.data?.detail || "", variant: "destructive" });
    } finally { setOdenen(null); }
  };

  const ogretmenler = data?.ogretmenler || [];
  const genelToplam = ogretmenler.reduce((s, o) => s + (o.toplam || 0), 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-lg font-bold text-content flex items-center gap-2"><CalendarClock className="h-5 w-5" />Dönem Ödemesi (Ayın 15'i)</h3>
          <p className="text-sm text-subtle">Dönem içinde tamamlanan kurlar için öğretmen payı. Standart maaş yoktur.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => kaydir(-1)} className="p-1.5 border border-line rounded-lg hover:bg-app" aria-label="Önceki dönem"><ChevronLeft className="h-4 w-4" /></button>
          <span className="text-sm font-semibold text-content min-w-[160px] text-center tabular-nums">{donemEtiket(donem)}</span>
          <button onClick={() => kaydir(1)} className="p-1.5 border border-line rounded-lg hover:bg-app" aria-label="Sonraki dönem"><ChevronRight className="h-4 w-4" /></button>
        </div>
      </div>

      {yukleniyor ? (
        <div className="text-sm text-subtle py-4">Yükleniyor…</div>
      ) : ogretmenler.length === 0 ? (
        <div className="text-sm text-subtle bg-surface border border-line rounded-2xl p-6 text-center">Bu dönemde ödenecek tamamlanmış kur yok.</div>
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-subtle">Bu dönem toplam ödenecek: <span className="font-bold text-content tabular-nums">{formatTL(genelToplam)}</span></div>
          {ogretmenler.map((o) => (
            <div key={o.ogretmen_id} className="bg-surface border border-line rounded-2xl shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2.5 bg-app border-b border-line">
                <span className="font-semibold text-content flex items-center gap-2"><Users className="h-4 w-4" />{o.ogretmen_ad || "—"}</span>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold text-content tabular-nums">{formatTL(o.toplam)}</span>
                  <button onClick={() => ode(o.ogretmen_id)} disabled={odenen === o.ogretmen_id}
                    className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white text-xs px-3 py-1.5 rounded-lg disabled:opacity-50">
                    <CheckCircle2 className="h-4 w-4" />{odenen === o.ogretmen_id ? "Kaydediliyor…" : "Ödemeyi Kaydet"}
                  </button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-subtle border-b border-line">
                      <th className="px-3 py-1.5">Öğrenci</th><th className="px-3 py-1.5">Kur</th>
                      <th className="px-3 py-1.5">Eğitim</th><th className="px-3 py-1.5">Tamamlanma</th>
                      <th className="px-3 py-1.5 text-right">Pay</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(o.kurlar || []).map((c) => (
                      <tr key={c.kur_ucreti_id} className="border-b border-line last:border-0">
                        <td className="px-3 py-1.5 text-content">{c.ogrenci_ad}</td>
                        <td className="px-3 py-1.5">{c.kur}. kur</td>
                        <td className="px-3 py-1.5 text-subtle">{c.egitim_turu || "—"}</td>
                        <td className="px-3 py-1.5 text-subtle whitespace-nowrap">{gun(c.tamamlanma_tarihi)}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums text-emerald-600">{formatTL(c.pay)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Geçmiş dönem ödemeleri */}
      <div className="border border-line rounded-2xl bg-surface overflow-hidden">
        <button onClick={() => setGecmisAcik(!gecmisAcik)} className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-app text-sm font-medium text-content">
          <span className="flex items-center gap-2"><History className="h-4 w-4" />Geçmiş Dönem Ödemeleri ({gecmis.length})</span>
          {gecmisAcik ? <ChevronLeft className="h-4 w-4 rotate-90" /> : <ChevronRight className="h-4 w-4" />}
        </button>
        {gecmisAcik && (
          <div className="border-t border-line overflow-x-auto">
            {gecmis.length === 0 ? <div className="px-4 py-3 text-xs text-subtle">Kayıt yok.</div> : (
              <table className="w-full text-xs">
                <thead><tr className="text-left text-subtle border-b border-line bg-app">
                  <th className="px-3 py-1.5">Dönem</th><th className="px-3 py-1.5">Öğretmen</th>
                  <th className="px-3 py-1.5 text-right">Kur</th><th className="px-3 py-1.5 text-right">Toplam</th>
                  <th className="px-3 py-1.5">Kayıt</th>
                </tr></thead>
                <tbody>
                  {gecmis.map((o) => (
                    <tr key={o.id} className="border-b border-line last:border-0">
                      <td className="px-3 py-1.5 tabular-nums">{donemEtiket(o.donem)}</td>
                      <td className="px-3 py-1.5 text-content">{o.ogretmen_ad || "—"}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{(o.kur_ids || []).length}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums font-medium">{formatTL(o.toplam)}</td>
                      <td className="px-3 py-1.5 text-subtle whitespace-nowrap">{gun(o.tarih)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
