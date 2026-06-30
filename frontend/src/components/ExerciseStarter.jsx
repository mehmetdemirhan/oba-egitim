import React, { useState, useEffect, useCallback } from "react";
import { useFullscreenExercise } from "../context/FullscreenExerciseContext";

/**
 * ExerciseStarter — her egzersiz/aktivite ekranını saran ortak başlatıcı.
 *
 * 1. Egzersiz açıldığında önce bir "başlangıç kartı" gösterir:
 *      - Egzersizin adı + kısa açıklaması
 *      - "Normal Modda Başlat"  → header/sekmeler görünür kalır
 *      - "Tam Ekran Başlat"     → uygulama içi tam sayfa modu (header/sekme gizlenir)
 *    Kullanıcı seçim yapana kadar egzersiz (children) render edilmez.
 *
 * 2. "Tam Ekran Başlat" seçilince global fullscreen state açılır; paneller
 *    header + sekme bar'ını gizler. Sağ üstte küçük bir "✕ Çıkış" butonu çıkar.
 *
 * 3. Tam ekrandan çıkış (buton veya ESC) egzersizi YARIDA KESMEZ; sadece görünümü
 *    normale döndürür — egzersiz state'i korunur.
 *
 * Props:
 *   title       — egzersiz adı (zorunlu)
 *   description — kısa açıklama (opsiyonel)
 *   icon        — emoji/ikon (opsiyonel)
 *   children    — egzersiz içeriği
 */
export default function ExerciseStarter({ title, description, icon, children }) {
  // null = henüz başlatılmadı; "normal" | "fullscreen" = başlatıldı
  const [mode, setMode] = useState(null);
  const { setIsFullscreen } = useFullscreenExercise();

  // Tam ekran modunda global state'i aç, diğer durumlarda kapat.
  useEffect(() => {
    setIsFullscreen(mode === "fullscreen");
  }, [mode, setIsFullscreen]);

  // Bileşen DOM'dan kalkınca (sekme değişimi vb.) global modu sıfırla.
  useEffect(() => {
    return () => setIsFullscreen(false);
  }, [setIsFullscreen]);

  // Tam ekrandan çık ama egzersizi koru → mode "normal"
  const tamEkrandanCik = useCallback(() => setMode("normal"), []);

  // ESC ile tam ekrandan çık
  useEffect(() => {
    if (mode !== "fullscreen") return;
    const onKey = (e) => { if (e.key === "Escape") tamEkrandanCik(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, tamEkrandanCik]);

  // ── Başlangıç kartı ──
  if (mode === null) {
    return (
      <div className="flex items-center justify-center py-6 px-2">
        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-6 sm:p-8 max-w-md w-full text-center">
          {icon && <div className="text-4xl mb-3">{icon}</div>}
          <h2 className="text-xl font-bold text-gray-900 mb-2">{title}</h2>
          {description && (
            <p className="text-gray-500 text-sm mb-6 leading-relaxed">{description}</p>
          )}
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => setMode("normal")}
              className="flex-1 px-4 py-3 rounded-2xl font-medium text-sm border border-gray-200 text-gray-700 hover:bg-gray-50 transition-all">
              Normal Modda Başlat
            </button>
            <button
              onClick={() => setMode("fullscreen")}
              className="flex-1 px-4 py-3 rounded-2xl font-medium text-sm bg-gradient-to-r from-orange-500 to-red-500 text-white shadow-sm hover:opacity-90 transition-all">
              ⛶ Tam Ekran Başlat
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Egzersiz başladı ──
  return (
    <>
      {mode === "fullscreen" && (
        <button
          onClick={tamEkrandanCik}
          title="Tam ekrandan çık (ESC)"
          className="fixed top-3 right-3 z-[60] flex items-center gap-1 px-3 py-2 rounded-xl bg-white/90 backdrop-blur border border-gray-200 shadow-md text-sm font-medium text-gray-700 hover:bg-white transition-all">
          ✕ Çıkış
        </button>
      )}
      {children}
    </>
  );
}
