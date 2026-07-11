import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { Plus, Trash2, Edit2, GraduationCap, BookOpen, Check, X } from "lucide-react";

/**
 * EgitimTurleriYonetimi — yönetici: öğrencinin alacağı eğitim türlerini yönet.
 * Ekle / düzenle / pasife al. Kategori: genel (okuma becerileri) | branş (Matematik vb.).
 * Pasif türler yeni seçimde çıkmaz, eski kayıtlarda görünür kalır.
 * Props: apiBase.
 */
export default function EgitimTurleriYonetimi({ apiBase }) {
  const { toast } = useToast();
  const [turler, setTurler] = useState([]);
  const [yeniAd, setYeniAd] = useState("");
  const [yeniKat, setYeniKat] = useState("genel");
  const [duzenle, setDuzenle] = useState(null); // {id, ad}

  const yukle = useCallback(async () => {
    try {
      const r = await axios.get(`${apiBase}/egitim-turleri?dahil_pasif=true`);
      setTurler(r.data?.turler || []);
    } catch {
      toast({ title: "Eğitim türleri yüklenemedi", variant: "destructive" });
    }
  }, [apiBase, toast]);

  useEffect(() => { yukle(); }, [yukle]);

  const ekle = async () => {
    if (yeniAd.trim().length < 2) { toast({ title: "Ad çok kısa", variant: "destructive" }); return; }
    try {
      await axios.post(`${apiBase}/egitim-turleri`, { ad: yeniAd.trim(), kategori: yeniKat });
      setYeniAd("");
      toast({ title: "Eğitim türü eklendi" });
      yukle();
    } catch (e) {
      toast({ title: "Eklenemedi", description: e?.response?.data?.detail || "", variant: "destructive" });
    }
  };

  const kaydet = async (id, guncelle) => {
    try {
      await axios.put(`${apiBase}/egitim-turleri/${id}`, guncelle);
      setDuzenle(null);
      yukle();
    } catch {
      toast({ title: "Güncellenemedi", variant: "destructive" });
    }
  };

  const pasifeAl = async (id) => {
    try { await axios.delete(`${apiBase}/egitim-turleri/${id}`); yukle(); }
    catch { toast({ title: "İşlem başarısız", variant: "destructive" }); }
  };

  const KAT = { genel: { ad: "Genel", Ikon: BookOpen }, brans: { ad: "Branş Dersi", Ikon: GraduationCap } };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-bold text-content">Eğitim Türleri</h3>
        <p className="text-sm text-subtle">Öğrenci eklerken/düzenlerken seçilen eğitim türleri. Pasife alınan tür yeni seçimlerde görünmez, eski kayıtlarda korunur.</p>
      </div>

      {/* Ekleme */}
      <div className="bg-surface border border-line rounded-2xl p-4 shadow-sm flex flex-wrap items-end gap-2">
        <div className="flex-1 min-w-[180px]">
          <label className="text-xs text-subtle">Yeni eğitim türü</label>
          <input value={yeniAd} onChange={(e) => setYeniAd(e.target.value)} placeholder="örn. Matematik"
            className="w-full border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
        </div>
        <div>
          <label className="text-xs text-subtle">Kategori</label>
          <select value={yeniKat} onChange={(e) => setYeniKat(e.target.value)}
            className="block border border-line rounded-lg px-2 py-2 text-sm bg-surface">
            <option value="genel">Genel</option>
            <option value="brans">Branş Dersi</option>
          </select>
        </div>
        <button onClick={ekle} className="inline-flex items-center gap-1 bg-primary hover:bg-primary-hover text-white text-sm px-4 py-2 rounded-xl">
          <Plus className="h-4 w-4" />Ekle
        </button>
      </div>

      {/* Liste */}
      <div className="bg-surface border border-line rounded-2xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-subtle border-b border-line bg-app">
              <th className="px-3 py-2">Ad</th><th className="px-3 py-2 w-32">Kategori</th>
              <th className="px-3 py-2 w-24">Durum</th><th className="px-3 py-2 w-24"></th>
            </tr>
          </thead>
          <tbody>
            {turler.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-subtle">Henüz eğitim türü yok.</td></tr>}
            {turler.map((t) => {
              const k = KAT[t.kategori] || KAT.genel;
              const pasif = t.durum === "pasif";
              return (
                <tr key={t.id} className={`border-b border-line last:border-0 ${pasif ? "opacity-50" : ""}`}>
                  <td className="px-3 py-2 text-content">
                    {duzenle?.id === t.id ? (
                      <input value={duzenle.ad} onChange={(e) => setDuzenle({ ...duzenle, ad: e.target.value })}
                        className="border border-primary rounded px-2 py-1 text-sm w-full" autoFocus />
                    ) : t.ad}
                  </td>
                  <td className="px-3 py-2 text-subtle"><span className="inline-flex items-center gap-1"><k.Ikon className="h-3.5 w-3.5" />{k.ad}</span></td>
                  <td className="px-3 py-2">
                    <span className={`text-[11px] px-2 py-0.5 rounded-full ${pasif ? "bg-gray-100 text-gray-500" : "bg-green-100 text-green-700"}`}>{pasif ? "Pasif" : "Aktif"}</span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      {duzenle?.id === t.id ? (
                        <>
                          <button onClick={() => kaydet(t.id, { ad: duzenle.ad })} className="text-emerald-600 hover:text-emerald-700" aria-label="Kaydet"><Check className="h-4 w-4" /></button>
                          <button onClick={() => setDuzenle(null)} className="text-slate-400 hover:text-slate-600" aria-label="İptal"><X className="h-4 w-4" /></button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => setDuzenle({ id: t.id, ad: t.ad })} className="text-slate-400 hover:text-primary" aria-label="Düzenle"><Edit2 className="h-4 w-4" /></button>
                          {pasif ? (
                            <button onClick={() => kaydet(t.id, { durum: "aktif" })} className="text-emerald-600 hover:text-emerald-700 text-xs">Aktifle</button>
                          ) : (
                            <button onClick={() => pasifeAl(t.id)} className="text-red-400 hover:text-red-600" aria-label="Pasife al" title="Pasife al"><Trash2 className="h-4 w-4" /></button>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
