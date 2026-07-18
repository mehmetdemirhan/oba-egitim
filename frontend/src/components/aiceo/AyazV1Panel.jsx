import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Terminal, ShieldCheck, ShieldAlert, RefreshCw, Check, X, Rocket, Undo2, AlertTriangle, Link2 } from "lucide-react";

/**
 * AyazV1Panel — Ayaz v1.5 (GÜVENLİ). Doğal dil → kod TASLAĞI + risk analizi + STATİK güvenlik
 * taraması. Süreç-içi exec YOK, otomatik deploy YOK. Yönetici gerçek kodu görür; canlıya alma
 * insan onaylı ve mevcut patch_manager (patch_security AST + sürüm arşivi + rollback) üzerinden.
 * Uçlar /ai/ayaz/*.
 */
const DURUM = {
  incelemede: { l: "İncelemede", c: "bg-amber-100 text-amber-700" },
  guvenlik_reddetti: { l: "Güvenlik reddetti", c: "bg-red-100 text-red-700" },
  reddedildi: { l: "Reddedildi", c: "bg-slate-200 text-slate-600" },
  canlida: { l: "Canlıda", c: "bg-emerald-100 text-emerald-700" },
  kurulum_hatasi: { l: "Kurulum hatası", c: "bg-red-100 text-red-700" },
  geri_alindi: { l: "Geri alındı", c: "bg-slate-200 text-slate-600" },
};

