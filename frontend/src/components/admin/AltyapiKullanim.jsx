import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Cloud, Server, RefreshCw, AlertTriangle } from "lucide-react";

/**
 * AltyapiKullanim — Vercel / Render altyapı bilgisi (best-effort).
 * KRİTİK: yalnızca API'nin döndürdüğü gerçek veri; token yoksa "yapılandırılmadı",
 * API farklıysa hata + bulgu. Tahmini/uydurma değer GÖSTERİLMEZ. Props: apiBase.
 */
const msTarih = (ms) => { try { return ms ? new Date(ms).toLocaleDateString("tr-TR") : "—"; } catch { return "—"; } };
const isoTarih = (s) => { try { return s ? new Date(s).toLocaleDateString("tr-TR") : "—"; } catch { return "—"; } };

function DurumRozeti({ durum }) {
  const harita = {
    ok: { t: "Bağlı", c: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    yapilandirilmadi: { t: "Yapılandırılmadı", c: "bg-gray-100 text-gray-500 border-gray-200" },
    hata: { t: "Hata", c: "bg-red-50 text-red-700 border-red-200" },
  };
  const d = harita[durum] || harita.hata;
  return <span className={`text-xs px-2 py-0.5 rounded-full border ${d.c}`}>{d.t}</span>;
}

function Panel({ ikon, baslik, veri }) {
  return (
    <div className="bg-surface border border-line rounded-2xl shadow-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-bold text-content inline-flex items-center gap-2">{ikon}{baslik}</h4>
        <DurumRozeti durum={veri?.durum} />
      </div>

      {veri?.durum === "yapilandirilmadi" && (
        <p className="text-xs text-subtle">{veri.aciklama} Token eklenince gerçek veri burada görünür.</p>
      )}

      {veri?.durum === "hata" && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg p-2.5 space-y-1">
          <div className="inline-flex items-center gap-1 font-semibold"><AlertTriangle className="h-3.5 w-3.5" />API erişimi beklenenden farklı</div>
          <div>{veri.aciklama}</div>
          {veri.govde && <pre className="whitespace-pre-wrap text-[10px] text-red-500/80 mt-1">{veri.govde}</pre>}
        </div>
      )}

      {veri?.durum === "ok" && (
        <div className="space-y-2 text-xs">
          {veri.hesap && <div className="flex justify-between"><span className="text-subtle">Hesap</span><span className="font-medium text-content">{veri.hesap}</span></div>}
          {veri.plan && <div className="flex justify-between"><span className="text-subtle">Plan</span><span className="font-medium text-content">{veri.plan}</span></div>}
          {typeof veri.proje_sayisi === "number" && <div className="flex justify-between"><span className="text-subtle">Proje sayısı</span><span className="font-medium text-content">{veri.proje_sayisi}</span></div>}
          {typeof veri.servis_sayisi === "number" && <div className="flex justify-between"><span className="text-subtle">Servis sayısı</span><span className="font-medium text-content">{veri.servis_sayisi}</span></div>}

          {Array.isArray(veri.projeler) && veri.projeler.length > 0 && (
            <div className="pt-1 border-t border-line">
              {veri.projeler.map((p, i) => (
                <div key={i} className="flex justify-between py-0.5"><span className="text-content truncate">{p.ad}</span><span className="text-subtle">{p.son_deploy_ms ? msTarih(p.son_deploy_ms) : (p.cerceve || "—")}</span></div>
              ))}
            </div>
          )}
          {Array.isArray(veri.servisler) && veri.servisler.length > 0 && (
            <div className="pt-1 border-t border-line">
              {veri.servisler.map((s, i) => (
                <div key={i} className="flex justify-between py-0.5"><span className="text-content truncate">{s.ad} <span className="text-subtle">({s.tip})</span></span><span className="text-subtle">{isoTarih(s.son_guncelleme)}</span></div>
              ))}
            </div>
          )}
          {veri.uyari && <div className="text-amber-600">{veri.uyari}</div>}
          {veri.kota_notu && <p className="text-[11px] text-subtle pt-1 border-t border-line">{veri.kota_notu}</p>}
        </div>
      )}
    </div>
  );
}

export default function AltyapiKullanim({ apiBase }) {
  const [veri, setVeri] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);

  const yukle = useCallback(async () => {
    setYukleniyor(true);
    try {
      const r = await axios.get(`${apiBase}/altyapi/kullanim`);
      setVeri(r.data);
    } catch { setVeri({ vercel: { durum: "hata", aciklama: "İstek başarısız." }, render: { durum: "hata", aciklama: "İstek başarısız." } }); }
    setYukleniyor(false);
  }, [apiBase]);

  useEffect(() => { yukle(); }, [yukle]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-content inline-flex items-center gap-2"><Cloud className="h-5 w-5 text-sky-500" />Altyapı Kullanımı</h3>
        <button onClick={yukle} disabled={yukleniyor} className="inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg border border-line hover:bg-app disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${yukleniyor ? "animate-spin" : ""}`} />Yenile</button>
      </div>
      <p className="text-xs text-subtle">Vercel ve Render hesap/servis bilgisi. Değerler yalnızca ilgili API'nin döndürdüğü gerçek verilerdir; token yoksa "yapılandırılmadı", erişim farklıysa hata olarak gösterilir (tahmini değer üretilmez).</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel ikon={<Cloud className="h-4 w-4 text-black dark:text-white" />} baslik="Vercel (Frontend)" veri={veri?.vercel} />
        <Panel ikon={<Server className="h-4 w-4 text-emerald-600" />} baslik="Render (Backend)" veri={veri?.render} />
      </div>
    </div>
  );
}
