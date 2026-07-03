import React from "react";
import { SEVIYE_RENK, rozetPuan } from "./RozetKarti";

/**
 * RozetDetayPopup — bir rozetin detayını (koşul + durum) gösteren küçük pop-up.
 * Props: rozet, kazanildi, kazanmaTarihi, onKapat
 */
export default function RozetDetayPopup({ rozet, kazanildi, kazanmaTarihi, onKapat }) {
  if (!rozet) return null;
  const kosul = rozet.kosul || {};
  const kosulMetni =
    rozet.aciklama ||
    (kosul.metrik && kosul.metrik !== "manuel"
      ? `${kosul.metrik} ${kosul.operator || ""} ${kosul.esik ?? ""}`
      : "Manuel verilir");
  return (
    <div className="flex items-start gap-3 p-3 bg-white rounded-xl border border-gray-200 shadow-sm">
      <div className="text-3xl">{kazanildi ? rozet.ikon : "🔒"}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-bold text-sm">{rozet.ad}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${SEVIYE_RENK[rozet.seviye] || "bg-gray-100"}`}>
            {rozet.seviye}
          </span>
          <span className="text-xs text-orange-600 font-medium">+{rozetPuan(rozet)} puan</span>
        </div>
        <p className="text-xs text-gray-600 mt-1">{kosulMetni}</p>
        <div className="mt-2">
          {kazanildi ? (
            <span className="text-[11px] text-green-600 font-medium">
              ✓ Kazanıldı{kazanmaTarihi ? ` — ${String(kazanmaTarihi).slice(0, 10)}` : ""}
            </span>
          ) : (
            <span className="text-[11px] text-gray-400">Henüz kazanılmadı</span>
          )}
        </div>
      </div>
      <button onClick={onKapat} className="text-gray-400 hover:text-gray-600 text-sm">✕</button>
    </div>
  );
}
