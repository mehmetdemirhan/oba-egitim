import React, { useState } from "react";
import { ChevronDown, ChevronRight, LineChart } from "lucide-react";
import BilgiIkonu from "../BilgiIkonu";

/**
 * Dashboard TEK KART SİSTEMİ — tüm dashboard kartları (KPI + grafik + tablo)
 * aynı görsel aileden gelsin diye ortak kabuk. KURAL: her kart başlığı =
 * ikon çipi + başlık + sağda tutarlı sıra (opsiyonel sagUst → (i) bilgi varsa
 * → aç/kapa chevron varsa). Seçmeli/keyfi değil; hepsi aynı düzen.
 */
export function DashboardKart({
  baslik, ikon: Ikon, bilgi, sagUst, acilir = true,
  varsayilanAcik = true, className = "", govdeClass = "p-4", children,
}) {
  const [acik, setAcik] = useState(varsayilanAcik);
  return (
    <section className={"rounded-2xl border border-line bg-surface shadow-sm overflow-hidden flex flex-col " + className}>
      <header className="flex items-center gap-2.5 px-4 py-3 border-b border-line">
        {Ikon && (
          <span className="grid place-items-center w-8 h-8 rounded-lg bg-primary/10 text-primary shrink-0">
            <Ikon className="h-4 w-4" />
          </span>
        )}
        <h3 className="font-semibold text-content text-sm flex-1 min-w-0 truncate">{baslik}</h3>
        <div className="flex items-center gap-1 shrink-0">
          {sagUst}
          {bilgi && <BilgiIkonu k={bilgi} />}
          {acilir && (
            <button type="button" onClick={() => setAcik((a) => !a)}
              aria-label={acik ? "Kapat" : "Aç"} aria-expanded={acik}
              className="text-subtle hover:text-content transition-colors p-0.5 rounded">
              {acik ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
          )}
        </div>
      </header>
      {(!acilir || acik) && <div className={govdeClass + " flex-1"}>{children}</div>}
    </section>
  );
}

/**
 * StatKart — KPI şeridi kartı. Grafik kartlarıyla AYNI kabuk ailesi (border-line,
 * rounded-2xl, shadow-sm); sadece içerik kompakt istatistik. Semantik renk ton
 * çipiyle. Tıklanabilirse hover + cursor.
 */
export function StatKart({ etiket, deger, altYazi, ikon: Ikon, ton = "bilgi", onClick, sagUst, vurgulu = false }) {
  const TONLAR = {
    bilgi: "bg-blue-500/12 text-blue-600",
    basari: "bg-emerald-500/12 text-emerald-600",
    uyari: "bg-amber-500/12 text-amber-600",
    tehlike: "bg-red-500/12 text-red-600",
    notr: "bg-slate-500/12 text-slate-500",
  };
  return (
    <div onClick={onClick} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } } : undefined}
      className={"rounded-2xl border bg-surface shadow-sm p-4 transition-colors " +
        (vurgulu ? "border-red-300 border-l-4 border-l-red-500 " : "border-line ") +
        (onClick ? "cursor-pointer hover:border-primary/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40" : "")}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-subtle font-medium truncate">{etiket}</span>
        <span className="flex items-center gap-1 shrink-0">
          {sagUst}
          {Ikon && <span className={"grid place-items-center w-7 h-7 rounded-lg " + (TONLAR[ton] || TONLAR.bilgi)}><Ikon className="h-4 w-4" /></span>}
        </span>
      </div>
      <div className={"text-3xl font-bold tabular-nums mt-1.5 " + (vurgulu ? "text-red-700" : "text-content")}>{deger}</div>
      {altYazi && <div className={"text-xs mt-0.5 " + (vurgulu ? "text-red-500" : "text-subtle")}>{altYazi}</div>}
    </div>
  );
}

/**
 * Bolum — adlandırılmış dashboard bölümü (başlık + ince ayraç). Kartları uzun
 * tek akış yerine anlamlı gruplara ayırır.
 */
export function Bolum({ baslik, aciklama, children, sag }) {
  return (
    <section className="space-y-3">
      <div className="flex items-end justify-between gap-3 border-b border-line pb-2">
        <div className="min-w-0">
          <h2 className="text-sm font-bold text-content uppercase tracking-wide">{baslik}</h2>
          {aciklama && <p className="text-xs text-subtle mt-0.5">{aciklama}</p>}
        </div>
        {sag && <div className="shrink-0">{sag}</div>}
      </div>
      {children}
    </section>
  );
}

/**
 * BosDurum — 12 aylık bir grafikte yeterli veri yokken zarif özet/placeholder.
 * Boş eksenleri göstermek yerine "veri birikince trend görünecek + mevcut özet".
 * ("veri yoksa —" dürüstlük ilkesiyle aynı ruhta.)
 */
export function BosDurum({ minAy = 3, ozet, mesaj }) {
  return (
    <div className="h-full min-h-[180px] flex flex-col items-center justify-center text-center gap-2.5 px-4 py-6">
      <span className="grid place-items-center w-11 h-11 rounded-full bg-app text-subtle">
        <LineChart className="h-5 w-5" />
      </span>
      <p className="text-sm text-subtle max-w-xs leading-relaxed">
        {mesaj || `Yeterli geçmiş veri birikince (en az ${minAy} ay) trend burada görünecek.`}
      </p>
      {ozet && ozet.length > 0 && (
        <div className="mt-1 flex flex-wrap justify-center gap-2">
          {ozet.map((o, i) => (
            <div key={i} className="rounded-xl border border-line bg-app px-3 py-1.5">
              <div className="text-[11px] text-subtle">{o.etiket}</div>
              <div className="text-base font-bold text-content tabular-nums leading-tight">{o.deger}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
