import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../ui/select";
import { useToast } from "../../hooks/use-toast";
import RozetGrid from "./RozetGrid";
import RozetFormu from "./RozetFormu";
import KazananlarDialog from "./KazananlarDialog";
import { IkonCoz } from "../../lib/ikonlar";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * RozetYonetimi — admin rozet yönetim paneli.
 * Tanım ekle/düzenle/sil, manuel ver, JSON içe/dışa aktar, istatistik.
 */
export default function RozetYonetimi() {
  const { toast } = useToast();
  const [tanimlar, setTanimlar] = useState([]);
  const [istatistik, setIstatistik] = useState(null);
  const [rolFiltre, setRolFiltre] = useState("hepsi");
  const [arama, setArama] = useState("");
  const [secili, setSecili] = useState(null); // düzenlenecek rozet
  const [mod, setMod] = useState(null); // "yeni" | "duzenle" | "kazananlar"
  const dosyaRef = useRef(null);

  const yukle = async () => {
    try {
      const [t, s] = await Promise.all([
        axios.get(`${API}/rozet/tanim`),
        axios.get(`${API}/rozet/istatistik`).catch(() => ({ data: null })),
      ]);
      setTanimlar(Array.isArray(t.data) ? t.data : []);
      setIstatistik(s.data);
    } catch (e) {
      toast({ title: "Rozetler yüklenemedi", variant: "destructive" });
    }
  };
  useEffect(() => { yukle(); /* eslint-disable-next-line */ }, []);

  const gosterilecek = useMemo(() => {
    let liste = tanimlar;
    if (rolFiltre !== "hepsi") liste = liste.filter((t) => t.rol === rolFiltre);
    if (arama.trim()) {
      const q = arama.toLowerCase();
      liste = liste.filter((t) => (t.ad || "").toLowerCase().includes(q) || (t.kod || "").toLowerCase().includes(q));
    }
    return liste;
  }, [tanimlar, rolFiltre, arama]);

  const kazananSayisi = (t) =>
    istatistik?.rozetler?.find((r) => r.kod === t.kod && r.rol === t.rol)?.kazanan_sayisi ?? 0;

  const kaydet = async (payload) => {
    try {
      if (mod === "yeni") {
        await axios.post(`${API}/rozet/tanim`, payload);
        toast({ title: "✅ Rozet eklendi" });
      } else {
        await axios.put(`${API}/rozet/${payload.rol}/${payload.kod}`, payload);
        toast({ title: "✅ Rozet güncellendi" });
      }
      setMod(null); setSecili(null);
      await yukle();
    } catch (e) {
      const msg = e?.response?.data?.detail || "Kaydedilemedi";
      toast({ title: "Hata", description: String(msg), variant: "destructive" });
    }
  };

  const sil = async () => {
    if (!secili) return;
    const koru = !window.confirm("Kazanılmış rozetler de silinsin mi?\n\nTAMAM = kazanımları da sil · İPTAL = tanımı sil, kazanımları koru");
    try {
      await axios.delete(`${API}/rozet/${secili.rol}/${secili.kod}`, { data: { kazananlari_koru: koru } });
      toast({ title: "🗑️ Rozet silindi" });
      setMod(null); setSecili(null);
      await yukle();
    } catch (e) {
      toast({ title: "Silinemedi", variant: "destructive" });
    }
  };

  const disaAktar = async () => {
    try {
      const r = await axios.get(`${API}/rozet/export`);
      const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "rozetler.json"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast({ title: "Dışa aktarılamadı", variant: "destructive" }); }
  };

  const iceAktar = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const metin = await file.text();
      const veri = JSON.parse(metin);
      const payload = Array.isArray(veri) ? { rozetler: veri } : veri;
      const r = await axios.post(`${API}/rozet/import`, payload);
      toast({ title: "📥 İçe aktarıldı", description: `${r.data.eklenen} yeni, ${r.data.guncellenen} güncel, ${r.data.hatali} hata` });
      await yukle();
    } catch (err) {
      toast({ title: "İçe aktarılamadı", description: "Geçerli JSON değil", variant: "destructive" });
    }
    if (dosyaRef.current) dosyaRef.current.value = "";
  };

  return (
    <div className="space-y-4">
      <Card className="border-0 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center justify-between flex-wrap gap-2">
            <span>🏅 Rozet Yönetimi</span>
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={() => { setSecili(null); setMod("yeni"); }} className="bg-blue-600 text-white">+ Yeni Rozet</Button>
              <Button size="sm" variant="outline" onClick={disaAktar}>⬇️ JSON İndir</Button>
              <Button size="sm" variant="outline" onClick={() => dosyaRef.current?.click()}>⬆️ JSON Yükle</Button>
              <input ref={dosyaRef} type="file" accept="application/json,.json" hidden onChange={iceAktar} />
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* İstatistik özeti */}
          {istatistik && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                ["Tanım", istatistik.toplam_tanim],
                ["Aktif", istatistik.aktif_tanim],
                ["Toplam Kazanım", istatistik.toplam_kazanim],
                ["En Yaygın", istatistik.en_yaygin
                  ? <span className="inline-flex items-center justify-center gap-1 text-amber-500"><IkonCoz deger={istatistik.en_yaygin.ikon} className="w-4 h-4" /><span className="text-gray-900">{istatistik.en_yaygin.kazanan_sayisi}</span></span>
                  : "—"],
              ].map(([l, v]) => (
                <div key={l} className="bg-gray-50 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-gray-900">{v}</div>
                  <div className="text-[10px] text-gray-500">{l}</div>
                </div>
              ))}
            </div>
          )}

          {/* Filtre */}
          <div className="flex items-center gap-2 flex-wrap">
            <Select value={rolFiltre} onValueChange={setRolFiltre}>
              <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="hepsi">Tüm roller</SelectItem>
                <SelectItem value="student">Öğrenci</SelectItem>
                <SelectItem value="teacher">Öğretmen</SelectItem>
              </SelectContent>
            </Select>
            <Input className="flex-1 min-w-[160px]" placeholder="Ara (ad / kod)…" value={arama} onChange={(e) => setArama(e.target.value)} />
          </div>

          {/* Grid — admin: tümü açık, tıkla = düzenle */}
          <RozetGrid
            tanimlar={gosterilecek}
            adminMi
            onRozetKlik={(t) => { setSecili(t); setMod("duzenle"); }}
            baslik={`Rozetler (${gosterilecek.length})`}
          />
          <p className="text-[11px] text-gray-400">Düzenlemek için bir rozete tıklayın.</p>
        </CardContent>
      </Card>

      {/* Ekle / Düzenle dialogu */}
      <Dialog open={mod === "yeni" || mod === "duzenle"} onOpenChange={(o) => { if (!o) { setMod(null); setSecili(null); } }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{mod === "yeni" ? "Yeni Rozet" : `Düzenle: ${secili?.ad || ""}`}</DialogTitle>
          </DialogHeader>
          <RozetFormu rozet={mod === "duzenle" ? secili : null} onKaydet={kaydet} onIptal={() => { setMod(null); setSecili(null); }} />
          {mod === "duzenle" && secili && (
            <div className="flex items-center justify-between border-t pt-2 mt-1">
              <Button variant="outline" size="sm" onClick={() => setMod("kazananlar")}>👥 Kazananlar ({kazananSayisi(secili)})</Button>
              <Button variant="outline" size="sm" className="text-red-600 border-red-200" onClick={sil}>🗑️ Sil</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Kazananlar dialogu */}
      <Dialog open={mod === "kazananlar"} onOpenChange={(o) => { if (!o) setMod("duzenle"); }}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Kazananlar</DialogTitle></DialogHeader>
          {secili && <KazananlarDialog rozet={secili} onKapat={() => setMod("duzenle")} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
