import React, { useEffect, useState } from "react";
import { Bell, BellOff, BellRing } from "lucide-react";
import { Button } from "./ui/button";
import { useToast } from "../hooks/use-toast";
import { pushDestekleniyor, bildirimDurumu, pushAboneOl, pushAbonelikBitir } from "../lib/push";

/**
 * BildirimIzni — veliye ders hatırlatma bildirimleri için izin kartı.
 * Ayarlar/panelde gösterilir; izin durumunu yönetir.
 */
export default function BildirimIzni() {
  const { toast } = useToast();
  const [durum, setDurum] = useState("default"); // default | granted | denied | desteklenmiyor
  const [islem, setIslem] = useState(false);

  useEffect(() => { setDurum(bildirimDurumu()); }, []);

  const izinVer = async () => {
    setIslem(true);
    try {
      await pushAboneOl();
      setDurum("granted");
      toast({ title: "🔔 Bildirimler açıldı", description: "Ders saatinden 15 dk önce hatırlatılacaksınız." });
    } catch (e) {
      setDurum(bildirimDurumu());
      toast({ title: "Açılamadı", description: e.message || "Bildirim izni alınamadı.", variant: "destructive" });
    }
    setIslem(false);
  };

  const kapat = async () => {
    setIslem(true);
    await pushAbonelikBitir();
    setDurum(bildirimDurumu());
    toast({ title: "Bildirimler kapatıldı" });
    setIslem(false);
  };

  if (!pushDestekleniyor() || durum === "desteklenmiyor") {
    return (
      <div className="bg-white rounded-2xl p-4 shadow-sm border flex items-center gap-3">
        <BellOff className="h-5 w-5 text-gray-400" />
        <div className="text-sm text-gray-500">Bu tarayıcı ders hatırlatma bildirimlerini desteklemiyor.
          <span className="block text-[11px] text-gray-400">iPhone'da: siteyi "Ana Ekrana Ekle" ile kurun (iOS 16.4+).</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border">
      <div className="flex items-center gap-3 mb-2">
        {durum === "granted" ? <BellRing className="h-5 w-5 text-green-600" /> : <Bell className="h-5 w-5 text-orange-500" />}
        <div>
          <div className="font-semibold text-sm text-gray-900">Ders Hatırlatma Bildirimleri</div>
          <div className="text-[11px] text-gray-500">Çocuğunuzun dersinden 15 dk önce tarayıcı bildirimi.</div>
        </div>
      </div>
      {durum === "granted" ? (
        <div className="flex items-center gap-2">
          <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">✓ Açık</span>
          <Button size="sm" variant="outline" onClick={kapat} disabled={islem}>Kapat</Button>
        </div>
      ) : durum === "denied" ? (
        <p className="text-xs text-red-600">Bildirimler tarayıcı ayarlarından engellenmiş. Site izinlerinden açabilirsiniz.</p>
      ) : (
        <Button size="sm" onClick={izinVer} disabled={islem} className="bg-orange-500 text-white">
          {islem ? "…" : "🔔 Bildirimlere İzin Ver"}
        </Button>
      )}
    </div>
  );
}
