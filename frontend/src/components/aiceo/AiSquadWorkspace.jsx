import React, { useState } from "react";
import axios from "axios";
import { Cpu, Play, Terminal, AlertTriangle, RefreshCw, Layers, Sparkles } from "lucide-react";

/**
 * AiSquadWorkspace — canlı orkestratörü (Atlas→Lina→Nova→[insan-onaylı Ayaz]) tetikleyen operasyon
 * odası. Gerçek POST /ai/squad/orkestrator/pipeline-tetikle (uydurma yok). Alanlar backend çıktısıyla
 * senkron: atlas_onay / lina_uretim / nova_vize / deploy_hazir / asama / son_not.
 */
const AJANLAR = [
  { id: "atlas", ad: "ATLAS — Baş Yazılım Mimarı", ico: "📐", alt: "SOLID, Cyclomatic Complexity, path-traversal + AST güvenlik", done: "atlas_onay", ok: "Onayladı", act: "Analiz ediyor", red: "Engelledi" },
  { id: "lina", ad: "LINA — UI/UX Mimarı", ico: "🎨", alt: "OBA tasarım dili React/Tailwind JSX üretimi", done: "lina_uretim", ok: "Tasarladı", act: "Kod üretiyor", red: "Reddedildi" },
  { id: "nova", ad: "NOVA — Test & Kalite (QA)", ico: "🧪", alt: "RBAC/XSS deterministik deploy kapısı + LLM inceleme", done: "nova_vize", ok: "Vize verdi", act: "İnceliyor", red: "Vize reddi" },
];

