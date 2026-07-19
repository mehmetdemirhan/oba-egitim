import React from "react";
import {
  ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar,
  CartesianGrid, XAxis, YAxis, Tooltip, Legend,
} from "recharts";
import {
  TrendingUp, AlertTriangle, Users, UserCheck, BookOpen, Calendar,
  Medal, Heart, Star, Wallet, BarChart3, PieChart as PieChartIcon,
  GraduationCap,
} from "lucide-react";
import BilgiIkonu from "./BilgiIkonu";
import { DashboardKart, StatKart, Bolum, BosDurum } from "./dashboard/Kart";
import { GRAFIK, EKSEN_TICK, doluAySayisi, MIN_AY } from "./dashboard/dashboardTema";
import { useAnalitik, HuniKarti, SatisKarti, NakitKarti, OgretmenPerfKarti } from "./admin/DashboardAnalitik";

/**
 * Dashboard — App.js'ten izole edilmiş yönetici gösterge paneli.
 * • Tek kart sistemi (DashboardKart/StatKart) → tüm kartlar aynı görsel aile.
 * • Adlandırılmış bölümler (Bolum): Genel Durum · Finansal Sağlık · Büyüme & Satış
 *   · Öğretmen Performansı.
 * • Tek semantik palet (dashboardTema) → grafikler tutarlı renkli.
 * • Veri azlığında zarif boş durum (BosDurum) → boş 12 ay ekseni yok.
 * Veri çekme AppContent'te kalır; buraya props ile gelir (davranış korunur).
 */
