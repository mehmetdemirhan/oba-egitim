import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Card, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { useToast } from "../hooks/use-toast";
import {
  Package, Upload, Trash2, RefreshCw, History, Power, PowerOff,
  Server, Monitor, Layers, AlertTriangle, Loader2,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TIP_IKON = {
  backend: <Server className="h-4 w-4" />,
  frontend: <Monitor className="h-4 w-4" />,
  both: <Layers className="h-4 w-4" />,
};

export default function ModulYonetimi() {
  const { toast } = useToast();
  const [moduller, setModuller] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [islemYapilan, setIslemYapilan] = useState(null); // modül adı (toggle/sil sırasında)
  const [restartUyari, setRestartUyari] = useState(null);
  const [gecmis, setGecmis] = useState(null); // {ad, versiyonlar:[]}
  const dosyaInput = useRef(null);
  const guncelleInput = useRef(null);
  const [guncellenecek, setGuncellenecek] = useState(null);

  const fetchModuller = async () => {
    try {
      const r = await axios.get(`${API}/admin/moduller`);
      setModuller(Array.isArray(r.data) ? r.data : []);
    } catch (e) {
      toast({ title: "Hata", description: "Modüller yüklenemedi", variant: "destructive" });
    }
  };

  useEffect(() => { fetchModuller(); }, []);

  const hataMesaji = (e) => {
    const d = e?.response?.data?.detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object") {
      const parcalar = [].concat(d.errors || [], d.mesaj || []);
      return parcalar.join(" • ") || JSON.stringify(d);
    }
    return "Beklenmeyen hata";
  };

  const yukle = async (file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".zip")) {
      toast({ title: "Geçersiz dosya", description: "Yalnızca .zip kabul edilir", variant: "destructive" });
      return;
    }
    setYukleniyor(true);
    try {
      const fd = new FormData();
      fd.append("dosya", file);
      const r = await axios.post(`${API}/admin/moduller/yukle`, fd);
      toast({ title: "Başarılı", description: r.data.mesaj });
      if (r.data.warnings?.length) {
        toast({ title: "Uyarılar", description: r.data.warnings.join(" • ") });
      }
      setRestartUyari(r.data.restart_uyarisi);
      await fetchModuller();
    } catch (e) {
      toast({ title: "Yükleme başarısız", description: hataMesaji(e), variant: "destructive" });
    } finally {
      setYukleniyor(false);
    }
  };

  const dosyaSecildi = (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    yukle(f);
  };

  const guncelleSecildi = (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    yukle(f); // install_patch mevcut modülü algılar → sürüm arşivlenir
  };

  const toggle = async (m) => {
    setIslemYapilan(m.name);
    try {
      const r = await axios.put(`${API}/admin/moduller/${m.name}/durum`, { active: !m.active });
      toast({ title: "Güncellendi", description: r.data.mesaj });
      setRestartUyari(r.data.restart_uyarisi);
      await fetchModuller();
    } catch (e) {
      toast({ title: "Hata", description: hataMesaji(e), variant: "destructive" });
    } finally {
      setIslemYapilan(null);
    }
  };

  const sil = async (m) => {
    if (!window.confirm(`'${m.name}' modülü tamamen silinecek. Emin misiniz?`)) return;
    setIslemYapilan(m.name);
    try {
      const r = await axios.delete(`${API}/admin/moduller/${m.name}`);
      toast({ title: "Silindi", description: r.data.mesaj });
      setRestartUyari(r.data.restart_uyarisi);
      await fetchModuller();
    } catch (e) {
      toast({ title: "Hata", description: hataMesaji(e), variant: "destructive" });
    } finally {
      setIslemYapilan(null);
    }
  };

  const gecmisAc = async (m) => {
    try {
      const r = await axios.get(`${API}/admin/moduller/${m.name}/versiyonlar`);
      setGecmis({ ad: m.name, versiyonlar: r.data });
    } catch (e) {
      toast({ title: "Hata", description: hataMesaji(e), variant: "destructive" });
    }
  };

  const geriYukle = async (ad, etiket) => {
    if (!window.confirm(`'${ad}' modülü '${etiket}' sürümüne döndürülecek. Onaylıyor musunuz?`)) return;
    try {
      const r = await axios.post(`${API}/admin/moduller/${ad}/geri-yukle/${etiket}`);
      toast({ title: "Geri yüklendi", description: r.data.mesaj });
      setRestartUyari(r.data.restart_uyarisi);
      setGecmis(null);
      await fetchModuller();
    } catch (e) {
      toast({ title: "Hata", description: hataMesaji(e), variant: "destructive" });
    }
  };

  const tarih = (s) => {
    if (!s) return "—";
    try { return new Date(s).toLocaleString("tr-TR"); } catch { return s; }
  };

  return (
    <div className="space-y-4">
      {/* Üst bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Package className="h-5 w-5" /> Modül Yönetimi
          </h2>
          <p className="text-sm text-gray-500">
            {moduller.length} modül kurulu • çekirdek modüller kapatılamaz
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input ref={dosyaInput} type="file" accept=".zip" className="hidden" onChange={dosyaSecildi} />
          <input ref={guncelleInput} type="file" accept=".zip" className="hidden" onChange={guncelleSecildi} />
          <Button onClick={() => dosyaInput.current?.click()} disabled={yukleniyor}>
            {yukleniyor ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />}
            Yeni Modül Yükle
          </Button>
        </div>
      </div>

      {/* Kart grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {moduller.map((m) => (
          <Card key={m.name} className={`border ${m.active ? "" : "opacity-60"}`}>
            <CardContent className="p-4 space-y-3">
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold truncate">{m.name}</span>
                    <Badge variant="secondary">v{m.version}</Badge>
                  </div>
                  <div className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                    {TIP_IKON[m.type] || <Server className="h-4 w-4" />}
                    <span>{m.type}</span>
                    <span className="mx-1">•</span>
                    <span>{m.author}</span>
                  </div>
                </div>
                {m.active
                  ? <Badge className="bg-green-100 text-green-700">Aktif</Badge>
                  : <Badge className="bg-gray-200 text-gray-600">Pasif</Badge>}
              </div>

              <p className="text-sm text-gray-600 line-clamp-2 min-h-[2.5rem]">{m.description}</p>

              <div className="text-xs text-gray-400">
                Son güncelleme: {tarih(m.restored_at || m.installed_at)}
                {m.core && <Badge className="ml-2 bg-amber-100 text-amber-700">çekirdek</Badge>}
              </div>

              <div className="flex flex-wrap gap-2 pt-1">
                <Button size="sm" variant={m.active ? "outline" : "default"}
                        disabled={m.core || islemYapilan === m.name}
                        title={m.core ? "Çekirdek modül kapatılamaz" : ""}
                        onClick={() => toggle(m)}>
                  {m.active ? <PowerOff className="h-4 w-4 mr-1" /> : <Power className="h-4 w-4 mr-1" />}
                  {m.active ? "Kapat" : "Aç"}
                </Button>
                <Button size="sm" variant="outline"
                        onClick={() => { setGuncellenecek(m.name); guncelleInput.current?.click(); }}>
                  <RefreshCw className="h-4 w-4 mr-1" /> Güncelle
                </Button>
                <Button size="sm" variant="outline" onClick={() => gecmisAc(m)}>
                  <History className="h-4 w-4 mr-1" /> Geçmiş
                </Button>
                <Button size="sm" variant="outline"
                        className="text-red-600 hover:bg-red-50"
                        disabled={m.core || islemYapilan === m.name}
                        title={m.core ? "Çekirdek modül silinemez" : ""}
                        onClick={() => sil(m)}>
                  <Trash2 className="h-4 w-4 mr-1" /> Sil
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Restart uyarı dialog */}
      <Dialog open={!!restartUyari} onOpenChange={() => setRestartUyari(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" /> Yeniden Başlatma
            </DialogTitle>
            <DialogDescription>{restartUyari}</DialogDescription>
          </DialogHeader>
          <div className="flex justify-end">
            <Button onClick={() => setRestartUyari(null)}>Anladım</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Geçmiş sürümler dialog */}
      <Dialog open={!!gecmis} onOpenChange={() => setGecmis(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Geçmiş Sürümler — {gecmis?.ad}</DialogTitle>
            <DialogDescription>Son 3 sürüm saklanır. Bir sürüme geri dönebilirsiniz.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            {(gecmis?.versiyonlar || []).length === 0 && (
              <p className="text-sm text-gray-500">Arşivlenmiş önceki sürüm yok.</p>
            )}
            {(gecmis?.versiyonlar || []).map((v) => (
              <div key={v.etiket} className="flex items-center justify-between border rounded p-2">
                <div className="text-sm">
                  <span className="font-medium">v{v.version}</span>
                  <span className="text-gray-400 ml-2">{tarih(v.archived_at)}</span>
                </div>
                <Button size="sm" variant="outline" onClick={() => geriYukle(gecmis.ad, v.etiket)}>
                  Bu sürüme dön
                </Button>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
