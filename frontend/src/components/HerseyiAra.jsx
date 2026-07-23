import React, { useState, useEffect, useRef, useMemo } from "react";
import axios from "axios";
import { Search, X, CornerDownLeft, Compass, GraduationCap, User } from "lucide-react";
import { araKayitlar, KAYIT_SAYISI } from "../aramaRegistry";

/**
 * HerseyiAra — TEK, birleşik genel arama. Sistemdeki HER ŞEYİ tarar:
 *  1) Bölümler & Özellikler (tüm menü/sekme/alt-sekme registry'si — 73 kayıt, role göre)
 *  2) Öğrenciler / Öğretmenler (backend /ara — yalnız yetkili roller)
 * Bölüm seçilince ilgili sekmeye yönlendirir (oba-git olayı); kişi seçilince onOgrenciSec/
 * onOgretmenSec çağrılır. Ctrl/Cmd+K veya "/" ile açılır. Türkçe-toleranslı.
 */
const KISI_ROLLERI = ["admin", "coordinator", "teacher", "accountant"];

export default function HerseyiAra({ apiBase, user, onOgrenciSec, onOgretmenSec }) {
  const [acik, setAcik] = useState(false);
  const [q, setQ] = useState("");
  const [sec, setSec] = useState(0);
  const [kisiler, setKisiler] = useState({ ogrenciler: [], ogretmenler: [] });
  const inputRef = useRef(null);
  const sonRef = useRef(0);
  const rol = user?.role;
  const kisiArayabilir = KISI_ROLLERI.includes(rol);

  // Bölüm/özellik sonuçları (anında, istemci tarafı)
  const bolumler = useMemo(() => (acik ? araKayitlar(q, rol) : []), [q, rol, acik]);

  // Kişi araması (debounce, backend)
  useEffect(() => {
    if (!acik || !kisiArayabilir || q.trim().length < 2) { setKisiler({ ogrenciler: [], ogretmenler: [] }); return; }
    const istek = ++sonRef.current;
    const t = setTimeout(async () => {
      try {
        const r = await axios.get(`${apiBase}/ara`, { params: { q } });
        if (istek === sonRef.current) setKisiler(r.data);
      } catch (e) { if (istek === sonRef.current) setKisiler({ ogrenciler: [], ogretmenler: [] }); }
    }, 250);
    return () => clearTimeout(t);
  }, [q, acik, apiBase, kisiArayabilir]);

  // Düz liste (klavye gezinme için): bölümler → öğrenciler → öğretmenler
  const duzListe = useMemo(() => [
    ...bolumler.map((e) => ({ tur: "bolum", veri: e })),
    ...(kisiler.ogrenciler || []).map((o) => ({ tur: "ogrenci", veri: o })),
    ...(kisiler.ogretmenler || []).map((t) => ({ tur: "ogretmen", veri: t })),
  ], [bolumler, kisiler]);

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

  const kapat = () => { setAcik(false); setQ(""); setKisiler({ ogrenciler: [], ogretmenler: [] }); };
  const sec_et = (item) => {
    if (item.tur === "bolum") {
      window.__obaGitHedef = item.veri.hedef;
      window.dispatchEvent(new CustomEvent("oba-git", { detail: item.veri.hedef }));
    } else if (item.tur === "ogrenci") { onOgrenciSec && onOgrenciSec(item.veri); }
    else if (item.tur === "ogretmen") { onOgretmenSec && onOgretmenSec(item.veri); }
    kapat();
  };

  const klavye = (ev) => {
    if (!duzListe.length) return;
    if (ev.key === "ArrowDown") { ev.preventDefault(); setSec((s) => Math.min(s + 1, duzListe.length - 1)); }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); setSec((s) => Math.max(s - 1, 0)); }
    else if (ev.key === "Enter") { ev.preventDefault(); sec_et(duzListe[sec]); }
  };

  let idx = -1;  // global index across sections for highlight
  const sat = (item, ikon, baslik, altmetin) => {
    idx += 1; const i = idx;
    return (
      <button key={item.tur + (item.veri.id || item.veri.ad) + i} onClick={() => sec_et(item)} onMouseEnter={() => setSec(i)}
        className={`w-full text-left flex items-center gap-2 px-4 py-2.5 border-b border-line/40 last:border-0 transition ${i === sec ? "bg-app" : "hover:bg-app"}`}>
        {ikon}
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-content truncate">{baslik}</div>
          {altmetin && <div className="text-[11px] text-subtle truncate">{altmetin}</div>}
        </div>
        {i === sec && <CornerDownLeft className="h-3.5 w-3.5 text-subtle shrink-0" />}
      </button>
    );
  };

  const bosSonuc = q.trim().length >= 2 && duzListe.length === 0;

  return (
    <>
      <button onClick={() => setAcik(true)} title="Ara — bölüm, özellik, öğrenci, öğretmen (Ctrl+K)"
        className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-app px-2.5 py-1.5 text-sm text-subtle hover:text-content hover:border-primary transition">
        <Search className="h-4 w-4" /><span className="hidden sm:inline">Ara</span>
        <kbd className="hidden md:inline text-[10px] bg-surface border border-line rounded px-1">Ctrl K</kbd>
      </button>

      {acik && (
        <div className="fixed inset-0 z-[95] bg-black/40 flex items-start justify-center p-4 pt-[8vh]" onClick={kapat}>
          <div className="bg-surface rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 px-4 py-3 border-b border-line">
              <Search className="h-5 w-5 text-subtle" />
              <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={klavye}
                placeholder={kisiArayabilir ? "Her şeyi ara: bölüm, özellik, öğrenci, veli, TC, öğretmen…" : "Bölüm veya özellik ara…"}
                className="flex-1 bg-transparent outline-none text-sm text-content" />
              <button onClick={kapat} className="text-subtle hover:text-content"><X className="h-4 w-4" /></button>
            </div>

            <div className="max-h-[62vh] overflow-y-auto">
              {q.trim().length < 2 && (
                <div className="p-6 text-center text-sm text-subtle">
                  Aradığınız şeyin adını yazın; sistem sizi oraya götürsün.<br />
                  <span className="text-xs">Menüde görünmeyen bölümler dahil {KAYIT_SAYISI} özellik{kisiArayabilir ? " + kişiler" : ""} taranır.</span>
                </div>
              )}
              {bosSonuc && <div className="p-6 text-center text-sm text-subtle">🔍 Eşleşme bulunamadı. Farklı bir kelime deneyin.</div>}

              {bolumler.length > 0 && (
                <div>
                  <div className="px-4 py-1 text-[11px] font-semibold text-subtle uppercase tracking-wide bg-app/50">Bölümler & Özellikler</div>
                  {bolumler.map((e) => sat({ tur: "bolum", veri: e },
                    <Compass className="h-4 w-4 text-primary shrink-0" />, e.ad,
                    e.hedef.altSekme ? "Ayarlar → alt bölüm" : null))}
                </div>
              )}

              {(kisiler.ogrenciler || []).length > 0 && (
                <div>
                  <div className="px-4 py-1 text-[11px] font-semibold text-subtle uppercase tracking-wide bg-app/50">Öğrenciler</div>
                  {kisiler.ogrenciler.map((o) => sat({ tur: "ogrenci", veri: o },
                    <GraduationCap className="h-4 w-4 text-emerald-600 shrink-0" />,
                    `${o.ad} ${o.soyad}`,
                    `${o.sinif ? o.sinif + ". sınıf" : ""}${o.kur ? " · " + o.kur : ""}${o.ogretmen_ad ? " · " + o.ogretmen_ad : ""}${o.veli_ad ? " · Veli: " + o.veli_ad + " " + (o.veli_soyad || "") : ""}${o.veli_telefon ? " · " + o.veli_telefon : ""}`))}
                </div>
              )}

              {(kisiler.ogretmenler || []).length > 0 && (
                <div>
                  <div className="px-4 py-1 text-[11px] font-semibold text-subtle uppercase tracking-wide bg-app/50">Öğretmenler</div>
                  {kisiler.ogretmenler.map((t) => sat({ tur: "ogretmen", veri: t },
                    <User className="h-4 w-4 text-indigo-500 shrink-0" />,
                    `${t.ad} ${t.soyad}`, t.telefon || ""))}
                </div>
              )}
            </div>
            <div className="px-4 py-2 border-t border-line text-[11px] text-subtle flex items-center justify-between">
              <span>↑↓ gez · ↵ git · Esc kapat</span>
              <span>Bölüm + kişi araması</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
