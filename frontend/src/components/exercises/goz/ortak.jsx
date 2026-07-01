// Göz egzersizleri ortak altyapısı.
// Tüm yeni göz/görme egzersizleri bu yardımcıları kullanır — tek tasarım dili,
// tek başlat/durdur/süre mantığı, tek ses motoru (WebAudio, dış dosya yok).
import React, { useCallback, useEffect, useRef, useState } from "react";
import { YardimBaloncugu } from "../ExerciseAyarlar";
import { useFullscreenExercise } from "../../../context/FullscreenExerciseContext";
import { Settings } from "lucide-react";

// ── WebAudio metronom / bip ─────────────────────────────────────────────
// Dış ses dosyası yok; kısa sinüs tonu üretir. 13 Nokta gibi metronomlu
// egzersizlerde ve doğru/yanlış geri bildiriminde kullanılır.
let _ac = null;
function _audioCtx() {
  if (typeof window === "undefined") return null;
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  if (!_ac) _ac = new AC();
  if (_ac.state === "suspended") _ac.resume().catch(() => {});
  return _ac;
}

export function bipCal(freq = 880, sure = 0.08, ses = 0.15) {
  const ac = _audioCtx();
  if (!ac) return;
  const osc = ac.createOscillator();
  const gain = ac.createGain();
  osc.type = "sine";
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(ses, ac.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + sure);
  osc.connect(gain).connect(ac.destination);
  osc.start();
  osc.stop(ac.currentTime + sure);
}

export const dogruSes = () => bipCal(660, 0.12, 0.12);
export const yanlisSes = () => bipCal(180, 0.18, 0.14);

// ── Oturum hook'u — başlat/durdur + geri sayım ──────────────────────────
// sure=0 → süresiz (interaktif skor egzersizleri). onTamamla süre dolunca
// (veya bileşen elle çağırınca) puanlama için tetiklenir.
export function useEgzersizOturum({ sure = 30, onTamamla }) {
  const [calisiyor, setCalisiyor] = useState(false);
  const [kalan, setKalan] = useState(sure);
  const tamamlandiRef = useRef(false);

  const baslat = useCallback(() => {
    tamamlandiRef.current = false;
    setKalan(sure);
    setCalisiyor(true);
  }, [sure]);

  const durdur = useCallback(() => setCalisiyor(false), []);

  const bitir = useCallback(() => {
    setCalisiyor(false);
    if (!tamamlandiRef.current) {
      tamamlandiRef.current = true;
      onTamamla && onTamamla();
    }
  }, [onTamamla]);

  useEffect(() => {
    if (!calisiyor || sure <= 0) return;
    if (kalan <= 0) { bitir(); return; }
    const t = setTimeout(() => setKalan((k) => k - 1), 1000);
    return () => clearTimeout(t);
  }, [calisiyor, kalan, sure, bitir]);

  return { calisiyor, kalan, setKalan, baslat, durdur, bitir };
}

// ── Canvas sahnesi — rAF döngüsü + retina + otomatik yeniden boyutlama ───
// ciz(ctx, W, H, t): her karede çağrılır. t saniye-benzeri artan zaman (hız'a bağlı).
export function CanvasSahne({ ciz, calisiyor, hiz = 1, className = "", style }) {
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const cizRef = useRef(ciz);
  cizRef.current = ciz;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const resize = () => {
      const w = canvas.offsetWidth, h = canvas.offsetHeight;
      canvas.width = Math.max(1, Math.floor(w * dpr));
      canvas.height = Math.max(1, Math.floor(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);
    // Tam ekran/panel geçişlerinde pencere boyutu değişmeden yükseklik değişebilir;
    // ResizeObserver ile canvas'ı kendi kutusuna göre yeniden ölçekle.
    let ro = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(() => resize());
      ro.observe(canvas);
    }

    let t = 0;
    const loop = () => {
      const W = canvas.offsetWidth, H = canvas.offsetHeight;
      t += 0.02 * hiz;
      ctx.clearRect(0, 0, W, H);
      cizRef.current && cizRef.current(ctx, W, H, t);
      animRef.current = requestAnimationFrame(loop);
    };
    if (calisiyor) loop();
    else { ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight); }

    return () => {
      window.removeEventListener("resize", resize);
      if (ro) ro.disconnect();
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [calisiyor, hiz]);

  return <canvas ref={canvasRef} className={`w-full h-full ${className}`} style={style} />;
}

