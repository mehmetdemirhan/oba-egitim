import React, { useState } from "react";
import axios from "axios";
import { Cpu, Play, Terminal, AlertTriangle, RefreshCw, Layers, Sparkles, MessageSquare, Eye, Send } from "lucide-react";

/**
 * AiSquadWorkspace v2 — orkestratör tetikleyici + Lina kodu CANLI ÖNİZLEME + ajan bazlı İNTERAKTİF
 * revizyon. Hepsi GERÇEK mevcut uçlarla (backend değişmedi):
 *   tetikle → /ai/squad/orkestrator/pipeline-tetikle ; önizleme → /ai/squad/lina/raporlar/{id}
 *   revizyon → atlas:/analiz-et · lina:/tasarla (önizlemeyi günceller) · nova:/incele
 * Alanlar backend çıktısıyla senkron: atlas_onay/lina_uretim/nova_vize/deploy_hazir/asama/son_not.
 */
const AJANLAR = [
  { id: "atlas", ad: "📐 ATLAS", alt: "Mimari & güvenlik", done: "atlas_onay" },
  { id: "lina", ad: "🎨 LINA", alt: "UI/UX kod üretimi", done: "lina_uretim" },
  { id: "nova", ad: "🧪 NOVA", alt: "Test & entegrasyon vizesi", done: "nova_vize" },
];
const SELAM = {
  atlas: "Atlas hazır — mimari/güvenlik revizyonu iste.",
  lina: "Lina hazır — tasarım/JSX revizyonu iste (önizleme güncellenir).",
  nova: "Nova hazır — test/RBAC vize kontrolü iste.",
};

