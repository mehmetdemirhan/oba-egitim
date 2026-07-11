import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { ScrollText, RefreshCw } from "lucide-react";

/**
 * IslemKayitlari — yönetici salt-okunur işlem/audit izi (db.islem_log).
 * Öğrenci düzenleme/kaldırma, muhasebe alan değişiklikleri, eğitim türü vb. kimin
 * ne zaman hangi alanı eski→yeni yaptığı. Modüle göre filtrelenir. Props: apiBase.
 */
const MODUL_ETIKET = { muhasebe: "Muhasebe", ogrenci: "Öğrenci", egitim_turu: "Eğitim Türü" };
const ISLEM_ETIKET = { duzenle: "Düzenledi", kaldir: "Pasife aldı", sil_kalici: "Kalıcı sildi", geri_al: "Geri aldı", kur_ucreti_ekle: "Kur ücreti ekledi", olustur: "Oluşturdu" };

export default function IslemKayitlari({ apiBase }) {
  const { toast } = useToast();
  const [kayitlar, setKayitlar] = useState([]);
  const [modul, setModul] = useState("");
  const [yukleniyor, setYukleniyor] = useState(false);

  const yukle = useCallback(async () => {
    setYukleniyor(true);
    try {
      const r = await axios.get(`${apiBase}/islem-log`, { params: { modul: modul || undefined, limit: 300 } });
      setKayitlar(r.data?.kayitlar || []);
    } catch {
      toast({ title: "İşlem kayıtları yüklenemedi", variant: "destructive" });
    } finally {
      setYukleniyor(false);
    }
  }, [apiBase, modul, toast]);

  useEffect(() => { yukle(); }, [yukle]);

  const tarihStr = (t) => { try { return new Date(t).toLocaleString("tr-TR"); } catch { return t; } };
  const deger = (v) => (v === null || v === undefined || v === "") ? "—" : String(v);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-lg font-bold text-content flex items-center gap-2"><ScrollText className="h-5 w-5" />İşlem Kayıtları</h3>
          <p className="text-sm text-subtle">Kim, ne zaman, hangi kaydı, hangi alanı değiştirdi (salt-okunur denetim izi).</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={modul} onChange={(e) => setModul(e.target.value)} className="border border-line rounded-lg px-2 py-1.5 text-sm bg-surface">
            <option value="">Tüm modüller</option>
            <option value="ogrenci">Öğrenci</option>
            <option value="muhasebe">Muhasebe</option>
            <option value="egitim_turu">Eğitim Türü</option>
          </select>
          <button onClick={yukle} className="inline-flex items-center gap-1 border border-line rounded-lg px-3 py-1.5 text-sm hover:bg-app"><RefreshCw className="h-4 w-4" />Yenile</button>
        </div>
      </div>

      <div className="bg-surface border border-line rounded-2xl shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-subtle border-b border-line bg-app">
              <th className="px-3 py-2 whitespace-nowrap">Tarih</th>
              <th className="px-3 py-2">Kullanıcı</th>
              <th className="px-3 py-2">Modül</th>
              <th className="px-3 py-2">İşlem</th>
              <th className="px-3 py-2">Alan</th>
              <th className="px-3 py-2">Eski → Yeni</th>
            </tr>
          </thead>
          <tbody>
            {yukleniyor && <tr><td colSpan={6} className="px-3 py-6 text-center text-subtle">Yükleniyor…</td></tr>}
            {!yukleniyor && kayitlar.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-subtle">Kayıt yok.</td></tr>}
            {!yukleniyor && kayitlar.map((k) => (
              <tr key={k.id} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-subtle whitespace-nowrap tabular-nums">{tarihStr(k.tarih)}</td>
                <td className="px-3 py-2 text-content">{k.kullanici_ad || k.kullanici_id?.slice(0, 8) || "—"}<span className="text-[10px] text-subtle ml-1">{k.kullanici_rol}</span></td>
                <td className="px-3 py-2 text-subtle">{MODUL_ETIKET[k.modul] || k.modul}</td>
                <td className="px-3 py-2">{ISLEM_ETIKET[k.islem] || k.islem}</td>
                <td className="px-3 py-2 text-subtle">{k.alan || "—"}</td>
                <td className="px-3 py-2 text-xs"><span className="text-red-500">{deger(k.eski)}</span> <span className="text-subtle">→</span> <span className="text-emerald-600">{deger(k.yeni)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
