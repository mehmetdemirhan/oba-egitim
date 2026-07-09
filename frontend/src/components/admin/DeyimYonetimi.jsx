import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { Sparkles, Plus, Trash2, BookMarked, Quote, Music } from "lucide-react";

/**
 * DeyimYonetimi — yönetici/koordinatör: Deyim, Atasözü ve Tekerleme havuzu yönetimi.
 * MEB Kelimeleri sekmesi altında bir alt bölüm olarak kullanılır. Manuel + toplu
 * giriş, AI ile anlam doldurma, filtreli liste. Bu havuz egzersiz motorunda
 * deyim/atasözü/tekerleme egzersizlerine kaynak olur.
 *
 * Props: apiBase — `${BACKEND_URL}/api`
 */
const TUR_META = {
  deyim: { ad: "Deyim", Ikon: BookMarked, anlam: true },
  atasozu: { ad: "Atasözü", Ikon: Quote, anlam: true },
  tekerleme: { ad: "Tekerleme", Ikon: Music, anlam: false },
};

export default function DeyimYonetimi({ apiBase }) {
  const { toast } = useToast();
  const [aktifTur, setAktifTur] = useState("deyim");
  const [istatistik, setIstatistik] = useState({});
  const [liste, setListe] = useState([]);
  const [toplam, setToplam] = useState(0);
  const [sayfa, setSayfa] = useState(1);
  const [sayfaSayisi, setSayfaSayisi] = useState(1);
  const [ara, setAra] = useState("");
  const [yukleniyor, setYukleniyor] = useState(false);

  const [form, setForm] = useState({ icerik: "", anlam: "", ornek_cumle: "", sinif_seviyesi: 3 });
  const [toplu, setToplu] = useState("");

  const anlamGerekli = TUR_META[aktifTur]?.anlam;

  const istatistikCek = useCallback(async () => {
    try {
      const r = await axios.get(`${apiBase}/deyim/istatistik`);
      setIstatistik(r.data?.tur_bazli || {});
    } catch { /* sessiz */ }
  }, [apiBase]);

  const listeCek = useCallback(async () => {
    setYukleniyor(true);
    try {
      const r = await axios.get(`${apiBase}/deyim/liste`, { params: { tur: aktifTur, ara: ara || undefined, sayfa, limit: 50 } });
      setListe(r.data?.ogeler || []);
      setToplam(r.data?.toplam || 0);
      setSayfaSayisi(r.data?.sayfa_sayisi || 1);
    } catch {
      toast({ title: "Liste yüklenemedi", variant: "destructive" });
    } finally {
      setYukleniyor(false);
    }
  }, [apiBase, aktifTur, ara, sayfa, toast]);

  useEffect(() => { istatistikCek(); }, [istatistikCek]);
  useEffect(() => { listeCek(); }, [listeCek]);

  const tekilEkle = async () => {
    if (form.icerik.trim().length < 2) { toast({ title: "İçerik çok kısa", variant: "destructive" }); return; }
    try {
      await axios.post(`${apiBase}/deyim/ekle`, { tur: aktifTur, ...form });
      setForm({ icerik: "", anlam: "", ornek_cumle: "", sinif_seviyesi: form.sinif_seviyesi });
      toast({ title: "Eklendi" });
      await Promise.all([listeCek(), istatistikCek()]);
    } catch {
      toast({ title: "Eklenemedi", variant: "destructive" });
    }
  };

  const topluEkle = async () => {
    const satirlar = toplu.split("\n").map((s) => s.trim()).filter((s) => s.length >= 2);
    if (!satirlar.length) { toast({ title: "Satır yok", variant: "destructive" }); return; }
    const ogeler = satirlar.map((s) => {
      const [icerik, anlam] = s.split("|").map((x) => (x || "").trim());
      return { tur: aktifTur, icerik, anlam: anlam || "", sinif_seviyesi: form.sinif_seviyesi };
    });
    try {
      const r = await axios.post(`${apiBase}/deyim/ekle`, { ogeler });
      setToplu("");
      toast({ title: `${r.data?.yeni_eklenen ?? 0} eklendi`, description: `${r.data?.mevcut_atlanan ?? 0} atlandı` });
      await Promise.all([listeCek(), istatistikCek()]);
    } catch {
      toast({ title: "Toplu ekleme başarısız", variant: "destructive" });
    }
  };

  const sil = async (id) => {
    try {
      await axios.delete(`${apiBase}/deyim/${id}`);
      await Promise.all([listeCek(), istatistikCek()]);
    } catch {
      toast({ title: "Silinemedi", variant: "destructive" });
    }
  };

  const aiAnlam = async () => {
    try {
      const r = await axios.post(`${apiBase}/deyim/ai-anlam`, {});
      toast({ title: `${r.data?.kuyrukta ?? 0} öğe AI kuyruğuna alındı`, description: "Anlamlar arka planda doldurulacak." });
    } catch {
      toast({ title: "AI tetiklenemedi", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-4">
      {/* Tür seçici */}
      <div className="grid grid-cols-3 gap-3">
        {Object.entries(TUR_META).map(([id, m]) => {
          const st = istatistik[id] || {};
          const aktif = aktifTur === id;
          return (
            <button key={id} onClick={() => { setAktifTur(id); setSayfa(1); }}
              className={`p-3 rounded-2xl border text-left transition-all ${aktif ? "border-primary bg-blue-50" : "border-line bg-surface hover:bg-app"}`}>
              <div className="inline-flex items-center gap-1.5 font-semibold text-content"><m.Ikon className="h-4 w-4" />{m.ad}</div>
              <div className="text-xs text-subtle mt-0.5 tabular-nums">{st.toplam ?? 0} öğe{m.anlam ? ` · ${st.anlam_bekleyen ?? 0} anlam bekliyor` : ""}</div>
            </button>
          );
        })}
      </div>

      {/* Ekleme kartı */}
      <div className="bg-surface border border-line rounded-2xl p-4 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="font-semibold text-content">Yeni {TUR_META[aktifTur].ad} Ekle</h4>
          <div className="flex items-center gap-2">
            <label className="text-xs text-subtle">Sınıf</label>
            <select value={form.sinif_seviyesi} onChange={(e) => setForm({ ...form, sinif_seviyesi: parseInt(e.target.value) })}
              className="border border-line rounded-lg px-2 py-1 text-sm bg-surface">
              {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <input value={form.icerik} onChange={(e) => setForm({ ...form, icerik: e.target.value })}
            placeholder={aktifTur === "tekerleme" ? "Tekerleme metni" : `${TUR_META[aktifTur].ad} metni`}
            className="border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
          {anlamGerekli && (
            <input value={form.anlam} onChange={(e) => setForm({ ...form, anlam: e.target.value })}
              placeholder="Anlam (boş bırakılırsa AI doldurur)"
              className="border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
          )}
        </div>
        <button onClick={tekilEkle} className="inline-flex items-center gap-1 bg-primary hover:bg-primary-hover text-white text-sm px-4 py-2 rounded-xl">
          <Plus className="h-4 w-4" />Ekle
        </button>

        <div className="pt-2 border-t border-line">
          <div className="text-xs text-subtle mb-1">Toplu ekleme — her satıra bir öğe{anlamGerekli ? " (\"içerik | anlam\" biçiminde; anlam opsiyonel)" : ""}.</div>
          <textarea value={toplu} onChange={(e) => setToplu(e.target.value)} rows={4}
            placeholder={anlamGerekli ? "göz atmak | kısaca bakmak\nkulak vermek | dikkatle dinlemek" : "Bir berber bir berbere...\nAl şu takatukaları..."}
            className="w-full border border-line rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-y" />
          <button onClick={topluEkle} className="inline-flex items-center gap-1 mt-2 border border-line text-content text-sm px-3 py-1.5 rounded-xl hover:bg-app">
            <Plus className="h-4 w-4" />Toplu Ekle
          </button>
        </div>
      </div>

      {/* Araç çubuğu */}
      <div className="flex items-center gap-2 flex-wrap">
        <input value={ara} onChange={(e) => { setAra(e.target.value); setSayfa(1); }} placeholder="Ara…"
          className="border border-line rounded-lg px-3 py-1.5 text-sm bg-surface focus:outline-none focus:ring-2 focus:ring-primary" />
        {anlamGerekli && (
          <button onClick={aiAnlam} className="inline-flex items-center gap-1 text-sm border border-line px-3 py-1.5 rounded-xl hover:bg-app text-primary">
            <Sparkles className="h-4 w-4" />Boş anlamları AI ile doldur
          </button>
        )}
        <span className="text-xs text-subtle ml-auto tabular-nums">{toplam} öğe</span>
      </div>

      {/* Liste */}
      <div className="bg-surface border border-line rounded-2xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-subtle border-b border-line bg-app">
              <th className="px-3 py-2">İçerik</th>
              {anlamGerekli && <th className="px-3 py-2">Anlam</th>}
              <th className="px-3 py-2 w-16">Sınıf</th>
              <th className="px-3 py-2 w-12"></th>
            </tr>
          </thead>
          <tbody>
            {yukleniyor && <tr><td colSpan={4} className="px-3 py-6 text-center text-subtle">Yükleniyor…</td></tr>}
            {!yukleniyor && liste.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-subtle">Henüz öğe yok.</td></tr>}
            {!yukleniyor && liste.map((o) => (
              <tr key={o.id} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-content">{o.icerik}</td>
                {anlamGerekli && <td className="px-3 py-2 text-subtle">{o.anlam || <span className="text-amber-600 text-xs">AI bekliyor…</span>}</td>}
                <td className="px-3 py-2 tabular-nums text-subtle">{o.sinif_seviyesi}</td>
                <td className="px-3 py-2">
                  <button onClick={() => sil(o.id)} className="text-red-400 hover:text-red-600" aria-label="Sil"><Trash2 className="h-4 w-4" /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Sayfalama */}
      {sayfaSayisi > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button disabled={sayfa <= 1} onClick={() => setSayfa((s) => s - 1)} className="px-3 py-1 rounded-lg border border-line text-sm disabled:opacity-30 hover:bg-app">Önceki</button>
          <span className="text-xs text-subtle tabular-nums">{sayfa} / {sayfaSayisi}</span>
          <button disabled={sayfa >= sayfaSayisi} onClick={() => setSayfa((s) => s + 1)} className="px-3 py-1 rounded-lg border border-line text-sm disabled:opacity-30 hover:bg-app">Sonraki</button>
        </div>
      )}
    </div>
  );
}
