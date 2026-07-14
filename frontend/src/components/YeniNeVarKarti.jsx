import React, { useEffect, useState } from "react";
import axios from "axios";
import { Sparkles, X } from "lucide-react";

/**
 * YeniNeVarKarti — dashboard kartı: sisteme eklenen özelliklerin son maddeleri
 * (tarih + kısa açıklama). Son 5 görünür; "Tümü" ile geçmiş modalda açılır.
 * Rol hedefleme backend'de. Props: apiBase.
 */
const tarihStr = (t) => { try { return new Date(t).toLocaleDateString("tr-TR", { day: "numeric", month: "short" }); } catch { return t; } };

function Madde({ d }) {
  return (
    <div className="flex gap-3">
      <div className="shrink-0 text-[11px] text-subtle w-12 pt-0.5 tabular-nums">{tarihStr(d.tarih)}</div>
      <div className="min-w-0 border-l-2 border-indigo-200 pl-3 pb-2">
        {d.baslik && <div className="text-sm font-semibold text-content">{d.baslik}</div>}
        {d.icerik && <div className="text-xs text-subtle mt-0.5">{d.icerik}</div>}
      </div>
    </div>
  );
}

export default function YeniNeVarKarti({ apiBase }) {
  const [duyurular, setDuyurular] = useState([]);
  const [toplam, setToplam] = useState(0);
  const [tumuAcik, setTumuAcik] = useState(false);
  const [tumDuyurular, setTumDuyurular] = useState([]);

  useEffect(() => {
    axios.get(`${apiBase}/duyurular`).then((r) => {
      setDuyurular(r.data?.duyurular || []);
      setToplam(r.data?.toplam || 0);
    }).catch(() => {});
  }, [apiBase]);

  const tumunuAc = async () => {
    try {
      const r = await axios.get(`${apiBase}/duyurular`, { params: { hepsi: true } });
      setTumDuyurular(r.data?.duyurular || []);
      setTumuAcik(true);
    } catch {}
  };

  if (duyurular.length === 0) return null;

  return (
    <>
      <div className="bg-surface border border-line rounded-2xl shadow-sm p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-content inline-flex items-center gap-1.5">
            <Sparkles className="h-4 w-4 text-indigo-500" />Yeni Ne Var?
          </h3>
          {toplam > duyurular.length && (
            <button onClick={tumunuAc} className="text-xs text-indigo-600 hover:underline">Tümü ({toplam})</button>
          )}
        </div>
        <div className="space-y-1">
          {duyurular.map((d) => <Madde key={d.id} d={d} />)}
        </div>
      </div>

      {tumuAcik && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-start justify-center overflow-y-auto p-4" onClick={() => setTumuAcik(false)}>
          <div className="bg-surface rounded-2xl shadow-xl w-full max-w-lg my-8 p-5 relative" onClick={(e) => e.stopPropagation()}>
            <button onClick={() => setTumuAcik(false)} className="absolute top-3 right-3 text-subtle hover:text-content"><X className="h-5 w-5" /></button>
            <h3 className="text-base font-bold text-content inline-flex items-center gap-1.5 mb-4"><Sparkles className="h-5 w-5 text-indigo-500" />Yeni Ne Var? — Tümü</h3>
            <div className="space-y-1">
              {tumDuyurular.map((d) => <Madde key={d.id} d={d} />)}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
