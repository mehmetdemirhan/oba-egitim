// Egzersiz layout yardımcıları: sağdan slide-in ayar paneli ve "?" yardım
// popover'ı. Tek tasarım dili; tüm egzersiz wrapper'ları bunları kullanır.
import React, { useEffect, useState } from "react";

/**
 * AyarPaneli — sağdan içeri kayan ayar çekmecesi.
 * Desktop'ta 320px, mobilde tam ekran modal. Arka plan (backdrop) tıklaması
 * veya ✕ ile kapanır. Açıkken egzersiz arka planda çalışmaya devam eder.
 */
export function AyarPaneli({ acik, onKapat, baslik = "⚙️ Ayarlar", children }) {
  // ESC ile kapat
  useEffect(() => {
    if (!acik) return;
    const onKey = (e) => { if (e.key === "Escape") { e.stopPropagation(); onKapat(); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [acik, onKapat]);

  return (
    <>
      {/* Backdrop */}
      <div onClick={onKapat}
        className={`fixed inset-0 z-[70] bg-black/30 transition-opacity duration-300 ${acik ? "opacity-100" : "opacity-0 pointer-events-none"}`}
        aria-hidden={!acik} />
      {/* Panel */}
      <div
        className={`fixed top-0 right-0 z-[71] h-full w-full sm:w-80 bg-white shadow-2xl flex flex-col transition-transform duration-300 ${acik ? "translate-x-0" : "translate-x-full"}`}
        role="dialog" aria-label="Egzersiz ayarları">
        <div className="flex items-center justify-between px-4 h-14 border-b border-gray-100 flex-shrink-0">
          <h3 className="font-bold text-sm text-gray-800">{baslik}</h3>
          <button onClick={onKapat} title="Kapat"
            className="w-9 h-9 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-500">✕</button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-5">{children}</div>
      </div>
    </>
  );
}

/**
 * YardimBaloncugu — "?" düğmesi; tıklanınca açıklama popover'ı açılır.
 * 6 saniye sonra veya tekrar tıklayınca kapanır.
 */
export function YardimBaloncugu({ metin }) {
  const [acik, setAcik] = useState(false);
  useEffect(() => {
    if (!acik) return;
    const t = setTimeout(() => setAcik(false), 6000);
    return () => clearTimeout(t);
  }, [acik]);

  return (
    <div className="relative">
      <button onClick={() => setAcik((a) => !a)} title="Açıklama"
        className="w-9 h-9 rounded-lg border border-gray-200 bg-white text-gray-500 hover:bg-gray-50 flex items-center justify-center text-sm font-bold">?</button>
      {acik && (
        <div className="absolute right-0 top-11 z-[72] w-72 max-w-[80vw] p-4 rounded-xl bg-slate-800 text-white text-sm leading-relaxed shadow-2xl">
          {metin}
          <div className="absolute -top-1 right-3 w-2.5 h-2.5 bg-slate-800 rotate-45" />
        </div>
      )}
    </div>
  );
}
