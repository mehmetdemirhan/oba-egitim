import React from "react";

/**
 * Logo — OBA marka logosu (tek merkezî bileşen).
 * Önceden login + panel başlıklarında dağınık/inline tanımlıydı; hepsi buraya alındı.
 *
 * Props:
 *   size     — "sm" | "md" | "lg" | "xl"   (varsayılan "md")
 *   showText — bool: ikon yanında metin göster (varsayılan true)
 *   text     — metin (varsayılan "Okuma Becerileri Akademisi")
 *   variant  — "light" | "dark": metin rengi (koyu zemin için "dark")
 */
const BOYUT = {
  sm: { box: 32, icon: 18, radius: 9, font: "text-sm" },
  md: { box: 44, icon: 24, radius: 12, font: "text-lg" },
  lg: { box: 56, icon: 30, radius: 14, font: "text-xl" },
  xl: { box: 64, icon: 34, radius: 16, font: "text-2xl" },
};

export default function Logo({ size = "md", showText = true, text = "Okuma Becerileri Akademisi", variant = "light" }) {
  const b = BOYUT[size] || BOYUT.md;
  return (
    <div className="flex items-center gap-3">
      <div
        style={{
          width: b.box, height: b.box, borderRadius: b.radius,
          background: "linear-gradient(135deg, #F97316, #EF4444)",
          boxShadow: "0 6px 18px rgba(249,115,22,0.28)",
        }}
        className="flex items-center justify-center flex-shrink-0"
      >
        <svg width={b.icon} height={b.icon} viewBox="0 0 24 24" fill="none" stroke="white"
             strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
        </svg>
      </div>
      {showText && (
        <span className={`font-bold leading-tight ${b.font} ${variant === "dark" ? "text-white" : "text-gray-800"}`}>
          {text}
        </span>
      )}
    </div>
  );
}
