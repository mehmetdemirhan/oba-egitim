import React, { useState } from "react";
import axios from "axios";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { useToast } from "../hooks/use-toast";
import { useAuth } from "../context/AuthContext";
import Logo from "./Logo";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** Ortak şifre değiştirme formu. onDone() başarılı değişimde çağrılır. */
export function SifreDegistirForm({ zorunlu = false, onDone, onIptal }) {
  const { toast } = useToast();
  const [eski, setEski] = useState("");
  const [yeni, setYeni] = useState("");
  const [tekrar, setTekrar] = useState("");
  const [yukleniyor, setYukleniyor] = useState(false);
  const [hata, setHata] = useState("");

  const gonder = async (e) => {
    e.preventDefault();
    setHata("");
    if (yeni.length < 6) return setHata("Yeni şifre en az 6 karakter olmalı.");
    if (yeni !== tekrar) return setHata("Yeni şifreler eşleşmiyor.");
    if (yeni === eski) return setHata("Yeni şifre eskisinden farklı olmalı.");
    setYukleniyor(true);
    try {
      await axios.post(`${API}/auth/change-password`, { old_password: eski, new_password: yeni });
      toast({ title: "✅ Şifre güncellendi" });
      onDone?.();
    } catch (err) {
      setHata(err?.response?.data?.detail || "Şifre değiştirilemedi.");
    }
    setYukleniyor(false);
  };

  return (
    <form onSubmit={gonder} className="space-y-3">
      <div>
        <Label>{zorunlu ? "Geçici (mevcut) şifre" : "Mevcut şifre"}</Label>
        <Input type="password" value={eski} onChange={(e) => setEski(e.target.value)} required />
      </div>
      <div>
        <Label>Yeni şifre</Label>
        <Input type="password" value={yeni} onChange={(e) => setYeni(e.target.value)} required minLength={6} />
      </div>
      <div>
        <Label>Yeni şifre (tekrar)</Label>
        <Input type="password" value={tekrar} onChange={(e) => setTekrar(e.target.value)} required />
      </div>
      {hata && <p className="text-xs text-red-600">{hata}</p>}
      <div className="flex gap-2 pt-1">
        <Button type="submit" disabled={yukleniyor} className="flex-1 bg-blue-600 text-white">
          {yukleniyor ? "Kaydediliyor…" : "Şifreyi Değiştir"}
        </Button>
        {!zorunlu && onIptal && <Button type="button" variant="outline" onClick={onIptal} className="flex-1">İptal</Button>}
      </div>
    </form>
  );
}

/** İlk girişte zorunlu tam ekran şifre değiştirme kapısı. Değişene kadar hiçbir modüle geçilmez. */
export function ZorunluSifreDegistir() {
  const { refreshUser, logout } = useAuth();
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-sm">
        <div className="flex justify-center mb-4"><Logo size="lg" showText={false} /></div>
        <div className="bg-white rounded-2xl shadow-sm border p-6">
          <h1 className="text-lg font-bold text-gray-900 text-center">Şifrenizi Belirleyin</h1>
          <p className="text-xs text-gray-500 text-center mt-1 mb-4">
            Hesabınız geçici bir şifreyle oluşturuldu. Devam etmek için lütfen yeni bir şifre belirleyin.
          </p>
          <SifreDegistirForm zorunlu onDone={() => refreshUser()} />
          <button onClick={logout} className="w-full text-center text-xs text-gray-400 hover:text-gray-600 mt-3">
            Çıkış yap
          </button>
        </div>
      </div>
    </div>
  );
}

/** Header'a konulabilen "Şifre Değiştir" butonu (kendi dialog'unu yönetir). */
export function SifreDegistirButton() {
  const [acik, setAcik] = useState(false);
  return (
    <>
      <button onClick={() => setAcik(true)} title="Şifre Değiştir"
        className="inline-flex items-center justify-center h-9 w-9 rounded-md border border-gray-200 hover:bg-gray-50 text-gray-600">
        🔑
      </button>
      <Dialog open={acik} onOpenChange={setAcik}>
        <DialogContent className="max-w-xs">
          <DialogHeader><DialogTitle>Şifre Değiştir</DialogTitle></DialogHeader>
          <SifreDegistirForm onDone={() => setAcik(false)} onIptal={() => setAcik(false)} />
        </DialogContent>
      </Dialog>
    </>
  );
}

export default SifreDegistirForm;
