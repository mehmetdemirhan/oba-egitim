import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  ResponsiveContainer, ComposedChart, Bar, Line, LineChart, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from "recharts";
import { Filter, TrendingUp, Users, ChevronDown, ChevronRight, ArrowUp, ArrowDown, ArrowDownRight, Clock } from "lucide-react";
import BilgiIkonu from "../BilgiIkonu";

/**
 * DashboardAnalitik — admin: kur yenileme hunisi + nakit akışı/alacak yaşlandırma +
 * öğretmen performans tablosu. Tek uçtan (/dashboard/analitik) beslenir. Bölümler
 * daraltılabilir. Props: apiBase, onYaslandirmaSec(kova), onOgretmenSec(id).
 */
const AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
const formatTL = (v) => new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 0 }).format(Number(v || 0));
const ayEtiket = (ym) => { if (!ym) return ""; const [y, m] = ym.split("-"); return `${AY_KISA[parseInt(m, 10) - 1]} ${y.slice(2)}`; };

function SatisTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-surface border border-line rounded-lg shadow-lg p-2.5 text-xs space-y-0.5">
      <div className="font-bold text-content mb-1">{d.ayK}</div>
      <div className="flex justify-between gap-4"><span className="text-blue-600">Yeni Kayıt</span><span className="font-medium">{d.yeni_kur} kur</span></div>
      <div className="flex justify-between gap-4"><span className="text-violet-600">Yenileme</span><span className="font-medium">{d.yenileme_kur} kur</span></div>
      <div className="flex justify-between gap-4 border-t border-line pt-0.5"><span className="text-content font-semibold">Satılan Kur</span><span className="font-bold">{d.satilan_kur}</span></div>
      <div className="flex justify-between gap-4"><span className="text-emerald-600">Yenileme Oranı</span><span className="font-medium">{d.yenileme_orani == null ? "—" : `%${d.yenileme_orani}`}</span></div>
      <div className="flex justify-between gap-4"><span className="text-subtle">Beklenen Gelir</span><span className="font-medium">{formatTL(d.beklenen_gelir)}</span></div>
    </div>
  );
}

function Bolum({ baslik, ikon: Ikon, bilgi, children, varsayilanAcik = true }) {
  const [acik, setAcik] = useState(varsayilanAcik);
  return (
    <div className="border border-line rounded-2xl bg-surface shadow-sm overflow-hidden">
      {/* Başlık satırı: aç/kapa butonu + (i) bilgi ikonu ayrı öğeler (iç içe buton olmaz) */}
      <div className="w-full flex items-center justify-between px-4 py-3 hover:bg-app transition-colors">
        <button onClick={() => setAcik(!acik)} className="flex-1 flex items-center gap-2 text-left font-bold text-content">
          {Ikon && <Ikon className="h-5 w-5 text-primary" />}{baslik}
        </button>
        <div className="flex items-center gap-2">
          {bilgi && <BilgiIkonu k={bilgi} />}
          <button onClick={() => setAcik(!acik)} aria-label={acik ? "Kapat" : "Aç"}>
            {acik ? <ChevronDown className="h-5 w-5 text-subtle" /> : <ChevronRight className="h-5 w-5 text-subtle" />}
          </button>
        </div>
      </div>
      {acik && <div className="border-t border-line p-4">{children}</div>}
    </div>
  );
}

