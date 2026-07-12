import React, { useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { Wrench, Save } from "lucide-react";

/**
 * BakimModu — YALNIZ admin. Bakım modunu aç/kapat + karşılama mesajı + tahmini bitiş.
 * DB tabanlı (sistem_ayarlari) — deploy'suz aç/kapa. Props: apiBase.
 */
export default function BakimModu({ apiBase }) {
  const { toast } = useToast();
  const [aktif, setAktif] = useState(false);
  const [mesaj, setMesaj] = useState("");
  const [tahminiBitis, setTahminiBitis] = useState("");
  const [varsayilan, setVarsayilan] = useState("");
  const [kaydediliyor, setKaydediliyor] = useState(false);

  useEffect(() => {
    axios.get(`${apiBase}/sistem/bakim`).then((r) => {
      const d = r.data || {};
      setAktif(!!d.aktif);
      setMesaj(d.mesaj || "");
      setTahminiBitis(d.tahmini_bitis || "");
      setVarsayilan(d.varsayilan_mesaj || "");
    }).catch(() => {});
  }, [apiBase]);

  const kaydet = async (yeniAktif) => {
    setKaydediliyor(true);
    try {
      const gonderilecekAktif = yeniAktif !== undefined ? yeniAktif : aktif;
      await axios.put(`${apiBase}/sistem/bakim`, {
        aktif: gonderilecekAktif,
        mesaj: (mesaj || "").trim() || varsayilan,
        tahmini_bitis: (tahminiBitis || "").trim() || null,
      });
      setAktif(gonderilecekAktif);
      toast({ title: gonderilecekAktif ? "Bakım modu AÇILDI" : "Bakım modu kapatıldı" });
    } catch (e) {
      toast({ title: "Kaydedilemedi", description: e?.response?.data?.detail, variant: "destructive" });
    } finally {
      setKaydediliyor(false);
    }
  };

  return (
    <div className="bg-surface border border-line rounded-2xl shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-lg font-bold text-content inline-flex items-center gap-2">
          <Wrench className="h-5 w-5" />Bakım Modu
        </h3>
        <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${aktif ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
          {aktif ? "● BAKIM AÇIK" : "● Sistem Aktif"}
        </span>
      </div>
      <p className="text-sm text-subtle">
        Bakım açıkken <b>admin dışındaki tüm roller</b> giriş yapamaz ve nazik bir bakım
        ekranı görür. Admin her zaman girebilir. Ayar DB'de tutulur — deploy gerekmez.
      </p>

      <div className="space-y-1">
        <label className="text-sm font-medium text-content">Karşılama mesajı</label>
        <textarea value={mesaj} onChange={(e) => setMesaj(e.target.value)} rows={3}
                  placeholder={varsayilan}
                  className="w-full border border-line rounded-lg px-3 py-2 text-sm bg-surface" />
        <p className="text-[11px] text-subtle">Boş bırakılırsa nazik varsayılan metin kullanılır.</p>
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium text-content">Tahmini bitiş (opsiyonel)</label>
        <input type="text" value={tahminiBitis} onChange={(e) => setTahminiBitis(e.target.value)}
               placeholder="örn. 18:00 / bugün akşam"
               className="w-full sm:w-64 border border-line rounded-lg px-3 py-2 text-sm bg-surface" />
      </div>

      <div className="flex items-center gap-2 flex-wrap pt-1">
        {!aktif ? (
          <button disabled={kaydediliyor} onClick={() => kaydet(true)}
                  className="inline-flex items-center gap-1 bg-amber-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-amber-700 disabled:opacity-50">
            <Wrench className="h-4 w-4" />Bakım modunu aç
          </button>
        ) : (
          <button disabled={kaydediliyor} onClick={() => kaydet(false)}
                  className="inline-flex items-center gap-1 bg-emerald-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-emerald-700 disabled:opacity-50">
            Bakımı kapat
          </button>
        )}
        <button disabled={kaydediliyor} onClick={() => kaydet()}
                className="inline-flex items-center gap-1 border border-line rounded-lg px-4 py-2 text-sm hover:bg-app disabled:opacity-50">
          <Save className="h-4 w-4" />Mesajı kaydet
        </button>
      </div>
    </div>
  );
}
