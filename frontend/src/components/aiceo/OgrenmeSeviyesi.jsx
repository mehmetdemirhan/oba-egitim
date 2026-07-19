import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Brain, RefreshCw, TrendingUp, TrendingDown, Info } from "lucide-react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";

/**
 * OgrenmeSeviyesi — dürüst öğrenme metrikleri (FAZ 4, madde 14).
 * SADECE ölçülebilir sayılar: (a) ajan başına geri bildirim, (b) onay/red oranı trendi,
 * (c) tekrarlayan hata oranı (düşerse öğrenme sinyali), (d) aktif enjekte edilen ders.
 * Veri <5 → "henüz öğrenecek kadar veri yok" (ASLA sahte yüzde).
 * DÜRÜSTLÜK: RAG hafıza enjeksiyonu — model ağırlıkları değişmiyor.
 */
export default function OgrenmeSeviyesi({ apiBase }) {
  const [d, setD] = useState(null);
  const [yuk, setYuk] = useState(false);

  const yukle = useCallback(async () => {
    setYuk(true);
    try { const r = await axios.get(`${apiBase}/ai/ceo/ogrenme/metrikler`); setD(r.data); }
    catch (e) { setD(null); } finally { setYuk(false); }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  // Tekrar oranı trendi (son vs ilk) — düşüyorsa gerçek öğrenme sinyali
  const tekrarTrend = (() => {
    const s = (d?.tekrar_hata_serisi || []).filter(x => x.tekrar_orani != null);
    if (s.length < 2) return null;
    return s[s.length - 1].tekrar_orani - s[0].tekrar_orani; // <0 iyi
  })();

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-violet-600" />
          <div>
            <div className="font-semibold text-content">Öğrenme Seviyesi</div>
            <div className="text-xs text-subtle">Geri bildirimlerden ölçülen gerçek sinyaller — uydurma yüzde yok.</div>
          </div>
        </div>
        <button onClick={yukle} disabled={yuk} className="inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-3 py-1.5 text-sm"><RefreshCw className={`h-4 w-4 ${yuk ? "animate-spin" : ""}`} />Yenile</button>
      </div>

      {/* Dürüstlük notu */}
      <div className="text-[11px] text-violet-800 bg-violet-50 border border-violet-200 rounded-lg px-3 py-2 flex items-start gap-1.5">
        <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
        <span>{d?.not || "RAG tabanlı hafıza enjeksiyonu — model ağırlıkları değişmiyor. Aşağıdaki metrikler yalnız gerçek sayımlardır."}</span>
      </div>

      {!d ? <div className="text-sm text-subtle p-4">Yükleniyor…</div>
        : !d.yeterli_veri ? (
          <div className="rounded-2xl border border-line bg-surface p-8 text-center text-sm text-subtle">
            — Henüz öğrenecek kadar veri yok ({d.toplam_geri_bildirim} geri bildirim; en az 5 gerekir).
          </div>
        ) : (
          <>
            {/* (a) + (d) özet kartları */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className="rounded-xl border border-line bg-surface p-3">
                <div className="text-[10px] text-subtle uppercase font-semibold">Toplam Geri Bildirim</div>
                <div className="text-2xl font-bold text-content tabular-nums">{d.toplam_geri_bildirim}</div>
              </div>
              <div className="rounded-xl border border-line bg-surface p-3">
                <div className="text-[10px] text-subtle uppercase font-semibold">Aktif Enjekte Ders</div>
                <div className="text-2xl font-bold text-violet-600 tabular-nums">{d.enjekte_edilen_ders}</div>
                <div className="text-[10px] text-subtle">prompta eklenen (RAG)</div>
              </div>
              <div className="rounded-xl border border-line bg-surface p-3 col-span-2">
                <div className="text-[10px] text-subtle uppercase font-semibold mb-1">Tekrarlayan Hata Sinyali</div>
                {tekrarTrend == null ? <div className="text-sm text-subtle">—</div>
                  : <div className={`text-sm font-semibold inline-flex items-center gap-1 ${tekrarTrend < 0 ? "text-emerald-600" : tekrarTrend > 0 ? "text-rose-600" : "text-subtle"}`}>
                      {tekrarTrend < 0 ? <><TrendingDown className="h-4 w-4" />Azalıyor ({tekrarTrend} puan) — öğrenme sinyali</> : tekrarTrend > 0 ? <><TrendingUp className="h-4 w-4" />Artıyor (+{tekrarTrend} puan) — dikkat</> : "Değişim yok"}
                    </div>}
              </div>
            </div>

            {/* (b) onay oranı trendi */}
            <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
              <div className="font-semibold text-content text-sm mb-3">Onay Oranı Trendi (haftalık)</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={d.onay_orani_serisi} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="hafta" tick={{ fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="onay_orani" name="Onay %" stroke="#10b981" strokeWidth={2} dot={{ r: 2 }} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* (c) tekrarlayan hata oranı trendi */}
            <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
              <div className="font-semibold text-content text-sm mb-1">Tekrarlayan Hata Oranı (haftalık)</div>
              <div className="text-[11px] text-subtle mb-3">Aynı kategoride tekrar eden olumsuz geri bildirim payı. Düşüş = gerçek öğrenme.</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={d.tekrar_hata_serisi} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="hafta" tick={{ fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={{ fontSize: 11 }} />
                  <Line type="monotone" dataKey="tekrar_orani" name="Tekrar %" stroke="#ef4444" strokeWidth={2} dot={{ r: 2 }} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Ajan başına dağılım */}
            <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
              <div className="font-semibold text-content text-sm mb-3">Ajan Başına Geri Bildirim</div>
              <div className="space-y-1">
                {Object.entries(d.ajan_sayim).map(([a, v]) => (
                  <div key={a} className="flex items-center gap-2 text-xs">
                    <span className="w-16 font-medium text-content capitalize">{a}</span>
                    <span className="text-emerald-600">👍 {v.olumlu || 0}</span>
                    <span className="text-rose-600">👎 {v.olumsuz || 0}</span>
                    <span className="text-subtle">/ {v.toplam}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
    </div>
  );
}
