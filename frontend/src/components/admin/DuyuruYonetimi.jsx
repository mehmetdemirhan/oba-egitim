import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { Sparkles, Plus, Trash2 } from "lucide-react";

/**
 * DuyuruYonetimi — admin "Yeni Ne Var" yönetimi: ekle/düzenle/arşivle + rol hedefleme.
 * Props: apiBase.
 */
const ROL_ETIKET = { herkes: "Herkes", ogretmen: "Öğretmen", admin: "Yönetici" };
const ROLLER = ["herkes", "ogretmen", "admin"];
const inp = "border border-line rounded-lg px-3 py-2 text-sm bg-surface";

function RolSecici({ roller, onChange }) {
  const toggle = (r) => {
    if (r === "herkes") { onChange(["herkes"]); return; }
    let y = roller.filter((x) => x !== "herkes");
    y = y.includes(r) ? y.filter((x) => x !== r) : [...y, r];
    onChange(y.length ? y : ["herkes"]);
  };
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {ROLLER.map((r) => (
        <label key={r} className="inline-flex items-center gap-1 text-xs cursor-pointer">
          <input type="checkbox" checked={roller.includes(r)} onChange={() => toggle(r)} />{ROL_ETIKET[r]}
        </label>
      ))}
    </div>
  );
}

export default function DuyuruYonetimi({ apiBase }) {
  const { toast } = useToast();
  const [duyurular, setDuyurular] = useState([]);
  const [form, setForm] = useState({ baslik: "", icerik: "", roller: ["herkes"], tarih: "" });
  const [kaydediliyor, setKaydediliyor] = useState(false);

  const yukle = useCallback(async () => {
    try {
      const r = await axios.get(`${apiBase}/duyurular/yonetim`);
      setDuyurular(r.data?.duyurular || []);
    } catch { toast({ title: "Duyurular yüklenemedi", variant: "destructive" }); }
  }, [apiBase, toast]);

  useEffect(() => { yukle(); }, [yukle]);

  const ekle = async () => {
    if (!form.baslik.trim() && !form.icerik.trim()) { toast({ title: "Başlık veya içerik gerekli", variant: "destructive" }); return; }
    setKaydediliyor(true);
    try {
      await axios.post(`${apiBase}/duyurular`, form);
      setForm({ baslik: "", icerik: "", roller: ["herkes"], tarih: "" });
      toast({ title: "Duyuru eklendi" }); yukle();
    } catch (e) { toast({ title: "Eklenemedi", description: e?.response?.data?.detail, variant: "destructive" }); }
    setKaydediliyor(false);
  };

  const guncelle = async (id, alan) => { try { await axios.put(`${apiBase}/duyurular/${id}`, alan); yukle(); } catch { toast({ title: "Güncellenemedi", variant: "destructive" }); } };
  const sil = async (id) => { if (!window.confirm("Duyuru silinsin mi?")) return; try { await axios.delete(`${apiBase}/duyurular/${id}`); toast({ title: "Silindi" }); yukle(); } catch { toast({ title: "Silinemedi", variant: "destructive" }); } };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-bold text-content inline-flex items-center gap-2"><Sparkles className="h-5 w-5 text-indigo-500" />Yeni Ne Var — Duyurular</h3>

      {/* Ekleme */}
      <div className="bg-surface border border-line rounded-2xl shadow-sm p-4 space-y-2">
        <input type="text" value={form.baslik} onChange={(e) => setForm({ ...form, baslik: e.target.value })} placeholder="Başlık" className={`${inp} w-full`} />
        <textarea value={form.icerik} onChange={(e) => setForm({ ...form, icerik: e.target.value })} rows={2} placeholder="Kısa açıklama (1-2 cümle)" className={`${inp} w-full`} />
        <div className="flex items-center gap-3 flex-wrap">
          <input type="date" value={form.tarih} onChange={(e) => setForm({ ...form, tarih: e.target.value })} className={inp} />
          <RolSecici roller={form.roller} onChange={(r) => setForm({ ...form, roller: r })} />
          <button onClick={ekle} disabled={kaydediliyor} className="inline-flex items-center gap-1 bg-indigo-600 text-white rounded-lg px-3 py-2 text-sm hover:bg-indigo-700 disabled:opacity-50 ml-auto"><Plus className="h-4 w-4" />Ekle</button>
        </div>
      </div>

      {/* Liste */}
      <div className="space-y-2">
        {duyurular.map((d) => (
          <div key={d.id} className={`bg-surface border rounded-2xl shadow-sm p-3 ${d.aktif ? "border-line" : "border-line/50 opacity-60"}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-content">{d.baslik || "—"}</div>
                {d.icerik && <div className="text-xs text-subtle mt-0.5">{d.icerik}</div>}
                <div className="flex items-center gap-2 mt-1 text-[11px] text-subtle flex-wrap">
                  <span className="tabular-nums">{d.tarih}</span>
                  <span>{(d.roller || []).map((r) => ROL_ETIKET[r] || r).join(", ")}</span>
                  {!d.aktif && <span className="text-amber-600">arşivli</span>}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button onClick={() => guncelle(d.id, { aktif: !d.aktif })} className="px-2 py-1 border border-line rounded hover:bg-app text-xs">{d.aktif ? "Arşivle" : "Yayına al"}</button>
                <button onClick={() => sil(d.id)} className="px-1.5 py-1 border border-red-200 text-red-600 rounded hover:bg-red-50"><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
