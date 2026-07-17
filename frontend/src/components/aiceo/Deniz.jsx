import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { ShieldCheck, Play, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import BilgiIkonu from "../BilgiIkonu";
import { PersonaBalon } from "./Personalar";

const ONEM_RENK = { kritik: "border-red-300 bg-red-50 text-red-700", orta: "border-amber-300 bg-amber-50 text-amber-700", dusuk: "border-slate-300 bg-slate-50 text-slate-600" };
const DURUM_ET = { yeni: "Yeni", admin_gecerli: "Geçerli", admin_gecersiz: "Geçersiz", cozuldu: "Çözüldü" };

/**
 * Deniz — Denetçi AI (yalnız admin). Ayda'nın çıktılarını bağımsız denetler.
 * Deterministik kontroller + AI denetim turu + admin onaylı iyileştirme notu + karne.
 * Sayfa açılışında AI çağrısı YOK (kayıtlı denetim gösterilir; "Denetle" ile tetiklenir).
 */
export default function Deniz({ apiBase }) {
  const [denetim, setDenetim] = useState(null);
  const [bulgular, setBulgular] = useState([]);
  const [karne, setKarne] = useState(null);
  const [notlar, setNotlar] = useState([]);
  const [calisiyor, setCalisiyor] = useState(false);
  const api = (p) => `${apiBase}${p}`;

  const yukle = useCallback(async () => {
    const [s, k, n] = await Promise.all([
      axios.get(api("/ai/ceo/deniz/son")).catch(() => null),
      axios.get(api("/ai/ceo/deniz/karne")).catch(() => null),
      axios.get(api("/ai/ceo/deniz/notlar")).catch(() => null),
    ]);
    if (s) { setDenetim(s.data.denetim); setBulgular(s.data.bulgular || []); }
    if (k) setKarne(k.data.karne);
    if (n) setNotlar(n.data.notlar || []);
  }, [apiBase]);

  useEffect(() => { yukle(); }, [yukle]);

  const denetle = async () => {
    setCalisiyor(true);
    try { await axios.post(api("/ai/ceo/deniz/denetle")); await yukle(); }
    finally { setCalisiyor(false); }
  };
  const bulguDurum = async (b, durum) => { await axios.put(api(`/ai/ceo/deniz/bulgu/${b.id}/durum`), { durum }); await yukle(); };
  const notOnayla = async (id) => { await axios.post(api(`/ai/ceo/deniz/not/${id}/onayla`)); await yukle(); };
  const notEkle = async () => {
    const metin = denetim?.iyilestirme_plani;
    if (!metin) return;
    await axios.post(api("/ai/ceo/deniz/not"), { metin }); await yukle();
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          <div className="flex-1"><PersonaBalon persona="deniz" mesaj={denetim?.ozet || "Ayda'nın çıktılarını bağımsız denetliyorum. 'Denetle' ile turu başlat."} /></div>
          <button onClick={denetle} disabled={calisiyor} className="inline-flex items-center gap-1.5 bg-slate-700 hover:bg-slate-800 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-xl">
            {calisiyor ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}{calisiyor ? "Denetleniyor…" : "Denetle"}
          </button>
        </div>
      </div>

      {/* Karne */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-bold text-content text-sm flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-slate-600" />Deniz'in Karnesi</h3>
          <BilgiIkonu nasil="Bulgu doğruluğu = admin'in geçerli bulduğu / değerlendirilen bulgu; yakalama değeri = çözülen kritik / toplam kritik; kaçırma = admin'in 'Deniz kaçırdı' işaretleri. Tümü deterministik." ne="Denetçinin gerçekten işe yarayıp yaramadığını (kovma kararı dahil) sayıyla görmek için." />
        </div>
        {karne ? (
          <>
            <div className="text-sm text-content mb-2">{karne.ozet}</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
              {[["Bulgu Doğruluğu", karne.bulgu_dogrulugu, "%"], ["Kritik Yakalama", karne.yakalama_degeri, "%"], ["Toplam Bulgu", karne.toplam_bulgu, ""], ["Kaçırma", karne.kacirilan_bildirilen, ""]].map(([l, v, u], i) => (
                <div key={i} className="rounded-lg bg-app border border-line p-2"><div className="text-lg font-bold tabular-nums">{v == null ? "—" : `${u === "%" ? "%" : ""}${v}`}</div><div className="text-[10px] text-subtle">{l}</div></div>
              ))}
            </div>
          </>
        ) : <div className="text-sm text-subtle">Karne verisi yok.</div>}
      </div>

      {/* Bulgular */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <h3 className="font-bold text-content text-sm mb-2">Denetim Bulguları</h3>
        {bulgular.length === 0 ? <div className="text-sm text-subtle">Bulgu yok — "Denetle" ile tur başlat.</div> : (
          <div className="space-y-2">
            {bulgular.map(b => (
              <div key={b.id} className={`rounded-lg border p-2 ${ONEM_RENK[b.onem] || "border-line"}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-content">{b.ozet}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/60 border border-current">{b.onem}</span>
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[10px] text-subtle">{b.tur} · {DURUM_ET[b.durum] || b.durum} · {b.kaynak}</span>
                  {b.durum === "yeni" && (
                    <span className="ml-auto flex gap-2">
                      <button onClick={() => bulguDurum(b, "admin_gecerli")} className="inline-flex items-center gap-0.5 text-[11px] text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />Geçerli</button>
                      <button onClick={() => bulguDurum(b, "admin_gecersiz")} className="inline-flex items-center gap-0.5 text-[11px] text-red-600"><XCircle className="h-3.5 w-3.5" />Geçersiz</button>
                    </span>
                  )}
                  {b.durum === "admin_gecerli" && <button onClick={() => bulguDurum(b, "cozuldu")} className="ml-auto text-[11px] text-indigo-600">Çözüldü işaretle</button>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* İyileştirme planı → onaylı not (guard) */}
      {(denetim?.iyilestirme_plani || notlar.length > 0) && (
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-1">
            <h3 className="font-bold text-content text-sm">İyileştirme Planı → Ayda'ya Not</h3>
            <BilgiIkonu nasil="Deniz'in iyileştirme planı yalnız admin ONAYIYLA sonraki Ayda analizinin promptuna 'denetim notu' olarak girer." ne="Ayda'yı otomatik değil, kontrollü biçimde iyileştirmek için (oto self-modifikasyon yok)." />
          </div>
          {denetim?.iyilestirme_plani && (
            <div className="text-sm text-content mb-2">{denetim.iyilestirme_plani}
              <button onClick={notEkle} className="ml-2 text-[11px] text-indigo-600 hover:underline">Taslak nota ekle</button>
            </div>
          )}
          {notlar.map(n => (
            <div key={n.id} className="rounded-lg border border-line p-2 text-sm flex items-center justify-between gap-2">
              <span className="flex-1">{n.metin}</span>
              {n.onayli ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">Onaylı</span>
                : <button onClick={() => notOnayla(n.id)} className="text-[11px] text-emerald-700 font-medium">Onayla</button>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
