import React, { useCallback, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import {
  Upload, FileSpreadsheet, CheckCircle2, AlertTriangle, PencilLine, Play,
  Download, Users, GraduationCap, UserCog, Wallet, ChevronRight,
} from "lucide-react";

/**
 * TopluKayit — kurumun Excel/CSV kayıt listesini sisteme aktaran yarı-otomatik akış.
 * yükle → eşleştirme ekranı (kuyruklar + öğretmen seçimi + elle düzeltme + varsayılan
 * ücret) → dry-run (deneme) → uygula → sonuç raporu + geçici şifre/hata xlsx indirme.
 * Backend: /toplu-kayit/*.  Props: apiBase.
 */
const KUYRUK_ETIKET = {
  temiz: { ad: "Temiz", renk: "bg-emerald-100 text-emerald-700", Ikon: CheckCircle2 },
  eslestirme: { ad: "Eşleştirme", renk: "bg-amber-100 text-amber-700", Ikon: PencilLine },
  elle: { ad: "Elle", renk: "bg-red-100 text-red-700", Ikon: AlertTriangle },
};

export default function TopluKayit({ apiBase }) {
  const { toast } = useToast();
  const [adim, setAdim] = useState("yukle");     // yukle | eslestir | sonuc
  const [taslakId, setTaslakId] = useState(null);
  const [taslak, setTaslak] = useState(null);
  const [ogretmenler, setOgretmenler] = useState([]);
  const [ucret, setUcret] = useState("");
  const [rapor, setRapor] = useState(null);
  const [mesgul, setMesgul] = useState(false);
  const [dosya, setDosya] = useState(null);

  const taslakYukle = useCallback(async (id) => {
    const r = await axios.get(`${apiBase}/toplu-kayit/taslak/${id}`);
    setTaslak(r.data);
    setOgretmenler(r.data.ogretmenler || []);
    setUcret(r.data.varsayilan_ucret ?? "");
  }, [apiBase]);

  const yukle = useCallback(async (f, sayfa) => {
    setMesgul(true);
    try {
      const fd = new FormData();
      fd.append("dosya", f);
      if (sayfa) fd.append("sayfa", sayfa);
      const r = await axios.post(`${apiBase}/toplu-kayit/yukle`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setTaslakId(r.data.taslak_id);
      await taslakYukle(r.data.taslak_id);
      setAdim("eslestir");
      toast({ title: "Dosya okundu", description: `${r.data.satir_sayisi} satır — temiz ${r.data.ozet.temiz}, eşleştirme ${r.data.ozet.eslestirme}, elle ${r.data.ozet.elle}` });
    } catch (err) {
      toast({ title: "Yüklenemedi", description: err?.response?.data?.detail || "", variant: "destructive" });
    } finally {
      setMesgul(false);
    }
  }, [apiBase, taslakYukle, toast]);

  const dosyaSec = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setDosya(f);
    yukle(f, null);
    e.target.value = "";
  };

  // Tek satır güncelle (öğretmen seçimi / elle düzeltme) → PUT
  const satirGuncelle = async (satir_no, degisiklik) => {
    try {
      await axios.put(`${apiBase}/toplu-kayit/taslak/${taslakId}`, { satir_guncelle: [{ satir_no, ...degisiklik }] });
      await taslakYukle(taslakId);
    } catch {
      toast({ title: "Satır güncellenemedi", variant: "destructive" });
    }
  };

  const ucretKaydet = async () => {
    try {
      await axios.put(`${apiBase}/toplu-kayit/taslak/${taslakId}`, { varsayilan_ucret: ucret === "" ? null : parseFloat(ucret) });
    } catch { /* sessiz */ }
  };

  const uygula = async (dryRun) => {
    setMesgul(true);
    try {
      const r = await axios.post(`${apiBase}/toplu-kayit/uygula/${taslakId}?dry_run=${dryRun}`);
      setRapor({ ...r.data.rapor, dry_run: dryRun, olusturulan: r.data.olusturulan_kullanici_sayisi });
      if (!dryRun) setAdim("sonuc");
      else toast({ title: "Deneme tamamlandı", description: "Hiçbir kayıt yazılmadı — planı inceleyin." });
    } catch (err) {
      toast({ title: "Uygulanamadı", description: err?.response?.data?.detail || "", variant: "destructive" });
    } finally {
      setMesgul(false);
    }
  };

  const raporIndir = async (tur) => {
    try {
      const r = await axios.get(`${apiBase}/toplu-kayit/rapor/${taslakId}/${tur}.xlsx`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `${tur}_${taslakId.slice(0, 8)}.xlsx`; a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast({ title: "İndirilemedi", variant: "destructive" });
    }
  };

  // ── Adım 1: Yükle ──
  if (adim === "yukle") {
    return (
      <div className="max-w-xl mx-auto text-center py-12">
        <div className="inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-primary/10 text-primary mb-4"><FileSpreadsheet className="h-7 w-7" /></div>
        <h3 className="text-lg font-bold text-content">Toplu Kayıt Aktarımı</h3>
        <p className="text-sm text-subtle mt-1 mb-6">Kurumun öğrenci-kur listesini (.xlsx / .csv) yükleyin. Her satır bir öğrenci-kur kaydıdır; öğrenci/veli/öğretmen kullanıcıları onayınızla oluşturulur.</p>
        <label className="inline-flex items-center gap-2 bg-primary hover:bg-primary-hover text-white px-5 py-2.5 rounded-xl cursor-pointer">
          <Upload className="h-4 w-4" />{mesgul ? "Okunuyor…" : "Dosya Seç"}
          <input type="file" accept=".xlsx,.csv" className="hidden" onChange={dosyaSec} disabled={mesgul} />
        </label>
      </div>
    );
  }

  // ── Adım 3: Sonuç ──
  if (adim === "sonuc" && rapor) {
    const kart = (Ikon, etiket, deger) => (
      <div className="bg-surface border border-line rounded-2xl p-4 text-center shadow-sm">
        <Ikon className="h-5 w-5 mx-auto text-primary mb-1" />
        <div className="text-2xl font-bold tabular-nums text-content">{deger}</div>
        <div className="text-xs text-subtle">{etiket}</div>
      </div>
    );
    return (
      <div className="max-w-3xl mx-auto space-y-5">
        <div className="flex items-center gap-2 text-emerald-600 font-semibold"><CheckCircle2 className="h-5 w-5" />Aktarım tamamlandı</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {kart(GraduationCap, "Öğrenci (yeni/eşleşen)", `${rapor.ogrenci_olusturuldu}/${rapor.ogrenci_eslesti}`)}
          {kart(Users, "Veli (yeni/eşleşen)", `${rapor.veli_olusturuldu}/${rapor.veli_eslesti}`)}
          {kart(UserCog, "Öğretmen (yeni/eşleşen)", `${rapor.ogretmen_olusturuldu}/${rapor.ogretmen_eslesti}`)}
          {kart(Wallet, "Kur alacağı", rapor.kur_alacak)}
        </div>
        <div className="text-sm text-subtle">{rapor.okundu} satır okundu · {rapor.elle_kuyrugu} satır elle tamamlanacak kuyruğunda · {(rapor.atlanan || []).length} satır atlandı.</div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => raporIndir("sifreler")} className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white text-sm px-4 py-2 rounded-xl"><Download className="h-4 w-4" />Kullanıcı + Şifre Listesi (xlsx)</button>
          <button onClick={() => raporIndir("hatalar")} className="inline-flex items-center gap-1.5 border border-line text-content text-sm px-4 py-2 rounded-xl hover:bg-app"><Download className="h-4 w-4" />Atlanan Satırlar (xlsx)</button>
          <button onClick={() => { setAdim("yukle"); setTaslak(null); setTaslakId(null); setRapor(null); }} className="inline-flex items-center gap-1.5 text-subtle text-sm px-4 py-2 rounded-xl hover:bg-app">Yeni Aktarım</button>
        </div>
      </div>
    );
  }

  // ── Adım 2: Eşleştirme ──
  const satirlar = taslak?.satirlar || [];
  const ozet = taslak?.ozet || {};
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm">
          {["temiz", "eslestirme", "elle"].map((k) => {
            const m = KUYRUK_ETIKET[k];
            return <span key={k} className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium ${m.renk}`}><m.Ikon className="h-3.5 w-3.5" />{m.ad}: {ozet[k] ?? 0}</span>;
          })}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {(taslak?.sayfalar?.length > 1) && (
            <>
              <label className="text-xs text-subtle">Sayfa</label>
              <select value={taslak.secili_sayfa || ""} disabled={mesgul}
                onChange={(e) => dosya && yukle(dosya, e.target.value)}
                className="border border-line rounded-lg px-2 py-1 text-sm max-w-[160px]">
                {taslak.sayfalar.map((sn) => <option key={sn} value={sn}>{sn.trim() || sn}</option>)}
              </select>
            </>
          )}
          <label className="text-xs text-subtle">Varsayılan kur ücreti (₺)</label>
          <input type="number" min="0" value={ucret} onChange={(e) => setUcret(e.target.value)} onBlur={ucretKaydet}
            className="w-28 border border-line rounded-lg px-2 py-1 text-sm tabular-nums" placeholder="örn. 2500" />
        </div>
      </div>

      <div className="border border-line rounded-2xl overflow-x-auto bg-surface shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-subtle border-b border-line bg-app">
              <th className="px-3 py-2">#</th><th className="px-3 py-2">Kuyruk</th>
              <th className="px-3 py-2">Öğrenci</th><th className="px-3 py-2">Sınıf</th><th className="px-3 py-2">Kur</th>
              <th className="px-3 py-2">Veli / Telefon</th><th className="px-3 py-2">Öğretmen</th>
              <th className="px-3 py-2">Ödeme / Not</th>
            </tr>
          </thead>
          <tbody>
            {satirlar.map((s) => {
              const n = s.norm; const m = KUYRUK_ETIKET[s.kuyruk] || KUYRUK_ETIKET.elle;
              const oneriIds = new Set((s.ogretmen_oneri?.oneriler || []).map((o) => o.id));
              return (
                <tr key={s.satir_no} className={`border-b border-line ${s.atla ? "opacity-40" : ""}`}>
                  <td className="px-3 py-2 tabular-nums text-subtle">{s.satir_no}</td>
                  <td className="px-3 py-2"><span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium ${m.renk}`}><m.Ikon className="h-3 w-3" />{m.ad}</span></td>
                  {/* Öğrenci — elle düzeltilebilir */}
                  <td className="px-3 py-2">
                    {n.ogrenci_gecerli ? (
                      <span className="text-content">{n.ogrenci_ad} {n.ogrenci_soyad}</span>
                    ) : (
                      <div className="flex gap-1">
                        <input defaultValue={n.ogrenci_ad} placeholder="Ad" className="w-20 border border-amber-300 rounded px-1.5 py-0.5 text-xs"
                          onBlur={(e) => { if (e.target.value.trim()) satirGuncelle(s.satir_no, { norm: { ogrenci_ad: e.target.value.trim(), ogrenci_soyad: n.ogrenci_soyad }, kuyruk: n.ogrenci_soyad ? "temiz" : s.kuyruk }); }} />
                        <input defaultValue={n.ogrenci_soyad} placeholder="Soyad" className="w-20 border border-amber-300 rounded px-1.5 py-0.5 text-xs"
                          onBlur={(e) => { if (e.target.value.trim()) satirGuncelle(s.satir_no, { norm: { ogrenci_ad: n.ogrenci_ad, ogrenci_soyad: e.target.value.trim() }, kuyruk: n.ogrenci_ad ? "temiz" : s.kuyruk }); }} />
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-subtle">{n.sinif ?? "—"}</td>
                  <td className="px-3 py-2 tabular-nums">{(n.kurlar || []).join(", ") || "—"}</td>
                  <td className="px-3 py-2">
                    <div className="text-content text-xs">{n.veli_ad} {n.veli_soyad}</div>
                    <div className={`text-[11px] tabular-nums ${n.veli_telefon_gecerli ? "text-subtle" : "text-red-500"}`}>{n.veli_telefon || "telefon yok"}</div>
                  </td>
                  {/* Öğretmen seçimi */}
                  <td className="px-3 py-2">
                    <select value={s.secili_ogretmen_id || (s.yeni_ogretmen_ad ? "yeni" : "")}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v === "yeni") satirGuncelle(s.satir_no, { secili_ogretmen_id: null, yeni_ogretmen_ad: s.ham?.ogretmen_ad || s.yeni_ogretmen_ad });
                        else satirGuncelle(s.satir_no, { secili_ogretmen_id: v || null, yeni_ogretmen_ad: "" });
                      }}
                      className="border border-line rounded-lg px-2 py-1 text-xs max-w-[160px]">
                      <option value="">— seçin —</option>
                      {s.yeni_ogretmen_ad && <option value="yeni">➕ Yeni: {s.yeni_ogretmen_ad}</option>}
                      {ogretmenler.map((o) => (
                        <option key={o.id} value={o.id}>{oneriIds.has(o.id) ? "★ " : ""}{o.ad}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {n.odeme_durumu && <span className="inline-block px-1.5 py-0.5 rounded bg-blue-50 text-primary mr-1">{n.odeme_durumu}</span>}
                    {n.egitim_notu && <span className="inline-block px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 mr-1" title="Eğitim notu (muhasebeye yazılmaz)">eğitim</span>}
                    {(n.aciklama || n.taksit_notu) && <span className="text-subtle">{n.aciklama || n.taksit_notu}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button onClick={() => uygula(true)} disabled={mesgul}
          className="inline-flex items-center gap-1.5 border border-line text-content text-sm px-4 py-2 rounded-xl hover:bg-app disabled:opacity-50">
          <Play className="h-4 w-4" />Deneme (dry-run)
        </button>
        <button onClick={() => uygula(false)} disabled={mesgul}
          className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white text-sm px-4 py-2 rounded-xl disabled:opacity-50">
          <ChevronRight className="h-4 w-4" />Uygula
        </button>
        {rapor?.dry_run && (
          <span className="text-xs text-subtle">Deneme planı: {rapor.ogrenci_olusturuldu} öğrenci, {rapor.veli_olusturuldu} veli, {rapor.ogretmen_olusturuldu} yeni öğretmen, {rapor.kur_alacak} kur alacağı · {rapor.elle_kuyrugu} elle kuyruğunda.</span>
        )}
      </div>
    </div>
  );
}
