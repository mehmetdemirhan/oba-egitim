import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { RefreshCw, Save, RotateCcw } from "lucide-react";

/**
 * GirisRaporAyarlari — admin/koordinatör için iki editör:
 *  A) Giriş Analizi Rapor Metinleri (Sonuç ve Genel Yorum + Eğitsel/Ev Önerileri
 *     metin bankası; bant/kombinasyon bazlı). Uçlar: GET/PUT/reset /diagnostic/rapor-metinleri.
 *  B) Sınıf Ölçüm Kategorileri (hangi sınıfta 4.1-4.4 pasif). Uçlar: GET/PUT /diagnostic/sinif-kategorileri.
 */
const BANT_ETIKET = {
  giris: "Giriş cümlesi", kapanis: "Kapanış / öneri (genel düzey bandı)",
  hiz: "Okuma hızı düzeyi", dogruluk: "Doğru okuma", anlama: "Okuduğunu anlama",
  prozodik: "Prozodik okuma",
  oneriler_baslik: "Öneriler başlığı", oneriler_okul_baslik: "Okul önerileri başlığı",
  oneriler_ev_baslik: "Ev önerileri başlığı", oneriler_okul: "Okul çalışma önerileri",
  oneriler_ev: "Ev çalışma önerileri",
};
const GRUP_ADI = { "4.1": "Sözcük Düzeyinde", "4.2": "Ana Yapı", "4.3": "Derin Anlama", "4.4": "Eleştirel/Yaratıcı" };
const SINIFLAR = ["1", "2", "3", "4", "5", "6", "7", "8"];

