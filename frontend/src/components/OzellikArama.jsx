import React, { useState, useEffect, useRef, useMemo } from "react";
import { Search, X, CornerDownLeft, Compass } from "lucide-react";
import { araKayitlar, KAYIT_SAYISI } from "../aramaRegistry";

/**
 * OzellikArama — sayfa üstü genel ÖZELLİK/MODÜL araması (komut paleti). Uygulamadaki
 * tüm sekme/alt-sekme/gizli bölümleri role göre arar; seçilince "oba-git" olayı ile
 * ilgili panele yönlendirir (sayfa yenilemeden). Ctrl/Cmd+K veya "/" ile açılır.
 *
 * Yönlendirme sözleşmesi: window.dispatchEvent(new CustomEvent("oba-git", {detail: hedef}))
 *   hedef = { sekme, altSekme? }. Ayrıca window.__obaGitHedef ayarlanır (henüz mount
 *   olmamış alt-panellerin mount'ta okuyabilmesi için).
 */
export default function OzellikArama({ user }) {
  const [acik, setAcik] = useState(false);
  const [q, setQ] = useState("");
  const [sec, setSec] = useState(0);
  const inputRef = useRef(null);
  const rol = user?.role;

  const sonuclar = useMemo(() => (acik ? araKayitlar(q, rol) : []), [q, rol, acik]);
  useEffect(() => { setSec(0); }, [q]);

  useEffect(() => {
    const h = (e) => {
      const k = e.key?.toLowerCase();
      if ((e.ctrlKey || e.metaKey) && k === "k") { e.preventDefault(); setAcik((v) => !v); return; }
      if (e.key === "/" && !acik && !/input|textarea|select/i.test(document.activeElement?.tagName || "")) { e.preventDefault(); setAcik(true); }
      if (e.key === "Escape") setAcik(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [acik]);

  useEffect(() => { if (acik) setTimeout(() => inputRef.current?.focus(), 40); }, [acik]);

  const kapat = () => { setAcik(false); setQ(""); };
  const git = (e) => {
    const hedef = e.hedef;
    window.__obaGitHedef = hedef;
    window.dispatchEvent(new CustomEvent("oba-git", { detail: hedef }));
    kapat();
  };

  const klavye = (ev) => {
    if (!sonuclar.length) return;
    if (ev.key === "ArrowDown") { ev.preventDefault(); setSec((s) => Math.min(s + 1, sonuclar.length - 1)); }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); setSec((s) => Math.max(s - 1, 0)); }
    else if (ev.key === "Enter") { ev.preventDefault(); git(sonuclar[sec]); }
  };

  return (
    <>
      <button onClick={() => setAcik(true)} title="Özellik / bölüm ara (Ctrl+K)"
        className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-app px-2.5 py-1.5 text-sm text-subtle hover:text-content hover:border-primary transition">
        <Compass className="h-4 w-4" /><span className="hidden md:inline">Bölüm ara</span>
        <kbd className="hidden md:inline text-[10px] bg-surface border border-line rounded px-1">Ctrl K</kbd>
      </button>

      {acik && (
        <div className="fixed inset-0 z-[95] bg-black/40 flex items-start justify-center p-4 pt-[8vh]" onClick={kapat}>
          <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 px-4 py-3 border-b border-line">
              <Search className="h-5 w-5 text-subtle" />
              <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={klavye}
                placeholder="Özellik, modül veya bölüm ara… (örn. havuz, kalite, vergi, modüller)"
                className="flex-1 bg-transparent outline-none text-sm text-content" />
              <button onClick={kapat} className="text-subtle hover:text-content"><X className="h-4 w-4" /></button>
            </div>

            <div className="max-h-[60vh] overflow-y-auto">
              {q.trim().length < 2 && (
                <div className="p-6 text-center text-sm text-subtle">
                  Aradığınız bölümün adını yazın; sistem sizi oraya götürsün.<br />
                  <span className="text-xs">Menüde görünmeyen bölümler de aranabilir. Rolünüze uygun {sonuclar.length || ""} sonuç.</span>
                </div>
              )}
              {q.trim().length >= 2 && sonuclar.length === 0 && (
                <div className="p-6 text-center text-sm text-subtle">🔍 Eşleşme bulunamadı. Farklı bir kelime deneyin.</div>
              )}
              {sonuclar.map((e, i) => (
                <button key={e.ad + i} onClick={() => git(e)} onMouseEnter={() => setSec(i)}
                  className={`w-full text-left flex items-center gap-2 px-4 py-2.5 border-b border-line/50 last:border-0 transition ${i === sec ? "bg-app" : "hover:bg-app"}`}>
                  <Compass className="h-4 w-4 text-primary shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-content truncate">{e.ad}</div>
                    {e.hedef.altSekme && <div className="text-[11px] text-subtle">Ayarlar → alt bölüm</div>}
                  </div>
                  {i === sec && <CornerDownLeft className="h-3.5 w-3.5 text-subtle shrink-0" />}
                </button>
              ))}
            </div>
            <div className="px-4 py-2 border-t border-line text-[11px] text-subtle flex items-center justify-between">
              <span>↑↓ gez · ↵ git · Esc kapat</span>
              <span>{KAYIT_SAYISI} bölüm kayıtlı</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
