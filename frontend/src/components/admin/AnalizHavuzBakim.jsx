import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Download, Upload, Sparkles, Trash2, Archive, RefreshCw } from "lucide-react";

/**
 * AnalizHavuzBakim — admin: Akıcı Okuma (150) tek-kaynak havuz bakımı.
 * Sıra: (1) Yedek Al → (2) İçe Aktar (150) → (3) AI Cevap Üret → (4) Tam Temizle.
 * Silme geri dönüşsüzdür ama geçmiş öğrenci ilerlemesi snapshot'lı olduğundan bozulmaz.
 */
export default function AnalizHavuzBakim({ apiBase }) {
  const [durum, setDurum] = useState({});
  const [mesaj, setMesaj] = useState("");
  const [yukleniyor, setYukleniyor] = useState("");
  const [yedekler, setYedekler] = useState([]);
  const [ornek, setOrnek] = useState(null);
  const api = (x) => `${apiBase}${x}`;

  const sayilariYukle = useCallback(async () => {
    try {
      const [analiz, eski] = await Promise.all([
        axios.get(api("/diagnostic/texts?bolum=analiz")),
        axios.get(api("/diagnostic/texts?bolum=okuma_parcalari")),
      ]);
      const dusuk = (analiz.data || []).reduce((n, m) => n + (m.sorular || []).filter(s => s.kontrol_gerekli).length, 0);
      setDurum({ analiz: (analiz.data || []).length, eski: (eski.data || []).length, dusuk_guven: dusuk });
    } catch (e) {}
    try { const r = await axios.get(api("/diagnostic/analiz-havuz/yedekler")); setYedekler(r.data.yedekler || []); } catch (e) {}
  }, [apiBase]);
  useEffect(() => { sayilariYukle(); }, [sayilariYukle]);

  const calistir = async (ad, fn) => {
    setYukleniyor(ad); setMesaj("");
    try { const m = await fn(); setMesaj(m || "Tamam ✓"); await sayilariYukle(); }
    catch (e) { setMesaj("Hata: " + (e.response?.data?.detail || e.message)); }
    finally { setYukleniyor(""); }
  };

  const yedekAl = () => calistir("yedek", async () => {
    const r = await axios.post(api("/diagnostic/analiz-havuz/yedekle"));
    return `Yedek alındı: ${r.data.yedeklenen_metin} metin (parti ${r.data.parti_id.slice(0, 8)})`;
  });
  const iceAktar = () => calistir("import", async () => {
    const r = await axios.post(api("/diagnostic/akici-okuma-goc"));
    return `İçe aktarım: ${r.data.eklenen} yeni, ${r.data.guncellenen} güncellendi, ${r.data.okuma_parcalarina_tasinan} eski taşındı`;
  });
  const cevapUret = () => calistir("cevap", async () => {
    let toplam = 0, tur = 0;
    while (true) {
      const r = await axios.post(api("/diagnostic/analiz-havuz/cevap-uret?limit=25"));
      toplam += r.data.islenen_metin; tur++;
      setMesaj(`AI cevap üretiliyor… ${toplam} metin işlendi, ${r.data.kalan_metin} kaldı`);
      if (r.data.kalan_metin <= 0 || r.data.islenen_metin === 0 || tur > 20) break;
    }
    return `AI cevap üretimi bitti: ${toplam} metin işlendi. Düşük güvenli sorular öğretmen paneline düştü.`;
  });
  const ornekGetir = () => calistir("ornek", async () => {
    const r = await axios.get(api("/diagnostic/analiz-havuz/cevap-ornek?n=10"));
    setOrnek(r.data);
    return `Örneklem: ${r.data.metin_sayisi} metin × ${r.data.toplam_soru} soru getirildi (aşağıda).`;
  });

  const tamTemizle = () => {
    if (!window.confirm("GERİ DÖNÜŞSÜZ: 150 Akıcı Okuma DIŞINDAKİ tüm metinler KALICI silinecek. Önce yedek aldığından emin misin?")) return;
    if (!window.confirm("Son onay: Silme işlemini başlatayım mı?")) return;
    calistir("temizle", async () => {
      const r = await axios.post(api("/diagnostic/analiz-havuz/temizle?onay=true"));
      return `Temizlik: ${r.data.silinen} metin silindi, ${r.data.korunan_akici} Akıcı Okuma korundu`;
    });
  };

  const Btn = ({ id, on, ikon, children, kirmizi }) => (
    <button onClick={on} disabled={!!yukleniyor}
      className={`inline-flex items-center gap-1.5 text-sm rounded-lg px-3 py-2 disabled:opacity-50 ${kirmizi ? "bg-red-600 text-white" : "bg-indigo-600 text-white"}`}>
      {yukleniyor === id ? <RefreshCw className="h-4 w-4 animate-spin" /> : ikon}{children}
    </button>
  );

  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-bold text-content text-sm flex items-center gap-1.5"><Archive className="h-4 w-4" />Analiz Havuzu Bakımı (Akıcı Okuma — tek kaynak)</h3>
        <div className="text-xs text-subtle">Havuz: <b>{durum.analiz ?? "…"}</b> · Eski: <b>{durum.eski ?? "…"}</b> · Düşük güvenli soru: <b>{durum.dusuk_guven ?? "…"}</b></div>
      </div>
      <div className="text-xs text-subtle">Sıra: 1) Yedek Al → 2) İçe Aktar (150) → 3) AI Cevap Üret → 4) Tam Temizle. Silme geri dönüşsüzdür; geçmiş öğrenci ilerlemesi korunur (snapshot).</div>
      <div className="flex flex-wrap gap-2">
        <Btn id="yedek" on={yedekAl} ikon={<Archive className="h-4 w-4" />}>1 · Yedek Al</Btn>
        <Btn id="import" on={iceAktar} ikon={<Upload className="h-4 w-4" />}>2 · İçe Aktar (150)</Btn>
        <Btn id="cevap" on={cevapUret} ikon={<Sparkles className="h-4 w-4" />}>3 · AI Cevap Üret</Btn>
        <Btn id="ornek" on={ornekGetir} ikon={<RefreshCw className="h-4 w-4" />}>3b · Cevap Örneklemi (10 metin)</Btn>
        <Btn id="temizle" on={tamTemizle} ikon={<Trash2 className="h-4 w-4" />} kirmizi>4 · Tam Temizle</Btn>
      </div>
      {mesaj && <div className="text-sm rounded-lg bg-app border border-line px-3 py-2">{mesaj}</div>}
      {ornek?.ornekler?.length > 0 && (
        <div className="border border-line rounded-xl p-3 max-h-96 overflow-auto space-y-3">
          <div className="text-xs font-semibold text-primary">AI Cevap Örneklemi — {ornek.metin_sayisi} metin × {ornek.toplam_soru} soru (dayanak cümleyle)</div>
          {ornek.ornekler.map((m, i) => (
            <div key={m.id} className="text-xs border-b border-line pb-2">
              <div className="font-semibold text-content">{i + 1}. {m.baslik} ({m.kelime_sayisi} kelime)</div>
              {m.sorular.map((s, j) => (
                <div key={j} className="mt-1 pl-2">
                  <div className="text-content">{j + 1}. {s.soru}</div>
                  <div className="pl-3 text-subtle">
                    {["A", "B", "C", "D"].filter(L => s.secenekler?.[L]).map(L => (
                      <span key={L} className={`inline-block mr-2 ${s.dogru_cevap === L ? "text-emerald-700 font-semibold" : ""}`}>{L}) {s.secenekler[L]}{s.dogru_cevap === L ? " ✓" : ""}</span>
                    ))}
                  </div>
                  <div className="pl-3">
                    <span className={`text-[10px] rounded px-1 ${s.guven === "high" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{s.guven === "high" ? "yüksek güven" : "düşük güven"}</span>
                    {s.kaynak === "manuel" && <span className="text-[10px] bg-blue-100 text-blue-700 rounded px-1 ml-1">manuel</span>}
                    {s.dayanak && <span className="text-subtle italic ml-1">— dayanak: "{s.dayanak}"</span>}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
      {yedekler.length > 0 && (
        <div className="text-xs">
          <div className="font-semibold text-subtle mb-1">Yedekler ({yedekler.length})</div>
          <div className="space-y-0.5">
            {yedekler.slice(0, 5).map(y => (
              <div key={y.id} className="flex items-center justify-between gap-2">
                <span>{new Date(y.tarih).toLocaleString("tr-TR")} · {y.metin_sayisi} metin</span>
                <a href={api(`/diagnostic/analiz-havuz/yedek/${y.id}`)} target="_blank" rel="noreferrer" className="text-primary inline-flex items-center gap-0.5"><Download className="h-3 w-3" />JSON</a>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
