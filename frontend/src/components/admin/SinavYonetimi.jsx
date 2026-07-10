import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";

/**
 * SinavYonetimi — yönetici Sınav soru bankası (LGS/Bursluluk).
 * PDF yükle → her soru "taslak" kaydedilir → "Taslak Sorular" ekranında solda
 * orijinal kırpım görseli / sağda çıkarılan metin-şık-cevap yan yana; admin
 * düzeltir, gosterimTuru/konu/zorluk/cozumTaktigi doldurur (AI taktik önerisi
 * opsiyonel), yayınlar. AI çıktısı asla otomatik yayınlanmaz.
 *
 * Props: apiBase — `${BACKEND_URL}/api`
 */
const DERS_FALLBACK = [
  { key: "turkce", ad: "Türkçe" },
  { key: "inkilap_tarihi", ad: "T.C. İnkılap Tarihi ve Atatürkçülük" },
  { key: "din_kulturu", ad: "Din Kültürü ve Ahlak Bilgisi" },
];
const DURUM_ETIKET = { taslak: "Taslak", yayinda: "Yayında", arsivli: "Arşivli" };
const ZORLUK_RENK = { kolay: "bg-green-100 text-green-700", orta: "bg-amber-100 text-amber-700", zor: "bg-red-100 text-red-700" };
const SIKLAR = ["A", "B", "C", "D"];

/** Bearer-korumalı /gorsel endpoint'i <img src> ile çalışmaz → blob + objectURL. */
function SoruGorsel({ apiBase, soruId, className }) {
  const [url, setUrl] = useState(null);
  const [hata, setHata] = useState(false);
  useEffect(() => {
    let aktif = true;
    let objUrl = null;
    setUrl(null); setHata(false);
    axios
      .get(`${apiBase}/sinav/soru/${soruId}/gorsel`, { responseType: "blob" })
      .then((r) => { if (!aktif) return; objUrl = URL.createObjectURL(r.data); setUrl(objUrl); })
      .catch(() => aktif && setHata(true));
    return () => { aktif = false; if (objUrl) URL.revokeObjectURL(objUrl); };
  }, [apiBase, soruId]);
  if (hata) return <div className="text-xs text-red-400 p-4">Görsel yüklenemedi.</div>;
  if (!url) return <div className="text-xs text-gray-400 p-4">Görsel yükleniyor…</div>;
  return <img src={url} alt="Orijinal soru" className={className} />;
}

