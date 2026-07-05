import React, { useEffect, useState } from "react";

/**
 * PWAKur — "Ana Ekrana Ekle" yönlendirmesi.
 * Android: beforeinstallprompt → tek tık "Kur". iOS Safari: elle ekleme yönergesi.
 * Standalone (zaten kurulu) veya kullanıcı kapattıysa gösterilmez.
 */
export default function PWAKur() {
  const [iosBanner, setIosBanner] = useState(false);
  const [deferred, setDeferred] = useState(null);

  useEffect(() => {
    if (localStorage.getItem("oba_pwa_kapat") === "1") return;
    const standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
    if (standalone) return;
    const ua = navigator.userAgent || "";
    const iosSafari = /iphone|ipad|ipod/i.test(ua) && !/crios|fxios/i.test(ua);
    if (iosSafari) setIosBanner(true);
    const handler = (e) => { e.preventDefault(); setDeferred(e); };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const kapat = () => { localStorage.setItem("oba_pwa_kapat", "1"); setIosBanner(false); setDeferred(null); };
  const kur = async () => {
    if (!deferred) return;
    deferred.prompt();
    try { await deferred.userChoice; } catch (e) {}
    kapat();
  };

  if (!iosBanner && !deferred) return null;
  return (
    <div className="fixed bottom-3 left-3 right-3 z-[60] mx-auto max-w-md bg-white rounded-2xl shadow-2xl border border-gray-200 p-3 flex items-center gap-3">
      <div className="text-2xl">📲</div>
      <div className="flex-1 text-xs text-gray-700 leading-snug">
        {deferred
          ? <>Uygulamayı <b>ana ekrana ekleyin</b> — daha hızlı erişim, tam ekran.</>
          : <>iPhone'da: aşağıdaki <b>Paylaş</b> ikonuna dokunun → <b>Ana Ekrana Ekle</b>.</>}
      </div>
      {deferred && <button onClick={kur} className="text-xs bg-orange-500 text-white px-3 py-1.5 rounded-lg font-medium whitespace-nowrap">Kur</button>}
      <button onClick={kapat} className="text-gray-400 hover:text-gray-600 text-sm">✕</button>
    </div>
  );
}
