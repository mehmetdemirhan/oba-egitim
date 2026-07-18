import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { GitBranch, RefreshCw, CheckCircle, Clock, Terminal } from "lucide-react";

/**
 * DeployQueuePanel — squad_deploy_queue görünürlük + manuel entegrasyon işaretleme.
 * OTOMATİK DEPLOY YOK: Lina JSX'i canlıya alma manuel git+Vercel'dir; bu panel yalnız takip/durum.
 * Uçlar /ai/squad/deploy-queue/*.
 */
export default function DeployQueuePanel({ apiBase, user }) {
  const [kuyruk, setKuyruk] = useState([]);
  const [secili, setSecili] = useState(null);
  const [not, setNot] = useState("");
  const [yuk, setYuk] = useState(false);
  const [mesaj, setMesaj] = useState("");
  const isAdmin = user?.role === "admin";

  const yukle = useCallback(async () => {
    setYuk(true);
    try {
      const r = await axios.get(`${apiBase}/ai/squad/deploy-queue/listele`);
      setKuyruk(r.data || []);
      setSecili((s) => (s ? (r.data || []).find((x) => x.queue_id === s.queue_id) || (r.data || [])[0] : (r.data || [])[0]) || null);
    } catch (e) {} finally { setYuk(false); }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  const entegreEt = async () => {
    if (!not.trim()) { setMesaj("Git commit SHA / Vercel referansı zorunlu."); return; }
    setYuk(true); setMesaj("");
    try {
      await axios.post(`${apiBase}/ai/squad/deploy-queue/entegre-et`, { queue_id: secili.queue_id, gelistirici_notu: not });
      setNot(""); setMesaj("Entegre edildi olarak mühürlendi."); await yukle();
    } catch (e) { setMesaj("İşlem başarısız: " + (e.response?.data?.detail || e.message)); } finally { setYuk(false); }
  };

  const bekleyen = kuyruk.filter((x) => x.durum !== "entegre_edildi").length;
  const t = secili;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <GitBranch className="h-5 w-5 text-indigo-600" />
          <div>
            <div className="font-semibold text-content">AI Dağıtım Kuyruğu (Git/Vercel köprüsü)</div>
            <div className="text-xs text-subtle">Onaylı işlerin <b>manuel</b> git+Vercel entegrasyon takibi — otomatik deploy yok. Bekleyen: {bekleyen}</div>
          </div>
        </div>
        <button onClick={yukle} disabled={yuk} className="inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-3 py-1.5 text-sm"><RefreshCw className={`h-4 w-4 ${yuk ? "animate-spin" : ""}`} />Yenile</button>
      </div>

      {mesaj && <div className="text-sm rounded-lg bg-app border border-line px-3 py-2">{mesaj}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-2xl border border-line bg-surface p-3 shadow-sm">
          <div className="text-[11px] font-bold text-subtle uppercase mb-2">Kuyruk</div>
          <div className="space-y-1.5 max-h-[28rem] overflow-auto">
            {kuyruk.length === 0 && <div className="text-sm text-subtle py-6 text-center">Kuyruk boş.</div>}
            {kuyruk.map((x) => (
              <button key={x.queue_id} onClick={() => { setSecili(x); setMesaj(""); }}
                className={`w-full text-left p-2.5 rounded-lg border transition ${secili?.queue_id === x.queue_id ? "border-indigo-300 bg-indigo-50/50" : "border-line hover:bg-app"}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-mono text-content truncate">{x.task_id}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 inline-flex items-center gap-1 ${x.durum === "entegre_edildi" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                    {x.durum === "entegre_edildi" ? <><CheckCircle className="h-3 w-3" />Entegre</> : <><Clock className="h-3 w-3" />Bekliyor</>}
                  </span>
                </div>
                <div className="text-[10px] text-subtle truncate mt-0.5">{x.hedef_dosya}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2">
          {!t ? <div className="rounded-2xl border border-line bg-surface p-10 text-center text-subtle text-sm">Bir öğe seçin.</div> : (
            <div className="rounded-2xl border border-line bg-surface shadow-sm p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-line pb-2">
                <div className="text-sm font-mono text-content">{t.queue_id}</div>
                <span className="text-[10px] text-subtle">{t.hedef_dosya}</span>
              </div>
              <div className="text-xs bg-app border border-line rounded-lg px-2.5 py-1.5"><b>Yönetici gerekçesi:</b> {t.admin_gerekce}</div>
              {(t.guvenlik_uyarilari || []).length > 0 && <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5">JSX uyarıları: {t.guvenlik_uyarilari.join("; ")}</div>}
              <div>
                <div className="text-[11px] font-bold uppercase text-subtle mb-1 flex items-center gap-1"><Terminal className="h-3.5 w-3.5 text-indigo-500" />Lina üretimi JSX (inceleyip manuel entegre edin)</div>
                <pre className="p-3 bg-app border border-line rounded-lg font-mono text-[11px] text-content overflow-auto max-h-72 whitespace-pre">{t.react_kodu}</pre>
              </div>
              {t.durum === "entegre_edildi" ? (
                <div className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-2.5 py-1.5">Entegre edildi · {t.entegrasyon_tarihi} · not: {t.gelistirici_notu}</div>
              ) : isAdmin ? (
                <div className="pt-2 border-t border-line space-y-2">
                  <input value={not} onChange={(e) => setNot(e.target.value)} placeholder="Git commit SHA / Vercel deploy referansı" className="w-full bg-app border border-line rounded-lg px-2.5 py-1.5 text-sm text-content outline-none focus:border-indigo-400 font-mono" />
                  <button onClick={entegreEt} disabled={yuk} className="w-full inline-flex items-center justify-center gap-1.5 bg-indigo-600 disabled:opacity-60 text-white text-sm rounded-lg py-2"><CheckCircle className="h-4 w-4" />Entegre Edildi olarak işaretle (kuyruğu kapat)</button>
                </div>
              ) : <div className="text-[11px] text-subtle">Entegre işaretleme yalnız admin.</div>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
