import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { getRenderComponent } from "./types";
import ExerciseSkeleton from "./ExerciseSkeleton";
import ExerciseCard from "./ExerciseCard";

// Tip listesi açıldığında arka planda ön-yüklenecek (prefetch) tip sayısı.
const PREFETCH_ADET = 3;

/**
 * UnifiedExerciseGrid — klasik + yeni tüm egzersizleri TEK grid'de, kategoriye göre
 * gruplayarak ve TEK tasarım dilinde (ExerciseCard) gösterir.
 *
 * "Klasik / Yeni" ayrımı kullanıcıya görünmez:
 *   - Yeni tipler (ExerciseEngine) → içeride oturum başlatılıp render edilir.
 *   - Klasik egzersizler → parent'ın verdiği onClick ile eski komponentlerine gider.
 *
 * Props:
 *   apiBase      — `${BACKEND_URL}/api`
 *   sinif        — varsayılan sınıf filtresi (öğrenci için user.sinif)
 *   ogretmenModu — true ise "Tümü" seçeneği + varsayılan "Tümü"; prefetch kapalı
 *   klasikler    — [{ id, ad, aciklama, ikon, kategoriKey, onClick, sinif_min?, sinif_max? }]
 */

// Kategori → başlık + renk (gradient [from, to]). Anahtarlar hem backend tip
// kategorileriyle (kelime/anlama/oyun/gelismis/fonoloji/test) hem de klasik
// egzersizlere atadığımız anahtarlarla (goz/sesli/diger) örtüşür.
const KATEGORI_META = {
  goz:      { ad: "👁 Göz ve Okuma Becerileri", renk: ["#3B82F6", "#1E40AF"] },
  kelime:   { ad: "📝 Kelime ve Anlam",         renk: ["#8B5CF6", "#6D28D9"] },
  anlama:   { ad: "📖 Anlama ve Yorumlama",     renk: ["#F97316", "#C2410C"] },
  sesli:    { ad: "🎤 Sesli ve Diyalog",        renk: ["#10B981", "#047857"] },
  oyun:     { ad: "🎮 Oyun ve Eğlence",         renk: ["#EC4899", "#BE185D"] },
  fonoloji: { ad: "🔤 Fonolojik Farkındalık",   renk: ["#14B8A6", "#0F766E"] },
  gelismis: { ad: "🚀 Gelişmiş Beceriler",      renk: ["#06B6D4", "#0E7490"] },
  test:     { ad: "🧪 Deneme",                  renk: ["#64748B", "#334155"] },
  diger:    { ad: "📚 Diğer",                    renk: ["#64748B", "#334155"] },
};
// Kategorilerin görünüm sırası.
const KATEGORI_SIRA = ["goz", "kelime", "anlama", "sesli", "oyun", "fonoloji", "gelismis", "diger", "test"];

