import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import KelimeGezmeceHarfDairesi from "./KelimeGezmeceHarfDairesi";

/**
 * KelimeGezmece — çapraz bulmaca harf oyunu (egzersiz tipi: kelime_gezmece).
 *
 * İçerik şeması:
 *   { harf_havuzu, grid (2D '.'/harf), kelimeler:[{kelime,yon,baslangic:[r,c],uzunluk}],
 *     bonus_kelimeler:[...], tema:{ad,emoji,ana_renk_hex} }
 *
 * Doğrulama İSTEMCİ tarafında yapılır (içerik grid + bonus listelerini taşır);
 * tüm grid kelimeleri bulununca onCevap(true) ile motora tek seferlik başarı
 * bildirilir (puanlama=serbest → tam XP). Oyun-içi puan (grid +10 / bonus +15 /
 * ipucu -20) çocuk-yüzlü görsel sayaçta gösterilir.
 *
 * Render sözleşmesi: { icerik, onCevap }. (icerik_id/apiBase render katmanına
 * geçmez; bu yüzden doğrulama yerel, backend /dogrula yetkili alternatiftir.)
 *
 * FAZ B: işlevsel iskelet. FAZ C: pastel/çocuksu görsel katman.
 */
const trKucuk = (s) => (s || "").toLocaleLowerCase("tr").replace(/\s+/g, "");
const anahtar = (r, c) => `${r},${c}`;

