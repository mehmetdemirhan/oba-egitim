import React, { useEffect, useState } from "react";
import axios from "axios";
import { Bell, SlidersHorizontal } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { useToast } from "../hooks/use-toast";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const KATEGORILER = [
  { k: "ogrenci", ad: "Öğrenci", aciklama: "Risk, rozet, streak, görev, lig…" },
  { k: "ogretmen", ad: "Öğretmen", aciklama: "Görev tamamlama, haftalık özet…" },
  { k: "veli", ad: "Veli", aciklama: "Rapor, değerlendirme, mesaj, ders değişikliği…" },
];

/** Kategori bazlı bildirim aç/kapa kartı (telefon bildirim ayarları gibi). */
export function BildirimTercihleri() {
  const { toast } = useToast();
  const [t, setT] = useState({ ogrenci: true, ogretmen: true, veli: true });

  useEffect(() => {
    axios.get(`${API}/bildirimler/tercihler`).then((r) => setT({ ...t, ...r.data })).catch(() => {});
    // eslint-disable-next-line
  }, []);

  const degistir = async (k) => {
    const yeni = { ...t, [k]: !t[k] };
    setT(yeni);
    try { await axios.put(`${API}/bildirimler/tercihler`, yeni); }
    catch { toast({ title: "Kaydedilemedi", variant: "destructive" }); }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-semibold text-gray-800"><Bell className="h-4 w-4" /> Bildirim Tercihleri</div>
      <p className="text-[11px] text-gray-500">Kapalı kategorinin bildirimleri panelde ve push'ta gösterilmez.</p>
      {KATEGORILER.map(({ k, ad, aciklama }) => (
        <label key={k} className="flex items-center justify-between gap-3 p-2 rounded-lg bg-gray-50 cursor-pointer">
          <span>
            <span className="text-sm font-medium text-gray-800">{ad}</span>
            <span className="block text-[10px] text-gray-400">{aciklama}</span>
          </span>
          <button type="button" onClick={() => degistir(k)}
            className={`relative w-10 h-6 rounded-full transition-colors ${t[k] ? "bg-green-500" : "bg-gray-300"}`}>
            <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${t[k] ? "translate-x-4" : ""}`} />
          </button>
        </label>
      ))}
    </div>
  );
}

/** Header'a konulabilen ayar (kaydırıcı) butonu — dialog içinde tercihleri açar. */
export function BildirimTercihleriButton() {
  const [acik, setAcik] = useState(false);
  return (
    <>
      <button onClick={() => setAcik(true)} title="Bildirim Ayarları"
        className="inline-flex items-center justify-center h-9 w-9 rounded-md border border-gray-200 hover:bg-gray-50 text-gray-600">
        <SlidersHorizontal className="h-4 w-4" />
      </button>
      <Dialog open={acik} onOpenChange={setAcik}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Bildirim Ayarları</DialogTitle></DialogHeader>
          <BildirimTercihleri />
        </DialogContent>
      </Dialog>
    </>
  );
}

export default BildirimTercihleri;