export default function UnifiedExerciseGrid({ apiBase, sinif = 3, ogretmenModu = false, klasikler = [] }) {
  // "tumu" → sınıf filtresi yok (tüm seviyeler). Öğretmen önizlemesinde varsayılan "Tümü".
  const [secliSinif, setSecliSinif] = useState(ogretmenModu ? "tumu" : (Number(sinif) || 3));
  const tumMu = secliSinif === "tumu";
  const sinifCozumle = (min) => (tumMu ? (min || 3) : secliSinif);

  const [tipler, setTipler] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(true);

  const [seciliTip, setSeciliTip] = useState(null);
  const [oturum, setOturum] = useState(null);
  const [soruNo, setSoruNo] = useState(0);
  const [cevaplandi, setCevaplandi] = useState(false);
  const [dogruSayisi, setDogruSayisi] = useState(0);
  const [baslangic, setBaslangic] = useState(0);
  const [sonuc, setSonuc] = useState(null);
  const [hata, setHata] = useState(null);
  const [basliyor, setBasliyor] = useState(false);
  const [baslayanTip, setBaslayanTip] = useState(null);

  const prefetchRef = useRef({});

  // Tip listesini çek (sınıf değişince yenile)
  useEffect(() => {
    let iptal = false;
    (async () => {
      setYukleniyor(true);
      try {
        const r = await axios.get(`${apiBase}/egzersiz/tipler`, { params: tumMu ? {} : { sinif: secliSinif } });
        if (!iptal) setTipler(r.data?.tipler || []);
      } catch (e) {
        if (!iptal) setTipler([]);
      } finally {
        if (!iptal) setYukleniyor(false);
      }
    })();
    return () => { iptal = true; };
  }, [apiBase, secliSinif, tumMu]);

  // İlk birkaç yeni tipi arka planda ön-yükle (öğrenci akışı; öğretmen önizlemesinde kapalı).
  useEffect(() => {
    if (ogretmenModu || !tipler.length) return;
    tipler.slice(0, PREFETCH_ADET).forEach((t) => {
      const anahtar = `${secliSinif}:${t.id}`;
      if (prefetchRef.current[anahtar]) return;
      prefetchRef.current[anahtar] = axios
        .post(`${apiBase}/egzersiz/oturum`, { tip: t.id, sinif: sinifCozumle(t.sinif_min) })
        .then((r) => r.data)
        .catch(() => null);
    });
  }, [tipler, secliSinif, ogretmenModu, apiBase]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Tüm öğeleri (klasik + yeni) birleştirip kategoriye göre grupla ──
  const gruplar = useMemo(() => {
    const items = [];
    for (const k of klasikler) {
      items.push({
        key: `klasik:${k.id}`,
        ad: k.ad, aciklama: k.aciklama, ikon: k.ikon,
        kategoriKey: KATEGORI_META[k.kategoriKey] ? k.kategoriKey : "diger",
        sinif_min: k.sinif_min || 1, sinif_max: k.sinif_max || 8,
        isKlasik: true, onClick: k.onClick,
      });
    }
    for (const t of tipler) {
      items.push({
        key: `tip:${t.id}`,
        ad: t.ad, aciklama: t.aciklama, ikon: t.ikon,
        kategoriKey: KATEGORI_META[t.kategori] ? t.kategori : "diger",
        sinif_min: t.sinif_min, sinif_max: t.sinif_max,
        isKlasik: false, tip: t,
      });
    }
    // Sınıf filtresi
    const uygun = items.filter((it) => tumMu || (it.sinif_min <= secliSinif && secliSinif <= it.sinif_max));
    // Kategoriye göre grupla, sabit sırada döndür
    const g = {};
    for (const it of uygun) (g[it.kategoriKey] = g[it.kategoriKey] || []).push(it);
    return KATEGORI_SIRA.filter((k) => g[k]?.length).map((k) => ({ key: k, meta: KATEGORI_META[k], liste: g[k] }));
  }, [klasikler, tipler, secliSinif, tumMu]);

  const egzersizBaslat = async (tip) => {
    if (basliyor) return;
    setBasliyor(true);
    setBaslayanTip(tip);
    setHata(null);
    try {
      const anahtar = `${secliSinif}:${tip.id}`;
      let data = null;
      if (prefetchRef.current[anahtar]) {
        data = await prefetchRef.current[anahtar];
        delete prefetchRef.current[anahtar];
      }
      if (!data) {
        const r = await axios.post(`${apiBase}/egzersiz/oturum`, { tip: tip.id, sinif: sinifCozumle(tip.sinif_min) });
        data = r.data;
      }
      setSeciliTip(tip);
      setOturum(data);
      setSoruNo(0);
      setCevaplandi(false);
      setDogruSayisi(0);
      setSonuc(null);
      setBaslangic(Date.now());
    } catch (e) {
      setHata("Egzersiz başlatılamadı. Lütfen tekrar deneyin.");
    } finally {
      setBasliyor(false);
      setBaslayanTip(null);
    }
  };

  const onCevap = async (cevap) => {
    if (!oturum) return { dogru: false, dogru_cevap: null };
    try {
      const r = await axios.post(`${apiBase}/egzersiz/oturum/${oturum.oturum_id}/cevap`, { soru_no: soruNo, cevap });
      setCevaplandi(true);
      if (r.data?.dogru) setDogruSayisi((s) => s + 1);
      return r.data;
    } catch (e) {
      setCevaplandi(true);
      return { dogru: false, dogru_cevap: null };
    }
  };

  const bitir = async () => {
    const sure = Math.max(0, Math.round((Date.now() - baslangic) / 1000));
    try {
      const r = await axios.post(`${apiBase}/egzersiz/oturum/${oturum.oturum_id}/bitir`, { sure_sn: sure });
      setSonuc(r.data);
    } catch (e) {
      setSonuc({ dogru_sayisi: dogruSayisi, toplam_soru: oturum?.toplam_soru || 1, oran: 0, xp: 0, puan: 0 });
    }
  };

  const sonraki = () => {
    const toplam = oturum?.toplam_soru || 1;
    if (soruNo + 1 < toplam) { setSoruNo((n) => n + 1); setCevaplandi(false); }
    else bitir();
  };

  const kutuphaneyeDon = () => {
    setSeciliTip(null); setOturum(null); setSonuc(null);
    setSoruNo(0); setCevaplandi(false); setHata(null);
  };

  const tekrarDene = () => seciliTip && egzersizBaslat(seciliTip);

  // ── SONUÇ EKRANI ───────────────────────────────────────────────
  if (sonuc) {
    const oran = sonuc.oran ?? 0;
    const basarili = oran >= 60;
    return (
      <div className="space-y-4">
        <div className={`rounded-2xl p-6 text-center border ${basarili ? "bg-green-50 border-green-200" : "bg-amber-50 border-amber-200"}`}>
          <div className="text-5xl mb-2">{basarili ? "🎉" : "💪"}</div>
          <div className="text-xl font-bold text-gray-800">{seciliTip?.ad}</div>
          <div className="text-3xl font-extrabold mt-3 text-gray-900">{sonuc.dogru_sayisi}/{sonuc.toplam_soru}</div>
          <div className="text-sm text-gray-500 mt-1">Başarı: %{oran}</div>
          <div className="flex items-center justify-center gap-4 mt-3 text-sm">
            <span className="px-3 py-1 rounded-full bg-indigo-100 text-indigo-700 font-semibold">+{sonuc.xp || 0} XP</span>
            <span className="px-3 py-1 rounded-full bg-purple-100 text-purple-700 font-semibold">+{sonuc.puan || 0} puan</span>
          </div>
        </div>
        <div className="flex items-center justify-center gap-2">
          <button onClick={tekrarDene} className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition">🔁 Tekrar Dene</button>
          <button onClick={kutuphaneyeDon} className="px-4 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">← Kütüphaneye Dön</button>
        </div>
      </div>
    );
  }

  // ── EGZERSİZ EKRANI ────────────────────────────────────────────
  if (oturum) {
    const Render = getRenderComponent(oturum.tip);
    const toplam = oturum.toplam_soru || 1;
    const sonSoru = soruNo + 1 >= toplam;
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <button onClick={kutuphaneyeDon} className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1">← Çık</button>
          <div className="text-sm font-semibold text-gray-700 flex items-center gap-2">
            <span>{seciliTip?.ikon} {seciliTip?.ad}</span>
            {oturum.mock && (<span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-400">çevrimdışı</span>)}
          </div>
          <div className="text-xs font-medium text-gray-400">{Math.min(soruNo + 1, toplam)}/{toplam}</div>
        </div>
        <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
          <div className="h-full bg-indigo-500 transition-all" style={{ width: `${(Math.min(soruNo + (cevaplandi ? 1 : 0), toplam) / toplam) * 100}%` }} />
        </div>
        {Render ? (
          <Render icerik={oturum.icerik} onCevap={onCevap} soruNo={soruNo} ilerleme={{ mevcut: soruNo + 1, toplam }} />
        ) : (
          <div className="text-center py-10 text-gray-400"><div className="text-3xl mb-2">🚧</div>Bu egzersiz türünün görünümü henüz hazır değil.</div>
        )}
        {(cevaplandi || !Render) && (
          <div className="flex justify-end">
            <button onClick={sonraki} className="px-5 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition">{sonSoru ? "Bitir ✓" : "Sonraki →"}</button>
          </div>
        )}
      </div>
    );
  }

  // ── YÜKLENİYOR (SKELETON) ──────────────────────────────────────
  if (basliyor && baslayanTip) {
    return <ExerciseSkeleton puanlama={baslayanTip.puanlama} ad={baslayanTip.ad} ikon={baslayanTip.ikon} />;
  }

  // ── BİRLEŞİK GRID (KATEGORİLER) ────────────────────────────────
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-base font-bold text-gray-800">🎯 Egzersizler</h3>
          <p className="text-xs text-gray-500">Bir egzersiz seç ve hemen başla.</p>
        </div>
        <label className="text-xs text-gray-600 flex items-center gap-1.5">
          Sınıf:
          <select value={secliSinif}
            onChange={(e) => { const v = e.target.value; setSecliSinif(v === "tumu" ? "tumu" : Number(v)); }}
            className="px-2 py-1 rounded-lg border border-gray-200 text-sm bg-white">
            {ogretmenModu && <option value="tumu">Tümü</option>}
            {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (<option key={s} value={s}>{s}. sınıf</option>))}
          </select>
        </label>
      </div>

      {hata && (<div className="px-4 py-2 rounded-xl bg-red-50 border border-red-200 text-sm text-red-600">{hata}</div>)}

      {yukleniyor ? (
        <div className="text-center py-10 text-gray-400 text-sm">Yükleniyor…</div>
      ) : gruplar.length === 0 ? (
        <div className="text-center py-10 text-gray-400 text-sm">Bu sınıf için egzersiz bulunamadı.</div>
      ) : (
        gruplar.map(({ key, meta, liste }) => (
          <div key={key} className="space-y-2">
            <h4 className="text-sm font-bold text-gray-500">{meta.ad}</h4>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {liste.map((it) => (
                <ExerciseCard key={it.key} ad={it.ad} aciklama={it.aciklama} ikon={it.ikon} renk={meta.renk}
                  disabled={basliyor}
                  onClick={() => (it.isKlasik ? it.onClick && it.onClick() : egzersizBaslat(it.tip))} />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
