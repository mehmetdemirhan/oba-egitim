import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import {
  ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, LineChart, Line,
} from "recharts";
import { Play, FileDown, RefreshCw, Send, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import BilgiIkonu from "../BilgiIkonu";
import { PersonaBalon, PersonaRozet, AydaAvatar } from "./Personalar";

const KAT_ETIKET = {
  ogretmen_gelisimi: "Öğretmen Gelişimi", tahsilat: "Tahsilat", urun_iyilestirme: "Ürün",
  ogrenci_memnuniyeti: "Öğrenci Memnuniyeti", buyume: "Büyüme",
};
const ONCELIK_RENK = { yuksek: "bg-red-100 text-red-700 border-red-200", orta: "bg-amber-100 text-amber-700 border-amber-200", dusuk: "bg-slate-100 text-slate-600 border-slate-200" };
const DURUM_ETIKET = { yeni: "Yeni", uygulaniyor: "Uygulanıyor", uygulandi: "Uygulandı", reddedildi: "Reddedildi" };

const fmt = (v) => (v === null || v === undefined ? "—" : (typeof v === "number" ? v.toLocaleString("tr-TR") : v));

// ── Yarım daire sağlık gauge (0-100) ──
function SaglikGauge({ skor }) {
  const s = Math.max(0, Math.min(100, Number(skor) || 0));
  const aci = (s / 100) * 180;
  const renk = s >= 75 ? "#16a34a" : s >= 50 ? "#f59e0b" : "#dc2626";
  const r = 70, cx = 90, cy = 90;
  const rad = (deg) => (deg - 180) * Math.PI / 180;
  const x2 = cx + r * Math.cos(rad(aci)), y2 = cy + r * Math.sin(rad(aci));
  const büyük = aci > 180 ? 1 : 0;
  return (
    <svg viewBox="0 0 180 110" className="w-full max-w-[240px]">
      <path d={`M20 90 A70 70 0 0 1 160 90`} fill="none" stroke="#e5e7eb" strokeWidth="14" strokeLinecap="round" />
      <path d={`M20 90 A70 70 0 ${büyük} 1 ${x2} ${y2}`} fill="none" stroke={renk} strokeWidth="14" strokeLinecap="round" />
      <text x="90" y="82" textAnchor="middle" fontSize="30" fontWeight="700" fill={renk}>{skor == null ? "—" : Math.round(s)}</text>
      <text x="90" y="102" textAnchor="middle" fontSize="11" fill="#64748b">/ 100 Sağlık</text>
    </svg>
  );
}

export default function AiCeo({ apiBase }) {
  const [saglik, setSaglik] = useState(null);
  const [analiz, setAnaliz] = useState(null);
  const [oneriler, setOneriler] = useState([]);
  const [anomaliler, setAnomaliler] = useState([]);
  const [karne, setKarne] = useState(null);
  const [hedefler, setHedefler] = useState([]);
  const [mektuplar, setMektuplar] = useState([]);
  const [odaklar, setOdaklar] = useState([]);
  const [rapor, setRapor] = useState(null);
  const [raporTip, setRaporTip] = useState("gunluk");
  const [katFiltre, setKatFiltre] = useState("hepsi");
  const [secili, setSecili] = useState(null);       // öneri detay
  const [calisiyor, setCalisiyor] = useState(false);
  const [genelSoru, setGenelSoru] = useState("");
  const [genelCevap, setGenelCevap] = useState(null);
  const [pazar, setPazar] = useState(null);
  const [pazarYukleniyor, setPazarYukleniyor] = useState(false);
  const [skor, setSkor] = useState(null);
  const [kuyrukVeri, setKuyrukVeri] = useState(null);
  const [planlar, setPlanlar] = useState([]);
  const [planForm, setPlanForm] = useState({ baslik: "", donem: "", h: [{ ad: "", metrik: "", mevcut: "", hedef: "" }, { ad: "", metrik: "", mevcut: "", hedef: "" }, { ad: "", metrik: "", mevcut: "", hedef: "" }] });
  const [planAcik, setPlanAcik] = useState(false);
  const [kurulFoto, setKurulFoto] = useState(null);
  const [kohort, setKohort] = useState([]);
  const [senForm, setSenForm] = useState({ kur_ucreti_degisim_yuzde: "", ogretmen_payi_degisim_yuzde: "", esneklik: "" });
  const [senSonuc, setSenSonuc] = useState(null);
  const [nps, setNps] = useState(null);
  const [fotoTarih, setFotoTarih] = useState(null);

  const api = (p) => `${apiBase}${p}`;

  const yukle = useCallback(async () => {
    try {
      const [s, a, k, an, h, m, o, sk, ku, pl] = await Promise.all([
        axios.get(api("/ai/ceo/saglik")).catch(() => null),
        axios.get(api("/ai/ceo/analiz/son")).catch(() => null),
        axios.get(api("/ai/ceo/karne")).catch(() => null),
        axios.get(api("/ai/ceo/anomali")).catch(() => null),
        axios.get(api("/ai/ceo/hedefler")).catch(() => null),
        axios.get(api("/ai/ceo/mektuplar")).catch(() => null),
        axios.get(api("/ai/ceo/miran/odaklar")).catch(() => null),
        axios.get(api("/ai/ceo/yonetim-skoru")).catch(() => null),
        axios.get(api("/ai/ceo/kuyruk")).catch(() => null),
        axios.get(api("/ai/ceo/planlar")).catch(() => null),
      ]);
      if (s) { setSaglik(s.data.saglik); setFotoTarih(s.data.fotograf_tarih); }
      if (a) { setAnaliz(a.data.analiz); setOneriler(a.data.oneriler || []); }
      if (k) setKarne(k.data.karne);
      if (an) setAnomaliler(an.data.anomaliler || []);
      if (h) setHedefler(h.data.hedefler || []);
      if (m) setMektuplar(m.data.mektuplar || []);
      if (o) setOdaklar(o.data.odaklar || []);
      if (sk) setSkor(sk.data.skor);
      if (ku) setKuyrukVeri(ku.data);
      if (pl) setPlanlar(pl.data.planlar || []);
      const [ff, kh, np] = await Promise.all([
        axios.get(api("/ai/ceo/fotograf/son")).catch(() => null),
        axios.get(api("/ai/ceo/kohort")).catch(() => null),
        axios.get(api("/ai/ceo/nps/ozet")).catch(() => null),
      ]);
      if (ff) setKurulFoto(ff.data.fotograf);
      if (kh) setKohort(kh.data.kohortlar || []);
      if (np) setNps(np.data);
    } catch (e) { /* sessiz */ }
  }, [apiBase]);

  useEffect(() => { yukle(); }, [yukle]);
  useEffect(() => {
    axios.get(api(`/ai/ceo/rapor/gunluk`)).then(r => setRapor(r.data.rapor)).catch(() => {});
  }, []); // günlük deterministik — açılışta AI yok

  const analizCalistir = async () => {
    setCalisiyor(true);
    try {
      await axios.post(api("/ai/ceo/fotograf/cek"));
      await axios.post(api("/ai/ceo/analiz/calistir"));
      await yukle();
    } catch (e) { /* */ } finally { setCalisiyor(false); }
  };

  const durumGuncelle = async (oneri, durum) => {
    const not = (durum === "reddedildi" || durum === "ertelendi") ? (window.prompt(durum === "ertelendi" ? "Erteleme notu (opsiyonel):" : "Red notu (opsiyonel):") || "") : "";
    await axios.put(api(`/ai/ceo/oneri/${oneri.id}/durum`), { durum, not });
    await yukle();
    setSecili(s => s && s.id === oneri.id ? { ...s, durum } : s);
  };

  const planOnayla = async (id) => { await axios.post(api(`/ai/ceo/plan/${id}/onayla`)); await yukle(); };
  const planKaydet = async () => {
    const hedefler = planForm.h.filter(x => x.ad.trim()).map(x => ({ ad: x.ad, metrik: x.metrik, mevcut: parseFloat(x.mevcut) || 0, hedef: parseFloat(x.hedef) || 0 }));
    if (hedefler.length < 3) { alert("En az 3 hedef girin."); return; }
    try { await axios.post(api("/ai/ceo/plan"), { baslik: planForm.baslik || "Üç Aylık Stratejik Plan", donem: planForm.donem, hedefler }); setPlanAcik(false); setPlanForm({ baslik: "", donem: "", h: [{ ad: "", metrik: "", mevcut: "", hedef: "" }, { ad: "", metrik: "", mevcut: "", hedef: "" }, { ad: "", metrik: "", mevcut: "", hedef: "" }] }); await yukle(); }
    catch (e) { alert("Plan kaydedilemedi (3-5 hedef gerekli)."); }
  };
  const briefingOku = async (raporId) => { try { await axios.post(api("/ai/ceo/yonetim/etkinlik"), { tur: "brifing_okundu", ref: raporId }); await yukle(); } catch (e) {} };

  const raporYukle = async (tip) => {
    setRaporTip(tip);
    if (tip === "gunluk") { const r = await axios.get(api("/ai/ceo/rapor/gunluk")); setRapor(r.data.rapor); }
    else if (tip === "haftalik") { const r = await axios.post(api("/ai/ceo/rapor/haftalik/calistir")); setRapor(r.data.rapor); }
    else { const r = await axios.post(api("/ai/ceo/rapor/aylik/olustur")); setRapor(r.data.rapor); }
  };

  const genelSor = async () => {
    if (!genelSoru.trim()) return;
    setGenelCevap({ bekliyor: true });
    try { const r = await axios.post(api("/ai/ceo/sor"), { soru: genelSoru }); setGenelCevap(r.data.mesaj || { hata: r.data.sebep }); }
    catch (e) { setGenelCevap({ hata: "Cevap alınamadı" }); }
  };

  const senaryoCalistir = async () => {
    const body = {};
    ["kur_ucreti_degisim_yuzde", "ogretmen_payi_degisim_yuzde", "esneklik"].forEach(k => { if (senForm[k] !== "") body[k] = parseFloat(senForm[k]); });
    try { const r = await axios.post(api("/ai/ceo/senaryo"), body); setSenSonuc(r.data.senaryo); } catch (e) {}
  };

  const pazarAra = async () => {
    setPazarYukleniyor(true);
    try { const r = await axios.post(api("/ai/ceo/pazar-arastirma"), {}); setPazar(r.data); }
    catch (e) { setPazar({ ok: false, durum: "hata", sebep: "İstek başarısız" }); }
    finally { setPazarYukleniyor(false); }
  };

  const radarVeri = Object.keys(KAT_ETIKET).map(k => ({
    kategori: KAT_ETIKET[k], sayi: oneriler.filter(o => o.kategori === k).length,
  }));
  const gorunenOneriler = katFiltre === "hepsi" ? oneriler : oneriler.filter(o => o.kategori === katFiltre);

  return (
    <div className="space-y-4">
      {/* ── Üst: Ayda + Sağlık + Analiz ── */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          <div className="flex-1"><PersonaBalon persona="ayda"
            mesaj={analiz?.ozet || "Sistemi 360° analiz etmeye hazırım. 'Analiz Çalıştır' ile başlayabilirsin."} /></div>
          <div className="flex flex-col items-center">
            <div className="flex items-center gap-1"><span className="text-xs text-subtle">Genel Sağlık</span><BilgiIkonu nasil="Tahsilat, yenileme, veli memnuniyeti, zamanında kur ve katılım bileşenlerinin ağırlıklı ortalaması (0-100)." ne="Kurumun genel gidişatını tek sayıda görüp nereye eğileceğini anlamak için." /></div>
            <SaglikGauge skor={saglik?.skor} />
            <div className="flex flex-wrap justify-center gap-1 mt-1">
              {(saglik?.bilesenler || []).map((b, i) => (
                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-app border border-line text-subtle">{b.ad}: {Math.round(b.puan)}</span>
              ))}
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-line">
          <span className="text-[11px] text-subtle">{fotoTarih ? `Son fotoğraf: ${new Date(fotoTarih).toLocaleString("tr-TR")}` : "Henüz fotoğraf yok"}</span>
          <button onClick={analizCalistir} disabled={calisiyor}
            className="inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-xl">
            {calisiyor ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {calisiyor ? "Analiz ediliyor…" : "Analiz Çalıştır"}
          </button>
        </div>
      </div>

      {/* ── Anomali kartları ── */}
      {anomaliler.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {anomaliler.map((a, i) => (
            <div key={i} className={`rounded-xl border p-3 ${a.seviye === "kritik" ? "border-red-300 bg-red-50" : "border-amber-300 bg-amber-50"}`}>
              <div className="flex items-center gap-1.5 text-xs font-bold mb-1"><AlertTriangle className={`h-4 w-4 ${a.seviye === "kritik" ? "text-red-600" : "text-amber-600"}`} />{a.seviye === "kritik" ? "Kritik" : "Dikkat"}</div>
              <div className="text-sm text-content">{a.mesaj}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Yönetim Skoru + Karar Bekleyenler (S3/S4) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-1">
            <h3 className="font-bold text-content text-sm">Yönetim Skoru</h3>
            <BilgiIkonu nasil="Önerilere karar vermek (ERTELE hariç), haftalık brifing/aylık rapor okumak, stratejik plan onaylamak deterministik puan kazandırır; öncelik ağırlıklıdır." ne="Yönetimin Ayda'nın önerilerini ne kadar takip ettiğini ölçmek için." />
          </div>
          {skor ? (
            <>
              <div className="text-3xl font-bold tabular-nums text-indigo-600">{skor.puan}</div>
              <div className="text-xs text-subtle">{skor.seviye} · 🔥 {skor.seri_hafta} hafta seri</div>
              <div className="mt-2">
                {skor.gozden_kacan_yok
                  ? <span className="text-xs px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-medium">🏅 Gözden Kaçan Yok</span>
                  : <span className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-500">Bekleyen işler var</span>}
              </div>
            </>
          ) : <div className="text-sm text-subtle">—</div>}
        </div>
        <div className="lg:col-span-2 rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-bold text-content text-sm">Karar Bekleyenler {kuyrukVeri ? `(${kuyrukVeri.bekleyen_sayi})` : ""}</h3>
            {kuyrukVeri?.gozden_kacan_sayi > 0 && <span className="text-xs text-red-600 font-medium">⚠ {kuyrukVeri.gozden_kacan_sayi} gözden kaçıyor olabilir</span>}
          </div>
          {(kuyrukVeri?.kuyruk || []).length === 0 ? <div className="text-sm text-subtle py-3">Kuyruk boş — tüm kararlar verildi 🎉</div> : (
            <div className="space-y-2 max-h-80 overflow-auto">
              {kuyrukVeri.kuyruk.map(o => (
                <div key={o.id} className={`rounded-lg border p-2 ${o.gozden_kaciyor ? "border-red-300 bg-red-50" : "border-line"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-content">{o.baslik}</span>
                    <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded border ${ONCELIK_RENK[o.oncelik] || ""}`}>{o.oncelik}</span>
                  </div>
                  <div className="text-xs text-subtle mt-0.5">{o.ozet}</div>
                  <div className="flex items-center gap-3 mt-1.5">
                    <button onClick={() => durumGuncelle(o, "uygulaniyor")} className="text-[11px] font-medium text-emerald-700 hover:underline">Uygulanacak</button>
                    <button onClick={() => durumGuncelle(o, "reddedildi")} className="text-[11px] font-medium text-red-600 hover:underline">Reddet</button>
                    <button onClick={() => durumGuncelle(o, "ertelendi")} className="text-[11px] font-medium text-slate-500 hover:underline">Ertele</button>
                    <button onClick={() => setSecili(o)} className="text-[11px] text-indigo-600 hover:underline ml-auto">Detay</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* ── Kategori radar ── */}
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-1"><h3 className="font-bold text-content text-sm">Öneri Kategorileri</h3><BilgiIkonu nasil="Ayda'nın son analizindeki önerilerin kategoriye göre sayısı." ne="Hangi alanda daha çok iyileştirme fırsatı olduğunu görmek için." /></div>
          <div className="h-56"><ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarVeri}><PolarGrid /><PolarAngleAxis dataKey="kategori" tick={{ fontSize: 10 }} />
              <Radar dataKey="sayi" stroke="#2563eb" fill="#2563eb" fillOpacity={0.4} /></RadarChart>
          </ResponsiveContainer></div>
        </div>

        {/* ── Rapor sekmeleri ── */}
        <div className="lg:col-span-2 rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <div className="inline-flex rounded-lg border border-line overflow-hidden text-sm">
              {[["gunluk", "Bugün"], ["haftalik", "Hafta"], ["aylik", "Ay"]].map(([t, l]) => (
                <button key={t} onClick={() => raporYukle(t)} className={`px-3 py-1.5 ${raporTip === t ? "bg-indigo-600 text-white" : "hover:bg-app"}`}>{l}</button>
              ))}
            </div>
            {rapor?.id && (raporTip === "aylik") && (
              <a href={api(`/ai/ceo/rapor/${rapor.id}/pdf`)} className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:underline"><FileDown className="h-3.5 w-3.5" />PDF</a>
            )}
          </div>
          {rapor ? (
            <div className="text-sm space-y-2">
              {rapor.yorum && <div className="text-content">{rapor.yorum}</div>}
              {rapor.ozet && <div className="text-content">{rapor.ozet}</div>}
              {rapor.gostergeler && (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {Object.entries(rapor.gostergeler).map(([k, v]) => (
                    <div key={k} className="rounded-lg bg-app border border-line p-2">
                      <div className="text-[10px] text-subtle">{k}</div><div className="font-bold tabular-nums">{fmt(v)}</div>
                    </div>
                  ))}
                </div>
              )}
              {(rapor.oncelikli_oneriler || []).map((o, i) => (
                <div key={i} className="rounded-lg border border-line p-2"><span className="font-medium">{o.baslik}</span> <span className="text-subtle">— {o.ozet}</span></div>
              ))}
            </div>
          ) : <div className="text-sm text-subtle py-6 text-center">Rapor yükleniyor…</div>}
        </div>
      </div>

      {/* ── Öneri kartları ── */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h3 className="font-bold text-content flex items-center gap-2"><AydaAvatar size={22} ring={false} />Ayda'nın Önerileri</h3>
          <div className="flex gap-1 flex-wrap">
            {["hepsi", ...Object.keys(KAT_ETIKET)].map(k => (
              <button key={k} onClick={() => setKatFiltre(k)} className={`text-xs px-2 py-1 rounded-lg border ${katFiltre === k ? "bg-indigo-600 text-white border-indigo-600" : "border-line text-subtle hover:bg-app"}`}>{k === "hepsi" ? "Hepsi" : KAT_ETIKET[k]}</button>
            ))}
          </div>
        </div>
        {gorunenOneriler.length === 0 ? (
          <div className="text-sm text-subtle text-center py-6">Henüz öneri yok — "Analiz Çalıştır" ile üret.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {gorunenOneriler.map(o => (
              <button key={o.id} onClick={() => setSecili(o)} className="text-left rounded-xl border border-line p-3 hover:ring-2 hover:ring-indigo-200 transition">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-semibold text-content text-sm">{o.baslik}</span>
                  <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded border ${ONCELIK_RENK[o.oncelik] || ""}`}>{o.oncelik}</span>
                </div>
                <div className="text-xs text-subtle mt-1 line-clamp-2">{o.ozet}</div>
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-app border border-line text-subtle">{KAT_ETIKET[o.kategori] || o.kategori}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">{DURUM_ETIKET[o.durum] || o.durum}</span>
                  {o.vizyon_onerisi && <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-100 text-violet-700">🔭 vizyon önerisi</span>}
                  {o.zayif_dayanak && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">⚠ zayıf dayanak</span>}
                  {o.plan_hedef && <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">🎯 {o.plan_hedef}</span>}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Karne + Hedefler ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-1"><h3 className="font-bold text-content text-sm">Ayda'nın Karnesi</h3><BilgiIkonu nasil="Kabul oranı, isabet (uygulanan önerinin 30+ gün sonra ölçülen etkisi), zayıf dayanak oranı ve Miran koç geri bildirimleri — tümü deterministik." ne="AI danışmanın gerçekten işe yarayıp yaramadığını sayıyla görmek için." /></div>
          {karne ? (
            <>
              <div className="text-sm text-content mb-2">{karne.ozet}</div>
              <div className="grid grid-cols-3 gap-2 text-center">
                {[["Kabul", karne.kabul_orani], ["İsabet", karne.isabet?.isabet_orani], ["Zayıf Dayanak", karne.zayif_dayanak_orani]].map(([l, v], i) => (
                  <div key={i} className="rounded-lg bg-app border border-line p-2"><div className="text-lg font-bold tabular-nums">{v == null ? "—" : `%${v}`}</div><div className="text-[10px] text-subtle">{l}</div></div>
                ))}
              </div>
              {(karne.aylik_trend || []).length > 0 && (
                <div className="h-40 mt-3"><ResponsiveContainer width="100%" height="100%">
                  <LineChart data={karne.aylik_trend}><CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="ay" tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} /><Tooltip />
                    <Line dataKey="oneri" name="Öneri" stroke="#2563eb" /><Line dataKey="kabul" name="Kabul" stroke="#16a34a" /></LineChart>
                </ResponsiveContainer></div>
              )}
            </>
          ) : <div className="text-sm text-subtle py-4">Karne verisi yok.</div>}
        </div>

        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2"><h3 className="font-bold text-content text-sm">Hedefler</h3><BilgiIkonu k={undefined} nasil="Koyduğun hedefin güncel fotoğraftaki değere oranı." ne="Hedefe ne kadar yaklaştığını ve sapmayı görmek için." /></div>
          {hedefler.length === 0 ? <div className="text-sm text-subtle">Henüz hedef yok.</div> : (
            <div className="space-y-2">
              {hedefler.map(h => (
                <div key={h.id} className="rounded-lg border border-line p-2">
                  <div className="flex justify-between text-sm"><span className="font-medium">{h.ad}</span><span className="tabular-nums text-subtle">{fmt(h.gauge?.guncel)} / {fmt(h.gauge?.hedef)}</span></div>
                  <div className="h-2 bg-app rounded-full mt-1 overflow-hidden"><div className={`h-full rounded-full ${h.gauge?.durum === "ulasildi" ? "bg-emerald-500" : h.gauge?.durum === "yolda" ? "bg-amber-500" : "bg-red-400"}`} style={{ width: `${h.gauge?.ilerleme_yuzde || 0}%` }} /></div>
                </div>
              ))}
            </div>
          )}
          {odaklar.length > 0 && (
            <div className="mt-3 pt-3 border-t border-line">
              <div className="flex items-center gap-1 text-xs font-semibold text-content mb-1"><PersonaRozet persona="miran" /> bu hafta ilettiği odaklar</div>
              <div className="flex flex-wrap gap-1">{odaklar.slice(0, 8).map((o, i) => <span key={i} className="text-[11px] px-1.5 py-0.5 rounded bg-amber-50 border border-amber-200 text-amber-700">{o.ad}: {o.odak_etiket}</span>)}</div>
            </div>
          )}
        </div>
      </div>

      {/* ── Performans mektupları ── */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-bold text-content text-sm">Öğretmen Performans Mektupları</h3>
          <button onClick={async () => { await axios.post(api("/ai/ceo/mektup/toplu")); await yukle(); }} className="text-xs bg-app border border-line rounded-lg px-2 py-1 hover:bg-surface">Tüm öğretmenlere taslak hazırla</button>
        </div>
        {mektuplar.length === 0 ? <div className="text-sm text-subtle">Henüz mektup yok.</div> : (
          <div className="space-y-2 max-h-72 overflow-auto">
            {mektuplar.map(m => (
              <div key={m.id} className="rounded-lg border border-line p-2 text-sm">
                <div className="flex justify-between items-center">
                  <span className="font-medium">{m.ogretmen_ad}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${m.onayli ? "bg-emerald-100 text-emerald-700" : m.durum === "reddedildi" ? "bg-red-100 text-red-600" : "bg-amber-100 text-amber-700"}`}>{m.onayli ? "Onaylı" : m.durum === "reddedildi" ? "Reddedildi" : "Taslak"}</span>
                </div>
                <div className="text-xs text-subtle mt-1">{m.icerik?.guclu_yonler}</div>
                {!m.onayli && m.durum !== "reddedildi" && (
                  <div className="flex gap-2 mt-1">
                    <button onClick={async () => { await axios.post(api(`/ai/ceo/mektup/${m.id}/onayla`)); await yukle(); }} className="inline-flex items-center gap-1 text-[11px] text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />Onayla & Gönder</button>
                    <button onClick={async () => { await axios.post(api(`/ai/ceo/mektup/${m.id}/reddet`), {}); await yukle(); }} className="inline-flex items-center gap-1 text-[11px] text-red-600"><XCircle className="h-3.5 w-3.5" />Reddet</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Ayda'ya Sor (genel) ── */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <h3 className="font-bold text-content text-sm mb-2 flex items-center gap-2"><AydaAvatar size={22} ring={false} />Ayda'ya Sor</h3>
        <div className="flex gap-2">
          <input value={genelSoru} onChange={e => setGenelSoru(e.target.value)} onKeyDown={e => e.key === "Enter" && genelSor()}
            placeholder="Örn: bu ayki tahsilat düşüşünün sebebi ne olabilir?" className="flex-1 px-3 py-2 rounded-xl border border-line text-sm outline-none focus:border-indigo-400" />
          <button onClick={genelSor} className="bg-indigo-600 text-white px-3 rounded-xl"><Send className="h-4 w-4" /></button>
        </div>
        {genelCevap && (
          <div className="mt-2 text-sm rounded-xl bg-app border border-line p-3">
            {genelCevap.bekliyor ? "Ayda düşünüyor…" : genelCevap.hata ? <span className="text-red-600">{genelCevap.hata}</span> : (
              <><div className="text-content whitespace-pre-wrap">{genelCevap.cevap}</div>{genelCevap.zayif_dayanak && <div className="text-[11px] text-amber-600 mt-1">⚠ Bu cevaptaki bazı sayılar fotoğrafta doğrulanamadı.</div>}</>
            )}
          </div>
        )}
      </div>

      {/* ── Kurul Özeti PDF + NPS (S6d/S6f) ── */}
      <div className="rounded-2xl border border-line bg-surface p-3 shadow-sm flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-4">
          <h3 className="font-bold text-content text-sm">Kurul Paketi</h3>
          {nps?.nps && (
            <span className="text-sm flex items-center gap-1">NPS: <b className={`tabular-nums ${nps.nps.nps < 0 ? "text-red-600" : nps.nps.nps >= 30 ? "text-emerald-600" : "text-amber-600"}`}>{nps.nps.nps ?? "—"}</b>
              <span className="text-xs text-subtle">({nps.nps.sayi} yanıt)</span>
              <BilgiIkonu nasil="NPS = %promoter (9-10) − %detractor (0-6). Sağlık skorunun bir bileşeni; negatifse anomali üretir." ne="Müşteri memnuniyetinin genel eğilimini görmek için." />
            </span>
          )}
        </div>
        <a href={api("/ai/ceo/kurul-paketi/pdf")} className="inline-flex items-center gap-1 text-sm text-indigo-600 hover:underline"><FileDown className="h-4 w-4" />Kurul Özeti PDF</a>
      </div>

      {/* ── Kurul Analitiği (S6) ── */}
      {(kurulFoto?.konsantrasyon || kurulFoto?.birim_ekonomi) && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
            <div className="flex items-center justify-between mb-1"><h3 className="font-bold text-content text-sm">Konsantrasyon Riski</h3><BilgiIkonu nasil="En büyük öğretmenin öğrenci/gelir payı, ilk 3 toplamı ve tek eğitim türü bağımlılığı; eşik %25." ne="Tek noktaya bağımlılık riskini görüp dağılımı çeşitlendirmek için." /></div>
            {kurulFoto.konsantrasyon && (
              <div className="space-y-1 text-sm">
                {[["En büyük öğretmen (öğrenci)", kurulFoto.konsantrasyon.en_buyuk_ogretmen_ogrenci_payi], ["İlk 3 öğretmen", kurulFoto.konsantrasyon.ilk3_ogretmen_ogrenci_payi], ["En büyük öğretmen (gelir)", kurulFoto.konsantrasyon.en_buyuk_ogretmen_gelir_payi], ["En büyük eğitim türü", kurulFoto.konsantrasyon.en_buyuk_tur_payi]].map(([l, v], i) => (
                  <div key={i} className="flex justify-between"><span className="text-subtle">{l}</span><span className={`tabular-nums font-medium ${v > (kurulFoto.konsantrasyon.esik_yuzde || 25) ? "text-red-600" : "text-content"}`}>%{v}</span></div>
                ))}
              </div>
            )}
          </div>
          <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
            <div className="flex items-center justify-between mb-1"><h3 className="font-bold text-content text-sm">Birim Ekonomi</h3><BilgiIkonu nasil="Net = brüt tahsilat − vergi − öğretmen payı. LTV = net / aktif öğrenci; kur başı marj = net / kur sayısı." ne="Öğrenci/kur başına gerçek kârlılığı görmek için." /></div>
            {kurulFoto.birim_ekonomi && (
              <div className="space-y-1 text-sm">
                <div className="flex justify-between"><span className="text-subtle">LTV (öğrenci/net)</span><span className="tabular-nums font-bold text-emerald-600">{fmt(kurulFoto.birim_ekonomi.ltv_ogrenci_basi_net)}₺</span></div>
                <div className="flex justify-between"><span className="text-subtle">Kur başı net marj</span><span className="tabular-nums font-medium">{fmt(kurulFoto.birim_ekonomi.kur_basi_net_marj)}₺</span></div>
                <div className="flex justify-between"><span className="text-subtle">Toplam net</span><span className="tabular-nums font-medium">{fmt(kurulFoto.birim_ekonomi.toplam_net)}₺</span></div>
              </div>
            )}
          </div>
          <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
            <div className="flex items-center justify-between mb-1"><h3 className="font-bold text-content text-sm">Kohort Yenileme</h3><BilgiIkonu nasil="Kayıt ayına göre öğrenci kohortlarının bir üst kura geçme (yenileme) oranı." ne="Hangi dönem kayıtlarının daha iyi yenilediğini görmek için." /></div>
            {kohort.length === 0 ? <div className="text-sm text-subtle">Veri yok.</div> : (
              <div className="h-36"><ResponsiveContainer width="100%" height="100%"><LineChart data={kohort}><CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="ay" tick={{ fontSize: 9 }} /><YAxis domain={[0, 100]} tick={{ fontSize: 9 }} /><Tooltip formatter={(v) => [`%${v}`, "Yenileme"]} /><Line dataKey="yenileme_orani" stroke="#2563eb" /></LineChart></ResponsiveContainer></div>
            )}
          </div>
        </div>
      )}

      {/* ── Senaryo Simülasyonu (S6e) ── */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2"><h3 className="font-bold text-content text-sm">Senaryo Simülasyonu</h3><BilgiIkonu nasil="Kur ücreti / öğretmen payı / vergi değişiminin gelir-marja deterministik etkisi. Esneklik girilirse hacim etkisi varsayım olarak eklenir (açıkça etiketli)." ne="Fiyat/pay/vergi kararlarının kâra etkisini uygulamadan önce görmek için." /></div>
        <div className="flex flex-wrap gap-2 items-end">
          {[["kur_ucreti_degisim_yuzde", "Kur ücreti %"], ["ogretmen_payi_degisim_yuzde", "Öğretmen payı %"], ["esneklik", "Esneklik (ops.)"]].map(([k, l]) => (
            <div key={k}><label className="text-[10px] text-subtle block">{l}</label><input value={senForm[k]} onChange={e => setSenForm({ ...senForm, [k]: e.target.value })} className="w-28 px-2 py-1 rounded border border-line text-sm" placeholder="0" /></div>
          ))}
          <button onClick={senaryoCalistir} className="bg-indigo-600 text-white text-sm rounded-lg px-3 py-1.5">Hesapla</button>
        </div>
        {senSonuc && (
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="rounded-lg border border-line p-2"><div className="text-xs text-subtle mb-1">Mevcut</div><div className="text-sm tabular-nums">Net: <b>{fmt(senSonuc.mevcut.net)}₺</b></div></div>
            <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-2"><div className="text-xs text-subtle mb-1">Senaryo</div><div className="text-sm tabular-nums">Net: <b>{fmt(senSonuc.senaryo.net)}₺</b> <span className={senSonuc.net_delta >= 0 ? "text-emerald-600" : "text-red-600"}>({senSonuc.net_delta >= 0 ? "+" : ""}{fmt(senSonuc.net_delta)}₺)</span></div></div>
            <div className="sm:col-span-2 text-[11px] text-amber-600">⚠ {senSonuc.varsayim}</div>
          </div>
        )}
      </div>

      {/* ── Stratejik Plan (S5) ── */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-bold text-content text-sm flex items-center gap-2">Üç Aylık Stratejik Plan
            <BilgiIkonu nasil="3-5 ölçülebilir hedef; onaylı plan sonraki Ayda analizlerinde referans olur (öneriler hangi hedefe hizmet ettiğini belirtir)." ne="Kurumun yönünü net hedeflere bağlamak ve önerileri bu hedeflere hizalamak için." />
          </h3>
          <button onClick={() => setPlanAcik(v => !v)} className="text-xs bg-app border border-line rounded-lg px-2 py-1 hover:bg-surface">{planAcik ? "Kapat" : "Yeni Plan"}</button>
        </div>
        {planAcik && (
          <div className="mb-3 rounded-lg border border-line p-3 space-y-2">
            <div className="flex gap-2">
              <input value={planForm.baslik} onChange={e => setPlanForm({ ...planForm, baslik: e.target.value })} placeholder="Plan başlığı" className="flex-1 px-2 py-1 rounded border border-line text-sm" />
              <input value={planForm.donem} onChange={e => setPlanForm({ ...planForm, donem: e.target.value })} placeholder="Dönem (2026-Q3)" className="w-40 px-2 py-1 rounded border border-line text-sm" />
            </div>
            {planForm.h.map((hd, i) => (
              <div key={i} className="grid grid-cols-4 gap-1.5">
                <input value={hd.ad} onChange={e => { const h = [...planForm.h]; h[i] = { ...h[i], ad: e.target.value }; setPlanForm({ ...planForm, h }); }} placeholder={`Hedef ${i + 1}`} className="px-2 py-1 rounded border border-line text-xs" />
                <input value={hd.metrik} onChange={e => { const h = [...planForm.h]; h[i] = { ...h[i], metrik: e.target.value }; setPlanForm({ ...planForm, h }); }} placeholder="metrik (%)" className="px-2 py-1 rounded border border-line text-xs" />
                <input value={hd.mevcut} onChange={e => { const h = [...planForm.h]; h[i] = { ...h[i], mevcut: e.target.value }; setPlanForm({ ...planForm, h }); }} placeholder="mevcut" className="px-2 py-1 rounded border border-line text-xs" />
                <input value={hd.hedef} onChange={e => { const h = [...planForm.h]; h[i] = { ...h[i], hedef: e.target.value }; setPlanForm({ ...planForm, h }); }} placeholder="hedef" className="px-2 py-1 rounded border border-line text-xs" />
              </div>
            ))}
            <div className="flex justify-end gap-2">
              <button onClick={() => setPlanForm({ ...planForm, h: [...planForm.h, { ad: "", metrik: "", mevcut: "", hedef: "" }].slice(0, 5) })} className="text-xs text-indigo-600">+ Hedef</button>
              <button onClick={planKaydet} className="text-xs bg-indigo-600 text-white rounded-lg px-3 py-1">Kaydet (taslak)</button>
            </div>
          </div>
        )}
        {planlar.length === 0 ? <div className="text-sm text-subtle">Henüz plan yok.</div> : (
          <div className="space-y-2">
            {planlar.map(p => (
              <div key={p.id} className="rounded-lg border border-line p-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{p.baslik} <span className="text-xs text-subtle">{p.donem}</span></span>
                  {p.durum === "onayli" ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">Onaylı</span>
                    : <button onClick={() => planOnayla(p.id)} className="text-[11px] text-emerald-700 font-medium">Onayla</button>}
                </div>
                <div className="flex flex-wrap gap-1 mt-1">{(p.hedefler || []).map((h, i) => (
                  <span key={i} className="text-[11px] px-1.5 py-0.5 rounded bg-app border border-line text-subtle">{h.ad}: {h.mevcut}→{h.hedef} {h.metrik}</span>
                ))}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Pazar Araştırması (opsiyonel, grounding) ── */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-bold text-content text-sm flex items-center gap-2"><AydaAvatar size={22} ring={false} />Pazar Araştırması</h3>
          <button onClick={pazarAra} disabled={pazarYukleniyor} className="text-xs bg-indigo-600 disabled:opacity-60 text-white rounded-lg px-3 py-1.5">
            {pazarYukleniyor ? "Araştırılıyor…" : "Web'de Araştır"}
          </button>
        </div>
        <div className="text-[11px] text-subtle mb-2">Web araması (grounding) kullanır — seyrek/elle tetikleyin (maliyetli).</div>
        {pazar && (pazar.ok ? (
          <div className="text-sm space-y-2">
            <div className="text-content whitespace-pre-wrap">{pazar.arastirma?.ozet}</div>
            {(pazar.arastirma?.kaynaklar || []).length > 0 && (
              <div><div className="text-xs font-semibold text-content mb-1">Kaynaklar</div>
                <ul className="space-y-0.5">{pazar.arastirma.kaynaklar.map((k, i) => (
                  <li key={i}><a href={k.url} target="_blank" rel="noreferrer" className="text-xs text-indigo-600 hover:underline break-all">🔗 {k.baslik}</a></li>
                ))}</ul></div>
            )}
          </div>
        ) : (
          <div className="text-sm rounded-lg bg-amber-50 border border-amber-200 text-amber-700 p-3">
            {pazar.durum === "yapilandirilmadi" ? "Grounding yapılandırılmadı / kullanılamıyor — uydurma analiz üretilmedi." : "Araştırma yapılamadı."}
            {pazar.sebep && <div className="text-[11px] mt-1 opacity-80">{pazar.sebep}</div>}
          </div>
        ))}
      </div>

      {/* ── Öneri detay modalı ── */}
      {secili && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setSecili(null)}>
          <div className="bg-surface rounded-2xl max-w-lg w-full max-h-[85vh] overflow-auto p-5" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-bold text-content">{secili.baslik}</h3>
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${ONCELIK_RENK[secili.oncelik]}`}>{secili.oncelik}</span>
            </div>
            <div className="text-sm text-content mt-2">{secili.ozet}</div>
            {secili.beklenen_etki && <div className="text-xs text-subtle mt-1">Beklenen etki: {secili.beklenen_etki}</div>}
            <div className="mt-3">
              <div className="text-xs font-semibold text-content mb-1">Dayanaklar</div>
              {(secili.dayanaklar || []).map((d, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-0.5">
                  <span>{d.metrik}: <b className="tabular-nums">{fmt(d.deger)}</b></span>
                  <span className={d.dogrulandi ? "text-emerald-600" : "text-amber-600"}>{d.dogrulandi ? "✓ doğrulandı" : "⚠ zayıf"}</span>
                </div>
              ))}
            </div>
            <div className="flex gap-2 mt-4 flex-wrap">
              {["uygulaniyor", "uygulandi", "reddedildi"].map(d => (
                <button key={d} onClick={() => durumGuncelle(secili, d)} className="text-xs px-3 py-1.5 rounded-lg border border-line hover:bg-app">{DURUM_ETIKET[d]}</button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
