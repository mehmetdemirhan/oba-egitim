import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Cpu, RefreshCw, ShieldCheck, ShieldAlert, HelpCircle } from "lucide-react";

/**
 * AgentScorecardReal — %100 dürüst AI Squad karnesi. Tüm sayılar canlı koleksiyonlardan
 * (GET /ai/squad/scorecard/ozet). Sabit/uydurma veri YOK; veri yoksa "—" gösterir (sahte %100 yok).
 */
const RISK = {
  safe: { l: "Güvenli", c: "bg-emerald-100 text-emerald-700", i: ShieldCheck },
  warning: { l: "İzlemede", c: "bg-amber-100 text-amber-700", i: ShieldAlert },
  critical: { l: "Kritik", c: "bg-red-100 text-red-700", i: ShieldAlert },
  veri_yok: { l: "Veri yok", c: "bg-slate-200 text-slate-500", i: HelpCircle },
};

export default function AgentScorecardReal({ apiBase }) {
  const [d, setD] = useState(null);
  const [yuk, setYuk] = useState(false);

  const yukle = useCallback(async () => {
    setYuk(true);
    try { const r = await axios.get(`${apiBase}/ai/squad/scorecard/ozet`); setD(r.data); } catch (e) {} finally { setYuk(false); }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  if (!d) return <div className="text-sm text-subtle p-4">Karne yükleniyor…</div>;

  const kpi = [
    ["Aktif ajan", d.total_active_agents, "text-content"],
    ["Toplam akış", d.total_pipeline_runs, "text-indigo-600"],
    ["Ajan reddi", d.total_rejected_runs, "text-red-600"],
    ["Deploy bekleyen", d.total_deploy_waiting, "text-amber-600"],
    ["Durduruldu", d.total_durduruldu, "text-subtle"],
    ["Ort. başarı", d.total_pipeline_runs || d.agent_matrix.some(a => a.yeterli_veri) ? `%${d.average_squad_performance}` : "—", "text-emerald-600"],
  ];

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-indigo-600" />
          <div>
            <div className="font-semibold text-content">AI Ajan Karnesi — Doğrulanmış (gerçek veri)</div>
            <div className="text-xs text-subtle">Tüm sayımlar canlı koleksiyonlardan; veri yoksa "—" (uydurma yok).</div>
          </div>
        </div>
        <button onClick={yukle} disabled={yuk} className="inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-3 py-1.5 text-sm">
          <RefreshCw className={`h-4 w-4 ${yuk ? "animate-spin" : ""}`} />Yenile
        </button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {kpi.map(([l, v, c]) => (
          <div key={l} className="rounded-xl border border-line bg-surface p-3">
            <div className="text-[10px] text-subtle uppercase font-semibold">{l}</div>
            <div className={`text-lg font-bold tabular-nums ${c}`}>{v}</div>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-line bg-surface p-3 shadow-sm overflow-x-auto">
        <div className="text-[11px] font-bold uppercase text-subtle mb-2">Ajan Performans Matrisi (gerçek sayımlar)</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] uppercase text-subtle border-b border-line">
              <th className="text-left pb-1.5">Ajan / Rol</th>
              <th className="text-right">Toplam</th>
              <th className="text-right">Olumlu</th>
              <th className="text-right">Engelleme</th>
              <th className="text-right">Skor</th>
              <th className="text-right">Durum</th>
            </tr>
          </thead>
          <tbody>
            {d.agent_matrix.map(a => {
              const rk = RISK[a.risk] || RISK.veri_yok;
              const Icon = rk.i;
              return (
                <tr key={a.agent_id} className="border-b border-line/60">
                  <td className="py-2"><div className="font-medium text-content">🤖 {a.agent_name}</div><div className="text-[10px] text-subtle">{a.role} · {a.son_not}</div></td>
                  <td className="text-right tabular-nums text-content">{a.toplam}</td>
                  <td className="text-right tabular-nums text-emerald-700">{a.olumlu}</td>
                  <td className="text-right tabular-nums text-red-600">{a.engelleme}</td>
                  <td className="text-right tabular-nums font-bold">{a.yeterli_veri ? `%${a.overall_score}` : "—"}</td>
                  <td className="text-right"><span className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded ${rk.c}`}><Icon className="h-3 w-3" />{rk.l}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="text-[10px] text-subtle mt-2">Not: "Olumlu/Engelleme" ajanın verdiği KARAR sayısıdır (Atlas onay/red, Nova vize/engelleme…), ajan hatası değil. Skor = olumlu/toplam.</div>
      </div>
    </div>
  );
}
