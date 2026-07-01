import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import KelimeGezmeceHarfDairesi from "./KelimeGezmeceHarfDairesi";
import KelimeGezmeceMascot from "./KelimeGezmeceMascot";

/**
 * KelimeGezmece — çok seviyeli çapraz bulmaca harf oyunu (tip: kelime_gezmece).
 *
 * İçerik şeması:
 *   { harf_havuzu, grid (2D '.'/harf), kelimeler:[{kelime,yon,baslangic:[r,c],uzunluk}],
 *     bonus_kelimeler:[...], tema:{ad,emoji,ana_renk_hex}, seviye_no, sinif }
 *
 * Akış:
 *   - İlk bulmaca prop `icerik` ile gelir (seviye 1). Her seviye tamamlanınca
 *     backend'den (/egzersiz/kelime-gezmece/seviye) bir sonraki seviye çekilir;
 *     zorluk seviye_no ile artar. Puan seviyeler boyunca birikir.
 *   - "Bitir" ile oturum tamamlanır (/egzersiz/kelime-gezmece/tamamla): XP =
 *     tamamlanan seviye × 50 + bonus × 15; öğrencinin toplam_xp'sine yazılır
 *     (sıralama/leaderboard bunu okur).
 *
 * Doğrulama İSTEMCİ tarafında (içerik grid + bonus listelerini taşır). Backend'e
 * doğrudan erişim: process.env.REACT_APP_BACKEND_URL + global axios auth header.
 *
 * Görsel dil: modern çocuk uygulaması (Sago Mini / Pok Pok). Responsive:
 *   mobil → dikey (grid üstte, tabak altta); tablet+ → yan yana (scroll yok).
 *
 * Render sözleşmesi: { icerik, onCevap }. onCevap ÇAĞRILMAZ; oyun kendi çok
 * seviyeli akışını yönetir ve /tamamla ile bitirir (çift XP'yi önlemek için).
 */
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const trKucuk = (s) => (s || "").toLocaleLowerCase("tr").replace(/\s+/g, "");
const anahtar = (r, c) => `${r},${c}`;

const KREM = "#FFF8F0";
const METIN = "#3D405B";
const KONFETI_RENK = ["#FFDD67", "#FFB5A7", "#A7E8BD", "#BFE6FF", "#C7B8EA"];

