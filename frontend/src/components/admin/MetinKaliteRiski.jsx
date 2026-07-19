import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { AlertTriangle, RefreshCw, ShieldCheck, PencilLine, Trash2, Star } from "lucide-react";

/**
 * MetinKaliteRiski — koordinatör/admin denetim kuyruğu (madde: çok kötü geri bildirim alan metinler).
 * Öğretmen puanı ort < 2.0 VE oy ≥ 2 olan, henüz İNCELENMEMİŞ metinler burada listelenir.
 * Karar: Koru / Düzeltildi / Havuzdan Çıkar → metin bir daha kuyruğa DÜŞMEZ.
 * Uçlar: GET /metin-kalite/riskli, POST /metin-kalite/{id}/karar.
 */
const BOLUM_AD = { analiz: "Okuma Metni", olcum: "Ölçüm Metni", okuma_parcalari: "Okuma Parçası" };

export default function MetinKaliteRiski({ apiBase }) {
  const [metinler, setMetinler] = useState([]);
  const [yuk, setYuk] = useState(false);
  const [islenen, setIslenen] = useState(null);

  const yukle = useCallback(async () => {
    setYuk(true);
    try { const r = await axios.get(`${apiBase}/metin-kalite/riskli`); setMetinler(r.data.metinler || []); }
    catch (e) { setMetinler([]); } finally { setYuk(false); }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  const karar = async (metinId, k) => {
    if (k === "cikarildi" && !window.confirm("Bu metin havuzdan çıkarılsın mı? (durum: reddedildi)")) return;
    setIslenen(metinId);
    try {
      await axios.post(`${apiBase}/metin-kalite/${metinId}/karar`, { karar: k });
      setMetinler((m) => m.filter((x) => x.id !== metinId));
    } catch (e) { /* yut */ } finally { setIslenen(null); }
  };

  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle className="h-5 w-5 text-rose-600" />
        <div>
          <div className="font-semibold text-content">Kalite Riski — Öğretmen Geri Bildirimi</div>
          <div className="text-xs text-subtle">Öğretmen puanı düşük (ort &lt; 2.0, en az 2 oy) metinler. Karar verince kuyruktan çıkar, tekrar düşmez.</div>
        </div>
        <button onClick={yukle} disabled={yuk} className="ml-auto inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-3 py-1.5 text-sm">
          <RefreshCw className={`h-4 w-4 ${yuk ? "animate-spin" : ""}`} />Yenile
        </button>
      </div>

      {metinler.length === 0 ? (
        <div className="text-sm text-subtle text-center py-8">Kalite riski taşıyan metin yok. 🎉</div>
      ) : (
        <div className="space-y-2">
          {metinler.map((m) => (
            <div key={m.id} className="rounded-xl border border-rose-200 bg-rose-50/40 p-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-content text-sm">{m.baslik}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-600">{BOLUM_AD[m.bolum] || m.bolum}</span>
                {m.sinif_seviyesi && <span className="text-[10px] text-subtle">{m.sinif_seviyesi}</span>}
                <span className="inline-flex items-center gap-1 text-sm font-bold text-rose-600 ml-auto">
                  <Star className="h-4 w-4 fill-rose-400 text-rose-400" />{m.kalite?.ort ?? "—"}
                  <span className="text-[11px] font-normal text-subtle">({m.kalite?.sayi ?? 0} oy)</span>
                </span>
              </div>
              {(m.yorumlar || []).length > 0 && (
                <div className="mt-2 space-y-1">
                  {m.yorumlar.slice(0, 4).map((y, i) => (
                    <div key={i} className="text-[11px] text-content flex items-start gap-1.5">
                      <span className="text-rose-500 shrink-0">{"★".repeat(y.yildiz)}{"☆".repeat(5 - y.yildiz)}</span>
                      <span className="text-subtle">{y.yorum}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-1.5 mt-2.5">
                <button onClick={() => karar(m.id, "korundu")} disabled={islenen === m.id}
                  className="inline-flex items-center gap-1 text-xs bg-app border border-line rounded-lg px-2.5 py-1.5 hover:border-emerald-400">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />Koru
                </button>
                <button onClick={() => karar(m.id, "duzeltildi")} disabled={islenen === m.id}
                  className="inline-flex items-center gap-1 text-xs bg-app border border-line rounded-lg px-2.5 py-1.5 hover:border-indigo-400">
                  <PencilLine className="h-3.5 w-3.5 text-indigo-600" />Düzeltildi
                </button>
                <button onClick={() => karar(m.id, "cikarildi")} disabled={islenen === m.id}
                  className="inline-flex items-center gap-1 text-xs bg-rose-600 text-white rounded-lg px-2.5 py-1.5 disabled:opacity-50">
                  <Trash2 className="h-3.5 w-3.5" />Havuzdan Çıkar
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
