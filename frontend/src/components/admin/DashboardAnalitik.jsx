import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  ResponsiveContainer, ComposedChart, Bar, Line, LineChart, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from "recharts";
import { Filter, TrendingUp, Users, ArrowUp, ArrowDown, ArrowDownRight, Clock } from "lucide-react";
import { DashboardKart } from "../dashboard/Kart";
import { GRAFIK, EKSEN_TICK, anlamliDilim } from "../dashboard/dashboardTema";

// Grafikte hiç veri yokken küçük tek satır (12 aylık boş eksen yerine).
const VeriYok = ({ mesaj = "Henüz veri yok — girildikçe burada görünecek." }) => (
  <div className="h-full grid place-items-center text-sm text-subtle px-4 text-center">{mesaj}</div>
);

/**
 * DashboardAnalitik — kur yenileme hunisi + satış + nakit akışı/yaşlandırma +
 * öğretmen performansı. Tek uçtan (/dashboard/analitik) beslenir. Kartlar TEK
 * KART SİSTEMİNE (DashboardKart) taşındı; grafikler tek semantik palete oturdu;
 * 12 aylık grafikler yeterli veri yoksa zarif özet gösterir; öğretmen tablosu
 * ilk 8 + "Tümünü Göster" ile sadeleşti. Bölümlere yerleştirmek için hook +
 * ayrı kart bileşenleri ihraç edilir (Dashboard.jsx bunları kullanır).
 */
const AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
const formatTL = (v) => new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 0 }).format(Number(v || 0));
const ayEtiket = (ym) => { if (!ym) return ""; const [y, m] = ym.split("-"); return `${AY_KISA[parseInt(m, 10) - 1]} ${y.slice(2)}`; };
const son = (arr) => (Array.isArray(arr) && arr.length ? arr[arr.length - 1] : null);

function SatisTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-surface border border-line rounded-lg shadow-lg p-2.5 text-xs space-y-0.5">
      <div className="font-bold text-content mb-1">{d.ayK}</div>
      <div className="flex justify-between gap-4"><span style={{ color: GRAFIK.bilgi }}>Yeni Kayıt</span><span className="font-medium">{d.yeni_kur} kur</span></div>
      <div className="flex justify-between gap-4"><span style={{ color: GRAFIK.vurgu }}>Yenileme</span><span className="font-medium">{d.yenileme_kur} kur</span></div>
      <div className="flex justify-between gap-4 border-t border-line pt-0.5"><span className="text-content font-semibold">Satılan Kur</span><span className="font-bold">{d.satilan_kur}</span></div>
      <div className="flex justify-between gap-4"><span style={{ color: GRAFIK.basari }}>Yenileme Oranı</span><span className="font-medium">{d.yenileme_orani == null ? "—" : `%${d.yenileme_orani}`}</span></div>
      <div className="flex justify-between gap-4"><span className="text-subtle">Beklenen Gelir</span><span className="font-medium">{formatTL(d.beklenen_gelir)}</span></div>
    </div>
  );
}