// ── Merkezi egzersiz düzeni ──────────────────────────────────────────────
// Üst ince kontrol satırı (Başlat/Durdur + süre + ⚙️ ayar + ? yardım) ve
// altında MAKSİMUM alanı kaplayan sahne. Ayarlar sağdan slide-in panelde;
// açıklama "?" popover'ında. Tam ekran modunda sahne viewport'u doldurur.
//
// Props:
//   calisiyor, kalan, sure, baslat, durdur — oturum kontrolü (useEgzersizOturum)
//   ayarlar   — ayar paneli içeriği (JSX: Slider/SesToggle...). Yoksa ⚙️ gizlenir.
//   aciklama  — "?" popover metni. Yoksa ? gizlenir.
//   koyu      — sahne zemini koyu mu (canvas için true, grid için false)
//   children  — sahne içeriği (canvas veya grid)
export function EgzersizDuzen({ calisiyor, kalan, sure = 0, baslat, durdur, ayarlar, aciklama, koyu = true, children }) {
  const [ayarAcik, setAyarAcik] = useState(false);
  const menuRef = useRef(null);
  const { isFullscreen } = useFullscreenExercise();
  // Sahne mümkün olan en büyük alanı kaplasın; alttaki boşluk kalmasın.
  const yukseklik = isFullscreen ? "calc(100vh - 88px)" : "clamp(440px, 82vh, 1200px)";

  // Dışarı tıklama / ESC ile ayar menüsünü kapat.
  useEffect(() => {
    if (!ayarAcik) return;
    const disaTikla = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setAyarAcik(false); };
    const esc = (e) => { if (e.key === "Escape") setAyarAcik(false); };
    document.addEventListener("mousedown", disaTikla);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", disaTikla); document.removeEventListener("keydown", esc); };
  }, [ayarAcik]);

  return (
    <div>
      {/* Üst ince kontrol satırı */}
      <div className="flex items-center justify-end gap-2 mb-2">
        {sure > 0 && (
          <span className={`mr-1 text-lg font-bold ${kalan <= 5 ? "text-red-500" : "text-gray-700"}`}>{kalan}s</span>
        )}
        {baslat && (
          <button onClick={() => (calisiyor ? durdur() : baslat())}
            className={`px-4 py-1.5 rounded-lg text-sm font-semibold text-white transition ${calisiyor ? "bg-red-500 hover:bg-red-600" : "bg-green-500 hover:bg-green-600"}`}>
            {calisiyor ? "⏸ Durdur" : "▶ Başlat"}
          </button>
        )}
        {ayarlar && (
          <div className="relative" ref={menuRef}>
            <button onClick={() => setAyarAcik((a) => !a)} title="Ayarlar" aria-label="Ayarlar"
              className={`w-9 h-9 rounded-lg border flex items-center justify-center transition ${ayarAcik ? "bg-indigo-50 border-indigo-300 text-indigo-600" : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"}`}>
              <Settings className="w-5 h-5" />
            </button>
            {/* Çarka tıklayınca sağdan aşağı açılan ayar menüsü */}
            {ayarAcik && (
              <div className="absolute right-0 top-full mt-2 z-[71] w-72 max-w-[90vw] max-h-[72vh] overflow-y-auto bg-white rounded-xl border border-gray-200 shadow-2xl p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-gray-800 flex items-center gap-1.5"><Settings className="w-4 h-4" /> Ayarlar</h4>
                  <button onClick={() => setAyarAcik(false)} className="w-7 h-7 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-400">✕</button>
                </div>
                {ayarlar}
              </div>
            )}
          </div>
        )}
        {aciklama && <YardimBaloncugu metin={aciklama} />}
      </div>

      {/* Sahne — maksimum alan */}
      <div className={`rounded-2xl border overflow-hidden ${koyu ? "bg-gray-900 border-gray-800" : "bg-gray-50 border-gray-200"}`}
        style={{ height: yukseklik }}>
        {children}
      </div>
    </div>
  );
}

export function Slider({ etiket, deger, min, max, step = 1, birim = "", onChange }) {
  return (
    <div>
      <label className="text-xs text-gray-500 block mb-1">{etiket}</label>
      <input type="range" min={min} max={max} step={step} value={deger}
        onChange={(e) => onChange(step % 1 === 0 ? parseInt(e.target.value, 10) : parseFloat(e.target.value))}
        className="w-full" />
      <span className="text-xs font-medium">{deger}{birim}</span>
    </div>
  );
}

export function SesToggle({ acik, onChange }) {
  return (
    <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer self-end">
      <input type="checkbox" checked={acik} onChange={(e) => onChange(e.target.checked)} className="accent-indigo-600" />
      🔔 Metronom sesi
    </label>
  );
}

// Skor rozeti.
export function Skor({ deger }) {
  return <div className="mt-3 text-center text-sm font-bold text-green-600">Skor: {deger}</div>;
}

// Türkçe karakter havuzları (grid/harf egzersizleri için).
export const TR_HARFLER = "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ";
export const TR_KELIMELER = "okuma kitap harf sözcük metin sayfa satır anlam kalem defter sınıf tahta pencere kapı masa hikaye masal roman şiir yazar çocuk anne baba kardeş arkadaş oyun park bahçe çiçek ağaç güneş yıldız bulut rüzgar yağmur deniz nehir orman kuş kedi köpek balık araba tren uçak gemi yol sokak şehir köy".split(" ");

export function karistir(dizi) {
  const a = [...dizi];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
export const rastgele = (dizi) => dizi[Math.floor(Math.random() * dizi.length)];