export default function AyazV1Panel({ apiBase, user }) {
  const [talep, setTalep] = useState("");
  const [tasks, setTasks] = useState([]);
  const [secili, setSecili] = useState(null);
  const [yuk, setYuk] = useState("");
  const [mesaj, setMesaj] = useState("");
  const [audit, setAudit] = useState(null);
  const isAdmin = user?.role === "admin";
  const api = (x) => `${apiBase}${x}`;

  const yukle = useCallback(async () => {
    try {
      const r = await axios.get(api("/ai/ayaz/gorevler"));
      setTasks(r.data.tasks || []);
      setSecili((s) => (s ? (r.data.tasks || []).find((t) => t.id === s.id) || s : (r.data.tasks || [])[0] || null));
    } catch (e) {}
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  useEffect(() => {
    if (!secili?.id) { setAudit(null); return; }
    let iptal = false;
    axios.get(api(`/ai/ayaz/gorev/${secili.id}/audit`)).then((r) => { if (!iptal) setAudit(r.data); }).catch(() => { if (!iptal) setAudit(null); });
    return () => { iptal = true; };
  }, [secili?.id, secili?.durum]);

  const talepGonder = async () => {
    if (!talep.trim()) return;
    setYuk("talep"); setMesaj("");
    try {
      const r = await axios.post(api("/ai/ayaz/talep-uret"), { talep });
      setTalep(""); await yukle(); setSecili(r.data.task);
      setMesaj(r.data.task.durum === "incelemede" ? "Kod taslağı hazır — statik güvenlik taraması temiz. Lütfen kodu inceleyin." : "Kod üretildi ancak statik güvenlik taramasını geçemedi.");
    } catch (e) { setMesaj("Kod üretilemedi: " + (e.response?.data?.detail || e.message)); }
    finally { setYuk(""); }
  };

  const eylem = async (id, yol, onay) => {
    if (onay && !window.confirm(onay)) return;
    setYuk(yol);
    try {
      const r = await axios.post(api(`/ai/ayaz/gorev/${id}/${yol}`));
      setMesaj(r.data.durum === "canlida" ? "Modül mevcut patch pipeline'ından geçerek canlıya alındı." : `İşlem: ${r.data.durum}`);
      await yukle(); const d = await axios.get(api(`/ai/ayaz/gorev/${id}`)); setSecili(d.data);
    } catch (e) {
      const det = e.response?.data?.detail;
      setMesaj("İşlem başarısız: " + (typeof det === "object" ? (det.mesaj || JSON.stringify(det)) : (det || e.message)));
      await yukle();
    } finally { setYuk(""); }
  };

  const t = secili;
  const g = t?.guvenlik || {};

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-indigo-200 bg-indigo-50/40 p-4">
        <div className="flex items-center gap-2 text-content font-semibold"><Terminal className="h-5 w-5 text-indigo-600" />Ayaz v1.5 — Kod Asistanı (güvenli mod)</div>
        <p className="text-xs text-subtle mt-1">Doğal dil talebini kod <b>taslağına</b> + risk analizine çevirir ve statik güvenlik taraması yapar. Süreç-içi çalıştırma yoktur; canlıya alma <b>siz kodu inceledikten sonra</b>, mevcut modül-yama pipeline'ından (AST güvenlik + sürüm arşivi + geri alma) geçer.</p>
      </div>

      {mesaj && <div className="text-sm rounded-lg bg-app border border-line px-3 py-2">{mesaj}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Sol: talep + kuyruk */}
        <div className="space-y-3">
          <div className="rounded-2xl border border-line bg-surface p-3 shadow-sm space-y-2">
            <label className="text-[11px] font-bold text-subtle uppercase">Yazılım talebi</label>
            <textarea rows={3} value={talep} onChange={(e) => setTalep(e.target.value)}
              placeholder="Örn: Öğrenci raporuna toplam ders süresini ekle (salt-okunur)."
              className="w-full bg-app border border-line rounded-lg px-2.5 py-1.5 text-sm text-content outline-none focus:border-indigo-400 resize-none" />
            <button onClick={talepGonder} disabled={yuk === "talep" || !talep.trim()}
              className="w-full inline-flex items-center justify-center gap-1.5 bg-indigo-600 disabled:opacity-60 text-white text-sm rounded-lg py-2">
              {yuk === "talep" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Terminal className="h-4 w-4" />}Talebi koda dönüştür
            </button>
          </div>
          <div className="rounded-2xl border border-line bg-surface p-3 shadow-sm">
            <div className="text-[11px] font-bold text-subtle uppercase mb-2">Görev kuyruğu ({tasks.length})</div>
            <div className="space-y-1.5 max-h-72 overflow-auto">
              {tasks.length === 0 && <div className="text-xs text-subtle py-4 text-center">Henüz görev yok.</div>}
              {tasks.map((x) => (
                <button key={x.id} onClick={() => { setSecili(x); setMesaj(""); }}
                  className={`w-full text-left p-2.5 rounded-lg border transition ${secili?.id === x.id ? "border-indigo-300 bg-indigo-50/50" : "border-line hover:bg-app"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-content truncate">{x.aciklama || x.id}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${(DURUM[x.durum] || {}).c || "bg-app"}`}>{(DURUM[x.durum] || {}).l || x.durum}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Sağ: detay */}
        <div className="lg:col-span-2">
          {!t ? <div className="rounded-2xl border border-line bg-surface p-10 text-center text-subtle text-sm">Bir görev seçin.</div> : (
            <div className="rounded-2xl border border-line bg-surface shadow-sm p-4 space-y-3">
              <div className="flex items-start justify-between border-b border-line pb-2">
                <div>
                  <div className="text-sm font-bold text-content">{t.aciklama || "Kodlama görevi"}</div>
                  <div className="text-xs text-subtle italic mt-0.5">"{t.kullanici_talebi}"</div>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded shrink-0 ${(DURUM[t.durum] || {}).c || "bg-app"}`}>{(DURUM[t.durum] || {}).l || t.durum}</span>
              </div>

              {/* Analiz */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs bg-app border border-line rounded-xl p-2.5">
                <div><span className="text-subtle block text-[10px]">Risk</span><b className="uppercase">{t.etki_analizi?.risk_seviyesi}</b></div>
                <div><span className="text-subtle block text-[10px]">Etki alanı</span>{t.etki_analizi?.etki_alani || "—"}</div>
                <div><span className="text-subtle block text-[10px]">Süre (dk)</span>{t.etki_analizi?.tahmini_sure_dk ?? "—"}</div>
                <div className="truncate"><span className="text-subtle block text-[10px]">Dosyalar</span><span className="font-mono">{(t.etki_analizi?.degisen_dosyalar || []).join(", ") || "—"}</span></div>
              </div>

              {/* Statik güvenlik */}
              <div className={`rounded-xl border p-2.5 text-xs ${(g.errors || []).length || g.derleme_hatasi ? "bg-red-50 border-red-200" : "bg-emerald-50 border-emerald-200"}`}>
                <div className="flex items-center gap-1.5 font-semibold">
                  {(g.errors || []).length || g.derleme_hatasi ? <ShieldAlert className="h-4 w-4 text-red-600" /> : <ShieldCheck className="h-4 w-4 text-emerald-600" />}
                  Statik güvenlik taraması (patch_security AST — çalıştırılmadan)
                </div>
                {(g.errors || []).map((e, i) => <div key={i} className="text-red-700 font-mono mt-1">✗ {e}</div>)}
                {g.derleme_hatasi && <div className="text-red-700 font-mono mt-1">✗ derleme: {g.derleme_hatasi}</div>}
                {(g.warnings || []).map((w, i) => <div key={i} className="text-amber-700 font-mono mt-1">⚠ {w}</div>)}
                {!(g.errors || []).length && !g.derleme_hatasi && !(g.warnings || []).length && <div className="text-emerald-700 mt-0.5">Temiz — tehlikeli import/çağrı yok.</div>}
              </div>

              {/* GERÇEK kod — inceleme */}
              <div className="border border-line rounded-xl overflow-hidden">
                <div className="bg-app border-b border-line px-3 py-1.5 text-[10px] font-mono text-subtle">ÜRETİLEN KOD (inceleyin — canlıya alma bunu uygular)</div>
                <pre className="p-3 text-[11px] font-mono text-content overflow-auto whitespace-pre max-h-72 bg-app/50">{t.uretilen_kod}</pre>
              </div>

              {t.durum === "kurulum_hatasi" && t.kurulum?.errors && (
                <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">Kurulum reddedildi: {(t.kurulum.errors || []).join("; ")}</div>
              )}
              {t.durum === "canlida" && <div className="text-xs text-emerald-700">Canlı modül: <b>{t.modul_adi}</b> (v{t.kurulum?.version}) · alan: {t.canliya_alan}</div>}

              {/* Kriptografik hash-chain audit izi */}
              {audit && (audit.olaylar || []).length > 0 && (
                <div className="border border-line rounded-xl p-2.5">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="text-[11px] font-bold uppercase text-subtle flex items-center gap-1"><Link2 className="h-3.5 w-3.5 text-indigo-500" />Değiştirilemez Denetim İzi (hash-chain)</div>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold flex items-center gap-1 ${audit.dogrulama?.gecerli ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
                      {audit.dogrulama?.gecerli ? <><ShieldCheck className="h-3 w-3" />Zincir doğrulandı</> : <><ShieldAlert className="h-3 w-3" />Kurcalanmış (seq {audit.dogrulama?.kirilma_seq})</>}
                    </span>
                  </div>
                  <div className="space-y-1 max-h-40 overflow-auto">
                    {(audit.olaylar || []).map((o) => (
                      <div key={o.event_id} className="text-[10px] font-mono bg-app border border-line rounded px-2 py-1">
                        <div className="flex items-center justify-between text-content"><span><b>#{o.seq}</b> {o.action}</span><span className="text-subtle">{o.actor} · {o.timestamp ? new Date(o.timestamp).toLocaleString("tr-TR") : ""}</span></div>
                        <div className="text-subtle truncate">hash {String(o.event_hash).slice(0, 16)}… ← prev {String(o.previous_hash).slice(0, 12)}…</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Admin eylemleri */}
              {isAdmin && (
                <div className="flex flex-wrap gap-2 pt-2 border-t border-line">
                  {t.durum === "incelemede" && <>
                    <button onClick={() => eylem(t.id, "uygula", "Bu kodu incelediniz mi? Canlıya alma mevcut patch pipeline'ından geçecek (AST güvenlik + sürüm arşivi + geri alma). Devam?")} disabled={!!yuk}
                      className="inline-flex items-center gap-1 bg-emerald-600 text-white text-sm rounded-lg px-3 py-2"><Rocket className="h-4 w-4" />İncele ve Uygula</button>
                    <button onClick={() => eylem(t.id, "reddet")} disabled={!!yuk} className="inline-flex items-center gap-1 bg-red-600 text-white text-sm rounded-lg px-3 py-2"><X className="h-4 w-4" />Reddet</button>
                  </>}
                  {t.durum === "guvenlik_reddetti" && <button onClick={() => eylem(t.id, "reddet")} disabled={!!yuk} className="inline-flex items-center gap-1 bg-red-600 text-white text-sm rounded-lg px-3 py-2"><X className="h-4 w-4" />Reddet</button>}
                  {t.durum === "canlida" && <button onClick={() => eylem(t.id, "geri-al", "Bu modül canlıdan kaldırılsın mı (patch_manager ile)?")} disabled={!!yuk} className="inline-flex items-center gap-1 bg-slate-700 text-white text-sm rounded-lg px-3 py-2"><Undo2 className="h-4 w-4" />Geri Al</button>}
                </div>
              )}
              {t.durum === "guvenlik_reddetti" && <div className="text-[11px] text-amber-700 flex items-center gap-1"><AlertTriangle className="h-3.5 w-3.5" />Statik güvenlik taramasını geçmediği için uygulanamaz.</div>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