export default function SinavYonetimi({ apiBase }) {
  const [dersler, setDersler] = useState(DERS_FALLBACK);
  const [sinavTurleri, setSinavTurleri] = useState(["LGS", "bursluluk"]);
  const [zorluklar, setZorluklar] = useState(["kolay", "orta", "zor"]);

  // Yükleme formu
  const [dosya, setDosya] = useState(null);
  const [sinavTuru, setSinavTuru] = useState("LGS");
  const [yil, setYil] = useState(new Date().getFullYear());
  const [sinifSeviyesi, setSinifSeviyesi] = useState(8);
  const [yukleniyor, setYukleniyor] = useState(false);

  // Gruplar + taslak listesi
  const [gruplar, setGruplar] = useState([]);
  const [aktifGrup, setAktifGrup] = useState("");
  const [filtreDers, setFiltreDers] = useState("");
  const [filtreDurum, setFiltreDurum] = useState("");
  const [sayfa, setSayfa] = useState(1);
  const [veri, setVeri] = useState({ sorular: [], toplam: 0, sayfa_sayisi: 1 });
  const [tabloYukleniyor, setTabloYukleniyor] = useState(false);

  const [duzenle, setDuzenle] = useState(null); // düzenlenen soru kopyası
  const [aiYukleniyor, setAiYukleniyor] = useState(false);
  const [toast, setToast] = useState(null);

  const toastGoster = (tip, metin) => { setToast({ tip, metin }); setTimeout(() => setToast(null), 3800); };
  const dersAd = (k) => dersler.find((d) => d.key === k)?.ad || k;

  // Enum + gruplar (bir kez)
  useEffect(() => {
    axios.get(`${apiBase}/sinav/dersler`).then((r) => {
      if (r.data?.dersler) setDersler(r.data.dersler);
      if (r.data?.sinavTurleri) setSinavTurleri(r.data.sinavTurleri);
      if (r.data?.zorluklar) setZorluklar(r.data.zorluklar);
    }).catch(() => {});
    grupGetir();
  }, [apiBase]); // eslint-disable-line

  const grupGetir = useCallback(async () => {
    try {
      const r = await axios.get(`${apiBase}/sinav/gruplar`);
      setGruplar(r.data?.gruplar || []);
    } catch { /* sessiz */ }
  }, [apiBase]);

  const listele = useCallback(async (gidilecek = 1) => {
    if (!aktifGrup) { setVeri({ sorular: [], toplam: 0, sayfa_sayisi: 1 }); return; }
    setTabloYukleniyor(true);
    try {
      const r = await axios.get(`${apiBase}/sinav/taslaklar`, {
        params: { grup_id: aktifGrup, ders: filtreDers || undefined, durum: filtreDurum || undefined, sayfa: gidilecek, limit: 50 },
      });
      setVeri(r.data || { sorular: [], toplam: 0, sayfa_sayisi: 1 });
    } catch {
      toastGoster("hata", "Liste yüklenemedi.");
    } finally { setTabloYukleniyor(false); }
  }, [apiBase, aktifGrup, filtreDers, filtreDurum]);

  useEffect(() => { setSayfa(1); listele(1); /* eslint-disable-next-line */ }, [aktifGrup, filtreDers, filtreDurum]);

  // ── PDF yükle → taslak kaydet ──
  const yukle = async () => {
    if (!dosya) { toastGoster("hata", "Önce PDF seçin."); return; }
    if (dosya.size > 25 * 1024 * 1024) { toastGoster("hata", "PDF en fazla 25MB olabilir."); return; }
    const fd = new FormData();
    fd.append("dosya", dosya);
    fd.append("sinavTuru", sinavTuru);
    fd.append("yil", String(yil));
    fd.append("sinifSeviyesi", String(sinifSeviyesi));
    setYukleniyor(true);
    try {
      const r = await axios.post(`${apiBase}/sinav/yukle`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      const u = r.data?.uyarilar?.length ? ` (${r.data.uyarilar.length} uyarı)` : "";
      toastGoster("ok", `✅ ${r.data.olusturulan} soru taslağa eklendi${u}.`);
      setDosya(null);
      await grupGetir();
      setAktifGrup(r.data.grup_id);
    } catch (e) {
      toastGoster("hata", e?.response?.data?.detail || "PDF işlenemedi.");
    } finally { setYukleniyor(false); }
  };

  // ── Düzenle kaydet (PUT) ──
  const duzenleKaydet = async (kapat = true) => {
    if (!duzenle) return;
    try {
      await axios.put(`${apiBase}/sinav/soru/${duzenle.id}`, {
        ders: duzenle.ders,
        soruMetni: duzenle.soruMetni,
        secenekler: duzenle.secenekler || {},
        dogruCevap: duzenle.dogruCevap || null,
        konu: duzenle.konu || "",
        zorluk: duzenle.zorluk || null,
        gosterimTuru: duzenle.gosterimTuru,
        cozumTaktigi: duzenle.cozumTaktigi || "",
      });
      toastGoster("ok", "✅ Kaydedildi");
      if (kapat) setDuzenle(null);
      listele(sayfa);
    } catch (e) {
      toastGoster("hata", e?.response?.data?.detail || "Kaydedilemedi.");
    }
  };

  const aiTaktikOner = async () => {
    if (!duzenle) return;
    setAiYukleniyor(true);
    try {
      const r = await axios.post(`${apiBase}/sinav/soru/${duzenle.id}/ai-taktik`);
      setDuzenle((d) => ({ ...d, cozumTaktigi: r.data?.cozumTaktigi_oneri || d.cozumTaktigi }));
      toastGoster("ok", "🤖 AI önerisi eklendi — düzenleyip kaydedin.");
    } catch (e) {
      toastGoster("hata", e?.response?.data?.detail || "AI önerisi alınamadı.");
    } finally { setAiYukleniyor(false); }
  };

  const yayinla = async (id) => {
    try {
      await axios.post(`${apiBase}/sinav/soru/${id}/yayinla`);
      toastGoster("ok", "✅ Yayınlandı");
      listele(sayfa); grupGetir();
    } catch (e) { toastGoster("hata", e?.response?.data?.detail || "Yayınlanamadı."); }
  };

  const grupYayinla = async () => {
    if (!aktifGrup) return;
    if (!window.confirm("Bu gruptaki, doğru cevabı olan tüm taslaklar yayınlansın mı?")) return;
    try {
      const r = await axios.post(`${apiBase}/sinav/grup/${aktifGrup}/yayinla`);
      toastGoster("ok", `✅ ${r.data.yayinlanan} soru yayınlandı.`);
      listele(sayfa); grupGetir();
    } catch (e) { toastGoster("hata", e?.response?.data?.detail || "Toplu yayın başarısız."); }
  };

  const arsivle = async (id) => {
    if (!window.confirm("Bu soruyu arşivlemek istiyor musunuz?")) return;
    try { await axios.delete(`${apiBase}/sinav/soru/${id}`); listele(sayfa); grupGetir(); }
    catch { toastGoster("hata", "Arşivlenemedi."); }
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-bold text-gray-800">📝 Sınav Soru Bankası</h3>
        <p className="text-sm text-gray-500">LGS/Bursluluk PDF'i yükleyin; sorular taslağa düşer. Solda orijinal görüntü, sağda çıkarılan metinle karşılaştırıp düzeltin, çözüm taktiğini girip yayınlayın.</p>
      </div>

      {/* ── Yükleme kartı ── */}
      <div className="bg-white rounded-2xl border shadow-sm p-5 space-y-3">
        <div className="font-semibold text-gray-700">📄 Yeni Sınav PDF'i Yükle</div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-gray-600 flex flex-col gap-1">Sınav Türü
            <select value={sinavTuru} onChange={(e) => setSinavTuru(e.target.value)} className="px-3 py-2 rounded-xl border border-gray-200 text-sm">
              {sinavTurleri.map((t) => <option key={t} value={t}>{t === "LGS" ? "LGS" : "Bursluluk"}</option>)}
            </select>
          </label>
          <label className="text-xs text-gray-600 flex flex-col gap-1">Yıl
            <input type="number" value={yil} onChange={(e) => setYil(Number(e.target.value))} className="w-24 px-3 py-2 rounded-xl border border-gray-200 text-sm" />
          </label>
          <label className="text-xs text-gray-600 flex flex-col gap-1">Sınıf
            <input type="number" value={sinifSeviyesi} onChange={(e) => setSinifSeviyesi(Number(e.target.value))} className="w-20 px-3 py-2 rounded-xl border border-gray-200 text-sm" />
          </label>
          <label className="text-xs text-gray-600 flex flex-col gap-1">Dosya (PDF, max 25MB)
            <input type="file" accept=".pdf" onChange={(e) => setDosya(e.target.files?.[0] || null)} className="text-sm" />
          </label>
          <button onClick={yukle} disabled={yukleniyor || !dosya}
            className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50">
            {yukleniyor ? "İşleniyor…" : "⬆️ Yükle ve Ayrıştır"}
          </button>
        </div>
        <div className="text-[11px] text-gray-400">İngilizce bölümü otomatik atlanır. Cevap anahtarı PDF'in son sayfasından eşleştirilir.</div>
      </div>

      {/* ── Grup seçimi ── */}
      <div className="bg-white rounded-2xl border shadow-sm p-4">
        <div className="text-xs font-semibold text-gray-500 mb-2">Yüklenen Sınavlar</div>
        {gruplar.length === 0 ? (
          <div className="text-sm text-gray-400">Henüz sınav yüklenmedi.</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {gruplar.map((g) => {
              const secili = g.grup_id === aktifGrup;
              return (
                <button key={g.grup_id} onClick={() => setAktifGrup(g.grup_id)}
                  className={`text-left p-3 rounded-2xl border transition-all ${secili ? "border-indigo-500 bg-indigo-50 ring-2 ring-indigo-200" : "border-gray-200 bg-white hover:border-indigo-300"}`}>
                  <div className="text-sm font-bold text-gray-800 leading-tight truncate">{g.kaynakDosya || "Sınav"}</div>
                  <div className="text-[11px] text-gray-500 mt-0.5">{g.sinavTuru} {g.yil} • {g.kitapcikTuru} kitapçığı</div>
                  <div className="text-[11px] mt-1"><span className="text-amber-600">{g.taslak} taslak</span> · <span className="text-green-600">{g.yayinda} yayında</span> · {g.toplam} toplam</div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {aktifGrup && (
        <>
          {/* ── Filtreler ── */}
          <div className="flex flex-wrap items-end gap-2 bg-white rounded-2xl border p-3 shadow-sm">
            <label className="text-xs text-gray-600 flex flex-col gap-1">Ders
              <select value={filtreDers} onChange={(e) => setFiltreDers(e.target.value)} className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm">
                <option value="">Tümü</option>
                {dersler.map((d) => <option key={d.key} value={d.key}>{d.ad}</option>)}
              </select>
            </label>
            <label className="text-xs text-gray-600 flex flex-col gap-1">Durum
              <select value={filtreDurum} onChange={(e) => setFiltreDurum(e.target.value)} className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm">
                <option value="">Aktif (taslak+yayında)</option>
                <option value="taslak">Taslak</option>
                <option value="yayinda">Yayında</option>
              </select>
            </label>
            <button onClick={grupYayinla} className="ml-auto px-4 py-2 rounded-xl bg-green-600 text-white text-sm font-semibold hover:bg-green-700">✅ Grubu Toplu Yayınla</button>
          </div>

          {/* ── Taslak tablosu ── */}
          <div className="bg-white rounded-2xl border shadow-sm overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b">
                  <th className="px-3 py-2 font-semibold">Ders / No</th>
                  <th className="px-3 py-2 font-semibold">Soru (metin özeti)</th>
                  <th className="px-3 py-2 font-semibold text-center">Cevap</th>
                  <th className="px-3 py-2 font-semibold">Konu</th>
                  <th className="px-3 py-2 font-semibold text-center">Zorluk</th>
                  <th className="px-3 py-2 font-semibold text-center">Gösterim</th>
                  <th className="px-3 py-2 font-semibold text-center">Taktik</th>
                  <th className="px-3 py-2 font-semibold">Durum</th>
                  <th className="px-3 py-2 font-semibold text-right">İşlem</th>
                </tr>
              </thead>
              <tbody>
                {tabloYukleniyor ? (
                  <tr><td colSpan={9} className="px-3 py-10 text-center text-gray-400">Yükleniyor…</td></tr>
                ) : veri.sorular.length === 0 ? (
                  <tr><td colSpan={9} className="px-3 py-10 text-center text-gray-400">Soru bulunamadı.</td></tr>
                ) : veri.sorular.map((s) => (
                  <tr key={s.id} className={`border-b border-gray-50 hover:bg-gray-50/60 ${s.durum === "arsivli" ? "opacity-50" : ""}`}>
                    <td className="px-3 py-2 whitespace-nowrap"><b>{dersAd(s.ders).split(" ")[0]}</b> {s.soruNo}</td>
                    <td className="px-3 py-2 max-w-[18rem]"><span className="line-clamp-2 text-gray-600">{s.soruMetni || <span className="text-gray-300">— (görsel soru)</span>}</span></td>
                    <td className="px-3 py-2 text-center">{s.dogruCevap ? <span className="font-bold text-indigo-600">{s.dogruCevap}</span> : <span className="text-red-400" title="Cevap yok">!</span>}</td>
                    <td className="px-3 py-2 text-gray-500">{s.konu || <span className="text-gray-300">—</span>}</td>
                    <td className="px-3 py-2 text-center"><span className={`text-[10px] px-2 py-0.5 rounded-full ${ZORLUK_RENK[s.zorluk] || "bg-gray-100 text-gray-400"}`}>{s.zorluk || "—"}</span></td>
                    <td className="px-3 py-2 text-center text-xs">{s.gosterimTuru === "gorsel" ? "🖼️" : "📝"}</td>
                    <td className="px-3 py-2 text-center text-xs">{s.cozumTaktigi ? "✅" : <span className="text-gray-300">—</span>}</td>
                    <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded-full ${s.durum === "yayinda" ? "bg-green-100 text-green-700" : s.durum === "taslak" ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-500"}`}>{DURUM_ETIKET[s.durum] || s.durum}</span></td>
                    <td className="px-3 py-2">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => setDuzenle({ ...s, secenekler: s.secenekler || {} })} title="İncele / Düzenle" className="px-2 py-1 rounded-lg text-xs border border-gray-200 hover:bg-gray-100">🔍</button>
                        {s.durum === "taslak" && <button onClick={() => yayinla(s.id)} title="Yayınla" className="px-2 py-1 rounded-lg text-xs border border-green-200 text-green-600 hover:bg-green-50">✅</button>}
                        {s.durum !== "arsivli" && <button onClick={() => arsivle(s.id)} title="Arşivle" className="px-2 py-1 rounded-lg text-xs border border-amber-200 text-amber-600 hover:bg-amber-50">🗑</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {veri.sayfa_sayisi > 1 && (
            <div className="flex items-center justify-center gap-2 text-sm">
              <button disabled={sayfa <= 1} onClick={() => { const p = Math.max(1, sayfa - 1); setSayfa(p); listele(p); }} className="px-3 py-1.5 rounded-lg border border-gray-200 disabled:opacity-40">← Önceki</button>
              <span className="text-gray-500">{sayfa} / {veri.sayfa_sayisi}</span>
              <button disabled={sayfa >= veri.sayfa_sayisi} onClick={() => { const p = sayfa + 1; setSayfa(p); listele(p); }} className="px-3 py-1.5 rounded-lg border border-gray-200 disabled:opacity-40">Sonraki →</button>
            </div>
          )}
        </>
      )}

      {/* ── İnceleme / Düzenleme modalı (Taslak Sorular ekranı) ── */}
      {duzenle && (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4" onClick={() => setDuzenle(null)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-5xl max-h-[92vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-3 border-b sticky top-0 bg-white rounded-t-2xl flex items-center justify-between z-10">
              <div className="font-bold text-gray-800">{dersAd(duzenle.ders)} — {duzenle.soruNo}. soru</div>
              <button onClick={() => setDuzenle(null)} className="text-gray-400 hover:text-gray-700 text-xl leading-none">✕</button>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 p-5">
              {/* Sol: orijinal kırpım görseli */}
              <div className="bg-gray-50 rounded-xl border overflow-y-auto max-h-[70vh] flex items-start justify-center">
                <SoruGorsel apiBase={apiBase} soruId={duzenle.id} className="w-full h-auto" />
              </div>
              {/* Sağ: düzenlenebilir alanlar */}
              <div className="space-y-3">
                <div className="flex gap-2">
                  <label className="text-xs text-gray-500 flex flex-col gap-1 flex-1">Ders
                    <select value={duzenle.ders} onChange={(e) => setDuzenle((d) => ({ ...d, ders: e.target.value }))} className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm">
                      {dersler.map((d) => <option key={d.key} value={d.key}>{d.ad}</option>)}
                    </select>
                  </label>
                  <label className="text-xs text-gray-500 flex flex-col gap-1">Gösterim
                    <select value={duzenle.gosterimTuru} onChange={(e) => setDuzenle((d) => ({ ...d, gosterimTuru: e.target.value }))} className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm">
                      <option value="metin">📝 Metin</option>
                      <option value="gorsel">🖼️ Görsel</option>
                    </select>
                  </label>
                </div>

                <div>
                  <label className="text-xs font-medium text-gray-500">Soru Metni</label>
                  <textarea value={duzenle.soruMetni || ""} onChange={(e) => setDuzenle((d) => ({ ...d, soruMetni: e.target.value }))} rows={4}
                    className="w-full mt-1 px-3 py-2 rounded-xl border border-gray-200 text-sm outline-none focus:border-indigo-400" />
                </div>

                <div className="grid grid-cols-1 gap-1.5">
                  {SIKLAR.map((h) => (
                    <div key={h} className="flex items-center gap-2">
                      <button type="button" onClick={() => setDuzenle((d) => ({ ...d, dogruCevap: h }))}
                        title="Doğru cevap olarak işaretle"
                        className={`w-7 h-7 shrink-0 rounded-full text-xs font-bold border ${duzenle.dogruCevap === h ? "bg-green-600 text-white border-green-600" : "bg-white text-gray-500 border-gray-300 hover:border-green-400"}`}>{h}</button>
                      <input value={duzenle.secenekler?.[h] || ""} onChange={(e) => setDuzenle((d) => ({ ...d, secenekler: { ...d.secenekler, [h]: e.target.value } }))}
                        placeholder={`${h} şıkkı`} className="flex-1 px-2 py-1.5 rounded-lg border border-gray-200 text-sm outline-none focus:border-indigo-400" />
                    </div>
                  ))}
                  <div className="text-[11px] text-gray-400">Yeşil daire = doğru cevap. Görsel-seçenekli sorularda şıkları boş bırakıp gösterim "Görsel" seçin.</div>
                </div>

                <div className="flex gap-2">
                  <label className="text-xs text-gray-500 flex flex-col gap-1 flex-1">Konu
                    <input value={duzenle.konu || ""} onChange={(e) => setDuzenle((d) => ({ ...d, konu: e.target.value }))} placeholder="örn. Cümlede Anlam" className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm" />
                  </label>
                  <label className="text-xs text-gray-500 flex flex-col gap-1">Zorluk
                    <select value={duzenle.zorluk || ""} onChange={(e) => setDuzenle((d) => ({ ...d, zorluk: e.target.value || null }))} className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm">
                      <option value="">—</option>
                      {zorluklar.map((z) => <option key={z} value={z}>{z}</option>)}
                    </select>
                  </label>
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-gray-500">Çözüm Taktiği <span className="text-gray-400">(cevap anahtarı açılınca öğrenciye görünür)</span></label>
                    <button onClick={aiTaktikOner} disabled={aiYukleniyor}
                      className="text-[11px] px-2 py-1 rounded-lg border border-indigo-200 text-indigo-600 hover:bg-indigo-50 disabled:opacity-50">
                      {aiYukleniyor ? "AI…" : "🤖 AI ile öner"}
                    </button>
                  </div>
                  <textarea value={duzenle.cozumTaktigi || ""} onChange={(e) => setDuzenle((d) => ({ ...d, cozumTaktigi: e.target.value }))} rows={4}
                    placeholder="Bu tür sorularda önce…" className="w-full mt-1 px-3 py-2 rounded-xl border border-gray-200 text-sm outline-none focus:border-indigo-400" />
                </div>

                <div className="flex justify-end gap-2 pt-1">
                  <button onClick={() => setDuzenle(null)} className="px-4 py-2 rounded-xl border border-gray-200 text-sm">Kapat</button>
                  <button onClick={() => duzenleKaydet(true)} className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700">💾 Kaydet</button>
                  <button onClick={async () => { await duzenleKaydet(false); await yayinla(duzenle.id); setDuzenle(null); }}
                    className="px-4 py-2 rounded-xl bg-green-600 text-white text-sm font-semibold hover:bg-green-700">✅ Kaydet & Yayınla</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-[80] px-4 py-2 rounded-xl text-sm font-medium shadow-lg ${toast.tip === "ok" ? "bg-green-600 text-white" : "bg-red-600 text-white"}`}>
          {toast.metin}
        </div>
      )}
    </div>
  );
}
