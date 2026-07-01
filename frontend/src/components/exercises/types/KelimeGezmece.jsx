import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import KelimeGezmeceHarfDairesi from "./KelimeGezmeceHarfDairesi";
import KelimeGezmeceMascot from "./KelimeGezmeceMascot";

/**
 * KelimeGezmece — çapraz bulmaca harf oyunu (egzersiz tipi: kelime_gezmece).
 *
 * İçerik şeması:
 *   { harf_havuzu, grid (2D '.'/harf), kelimeler:[{kelime,yon,baslangic:[r,c],uzunluk}],
 *     bonus_kelimeler:[...], tema:{ad,emoji,ana_renk_hex} }
 *
 * Doğrulama İSTEMCİ tarafında yapılır (içerik grid + bonus listelerini taşır);
 * tüm grid kelimeleri bulununca onCevap(true) ile motora tek seferlik başarı
 * bildirilir (puanlama=serbest → tam XP). Oyun-içi puan: grid +10 / bonus +15 /
 * ipucu -20 (çocuk-yüzlü sayaçta).
 *
 * Görsel dil: modern çocuk uygulaması (Sago Mini / Pok Pok) — krem zemin, pastel
 * bloblar, squircle taşlar, yumuşak animasyonlar, bulut maskot. SADECE bu oyuna
 * özeldir; diğer egzersizleri etkilemez.
 *
 * Render sözleşmesi: { icerik, onCevap }.
 */
const trKucuk = (s) => (s || "").toLocaleLowerCase("tr").replace(/\s+/g, "");
const anahtar = (r, c) => `${r},${c}`;

// Pastel palet (FAZ C)
const KREM = "#FFF8F0";
const METIN = "#3D405B";
const KONFETI_RENK = ["#FFDD67", "#FFB5A7", "#A7E8BD", "#BFE6FF", "#C7B8EA"];

// ── Hafif WebAudio ses sentezi (harici dosya yok, çevrimdışı çalışır) ──
let _ac = null;
function _ctx() {
  if (typeof window === "undefined") return null;
  try {
    if (!_ac) _ac = new (window.AudioContext || window.webkitAudioContext)();
    if (_ac.state === "suspended") _ac.resume();
    return _ac;
  } catch {
    return null;
  }
}
function _nota(frek, baslangic = 0, sure = 0.14, kazanc = 0.06, tip = "sine") {
  const ac = _ctx();
  if (!ac) return;
  const t = ac.currentTime + baslangic;
  const osc = ac.createOscillator();
  const g = ac.createGain();
  osc.type = tip;
  osc.frequency.value = frek;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(kazanc, t + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, t + sure);
  osc.connect(g).connect(ac.destination);
  osc.start(t);
  osc.stop(t + sure + 0.02);
}
const SES = {
  pop: () => _nota(440, 0, 0.08, 0.04, "triangle"),
  dogru: () => { _nota(659, 0, 0.16, 0.06); _nota(988, 0.05, 0.16, 0.05); },
  bonus: () => { _nota(784, 0, 0.14); _nota(1047, 0.08, 0.14); _nota(1319, 0.16, 0.18); },
  bitir: () => { [523, 659, 784, 1047].forEach((f, i) => _nota(f, i * 0.1, 0.3, 0.05)); },
};

