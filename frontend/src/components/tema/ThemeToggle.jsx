import React, { useState } from "react";
import { Sun, Moon, Monitor, Palette } from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { useToast } from "../../hooks/use-toast";

/**
 * ThemeToggle — header'da tema/mod seçici.
 * Mod (açık/koyu/otomatik) + kullanıcının seçebileceği tema listesi.
 */
const MODLAR = [
  { k: "light", ad: "Açık", ikon: Sun },
  { k: "dark", ad: "Koyu", ikon: Moon },
  { k: "auto", ad: "Otomatik", ikon: Monitor },
];

export default function ThemeToggle() {
  const { tema, mod, temalar, etkinMod, setTema, setMod } = useTheme() || {};
  const { toast } = useToast();
  const [acik, setAcik] = useState(false);
  const AktifIkon = etkinMod === "dark" ? Moon : Sun;

  const temaSec = (t) => { setTema?.(t.kod); toast({ title: `🎨 Tema: ${t.ad}` }); };
  const modSec = (k, ad) => { setMod?.(k); toast({ title: `Görünüm: ${ad}` }); };

  return (
    <div className="relative">
      <button
        onClick={() => setAcik((v) => !v)}
        title="Tema"
        className="inline-flex items-center justify-center h-9 w-9 rounded-md border border-gray-200 hover:bg-gray-50 text-gray-600"
      >
        <AktifIkon className="h-4 w-4" />
      </button>

      {acik && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setAcik(false)} />
          <div className="absolute right-0 mt-2 w-56 z-50 rounded-xl border border-gray-200 bg-white shadow-lg p-2">
            {/* Mod */}
            <div className="text-[10px] font-semibold text-gray-400 px-2 pb-1">GÖRÜNÜM</div>
            <div className="grid grid-cols-3 gap-1 mb-2">
              {MODLAR.map(({ k, ad, ikon: Ikon }) => (
                <button key={k} onClick={() => modSec(k, ad)}
                  className={`flex flex-col items-center gap-0.5 py-1.5 rounded-lg text-[10px] ${mod === k ? "bg-blue-50 text-blue-600 ring-1 ring-blue-200" : "text-gray-600 hover:bg-gray-50"}`}>
                  <Ikon className="h-4 w-4" /> {ad}
                </button>
              ))}
            </div>
            {/* Tema listesi */}
            {temalar?.length > 0 && (
              <>
                <div className="text-[10px] font-semibold text-gray-400 px-2 pb-1 flex items-center gap-1"><Palette className="h-3 w-3" />TEMA</div>
                <div className="max-h-52 overflow-y-auto space-y-0.5">
                  {temalar.map((t) => {
                    const c = t?.modlar?.light || {};
                    return (
                      <button key={t.kod} onClick={() => temaSec(t)}
                        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs ${tema?.kod === t.kod ? "bg-gray-100 font-medium" : "hover:bg-gray-50"}`}>
                        <span className="flex -space-x-1">
                          {["primary", "accent", "success"].map((tok) => (
                            <span key={tok} className="w-3 h-3 rounded-full border border-white" style={{ backgroundColor: c[tok] || "#ccc" }} />
                          ))}
                        </span>
                        <span className="flex-1 text-left text-gray-700">{t.ad}</span>
                        {tema?.kod === t.kod && <span className="text-blue-500">✓</span>}
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