export default function GirisRaporAyarlari({ apiBase }) {
  const [metinler, setMetinler] = useState(null);
  const [kategoriler, setKategoriler] = useState(null);
  const [yuk, setYuk] = useState(false);
  const [kaydet, setKaydet] = useState("");

  const yukle = useCallback(async () => {
    setYuk(true);
    try {
      const [m, k] = await Promise.all([
        axios.get(`${apiBase}/diagnostic/rapor-metinleri`),
        axios.get(`${apiBase}/diagnostic/sinif-kategorileri`),
      ]);
      setMetinler(m.data.metinler || {});
      setKategoriler(k.data.kategoriler || {});
    } catch (e) { /* yut */ } finally { setYuk(false); }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  const metinKaydet = async () => {
    setKaydet("m");
    try { await axios.put(`${apiBase}/diagnostic/rapor-metinleri`, { metinler }); }
    catch (e) { /* yut */ } finally { setKaydet(""); }
  };
  const metinReset = async () => {
    if (!window.confirm("Rapor metinleri varsayılana dönsün mü?")) return;
    const r = await axios.post(`${apiBase}/diagnostic/rapor-metinleri/varsayilana-don`);
    setMetinler(r.data.metinler || {});
  };
  const kategoriKaydet = async () => {
    setKaydet("k");
    try { await axios.put(`${apiBase}/diagnostic/sinif-kategorileri`, { kategoriler }); }
    catch (e) { /* yut */ } finally { setKaydet(""); }
  };

  // metinler içindeki bir yolu güncelle (yol: dizi)
  const setYol = (yol, deger) => {
    setMetinler((m) => {
      const kopya = JSON.parse(JSON.stringify(m));
      let ref = kopya;
      for (let i = 0; i < yol.length - 1; i++) ref = ref[yol[i]];
      ref[yol[yol.length - 1]] = deger;
      return kopya;
    });
  };

  const alanCiz = (anahtar, deger, yol) => {
    if (typeof deger === "string") {
      return (
        <label key={yol.join(".")} className="block mb-2">
          <span className="text-xs text-subtle">{BANT_ETIKET[anahtar] || anahtar}</span>
          <textarea value={deger} onChange={(e) => setYol(yol, e.target.value)} rows={2}
            className="mt-1 w-full px-2 py-1.5 rounded-lg border border-line text-xs" />
        </label>
      );
    }
    if (Array.isArray(deger)) {
      return (
        <div key={yol.join(".")} className="mb-2">
          <div className="text-xs font-semibold text-content mb-1">{BANT_ETIKET[anahtar] || anahtar}</div>
          {deger.map((m, i) => (
            <textarea key={i} value={m} onChange={(e) => { const yeni = [...deger]; yeni[i] = e.target.value; setYol(yol, yeni); }} rows={2}
              className="mb-1 w-full px-2 py-1.5 rounded-lg border border-line text-xs" />
          ))}
        </div>
      );
    }
    if (deger && typeof deger === "object") {
      return (
        <div key={yol.join(".")} className="mb-3 pl-2 border-l-2 border-line">
          <div className="text-xs font-semibold text-primary mb-1">{BANT_ETIKET[anahtar] || anahtar}</div>
          {Object.entries(deger).map(([k, v]) => alanCiz(k, v, [...yol, k]))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-5">
      {/* A) Rapor metinleri */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="font-semibold text-content">Giriş Analizi Rapor Metinleri</div>
          <button onClick={yukle} disabled={yuk} className="ml-auto inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-2.5 py-1 text-xs"><RefreshCw className={`h-3.5 w-3.5 ${yuk ? "animate-spin" : ""}`} />Yenile</button>
          <button onClick={metinReset} className="inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-2.5 py-1 text-xs"><RotateCcw className="h-3.5 w-3.5" />Varsayılan</button>
          <button onClick={metinKaydet} disabled={kaydet === "m"} className="inline-flex items-center gap-1.5 bg-primary text-white rounded-lg px-2.5 py-1 text-xs disabled:opacity-50"><Save className="h-3.5 w-3.5" />{kaydet === "m" ? "…" : "Kaydet"}</button>
        </div>
        <p className="text-xs text-subtle mb-2">Sonuç paragrafı, hıza/doğruluğa/anlamaya/prozodiye göre bu bantlardan birleştirilir. {"{ad}"} → öğrenci adı.</p>
        {metinler ? (
          <div className="max-h-[55vh] overflow-y-auto pr-1">
            {Object.entries(metinler).map(([k, v]) => alanCiz(k, v, [k]))}
          </div>
        ) : <div className="text-sm text-subtle py-4">Yükleniyor…</div>}
      </div>

      {/* B) Sınıf ölçüm kategorileri */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <div className="font-semibold text-content">Sınıf Ölçüm Kategorileri</div>
          <button onClick={kategoriKaydet} disabled={kaydet === "k"} className="ml-auto inline-flex items-center gap-1.5 bg-primary text-white rounded-lg px-2.5 py-1 text-xs disabled:opacity-50"><Save className="h-3.5 w-3.5" />{kaydet === "k" ? "…" : "Kaydet"}</button>
        </div>
        <p className="text-xs text-subtle mb-2">İşaretli (aktif) kategoriler o sınıfta ölçülür. 4.5 (Soru Performansı) her zaman aktiftir. Varsayılan: 1. sınıfta 4.1–4.4 pasif.</p>
        {kategoriler !== null ? (
          <div className="overflow-x-auto">
            <table className="text-xs w-full">
              <thead><tr className="text-subtle"><th className="text-left py-1 pr-2">Sınıf</th>{["4.1", "4.2", "4.3", "4.4"].map(g => <th key={g} className="px-2">{g} {GRUP_ADI[g]}</th>)}</tr></thead>
              <tbody>
                {SINIFLAR.map((s) => {
                  const pasif = kategoriler[s] || [];
                  return (
                    <tr key={s} className="border-t border-line">
                      <td className="py-1.5 pr-2 font-medium">{s}. Sınıf</td>
                      {["4.1", "4.2", "4.3", "4.4"].map((g) => (
                        <td key={g} className="px-2 text-center">
                          <input type="checkbox" checked={!pasif.includes(g)}
                            onChange={(e) => {
                              setKategoriler((c) => {
                                const kopya = { ...c };
                                const liste = new Set(kopya[s] || []);
                                if (e.target.checked) liste.delete(g); else liste.add(g);
                                const arr = [...liste];
                                if (arr.length) kopya[s] = arr; else delete kopya[s];
                                return kopya;
                              });
                            }} />
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : <div className="text-sm text-subtle py-4">Yükleniyor…</div>}
      </div>
    </div>
  );
}
