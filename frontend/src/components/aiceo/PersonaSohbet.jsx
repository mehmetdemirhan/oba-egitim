import React, { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import { Send, MessageSquare, AlertTriangle, ShieldAlert, Bot } from "lucide-react";
import GeriBildirimWidget from "./GeriBildirimWidget";

/**
 * PersonaSohbet — birleşik çok-persona sohbeti (FAZ 3, madde 11).
 * Üstte persona seçici (role göre filtreli). Ayda/Deniz/Miran serbest sohbet; Atlas/Lina/Nova/Ayaz
 * "bu kararı neden verdin" açıklama sorgusu (opsiyonel task_id). Her cevap zayıf-dayanak uyarısından
 * geçer; deterministik'e düşen (guard ihlali) cevaplar ayrıca işaretlenir.
 */
const PERSONALAR = [
  { key: "ayda", ad: "Ayda", unvan: "AI CEO", roller: ["admin", "coordinator"], renk: "#2563eb", tip: "chat" },
  { key: "deniz", ad: "Deniz", unvan: "Denetçi", roller: ["admin"], renk: "#475569", tip: "chat" },
  { key: "miran", ad: "Miran", unvan: "Sistem Danışmanı", roller: ["teacher", "accountant"], renk: "#d97706", tip: "chat" },
  { key: "atlas", ad: "Atlas", unvan: "Mimar", roller: ["admin", "coordinator"], renk: "#6366f1", tip: "aciklama" },
  { key: "lina", ad: "Lina", unvan: "UI/UX", roller: ["admin", "coordinator"], renk: "#ec4899", tip: "aciklama" },
  { key: "nova", ad: "Nova", unvan: "Test/QA", roller: ["admin", "coordinator"], renk: "#10b981", tip: "aciklama" },
  { key: "ayaz", ad: "Ayaz", unvan: "Uygulama/Deploy", roller: ["admin", "coordinator"], renk: "#f59e0b", tip: "aciklama" },
];

export default function PersonaSohbet({ apiBase, user }) {
  const rol = user?.role;
  const uygun = PERSONALAR.filter((p) => p.roller.includes(rol));
  const [aktif, setAktif] = useState(uygun[0]?.key || "ayda");
  const [gecmis, setGecmis] = useState([]);
  const [soru, setSoru] = useState("");
  const [taskId, setTaskId] = useState("");
  const [yuk, setYuk] = useState(false);
  const listeRef = useRef(null);
  const p = PERSONALAR.find((x) => x.key === aktif);

  const gecmisYukle = useCallback(async () => {
    try {
      const r = await axios.get(`${apiBase}/ai/ceo/persona-sohbet`, { params: { persona: aktif } });
      setGecmis((r.data.mesajlar || []).slice().reverse());
    } catch (e) { setGecmis([]); }
  }, [apiBase, aktif]);
  useEffect(() => { gecmisYukle(); }, [gecmisYukle]);
  useEffect(() => { if (listeRef.current) listeRef.current.scrollTop = listeRef.current.scrollHeight; }, [gecmis]);

  const gonder = async () => {
    if (!soru.trim() || yuk) return;
    setYuk(true);
    const q = soru; setSoru("");
    try {
      const r = await axios.post(`${apiBase}/ai/ceo/persona-sor`, { persona: aktif, soru: q, task_id: taskId || undefined });
      if (r.data.ok) setGecmis((g) => [...g, r.data.mesaj]);
      else setGecmis((g) => [...g, { id: Math.random(), soru: q, cevap: "⚠ " + (r.data.sebep || "Cevap alınamadı."), kaynak: "hata" }]);
    } catch (e) {
      const detay = e.response?.data?.detail || e.message;
      setGecmis((g) => [...g, { id: Math.random(), soru: q, cevap: "⚠ " + detay, kaynak: "hata" }]);
    } finally { setYuk(false); }
  };

  if (uygun.length === 0) return <div className="text-sm text-subtle p-4">Bu rolde erişilebilir persona yok.</div>;

  return (
    <div className="rounded-2xl border border-line bg-surface shadow-sm flex flex-col h-[32rem]">
      {/* Persona seçici */}
      <div className="p-3 border-b border-line flex items-center gap-2 flex-wrap">
        <MessageSquare className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold text-content mr-1">Persona Sohbeti</span>
        {uygun.map((x) => (
          <button key={x.key} onClick={() => { setAktif(x.key); setTaskId(""); }}
            className={"text-xs px-2.5 py-1 rounded-full border transition-all " +
              (aktif === x.key ? "text-white border-transparent" : "bg-app text-subtle border-line hover:border-primary/40")}
            style={aktif === x.key ? { backgroundColor: x.renk } : {}}>
            {x.ad}<span className="opacity-70"> · {x.unvan}</span>
          </button>
        ))}
      </div>

      {/* Kapsam ipucu */}
      <div className="px-3 pt-2 text-[11px] text-subtle">
        {p?.tip === "aciklama"
          ? `${p.ad}'a "bu kararı neden verdin?" sor — yalnız kendi raporundaki karara dayanır.`
          : `${p?.ad} yalnız kendi veri kapsamına erişir (persona-leakage guard).`}
      </div>

      {/* Mesaj listesi */}
      <div ref={listeRef} className="flex-1 overflow-auto p-3 space-y-3">
        {gecmis.length === 0 && <div className="text-sm text-subtle text-center py-10">Henüz mesaj yok. İlk soruyu sor.</div>}
        {gecmis.map((m) => (
          <div key={m.id} className="space-y-1">
            <div className="text-right"><span className="inline-block bg-app border border-line rounded-2xl rounded-tr-sm px-3 py-1.5 text-sm text-content max-w-[85%] text-left">{m.soru}</span></div>
            <div className="flex items-start gap-2">
              <Bot className="h-4 w-4 mt-1 shrink-0" style={{ color: p?.renk }} />
              <div className="inline-block bg-surface border border-line rounded-2xl rounded-tl-sm px-3 py-1.5 text-sm text-content max-w-[85%] whitespace-pre-wrap">
                {m.cevap}
                {(m.zayif_dayanak || m.kaynak === "deterministik") && (
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {m.zayif_dayanak && <span className="inline-flex items-center gap-1 text-[10px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"><AlertTriangle className="h-3 w-3" />Zayıf dayanak: doğrulanamayan sayı{Array.isArray(m.dogrulanamayan_sayilar) && m.dogrulanamayan_sayilar.length ? ` (${m.dogrulanamayan_sayilar.join(", ")})` : ""}</span>}
                    {m.kaynak === "deterministik" && <span className="inline-flex items-center gap-1 text-[10px] text-slate-600 bg-slate-100 border border-slate-200 rounded px-1.5 py-0.5"><ShieldAlert className="h-3 w-3" />Guard: deterministik güvenli cevap</span>}
                  </div>
                )}
                {m.id && m.kaynak !== "hata" && (
                  <GeriBildirimWidget apiBase={apiBase} ajan={aktif} kaynakId={m.id} kaynakTur="sohbet" kategori={aktif} />
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Girdi */}
      <div className="p-3 border-t border-line space-y-2">
        {p?.tip === "aciklama" && (
          <input value={taskId} onChange={(e) => setTaskId(e.target.value)} placeholder="(opsiyonel) task_id — boşsa son rapor"
            className="w-full bg-app border border-line rounded-lg px-2.5 py-1.5 text-xs text-content outline-none focus:border-primary/40 font-mono" />
        )}
        <div className="flex gap-1.5">
          <input value={soru} onChange={(e) => setSoru(e.target.value)} onKeyDown={(e) => e.key === "Enter" && gonder()}
            placeholder={p?.tip === "aciklama" ? `${p.ad}'a bu kararı neden verdiğini sor…` : `${p?.ad}'a sor…`}
            className="flex-1 bg-app border border-line rounded-lg px-3 py-2 text-sm text-content outline-none focus:border-primary/40" />
          <button onClick={gonder} disabled={yuk || !soru.trim()} className="inline-flex items-center gap-1 bg-primary disabled:opacity-50 text-white text-sm rounded-lg px-3">
            <Send className="h-4 w-4" />{yuk ? "…" : "Gönder"}
          </button>
        </div>
      </div>
    </div>
  );
}