export default function AiSquadWorkspace({ apiBase }) {
  const [talep, setTalep] = useState("");
  const [kod, setKod] = useState("");
  const [yuk, setYuk] = useState(false);
  const [mesaj, setMesaj] = useState("");
  const [r, setR] = useState(null);
  const [gorunum, setGorunum] = useState("pipeline"); // pipeline | preview
  const [onizleme, setOnizleme] = useState("");
  const [ajan, setAjan] = useState("atlas");
  const [sohbet, setSohbet] = useState({ atlas: [{ k: "sys", t: SELAM.atlas }], lina: [{ k: "sys", t: SELAM.lina }], nova: [{ k: "sys", t: SELAM.nova }] });
  const [girdi, setGirdi] = useState("");
  const [sohbetYuk, setSohbetYuk] = useState(false);
  const api = (x) => `${apiBase}${x}`;
  const ekle = (a, m) => setSohbet((p) => ({ ...p, [a]: [...p[a], m] }));

  const linaKoduGetir = async (tid) => {
    try {
      const rr = await axios.get(api(`/ai/squad/lina/raporlar/${tid}`));
      const rap = (rr.data.raporlar || []).find((x) => x.durum === "tamam");
      const code = rap?.tasarim?.react_kodu;
      if (code) { setOnizleme(code); return true; }
    } catch (e) {}
    return false;
  };

  const tetikle = async () => {
    if (talep.trim().length < 10) { setMesaj("Talep en az 10 karakter olmalı."); return; }
    setYuk(true); setMesaj(""); setR(null); setOnizleme("");
    try {
      const task_id = `task_user_${Date.now().toString().slice(-6)}`;
      const res = await axios.post(api("/ai/squad/orkestrator/pipeline-tetikle"), { task_id, talep_metni: talep, baslangic_kodu: kod || null });
      setR(res.data);
      if (res.data.lina_uretim) { const ok = await linaKoduGetir(res.data.task_id); if (ok) setGorunum("preview"); }
      else setOnizleme(`// Lina kod üretmedi. Aşama: ${res.data.asama}\n// ${res.data.son_not}`);
    } catch (e) { setMesaj("Pipeline tetiklenemedi: " + (e.response?.data?.detail || e.message)); }
    finally { setYuk(false); }
  };

  const revizyon = async () => {
    if (girdi.trim().length < 5) return;
    const a = ajan, msg = girdi.trim();
    ekle(a, { k: "user", t: msg }); setGirdi(""); setSohbetYuk(true);
    const tid = r?.task_id || `task_rev_${Date.now().toString().slice(-6)}`;
    try {
      if (a === "atlas") {
        const res = await axios.post(api("/ai/squad/atlas/analiz-et"), { task_id: tid, kod_blogu: `[Revizyon talebi]: ${msg}\n\nMevcut kod:\n${onizleme || "(yok)"}` });
        const rap = res.data.rapor || {};
        ekle(a, { k: "agent", t: rap.durum === "reddedildi" ? `✕ Reddetti: ${rap.neden}` : `Onay: ${rap.mimari_onay} · kalite ${rap.llm_analizi?.kod_kalitesi_notu ?? "—"}. ${rap.llm_analizi?.teknik_borc_analizi || "(deterministik)"}` });
      } else if (a === "lina") {
        const res = await axios.post(api("/ai/squad/lina/tasarla"), { task_id: tid, talep: msg });
        const rap = res.data.rapor || {};
        if (res.data.durum === "tamam" && rap.tasarim?.react_kodu) {
          setOnizleme(rap.tasarim.react_kodu); setGorunum("preview");
          ekle(a, { k: "agent", t: `✓ Yeni tasarım üretildi → ${rap.tasarim.hedef_dosya}. Önizleme güncellendi.` });
        } else if (res.data.durum === "llm_gerekli") ekle(a, { k: "agent", t: "AI (GEMINI) gerekli — uydurma tasarım üretilmez." });
        else ekle(a, { k: "agent", t: `✕ Güvenlik reddi: ${(rap.guvenlik_bloklari || []).join("; ")}` });
      } else {
        const res = await axios.post(api("/ai/squad/nova/incele"), { task_id: tid, kod_blogu: onizleme && onizleme.length >= 10 ? onizleme : `[İnceleme]: ${msg}` });
        const rap = res.data.rapor || {};
        ekle(a, { k: "agent", t: `deploy_onayi=${rap.deploy_onayi}. ${(rap.engelleme_nedenleri || []).join("; ") || "engel yok"}` });
      }
    } catch (e) { ekle(a, { k: "sys", t: "⚠️ Revizyon iletilemedi: " + (e.response?.data?.detail || e.message) }); }
    finally { setSohbetYuk(false); }
  };

  const durdu = r && (r.asama === "reddedildi" || r.asama === "durduruldu");
  const ilkYok = r ? AJANLAR.find((x) => !r[x.done])?.id : null;
  const adimDurumu = (x) => !r ? "bekliyor" : r[x.done] ? "tamamlandi" : (durdu && x.id === ilkYok ? (r.asama === "durduruldu" ? "durduruldu" : "reddedildi") : r.asama === x.id ? "aktif" : "bekliyor");
  const rozet = (s) => ({ tamamlandi: "bg-emerald-100 text-emerald-700 border-emerald-200", aktif: "bg-indigo-100 text-indigo-700 border-indigo-200 animate-pulse", reddedildi: "bg-red-100 text-red-700 border-red-200", durduruldu: "bg-amber-100 text-amber-700 border-amber-200" }[s] || "bg-app text-subtle border-line");

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-indigo-600" />
          <div>
            <div className="font-semibold text-content">AI Squad — Komuta & Prova Odası</div>
            <div className="text-xs text-subtle">Tetikle · Lina kodunu canlı önizle · ajanlara interaktif revizyon. Otomatik deploy yok.</div>
          </div>
        </div>
        <div className="flex bg-app border border-line rounded-lg p-0.5 text-xs font-semibold">
          <button onClick={() => setGorunum("pipeline")} className={`px-3 py-1 rounded flex items-center gap-1 ${gorunum === "pipeline" ? "bg-indigo-600 text-white" : "text-subtle"}`}><Layers className="h-3.5 w-3.5" />Akış</button>
          <button onClick={() => setGorunum("preview")} className={`px-3 py-1 rounded flex items-center gap-1 ${gorunum === "preview" ? "bg-indigo-600 text-white" : "text-subtle"}`}><Eye className="h-3.5 w-3.5" />Önizleme</button>
        </div>
      </div>

      {mesaj && <div className="text-sm rounded-lg bg-app border border-line px-3 py-2 flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-amber-600" />{mesaj}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Girdi */}
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm space-y-3 flex flex-col">
          <div className="text-[11px] font-bold uppercase text-subtle flex items-center gap-1"><Terminal className="h-3.5 w-3.5 text-indigo-500" />Görev girişi</div>
          <textarea rows={3} value={talep} onChange={(e) => setTalep(e.target.value)} placeholder="Örn: Veli ödeme rapor ekranı için responsive tablo tasarla…" className="w-full bg-app border border-line rounded-lg px-2.5 py-2 text-sm text-content resize-none outline-none focus:border-indigo-400" />
          <textarea rows={4} value={kod} onChange={(e) => setKod(e.target.value)} placeholder="Başlangıç kodu (opsiyonel)…" className="w-full bg-app border border-line rounded-lg px-2.5 py-2 text-[11px] font-mono text-content resize-none outline-none focus:border-indigo-400" />
          <button onClick={tetikle} disabled={yuk} className="w-full inline-flex items-center justify-center gap-1.5 bg-indigo-600 disabled:opacity-60 text-white text-sm font-semibold rounded-lg py-2">
            {yuk ? <><RefreshCw className="h-4 w-4 animate-spin" />Koşuyor…</> : <><Play className="h-4 w-4" />Ekibi harekete geçir</>}
          </button>
          <div className="text-[10px] text-subtle">Her tetikleme/revizyon gerçek LLM çağrısıdır (AI kotasından düşer).</div>
        </div>

        {/* Akış / Önizleme */}
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          {gorunum === "pipeline" ? (
            <div className="space-y-2">
              <div className="text-[11px] font-bold uppercase text-subtle flex items-center gap-1"><Layers className="h-3.5 w-3.5 text-emerald-600" />Canlı akış</div>
              {AJANLAR.map((x) => { const s = adimDurumu(x.id); return (
                <div key={x.id} className={`p-2.5 border rounded-lg flex items-center justify-between ${s === "aktif" ? "border-indigo-300 bg-indigo-50/40" : "border-line bg-app"}`}>
                  <div><div className="text-xs font-bold text-content">{x.ad}</div><div className="text-[10px] text-subtle">{x.alt}</div></div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border ${rozet(s)}`}>{s}</span>
                </div>); })}
              <div className={`p-2.5 border border-line bg-app rounded-lg flex items-center justify-between`}>
                <div><div className="text-xs font-bold text-content">🚀 AYAZ</div><div className="text-[10px] text-subtle">İnsan-onaylı devir (otomatik deploy yok)</div></div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full border ${r?.asama === "deploy_bekliyor" ? rozet("aktif") : rozet(r?.deploy_hazir ? "tamamlandi" : "bekliyor")}`}>{r?.asama === "deploy_bekliyor" ? "🛠 onay bekliyor" : r?.deploy_hazir ? "devredildi" : "bekliyor"}</span>
              </div>
              {r && <div className="rounded-lg border border-line bg-app p-2.5 text-xs"><b className="text-content">Aşama:</b> {r.asama} · <span className="text-subtle">{r.son_not}</span></div>}
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-[11px] font-bold uppercase text-subtle flex items-center gap-1"><Eye className="h-3.5 w-3.5 text-indigo-500" />Lina üretimi JSX (canlı)</div>
              <pre className="p-3 bg-app border border-line rounded-lg font-mono text-[11px] text-content overflow-auto h-72 whitespace-pre">{onizleme || "// Henüz kod üretilmedi. Tetikle veya Lina'ya revizyon iste."}</pre>
            </div>
          )}
        </div>

        {/* İnteraktif revizyon */}
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm flex flex-col h-[26rem]">
          <div className="text-[11px] font-bold uppercase text-subtle flex items-center gap-1 mb-2"><MessageSquare className="h-3.5 w-3.5 text-amber-600" />İnteraktif revizyon</div>
          <div className="grid grid-cols-3 gap-1 mb-2 text-xs font-semibold">
            {AJANLAR.map((x) => <button key={x.id} onClick={() => setAjan(x.id)} className={`py-1 rounded border ${ajan === x.id ? "border-indigo-300 bg-indigo-50 text-indigo-700" : "border-line text-subtle"}`}>{x.id.toUpperCase()}</button>)}
          </div>
          <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 text-xs">
            {sohbet[ajan].map((m, i) => (
              <div key={i} className={`p-2 rounded-lg leading-relaxed ${m.k === "user" ? "bg-indigo-600 text-white ml-6" : m.k === "sys" ? "bg-app text-subtle border border-line text-[11px]" : "bg-app border border-line text-content mr-6"}`}>
                <b>{m.k === "user" ? "Sen: " : m.k === "sys" ? "Platform: " : ajan.toUpperCase() + ": "}</b>{m.t}
              </div>
            ))}
            {sohbetYuk && <div className="text-[11px] text-subtle flex items-center gap-1"><RefreshCw className="h-3 w-3 animate-spin" />{ajan.toUpperCase()} çalışıyor…</div>}
          </div>
          <div className="pt-2 border-t border-line flex gap-1.5 mt-2">
            <input value={girdi} onChange={(e) => setGirdi(e.target.value)} onKeyDown={(e) => e.key === "Enter" && !sohbetYuk && revizyon()} placeholder={`${ajan.toUpperCase()}'a revizyon emri…`} className="flex-1 bg-app border border-line rounded-lg px-2.5 py-1.5 text-sm text-content outline-none focus:border-indigo-400" />
            <button onClick={revizyon} disabled={sohbetYuk} className="bg-indigo-600 disabled:opacity-60 text-white p-2 rounded-lg"><Send className="h-4 w-4" /></button>
          </div>
        </div>
      </div>
    </div>
  );
}