export default function KelimeGezmece({ icerik, onCevap }) {
  const tema = icerik?.tema || { ad: "Oyun", emoji: "🧩", ana_renk_hex: "#A7E8BD" };
  const anaRenk = tema.ana_renk_hex || "#A7E8BD";
  const harfHavuzu = useMemo(() => icerik?.harf_havuzu || [], [icerik]);
  const grid = useMemo(() => icerik?.grid || [["."]], [icerik]);
  const gridKelimeler = useMemo(() => icerik?.kelimeler || [], [icerik]);
  const bonusListesi = useMemo(
    () => new Set((icerik?.bonus_kelimeler || []).map(trKucuk)),
    [icerik]
  );

  const kelimeHucreleri = useMemo(() => {
    const m = {};
    for (const k of gridKelimeler) {
      const [r, c] = k.baslangic || [0, 0];
      const yatay = k.yon === "yatay";
      const huc = [];
      for (let i = 0; i < (k.uzunluk || 0); i++) huc.push(yatay ? [r, c + i] : [r + i, c]);
      m[trKucuk(k.kelime)] = huc;
    }
    return m;
  }, [gridKelimeler]);

  const gridKelimeSet = useMemo(
    () => new Set(gridKelimeler.map((k) => trKucuk(k.kelime))),
    [gridKelimeler]
  );

  const [bulunanGrid, setBulunanGrid] = useState(() => new Set());
  const [bulunanBonus, setBulunanBonus] = useState(() => new Set());
  const [acikHucreler, setAcikHucreler] = useState(() => new Set());
  const [puan, setPuan] = useState(0);
  const [ipucuSayisi, setIpucuSayisi] = useState(0);
  const [seciliIdx, setSeciliIdx] = useState([]);
  const [mesaj, setMesaj] = useState(null);
  const [balon, setBalon] = useState(null); // bonus balonu {metin}
  const [titre, setTitre] = useState(false);
  const [bitti, setBitti] = useState(false);
  const [sifirla, setSifirla] = useState(0);
  const [karistir, setKaristir] = useState(0);
  const [sessiz, setSessiz] = useState(false);
  const [mascot, setMascot] = useState({ durum: "idle", tetik: 0 });
  const [boyut, setBoyut] = useState(260);

  const cevapGonderildiRef = useRef(false);
  const mesajZamanRef = useRef(null);
  const balonZamanRef = useRef(null);
  const sessizRef = useRef(false);
  useEffect(() => { sessizRef.current = sessiz; }, [sessiz]);

  // Fredoka fontunu bir kez dinamik ekle (App.js'e dokunmadan)
  useEffect(() => {
    const id = "kg-fredoka-font";
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&display=swap";
    document.head.appendChild(link);
  }, []);

  // Responsive harf tabağı boyutu
  useEffect(() => {
    const guncelle = () => {
      const w = typeof window !== "undefined" ? window.innerWidth : 400;
      setBoyut(Math.max(220, Math.min(300, w - 80)));
    };
    guncelle();
    window.addEventListener("resize", guncelle);
    return () => window.removeEventListener("resize", guncelle);
  }, []);

  useEffect(() => {
    setBulunanGrid(new Set());
    setBulunanBonus(new Set());
    setAcikHucreler(new Set());
    setPuan(0);
    setIpucuSayisi(0);
    setSeciliIdx([]);
    setMesaj(null);
    setBalon(null);
    setBitti(false);
    cevapGonderildiRef.current = false;
  }, [icerik]);

  const gorunurHucreler = useMemo(() => {
    const s = new Set(acikHucreler);
    for (const k of bulunanGrid) {
      for (const [r, c] of kelimeHucreleri[k] || []) s.add(anahtar(r, c));
    }
    return s;
  }, [bulunanGrid, acikHucreler, kelimeHucreleri]);

  const ses = useCallback((ad) => {
    if (sessizRef.current) return;
    try { SES[ad] && SES[ad](); } catch { /* yoksay */ }
  }, []);

  const mascotTetikle = useCallback((durum) => {
    setMascot((m) => ({ durum, tetik: m.tetik + 1 }));
    if (durum !== "idle") {
      setTimeout(() => setMascot((m) => ({ durum: "idle", tetik: m.tetik })), 1000);
    }
  }, []);

  const mesajGoster = useCallback((tip, metin) => {
    setMesaj({ tip, metin });
    clearTimeout(mesajZamanRef.current);
    mesajZamanRef.current = setTimeout(() => setMesaj(null), 1400);
  }, []);

  const balonGoster = useCallback((metin) => {
    setBalon({ metin });
    clearTimeout(balonZamanRef.current);
    balonZamanRef.current = setTimeout(() => setBalon(null), 900);
  }, []);

  useEffect(() => {
    if (
      gridKelimeSet.size > 0 &&
      bulunanGrid.size >= gridKelimeSet.size &&
      !cevapGonderildiRef.current
    ) {
      cevapGonderildiRef.current = true;
      setBitti(true);
      ses("bitir");
      mascotTetikle("kutla");
      onCevap && onCevap(true);
    }
  }, [bulunanGrid, gridKelimeSet, onCevap, ses, mascotTetikle]);

  const kelimeDenetle = useCallback(
    (kelime) => {
      const w = trKucuk(kelime);
      if (!w || w.length < 2) return;
      if (bulunanGrid.has(w) || bulunanBonus.has(w)) {
        mesajGoster("tekrar", `“${w.toUpperCase()}” zaten bulundu`);
        return;
      }
      if (gridKelimeSet.has(w)) {
        setBulunanGrid((s) => new Set(s).add(w));
        setPuan((p) => p + 10);
        mesajGoster("grid", `✓ ${w.toUpperCase()} (+10)`);
        ses("dogru");
        mascotTetikle("zipla");
        return;
      }
      if (bonusListesi.has(w)) {
        setBulunanBonus((s) => new Set(s).add(w));
        setPuan((p) => p + 15);
        mesajGoster("bonus", `⭐ Bonus: ${w.toUpperCase()} (+15)`);
        balonGoster(`+15 ⭐`);
        ses("bonus");
        mascotTetikle("kutla");
        return;
      }
      setTitre(true);
      setTimeout(() => setTitre(false), 320);
      mesajGoster("hata", `“${w.toUpperCase()}” listede yok`);
    },
    [bulunanGrid, bulunanBonus, gridKelimeSet, bonusListesi, mesajGoster, balonGoster, ses, mascotTetikle]
  );

  const onTamamla = useCallback(
    (indeksler) => {
      const kelime = indeksler.map((i) => harfHavuzu[i] || "").join("");
      kelimeDenetle(kelime);
      setSifirla((s) => s + 1);
    },
    [harfHavuzu, kelimeDenetle]
  );

  const onSecim = useCallback((idx) => {
    setSeciliIdx(idx);
    if (idx.length) ses("pop");
  }, [ses]);

  const gonderBtn = () => { if (seciliIdx.length) onTamamla(seciliIdx); };

  const ipucuVer = () => {
    const eksik = gridKelimeler
      .map((k) => trKucuk(k.kelime))
      .filter((w) => !bulunanGrid.has(w))
      .sort((a, b) => a.length - b.length);
    for (const w of eksik) {
      const gizli = (kelimeHucreleri[w] || []).find(
        ([r, c]) => !gorunurHucreler.has(anahtar(r, c))
      );
      if (gizli) {
        setAcikHucreler((s) => new Set(s).add(anahtar(gizli[0], gizli[1])));
        setPuan((p) => Math.max(0, p - 20));
        setIpucuSayisi((n) => n + 1);
        mesajGoster("ipucu", "💡 Bir harf açıldı (−20)");
        return;
      }
    }
    mesajGoster("tekrar", "Açılacak harf kalmadı");
  };

  const seciliKelime = seciliIdx.map((i) => harfHavuzu[i] || "").join("");
  const cols = grid[0]?.length || 1;
  const hucreMax = Math.min(cols * 54, 460);

  return (
    <div
      className="relative rounded-3xl overflow-hidden"
      style={{
        color: METIN,
        fontFamily: "'Fredoka', 'Inter', system-ui, sans-serif",
        background: KREM,
        backgroundImage: `radial-gradient(circle at 18% 22%, ${anaRenk} 0%, transparent 42%), radial-gradient(circle at 84% 78%, #BFE6FF 0%, transparent 42%)`,
        padding: "16px 14px 20px",
        minHeight: 420,
      }}
    >
      {/* Dekoratif SVG (pointer yok) */}
      <svg
        className="absolute inset-0"
        width="100%"
        height="100%"
        style={{ pointerEvents: "none", opacity: 0.9 }}
        aria-hidden="true"
      >
        <circle cx="12%" cy="14%" r="3" fill="#FFDD67" />
        <circle cx="90%" cy="20%" r="2.5" fill="#FFDD67" />
        <circle cx="78%" cy="10%" r="2" fill="#FFDD67" />
        <ellipse cx="24%" cy="88%" rx="26" ry="12" fill="#FFFFFF" opacity="0.5" />
        <ellipse cx="88%" cy="46%" rx="20" ry="9" fill="#FFFFFF" opacity="0.45" />
      </svg>

      <div className="relative space-y-3">
        {/* ── Üst bar ── */}
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2 text-base font-semibold">
            <span className="text-2xl">{tema.emoji}</span>
            <span>{tema.ad}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSessiz((s) => !s)}
              title={sessiz ? "Sesi aç" : "Sesi kapat"}
              className="w-9 h-9 flex items-center justify-center rounded-2xl bg-white text-sm"
              style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
            >
              {sessiz ? "🔇" : "🔊"}
            </button>
            <button
              onClick={ipucuVer}
              disabled={bitti}
              title="İpucu (−20)"
              className="flex items-center gap-1 px-3 py-1.5 rounded-2xl bg-white text-sm font-medium disabled:opacity-40"
              style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
            >
              💡 <span className="text-xs" style={{ color: "#9aa0b4" }}>{ipucuSayisi}</span>
            </button>
            <div
              className="flex items-center gap-1 px-3 py-1.5 rounded-2xl bg-white text-sm font-bold"
              style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
            >
              🪙 {puan}
            </div>
          </div>
        </div>

        {/* ── Çapraz bulmaca grid ── */}
        <div className="flex justify-center py-1">
          <div
            className="grid gap-1.5"
            style={{
              gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
              maxWidth: hucreMax,
              width: "100%",
            }}
          >
            {grid.map((satir, r) =>
              satir.map((hucre, c) => {
                if (hucre === ".") return <div key={anahtar(r, c)} className="aspect-square" />;
                const acik = gorunurHucreler.has(anahtar(r, c));
                return (
                  <div
                    key={anahtar(r, c)}
                    className="aspect-square flex items-center justify-center rounded-xl font-bold uppercase"
                    style={{
                      minWidth: 26,
                      fontSize: "min(5vw, 20px)",
                      background: acik ? "#FFFFFF" : "rgba(255,255,255,0.55)",
                      border: acik ? "2px solid #86EFAC" : "2px dashed #C7B8EA",
                      color: METIN,
                      transition: "background 220ms ease, border 220ms ease",
                      animation: acik ? "kg-pop 300ms ease" : undefined,
                    }}
                  >
                    {acik ? grid[r][c] : ""}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── Mesaj ── */}
        <div className="h-6 text-center text-sm font-semibold">
          {mesaj && (
            <span
              style={{
                color:
                  mesaj.tip === "grid" ? "#16a34a"
                  : mesaj.tip === "bonus" ? "#d97706"
                  : mesaj.tip === "hata" ? "#e06a73"
                  : mesaj.tip === "ipucu" ? "#d97706"
                  : "#8a90a4",
              }}
            >
              {mesaj.metin}
            </span>
          )}
        </div>

        {bitti ? (
          <div className="text-center py-4 space-y-2 relative">
            {/* Konfeti */}
            <div className="absolute inset-x-0 -top-4 h-40 overflow-hidden pointer-events-none">
              {Array.from({ length: 20 }).map((_, i) => (
                <span
                  key={i}
                  style={{
                    position: "absolute",
                    left: `${(i * 97) % 100}%`,
                    top: 0,
                    width: 8,
                    height: 8,
                    borderRadius: i % 2 ? "50%" : 3,
                    background: KONFETI_RENK[i % KONFETI_RENK.length],
                    animation: `kg-konfeti ${1200 + (i % 5) * 200}ms ease-in ${(i % 7) * 60}ms forwards`,
                  }}
                />
              ))}
            </div>
            <div className="flex justify-center">
              <KelimeGezmeceMascot renk={anaRenk} durum={mascot.durum} tetik={mascot.tetik} boyut={90} />
            </div>
            <div className="text-lg font-bold">🎉 Harika! Bulmacayı tamamladın.</div>
            <div className="text-sm" style={{ color: "#8a90a4" }}>
              Toplam {puan} oyun puanı • {bulunanBonus.size} bonus kelime
            </div>
          </div>
        ) : (
          <>
            {/* Maskot + yazılan kelime */}
            <div className="flex items-center justify-center gap-3 min-h-[3rem] relative">
              <KelimeGezmeceMascot renk={anaRenk} durum={mascot.durum} tetik={mascot.tetik} boyut={64} />
              {seciliKelime ? (
                <span
                  className="inline-block px-4 py-1.5 rounded-2xl bg-white text-lg font-bold uppercase tracking-wide"
                  style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
                >
                  {seciliKelime}
                </span>
              ) : (
                <span className="text-sm" style={{ color: "#9aa0b4" }}>
                  Harfleri sürükle ya da tıkla
                </span>
              )}
              {/* Bonus balonu */}
              {balon && (
                <span
                  className="absolute left-1/2 -top-2 text-base font-bold"
                  style={{
                    transform: "translateX(-50%)",
                    color: "#d97706",
                    animation: "kg-balon 900ms ease forwards",
                  }}
                >
                  {balon.metin}
                </span>
              )}
            </div>

            {/* Harf dairesi */}
            <div style={{ animation: titre ? "kg-shake 320ms ease" : undefined }}>
              <KelimeGezmeceHarfDairesi
                harfler={harfHavuzu}
                anaRenk={anaRenk}
                boyut={boyut}
                sifirlaAnahtar={sifirla}
                karistirAnahtar={karistir}
                onSeciliDegis={onSecim}
                onTamamla={onTamamla}
              />
            </div>

            {/* Butonlar */}
            <div className="flex items-center justify-center gap-2">
              <button
                onClick={gonderBtn}
                disabled={seciliIdx.length < 2}
                className="px-5 py-2 rounded-2xl text-sm font-bold disabled:opacity-40"
                style={{ background: "#86EFAC", color: "#1a5c34" }}
              >
                Gönder ✓
              </button>
              <button
                onClick={() => setKaristir((k) => k + 1)}
                className="px-3 py-2 rounded-2xl bg-white text-sm font-medium"
                style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
              >
                🔀 Karıştır
              </button>
              <button
                onClick={() => setSifirla((s) => s + 1)}
                className="px-3 py-2 rounded-2xl bg-white text-sm font-medium"
                style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
              >
                🧹 Temizle
              </button>
            </div>

            <div className="text-center text-xs" style={{ color: "#9aa0b4" }}>
              {bulunanGrid.size}/{gridKelimeSet.size} kelime bulundu
              {bulunanBonus.size > 0 && ` • ${bulunanBonus.size} bonus`}
            </div>
          </>
        )}
      </div>

      <style>{`
        @keyframes kg-shake {
          0%,100% { transform: translateX(0); }
          25% { transform: translateX(-3px); }
          75% { transform: translateX(3px); }
        }
        @keyframes kg-pop {
          0% { transform: scale(0.8); }
          60% { transform: scale(1.1); }
          100% { transform: scale(1); }
        }
        @keyframes kg-balon {
          0% { opacity: 0; transform: translate(-50%, 6px) scale(0.8); }
          30% { opacity: 1; transform: translate(-50%, -6px) scale(1.1); }
          100% { opacity: 0; transform: translate(-50%, -24px) scale(1); }
        }
        @keyframes kg-konfeti {
          0% { opacity: 0; transform: translateY(-10px) rotate(0); }
          20% { opacity: 1; }
          100% { opacity: 0; transform: translateY(150px) rotate(320deg); }
        }
      `}</style>
    </div>
  );
}
