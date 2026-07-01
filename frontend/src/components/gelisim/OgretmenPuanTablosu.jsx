import React, { useEffect, useState } from "react";
import axios from "axios";

/**
 * OgretmenPuanTablosu — öğretmene özel, motive edici puan tablosu.
 *
 * Öğrenci puanlarıyla KARIŞTIRILMAZ; yalnızca öğretmenler arası konum gösterilir.
 * Diğer öğretmenlerin İSİM ve SIRALARı gizlidir (backend isim/sıra listesi döndürmez).
 * Sadece kendi konum + isimsiz agrega istatistikler + motivasyon mesajı.
 *
 * Props:
 *   apiBase — `${BACKEND_URL}/api`
 */
export default function OgretmenPuanTablosu({ apiBase }) {
  const [veri, setVeri] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState(false);

  useEffect(() => {
    let iptal = false;
    (async () => {
      setYukleniyor(true);
      setHata(false);
      try {
        const r = await axios.get(`${apiBase}/puan-tablosu`, { params: { rol: "ogretmen" } });
        if (!iptal) setVeri(r.data);
      } catch (e) {
        if (!iptal) setHata(true);
      } finally {
        if (!iptal) setYukleniyor(false);
      }
    })();
    return () => { iptal = true; };
  }, [apiBase]);

  if (yukleniyor) return <div className="text-center py-10 text-gray-400 text-sm">Yükleniyor…</div>;
  if (hata || !veri) return <div className="text-center py-10 text-gray-400 text-sm">Puan tablosu yüklenemedi.</div>;

  const sira = veri.kullanicinin_sirasi;
  const toplam = veri.toplam_ogretmen || 0;
  const puan = veri.kullanicinin_puani || 0;
  const ist = veri.istatistikler || {};
  const enDusuk = ist.en_dusuk_puan || 0;
  const enYuksek = ist.en_yuksek_puan || 0;
  const ortalama = ist.ortalama_puan_ogretmen || 0;

  const fmt = (n) => (n || 0).toLocaleString("tr-TR");

  // Konum yüzdesi (en düşük 0% → en yüksek 100%)
  const aralik = Math.max(1, enYuksek - enDusuk);
  const konumYuzde = Math.min(100, Math.max(0, ((puan - enDusuk) / aralik) * 100));
  const ortYuzde = Math.min(100, Math.max(0, ((ortalama - enDusuk) / aralik) * 100));
  const ortUstunde = puan >= ortalama;

  return (
    <div className="space-y-4">
      {/* ── Üst: Konumun kartı ── */}
      <div className="rounded-2xl p-6 text-white bg-gradient-to-br from-indigo-600 to-purple-700 shadow-lg text-center">
        <div className="text-sm font-medium opacity-90 flex items-center justify-center gap-2">🏆 Sıralaman</div>
        <div className="text-5xl font-extrabold mt-3 leading-none">
          {sira ?? "—"}<span className="text-2xl font-bold opacity-70"> / {toplam}</span>
        </div>
        <div className="text-xs opacity-80 mt-2">{toplam} öğretmen içinde</div>
        <div className="mt-4 inline-flex items-center gap-2 bg-white/15 rounded-full px-4 py-1.5">
          <span className="text-xs opacity-90">Puanın</span>
          <span className="text-lg font-bold">{fmt(puan)}</span>
        </div>
      </div>

      {/* ── Orta: Karşılaştırma çubuğu (isim yok) ── */}
      <div className="rounded-2xl p-5 bg-white border border-gray-100 shadow-sm">
        <div className="text-sm font-bold text-gray-700 mb-4">📊 Öğretmenler Arası Konumun</div>
        <div className="relative h-3 rounded-full bg-gradient-to-r from-red-200 via-yellow-200 to-green-300 mt-2 mb-2">
          {/* Ortalama işareti */}
          <div className="absolute -top-1.5 w-0.5 h-6 bg-gray-400/70" style={{ left: `${ortYuzde}%` }} title="Ortalama" />
          {/* Senin konumun */}
          <div className="absolute -top-2.5 -translate-x-1/2 flex flex-col items-center" style={{ left: `${konumYuzde}%` }}>
            <div className="w-5 h-5 rounded-full bg-indigo-600 border-2 border-white shadow" />
          </div>
        </div>
        <div className="flex justify-between text-[11px] text-gray-400 mt-1">
          <span>En Düşük<br />{fmt(enDusuk)}</span>
          <span className="text-center">Ortalama<br />{fmt(ortalama)}</span>
          <span className="text-right">En Yüksek<br />{fmt(enYuksek)}</span>
        </div>
        <div className="mt-4 flex items-center justify-between bg-indigo-50 rounded-xl px-4 py-2.5">
          <span className="text-xs font-medium text-indigo-700">● Sen: {fmt(puan)}</span>
          <span className={`text-xs font-bold ${ortUstunde ? "text-green-600" : "text-orange-500"}`}>
            {ortUstunde ? "ortalamanın üstünde ▲" : "ortalamaya yakın"}
          </span>
        </div>
      </div>

      {/* ── Alt: Motivasyon mesajı ── */}
      {veri.motivasyon_mesaji && (
        <div className="rounded-2xl p-5 bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200">
          <div className="flex items-start gap-3">
            <span className="text-2xl">💡</span>
            <p className="text-sm font-medium text-amber-900 leading-relaxed">{veri.motivasyon_mesaji}</p>
          </div>
        </div>
      )}

      <p className="text-[11px] text-gray-400 text-center">
        Öğretmen puanları öğrenci puanlarından ayrı değerlendirilir. Diğer öğretmenlerin isimleri gizlidir.
      </p>
    </div>
  );
}
