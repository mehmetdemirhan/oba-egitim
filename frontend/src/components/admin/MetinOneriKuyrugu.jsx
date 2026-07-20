import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Inbox, RefreshCw, Check, X, PencilLine, ListPlus } from "lucide-react";

/**
 * MetinOneriKuyrugu — koordinatör/admin onay kuyruğu (madde: öğretmen metin
 * düzeltme / soru ekleme önerileri). Öğretmen düzenlemesi canlıya yazılmaz;
 * burada onaylanınca havuza işlenir ve öneren XP kazanır.
 * Uçlar: GET /diagnostic/oneri-kuyrugu, POST /diagnostic/oneri/{id}/karar.
 */
const BOLUM_AD = { analiz: "Okuma Metni", olcum: "Ölçüm Metni", okuma_parcalari: "Okuma Parçası" };

export default function MetinOneriKuyrugu({ apiBase }) {
  const [oneriler, setOneriler] = useState([]);
  const [yuk, setYuk] = useState(false);
  const [islenen, setIslenen] = useState(null);
  const [acik, setAcik] = useState(null);

  const yukle = useCallback(async () => {
    setYuk(true);
    try { const r = await axios.get(`${apiBase}/diagnostic/oneri-kuyrugu`); setOneriler(Array.isArray(r.data) ? r.data : []); }
    catch (e) { setOneriler([]); } finally { setYuk(false); }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  const karar = async (id, k) => {
    if (k === "reddet" && !window.confirm("Bu öneri reddedilsin mi? (havuza uygulanmaz)")) return;
    setIslenen(id);
    try {
      await axios.post(`${apiBase}/diagnostic/oneri/${id}/karar`, { karar: k });
      setOneriler((o) => o.filter((x) => x.id !== id));
    } catch (e) { /* yut */ } finally { setIslenen(null); }
  };

  const dOzet = (d = {}) => {
    const p = [];
    if (d.baslik != null) p.push("Başlık");
    if (d.icerik != null) p.push("İçerik");
    if (d.zorluk != null) p.push("Zorluk");
    if (d.tur != null) p.push("Tür");
    if (d.sinif_seviyesi != null) p.push("Sınıf");
    if (d.sorular != null) p.push(`${d.sorular.length} ÇSS`);
    if (d.acik_sorular != null) p.push(`${d.acik_sorular.length} açık uçlu`);
    return p.join(" • ") || "—";
  };

  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm mt-4">
      <div className="flex items-center gap-2 mb-3">
        <Inbox className="h-5 w-5 text-indigo-600" />
        <div>
          <div className="font-semibold text-content">Metin Düzeltme / Soru Ekleme Önerileri</div>
          <div className="text-xs text-subtle">Öğretmen önerileri. Onaylayınca havuza işlenir + öneren XP kazanır; reddedince uygulanmaz.</div>
        </div>
        <button onClick={yukle} disabled={yuk} className="ml-auto inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-3 py-1.5 text-sm">
          <RefreshCw className={`h-4 w-4 ${yuk ? "animate-spin" : ""}`} />Yenile
        </button>
      </div>

      {oneriler.length === 0 ? (
        <div className="text-sm text-subtle text-center py-8">Bekleyen öneri yok. 🎉</div>
      ) : (
        <div className="space-y-2">
          {oneriler.map((o) => (
            <div key={o.id} className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-3">
              <div className="flex items-center gap-2 flex-wrap">
                {o.metin_degisti && <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-amber-200 text-amber-800"><PencilLine className="h-3 w-3" />Düzeltme</span>}
                {o.soru_eklendi && <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-emerald-200 text-emerald-800"><ListPlus className="h-3 w-3" />Soru</span>}
                <span className="font-semibold text-content text-sm">{o.metin_baslik || "Metin"}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-600">{BOLUM_AD[o.bolum] || o.bolum}</span>
                <span className="text-xs text-subtle ml-auto">{o.oneren_ad} • {o.olusturma_tarihi ? new Date(o.olusturma_tarihi).toLocaleDateString("tr-TR") : ""}</span>
              </div>
              <div className="text-xs text-content mt-1.5">Değişiklik: <span className="text-subtle">{dOzet(o.degisiklikler)}</span></div>
              <button onClick={() => setAcik(acik === o.id ? null : o.id)} className="text-[11px] text-indigo-600 hover:underline mt-1">{acik === o.id ? "Önizlemeyi gizle" : "Önizle"}</button>
              {acik === o.id && (
                <div className="mt-2 space-y-2 text-xs">
                  {o.degisiklikler?.baslik != null && <div><b>Başlık:</b> {o.degisiklikler.baslik}</div>}
                  {o.degisiklikler?.icerik != null && <div className="max-h-40 overflow-y-auto whitespace-pre-wrap bg-surface border border-line rounded-lg p-2"><b>İçerik:</b>{"\n"}{o.degisiklikler.icerik}</div>}
                  {Array.isArray(o.degisiklikler?.acik_sorular) && (
                    <div className="space-y-0.5">{o.degisiklikler.acik_sorular.map((s, i) => (
                      <div key={i} className="border-l-2 border-indigo-300 pl-2"><span className="text-indigo-600 font-medium">{s.kategori || "?"}</span> — {s.soru}</div>
                    ))}</div>
                  )}
                </div>
              )}
              <div className="flex items-center gap-1.5 mt-2.5">
                <button onClick={() => karar(o.id, "onayla")} disabled={islenen === o.id}
                  className="inline-flex items-center gap-1 text-xs bg-emerald-600 text-white rounded-lg px-3 py-1.5 disabled:opacity-50">
                  <Check className="h-3.5 w-3.5" />Onayla & Uygula
                </button>
                <button onClick={() => karar(o.id, "reddet")} disabled={islenen === o.id}
                  className="inline-flex items-center gap-1 text-xs bg-app border border-line rounded-lg px-2.5 py-1.5 hover:border-rose-400 disabled:opacity-50">
                  <X className="h-3.5 w-3.5 text-rose-600" />Reddet
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