// ── Veri hook: tek çağrı, türetilmiş seriler ──
export function useAnalitik(apiBase) {
  const [veri, setVeri] = useState(null);
  const yukle = useCallback(async () => {
    try { const r = await axios.get(`${apiBase}/dashboard/analitik`); setVeri(r.data); } catch { /* yetkisiz/sessiz */ }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);
  return [veri, yukle];
}

// ── 1) Kur Yenileme Hunisi ──
export function HuniKarti({ veri }) {
  if (!veri) return null;
  const huni = veri.huni || [];
  // MEVCUT veriyi hemen yansıt: trend yalnız veri olan aylara kırpılır (3 ay bekleme yok).
  const trend = anlamliDilim((veri.yenileme_trend || []).map((n) => ({ ...n, ayK: ayEtiket(n.ay) })), ["tamamlanan"]);
  const enFazla = Math.max(1, ...huni.map((h) => h.tamamlayan));
  const oranRenk = (oran) =>
    oran == null ? { bar: "bg-slate-400", ok: "text-slate-500" }
      : oran >= 70 ? { bar: "bg-emerald-500", ok: "text-emerald-700" }
        : oran >= 40 ? { bar: "bg-amber-500", ok: "text-amber-700" }
          : { bar: "bg-red-500", ok: "text-red-600" };
  return (
    <DashboardKart baslik="Kur Yenileme Hunisi" ikon={Filter} bilgi="huni" acilir>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-1.5">
          {huni.length === 0 ? <div className="text-sm text-subtle">Veri yok.</div> : huni.map((h, i) => {
            const sonBasamak = i === huni.length - 1;
            const renk = oranRenk(sonBasamak ? null : h.oran);
            const gen = Math.max(10, (h.tamamlayan / enFazla) * 100);
            return (
              <div key={h.kur}>
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
          <div className="text-xs text-subtle mb-1">Aylık yenileme oranı (%) — beklemede penceresi paydadan düşülür</div>
          <div className="h-56">
            {trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRAFIK.izgara} vertical={false} />
                  <XAxis dataKey="ayK" tick={EKSEN_TICK} /><YAxis domain={[0, 100]} tick={EKSEN_TICK} unit="%" />
                  <Tooltip formatter={(v, n) => n === "oran" ? [`%${v}`, "Yenileme"] : [v, n]} />
                  <Line type="monotone" dataKey="oran" stroke={GRAFIK.basari} strokeWidth={2} name="Yenileme %" connectNulls dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : <VeriYok mesaj="Henüz tamamlanan kur yok — yenileme trendi burada oluşacak." />}
          </div>
        </div>
      </div>
    </DashboardKart>
  );
}

// ── 2) Satış Başarısı ──
export function SatisKarti({ veri }) {
  if (!veri) return null;
  const satis = anlamliDilim((veri.satis_basarisi || []).map((n) => ({ ...n, ayK: ayEtiket(n.ay) })), ["satilan_kur", "yeni_kur", "yenileme_kur"]);
  return (
    <DashboardKart baslik="Satış Başarısı" ikon={TrendingUp} bilgi="satis_basarisi" acilir>
      <div className="text-xs text-subtle mb-2">Veri olan aylar — çubuklar (yığılmış): satılan kur = yeni kayıt + yenileme; çizgi: yenileme oranı (%)</div>
      <div style={{ width: "100%", height: 260 }}>
        {satis.length > 0 ? (
          <ResponsiveContainer>
            <ComposedChart data={satis} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRAFIK.izgara} vertical={false} />
              <XAxis dataKey="ayK" tick={EKSEN_TICK} />
              <YAxis yAxisId="left" allowDecimals={false} tick={EKSEN_TICK} />
              <YAxis yAxisId="right" orientation="right" domain={[0, 100]} unit="%" tick={EKSEN_TICK} />
              <Tooltip content={<SatisTooltip />} />
              <Legend iconType="circle" wrapperStyle={{ fontSize: 11 }} />
              <Bar yAxisId="left" dataKey="yeni_kur" stackId="s" fill={GRAFIK.bilgi} name="Yeni Kayıt" />
              <Bar yAxisId="left" dataKey="yenileme_kur" stackId="s" fill={GRAFIK.vurgu} name="Yenileme" radius={[4, 4, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="yenileme_orani" stroke={GRAFIK.basari} strokeWidth={2.5} name="Yenileme %" connectNulls dot={{ r: 3 }} />
            </ComposedChart>
          </ResponsiveContainer>
        ) : <VeriYok mesaj="Henüz kayıt/satış yok — ilk kayıtlarla bu grafik dolmaya başlar." />}
      </div>
    </DashboardKart>
  );
}

// ── 3) Nakit Akışı + Yaşlandırma ──
export function NakitKarti({ veri, onYaslandirmaSec, apiBase, onGuncelle }) {
  const [ay, setAy] = React.useState(() => new Date().toISOString().slice(0, 7));
  const [tutar, setTutar] = React.useState("");
  const [kaydet, setKaydet] = React.useState(false);
  if (!veri) return null;
  const nakit = anlamliDilim((veri.nakit_akisi || []).map((n) => ({ ...n, ayK: ayEtiket(n.ay) })), ["tahsilat", "vergi", "ogretmen_odeme", "reklam"]);
  const reklamKaydet = async () => {
    if (!/^\d{4}-\d{2}$/.test(ay)) return;
    setKaydet(true);
    try { await axios.put(`${apiBase}/muhasebe/reklam-gideri`, { ay, tutar: parseFloat(tutar) || 0 }); setTutar(""); onGuncelle && onGuncelle(); }
    catch (e) { /* yut */ } finally { setKaydet(false); }
  };
  const yas = veri.yaslandirma || {};
  const KOVA = [["0-30", "0-30 gün", "bg-emerald-50 border-emerald-200 text-emerald-700"],
                ["31-60", "31-60 gün", "bg-amber-50 border-amber-200 text-amber-700"],
                ["60+", "60+ gün", "bg-red-50 border-red-200 text-red-700"]];
  return (
    <DashboardKart baslik="Nakit Akışı & Alacak Yaşlandırma" ikon={TrendingUp} bilgi="nakit_akisi" acilir>
      <div className="text-xs text-subtle mb-2">Veri olan aylar — çubuklar: tahsilat/vergi/öğretmen ödemesi, çizgi: NET (tahsilat − vergi − ödeme)</div>
      <div className="h-64">
        {nakit.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={nakit}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRAFIK.izgara} vertical={false} />
              <XAxis dataKey="ayK" tick={EKSEN_TICK} /><YAxis tick={EKSEN_TICK} />
              <Tooltip formatter={(v, n) => [formatTL(v), n]} />
              <Legend iconType="circle" />
              <Bar dataKey="tahsilat" fill={GRAFIK.bilgi} name="Tahsilat" />
              <Bar dataKey="vergi" fill={GRAFIK.tehlike} name="Vergi" />
              <Bar dataKey="ogretmen_odeme" fill={GRAFIK.uyari} name="Öğretmen Ödemesi" />
              <Bar dataKey="reklam" fill="#9333EA" name="Reklam Gideri" />
              <Line type="monotone" dataKey="net" stroke={GRAFIK.basari} strokeWidth={2.5} name="Net (Tahsilat−Vergi−Öğr.−Reklam)" dot={{ r: 3 }} />
            </ComposedChart>
          </ResponsiveContainer>
        ) : <VeriYok mesaj="Henüz ödeme kaydı yok — tahsilat girildikçe akış burada oluşur." />}
      </div>
      {apiBase && (
        <div className="mt-3 flex flex-wrap items-end gap-2 bg-app rounded-xl p-3">
          <div className="text-xs text-subtle w-full">Aylık Reklam Gideri (geçmişe dönük girilebilir; Net'ten düşülür)</div>
          <input type="month" value={ay} onChange={(e) => setAy(e.target.value)} className="border border-line rounded-lg px-2 py-1.5 text-sm" />
          <input type="number" min="0" value={tutar} onChange={(e) => setTutar(e.target.value)} placeholder="Tutar (₺)" className="border border-line rounded-lg px-2 py-1.5 text-sm w-32" />
          <button onClick={reklamKaydet} disabled={kaydet} className="bg-purple-600 hover:bg-purple-700 text-white rounded-lg px-3 py-1.5 text-sm font-semibold disabled:opacity-50">{kaydet ? "…" : "Kaydet"}</button>
        </div>
      )}
      <div className="mt-4">
        <div className="text-xs text-subtle mb-2" title={veri.yaslandirma_tanim}>Alacak Yaşlandırma — {veri.yaslandirma_tanim} (kovaya tıkla → tabloyu filtrele)</div>
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
    </DashboardKart>
  );
}

// ── 4) Öğretmen Performans Tablosu (sadeleştirilmiş) ──
const PERF_VARSAYILAN = 8;
export function OgretmenPerfKarti({ veri, onOgretmenSec }) {
  const [siralama, setSiralama] = useState({ alan: "aktif_ogrenci", yon: "desc" });
  const [hepsi, setHepsi] = useState(false);

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
  const gosterilen = hepsi ? perf : perf.slice(0, PERF_VARSAYILAN);
  const bos = <span className="text-subtle opacity-50">—</span>;

  return (
    <DashboardKart baslik="Öğretmen Performans Tablosu" ikon={Users} bilgi="ogretmen_performans" acilir>
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
            {gosterilen.map((p) => {
              const sureAsim = p.ort_tamamlama_gun != null && p.ort_tamamlama_gun > 35;
              return (
                <tr key={p.ogretmen_id} onClick={() => onOgretmenSec && onOgretmenSec(p.ogretmen_id)}
                  className="border-b border-line last:border-0 cursor-pointer hover:bg-app">
                  <td className="px-3 py-2 text-content font-medium">{p.ad}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{p.aktif_ogrenci || bos}</td>
                  <td className={`px-3 py-2 text-right tabular-nums ${sureAsim ? (p.ort_tamamlama_gun > 42 ? "text-red-600 font-semibold" : "text-amber-600 font-medium") : ""}`}>
                    {p.ort_tamamlama_gun != null ? `${p.ort_tamamlama_gun} g` : bos}
                  </td>
                  <td className={`px-3 py-2 text-right tabular-nums ${p.geciken_kur > 0 ? "text-amber-700 font-medium" : "text-subtle/60"}`}>{p.geciken_kur || bos}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{p.yenileme_yetersiz ? <span className="text-[10px] text-subtle/50">yetersiz veri</span> : (p.yenileme_orani != null ? `%${p.yenileme_orani}` : bos)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{p.memnuniyet != null ? <span className="font-semibold text-content">{p.memnuniyet.toFixed(2)}</span> : bos}</td>
                  <td className="px-3 py-2 text-right tabular-nums font-medium">{p.donem_hakedis ? formatTL(p.donem_hakedis) : bos}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between flex-wrap gap-2 mt-2.5">
        {perf.length > PERF_VARSAYILAN && (
          <button onClick={() => setHepsi((h) => !h)} className="text-xs font-medium text-primary hover:underline">
            {hepsi ? "İlk 8'i göster" : `Tümünü göster (${perf.length})`}
          </button>
        )}
        <div className="text-[11px] text-subtle flex items-center gap-3 flex-wrap ml-auto">
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" />Ort. süre 35+ gün</span>
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" />42+ gün</span>
          <span>· Satıra tıkla → öğretmen detayı</span>
        </div>
      </div>
    </DashboardKart>
  );
}

// Geriye uyum: hepsini tek blokta render eden varsayılan bileşen.
export default function DashboardAnalitik({ apiBase, onYaslandirmaSec, onOgretmenSec }) {
  const [veri, yukleAnalitik] = useAnalitik(apiBase);
  if (!veri) return null;
  return (
    <div className="space-y-6">
      <HuniKarti veri={veri} />
      <SatisKarti veri={veri} />
      <NakitKarti veri={veri} onYaslandirmaSec={onYaslandirmaSec} apiBase={apiBase} onGuncelle={yukleAnalitik} />
      <OgretmenPerfKarti veri={veri} onOgretmenSec={onOgretmenSec} />
    </div>
  );
}
