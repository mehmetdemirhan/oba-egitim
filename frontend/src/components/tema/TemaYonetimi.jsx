import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { useToast } from "../../hooks/use-toast";
import { useTheme } from "../../context/ThemeContext";
import TemaKarti from "./TemaKarti";
import TemaFormu from "./TemaFormu";
import LogoYukleyici from "./LogoYukleyici";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** Admin tema yönetim paneli. */
export default function TemaYonetimi() {
  const { toast } = useToast();
  const { setTema } = useTheme() || {};
  const [temalar, setTemalar] = useState([]);
  const [sistemAktif, setSistemAktif] = useState(null);
  const [secili, setSecili] = useState(null);
  const [mod, setModAcik] = useState(null); // "yeni" | "duzenle"
  const dosyaRef = useRef(null);

  const yukle = async () => {
    try {
      const r = await axios.get(`${API}/tema/tumu`);
      setTemalar(r.data?.temalar || []);
      setSistemAktif(r.data?.sistem_aktif || null);
    } catch (e) { toast({ title: "Temalar yüklenemedi", variant: "destructive" }); }
  };
  useEffect(() => { yukle(); /* eslint-disable-next-line */ }, []);

  const kaydet = async (payload) => {
    try {
      if (mod === "yeni") await axios.post(`${API}/tema`, payload);
      else await axios.put(`${API}/tema/${payload.kod}`, payload);
      toast({ title: mod === "yeni" ? "✅ Tema eklendi" : "✅ Tema güncellendi" });
      setModAcik(null); setSecili(null);
      await yukle();
    } catch (e) {
      toast({ title: "Hata", description: String(e?.response?.data?.detail || ""), variant: "destructive" });
    }
  };

  const sil = async (t) => {
    if (!window.confirm(`"${t.ad}" silinsin mi?`)) return;
    try { await axios.delete(`${API}/tema/${t.kod}`); toast({ title: "🗑️ Silindi" }); await yukle(); }
    catch (e) { toast({ title: "Silinemedi", description: String(e?.response?.data?.detail || ""), variant: "destructive" }); }
  };

  const aktifYap = async (t) => {
    try { await axios.post(`${API}/tema/aktif-yap/${t.kod}`); toast({ title: `🎨 Sistem teması: ${t.ad}` }); await yukle(); }
    catch (e) { toast({ title: "Uygulanamadı", variant: "destructive" }); }
  };

  const disaAktar = async () => {
    try {
      const r = await axios.get(`${API}/tema/export`);
      const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "temalar.json"; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast({ title: "Dışa aktarılamadı", variant: "destructive" }); }
  };

  const iceAktar = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const veri = JSON.parse(await file.text());
      const r = await axios.post(`${API}/tema/import`, Array.isArray(veri) ? { temalar: veri } : veri);
      toast({ title: "📥 İçe aktarıldı", description: `${r.data.eklenen} yeni, ${r.data.guncellenen} güncel` });
      await yukle();
    } catch (err) { toast({ title: "İçe aktarılamadı", variant: "destructive" }); }
    if (dosyaRef.current) dosyaRef.current.value = "";
  };

  const onizle = (t) => setTema?.(t.kod); // canlı önizleme (kendi ekranında uygula)

  return (
    <div className="space-y-4">
      <Card className="border-0 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center justify-between flex-wrap gap-2">
            <span>🎨 Tema Yönetimi</span>
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={() => { setSecili(null); setModAcik("yeni"); }} className="bg-blue-600 text-white">+ Yeni Tema</Button>
              <Button size="sm" variant="outline" onClick={disaAktar}>⬇️ JSON İndir</Button>
              <Button size="sm" variant="outline" onClick={() => dosyaRef.current?.click()}>⬆️ JSON Yükle</Button>
              <input ref={dosyaRef} type="file" accept="application/json,.json" hidden onChange={iceAktar} />
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3 pb-3 border-b">
            <div>
              <div className="text-xs font-medium text-gray-700 mb-1">Uygulama Logosu</div>
              <LogoYukleyici />
            </div>
            <div className="text-xs text-gray-500">
              Sistem aktif teması: <span className="font-semibold text-gray-700">{sistemAktif || "—"}</span>
              <p className="text-[10px] text-gray-400 mt-1">Karta "Sistem aktif yap" ile değiştirin. Kartlar tıklanınca kendi ekranınızda önizlenir.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {temalar.map((t) => (
              <div key={t.kod} onClick={() => onizle(t)} className="cursor-pointer">
                <TemaKarti
                  tema={t}
                  aktifMi={t.kod === sistemAktif}
                  onDuzenle={(x) => { setSecili(x); setModAcik("duzenle"); }}
                  onSil={sil}
                  onAktifYap={aktifYap}
                />
              </div>
            ))}
            {temalar.length === 0 && <div className="col-span-full text-center text-sm text-gray-400 py-8">Tema yok</div>}
          </div>
        </CardContent>
      </Card>

      <Dialog open={mod === "yeni" || mod === "duzenle"} onOpenChange={(o) => { if (!o) { setModAcik(null); setSecili(null); } }}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>{mod === "yeni" ? "Yeni Tema" : `Düzenle: ${secili?.ad || ""}`}</DialogTitle></DialogHeader>
          <TemaFormu tema={mod === "duzenle" ? secili : null} onKaydet={kaydet} onIptal={() => { setModAcik(null); setSecili(null); }} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