export default function KelimeGezmece({ icerik, onCevap }) {
  const tema = icerik?.tema || { ad: "Oyun", emoji: "🧩", ana_renk_hex: "#A7E8BD" };
  const anaRenk = tema.ana_renk_hex || "#A7E8BD";
  const harfHavuzu = useMemo(() => icerik?.harf_havuzu || [], [icerik]);
  const grid = useMemo(() => icerik?.grid || [[".."]], [icerik]);
  const gridKelimeler = useMemo(() => icerik?.kelimeler || [], [icerik]);
  const bonusListesi = useMemo(
    () => new Set((icerik?.bonus_kelimeler || []).map(trKucuk)),
    [icerik]
  );

  // Grid kelime → hücre koordinatları
  const kelimeHucreleri = useMemo(() => {
    const m = {};
    for (const k of gridKelimeler) {
      const [r, c] = k.baslangic || [0, 0];
      const yatay = k.yon === "yatay";
      const huc = [];
      for (let i = 0; i < (k.uzunluk || 0); i++) {
        huc.push(yatay ? [r, c + i] : [r + i, c]);
      }
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
  const [acikHucreler, setAcikHucreler] = useState(() => new Set()); // ipucu açılan tek hücreler
  const [puan, setPuan] = useState(0);
  const [ipucuSayisi, setIpucuSayisi] = useState(0);
  const [seciliIdx, setSeciliIdx] = useState([]);
  const [mesaj, setMesaj] = useState(null); // {tip:"grid"|"bonus"|"hata"|"tekrar", metin}
  const [titre, setTitre] = useState(false);
  const [bitti, setBitti] = useState(false);
  const [sifirla, setSifirla] = useState(0);
  const [karistir, setKaristir] = useState(0);

  const cevapGonderildiRef = useRef(false);
  const mesajZamanRef = useRef(null);

  // İçerik değişince state sıfırla
  useEffect(() => {
    setBulunanGrid(new Set());
    setBulunanBonus(new Set());
    setAcikHucreler(new Set());
    setPuan(0);
    setIpucuSayisi(0);
    setSeciliIdx([]);
    setMesaj(null);
    setBitti(false);
    cevapGonderildiRef.current = false;
  }, [icerik]);

  // Açık (görünür) hücreler: bulunan grid kelimelerinin + ipucu hücreleri
  const gorunurHucreler = useMemo(() => {
    const s = new Set(acikHucreler);
    for (const k of bulunanGrid) {
      for (const [r, c] of kelimeHucreleri[k] || []) s.add(anahtar(r, c));
    }
    return s;
  }, [bulunanGrid, acikHucreler, kelimeHucreleri]);

  const mesajGoster = useCallback((tip, metin) => {
    setMesaj({ tip, metin });
    clearTimeout(mesajZamanRef.current);
    mesajZamanRef.current = setTimeout(() => setMesaj(null), 1400);
  }, []);

  // Tüm grid kelimeleri bulununca tamamla
  useEffect(() => {
    if (
      gridKelimeSet.size > 0 &&
      bulunanGrid.size >= gridKelimeSet.size &&
      !cevapGonderildiRef.current
    ) {
      cevapGonderildiRef.current = true;
      setBitti(true);
      onCevap && onCevap(true);
    }
  }, [bulunanGrid, gridKelimeSet, onCevap]);

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
        return;
      }
      if (bonusListesi.has(w)) {
        setBulunanBonus((s) => new Set(s).add(w));
        setPuan((p) => p + 15);
        mesajGoster("bonus", `⭐ Bonus: ${w.toUpperCase()} (+15)`);
        return;
      }
      // Geçersiz → hafif titreme
      setTitre(true);
      setTimeout(() => setTitre(false), 320);
      mesajGoster("hata", `“${w.toUpperCase()}” listede yok`);
    },
    [bulunanGrid, bulunanBonus, gridKelimeSet, bonusListesi, mesajGoster]
  );

  const onTamamla = useCallback(
    (indeksler) => {
      const kelime = indeksler.map((i) => harfHavuzu[i] || "").join("");
      kelimeDenetle(kelime);
      setSifirla((s) => s + 1);
    },
    [harfHavuzu, kelimeDenetle]
  );

  const gonderBtn = () => {
    if (!seciliIdx.length) return;
    onTamamla(seciliIdx);
  };

  // İpucu: bulunmamış bir grid kelimesinin ilk gizli hücresini aç (-20 puan)
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
        mesajGoster("hata", "💡 Bir harf açıldı (−20)");
        return;
      }
    }
    mesajGoster("tekrar", "Açılacak harf kalmadı");
  };

  const seciliKelime = seciliIdx.map((i) => harfHavuzu[i] || "").join("");
  const rows = grid.length;
  const cols = grid[0]?.length || 1;

  return (
    <div className="space-y-3" style={{ color: "#3D405B" }}>
      {/* ── Üst bar ── */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 text-base font-semibold">
          <span className="text-2xl">{tema.emoji}</span>
          <span>{tema.ad}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={ipucuVer}
            disabled={bitti}
            title="İpucu (−20)"
            className="flex items-center gap-1 px-3 py-1.5 rounded-2xl bg-white shadow-sm text-sm font-medium disabled:opacity-40"
            style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
          >
            💡 <span className="text-xs text-gray-400">{ipucuSayisi}</span>
          </button>
          <div
            className="flex items-center gap-1 px-3 py-1.5 rounded-2xl bg-white shadow-sm text-sm font-bold"
            style={{ boxShadow: "0 4px 12px rgba(0,0,0,0.06)" }}
          >
            🪙 {puan}
          </div>
        </div>
      </div>

      {/* ── Çapraz bulmaca grid ── */}
      <div className="flex justify-center py-2">
        <div
          className="grid gap-1.5"
          style={{
            gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
            maxWidth: Math.min(cols * 56, 480),
          }}
        >
          {grid.map((satir, r) =>
            satir.map((hucre, c) => {
              if (hucre === ".") {
                return <div key={anahtar(r, c)} className="aspect-square" />;
              }
              const acik = gorunurHucreler.has(anahtar(r, c));
              return (
                <div
                  key={anahtar(r, c)}
                  className="aspect-square flex items-center justify-center rounded-xl text-lg font-bold uppercase"
                  style={{
                    minWidth: 28,
                    background: acik ? "#FFFFFF" : "rgba(255,255,255,0.6)",
                    border: acik ? "2px solid #86EFAC" : "2px dashed #C7B8EA",
                    color: "#3D405B",
                    transition: "all 220ms ease",
                  }}
                >
                  {acik ? grid[r][c] : ""}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── Mesaj / durum ── */}
      <div className="h-7 text-center text-sm font-semibold">
        {mesaj && (
          <span
            style={{
              color:
                mesaj.tip === "grid"
                  ? "#16a34a"
                  : mesaj.tip === "bonus"
                  ? "#d97706"
                  : mesaj.tip === "hata"
                  ? "#e06a73"
                  : "#6b7280",
            }}
          >
            {mesaj.metin}
          </span>
        )}
      </div>

      {/* ── Tamamlandı ── */}
      {bitti ? (
        <div className="text-center py-4 space-y-2">
          <div className="text-4xl">🎉</div>
          <div className="text-lg font-bold">Harika! Bulmacayı tamamladın.</div>
          <div className="text-sm text-gray-500">
            Toplam {puan} oyun puanı • {bulunanBonus.size} bonus kelime
          </div>
        </div>
      ) : (
        <>
          {/* Yazılan kelime önizleme */}
          <div className="text-center min-h-[2rem]">
            {seciliKelime ? (
              <span className="inline-block px-4 py-1.5 rounded-2xl bg-white shadow-sm text-lg font-bold uppercase tracking-wide">
                {seciliKelime}
              </span>
            ) : (
              <span className="text-sm text-gray-400">
                Harfleri sürükle ya da tıkla
              </span>
            )}
          </div>

          {/* Harf dairesi */}
          <div
            style={{
              transform: titre ? "translateX(0)" : undefined,
              animation: titre ? "kg-shake 320ms ease" : undefined,
            }}
          >
            <KelimeGezmeceHarfDairesi
              harfler={harfHavuzu}
              anaRenk={anaRenk}
              sifirlaAnahtar={sifirla}
              karistirAnahtar={karistir}
              onSeciliDegis={setSeciliIdx}
              onTamamla={onTamamla}
            />
          </div>

          {/* Butonlar */}
          <div className="flex items-center justify-center gap-2">
            <button
              onClick={gonderBtn}
              disabled={seciliIdx.length < 2}
              className="px-4 py-2 rounded-2xl text-white text-sm font-semibold disabled:opacity-40"
              style={{ background: "#86EFAC", color: "#1a5c34" }}
            >
              Gönder ✓
            </button>
            <button
              onClick={() => setKaristir((k) => k + 1)}
              className="px-3 py-2 rounded-2xl bg-white shadow-sm text-sm font-medium"
            >
              🔀 Karıştır
            </button>
            <button
              onClick={() => setSifirla((s) => s + 1)}
              className="px-3 py-2 rounded-2xl bg-white shadow-sm text-sm font-medium"
            >
              🧹 Temizle
            </button>
          </div>

          {/* İlerleme */}
          <div className="text-center text-xs text-gray-400">
            {bulunanGrid.size}/{gridKelimeSet.size} kelime bulundu
          </div>
        </>
      )}

      {/* Yerel keyframe (FAZ C'de zenginleşir) */}
      <style>{`
        @keyframes kg-shake {
          0%,100% { transform: translateX(0); }
          25% { transform: translateX(-3px); }
          75% { transform: translateX(3px); }
        }
      `}</style>
    </div>
  );
}
