import React, { useRef, useState } from "react";
import axios from "axios";
import { Button } from "../ui/button";
import { useToast } from "../../hooks/use-toast";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND}/api`;

/** Logo yükleyici — /tema/logo'ya POST eder, önizleme gösterir. */
export default function LogoYukleyici({ mevcutUrl }) {
  const { toast } = useToast();
  const ref = useRef(null);
  const [url, setUrl] = useState(mevcutUrl || null);
  const [yukleniyor, setYukleniyor] = useState(false);

  const sec = async (e) => {
    const dosya = e.target.files?.[0];
    if (!dosya) return;
    setYukleniyor(true);
    try {
      const fd = new FormData();
      fd.append("dosya", dosya);
      const r = await axios.post(`${API}/tema/logo`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setUrl(r.data.logo_url);
      toast({ title: "✅ Logo yüklendi" });
    } catch (err) {
      toast({ title: "Logo yüklenemedi", variant: "destructive" });
    }
    setYukleniyor(false);
    if (ref.current) ref.current.value = "";
  };

  return (
    <div className="flex items-center gap-3">
      <div className="w-16 h-16 rounded-lg border border-gray-200 flex items-center justify-center bg-gray-50 overflow-hidden">
        {url ? <img src={`${BACKEND}${url}`} alt="logo" className="max-w-full max-h-full" /> : <span className="text-2xl">🖼️</span>}
      </div>
      <div>
        <Button size="sm" variant="outline" onClick={() => ref.current?.click()} disabled={yukleniyor}>
          {yukleniyor ? "Yükleniyor…" : "Logo Yükle"}
        </Button>
        <input ref={ref} type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp" hidden onChange={sec} />
        <p className="text-[10px] text-gray-400 mt-1">PNG / JPG / SVG / WebP</p>
      </div>
    </div>
  );
}
