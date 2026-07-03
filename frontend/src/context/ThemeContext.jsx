import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import { useAuth } from "./AuthContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const CACHE_KEY = "oba_tema";

const ThemeContext = createContext(null);
export const useTheme = () => useContext(ThemeContext) || {};

/** mod ("light"|"dark"|"auto") → gerçek uygulanacak mod */
function etkinMod(mod) {
  if (mod === "auto") {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return mod === "dark" ? "dark" : "light";
}

/** Tema token'larını <html>'e CSS değişkeni olarak uygula + .dark sınıfı + data-theme */
function domaUygula(tema, mod) {
  if (!tema?.modlar) return;
  const em = etkinMod(mod);
  const tokens = tema.modlar[em] || tema.modlar.light || {};
  const root = document.documentElement;
  Object.entries(tokens).forEach(([k, v]) => {
    root.style.setProperty(`--${k.replace(/_/g, "-")}`, v);
  });
  root.classList.toggle("dark", em === "dark");
  root.setAttribute("data-theme", tema.kod || "");
  root.setAttribute("data-mode", em);
}

function cacheOku() {
  try { return JSON.parse(localStorage.getItem(CACHE_KEY) || "null"); } catch { return null; }
}
function cacheYaz(tema, mod) {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify({ tema, mod })); } catch {}
}

export function ThemeProvider({ children }) {
  const { user } = useAuth() || {};
  const [tema, setTemaState] = useState(null);
  const [mod, setModState] = useState("light");
  const [temalar, setTemalar] = useState([]);
  const mediaRef = useRef(null);

  // 1) Mount: cache'ten anında uygula (FOUC önle)
  useEffect(() => {
    const c = cacheOku();
    if (c?.tema) {
      setTemaState(c.tema);
      setModState(c.mod || "light");
      domaUygula(c.tema, c.mod || "light");
    }
  }, []);

  // 2) Hazır tema listesini çek (herkese açık)
  useEffect(() => {
    axios.get(`${API}/tema/hazir`).then((r) => setTemalar(Array.isArray(r.data) ? r.data : [])).catch(() => {});
  }, []);

  // 3) Kullanıcı değişince backend'den çözümlenmiş temayı çek
  useEffect(() => {
    let iptal = false;
    if (!user) return;
    axios.get(`${API}/tema/aktif`).then((r) => {
      if (iptal || !r.data?.tema) return;
      setTemaState(r.data.tema);
      setModState(r.data.mod || "light");
      domaUygula(r.data.tema, r.data.mod || "light");
      cacheYaz(r.data.tema, r.data.mod || "light");
    }).catch(() => {});
    return () => { iptal = true; };
  }, [user]);

  // 4) mod === "auto" iken sistem tercihini dinle
  useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mediaRef.current = () => { if (mod === "auto" && tema) domaUygula(tema, "auto"); };
    mq.addEventListener?.("change", mediaRef.current);
    return () => mq.removeEventListener?.("change", mediaRef.current);
  }, [mod, tema]);

  const _persist = useCallback(async (tema_kodu, yeniMod) => {
    if (!user) return;
    try {
      await axios.post(`${API}/tema/kullanici/tercih`, { tema_kodu, mod: yeniMod });
    } catch {}
  }, [user]);

  const setTema = useCallback((kod) => {
    const t = temalar.find((x) => x.kod === kod);
    if (!t) return;
    setTemaState(t);
    domaUygula(t, mod);
    cacheYaz(t, mod);
    _persist(kod, mod);
  }, [temalar, mod, _persist]);

  const setMod = useCallback((yeniMod) => {
    setModState(yeniMod);
    if (tema) { domaUygula(tema, yeniMod); cacheYaz(tema, yeniMod); }
    _persist(tema?.kod, yeniMod);
  }, [tema, _persist]);

  const deger = { tema, mod, temalar, etkinMod: etkinMod(mod), setTema, setMod };
  return <ThemeContext.Provider value={deger}>{children}</ThemeContext.Provider>;
}
