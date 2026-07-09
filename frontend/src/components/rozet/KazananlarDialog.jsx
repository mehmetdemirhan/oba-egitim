import React, { useEffect, useState } from "react";
import axios from "axios";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { IkonCoz } from "../../lib/ikonlar";
import { useToast } from "../../hooks/use-toast";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * KazananlarDialog — bir rozetin kazananlarını listeler; manuel ver / geri al.
 * Props: rozet {rol, kod, ad}, onKapat()
 */
export default function KazananlarDialog({ rozet, onKapat }) {
  const { toast } = useToast();
  const [liste, setListe] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [yeniUser, setYeniUser] = useState("");
  const [islem, setIslem] = useState(false);

  const yukle = async () => {
    setYukleniyor(true);
    try {
      const r = await axios.get(`${API}/rozet/${rozet.rol}/${rozet.kod}/kazananlar`);
      setListe(r.data?.kazananlar || []);
    } catch (e) { setListe([]); }
    setYukleniyor(false);
  };

  useEffect(() => { yukle(); /* eslint-disable-next-line */ }, [rozet.rol, rozet.kod]);

  const manuelVer = async () => {
    if (!yeniUser.trim()) return;
    setIslem(true);
    try {
      await axios.post(`${API}/rozet/${rozet.rol}/${rozet.kod}/ver`, { user_id: yeniUser.trim() });
      setYeniUser("");
      await yukle();
      toast({ title: "Rozet verildi" });
    } catch (e) {
      toast({ title: "Rozet verilemedi", description: e?.response?.data?.detail || "Bir hata oluştu", variant: "destructive" });
    }
    setIslem(false);
  };

  const geriAl = async (user_id) => {
    setIslem(true);
    try {
      await axios.post(`${API}/rozet/${rozet.rol}/${rozet.kod}/geri-al`, { user_id });
      await yukle();
      toast({ title: "Rozet geri alındı" });
    } catch (e) {
      toast({ title: "Rozet geri alınamadı", description: e?.response?.data?.detail || "Bir hata oluştu", variant: "destructive" });
    }
    setIslem(false);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-amber-500"><IkonCoz deger={rozet.ikon} className="w-6 h-6" /></span>
        <div>
          <div className="font-bold text-sm">{rozet.ad}</div>
          <div className="text-[11px] text-gray-500">{rozet.rol} · {rozet.kod}</div>
        </div>
      </div>

      <div className="flex gap-2">
        <Input placeholder="Kullanıcı ID (manuel ver)" value={yeniUser} onChange={(e) => setYeniUser(e.target.value)} />
        <Button onClick={manuelVer} disabled={islem || !yeniUser.trim()} className="bg-green-600 text-white whitespace-nowrap">🏅 Ver</Button>
      </div>

      <div className="max-h-64 overflow-y-auto border rounded-lg divide-y">
        {yukleniyor ? (
          <div className="p-3 text-center text-xs text-gray-400">Yükleniyor…</div>
        ) : liste.length === 0 ? (
          <div className="p-3 text-center text-xs text-gray-400">Henüz kimse kazanmadı</div>
        ) : (
          liste.map((k) => (
            <div key={k.kullanici_id} className="flex items-center justify-between p-2 text-xs">
              <div>
                <div className="font-medium">{k.ad_soyad || k.kullanici_id}</div>
                <div className="text-[10px] text-gray-400">{String(k.kazanma_tarihi || "").slice(0, 10)}</div>
              </div>
              <button onClick={() => geriAl(k.kullanici_id)} disabled={islem}
                className="text-red-500 hover:text-red-700 text-[11px]">Geri al</button>
            </div>
          ))
        )}
      </div>

      <div className="text-[11px] text-gray-500">Toplam kazanan: {liste.length}</div>
    </div>
  );
}
