import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { Wallet, Save } from "lucide-react";

/**
 * KurUcretleriYonetimi — genel+eğitim türü bazlı ₺ ayar editörü. Varsayılan olarak
 * KUR ÜCRETLERİ'ni yönetir; props ile ÖĞRETMEN PAYI gibi aynı {genel, turler} şeklini
 * paylaşan başka ayarlar için de kullanılır (kopya YOK). Kaydetme muhasebe ucundan
 * (admin + accountant). Props: apiBase + opsiyonel baslik/aciklama/ayarTip/putYol/kolon.
 */
export default function KurUcretleriYonetimi({
  apiBase,
  baslik = "Kur Ücretleri",
  aciklama = "Kur geçişinde açılan yeni alacağın varsayılan tutarı. Eğitim türü için özel tutar girilmezse genel varsayılan kullanılır. Öğretmen bu tutarı görmez; muhasebe sonradan düzeltebilir.",
  ayarTip = "kur_ucretleri",
  putYol = "muhasebe/ayarlar/kur-ucretleri",
  kolonBaslik = "Kur Ücreti (₺)",
}) {
  const { toast } = useToast();
  const [genel, setGenel] = useState("");
  const [turUcret, setTurUcret] = useState({}); // {turAd: tutar}
  const [turler, setTurler] = useState([]);     // aktif eğitim türleri
  const [kaydediyor, setKaydediyor] = useState(false);

  const yukle = useCallback(async () => {
    try {
      const [a, t] = await Promise.all([
        axios.get(`${apiBase}/ayarlar/${ayarTip}`),
        axios.get(`${apiBase}/egitim-turleri`),
      ]);
      const d = a.data?.degerler || {};
      setGenel(d.genel != null ? String(d.genel) : "");
      setTurUcret(d.turler || {});
      setTurler((t.data?.turler || []).map((x) => x.ad));
    } catch {
      toast({ title: `${baslik} yüklenemedi`, variant: "destructive" });
    }
  }, [apiBase, ayarTip, baslik, toast]);

  useEffect(() => { yukle(); }, [yukle]);

  const kaydet = async () => {
    setKaydediyor(true);
    try {
      const turler_temiz = {};
      for (const [ad, v] of Object.entries(turUcret)) {
        const n = parseFloat(v);
        if (!isNaN(n) && n > 0) turler_temiz[ad] = Math.round(n * 100) / 100;
      }
      const degerler = { genel: parseFloat(genel) || 0, turler: turler_temiz };
      // Muhasebe ucu: admin + accountant düzenleyebilir (generic /ayarlar admin-only).
      await axios.put(`${apiBase}/${putYol}`, { degerler });
      toast({ title: `${baslik} kaydedildi` });
      yukle();
    } catch (e) {
      toast({ title: "Kaydedilemedi", description: e?.response?.data?.detail || "", variant: "destructive" });
    } finally {
      setKaydediyor(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-bold text-content flex items-center gap-2"><Wallet className="h-5 w-5" />{baslik}</h3>
        <p className="text-sm text-subtle">{aciklama}</p>
      </div>

      <div className="bg-surface border border-line rounded-2xl p-4 shadow-sm space-y-4">
        <div className="max-w-xs">
          <label className="text-xs text-subtle">Genel varsayılan (₺)</label>
          <input type="number" min="0" value={genel} onChange={(e) => setGenel(e.target.value)}
            placeholder="örn. 1000"
            className="w-full border border-line rounded-lg px-3 py-2 text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-primary" />
        </div>

        <div>
          <div className="text-xs text-subtle mb-2">Eğitim türü bazlı (opsiyonel — boş bırakılırsa genel geçerli)</div>
          <div className="border border-line rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-subtle border-b border-line bg-app">
                  <th className="px-3 py-2">Eğitim Türü</th><th className="px-3 py-2 w-40">{kolonBaslik}</th>
                </tr>
              </thead>
              <tbody>
                {turler.length === 0 && <tr><td colSpan={2} className="px-3 py-4 text-center text-subtle">Önce eğitim türü tanımlayın.</td></tr>}
                {turler.map((ad) => (
                  <tr key={ad} className="border-b border-line last:border-0">
                    <td className="px-3 py-2 text-content">{ad}</td>
                    <td className="px-3 py-1.5">
                      <input type="number" min="0" value={turUcret[ad] ?? ""}
                        onChange={(e) => setTurUcret({ ...turUcret, [ad]: e.target.value })}
                        placeholder="genel"
                        className="w-32 border border-line rounded-lg px-2 py-1 text-sm tabular-nums text-right focus:outline-none focus:ring-2 focus:ring-primary" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex justify-end">
          <button onClick={kaydet} disabled={kaydediyor}
            className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white text-sm px-4 py-2 rounded-xl disabled:opacity-50">
            <Save className="h-4 w-4" />{kaydediyor ? "Kaydediliyor…" : "Kaydet"}
          </button>
        </div>
      </div>
    </div>
  );
}
