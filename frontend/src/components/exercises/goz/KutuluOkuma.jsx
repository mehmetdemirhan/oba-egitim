// Kutulu Okuma — metin normal akan bir paragraf olarak gösterilir; ÜZERİNE, o ana
// kadar okunan her kelime grubunu çerçeveleyen kutular BİRİKEREK bindirilir.
// Öğretmen ilerledikçe (SAĞ ok / ▶) yeni kelimeye kutu eklenir; önceki kutular
// SİLİNMEZ, ekranda kalır. Aktif (şu an okunan) kutu belirgin (dolu indigo), geçilmiş
// kutular soluk/gri gösterilir. Son kelimeye ulaşınca tüm metin kutulu olur.
// Kontrol: SAĞ/SOL ok (klavye) + ◀/▶ butonları. Kutu genişliği/konumu, kelimenin
// gerçek DOM konumuna göre dinamik ölçülür (font sabit, taşma yok, satır sonunda alt
// satıra geçer). Metin, öğrencinin SINIF + KUR'una göre havuzdan otomatik gelir.
import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { EgzersizDuzen } from "./ortak";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const ZORLUK_ETIKET = { kolay: "Kolay", orta: "Orta", zor: "Zor" };
const PAD = 6; // kutu iç boşluğu (px)

export default function KutuluOkuma({ onTamamla }) {
  const [metin, setMetin] = useState(null);
  const [kutuBasi, setKutuBasi] = useState(1);   // aynı anda çerçevelenecek kelime sayısı
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState("");
  const [basIndex, setBasIndex] = useState(0);   // aktif grubun ilk kelime indeksi
  const [bitti, setBitti] = useState(false);
  const [kutular, setKutular] = useState([]);    // [{left,top,width,height,aktif}] — biriken kutular

  const containerRef = useRef(null);
  const wordRefs = useRef([]);
  const bittiRef = useRef(false);

  // Genel varsayılan kutu-başına-kelime (Ayarlar) — başlangıç değeri.
  useEffect(() => {
    let iptal = false;
    axios.get(`${API}/ayarlar/kutulu_okuma`).then((r) => {
      const v = r.data?.degerler?.kutu_basi_kelime;
      if (!iptal && (v === 1 || v === 2 || v === 3)) setKutuBasi(v);
    }).catch(() => {});
    return () => { iptal = true; };
  }, []);

  const metinGetir = useCallback(async () => {
    setYukleniyor(true); setHata(""); setBitti(false); bittiRef.current = false; setBasIndex(0);
    try {
      const r = await axios.get(`${API}/kutulu-okuma/metin`);
      setMetin(r.data);
    } catch (e) {
      setHata(e?.response?.data?.detail || "Uygun metin bulunamadı. Havuzda metin olmayabilir.");
      setMetin(null);
    } finally {
      setYukleniyor(false);
    }
  }, []);

  useEffect(() => { metinGetir(); }, [metinGetir]);

  const kelimeler = useMemo(
    () => (metin?.icerik ? metin.icerik.trim().split(/\s+/).filter(Boolean) : []),
    [metin]
  );
  const n = kelimeler.length;
  const sonGrupBas = n > 0 ? Math.floor((n - 1) / kutuBasi) * kutuBasi : 0;
  const aktifGrup = kutuBasi > 0 ? Math.floor(basIndex / kutuBasi) : 0;

  // O ana kadar okunan TÜM grupların (0..aktifGrup) kutularını DOM konumlarına göre
  // ölç. Kutular birikir; sonuncusu "aktif" işaretlenir.
  const olcKutular = useCallback(() => {
    const cont = containerRef.current;
    if (!cont || n === 0) { setKutular([]); return; }
    const cr = cont.getBoundingClientRect();
    const sonuc = [];
    for (let g = 0; g <= aktifGrup; g++) {
      const bas = g * kutuBasi;
      const son = Math.min(bas + kutuBasi, n);
      let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
      for (let k = bas; k < son; k++) {
        const el = wordRefs.current[k];
        if (!el) continue;
        const rc = el.getBoundingClientRect();
        l = Math.min(l, rc.left); t = Math.min(t, rc.top);
        r = Math.max(r, rc.right); b = Math.max(b, rc.bottom);
      }
      if (l === Infinity) continue;
      sonuc.push({
        left: l - cr.left + cont.scrollLeft - PAD,
        top: t - cr.top + cont.scrollTop - PAD,
        width: (r - l) + PAD * 2,
        height: (b - t) + PAD * 2,
        aktif: g === aktifGrup,
      });
    }
    setKutular(sonuc);
    // Aktif kutu görünür kalsın (uzun metinde otomatik kaydır)
    const ilk = wordRefs.current[basIndex];
    if (ilk) ilk.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [aktifGrup, basIndex, kutuBasi, n]);

  useLayoutEffect(() => { olcKutular(); }, [olcKutular, metin]);

  // Yeniden boyutlanma / reflow'da kutuları yeniden ölç.
  useEffect(() => {
    const cont = containerRef.current;
    if (!cont) return;
    const ro = new ResizeObserver(() => olcKutular());
    ro.observe(cont);
    window.addEventListener("resize", olcKutular);
    return () => { ro.disconnect(); window.removeEventListener("resize", olcKutular); };
  }, [olcKutular]);

  const ileri = useCallback(() => {
    setBasIndex((bi) => {
      if (bi >= sonGrupBas) { // son gruptayken ileri → bitti
        if (!bittiRef.current) { bittiRef.current = true; setBitti(true); onTamamla && onTamamla(); }
        return bi;
      }
      return Math.min(sonGrupBas, bi + kutuBasi);
    });
  }, [sonGrupBas, kutuBasi, onTamamla]);

  const geri = useCallback(() => {
    setBitti(false);
    setBasIndex((bi) => Math.max(0, bi - kutuBasi));
  }, [kutuBasi]);

  // Klavye: SAĞ/SOL ok.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "ArrowRight") { e.preventDefault(); ileri(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); geri(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ileri, geri]);

  // Kutu-başına-kelime değişince grup sınırına hizala.
  const kutuBasiDegistir = (yeni) => {
    setKutuBasi(yeni);
    setBasIndex((bi) => Math.floor(bi / yeni) * yeni);
    setBitti(false); bittiRef.current = false;
  };

  const ayarlar = (
    <div>
      <label className="text-xs text-gray-500 block mb-1.5">Kutu Başına Kelime</label>
      <div className="flex gap-1.5">
        {[1, 2, 3].map((k) => (
          <button key={k} onClick={() => kutuBasiDegistir(k)}
            className={`flex-1 py-1.5 rounded-lg text-sm font-semibold border transition ${
              kutuBasi === k ? "bg-indigo-600 border-indigo-600 text-white"
                             : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"}`}>{k}</button>
        ))}
      </div>
      <p className="text-[11px] text-gray-400 mt-1.5">Kutu aynı anda kaç kelimeyi çerçevelesin (1–3).</p>
    </div>
  );

  const aciklama =
    "Metin normal akan bir paragraf olarak görünür. SAĞ ok (veya ▶) ile ilerledikçe " +
    "her kelimeye bir kutu eklenir ve önceki kutular kalır; böylece kutular birikerek " +
    "metni sarar. Aktif kelime belirgin, geçilmiş kelimeler soluk kutuludur. SOL ok (◀) " +
    "ile geri gidilir. Kutu başına kelime sayısını (1/2/3) ayardan değiştirebilirsiniz. " +
    "Metin sınıf ve seviyenize göre otomatik seçilir.";

  const okunanSon = Math.min(basIndex + kutuBasi, n);

  return (
    <EgzersizDuzen koyu={false} ayarlar={ayarlar} aciklama={aciklama}>
      <div className="h-full flex flex-col p-3 sm:p-4">
        {/* Üst bilgi + kontroller */}
        <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
          <div className="min-w-0">
            <div className="font-bold text-gray-800 truncate">📦 {metin?.baslik || "Kutulu Okuma"}</div>
            {metin && (
              <div className="text-xs text-gray-500 flex items-center gap-2 mt-0.5 flex-wrap">
                <span>{metin.sinif ? `${metin.sinif}. sınıf` : "—"}</span>
                {metin.zorluk && (
                  <span className="px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-600 font-medium">
                    {ZORLUK_ETIKET[metin.zorluk] || metin.zorluk}
                  </span>
                )}
                <span>{n ? `kelime ${okunanSon} / ${n}` : ""}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={geri} disabled={yukleniyor || !n || basIndex === 0}
              title="Geri (◀ Sol ok)"
              className="w-9 h-9 rounded-lg border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40 text-lg leading-none">◀</button>
            <button onClick={ileri} disabled={yukleniyor || !n}
              title="İleri (▶ Sağ ok)"
              className="w-9 h-9 rounded-lg border border-indigo-200 bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-40 text-lg leading-none">▶</button>
            <button onClick={metinGetir} disabled={yukleniyor}
              className="px-3 py-1.5 rounded-lg text-sm font-semibold border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-50">🔄 Yeni Metin</button>
          </div>
        </div>

        {/* Metne yüklenmiş görsel (varsa) — image_prompt DEĞİL, öğretmen görseli */}
        {metin?.gorsel_var && !yukleniyor && !hata && (
          <div className="mb-3 flex justify-center">
            <img src={`${API}/diagnostic/texts/${metin.id}/gorsel`} alt={metin.baslik}
              className="max-h-44 rounded-xl border border-gray-200 object-contain" />
          </div>
        )}

        {/* Akan metin + hareketli çerçeve */}
        <div className="flex-1 overflow-y-auto rounded-xl bg-white border border-gray-200">
          {yukleniyor ? (
            <div className="h-full flex items-center justify-center text-gray-400 text-sm">Metin yükleniyor…</div>
          ) : hata ? (
            <div className="h-full flex flex-col items-center justify-center text-center gap-2 px-4">
              <div className="text-sm text-red-500">{hata}</div>
              <button onClick={metinGetir} className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-indigo-600 text-white">Tekrar dene</button>
            </div>
          ) : (
            <div
              ref={containerRef}
              className="relative px-4 sm:px-6 py-5 text-gray-800"
              style={{ fontSize: "1.4rem", lineHeight: 2.4 }}>
              {/* Biriken çerçeve kutuları (metnin altında; kelimeler üstte kalır).
                  Aktif kutu belirgin indigo, geçilmiş kutular soluk/gri. */}
              {kutular.map((k, i) => (
                <div
                  key={i}
                  className={`absolute pointer-events-none rounded-md transition-all duration-150 ease-out ${
                    k.aktif
                      ? "border-2 border-indigo-500 bg-indigo-500/15"
                      : "border border-gray-300 bg-gray-200/40"}`}
                  style={{ left: k.left, top: k.top, width: k.width, height: k.height, zIndex: 0 }}
                />
              ))}
              {kelimeler.map((w, idx) => (
                <React.Fragment key={idx}>
                  <span
                    ref={(el) => { wordRefs.current[idx] = el; }}
                    className="relative"
                    style={{ zIndex: 1 }}>{w}</span>
                  {" "}
                </React.Fragment>
              ))}
            </div>
          )}
        </div>

        {bitti && (
          <div className="mt-3 text-center text-sm font-bold text-green-600">✓ Metin bitti — puan işlendi.</div>
        )}
      </div>
    </EgzersizDuzen>
  );
}
