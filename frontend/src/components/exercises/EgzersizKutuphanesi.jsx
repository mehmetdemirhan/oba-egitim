import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { getRenderComponent } from "./types";
import ExerciseSkeleton from "./ExerciseSkeleton";

// Tip listesi açıldığında arka planda ön-yüklenecek (prefetch) tip sayısı.
const PREFETCH_ADET = 3;

/**
 * EgzersizKutuphanesi — jenerik egzersiz motoru (UI tarafı).
 *
 * Tek bir bileşen tüm egzersiz tiplerini yönetir:
 *   1. /egzersiz/tipler ile kayıtlı tipleri listeler (kategoriye göre gruplu).
 *   2. Seçilen tip için /egzersiz/oturum başlatır, içeriği alır.
 *   3. Tipe uygun render bileşenini (types/index.js) seçip soru soru gösterir.
 *   4. Her cevabı /egzersiz/oturum/{id}/cevap ile değerlendirir.
 *   5. Bitince /egzersiz/oturum/{id}/bitir ile puan + XP hesaplar, sonucu gösterir.
 *
 * Tip başına özel kod YOKTUR; yeni tip eklemek = backend kaydı + bir render bileşeni.
 *
 * Props:
 *   apiBase      — `${BACKEND_URL}/api` (App.js'teki API sabiti)
 *   sinif        — varsayılan sınıf filtresi (öğrenci için user.sinif)
 *   ogretmenModu — true ise sınıf seçici her zaman açık (öğretmen önizlemesi)
 */
