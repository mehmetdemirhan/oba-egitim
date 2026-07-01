import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

/**
 * KelimeGezmeceHarfDairesi — dairesel harf seçici.
 *
 * Kullanıcı harflere SÜRÜKLEYEREK (parmak/fare) veya tek tek TIKLAYARAK kelime
 * oluşturur. Sürükleme bırakıldığında kelime otomatik gönderilir (onTamamla);
 * tıklama ile harfler birikir, gönderme üst bardaki "Gönder" ya da Enter ile
 * yapılır (parent yönetir). Harfler arası SVG çizgi seçim sırasını gösterir.
 *
 * Görsel dil (pastel/çocuksu) FAZ C'de zenginleştirilir; burada işlevsel iskelet.
 *
 * Props:
 *   harfler         — ["e","l","m","a"]
 *   anaRenk         — tema ana rengi (hex), çizgi/seçim vurgusu
 *   boyut           — kare kenar (px), varsayılan 260
 *   sifirlaAnahtar  — değişince iç seçim sıfırlanır
 *   karistirAnahtar — değişince harf konumları yeniden dağıtılır
 *   pasif           — true ise etkileşim kapalı
 *   onSeciliDegis(indeksler) — seçim değiştikçe (canlı kelime gösterimi için)
 *   onTamamla(indeksler)     — sürükleme bırakıldığında (otomatik gönder)
 */
export default function KelimeGezmeceHarfDairesi({
  harfler = [],
  anaRenk = "#C7B8EA",
  boyut = 260,
  sifirlaAnahtar = 0,
  karistirAnahtar = 0,
  pasif = false,
  onSeciliDegis,
  onTamamla,
}) {
  const N = harfler.length;
  const merkez = boyut / 2;
  const yaricap = boyut * 0.34;
  const tasBoyut = Math.max(44, Math.min(64, boyut * 0.22));

  const kapsayiciRef = useRef(null);
  const merkezlerRef = useRef([]); // tile id -> {x, y} (kapsayıcıya göre)

  // Konum permütasyonu: slot index'leri (karıştırılabilir)
  const [duzen, setDuzen] = useState(() => harfler.map((_, i) => i));
  const [sec, setSec] = useState([]); // seçili harf id'leri (sıralı)
  const surukluyorRef = useRef(false);
  const tasindiRef = useRef(false);

  // Harf sayısı değişince düzeni sıfırla
  useEffect(() => {
    setDuzen(harfler.map((_, i) => i));
  }, [N]); // eslint-disable-line react-hooks/exhaustive-deps

  // Karıştır
  useEffect(() => {
    setDuzen((d) => {
      const k = [...d];
      for (let i = k.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [k[i], k[j]] = [k[j], k[i]];
      }
      return k;
    });
  }, [karistirAnahtar]);

  // Sıfırla (dışarıdan)
  useEffect(() => {
    setSec([]);
  }, [sifirlaAnahtar]);

  // Seçim değişince parent'e bildir
  useEffect(() => {
    onSeciliDegis && onSeciliDegis(sec);
  }, [sec]); // eslint-disable-line react-hooks/exhaustive-deps

  // Her harf id'sinin (x,y) merkezi — slot konumuna göre
  const konumlar = useMemo(() => {
    const m = {};
    duzen.forEach((slot, id) => {
      const aci = -Math.PI / 2 + (slot * 2 * Math.PI) / Math.max(1, N);
      m[id] = {
        x: merkez + yaricap * Math.cos(aci),
        y: merkez + yaricap * Math.sin(aci),
      };
    });
    merkezlerRef.current = m;
    return m;
  }, [duzen, N, merkez, yaricap]);

  // Pointer konumundan en yakın taşı bul (taş yarıçapı içinde)
  const tasBul = useCallback((clientX, clientY) => {
    const kutu = kapsayiciRef.current?.getBoundingClientRect();
    if (!kutu) return null;
    const px = clientX - kutu.left;
    const py = clientY - kutu.top;
    const esik = tasBoyut * 0.62;
    let enYakin = null;
    let enYakinMes = esik;
    for (const id of Object.keys(merkezlerRef.current)) {
      const { x, y } = merkezlerRef.current[id];
      const mes = Math.hypot(px - x, py - y);
      if (mes <= enYakinMes) {
        enYakinMes = mes;
        enYakin = Number(id);
      }
    }
    return enYakin;
  }, [tasBoyut]);

  const pointerBasla = (e) => {
    if (pasif) return;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    surukluyorRef.current = true;
    tasindiRef.current = false;
    const id = tasBul(e.clientX, e.clientY);
    if (id != null) {
      setSec((s) => (s.includes(id) ? s : [...s, id]));
    }
  };

  const pointerHareket = (e) => {
    if (pasif || !surukluyorRef.current) return;
    const id = tasBul(e.clientX, e.clientY);
    if (id != null) {
      setSec((s) => {
        if (s.includes(id)) return s;
        tasindiRef.current = true; // yeni taşa sürüklendi → bu bir sürükleme
        return [...s, id];
      });
    }
  };

  const pointerBitir = () => {
    if (pasif || !surukluyorRef.current) return;
    surukluyorRef.current = false;
    // Sürükleme (≥2 taşa gezinme) → otomatik gönder. Tek tık → birikmeye devam.
    if (tasindiRef.current && sec.length >= 2) {
      onTamamla && onTamamla(sec);
    }
  };

  // SVG çizgi noktaları (seçili sıraya göre)
  const cizgiNoktalar = sec
    .map((id) => konumlar[id])
    .filter(Boolean)
    .map((p) => `${p.x},${p.y}`)
    .join(" ");

  return (
    <div
      ref={kapsayiciRef}
      onPointerDown={pointerBasla}
      onPointerMove={pointerHareket}
      onPointerUp={pointerBitir}
      onPointerCancel={pointerBitir}
      style={{ width: boyut, height: boyut, touchAction: "none" }}
      className="relative mx-auto select-none"
    >
      {/* Tabak zemini */}
      <div
        className="absolute inset-0 rounded-full"
        style={{ background: anaRenk, opacity: 0.5, boxShadow: "0 8px 32px rgba(0,0,0,0.06)" }}
      />

      {/* Birleştirme çizgisi */}
      <svg className="absolute inset-0 pointer-events-none" width={boyut} height={boyut}>
        {cizgiNoktalar && (
          <polyline
            points={cizgiNoktalar}
            fill="none"
            stroke={anaRenk}
            strokeWidth={5}
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.85}
            style={{ filter: "drop-shadow(0 2px 4px rgba(199,184,234,0.5))" }}
          />
        )}
      </svg>

      {/* Harf taşları */}
      {harfler.map((harf, id) => {
        const pos = konumlar[id] || { x: merkez, y: merkez };
        const secili = sec.includes(id);
        return (
          <div
            key={id}
            style={{
              position: "absolute",
              left: pos.x - tasBoyut / 2,
              top: pos.y - tasBoyut / 2,
              width: tasBoyut,
              height: tasBoyut,
              borderRadius: 18,
              background: secili ? "#FFDD67" : "#FFFFFF",
              color: "#3D405B",
              transform: secili ? "scale(1.08)" : "scale(1)",
              transition: "transform 180ms ease, background 180ms ease",
              boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
              fontWeight: 700,
              fontSize: tasBoyut * 0.42,
              fontFamily: "'Fredoka', 'Inter', system-ui, sans-serif",
            }}
            className="flex items-center justify-center uppercase pointer-events-none"
          >
            {harf}
          </div>
        );
      })}
    </div>
  );
}
