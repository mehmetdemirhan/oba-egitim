import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";

/**
 * OgretmenBasarilarim — öğretmene özel, tam genişlikte zengin başarı sayfası.
 * Hero (sıralama) + 6 KPI kart + zaman grafiği (XP/Rozet) + son rozetler + puan rehberi.
 * Yalnızca öğretmen panelinde (Gelişim → 🏆 Başarılarım) kullanılır.
 *
 * Props: apiBase — `${BACKEND_URL}/api`
 */
export default function OgretmenBasarilarim({ apiBase }) {
  const [veri, setVeri] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState(false);
  const [grafikSekme, setGrafikSekme] = useState("xp"); // xp | rozet

  useEffect(() => {
    let iptal = false;
    (async () => {
      setYukleniyor(true); setHata(false);
      try {
        const r = await axios.get(`${apiBase}/ogretmen/basarilarim`);
        if (!iptal) setVeri(r.data);
      } catch (e) {
        if (!iptal) setHata(true);
      } finally {
        if (!iptal) setYukleniyor(false);
      }
    })();
    return () => { iptal = true; };
  }, [apiBase]);

  const grafikData = useMemo(() => {
    if (!veri?.zaman_serisi) return [];
    const zs = veri.zaman_serisi;
    return zs.etiketler.map((e, i) => ({
      hafta: e.replace("Hafta ", "H"),
      xp: zs.xp_gelisim[i] ?? 0,
      rozet: zs.rozet_gelisim[i] ?? 0,
    }));
  }, [veri]);

  if (yukleniyor) return <div className="text-center py-16 text-gray-400 text-sm">Yükleniyor…</div>;
  if (hata || !veri) return <div className="text-center py-16 text-gray-400 text-sm">Başarılarım yüklenemedi.</div>;

  const pb = veri.puan_bilgisi || {};
  const fmt = (n) => (n || 0).toLocaleString("tr-TR");
  const eu = veri.kur_basarilari?.en_uzun_takip;

  const kpiKartlar = [
    { emoji: "🎖️", buyuk: `${veri.rozetler?.kazanilan_sayisi ?? 0}/${veri.rozetler?.toplam_rozet ?? 0}`, alt: "Kazanılan rozet", renk: "border-l-amber-400" },
    { emoji: "⭐", buyuk: `${veri.veli_degerlendirmesi?.ortalama ?? 0}/5`, alt: `Veli değerlendirmesi (${veri.veli_degerlendirmesi?.toplam_anket ?? 0} anket)`, renk: "border-l-pink-400" },
    { emoji: "👥", buyuk: `${veri.ogrenci_ozet?.toplam_ogrenci_tum ?? veri.ogrenci_ozet?.toplam_ogrenci ?? 0}`, alt: `Şimdiye kadar aldığın öğrenci (${veri.ogrenci_ozet?.aktif_ogrenci ?? 0} aktif)`, renk: "border-l-blue-400" },
    { emoji: "📝", buyuk: `${veri.icerik_ozet?.olusturulan_icerik ?? 0}`, alt: `Oluşturdum (${veri.icerik_ozet?.onaylanan_icerik ?? 0} onaylı)`, renk: "border-l-green-400" },
    { emoji: "🎓", buyuk: `${veri.kur_basarilari?.toplam_kur_atlatma ?? 0}`, alt: `Toplam kur atlatma (${veri.kur_basarilari?.kur_atlatilan_ogrenci_sayisi ?? 0} öğrenci)`, renk: "border-l-violet-400" },
    {
      emoji: "🏅",
      buyuk: eu ? `${eu.kur_sayisi} kur` : "—",
      alt: eu ? `${eu.ogrenci_adi} · Kur ${eu.baslangic_kur}→${eu.mevcut_kur}` : "Henüz kur atlatan öğrencin yok",
      renk: "border-l-emerald-400",
      soluk: !eu,
    },
  ];

  // Öğrenci çıktısı / bağlılık / kalite metrikleri
  const em = veri.ek_metrikler || {};
  const og = em.okuma_gelisim || {}, an = em.anlama || {}, gr = em.gorev || {}, bg = em.baglilik || {}, ik = em.icerik_kalitesi || {}, vl = em.veli || {};
  const etkiKartlar = [
    { emoji: "📈", buyuk: og.olculen_ogrenci ? `${og.wpm_artis > 0 ? "+" : ""}${og.wpm_artis} kel/dk` : "—",
      alt: og.olculen_ogrenci ? `Okuma hızı gelişimi (${og.olculen_ogrenci} öğrenci)` : "Okuma hızı — yeterli ölçüm yok", renk: "border-l-indigo-400", soluk: !og.olculen_ogrenci },
    { emoji: "🧠", buyuk: an.test_sayisi ? `%${an.ortalama_yuzde}` : "—",
      alt: an.test_sayisi ? `Anlama ortalaması (${an.test_sayisi} test)` : "Anlama — henüz test yok", renk: "border-l-sky-400", soluk: !an.test_sayisi },
    { emoji: "🎯", buyuk: gr.atanan ? `%${gr.oran}` : "—",
      alt: gr.atanan ? `Görev tamamlama (${gr.tamamlanan}/${gr.atanan})` : "Henüz görev atamadın", renk: "border-l-teal-400", soluk: !gr.atanan },
    { emoji: "🔥", buyuk: `%${bg.aktif_oran ?? 0}`, alt: "Son 7 günde aktif öğrenci", renk: "border-l-orange-400" },
    { emoji: "🚨", buyuk: `${bg.risk_ogrenci ?? 0}`, alt: "2 haftadır okumayan öğrenci", renk: "border-l-red-400", soluk: (bg.risk_ogrenci ?? 0) === 0 },
    { emoji: "💥", buyuk: `${ik.etki_ogrenci_sayisi ?? 0}`, alt: "İçeriğini tamamlayan öğrenci", renk: "border-l-fuchsia-400", soluk: (ik.etki_ogrenci_sayisi ?? 0) === 0 },
    { emoji: "📅", buyuk: `${bg.ortalama_streak ?? 0}`, alt: "Ort. okuma serisi (gün)", renk: "border-l-lime-500" },
    { emoji: "🤝", buyuk: `%${vl.yanit_orani ?? 0}`, alt: "Veli anket yanıt oranı", renk: "border-l-rose-400", soluk: (vl.yanit_orani ?? 0) === 0 },
  ];
  const ipuclari = veri.ipuclari || [];

  return (
    <div className="space-y-5">
      {/* ── ÜST: Hero kart ── */}
      <div className="rounded-2xl p-6 bg-gradient-to-r from-purple-500 to-indigo-500 text-white shadow-lg">
        <div className="text-sm font-medium opacity-90 flex items-center gap-2">🏆 Sıralaman</div>
        <div className="flex items-center gap-6 mt-3 flex-wrap">
          <div className="w-24 h-24 rounded-full bg-white/15 border-4 border-white/30 flex flex-col items-center justify-center shrink-0">
            <span className="text-4xl font-extrabold leading-none">{pb.sira ?? "—"}</span>
            <span className="text-xs opacity-80 mt-0.5">/ {pb.toplam_ogretmen ?? 0}</span>
          </div>
          <div className="min-w-0">
            <div className="text-xl font-bold">Sen {pb.sira ?? "—"}. sıradasın</div>
            <div className="text-sm opacity-80">{pb.toplam_ogretmen ?? 0} öğretmen içinde</div>
            <div className="mt-2 inline-flex items-center gap-2 bg-white/15 rounded-full px-3 py-1">
              <span className="text-xs opacity-90">Puanın</span>
              <span className="text-base font-bold">{fmt(pb.toplam_xp)} XP</span>
            </div>
            {pb.motivasyon_mesaji && (
              <p className="text-sm font-medium mt-3 opacity-95">💡 {pb.motivasyon_mesaji}</p>
            )}
          </div>
        </div>
      </div>

      {/* ── ORTA: Etkinliğin (6 KPI) ── */}
      <div>
        <h4 className="text-sm font-bold text-gray-500 mb-2 px-1">📌 Etkinliğin</h4>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {kpiKartlar.map((k, i) => (
            <div key={i} className={`bg-white rounded-2xl shadow-md p-5 border-l-4 ${k.renk} flex flex-col`}>
              <div className="text-3xl mb-1">{k.emoji}</div>
              <div className={`text-[28px] font-bold leading-tight ${k.soluk ? "text-gray-300" : "text-gray-800"}`}>{k.buyuk}</div>
              <div className="text-xs text-gray-500 mt-1 leading-snug">{k.alt}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Öğrenci Etkisi & Bağlılık (çıktı odaklı metrikler) ── */}
      <div>
        <h4 className="text-sm font-bold text-gray-500 mb-2 px-1">🚀 Öğrenci Etkisi & Bağlılık</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {etkiKartlar.map((k, i) => (
            <div key={i} className={`bg-white rounded-2xl shadow-md p-4 border-l-4 ${k.renk} flex flex-col`}>
              <div className="text-2xl mb-1">{k.emoji}</div>
              <div className={`text-[22px] font-bold leading-tight ${k.soluk ? "text-gray-300" : "text-gray-800"}`}>{k.buyuk}</div>
              <div className="text-[11px] text-gray-500 mt-1 leading-snug">{k.alt}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── ORTA-ALT: Zaman grafiği ── */}
      <div className="bg-white rounded-2xl shadow-md p-5">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
          <h4 className="text-sm font-bold text-gray-700">📈 Son 12 Hafta</h4>
          <div className="flex gap-1.5">
            {[{ v: "xp", l: "XP Gelişimi" }, { v: "rozet", l: "Rozet Kazanımları" }].map((t) => (
              <button key={t.v} onClick={() => setGrafikSekme(t.v)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-all ${grafikSekme === t.v ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"}`}>
                {t.l}
              </button>
            ))}
          </div>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={grafikData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="basariGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="hafta" tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} width={40} allowDecimals={false} />
              <Tooltip
                formatter={(v) => [v, grafikSekme === "xp" ? "XP" : "Rozet"]}
                labelFormatter={(l) => `Hafta ${String(l).replace("H", "")}`}
                contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }} />
              <Area type="monotone" dataKey={grafikSekme} stroke="#6366f1" strokeWidth={2.5} fill="url(#basariGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── ALT: Son Rozetler ── */}
      {veri.rozetler?.son_kazanilanlar?.length > 0 && (
        <div className="bg-white rounded-2xl shadow-md p-5">
          <h4 className="text-sm font-bold text-gray-700 mb-3">✨ Son Kazandıklarım</h4>
          <div className="flex flex-wrap gap-4">
            {veri.rozetler.son_kazanilanlar.map((r, i) => (
              <div key={i} className="flex flex-col items-center text-center w-24">
                <div className="text-3xl">{r.ikon}</div>
                <div className="text-[11px] font-semibold text-gray-700 mt-1 leading-tight line-clamp-2">{r.ad}</div>
                <div className="text-[10px] text-gray-400 mt-0.5">
                  {r.kazanma_tarihi ? new Date(r.kazanma_tarihi).toLocaleDateString("tr-TR") : ""}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Başarını artıracak ipuçları (dinamik) ── */}
      {ipuclari.length > 0 && (
        <div className="rounded-2xl shadow-md bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-100 p-5">
          <h4 className="font-semibold text-gray-800 mb-3">💡 Başarını Artıracak İpuçları</h4>
          <div className="space-y-2.5">
            {ipuclari.map((t, i) => (
              <div key={i} className="flex items-start gap-3 bg-white/70 rounded-xl p-3">
                <span className="text-xl leading-none mt-0.5">{t.ikon}</span>
                <div className="min-w-0">
                  <div className="text-sm font-bold text-gray-800">{t.baslik}</div>
                  <div className="text-xs text-gray-600 leading-snug mt-0.5">{t.mesaj}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── EN ALT: Puanın (XP) Nasıl Hesaplanır? ── */}
      {(() => {
        const kir = pb.kirilim || {};
        const ag = pb.agirliklar || {};
        // XP bileşenleri (kullanıcının gerçek kırılımı + kural)
        const bilesenler = [
          { ikon: "✅", ad: "Etkinlikler (içerik, test, oylama)", kural: "içerik +1 · test +10 · oylama +2 · yayın +5", puan: kir.etkinlik },
          { ikon: "🎖️", ad: "Kazandığın rozetler", kural: "her rozet kendi puanı kadar", puan: kir.rozet },
          { ikon: "👥", ad: "Aldığın öğrenciler", kural: `öğrenci başına +${ag.ogrenci_basi ?? 20}`, puan: kir.ogrenci },
          { ikon: "🎓", ad: "Kur atlattığın öğrenciler", kural: `her kur atlatma +${ag.kur_basi ?? 50}`, puan: kir.kur },
          { ikon: "⭐", ad: "Veli anket memnuniyeti", kural: `yıldız başına +${ag.veli_yildiz ?? 5} (5★ = +25/anket)`, puan: kir.veli },
        ];
        return (
          <div className="rounded-2xl shadow-md bg-gradient-to-br from-orange-50 to-yellow-50 p-5">
            <h4 className="font-semibold text-gray-800 mb-1">🎯 Puanın (XP) Nasıl Hesaplanır?</h4>
            <p className="text-xs text-gray-500 mb-3">
              Toplam XP'n aşağıdaki 5 kaynağın toplamıdır. <span className="font-medium text-gray-700">Sadece içerik üretmek değil;
              öğrenci alman, kur atlatman ve veli memnuniyetin de puanına doğrudan yansır.</span> Öğretmenler arası sıralaman bu toplama göre belirlenir.
            </p>
            <div className="space-y-1.5">
              {bilesenler.map((b, i) => (
                <div key={i} className="flex items-center justify-between gap-2 bg-white/60 rounded-lg px-3 py-2">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-gray-700">{b.ikon} {b.ad}</div>
                    <div className="text-[11px] text-gray-400">{b.kural}</div>
                  </div>
                  {b.puan != null && <span className="text-sm font-bold text-orange-600 shrink-0">{fmt(b.puan)}</span>}
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-orange-200">
              <span className="text-sm font-bold text-gray-800">Toplam XP'n</span>
              <span className="text-lg font-extrabold text-orange-600">{fmt(pb.toplam_xp)}</span>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