export default function Dashboard({
  user, adminVeyaKoord, dashboardStats, ogrenciRiskler = [], adminAnketOzet = [],
  sinifDagilimi, monthlyStats = [], api, formatCurrency,
  onTab, onYaslandirmaSec, onOgretmenSec, ustSerit,
}) {
  const analitik = useAnalitik(api);
  if (!dashboardStats) return null;

  const koord = user.role === "coordinator";
  const yuksekRisk = ogrenciRiskler.filter((r) => r.risk_seviye === "yuksek");
  const aylikDolu = doluAySayisi(monthlyStats, ["yeni_ogrenciler", "gelir"]);
  const sonAy = monthlyStats.length ? monthlyStats[monthlyStats.length - 1] : null;

  const pieData = [
    { name: "Öğrenci Alacakları", value: dashboardStats.toplam_ogrenci_alacak || 0, color: GRAFIK.basari },
    { name: "Öğretmen Borçları", value: dashboardStats.toplam_ogretmen_borc || 0, color: GRAFIK.tehlike },
  ];
  const pieDataKoord = [
    { name: "Yeni Kayıt", value: dashboardStats.bu_ay_yeni_kayit || 0, color: GRAFIK.bilgi },
    { name: "Kur Atlayan", value: dashboardStats.bu_ay_kur_atlayan || 0, color: GRAFIK.basari },
  ];
  const pieToplam = (d) => d.reduce((t, x) => t + (x.value || 0), 0);

  const Donut = ({ data, formatter, birim }) => {
    const toplam = pieToplam(data);
    if (toplam <= 0) return <BosDurum minAy={1} mesaj="Henüz veri yok — kayıt/ödeme girildikçe burada görünecek." />;
    return (
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={55} outerRadius={88} dataKey="value" nameKey="name" stroke="var(--surface, #fff)" strokeWidth={2} paddingAngle={2}>
            {data.map((e, i) => <Cell key={i} fill={e.color} />)}
          </Pie>
          <Tooltip formatter={formatter} />
          <Legend verticalAlign="bottom" height={28} iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    );
  };

  return (
    <div className="space-y-8">
      {/* ══ GENEL DURUM ══ */}
      <Bolum baslik="Genel Durum" aciklama="Önce görülmesi gerekenler — bekleyen işler, risk ve temel sayılar.">
        {ustSerit && <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">{ustSerit}</div>}

        {ogrenciRiskler.length > 0 && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatKart etiket="Düşük Risk" ton="basari" ikon={Users} deger={ogrenciRiskler.filter((r) => r.risk_seviye === "dusuk").length} altYazi="öğrenci" />
            <StatKart etiket="Orta Risk" ton="uyari" ikon={Users} deger={ogrenciRiskler.filter((r) => r.risk_seviye === "orta").length} altYazi="öğrenci" />
            <StatKart etiket="Yüksek Risk" ton="tehlike" vurgulu ikon={AlertTriangle} deger={yuksekRisk.length} altYazi="öğrenci — müdahale gerekli" />
            <StatKart etiket="North Star" ton="bilgi" ikon={TrendingUp} sagUst={<BilgiIkonu k="risk" />}
              deger={`${ogrenciRiskler.length ? Math.round(ogrenciRiskler.filter((r) => r.aktif_gunler_7 >= 4).length / ogrenciRiskler.length * 100) : 0}%`}
              altYazi="haftada 4+ gün okuyan" />
          </div>
        )}

        {yuksekRisk.length > 0 && (
          <DashboardKart baslik="Yüksek Riskli Öğrenciler" ikon={AlertTriangle} bilgi="risk" className="border-l-4 border-l-red-500">
            <div className="space-y-2">
              {yuksekRisk.slice(0, 5).map((r) => (
                <div key={r.id} className="flex items-center justify-between p-2.5 bg-red-500/5 rounded-lg">
                  <div><span className="font-medium text-sm text-content">{r.ad} {r.soyad}</span><span className="text-xs text-subtle ml-2">{r.sinif}. sınıf</span></div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="text-subtle">Streak: {r.streak}</span>
                    <span className="text-subtle">7g: {r.dakika_7}dk</span>
                    <span className="bg-red-500/15 text-red-600 px-2 py-0.5 rounded-full font-bold tabular-nums">Risk: {r.risk_skoru}</span>
                  </div>
                </div>
              ))}
            </div>
          </DashboardKart>
        )}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatKart etiket="Öğrenci" ton="basari" ikon={Users} deger={dashboardStats.toplam_ogrenci} onClick={() => onTab("students")} sagUst={<BilgiIkonu k="sayilar" />} />
          <StatKart etiket="Öğretmen" ton="bilgi" ikon={UserCheck} deger={dashboardStats.toplam_ogretmen} onClick={() => onTab("teachers")} />
          <StatKart etiket="Kurs" ton="uyari" ikon={BookOpen} deger={dashboardStats.toplam_kurs} onClick={() => onTab("courses")} />
          {koord ? (
            <StatKart etiket="Bu Ay Yeni Kayıt" ton="notr" ikon={Calendar} deger={dashboardStats.bu_ay_yeni_kayit || 0} onClick={() => onTab("students")} sagUst={<BilgiIkonu k="bu_ay" />} />
          ) : (
            <StatKart etiket="Bu Ay Tahsilat" ton="notr" ikon={Calendar} deger={formatCurrency(dashboardStats.bu_ay_odenen_toplam)} onClick={() => onTab("payments")} sagUst={<BilgiIkonu k="bu_ay" />} />
          )}
        </div>
      </Bolum>

      {/* ══ FİNANSAL SAĞLIK (yalnız yönetici) ══ */}
      {!koord && (
        <Bolum baslik="Finansal Sağlık" aciklama="Alacak/borç dengesi, nakit akışı ve yaşlanan tahsilat.">
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-stretch">
            <DashboardKart baslik="Finansal Durum" ikon={Wallet} bilgi="finansal_durum" className="xl:col-span-1">
              <div className="h-60" role="img" aria-label="Finansal durum: öğrenci alacakları ve öğretmen borçları">
                <Donut data={pieData} formatter={(v) => formatCurrency(v)} />
              </div>
            </DashboardKart>
            <div className="xl:col-span-2">
              {analitik ? <NakitKarti veri={analitik} onYaslandirmaSec={onYaslandirmaSec} />
                : <DashboardKart baslik="Nakit Akışı & Alacak Yaşlandırma" ikon={TrendingUp}><div className="h-40 grid place-items-center text-sm text-subtle">Yükleniyor…</div></DashboardKart>}
            </div>
          </div>
        </Bolum>
      )}

      {/* ══ BÜYÜME & SATIŞ ══ */}
      <Bolum baslik="Büyüme & Satış" aciklama="Yeni kayıt, yenileme ve kur geçiş performansı.">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {!koord && (
            <DashboardKart baslik="Aylık İstatistikler" ikon={BarChart3} bilgi="aylik_istatistik">
              <div className="h-60" role="img" aria-label="Aylık yeni öğrenci ve gelir">
                {aylikDolu >= MIN_AY ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={monthlyStats}>
                      <CartesianGrid strokeDasharray="3 3" stroke={GRAFIK.izgara} vertical={false} />
                      <XAxis dataKey="ay" tick={EKSEN_TICK} /><YAxis tick={EKSEN_TICK} />
                      <Tooltip /><Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="yeni_ogrenciler" name="Yeni Öğrenci" fill={GRAFIK.bilgi} radius={[3, 3, 0, 0]} />
                      <Bar dataKey="gelir" name="Gelir" fill={GRAFIK.basari} radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <BosDurum ozet={sonAy ? [
                    { etiket: "Bu ay yeni öğrenci", deger: sonAy.yeni_ogrenciler ?? 0 },
                    { etiket: "Bu ay gelir", deger: formatCurrency(sonAy.gelir) },
                  ] : []} />
                )}
              </div>
            </DashboardKart>
          )}
          <DashboardKart baslik="Yeni Kayıt vs Kur Atlayan (Bu Ay)" ikon={PieChartIcon} bilgi="yeni_vs_kuratlayan">
            <div className="h-60" role="img" aria-label="Bu ay yeni kayıt ve kur atlayan dağılımı">
              <Donut data={pieDataKoord} formatter={(v, n) => [`${v} öğrenci`, n]} />
            </div>
          </DashboardKart>
          <DashboardKart baslik="Öğrenci Sınıf Dağılımı" ikon={GraduationCap} bilgi="sinif_dagilimi">
            <div className="h-60" role="img" aria-label="Aktif öğrencilerin sınıf dağılımı">
              {(sinifDagilimi?.dagilim || []).some((d) => d.sayi > 0) ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sinifDagilimi.dagilim}>
                    <CartesianGrid strokeDasharray="3 3" stroke={GRAFIK.izgara} vertical={false} />
                    <XAxis dataKey="sinif" tick={EKSEN_TICK} /><YAxis allowDecimals={false} tick={EKSEN_TICK} />
                    <Tooltip formatter={(v) => [`${v} öğrenci`, "Sayı"]}
                      labelFormatter={(l) => { const d = (sinifDagilimi?.dagilim || []).find((x) => x.sinif === l); return d ? `${d.etiket} · toplam içinde %${d.yuzde}` : l; }} />
                    <Bar dataKey="sayi" name="Öğrenci" radius={[4, 4, 0, 0]}>
                      {sinifDagilimi.dagilim.map((e, i) => <Cell key={i} fill={e.sinif === "?" ? GRAFIK.notr : GRAFIK.bilgi} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : <BosDurum minAy={1} mesaj="Sınıf verisi yok." />}
            </div>
          </DashboardKart>
        </div>
        {analitik && <SatisKarti veri={analitik} />}
        {analitik && <HuniKarti veri={analitik} />}
      </Bolum>

      {/* ══ ÖĞRETMEN PERFORMANSI ══ */}
      <Bolum baslik="Öğretmen Performansı" aciklama="Öğretmen bazında yük, yenileme, süre ve veli memnuniyeti.">
        {analitik && <OgretmenPerfKarti veri={analitik} onOgretmenSec={onOgretmenSec} />}
        {adminAnketOzet.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <DashboardKart baslik="Öğretmen Rozet Durumu" ikon={Medal} bilgi="rozet_durumu">
              <div className="space-y-2.5">
                {adminAnketOzet.map((o) => (
                  <div key={o.id} className="flex items-center justify-between p-2.5 bg-app rounded-xl">
                    <div className="font-medium text-sm text-content truncate">{o.ad} {o.soyad}</div>
                    <div className="flex items-center gap-2 shrink-0">
                      <div className="bg-app rounded-full h-2 w-24 overflow-hidden border border-line"><div className="h-2 bg-primary rounded-full" style={{ width: `${(o.rozet_sayisi / Math.max(o.rozet_toplam, 1)) * 100}%` }} /></div>
                      <span className="text-xs font-medium text-subtle tabular-nums">{o.rozet_sayisi}/{o.rozet_toplam}</span>
                    </div>
                  </div>
                ))}
              </div>
            </DashboardKart>
            <DashboardKart baslik="Veli Değerlendirme Özeti" ikon={Heart} bilgi="veli_degerlendirme">
              <div className="space-y-2.5">
                {adminAnketOzet.map((o) => (
                  <div key={o.id} className="flex items-center justify-between p-2.5 bg-app rounded-xl">
                    <div className="min-w-0"><div className="font-medium text-sm text-content truncate">{o.ad} {o.soyad}</div><div className="text-xs text-subtle">{o.anket?.anket_sayisi || 0} anket</div></div>
                    <div className="flex items-center gap-3 shrink-0">
                      {o.anket?.anket_sayisi > 0 ? (<>
                        <span className="inline-flex items-center gap-1 text-lg font-bold text-content tabular-nums"><Star className="h-4 w-4 text-amber-500 fill-amber-500" />{o.anket.ortalama}</span>
                        <span className="text-xs text-emerald-600 font-medium tabular-nums">%{o.anket.tavsiye_oran} tavsiye</span>
                      </>) : (<span className="text-xs text-subtle/60">Anket yok</span>)}
                    </div>
                  </div>
                ))}
              </div>
            </DashboardKart>
          </div>
        )}
      </Bolum>
    </div>
  );
}
