import React, { useEffect, useCallback } from "react";
import SecmeliRender from "./SecmeliRender";

/**
 * Fonolojik Farkındalık render bileşeni (FAZ 5 — 1-2. sınıf).
 * İçerik şeması: { sorular: [{ soru, secenekler, dogru, seslendir }] }
 *
 * Tüm fonoloji alt tipleri (hece sayma, hece/ses birleştirme, ilk/son ses,
 * kafiye, ses çıkarma) bu bileşeni kullanır. Küçük yaş grubu için her soruda
 * 🔊 "Dinle" düğmesi vardır; tarayıcının Web Speech API'si (window.speechSynthesis)
 * ile 'seslendir' metni (yoksa soru) Türkçe okunur — backend'e yük binmez.
 *
 * Render sözleşmesi: { icerik, onCevap, soruNo }
 */
const sesDestegi = () =>
  typeof window !== "undefined" && "speechSynthesis" in window;

function seslendir(metin) {
  if (!sesDestegi() || !metin) return;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(metin);
    u.lang = "tr-TR";
    u.rate = 0.85;
    window.speechSynthesis.speak(u);
  } catch (e) {
    /* sessiz geç — ses olmadan da egzersiz çözülebilir */
  }
}

export default function FonolojiRender({ icerik, onCevap, soruNo }) {
  const soru = (icerik?.sorular || [])[soruNo];
  const okunacak = soru?.seslendir || soru?.soru || "";

  const dinle = useCallback(() => seslendir(okunacak), [okunacak]);

  // Soru değişince otomatik bir kez seslendir (kullanıcı egzersizi zaten
  // tıklayarak başlattığı için tarayıcı otomatik oynatmaya genelde izin verir).
  useEffect(() => {
    if (okunacak) seslendir(okunacak);
    return () => { if (sesDestegi()) window.speechSynthesis.cancel(); };
  }, [okunacak]);

  if (!soru) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between bg-orange-50 border border-orange-200 rounded-2xl px-4 py-3">
        <span className="text-sm font-semibold text-orange-600">🎧 Dinle ve doğru cevabı seç</span>
        <button
          onClick={dinle}
          disabled={!sesDestegi()}
          title={sesDestegi() ? "Sesli oku" : "Tarayıcı sesi desteklemiyor"}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-orange-500 text-white text-sm font-semibold shadow-sm hover:bg-orange-600 disabled:opacity-40 transition">
          🔊 Dinle
        </button>
      </div>
      <SecmeliRender icerik={icerik} onCevap={onCevap} soruNo={soruNo} />
    </div>
  );
}
