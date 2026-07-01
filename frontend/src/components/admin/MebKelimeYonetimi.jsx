import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";

/**
 * MebKelimeYonetimi — yönetici MEB kelime listesi yönetimi.
 * Yükle (PDF/DOCX) → önizle → onayla → arka planda AI anlam/örnek üretir.
 * İstatistik + filtreli/sayfalı tablo + düzenleme + arşivleme.
 *
 * Props: apiBase — `${BACKEND_URL}/api`
 */
const SINIFLAR = [1, 2, 3, 4, 5, 6, 7, 8];
const DURUM_ETIKET = { aktif: "Aktif", onaysiz: "AI bekliyor", arsivli: "Arşivli" };
const ZORLUK_RENK = { kolay: "bg-green-100 text-green-700", orta: "bg-amber-100 text-amber-700", zor: "bg-red-100 text-red-700" };

export default function MebKelimeYonetimi({ apiBase }) {
  const [sinif, setSinif] = useState(1);
  const [dosya, setDosya] = useState(null);
  const [onizleme, setOnizleme] = useState(null); // {onizleme:[], toplam, dosya_adi, sinif}
  const [yukleniyor, setYukleniyor] = useState(false);
  const [onayIsleniyor, setOnayIsleniyor] = useState(false);
  const [toast, setToast] = useState(null);

  const [istatistik, setIstatistik] = useState(null);
  const [filtreSinif, setFiltreSinif] = useState("");
  const [filtreDurum, setFiltreDurum] = useState("aktif");
  const [arama, setArama] = useState("");
  const [sayfa, setSayfa] = useState(1);
  const [veri, setVeri] = useState({ kelimeler: [], toplam: 0, sayfa_sayisi: 1 });
  const [tabloYukleniyor, setTabloYukleniyor] = useState(false);
  const [duzenle, setDuzenle] = useState(null); // {id, kelime, anlam, ornek_cumle}

  const toastGoster = (tip, metin) => { setToast({ tip, metin }); setTimeout(() => setToast(null), 3500); };

  const listele = useCallback(async (gidilecek = sayfa) => {
    setTabloYukleniyor(true);
    try {
      const r = await axios.get(`${apiBase}/meb-kelime/liste`, {
        params: { sinif: filtreSinif || undefined, durum: filtreDurum, kelime: arama || undefined, sayfa: gidilecek, limit: 20 },
      });
      setVeri(r.data || { kelimeler: [], toplam: 0, sayfa_sayisi: 1 });
    } catch (e) {
      toastGoster("hata", "Liste yüklenemedi.");
    } finally { setTabloYukleniyor(false); }
  }, [apiBase, filtreSinif, filtreDurum, arama, sayfa]);

  const istatistikGetir = useCallback(async () => {
    try {
      const r = await axios.get(`${apiBase}/meb-kelime/istatistik`, { params: { sinif: filtreSinif || undefined } });
      setIstatistik(r.data);
    } catch { setIstatistik(null); }
  }, [apiBase, filtreSinif]);

  useEffect(() => { listele(sayfa); /* eslint-disable-next-line */ }, [sayfa, filtreDurum]);
  useEffect(() => { istatistikGetir(); /* eslint-disable-next-line */ }, [filtreSinif]);
  useEffect(() => { listele(1); istatistikGetir(); /* eslint-disable-next-line */ }, []);

  // ── Yükle → önizle ──
  const onizle = async () => {
    if (!dosya) { toastGoster("hata", "Önce dosya seçin."); return; }
    if (dosya.size > 5 * 1024 * 1024) { toastGoster("hata", "Dosya en fazla 5MB olabilir."); return; }
    const fd = new FormData();
    fd.append("dosya", dosya);
    fd.append("sinif", String(sinif));
    setYukleniyor(true);
    try {
      const r = await axios.post(`${apiBase}/meb-kelime/yukle`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setOnizleme(r.data);
    } catch (e) {
      toastGoster("hata", e?.response?.data?.detail || "Dosya işlenemedi.");
    } finally { setYukleniyor(false); }
  };

  const onizlemeKaldir = (k) => setOnizleme((o) => ({ ...o, onizleme: o.onizleme.filter((x) => x !== k) }));

  const onayla = async () => {
    if (!onizleme?.onizleme?.length) return;
    setOnayIsleniyor(true);
    try {
      const r = await axios.post(`${apiBase}/meb-kelime/onayla`, {
        kelimeler: onizleme.onizleme, sinif: onizleme.sinif, kaynak_dosya: onizleme.dosya_adi,
      });
      toastGoster("ok", `✅ ${r.data.yeni_eklenen} kelime eklendi, ${r.data.mevcut_atlanan} atlandı. AI üretimi arka planda başladı.`);
      setOnizleme(null); setDosya(null);
      setFiltreSinif(String(onizleme.sinif)); setSayfa(1);
      setTimeout(() => { listele(1); istatistikGetir(); }, 500);
    } catch (e) {
      toastGoster("hata", "Onaylama başarısız.");
    } finally { setOnayIsleniyor(false); }
  };

  const aiYenile = async () => {
    try {
      await axios.post(`${apiBase}/meb-kelime/toplu-ai-yenile`, filtreSinif ? { sinif: Number(filtreSinif) } : {});
      toastGoster("ok", "🔄 AI üretimi başlatıldı (bekleyen kelimeler için).");
    } catch { toastGoster("hata", "AI yenileme başlatılamadı."); }
  };

  const arsivle = async (id) => {
    if (!window.confirm("Bu kelimeyi arşivlemek istiyor musunuz?")) return;
    try { await axios.delete(`${apiBase}/meb-kelime/${id}`); listele(sayfa); istatistikGetir(); }
    catch { toastGoster("hata", "Arşivlenemedi."); }
  };

  const duzenleKaydet = async () => {
    try {
      await axios.put(`${apiBase}/meb-kelime/${duzenle.id}`, { anlam: duzenle.anlam, ornek_cumle: duzenle.ornek_cumle });
      setDuzenle(null); listele(sayfa); toastGoster("ok", "✅ Güncellendi");
    } catch { toastGoster("hata", "Güncellenemedi."); }
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-bold text-gray-800">📖 MEB Kelimeleri</h3>
        <p className="text-sm text-gray-500">Sınıf bazlı MEB kelime listelerini yükleyin; kelimeler tüm kelime egzersizlerinde önceliklidir.</p>
      </div>

      {/* ── Yükleme kartı ── */}
      <div className="bg-white rounded-2xl border shadow-sm p-5 space-y-3">
        <div className="font-semibold text-gray-700">📄 Yeni MEB Kelime Listesi Yükle</div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-gray-600 flex flex-col gap-1">Sınıf
            <select value={sinif} onChange={(e) => setSinif(Number(e.target.value))}
              className="px-3 py-2 rounded-xl border border-gray-200 text-sm">
              {SINIFLAR.map((s) => <option key={s} value={s}>{s}. sınıf</option>)}
            </select>
          </label>
          <label className="text-xs text-gray-600 flex flex-col gap-1">Dosya (PDF/DOCX, max 5MB)
            <input type="file" accept=".pdf,.docx" onChange={(e) => setDosya(e.target.files?.[0] || null)}
              className="text-sm" />
          </label>
          <button onClick={onizle} disabled={yukleniyor || !dosya}
            className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50">
            {yukleniyor ? "İşleniyor…" : "🔍 Önizle"}
          </button>
        </div>
      </div>

      {/* ── İstatistik ── */}
      {istatistik && (
        <div className="bg-indigo-50 border border-indigo-100 rounded-2xl px-4 py-3 text-sm text-indigo-800 flex flex-wrap gap-x-6 gap-y-1">
          <span>📊 {filtreSinif ? `${filtreSinif}. sınıf` : "Tümü"}: <b>{istatistik.toplam_kelime}</b> kelime</span>
          <span>✅ <b>{istatistik.ai_uretimi_tamamlanan}</b> AI hazır</span>
          <span>⏳ <b>{istatistik.ai_bekleyen}</b> bekliyor</span>
          {istatistik.ai_bekleyen > 0 && (
            <button onClick={aiYenile} className="ml-auto text-indigo-600 underline text-xs">🔄 Bekleyenler için AI üret</button>
          )}
        </div>
      )}

      {/* ── Filtreler ── */}
      <div className="flex flex-wrap items-end gap-2 bg-white rounded-2xl border p-3 shadow-sm">
        <label className="text-xs text-gray-600 flex flex-col gap-1">Sınıf
          <select value={filtreSinif} onChange={(e) => { setFiltreSinif(e.target.value); setSayfa(1); }}
            className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm">
            <option value="">Tümü</option>
            {SINIFLAR.map((s) => <option key={s} value={s}>{s}. sınıf</option>)}
          </select>
        </label>
        <label className="text-xs text-gray-600 flex flex-col gap-1">Durum
          <select value={filtreDurum} onChange={(e) => { setFiltreDurum(e.target.value); setSayfa(1); }}
            className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm">
            <option value="aktif">Aktif</option>
            <option value="onaysiz">AI bekleyen</option>
            <option value="arsivli">Arşivli</option>
            <option value="hepsi">Hepsi</option>
          </select>
        </label>
        <label className="text-xs text-gray-600 flex flex-col gap-1">Ara
          <input value={arama} onChange={(e) => setArama(e.target.value)} placeholder="kelime…"
            onKeyDown={(e) => { if (e.key === "Enter") { setSayfa(1); listele(1); } }}
            className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm" />
        </label>
        <button onClick={() => { setSayfa(1); listele(1); }}
          className="px-4 py-2 rounded-xl bg-gray-800 text-white text-sm font-medium">Ara</button>
        <span className="text-xs text-gray-400 ml-auto self-center">{veri.toplam} kelime</span>
      </div>

      {/* ── Tablo ── */}
      <div className="bg-white rounded-2xl border shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400 border-b">
              <th className="px-3 py-2 font-semibold">Kelime</th>
              <th className="px-3 py-2 font-semibold">Sınıf</th>
              <th className="px-3 py-2 font-semibold">Anlam (AI)</th>
              <th className="px-3 py-2 font-semibold">Örnek</th>
              <th className="px-3 py-2 font-semibold">Zorluk</th>
              <th className="px-3 py-2 font-semibold text-center">Kullanım</th>
              <th className="px-3 py-2 font-semibold">Durum</th>
              <th className="px-3 py-2 font-semibold text-right">İşlem</th>
            </tr>
          </thead>
          <tbody>
            {tabloYukleniyor ? (
              <tr><td colSpan={8} className="px-3 py-10 text-center text-gray-400">Yükleniyor…</td></tr>
            ) : veri.kelimeler.length === 0 ? (
              <tr><td colSpan={8} className="px-3 py-10 text-center text-gray-400">Kelime bulunamadı.</td></tr>
            ) : veri.kelimeler.map((k) => (
              <tr key={k.id} className={`border-b border-gray-50 hover:bg-gray-50/60 ${k.durum === "arsivli" ? "opacity-50" : ""}`}>
                <td className="px-3 py-2 font-semibold text-gray-800">{k.kelime}</td>
                <td className="px-3 py-2">{k.sinif}</td>
                <td className="px-3 py-2 max-w-[16rem]"><span className="line-clamp-2 text-gray-600">{k.anlam || <span className="text-gray-300">—</span>}</span></td>
                <td className="px-3 py-2 max-w-[16rem]"><span className="line-clamp-2 text-gray-500 italic">{k.ornek_cumle || ""}</span></td>
                <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded-full ${ZORLUK_RENK[k.zorluk] || "bg-gray-100 text-gray-500"}`}>{k.zorluk || "—"}</span></td>
                <td className="px-3 py-2 text-center">{k.kullanim_sayisi || 0}</td>
                <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded-full ${k.durum === "aktif" ? "bg-green-100 text-green-700" : k.durum === "onaysiz" ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-500"}`}>{DURUM_ETIKET[k.durum] || k.durum}</span></td>
                <td className="px-3 py-2">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => setDuzenle({ id: k.id, kelime: k.kelime, anlam: k.anlam || "", ornek_cumle: k.ornek_cumle || "" })}
                      title="Düzenle" className="px-2 py-1 rounded-lg text-xs border border-gray-200 hover:bg-gray-100">✏️</button>
                    {k.durum !== "arsivli" && (
                      <button onClick={() => arsivle(k.id)} title="Arşivle"
                        className="px-2 py-1 rounded-lg text-xs border border-amber-200 text-amber-600 hover:bg-amber-50">🗑</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Sayfalama ── */}
      {veri.sayfa_sayisi > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button disabled={sayfa <= 1} onClick={() => setSayfa((s) => Math.max(1, s - 1))}
            className="px-3 py-1.5 rounded-lg border border-gray-200 disabled:opacity-40">← Önceki</button>
          <span className="text-gray-500">{sayfa} / {veri.sayfa_sayisi}</span>
          <button disabled={sayfa >= veri.sayfa_sayisi} onClick={() => setSayfa((s) => s + 1)}
            className="px-3 py-1.5 rounded-lg border border-gray-200 disabled:opacity-40">Sonraki →</button>
        </div>
      )}

      {/* ── Önizleme modalı ── */}
      {onizleme && (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4" onClick={() => setOnizleme(null)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[88vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-3 border-b sticky top-0 bg-white rounded-t-2xl">
              <div className="font-bold text-gray-800">Bulunan Kelimeler ({onizleme.onizleme.length} adet) • {onizleme.sinif}. sınıf</div>
              <div className="text-xs text-gray-400">{onizleme.dosya_adi}</div>
            </div>
            <div className="p-5 space-y-4">
              <div className="flex flex-wrap gap-1.5 max-h-72 overflow-y-auto">
                {onizleme.onizleme.map((k) => (
                  <span key={k} className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-100 text-sm text-gray-700">
                    {k}
                    <button onClick={() => onizlemeKaldir(k)} className="text-gray-400 hover:text-red-500">✕</button>
                  </span>
                ))}
              </div>
              <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                ⚠️ Sonraki adımda AI her kelime için anlam ve örnek cümle üretecek. Bu birkaç dakika sürebilir (arka planda çalışır).
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setOnizleme(null)} className="px-4 py-2 rounded-xl border border-gray-200 text-sm">İptal</button>
                <button onClick={onayla} disabled={onayIsleniyor || onizleme.onizleme.length === 0}
                  className="px-4 py-2 rounded-xl bg-green-600 text-white text-sm font-semibold hover:bg-green-700 disabled:opacity-50">
                  {onayIsleniyor ? "Kaydediliyor…" : "✅ Onayla ve AI Üretimini Başlat"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Düzenle modalı ── */}
      {duzenle && (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4" onClick={() => setDuzenle(null)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-3 border-b font-bold text-gray-800">✏️ {duzenle.kelime}</div>
            <div className="p-5 space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-500">Anlam</label>
                <textarea value={duzenle.anlam} onChange={(e) => setDuzenle((d) => ({ ...d, anlam: e.target.value }))} rows={2}
                  className="w-full mt-1 px-3 py-2 rounded-xl border border-gray-200 text-sm outline-none focus:border-indigo-400" />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500">Örnek Cümle</label>
                <textarea value={duzenle.ornek_cumle} onChange={(e) => setDuzenle((d) => ({ ...d, ornek_cumle: e.target.value }))} rows={2}
                  className="w-full mt-1 px-3 py-2 rounded-xl border border-gray-200 text-sm outline-none focus:border-indigo-400" />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setDuzenle(null)} className="px-4 py-2 rounded-xl border border-gray-200 text-sm">İptal</button>
                <button onClick={duzenleKaydet} className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700">Kaydet</button>
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
