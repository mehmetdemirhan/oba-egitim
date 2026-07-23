import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { Search, X, User, GraduationCap } from "lucide-react";

/**
 * GlobalArama — site geneli arama simgesi + modal. Öğrenci ve öğretmenleri ada/veliye/
 * TC'ye/telefona/sınıfa/kura göre arar (rol duyarlı; backend /ara). Öğrenci sonucuna
 * tıklanınca onOgrenciSec (varsa) çağrılır (detay açma); yoksa bilgiler yerinde gösterilir.
 */
export default function GlobalArama({ apiBase, onOgrenciSec, onOgretmenSec }) {
  const [acik, setAcik] = useState(false);
  const [q, setQ] = useState("");
  const [sonuc, setSonuc] = useState(null);
  const [yuk, setYuk] = useState(false);
  const inputRef = useRef(null);
  const sonRef = useRef(0);

  const ara = useCallback(async (deger) => {
    if ((deger || "").trim().length < 2) { setSonuc(null); return; }
    const istek = ++sonRef.current;
    setYuk(true);
    try {
      const r = await axios.get(`${apiBase}/ara`, { params: { q: deger } });
      if (istek === sonRef.current) setSonuc(r.data);
    } catch (e) { if (istek === sonRef.current) setSonuc({ ogrenciler: [], ogretmenler: [] }); }
    finally { if (istek === sonRef.current) setYuk(false); }
  }, [apiBase]);

  // Debounce
  useEffect(() => {
    if (!acik) return;
    const t = setTimeout(() => ara(q), 250);
    return () => clearTimeout(t);
  }, [q, acik, ara]);

  useEffect(() => { if (acik) setTimeout(() => inputRef.current?.focus(), 50); }, [acik]);
  // Klavye kısayolu: "/" ile aç
  useEffect(() => {
    const h = (e) => {
      if (e.key === "/" && !acik && !/input|textarea/i.test(document.activeElement?.tagName || "")) { e.preventDefault(); setAcik(true); }
      if (e.key === "Escape") setAcik(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [acik]);

  const kapat = () => { setAcik(false); setQ(""); setSonuc(null); };
  const ogrenciSec = (o) => { kapat(); onOgrenciSec && onOgrenciSec(o); };
  const ogretmenSec = (t) => { kapat(); onOgretmenSec && onOgretmenSec(t); };

  const durumRoz = (o) => o.ayrildi ? <span className="text-[10px] text-orange-600">ayrıldı</span>
    : o.mezun ? <span className="text-[10px] text-blue-600">mezun</span>
    : o.arsivli ? <span className="text-[10px] text-subtle">arşiv</span> : null;

  return (
    <>
      <button onClick={() => setAcik(true)} title="Ara ( / )" className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-app px-2.5 py-1.5 text-sm text-subtle hover:text-content hover:border-primary transition">
        <Search className="h-4 w-4" /><span className="hidden sm:inline">Ara</span>
      </button>

      {acik && (
        <div className="fixed inset-0 z-[90] bg-black/40 flex items-start justify-center p-4 pt-[8vh]" onClick={kapat}>
          <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 px-4 py-3 border-b border-line">
              <Search className="h-5 w-5 text-subtle" />
              <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)}
                placeholder="Öğrenci, veli, TC, telefon, öğretmen ara…"
                className="flex-1 bg-transparent outline-none text-sm text-content" />
              {yuk && <span className="text-xs text-subtle">…</span>}
              <button onClick={kapat} className="text-subtle hover:text-content"><X className="h-4 w-4" /></button>
            </div>

            <div className="max-h-[60vh] overflow-y-auto">
              {q.trim().length < 2 && <div className="p-6 text-center text-sm text-subtle">En az 2 karakter yazın. İpucu: TC veya telefon ile de arayabilirsiniz.</div>}
              {sonuc && (sonuc.ogrenciler.length + sonuc.ogretmenler.length) === 0 && q.trim().length >= 2 && !yuk && (
                <div className="p-6 text-center text-sm text-subtle">Sonuç bulunamadı.</div>
              )}

              {sonuc && sonuc.ogrenciler.length > 0 && (
                <div className="p-2">
                  <div className="px-2 py-1 text-[11px] font-semibold text-subtle uppercase tracking-wide">Öğrenciler</div>
                  {sonuc.ogrenciler.map((o) => (
                    <button key={o.id} onClick={() => ogrenciSec(o)} className="w-full text-left flex items-start gap-2 rounded-lg px-2 py-2 hover:bg-app transition">
                      <GraduationCap className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-content flex items-center gap-2">{o.ad} {o.soyad} {durumRoz(o)}</div>
                        <div className="text-xs text-subtle truncate">
                          {o.sinif ? `${o.sinif}. sınıf` : ""}{o.kur ? ` · ${o.kur}` : ""}
                          {o.ogretmen_ad ? ` · ${o.ogretmen_ad}` : ""}
                          {o.veli_ad ? ` · Veli: ${o.veli_ad} ${o.veli_soyad || ""}` : ""}
                          {o.veli_tc ? ` · TC ${o.veli_tc}` : ""}{o.veli_telefon ? ` · ${o.veli_telefon}` : ""}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {sonuc && sonuc.ogretmenler.length > 0 && (
                <div className="p-2 border-t border-line">
                  <div className="px-2 py-1 text-[11px] font-semibold text-subtle uppercase tracking-wide">Öğretmenler</div>
                  {sonuc.ogretmenler.map((t) => (
                    <button key={t.id} onClick={() => ogretmenSec(t)} className="w-full text-left flex items-center gap-2 rounded-lg px-2 py-2 hover:bg-app transition">
                      <User className="h-4 w-4 text-indigo-500 shrink-0" />
                      <div className="text-sm text-content">{t.ad} {t.soyad}<span className="text-xs text-subtle ml-2">{t.telefon || ""}{t.brans ? ` · ${t.brans}` : ""}</span></div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