export default function EgzersizKutuphanesi({ apiBase, sinif = 3, ogretmenModu = false }) {
  // "tumu" → sınıf filtresi yok (tüm seviyeler). Öğretmen önizlemesinde varsayılan "Tümü";
  // öğrencide kendi sınıfı varsayılan kalır.
  const [secliSinif, setSecliSinif] = useState(ogretmenModu ? "tumu" : (Number(sinif) || 3));
  const tumMu = secliSinif === "tumu";
  // "Tümü" seçiliyken egzersiz başlatırken backend int sınıf bekler → tipin alt sınırını gönder.
  const sinifCozumle = (t) => (tumMu ? (t?.sinif_min || 3) : secliSinif);
  // Manuel zorluk seçimi (öğretmen/öğrenci). "oto" → adaptif (backend başarıya göre ayarlar).
  const [secliZorluk, setSecliZorluk] = useState("oto");
  const [tipler, setTipler] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(true);

  const [seciliTip, setSeciliTip] = useState(null);   // {id, ad, ...}
  const [oturum, setOturum] = useState(null);          // {oturum_id, tip, toplam_soru, icerik, mock}
  const [soruNo, setSoruNo] = useState(0);
  const [cevaplandi, setCevaplandi] = useState(false);
  const [dogruSayisi, setDogruSayisi] = useState(0);
  const [baslangic, setBaslangic] = useState(0);
  const [sonuc, setSonuc] = useState(null);
  const [hata, setHata] = useState(null);
  const [basliyor, setBasliyor] = useState(false);
  const [baslayanTip, setBaslayanTip] = useState(null); // skeleton için seçilen tip

  // Ön-yükleme (prefetch) cache'i — `${sinif}:${tipId}` -> Promise<oturumData>.
  // Tarayıcı deposu (localStorage vb.) YOK; sadece bileşen ömrü boyunca bellekte.
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
  }, [apiBase, secliSinif]);

  // Kategoriye göre grupla (listede başlıklı bölümler)
  const gruplar = useMemo(() => {
    const g = {};
    for (const t of tipler) {
      const k = t.kategori_ad || "Diğer";
      (g[k] = g[k] || []).push(t);
    }
    return g;
  }, [tipler]);

  // Tip listesi gelince ilk birkaç tipin oturumunu arka planda ön-yükle (prefetch).
  // Öğrenci bir tipe tıkladığında network çağrısı çoğunlukla zaten bitmiş olur.
  // Öğretmen önizlemesinde (ogretmenModu) prefetch yapılmaz — gereksiz oturum açmamak için.
  useEffect(() => {
    if (ogretmenModu || !tipler.length) return;
    tipler.slice(0, PREFETCH_ADET).forEach((t) => {
      const anahtar = `${secliSinif}:${t.id}`;
      if (prefetchRef.current[anahtar]) return;
      prefetchRef.current[anahtar] = axios
        .post(`${apiBase}/egzersiz/oturum`, { tip: t.id, sinif: sinifCozumle(t) })
        .then((r) => r.data)
        .catch(() => null);
    });
  }, [tipler, secliSinif, ogretmenModu, apiBase]);

  const egzersizBaslat = async (tip) => {
    if (basliyor) return;
    setBasliyor(true);
    setBaslayanTip(tip);   // skeleton bu tipin düzenine göre çizilir
    setHata(null);
    try {
      const anahtar = `${secliSinif}:${tip.id}`;
      let data = null;
      // Manuel zorluk seçiliyse ön-yükleme (varsayılan zorlukla açılmış) atlanır.
      if (secliZorluk === "oto" && prefetchRef.current[anahtar]) {
        data = await prefetchRef.current[anahtar];   // ön-yüklenmişse anında gelir
        delete prefetchRef.current[anahtar];          // tüketildi
      }
      if (!data) {
        const govde = { tip: tip.id, sinif: sinifCozumle(tip) };
        if (secliZorluk !== "oto") govde.zorluk = secliZorluk;
        const r = await axios.post(`${apiBase}/egzersiz/oturum`, govde);
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

  // Render bileşenlerinin çağırdığı ortak cevap fonksiyonu
  const onCevap = async (cevap) => {
    if (!oturum) return { dogru: false, dogru_cevap: null };
    try {
      const r = await axios.post(
        `${apiBase}/egzersiz/oturum/${oturum.oturum_id}/cevap`,
        { soru_no: soruNo, cevap }
      );
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
      const r = await axios.post(
        `${apiBase}/egzersiz/oturum/${oturum.oturum_id}/bitir`,
        { sure_sn: sure }
      );
      setSonuc(r.data);
    } catch (e) {
      setSonuc({
        dogru_sayisi: dogruSayisi,
        toplam_soru: oturum?.toplam_soru || 1,
        oran: 0, xp: 0, puan: 0,
      });
    }
  };

  const sonraki = () => {
    const toplam = oturum?.toplam_soru || 1;
    if (soruNo + 1 < toplam) {
      setSoruNo((n) => n + 1);
      setCevaplandi(false);
    } else {
      bitir();
    }
  };

  const kutuphaneyeDon = () => {
    setSeciliTip(null);
    setOturum(null);
    setSonuc(null);
    setSoruNo(0);
    setCevaplandi(false);
    setHata(null);
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
          <div className="text-3xl font-extrabold mt-3 text-gray-900">
            {sonuc.dogru_sayisi}/{sonuc.toplam_soru}
          </div>
          <div className="text-sm text-gray-500 mt-1">Başarı: %{oran}</div>
          <div className="flex items-center justify-center gap-3 mt-3 text-sm flex-wrap">
            <span className="px-3 py-1 rounded-full bg-indigo-100 text-indigo-700 font-semibold">+{sonuc.xp || 0} XP</span>
            <span className="px-3 py-1 rounded-full bg-purple-100 text-purple-700 font-semibold">+{sonuc.puan || 0} puan</span>
            {sonuc.skor != null && (
              <span className="px-3 py-1 rounded-full bg-amber-100 text-amber-700 font-semibold">⭐ {sonuc.skor} skor</span>
            )}
          </div>
          {sonuc.rekor != null && (
            <div className="mt-2 text-sm font-semibold">
              {sonuc.yeni_rekor
                ? <span className="text-green-600">🏆 Yeni Rekor! En Yüksek Skor: {sonuc.rekor}</span>
                : <span className="text-gray-500">En Yüksek Skor: {sonuc.rekor}</span>}
            </div>
          )}
        </div>
        <div className="flex items-center justify-center gap-2">
          <button onClick={tekrarDene}
            className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition">
            🔁 Tekrar Dene
          </button>
          <button onClick={kutuphaneyeDon}
            className="px-4 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">
            ← Kütüphaneye Dön
          </button>
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
        {/* Üst bar: başlık + ilerleme */}
        <div className="flex items-center justify-between">
          <button onClick={kutuphaneyeDon}
            className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1">
            ← Çık
          </button>
          <div className="text-sm font-semibold text-gray-700 flex items-center gap-2">
            <span>{seciliTip?.ikon} {seciliTip?.ad}</span>
            {oturum.mock && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-400">çevrimdışı</span>
            )}
          </div>
          <div className="text-xs font-medium text-gray-400">{Math.min(soruNo + 1, toplam)}/{toplam}</div>
        </div>

        {/* İlerleme çubuğu */}
        <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
          <div className="h-full bg-indigo-500 transition-all"
            style={{ width: `${(Math.min(soruNo + (cevaplandi ? 1 : 0), toplam) / toplam) * 100}%` }} />
        </div>

        {/* Soru render */}
        {Render ? (
          <Render icerik={oturum.icerik} onCevap={onCevap} soruNo={soruNo}
            ilerleme={{ mevcut: soruNo + 1, toplam }} />
        ) : (
          <div className="text-center py-10 text-gray-400">
            <div className="text-3xl mb-2">🚧</div>
            Bu egzersiz türünün görünümü henüz hazır değil.
          </div>
        )}

        {/* Sonraki / Bitir */}
        {(cevaplandi || !Render) && (
          <div className="flex justify-end">
            <button onClick={sonraki}
              className="px-5 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition">
              {sonSoru ? "Bitir ✓" : "Sonraki →"}
            </button>
          </div>
        )}
      </div>
    );
  }

  // ── YÜKLENİYOR (SKELETON) ──────────────────────────────────────
  // Bir tipe tıklandı, oturum/içerik henüz gelmedi → iskelet göster.
  if (basliyor && baslayanTip) {
    return (
      <ExerciseSkeleton
        puanlama={baslayanTip.puanlama}
        ad={baslayanTip.ad}
        ikon={baslayanTip.ikon}
      />
    );
  }

  // ── KÜTÜPHANE (TİP LİSTESİ) ────────────────────────────────────
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-base font-bold text-gray-800">🎯 Egzersiz Kütüphanesi</h3>
          <p className="text-xs text-gray-500">Bir egzersiz seç ve hemen başla.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <label className="text-xs text-gray-600 flex items-center gap-1.5">
            Zorluk:
            <select value={secliZorluk}
              onChange={(e) => setSecliZorluk(e.target.value)}
              className="px-2 py-1 rounded-lg border border-gray-200 text-sm bg-white">
              <option value="oto">Otomatik</option>
              <option value="kolay">Kolay</option>
              <option value="orta">Orta</option>
              <option value="zor">Zor</option>
            </select>
          </label>
          <label className="text-xs text-gray-600 flex items-center gap-1.5">
            Sınıf:
            <select value={secliSinif}
              onChange={(e) => { const v = e.target.value; setSecliSinif(v === "tumu" ? "tumu" : Number(v)); }}
              className="px-2 py-1 rounded-lg border border-gray-200 text-sm bg-white">
              {ogretmenModu && <option value="tumu">Tümü</option>}
              {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
                <option key={s} value={s}>{s}. sınıf</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {hata && (
        <div className="px-4 py-2 rounded-xl bg-red-50 border border-red-200 text-sm text-red-600">{hata}</div>
      )}

      {yukleniyor ? (
        <div className="text-center py-10 text-gray-400 text-sm">Yükleniyor…</div>
      ) : tipler.length === 0 ? (
        <div className="text-center py-10 text-gray-400 text-sm">Bu sınıf için egzersiz bulunamadı.</div>
      ) : (
        Object.entries(gruplar).map(([kategori, liste]) => (
          <div key={kategori} className="space-y-2">
            <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wide">{kategori}</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {liste.map((t) => (
                <button key={t.id} onClick={() => egzersizBaslat(t)} disabled={basliyor}
                  className="text-left p-3 rounded-2xl border border-gray-100 bg-white shadow-sm hover:shadow-md hover:border-indigo-200 transition disabled:opacity-50">
                  <div className="text-2xl mb-1">{t.ikon || "📝"}</div>
                  <div className="text-sm font-semibold text-gray-800 leading-tight">{t.ad}</div>
                  <div className="text-[11px] text-gray-400 mt-0.5 line-clamp-2">{t.aciklama}</div>
                </button>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
