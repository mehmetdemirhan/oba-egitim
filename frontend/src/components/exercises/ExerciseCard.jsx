import React from "react";

/**
 * ExerciseCard — tüm egzersizler için tek, tutarlı kart bileşeni.
 *
 * Klasik (eski komponente giden) ve yeni (ExerciseEngine) egzersizler AYNI kartı
 * kullanır; kullanıcı için bu ayrım görünmez. Kategoriye göre renklendirilir.
 *
 * Props:
 *   ad       — egzersiz adı
 *   aciklama — 1-2 satır kısa açıklama
 *   ikon     — emoji/ikon
 *   renk     — [from, to] gradient renkleri veya tek renk string
 *   onClick  — tıklama işleyicisi (klasik: eski komponenti açar, yeni: motoru başlatır)
 *   disabled — pasif durum
 */
export default function ExerciseCard({ ad, aciklama, ikon, renk, onClick, disabled = false }) {
  const style = Array.isArray(renk)
    ? { backgroundImage: `linear-gradient(135deg, ${renk[0]}, ${renk[1]})` }
    : { backgroundColor: renk || "#64748B" };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={style}
      className="relative text-left rounded-[20px] p-5 text-white flex flex-col min-h-[150px]
                 shadow-[0_4px_12px_rgba(0,0,0,0.08)] transition-all duration-150
                 hover:scale-[1.02] hover:shadow-[0_8px_20px_rgba(0,0,0,0.18)]
                 active:scale-[0.98] disabled:opacity-50 disabled:hover:scale-100
                 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/70">
      <div className="text-[40px] leading-none mb-2 drop-shadow-sm">{ikon || "📝"}</div>
      <div className="font-bold text-[15px] leading-tight">{ad}</div>
      {aciklama && (
        <div className="text-[12px] font-normal text-white/90 mt-1 leading-snug line-clamp-3">
          {aciklama}
        </div>
      )}
    </button>
  );
}