export default function DashboardAnalitik({ apiBase, onYaslandirmaSec, onOgretmenSec }) {
  const [veri, setVeri] = useState(null);
  const [siralama, setSiralama] = useState({ alan: "aktif_ogrenci", yon: "desc" });

  const yukle = useCallback(async () => {
    try { const r = await axios.get(`${apiBase}/dashboard/analitik`); setVeri(r.data); } catch { /* yetkisiz/sessiz */ }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  const perf = useMemo(() => {
    const liste = [...(veri?.ogretmen_performans || [])];
    const { alan, yon } = siralama;
    liste.sort((a, b) => {
      const av = a[alan] ?? -Infinity, bv = b[alan] ?? -Infinity;
      if (av === bv) return 0;
      return (yon === "asc" ? 1 : -1) * (av > bv ? 1 : -1);
    });
    return liste;
  }, [veri, siralama]);

  if (!veri) return null;
  const sirala = (alan) => setSiralama((s) => ({ alan, yon: s.alan === alan && s.yon === "desc" ? "asc" : "desc" }));
  const okIcon = (alan) => siralama.alan !== alan ? null : (siralama.yon === "desc" ? <ArrowDown className="h-3 w-3 inline" /> : <ArrowUp className="h-3 w-3 inline" />);

  const nakit = (veri.nakit_akisi || []).map((n) => ({ ...n, ayK: ayEtiket(n.ay) }));
  const trend = (veri.yenileme_trend || []).map((n) => ({ ...n, ayK: ayEtiket(n.ay) }));
  const satis = (veri.satis_basarisi || []).map((n) => ({ ...n, ayK: ayEtiket(n.ay) }));
  const huni = veri.huni || [];
  const enFazla = Math.max(1, ...huni.map((h) => h.tamamlayan));
  const yas = veri.yaslandirma || {};
  const KOVA = [["0-30", "0-30 gün", "bg-emerald-50 border-emerald-200 text-emerald-700"],
                ["31-60", "31-60 gün", "bg-amber-50 border-amber-200 text-amber-700"],
                ["60+", "60+ gün", "bg-red-50 border-red-200 text-red-700"]];
  // Huni basamağının rengi = o basamaktan bir üst kura GEÇİŞ sağlığı (leak noktasını vurgular).
  const oranRenk = (oran) =>
    oran == null ? { bar: "bg-slate-400", ok: "text-slate-500" }
      : oran >= 70 ? { bar: "bg-emerald-500", ok: "text-emerald-700" }
        : oran >= 40 ? { bar: "bg-amber-500", ok: "text-amber-700" }
          : { bar: "bg-red-500", ok: "text-red-600" };

  return (
    <div className="space-y-6">
      {/* 1. Kur Yenileme Hunisi */}
      <Bolum baslik="Kur Yenileme Hunisi" ikon={Filter} bilgi="huni">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-1.5">
            {huni.length === 0 ? <div className="text-sm text-subtle">Veri yok.</div> : huni.map((h, i) => {
              const sonBasamak = i === huni.length - 1;
              const renk = oranRenk(sonBasamak ? null : h.oran);
              const gen = Math.max(10, (h.tamamlayan / enFazla) * 100);
              return (
                <div key={h.kur}>
                  {/* Etiket bar ÜSTÜNDE — huni şekli (∝ öğrenci) korunur, metin okunur kalır */}
                  <div className="flex items-center justify-between gap-2 text-xs mb-1">
                    <span className="text-content font-medium">
                      {h.kur}. kuru tamamlayan: <span className="tabular-nums font-bold">{h.tamamlayan}</span> öğrenci
                    </span>
                    {h.beklemede > 0 && (
                      <span title="Kuru bitireli 30 günden az — bekleme penceresinde; geçiş oranı paydasından düşülür."
                        className="shrink-0 inline-flex items-center gap-1 text-[11px] text-amber-500/80 bg-amber-50 border border-amber-200/60 rounded-md px-1.5 py-0.5">
                        <Clock className="h-3 w-3" />{h.beklemede} beklemede
                      </span>
                    )}
                  </div>
                  <div className="h-7 bg-app rounded-lg overflow-hidden">
                    <div className={`h-full ${renk.bar} rounded-lg flex items-center px-2 transition-all`} style={{ width: `${gen}%` }}>
                      <span className="text-[11px] text-white font-semibold tabular-nums">{h.tamamlayan}</span>
                    </div>
                  </div>
                  {!sonBasamak && (
                    <div className="flex items-center flex-wrap gap-x-1.5 gap-y-0.5 pl-3 py-1">
                      <ArrowDownRight className={`h-3.5 w-3.5 ${renk.ok}`} />
                      <span className={`text-[11px] font-semibold tabular-nums ${renk.ok}`}>
                        {h.oran != null ? `%${h.oran} devam etti` : "geçiş yok"}
                      </span>
                      <span className="text-[11px] text-subtle tabular-nums">({h.gecen} öğrenci {h.kur + 1}. kura geçti)</span>
                    </div>
                  )}
                </div>
              );
            })}
            <div className="pt-1.5 text-[10px] text-subtle flex items-start gap-1 leading-snug">
              <Clock className="h-3 w-3 mt-0.5 shrink-0 text-amber-500/70" />
              <span>"Beklemede" = kuru bitireli 30 günden az; henüz üst kura geçmemiş ama bekleme penceresi açık. Geçiş oranının paydasından düşülür (kaybolmuş sayılmaz).</span>
            </div>
          </div>
          <div>
            <div className="text-xs text-subtle mb-1 flex items-center gap-1">
              Aylık yenileme oranı (%) — beklemede penceresi paydadan düşülür
              <BilgiIkonu k="yenileme_trend" konum="tl" />
            </div>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="ayK" fontSize={11} /><YAxis domain={[0, 100]} fontSize={11} unit="%" />
                  <Tooltip formatter={(v, n) => n === "oran" ? [`%${v}`, "Yenileme"] : [v, n]} />
                  <Line type="monotone" dataKey="oran" stroke="#059669" strokeWidth={2} name="Yenileme %" connectNulls dot={{ r: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </Bolum>

      {/* 1b. Satış Başarısı */}
      <Bolum baslik="Satış Başarısı" ikon={TrendingUp} bilgi="satis_basarisi">
        <div className="text-xs text-subtle mb-1">Son 12 ay — çubuklar (yığılmış): satılan kur = yeni kayıt + yenileme; çizgi: yenileme oranı (%)</div>
        <div style={{ width: "100%", height: 260 }}>
          <ResponsiveContainer>
            <ComposedChart data={satis} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
              <XAxis dataKey="ayK" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
              <Tooltip content={<SatisTooltip />} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
              <Bar yAxisId="left" dataKey="yeni_kur" stackId="s" fill="#3b82f6" name="Yeni Kayıt" />
              <Bar yAxisId="left" dataKey="yenileme_kur" stackId="s" fill="#8b5cf6" name="Yenileme" radius={[4, 4, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="yenileme_orani" stroke="#059669" strokeWidth={2.5} name="Yenileme %" connectNulls dot={{ r: 2 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Bolum>

      {/* 2. Nakit Akışı + Yaşlandırma */}
      <Bolum baslik="Nakit Akışı & Alacak Yaşlandırma" ikon={TrendingUp} bilgi="nakit_akisi">
        <div className="text-xs text-subtle mb-1">Son 12 ay — çubuklar: tahsilat/vergi/öğretmen ödemesi, çizgi: NET (tahsilat − vergi − ödeme)</div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={nakit}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="ayK" fontSize={11} /><YAxis fontSize={11} />
              <Tooltip formatter={(v, n) => [formatTL(v), n]} />
              <Legend iconType="circle" />
              <Bar dataKey="tahsilat" fill="#3b82f6" name="Tahsilat" />
              <Bar dataKey="vergi" fill="#ef4444" name="Vergi" />
              <Bar dataKey="ogretmen_odeme" fill="#f59e0b" name="Öğretmen Ödemesi" />
              <Line type="monotone" dataKey="net" stroke="#059669" strokeWidth={2.5} name="Net" dot={{ r: 2 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4">
          <div className="text-xs text-subtle mb-2 flex items-center gap-1" title={veri.yaslandirma_tanim}>Alacak Yaşlandırma — {veri.yaslandirma_tanim} (kovaya tıkla → tabloyu filtrele)<BilgiIkonu k="yaslandirma" konum="tl" /></div>
          <div className="grid grid-cols-3 gap-3">
            {KOVA.map(([k, etiket, renk]) => (
              <button key={k} onClick={() => onYaslandirmaSec && onYaslandirmaSec(k)}
                className={`border rounded-xl p-3 text-left hover:ring-2 hover:ring-offset-1 transition-all ${renk}`}>
                <div className="text-xs font-medium">{etiket}</div>
                <div className="text-xl font-bold tabular-nums">{yas[k]?.sayi ?? 0}</div>
                <div className="text-[11px] tabular-nums opacity-80">{formatTL(yas[k]?.toplam ?? 0)}</div>
              </button>
            ))}
          </div>
        </div>
      </Bolum>

      {/* 3. Öğretmen Performans Tablosu */}
      <Bolum baslik="Öğretmen Performans Tablosu" ikon={Users} bilgi="ogretmen_performans">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-subtle border-b border-line bg-app">
                <th className="px-3 py-2 cursor-pointer" onClick={() => sirala("ad")}>Öğretmen {okIcon("ad")}</th>
                <th className="px-3 py-2 text-right cursor-pointer" onClick={() => sirala("aktif_ogrenci")}>Aktif Öğr. {okIcon("aktif_ogrenci")}</th>
                <th className="px-3 py-2 text-right cursor-pointer" onClick={() => sirala("ort_tamamlama_gun")}>Ort. Süre {okIcon("ort_tamamlama_gun")}</th>
                <th className="px-3 py-2 text-right cursor-pointer" onClick={() => sirala("geciken_kur")}>Geciken {okIcon("geciken_kur")}</th>
                <th className="px-3 py-2 text-right cursor-pointer" onClick={() => sirala("yenileme_orani")}>Yenileme {okIcon("yenileme_orani")}</th>
                <th className="px-3 py-2 text-right cursor-pointer" onClick={() => sirala("memnuniyet")}>Memnuniyet {okIcon("memnuniyet")}</th>
                <th className="px-3 py-2 text-right cursor-pointer" onClick={() => sirala("donem_hakedis")}>Bu Dönem {okIcon("donem_hakedis")}</th>
              </tr>
            </thead>
            <tbody>
              {perf.length === 0 && <tr><td colSpan={7} className="px-3 py-6 text-center text-subtle">Öğretmen yok.</td></tr>}
              {perf.map((p) => {
                const sureAsim = p.ort_tamamlama_gun != null && p.ort_tamamlama_gun > 35;
                return (
                  <tr key={p.ogretmen_id} onClick={() => onOgretmenSec && onOgretmenSec(p.ogretmen_id)}
                    className="border-b border-line last:border-0 cursor-pointer hover:bg-app">
                    <td className="px-3 py-2 text-content font-medium">{p.ad}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{p.aktif_ogrenci}</td>
                    <td className={`px-3 py-2 text-right tabular-nums ${sureAsim ? (p.ort_tamamlama_gun > 42 ? "text-red-600 font-semibold" : "text-amber-600 font-medium") : ""}`}>
                      {p.ort_tamamlama_gun != null ? `${p.ort_tamamlama_gun} g` : "—"}
                    </td>
                    <td className={`px-3 py-2 text-right tabular-nums ${p.geciken_kur > 0 ? "text-amber-700 font-medium" : "text-subtle"}`}>{p.geciken_kur}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{p.yenileme_yetersiz ? <span className="text-[10px] text-subtle">yetersiz veri</span> : (p.yenileme_orani != null ? `%${p.yenileme_orani}` : "—")}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{p.memnuniyet != null ? p.memnuniyet.toFixed(2) : "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums font-medium">{formatTL(p.donem_hakedis)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-subtle mt-2">Ort. süre 35 günü aşarsa amber, 42+ kırmızı. Satıra tıkla → öğretmen detayı.</p>
      </Bolum>
    </div>
  );
}
