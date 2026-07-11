import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { Settings, ChevronDown, ChevronRight, Receipt, Save } from "lucide-react";
import KurUcretleriYonetimi from "./KurUcretleriYonetimi";

/**
 * MuhasebeAyarlari — muhasebeyle ilgili ayarların TEK yeri. Admin Muhasebe sekmesi
 * ve muhasebe (accountant) panelinde AYNI bileşen paylaşılır (kopya yok).
 * İçindekiler: Vergi Oranı + Kur Ücretleri (genel + eğitim türü bazlı).
 * Tam-yetki kararımıza uygun: admin + accountant düzenleyebilir (backend
 * /muhasebe/ayarlar/* uçları bu iki role açıktır). Props: apiBase.
 */
function VergiOraniEditor({ apiBase }) {
  const { toast } = useToast();
  const [oran, setOran] = useState("");
  const [kaydediyor, setKaydediyor] = useState(false);

  const yukle = useCallback(async () => {
    try {
      const r = await axios.get(`${apiBase}/ayarlar/vergi_ayarlari`);
      const v = r.data?.degerler?.vergi_orani;
      setOran(v != null ? String(v) : "15");
    } catch {
      setOran("15");
    }
  }, [apiBase]);

  useEffect(() => { yukle(); }, [yukle]);

  const kaydet = async () => {
    const n = parseFloat(oran);
    if (isNaN(n) || n < 0 || n > 100) { toast({ title: "Vergi oranı 0-100 arası olmalı", variant: "destructive" }); return; }
    setKaydediyor(true);
    try {
      await axios.put(`${apiBase}/muhasebe/ayarlar/vergi`, { vergi_orani: n });
      toast({ title: "Vergi oranı kaydedildi", description: `%${n} olarak güncellendi.` });
    } catch (e) {
      toast({ title: "Kaydedilemedi", description: e?.response?.data?.detail || "", variant: "destructive" });
    } finally {
      setKaydediyor(false);
    }
  };

  return (
    <div className="space-y-2">
      <h3 className="text-lg font-bold text-content flex items-center gap-2"><Receipt className="h-5 w-5" />Vergi Oranı</h3>
      <p className="text-sm text-subtle">Öğrenci tahsilatlarından kesilen devlet vergisi (yüzde). Tahsilat anındaki oran o kayda sabitlenir; sonradan değişse eski tahsilatlar kendi oranını korur.</p>
      <div className="bg-surface border border-line rounded-2xl p-4 shadow-sm flex items-end gap-2 flex-wrap">
        <div className="max-w-[160px]">
          <label className="text-xs text-subtle">Vergi oranı (%)</label>
          <input type="number" min="0" max="100" step="0.5" value={oran} onChange={(e) => setOran(e.target.value)}
            className="w-full border border-line rounded-lg px-3 py-2 text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-primary" />
        </div>
        <button onClick={kaydet} disabled={kaydediyor}
          className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white text-sm px-4 py-2 rounded-xl disabled:opacity-50">
          <Save className="h-4 w-4" />{kaydediyor ? "Kaydediliyor…" : "Kaydet"}
        </button>
      </div>
    </div>
  );
}

export default function MuhasebeAyarlari({ apiBase }) {
  const [acik, setAcik] = useState(false);
  return (
    <div className="border border-line rounded-2xl bg-surface shadow-sm overflow-hidden">
      <button onClick={() => setAcik(!acik)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-app transition-colors">
        <span className="font-bold text-content flex items-center gap-2"><Settings className="h-5 w-5" />Muhasebe Ayarları</span>
        {acik ? <ChevronDown className="h-5 w-5 text-subtle" /> : <ChevronRight className="h-5 w-5 text-subtle" />}
      </button>
      {acik && (
        <div className="border-t border-line p-4 space-y-8">
          <VergiOraniEditor apiBase={apiBase} />
          <KurUcretleriYonetimi apiBase={apiBase} />
        </div>
      )}
    </div>
  );
}