// ── Hafif WebAudio ses sentezi (harici dosya yok) ──
let _ac = null;
function _ctx() {
  if (typeof window === "undefined") return null;
  try {
    if (!_ac) _ac = new (window.AudioContext || window.webkitAudioContext)();
    if (_ac.state === "suspended") _ac.resume();
    return _ac;
  } catch { return null; }
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
  // ── Oyun (çok seviyeli) durumu ──
  const [aktifIcerik, setAktifIcerik] = useState(icerik || {});
  const [seviye, setSeviye] = useState(icerik?.seviye_no || 1);
  const sinif = aktifIcerik?.sinif || icerik?.sinif || 3;

  const [toplamPuan, setToplamPuan] = useState(0);       // tamamlanan seviyelerden kilitlenen
  const [tamamlananSeviye, setTamamlananSeviye] = useState(0);
  const [toplamBonus, setToplamBonus] = useState(0);
  const [seviyeGecis, setSeviyeGecis] = useState(false);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [oyunBitti, setOyunBitti] = useState(false);
  const [sonuc, setSonuc] = useState(null);

  // ── Seviye-içi durum ──
  const [bulunanGrid, setBulunanGrid] = useState(() => new Set());
  const [bulunanBonus, setBulunanBonus] = useState(() => new Set());
  const [acikHucreler, setAcikHucreler] = useState(() => new Set());
  const [seviyePuan, setSeviyePuan] = useState(0);
  const [ipucuSayisi, setIpucuSayisi] = useState(0);
  const [seciliIdx, setSeciliIdx] = useState([]);
  const [mesaj, setMesaj] = useState(null);
  const [balon, setBalon] = useState(null);
  const [titre, setTitre] = useState(false);
  const [sifirla, setSifirla] = useState(0);
  const [karistir, setKaristir] = useState(0);
  const [sessiz, setSessiz] = useState(false);
  const [mascot, setMascot] = useState({ durum: "idle", tetik: 0 });
  const [vw, setVw] = useState(typeof window !== "undefined" ? window.innerWidth : 800);

  const seviyeTamamRef = useRef(false);
  const bitiriliyorRef = useRef(false);
  const baslangicRef = useRef(Date.now());
  const mesajZamanRef = useRef(null);
  const balonZamanRef = useRef(null);
  const sessizRef = useRef(false);
  useEffect(() => { sessizRef.current = sessiz; }, [sessiz]);

  const tema = aktifIcerik?.tema || { ad: "Oyun", emoji: "🧩", ana_renk_hex: "#A7E8BD" };
  const anaRenk = tema.ana_renk_hex || "#A7E8BD";
  const harfHavuzu = useMemo(() => aktifIcerik?.harf_havuzu || [], [aktifIcerik]);
  const grid = useMemo(() => aktifIcerik?.grid || [["."]], [aktifIcerik]);
  const gridKelimeler = useMemo(() => aktifIcerik?.kelimeler || [], [aktifIcerik]);
  const bonusListesi = useMemo(
    () => new Set((aktifIcerik?.bonus_kelimeler || []).map(trKucuk)),
    [aktifIcerik]
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

  // Fredoka fontu (bir kez)
  useEffect(() => {
    const id = "kg-fredoka-font";
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&display=swap";
    document.head.appendChild(link);
  }, []);

  useEffect(() => {
    const g = () => setVw(window.innerWidth);
    g();
    window.addEventListener("resize", g);
    return () => window.removeEventListener("resize", g);
  }, []);

  // Aktif içerik (seviye) değişince seviye-içi durumu sıfırla
  useEffect(() => {
    setBulunanGrid(new Set());
    setBulunanBonus(new Set());
    setAcikHucreler(new Set());
    setSeviyePuan(0);
    setIpucuSayisi(0);
    setSeciliIdx([]);
    setMesaj(null);
    setBalon(null);
    setSifirla((s) => s + 1);
    seviyeTamamRef.current = false;
  }, [aktifIcerik]);

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
    if (durum !== "idle") setTimeout(() => setMascot((m) => ({ durum: "idle", tetik: m.tetik })), 1000);
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

  // Bir sonraki seviyeyi backend'den yükle
  const seviyeYukle = useCallback(async (yeniSeviye) => {
    setYukleniyor(true);
    try {
      const r = await axios.post(`${API}/egzersiz/kelime-gezmece/seviye`, {
        sinif, seviye_no: yeniSeviye,
      });
      setAktifIcerik(r.data.icerik || {});
      setSeviye(yeniSeviye);
    } catch (e) {
      mesajGoster("hata", "Sonraki seviye yüklenemedi");
    } finally {
      setYukleniyor(false);
      setSeviyeGecis(false);
    }
  }, [sinif, mesajGoster]);

  // Seviye tamamlanınca: puanı kilitle → geçiş → sonraki seviye
  useEffect(() => {
    if (
      gridKelimeSet.size > 0 &&
      bulunanGrid.size >= gridKelimeSet.size &&
      !seviyeTamamRef.current &&
      !oyunBitti
    ) {
      seviyeTamamRef.current = true;
      const bitisBonusu = 50 * seviye; // artan seviye tamamlama puanı
      setToplamPuan((p) => p + Math.max(0, seviyePuan) + bitisBonusu);
      setToplamBonus((b) => b + bulunanBonus.size);
      setTamamlananSeviye(seviye);
      ses("bitir");
      mascotTetikle("kutla");
      setSeviyeGecis(true);
      const sonraki = seviye + 1;
      setTimeout(() => seviyeYukle(sonraki), 2000);
    }
  }, [bulunanGrid, gridKelimeSet, oyunBitti, seviye, seviyePuan, bulunanBonus, ses, mascotTetikle, seviyeYukle]);

  const kelimeDenetle = useCallback((kelime) => {
    const w = trKucuk(kelime);
    if (!w || w.length < 2) return;
    if (bulunanGrid.has(w) || bulunanBonus.has(w)) {
      mesajGoster("tekrar", `“${w.toUpperCase()}” zaten bulundu`);
      return;
    }
    if (gridKelimeSet.has(w)) {
      setBulunanGrid((s) => new Set(s).add(w));
      setSeviyePuan((p) => p + 10);
      mesajGoster("grid", `✓ ${w.toUpperCase()} (+10)`);
      ses("dogru"); mascotTetikle("zipla");
      return;
    }
    if (bonusListesi.has(w)) {
      setBulunanBonus((s) => new Set(s).add(w));
      setSeviyePuan((p) => p + 15);
      mesajGoster("bonus", `⭐ Bonus: ${w.toUpperCase()} (+15)`);
      balonGoster("+15 ⭐"); ses("bonus"); mascotTetikle("kutla");
      return;
    }
    setTitre(true);
    setTimeout(() => setTitre(false), 320);
    mesajGoster("hata", `“${w.toUpperCase()}” listede yok`);
  }, [bulunanGrid, bulunanBonus, gridKelimeSet, bonusListesi, mesajGoster, balonGoster, ses, mascotTetikle]);

  const onTamamla = useCallback((indeksler) => {
    const kelime = indeksler.map((i) => harfHavuzu[i] || "").join("");
    kelimeDenetle(kelime);
    setSifirla((s) => s + 1);
  }, [harfHavuzu, kelimeDenetle]);

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
      const gizli = (kelimeHucreleri[w] || []).find(([r, c]) => !gorunurHucreler.has(anahtar(r, c)));
      if (gizli) {
        setAcikHucreler((s) => new Set(s).add(anahtar(gizli[0], gizli[1])));
        setSeviyePuan((p) => p - 20);
        setIpucuSayisi((n) => n + 1);
        mesajGoster("ipucu", "💡 Bir harf açıldı (−20)");
        return;
      }
    }
    mesajGoster("tekrar", "Açılacak harf kalmadı");
  };

  // Oyunu bitir → oturumu tamamla, XP'yi sıralamaya işle
  const oyunuBitir = async () => {
    if (bitiriliyorRef.current) return;
    bitiriliyorRef.current = true;
    const sure = Math.max(0, Math.round((Date.now() - baslangicRef.current) / 1000));
    let veri = {
      xp: tamamlananSeviye * 50 + toplamBonus * 15,
      seviye_sayisi: tamamlananSeviye,
      bonus_sayisi: toplamBonus,
      toplam_puan: toplamPuan,
    };
    try {
      const r = await axios.post(`${API}/egzersiz/kelime-gezmece/tamamla`, {
        sinif,
        seviye_sayisi: tamamlananSeviye,
        bonus_sayisi: toplamBonus,
        toplam_puan: toplamPuan,
        en_yuksek_seviye: seviye,
        sure_sn: sure,
      });
      veri = { ...veri, ...(r.data || {}) };
    } catch (e) {
      /* çevrimdışı: yerel hesaplanan değerlerle sonucu göster */
    }
    setSonuc(veri);
    setOyunBitti(true);
    ses("bitir");
    mascotTetikle("kutla");
  };

  const seciliKelime = seciliIdx.map((i) => harfHavuzu[i] || "").join("");
  const cols = grid[0]?.length || 1;

  // Responsive ölçüler
  const yanYana = vw >= 768;
  const gridAlan = yanYana ? vw * 0.5 - 56 : vw - 40;
  const hucreTavan = vw >= 1024 ? 62 : yanYana ? 54 : 46;
  const hucrePx = Math.max(24, Math.min(hucreTavan, Math.floor(gridAlan / cols) - 6));
  const daireBoyut = vw >= 1024
    ? Math.min(320, vw * 0.34)
    : yanYana
    ? Math.min(280, vw * 0.4)
    : Math.max(220, Math.min(300, vw - 80));

  // ── SOL SÜTUN: banner + üst bar + grid ──
  const solSutun = (
    <div className="order-1 space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 text-base font-semibold">
          <span className="text-2xl">{tema.emoji}</span>
          <span>{tema.ad}</span>
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{ background: "#FFFFFF", color: "#8a90a4", boxShadow: "0 2px 8px rgba(0,0,0,0.05)" }}
          >
            Seviye {seviye}
          </span>
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
            title="İpucu (−20)"
            className="flex items-center gap-1 px-3 py-1.5 rounded-2xl bg-white text-sm font-medium"
            style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
          >
            💡 <span className="text-xs" style={{ color: "#9aa0b4" }}>{ipucuSayisi}</span>
          </button>
          <div
            className="flex items-center gap-1 px-3 py-1.5 rounded-2xl bg-white text-sm font-bold"
            style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
          >
            🪙 {toplamPuan + Math.max(0, seviyePuan)}
          </div>
          <button
            onClick={oyunuBitir}
            title="Bitir ve sıralamaya ekle"
            className="px-3 py-1.5 rounded-2xl text-sm font-bold"
            style={{ background: "#FFDD67", color: "#7a5b00" }}
          >
            🏁 Bitir
          </button>
        </div>
      </div>

      <div className="flex justify-center py-1">
        <div
          className="grid gap-1.5"
          style={{ gridTemplateColumns: `repeat(${cols}, ${hucrePx}px)` }}
        >
          {grid.map((satir, r) =>
            satir.map((hucre, c) => {
              if (hucre === ".") return <div key={anahtar(r, c)} style={{ width: hucrePx, height: hucrePx }} />;
              const acik = gorunurHucreler.has(anahtar(r, c));
              return (
                <div
                  key={anahtar(r, c)}
                  className="flex items-center justify-center rounded-xl font-bold uppercase"
                  style={{
                    width: hucrePx,
                    height: hucrePx,
                    fontSize: hucrePx * 0.42,
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
    </div>
  );

  // ── SAĞ SÜTUN: geçiş / harf tabağı ──
  const sagSutun = (
    <div className="order-2 flex flex-col items-center justify-center gap-3">
      {seviyeGecis || yukleniyor ? (
        <div className="text-center py-6 space-y-3">
          <div className="flex justify-center">
            <KelimeGezmeceMascot renk={anaRenk} durum={mascot.durum} tetik={mascot.tetik} boyut={90} />
          </div>
          <div className="text-lg font-bold">🎉 Harika!</div>
          <div className="text-sm" style={{ color: "#8a90a4" }}>
            {yukleniyor ? "Bir sonraki seviye hazırlanıyor…" : "Bir sonraki seviye açılıyor…"}
          </div>
          <button
            onClick={oyunuBitir}
            className="px-4 py-2 rounded-2xl text-sm font-bold"
            style={{ background: "#FFDD67", color: "#7a5b00" }}
          >
            🏁 Şimdi Bitir
          </button>
        </div>
      ) : (
        <>
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
              <span className="text-sm" style={{ color: "#9aa0b4" }}>Harfleri sürükle ya da tıkla</span>
            )}
            {balon && (
              <span
                className="absolute left-1/2 -top-2 text-base font-bold"
                style={{ transform: "translateX(-50%)", color: "#d97706", animation: "kg-balon 900ms ease forwards" }}
              >
                {balon.metin}
              </span>
            )}
          </div>

          <div style={{ animation: titre ? "kg-shake 320ms ease" : undefined }}>
            <KelimeGezmeceHarfDairesi
              harfler={harfHavuzu}
              anaRenk={anaRenk}
              boyut={daireBoyut}
              sifirlaAnahtar={sifirla}
              karistirAnahtar={karistir}
              onSeciliDegis={onSecim}
              onTamamla={onTamamla}
            />
          </div>

          <div className="flex items-center justify-center gap-2">
            <button
              onClick={gonderBtn}
              disabled={seciliIdx.length < 2}
              className="px-5 py-2 rounded-2xl text-sm font-bold disabled:opacity-40"
              style={{ background: "#86EFAC", color: "#1a5c34" }}
            >
              Gönder ✓
            </button>
            <button onClick={() => setKaristir((k) => k + 1)}
              className="px-3 py-2 rounded-2xl bg-white text-sm font-medium"
              style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}>
              🔀 Karıştır
            </button>
            <button onClick={() => setSifirla((s) => s + 1)}
              className="px-3 py-2 rounded-2xl bg-white text-sm font-medium"
              style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}>
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
  );

  return (
    <div
      className="relative rounded-3xl overflow-hidden"
      style={{
        color: METIN,
        fontFamily: "'Fredoka', 'Inter', system-ui, sans-serif",
        background: KREM,
        backgroundImage: `radial-gradient(circle at 18% 22%, ${anaRenk} 0%, transparent 42%), radial-gradient(circle at 84% 78%, #BFE6FF 0%, transparent 42%)`,
        padding: "16px 14px 20px",
        minHeight: 380,
      }}
    >
      <svg className="absolute inset-0" width="100%" height="100%"
        style={{ pointerEvents: "none", opacity: 0.9 }} aria-hidden="true">
        <circle cx="12%" cy="14%" r="3" fill="#FFDD67" />
        <circle cx="90%" cy="20%" r="2.5" fill="#FFDD67" />
        <circle cx="78%" cy="10%" r="2" fill="#FFDD67" />
        <ellipse cx="24%" cy="90%" rx="26" ry="12" fill="#FFFFFF" opacity="0.5" />
        <ellipse cx="88%" cy="46%" rx="20" ry="9" fill="#FFFFFF" opacity="0.45" />
      </svg>

      <div className="relative">
        {oyunBitti ? (
          <div className="text-center py-6 space-y-3 relative">
            <div className="absolute inset-x-0 -top-4 h-44 overflow-hidden pointer-events-none">
              {Array.from({ length: 20 }).map((_, i) => (
                <span key={i}
                  style={{
                    position: "absolute",
                    left: `${(i * 97) % 100}%`,
                    top: 0, width: 8, height: 8,
                    borderRadius: i % 2 ? "50%" : 3,
                    background: KONFETI_RENK[i % KONFETI_RENK.length],
                    animation: `kg-konfeti ${1200 + (i % 5) * 200}ms ease-in ${(i % 7) * 60}ms forwards`,
                  }} />
              ))}
            </div>
            <div className="flex justify-center">
              <KelimeGezmeceMascot renk={anaRenk} durum={mascot.durum} tetik={mascot.tetik} boyut={96} />
            </div>
            <div className="text-xl font-bold">
              🎯 {sonuc?.seviye_sayisi ?? tamamlananSeviye} seviye tamamladın!
            </div>
            <div className="text-base font-semibold">
              Toplam puanın: {sonuc?.toplam_puan ?? toplamPuan}
            </div>
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold"
              style={{ background: "#86EFAC", color: "#1a5c34" }}>
              +{sonuc?.xp ?? 0} XP • Sıralamada güncellendi ✓
            </div>
            <div className="text-xs" style={{ color: "#9aa0b4" }}>
              {sonuc?.bonus_sayisi ?? toplamBonus} bonus kelime • Çıkmak için “← Çık”
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-8 md:items-center">
            {solSutun}
            {sagSutun}
          </div>
        )}
      </div>

      <style>{`
        @keyframes kg-shake { 0%,100%{transform:translateX(0);}25%{transform:translateX(-3px);}75%{transform:translateX(3px);} }
        @keyframes kg-pop { 0%{transform:scale(0.8);}60%{transform:scale(1.1);}100%{transform:scale(1);} }
        @keyframes kg-balon { 0%{opacity:0;transform:translate(-50%,6px) scale(0.8);}30%{opacity:1;transform:translate(-50%,-6px) scale(1.1);}100%{opacity:0;transform:translate(-50%,-24px) scale(1);} }
        @keyframes kg-konfeti { 0%{opacity:0;transform:translateY(-10px) rotate(0);}20%{opacity:1;}100%{opacity:0;transform:translateY(160px) rotate(320deg);} }
      `}</style>
    </div>
  );
}
