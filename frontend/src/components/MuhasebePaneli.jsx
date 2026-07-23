import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Card, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { useToast } from "../hooks/use-toast";
import { Wallet, TrendingUp, TrendingDown, Clock, LogOut, GraduationCap, Users, Receipt, PiggyBank, AlertTriangle, Send } from "lucide-react";
import OdemeTablosu from "./OdemeTablosu";
import MuhasebeAyarlari from "./admin/MuhasebeAyarlari";
import OgretmenDonemOdeme from "./admin/OgretmenDonemOdeme";
import GecikenKurlar from "./admin/GecikenKurlar";
import FunnelPanel from "./admin/FunnelPanel";
import BilgiIkonu from "./BilgiIkonu";
import HerseyiAra from "./HerseyiAra";
import { PersonaBalon, PERSONA_UI } from "./aiceo/Personalar";

// Muhasebe rolüne özel "Sistem Danışmanı Miran" kartı (finansal; pedagojik veri YOK)
function MuhasebeMiran({ apiBase, onOdak }) {
  const [miran, setMiran] = React.useState(null);
  const [gb, setGb] = React.useState(null);
  const p = PERSONA_UI.miran;
  React.useEffect(() => { axios.get(`${apiBase}/ai/ceo/miran/muhasebe`).then(r => setMiran(r.data.miran)).catch(() => {}); }, [apiBase]);
  const bildir = async (f) => { if (!miran) return; try { await axios.post(`${apiBase}/ai/ceo/miran/${miran.id}/geri-bildirim`, { faydali: f }); setGb(f); } catch (e) {} };
  if (!miran) return null;
  return (
    <div className="rounded-2xl border p-4 shadow-sm mb-4" style={{ borderColor: p.renkAcik, background: p.renkAcik + "33" }}>
      <PersonaBalon persona="miran" mesaj={miran.icerik?.selam} size={56} />
      <div className="mt-3 space-y-2">
        {(miran.icerik?.oneriler || []).map((o, i) => {
          const tiklanabilir = !!(o.hedef && onOdak);
          return (
            <div key={i} onClick={tiklanabilir ? () => onOdak(o) : undefined}
              className={`rounded-xl bg-surface border p-3 ${tiklanabilir ? "border-primary/40 cursor-pointer hover:ring-2 hover:ring-primary/30 transition" : "border-line"}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold text-content text-sm">{o.baslik}</div>
                {tiklanabilir && <span className="text-xs text-primary shrink-0 whitespace-nowrap">Ödemelere git →</span>}
              </div>
              <div className="text-sm text-subtle mt-0.5">{o.aciklama}</div>
            </div>
          );
        })}
      </div>
      {miran.icerik?.kapanis && <div className="mt-2 text-sm font-medium" style={{ color: p.renk }}>{miran.icerik.kapanis}</div>}
      <div className="mt-2 pt-2 border-t flex items-center gap-3" style={{ borderColor: p.renkAcik }}>
        <span className="text-xs text-subtle">Faydalı mı?</span>
        <button onClick={() => bildir(true)} className={`text-xs px-2 py-1 rounded-lg border ${gb === true ? "bg-emerald-100 text-emerald-700 border-emerald-200" : "border-line"}`}>👍 Faydalı</button>
        <button onClick={() => bildir(false)} className={`text-xs px-2 py-1 rounded-lg border ${gb === false ? "bg-red-100 text-red-600 border-red-200" : "border-line"}`}>👎 Faydasız</button>
        {gb !== null && <span className="text-xs" style={{ color: p.renk }}>Teşekkürler!</span>}
      </div>
    </div>
  );
}

/**
 * MuhasebePaneli — "accountant" rolüne özel SADE ödeme paneli.
 * Yönetim sekme çubuğu YOK. Excel-benzeri satır içi düzenlenebilir tablolar
 * (OdemeTablosu — admin Muhasebe sekmesiyle paylaşılan bileşen).
 */
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatTL = (v) =>
  new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 0 }).format(Number(v || 0));

function KpiKart({ Ikon, etiket, tutar, vurgu, bilgi }) {
  const renk = {
    blue: ["border-l-blue-500", "text-blue-600"],
    green: ["border-l-emerald-500", "text-emerald-600"],
    amber: ["border-l-amber-500", "text-amber-600"],
    slate: ["border-l-slate-400", "text-slate-600"],
    red: ["border-l-red-500", "text-red-600"],
  }[vurgu] || ["border-l-slate-400", "text-slate-600"];
  return (
    <Card className="border border-line shadow-sm">
      <CardContent className={`p-4 border-l-4 rounded-l-none ${renk[0]}`}>
        <div className="flex items-center justify-between gap-1.5 text-xs text-subtle mb-1">
          <span className="flex items-center gap-1.5"><Ikon className={`h-4 w-4 ${renk[1]}`} />{etiket}</span>
          {bilgi && <BilgiIkonu k={bilgi} />}
        </div>
        <div className={`text-2xl font-bold tabular-nums ${renk[1]}`}>{formatTL(tutar)}</div>
      </CardContent>
    </Card>
  );
}

export default function MuhasebePaneli({ user, logout }) {
  const { toast } = useToast();
  const [ozet, setOzet] = useState(null);
  const [kisiler, setKisiler] = useState({ ogrenciler: [], ogretmenler: [] });
  const [payments, setPayments] = useState([]);
  const [sekme, setSekme] = useState("ogrenci");
  useEffect(() => {   // genel arama → sekme yönlendirmesi
    const h = (e) => { const d = e.detail || {}; if (d.sekme) setSekme(d.sekme); };
    window.addEventListener("oba-git", h);
    return () => window.removeEventListener("oba-git", h);
  }, []);
  const [sadeceBorclu, setSadeceBorclu] = useState(false);
  const [odakIdler, setOdakIdler] = useState(null);  // Miran deep-link: işaretsiz ödeme öğrenci id'leri

  // Miran notuna tıklama → ilgili ödemelere git (öğrenci sekmesi + odak/filtre)
  const miranOdak = (o) => {
    setSekme("ogrenci");
    if (o.hedef === "borclu") { setSadeceBorclu(true); setOdakIdler(null); }
    else if (o.hedef === "damgasiz") { setSadeceBorclu(false); setOdakIdler(o.odak_idler || []); }
  };

  const veriYukle = useCallback(async () => {
    try {
      const [o, k, p] = await Promise.all([
        axios.get(`${API}/muhasebe/ozet`),
        axios.get(`${API}/muhasebe/kisiler`),
        axios.get(`${API}/payments`),
      ]);
      setOzet(o.data);
      setKisiler(k.data || { ogrenciler: [], ogretmenler: [] });
      setPayments(Array.isArray(p.data) ? p.data : []);
    } catch {
      toast({ title: "Veriler yüklenemedi", variant: "destructive" });
    }
  }, [toast]);

  useEffect(() => { veriYukle(); }, [veriYukle]);

  const liste = sekme === "ogrenci" ? kisiler.ogrenciler : kisiler.ogretmenler;
  const ogr = ozet?.ogrenci || {}; const ogt = ozet?.ogretmen || {};

  const tabButon = (id, etiket, Ikon) => (
    <button onClick={() => setSekme(id)}
      className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all ${sekme === id ? "bg-primary text-white border-primary" : "bg-surface text-subtle border-line hover:bg-app"}`}>
      <Ikon className="h-4 w-4" />{etiket}
    </button>
  );

  return (
    <div className="min-h-dvh bg-app">
      <header className="bg-surface border-b border-line">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center h-9 w-9 rounded-xl bg-primary text-white"><Wallet className="h-5 w-5" /></span>
            <div>
              <div className="font-bold text-content leading-tight">OBA Muhasebe</div>
              <div className="text-xs text-subtle">{user?.ad} {user?.soyad}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <HerseyiAra apiBase={API} user={user} />
            <Button variant="ghost" size="sm" onClick={logout} className="text-subtle">
              <LogOut className="h-4 w-4 mr-1" />Çıkış
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-8 gap-3">
          {/* Alınmayan kartı tıklanabilir (buton) — (i) ikonu iç içe buton olmasın diye köşede ayrı */}
          <div className="relative">
            <button type="button" onClick={() => { setSadeceBorclu(true); setSekme("ogrenci"); }} className="text-left w-full">
              <Card className="border border-line shadow-sm hover:ring-2 hover:ring-amber-300 transition-all h-full">
                <CardContent className="p-4 border-l-4 border-l-amber-500 rounded-l-none">
                  <div className="flex items-center gap-1.5 text-xs text-subtle mb-1"><AlertTriangle className="h-4 w-4 text-amber-600" />Alınmayan Ödeme</div>
                  <div className="text-2xl font-bold tabular-nums text-amber-600">{ozet?.alinmayan?.sayi ?? 0}</div>
                  <div className="text-[11px] text-subtle tabular-nums">{formatTL(ozet?.alinmayan?.toplam_kalan ?? 0)} kalan</div>
                </CardContent>
              </Card>
            </button>
            <span className="absolute top-3 right-3"><BilgiIkonu k="m_alinmayan" /></span>
          </div>
          <KpiKart Ikon={TrendingUp} etiket="Beklenen Tahsilat" tutar={ogr.beklenen} vurgu="blue" bilgi="m_beklenen" />
          <KpiKart Ikon={Wallet} etiket="Tahsil Edilen (brüt)" tutar={ogr.tahsil_edilen} vurgu="green" bilgi="m_tahsil" />
          <KpiKart Ikon={Receipt} etiket={`Toplam Vergi (%${ozet?.vergi?.oran ?? 15})`} tutar={ozet?.vergi?.toplam_vergi} vurgu="red" bilgi="m_vergi" />
          <KpiKart Ikon={Clock} etiket="Bekleyen Tahsilat" tutar={ogr.bekleyen} vurgu="amber" bilgi="m_bekleyen" />
          <KpiKart Ikon={TrendingDown} etiket="Öğretmene Ödenecek" tutar={ogt.odenecek} vurgu="slate" bilgi="m_ogretmene_odenecek" />
          <KpiKart Ikon={Wallet} etiket="Öğretmene Ödenen" tutar={ogt.odenen} vurgu="green" bilgi="m_ogretmene_odenen" />
          <KpiKart Ikon={PiggyBank} etiket="Net Kasa (vergi düşülmüş)" tutar={ozet?.kasa_net} vurgu="green" bilgi="m_net_kasa" />
        </div>

        <MuhasebeMiran apiBase={API} onOdak={miranOdak} />

        <GecikenKurlar apiBase={API} />

        <div className="flex flex-wrap gap-2">
          {tabButon("ogrenci", "Öğrenci Ödemeleri", GraduationCap)}
          {tabButon("ogretmen", "Öğretmen Ödemeleri", Users)}
          {tabButon("funnel", "Veli Mesajları", Send)}
        </div>

        {(sekme === "ogrenci" || sekme === "ogretmen") && (
          <OdemeTablosu tip={sekme} kisiler={liste} payments={payments} apiBase={API} onDegisim={veriYukle}
            sadeceBorclu={sekme === "ogrenci" && sadeceBorclu} onBorcluTemizle={() => setSadeceBorclu(false)}
            odakKisiId={sekme === "ogrenci" ? (odakIdler || "") : ""} onOdakTemizle={() => setOdakIdler(null)} />
        )}

        {/* Öğretmen sekmesinde dönem bazlı ödeme (ayın 15'i) */}
        {sekme === "ogretmen" && <OgretmenDonemOdeme apiBase={API} />}

        {/* Veli Mesajları / Funnel */}
        {sekme === "funnel" && <FunnelPanel apiBase={API} />}

        {/* Muhasebe Ayarları — muhasebeci de vergi oranı + kur ücretlerini düzenler */}
        <MuhasebeAyarlari apiBase={API} />
      </main>
    </div>
  );
}