export default function AiSquadWorkspace({ apiBase }) {
  const [talep, setTalep] = useState("");
  const [kod, setKod] = useState("");
  const [yuk, setYuk] = useState(false);
  const [mesaj, setMesaj] = useState("");
  const [r, setR] = useState(null);

  const tetikle = async () => {
    if (talep.trim().length < 10) { setMesaj("Talep en az 10 karakter olmalı."); return; }
    setYuk(true); setMesaj(""); setR(null);
    try {
      const task_id = `task_user_${Date.now().toString().slice(-6)}`;
      const res = await axios.post(`${apiBase}/ai/squad/orkestrator/pipeline-tetikle`, {
        task_id, talep_metni: talep, baslangic_kodu: kod || null });
      setR(res.data);
    } catch (e) { setMesaj("Pipeline tetiklenemedi: " + (e.response?.data?.detail || e.message)); }
    finally { setYuk(false); }
  };

  const durdu = r && (r.asama === "reddedildi" || r.asama === "durduruldu");
  const ilkYapilmayan = r ? AJANLAR.find(a => !r[a.done])?.id : null;

  const adimDurumu = (a) => {
    if (!r) return "bekliyor";
    if (r[a.done]) return "tamamlandi";
    if (durdu && a.id === ilkYapilmayan) return r.asama === "durduruldu" ? "durduruldu" : "reddedildi";
    if (r.asama === a.id) return "aktif";
    return "bekliyor";
  };

  const rozet = (s) => ({
    tamamlandi: "bg-emerald-100 text-emerald-700 border-emerald-200",
    aktif: "bg-indigo-100 text-indigo-700 border-indigo-200 animate-pulse",
    reddedildi: "bg-red-100 text-red-700 border-red-200",
    durduruldu: "bg-amber-100 text-amber-700 border-amber-200",
    bekliyor: "bg-app text-subtle border-line",
  }[s] || "bg-app text-subtle border-line");

  const ayazRozet = () => {
    if (!r) return { l: "Bekliyor", c: rozet("bekliyor") };
    if (r.asama === "deploy_bekliyor") return { l: "🛠 Onay bekliyor", c: rozet("aktif") };
    if (r.asama === "onaylandi_devir") return { l: "Kuyruğa devredildi", c: rozet("tamamlandi") };
    if (r.asama === "tamamlandi") return { l: "Entegre edildi", c: rozet("tamamlandi") };
    return { l: "Bekliyor", c: rozet("bekliyor") };
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm flex items-center gap-2">
        <Cpu className="h-5 w-5 text-indigo-600" />
        <div>
          <div className="font-semibold text-content">AI Squad — Canlı Operasyon Odası</div>
          <div className="text-xs text-subtle">Atlas→Lina→Nova motorlarını gerçek verilerle tetikle. Otomatik deploy yok — Ayaz insan-onaylı devir kuyruğuna sevk eder.</div>
        </div>
      </div>

      {mesaj && <div className="text-sm rounded-lg bg-app border border-line px-3 py-2 flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-amber-600" />{mesaj}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Girdi */}
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm space-y-3">
          <div className="text-[11px] font-bold uppercase text-subtle flex items-center gap-1"><Terminal className="h-3.5 w-3.5 text-indigo-500" />Görev girişi</div>
          <div className="space-y-1">
            <label className="text-[10px] text-subtle uppercase font-semibold">Talep metni (≥10)</label>
            <textarea rows={4} value={talep} onChange={(e) => setTalep(e.target.value)}
              placeholder="Örn: Öğrenci rapor ekranını mobil uyumlu, responsive grid yap. RBAC admin vizesi zorunlu."
              className="w-full bg-app border border-line rounded-lg px-2.5 py-2 text-sm text-content resize-none outline-none focus:border-indigo-400" />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-subtle uppercase font-semibold">Başlangıç kodu (opsiyonel)</label>
            <textarea rows={4} value={kod} onChange={(e) => setKod(e.target.value)}
              placeholder="export default function RaporComponent() { ... }"
              className="w-full bg-app border border-line rounded-lg px-2.5 py-2 text-[11px] font-mono text-content resize-none outline-none focus:border-indigo-400" />
          </div>
          <button onClick={tetikle} disabled={yuk} className="w-full inline-flex items-center justify-center gap-1.5 bg-indigo-600 disabled:opacity-60 text-white text-sm font-semibold rounded-lg py-2">
            {yuk ? <><RefreshCw className="h-4 w-4 animate-spin" />Ajan zinciri koşuyor…</> : <><Play className="h-4 w-4" />Otonom ekibi tetikle</>}
          </button>
          <div className="text-[10px] text-subtle">Not: her tetikleme gerçek LLM çağrısı yapar (Atlas+Lina+Nova, AI kotasından düşer).</div>
        </div>

        {/* Pipeline */}
        <div className="lg:col-span-2 rounded-2xl border border-line bg-surface p-4 shadow-sm space-y-3">
          <div className="text-[11px] font-bold uppercase text-subtle flex items-center gap-1"><Layers className="h-3.5 w-3.5 text-emerald-600" />Canlı iş akışı</div>
          <div className="space-y-2">
            {AJANLAR.map((a) => {
              const s = adimDurumu(a.id);
              const et = s === "tamamlandi" ? `✓ ${a.ok}` : s === "aktif" ? a.act : s === "reddedildi" ? `✕ ${a.red}` : s === "durduruldu" ? "⏸ Durdu (AI yok)" : "Bekliyor";
              return (
                <div key={a.id} className={`p-3 border rounded-xl flex items-center justify-between ${s === "aktif" ? "border-indigo-300 bg-indigo-50/40" : "border-line bg-app"}`}>
                  <div className="flex items-center gap-2">
                    <span className="text-base">{a.ico}</span>
                    <div><div className="text-xs font-bold text-content">{a.ad}</div><div className="text-[10px] text-subtle">{a.alt}</div></div>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border shrink-0 ${rozet(s)}`}>{et}</span>
                </div>
              );
            })}
            {/* Ayaz */}
            <div className="p-3 border border-line bg-app rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-base">🚀</span>
                <div><div className="text-xs font-bold text-content">AYAZ — Dağıtım Masası</div><div className="text-[10px] text-subtle">İnsan-onaylı devir kuyruğu + manuel Git/Vercel köprüsü (otomatik deploy yok)</div></div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full border shrink-0 ${ayazRozet().c}`}>{ayazRozet().l}</span>
            </div>
          </div>

          {r && (
            <div className="rounded-xl border border-line bg-app p-3 text-xs space-y-1">
              <div className="font-semibold text-content flex items-center gap-1"><Sparkles className="h-3.5 w-3.5 text-indigo-500" />Süreç raporu</div>
              <div><span className="text-subtle">Task:</span> <span className="font-mono">{r.task_id}</span></div>
              <div><span className="text-subtle">Aşama:</span> <b className="uppercase">{r.asama}</b></div>
              <div className="pt-1 border-t border-line"><span className="text-subtle">Son not:</span> {r.son_not}</div>
              {r.asama === "deploy_bekliyor" && <div className="text-indigo-700">→ Yukarıdaki <b>Dağıtım Köprüsü / Kuyruk</b> panelinden admin onayı ile devredilebilir.</div>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
