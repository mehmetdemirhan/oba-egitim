import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { useToast } from "../hooks/use-toast";
import { HelpCircle, Search, ChevronDown, ChevronRight, Send, CheckCircle } from "lucide-react";

/**
 * SSS — kullanıcı tarafı yardım bölümü (öğretmen/veli/öğrenci).
 * Rolüne açık yayın kayıtlarını kategorili akordiyon + arama ile gösterir.
 * "Sorum burada yok" akışıyla soru gönderir (yayında görünmez, kuyruğa düşer).
 * Props: apiBase.
 */
const inp = "border border-line rounded-lg px-3 py-2 text-sm bg-surface";

export default function SSS({ apiBase }) {
  const { toast } = useToast();
  const [kayitlar, setKayitlar] = useState([]);
  const [kategoriler, setKategoriler] = useState([]);
  const [ara, setAra] = useState("");
  const [acikId, setAcikId] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);

  // Soru gönderme
  const [soruAcik, setSoruAcik] = useState(false);
  const [soruKategori, setSoruKategori] = useState("Genel");
  const [soruMetin, setSoruMetin] = useState("");
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [gonderildi, setGonderildi] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${apiBase}/sss`);
        setKayitlar(r.data?.kayitlar || []);
        setKategoriler(r.data?.kategoriler || []);
      } catch {
        toast({ title: "SSS yüklenemedi", variant: "destructive" });
      } finally {
        setYukleniyor(false);
      }
    })();
  }, [apiBase, toast]);

  // Arama + kategoriye göre grupla
  const gruplu = useMemo(() => {
    const q = ara.trim().toLocaleLowerCase("tr");
    const filt = q
      ? kayitlar.filter((k) => (k.soru || "").toLocaleLowerCase("tr").includes(q) ||
                               (k.cevap || "").toLocaleLowerCase("tr").includes(q))
      : kayitlar;
    const map = {};
    filt.forEach((k) => {
      const kat = k.kategori || "Genel";
      (map[kat] = map[kat] || []).push(k);
    });
    return map;
  }, [kayitlar, ara]);

  const gonder = async () => {
    if (!soruMetin.trim()) { toast({ title: "Lütfen sorunuzu yazın", variant: "destructive" }); return; }
    setGonderiliyor(true);
    try {
      await axios.post(`${apiBase}/sss/soru`, { soru: soruMetin, kategori: soruKategori });
      setGonderildi(true);
      setSoruMetin("");
      toast({ title: "Sorunuz iletildi", description: "Yanıtlandığında bildirim alacaksınız." });
    } catch (e) {
      const msg = e?.response?.status === 429
        ? (e?.response?.data?.detail || "Günlük soru limitine ulaştınız.")
        : (e?.response?.data?.detail || "Soru gönderilemedi.");
      toast({ title: "Gönderilemedi", description: msg, variant: "destructive" });
    } finally {
      setGonderiliyor(false);
    }
  };

  const katListe = kategoriler.length ? kategoriler : Object.keys(gruplu);

  return (
    <div className="space-y-4 max-w-3xl">
      <div>
        <h2 className="text-xl font-bold text-content inline-flex items-center gap-2">
          <HelpCircle className="h-6 w-6" />SSS / Yardım
        </h2>
        <p className="text-sm text-subtle">Sık sorulan sorular. Aradığınızı bulamazsanız bize sorabilirsiniz.</p>
      </div>

      {/* Arama */}
      <div className="relative">
        <Search className="h-4 w-4 text-subtle absolute left-3 top-1/2 -translate-y-1/2" />
        <input type="text" value={ara} onChange={(e) => setAra(e.target.value)}
               placeholder="Soru ara…" className={`${inp} w-full pl-9`} />
      </div>

      {yukleniyor && <p className="text-subtle text-sm">Yükleniyor…</p>}
      {!yukleniyor && kayitlar.length === 0 && (
        <p className="text-subtle text-sm bg-app rounded-lg p-3">Henüz yayınlanmış soru yok. Aşağıdan bize sorabilirsiniz.</p>
      )}

      {/* Kategorili akordiyon */}
      <div className="space-y-4">
        {katListe.map((kat) => {
          const liste = gruplu[kat] || [];
          if (liste.length === 0) return null;
          return (
            <div key={kat}>
              <h3 className="text-sm font-bold text-subtle uppercase tracking-wide mb-2">{kat}</h3>
              <div className="space-y-2">
                {liste.map((k) => {
                  const acik = acikId === k.id;
                  return (
                    <div key={k.id} className="bg-surface border border-line rounded-2xl shadow-sm overflow-hidden">
                      <button onClick={() => setAcikId(acik ? null : k.id)}
                              className="w-full flex items-center justify-between gap-2 px-4 py-3 text-left hover:bg-app">
                        <span className="text-sm font-medium text-content">{k.soru}</span>
                        {acik ? <ChevronDown className="h-4 w-4 text-subtle shrink-0" /> : <ChevronRight className="h-4 w-4 text-subtle shrink-0" />}
                      </button>
                      {acik && (
                        <div className="px-4 pb-3 text-sm text-subtle whitespace-pre-wrap border-t border-line pt-2">{k.cevap}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Sorum burada yok */}
      <div className="bg-app border border-line rounded-2xl p-4">
        {gonderildi ? (
          <div className="flex items-center gap-2 text-emerald-600 text-sm font-medium">
            <CheckCircle className="h-5 w-5" />Sorunuz iletildi. Yanıtlandığında bildirim alacaksınız.
            <button onClick={() => setGonderildi(false)} className="ml-2 text-subtle underline text-xs">Yeni soru</button>
          </div>
        ) : !soruAcik ? (
          <button onClick={() => setSoruAcik(true)} className="text-sm font-medium text-indigo-600 hover:underline">
            Sorum burada yok →
          </button>
        ) : (
          <div className="space-y-2">
            <p className="text-sm font-bold text-content">Sorunuzu iletin</p>
            <select value={soruKategori} onChange={(e) => setSoruKategori(e.target.value)} className={inp}>
              {(kategoriler.length ? kategoriler : ["Genel"]).map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
            <textarea value={soruMetin} onChange={(e) => setSoruMetin(e.target.value)} rows={3} maxLength={1000}
                      placeholder="Sorunuzu yazın…" className={`${inp} w-full`} />
            <div className="flex items-center gap-2">
              <button disabled={gonderiliyor} onClick={gonder}
                      className="inline-flex items-center gap-1 bg-indigo-600 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-indigo-700 disabled:opacity-50">
                <Send className="h-4 w-4" />Gönder
              </button>
              <button onClick={() => setSoruAcik(false)} className="border border-line rounded-lg px-3 py-1.5 text-sm hover:bg-surface">Vazgeç</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
