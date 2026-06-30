import React, { useEffect, useCallback } from "react";
import { useFullscreenExercise } from "../context/FullscreenExerciseContext";

/**
 * ExerciseStarter — her egzersiz/aktivite ekranını saran ortak kapsayıcı.
 *
 * Egzersiz doğrudan normal modda açılır (başlangıçta zorunlu seçim YOK).
 * Egzersizin üstünde küçük bir "⛶ Tam Ekran" düğmesi (ayar kontrolü) bulunur;
 * buna basınca uygulama içi tam sayfa moduna geçilir:
 *   - Panel header'ı + sekme bar'ı gizlenir
 *   - Sağ üstte sabit "✕ Tam Ekrandan Çık" düğmesi çıkar
 *
 * Tam ekrandan çıkış (düğme veya ESC) egzersizi YARIDA KESMEZ; sadece görünümü
 * normale döndürür — egzersiz state'i korunur. Bileşen DOM'dan kalkınca
 * (sekme değişimi vb.) tam ekran modu otomatik sıfırlanır.
 *
 * Props:
 *   title       — egzersiz adı (opsiyonel, erişilebilirlik etiketinde kullanılır)
 *   description — kısa açıklama (opsiyonel)
 *   icon        — emoji/ikon (opsiyonel, geriye dönük uyumluluk için kabul edilir)
 *   children    — egzersiz içeriği
 */
export default function ExerciseStarter({ title, children }) {
  const { isFullscreen, setIsFullscreen } = useFullscreenExercise();

  // Bileşen DOM'dan kalkınca (sekme değişimi vb.) tam ekran modunu sıfırla.
  useEffect(() => {
    return () => setIsFullscreen(false);
  }, [setIsFullscreen]);

  const tamEkraniAc = useCallback(() => setIsFullscreen(true), [setIsFullscreen]);
  const tamEkrandanCik = useCallback(() => setIsFullscreen(false), [setIsFullscreen]);

  // ESC ile tam ekrandan çık
  useEffect(() => {
    if (!isFullscreen) return;
    const onKey = (e) => { if (e.key === "Escape") tamEkrandanCik(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isFullscreen, tamEkrandanCik]);

  return (
    <div className="space-y-2">
      {/* Ayar kontrolü — egzersizi tam ekrana al */}
      {!isFullscreen && (
        <div className="flex justify-end">
          <button
            onClick={tamEkraniAc}
            title={title ? `${title} — tam ekran` : "Tam ekran"}
            className="flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-medium border border-gray-200 text-gray-600 bg-white hover:bg-gray-50 transition-all">
            ⛶ Tam Ekran
          </button>
        </div>
      )}

      {/* Tam ekran modunda sabit çıkış düğmesi */}
      {isFullscreen && (
        <button
          onClick={tamEkrandanCik}
          title="Tam ekrandan çık (ESC)"
          className="fixed top-3 right-3 z-[60] flex items-center gap-1 px-3 py-2 rounded-xl bg-white/90 backdrop-blur border border-gray-200 shadow-md text-sm font-medium text-gray-700 hover:bg-white transition-all">
          ✕ Tam Ekrandan Çık
        </button>
      )}

      {children}
    </div>
  );
}
