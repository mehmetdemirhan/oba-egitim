import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";

/**
 * SinavCozum — öğrenci sınav çözüm ekranı (tam-ekran overlay).
 * Sorular sırayla; gösterim "gorsel" ise orijinal kırpım (blob), "metin" ise
 * dizgi + A-D. HER cevaptan HEMEN SONRA cevap anahtarı açılır: doğru vurgulanır,
 * altında çözüm taktiği görünür (özelliğin çekirdeği). Bitince görev tamamlanır.
 *
 * Props: apiBase, odevId, gorevId, onClose(), onComplete(gorevId)
 */
function SoruGorsel({ apiBase, soruId }) {
  const [url, setUrl] = useState(null);
  const [hata, setHata] = useState(false);
  useEffect(() => {
    let aktif = true; let objUrl = null;
    setUrl(null); setHata(false);
    axios.get(`${apiBase}/sinav/soru/${soruId}/gorsel`, { responseType: "blob" })
      .then((r) => { if (!aktif) return; objUrl = URL.createObjectURL(r.data); setUrl(objUrl); })
      .catch(() => aktif && setHata(true));
    return () => { aktif = false; if (objUrl) URL.revokeObjectURL(objUrl); };
  }, [apiBase, soruId]);
  if (hata) return <div className="text-sm text-red-400 p-6 text-center">Soru görseli yüklenemedi.</div>;
  if (!url) return <div className="text-sm text-gray-400 p-6 text-center">Soru yükleniyor…</div>;
  return <img src={url} alt="Soru" className="w-full h-auto rounded-xl border" />;
}

const SIKLAR = ["A", "B", "C", "D"];

export default function SinavCozum({ apiBase, odevId, gorevId, onClose, onComplete }) {
  const [sorular, setSorular] = useState([]);
  const [odevAd, setOdevAd] = useState("");
  const [idx, setIdx] = useState(0);
  const [cevaplar, setCevaplar] = useState({}); // soruId → {verilen, dogruMu, dogruCevap, cozumTaktigi}
  const [yukleniyor, setYukleniyor] = useState(true);
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [bitti, setBitti] = useState(false);
  const [hata, setHata] = useState("");

  useEffect(() => {
    let aktif = true;
    axios.get(`${apiBase}/sinav/odev/${odevId}/sorular`)
      .then((r) => {
        if (!aktif) return;
        setSorular(r.data?.sorular || []);
        setOdevAd(r.data?.odev?.ad || "Sınav");
      })
      .catch((e) => aktif && setHata(e?.response?.data?.detail || "Sınav yüklenemedi."))
      .finally(() => aktif && setYukleniyor(false));
    return () => { aktif = false; };
  }, [apiBase, odevId]);

  const soru = sorular[idx];
  const mevcutCevap = soru ? cevaplar[soru.id] : null;

  const cevapVer = useCallback(async (harf) => {
    if (!soru || cevaplar[soru.id] || gonderiliyor) return;
    setGonderiliyor(true);
    try {
      const r = await axios.post(`${apiBase}/sinav/cevap`, { odevId, soruId: soru.id, verilenCevap: harf });
      setCevaplar((c) => ({ ...c, [soru.id]: { verilen: harf, dogruMu: r.data.dogruMu, dogruCevap: r.data.dogruCevap, cozumTaktigi: r.data.cozumTaktigi } }));
    } catch (e) {
      setHata(e?.response?.data?.detail || "Cevap kaydedilemedi.");
    } finally { setGonderiliyor(false); }
  }, [apiBase, odevId, soru, cevaplar, gonderiliyor]);

  const dogruSayisi = Object.values(cevaplar).filter((c) => c.dogruMu).length;
  const cevaplananSayisi = Object.keys(cevaplar).length;

  // ── Bitiş ekranı ──
  if (bitti) {
    const yuzde = sorular.length ? Math.round((dogruSayisi / sorular.length) * 100) : 0;
    return (
      <div className="fixed inset-0 z-[100] bg-white overflow-y-auto flex items-center justify-center p-6">
        <div className="w-full max-w-md text-center space-y-4">
          <div className="text-6xl">{yuzde >= 70 ? "🎉" : yuzde >= 40 ? "👍" : "💪"}</div>
          <h2 className="text-2xl font-bold text-gray-800">Sınav Tamamlandı!</h2>
          <div className="text-gray-600">{odevAd}</div>
          <div className="bg-indigo-50 rounded-2xl p-5 border border-indigo-100">
            <div className="text-4xl font-bold text-indigo-600">{dogruSayisi} / {sorular.length}</div>
            <div className="text-sm text-indigo-500 mt-1">%{yuzde} doğru</div>
          </div>
          <button onClick={() => { onComplete && onComplete(gorevId); }}
            className="w-full px-4 py-3 rounded-xl bg-green-600 text-white font-semibold hover:bg-green-700">
            Bitir ve Görevi Tamamla
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[100] bg-white overflow-y-auto">
      {/* Üst bar */}
      <div className="sticky top-0 bg-white/95 backdrop-blur border-b z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-sm">✕ Çıkış</button>
          <div className="flex-1">
            <div className="text-xs text-gray-500 mb-1 flex justify-between">
              <span className="font-semibold truncate">{odevAd}</span>
              <span>{sorular.length ? idx + 1 : 0} / {sorular.length} • ✅ {dogruSayisi}</span>
            </div>
            <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
              <div className="h-full bg-indigo-500 transition-all" style={{ width: `${sorular.length ? ((idx + 1) / sorular.length) * 100 : 0}%` }} />
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-5 space-y-4">
        {yukleniyor ? (
          <div className="text-center text-gray-400 py-16">Sınav yükleniyor…</div>
        ) : hata ? (
          <div className="text-center text-red-500 py-16">{hata}<div className="mt-4"><button onClick={onClose} className="px-4 py-2 rounded-xl border">Kapat</button></div></div>
        ) : !soru ? (
          <div className="text-center text-gray-400 py-16">Bu sınavda soru yok.<div className="mt-4"><button onClick={onClose} className="px-4 py-2 rounded-xl border">Kapat</button></div></div>
        ) : (
          <>
            {/* Soru */}
            <div className="bg-white rounded-2xl border shadow-sm p-4">
              <div className="text-[11px] font-semibold text-indigo-500 uppercase tracking-wide mb-2">
                {soru.konu || `${idx + 1}. Soru`}
              </div>
              {soru.gosterimTuru === "gorsel" ? (
                <SoruGorsel apiBase={apiBase} soruId={soru.id} />
              ) : (
                <div className="whitespace-pre-line text-gray-800 text-[15px] leading-relaxed">{soru.soruMetni}</div>
              )}
            </div>

            {/* Şıklar */}
            <div className="space-y-2">
              {SIKLAR.map((h) => {
                const secili = mevcutCevap?.verilen === h;
                const dogru = mevcutCevap && mevcutCevap.dogruCevap === h;
                let renk = "border-gray-200 bg-white hover:border-indigo-300";
                if (mevcutCevap) {
                  if (dogru) renk = "border-green-500 bg-green-50";
                  else if (secili) renk = "border-red-400 bg-red-50";
                  else renk = "border-gray-200 bg-white opacity-70";
                }
                const metinModu = soru.gosterimTuru !== "gorsel" && soru.secenekler?.[h];
                return (
                  <button key={h} onClick={() => cevapVer(h)} disabled={!!mevcutCevap || gonderiliyor}
                    className={`w-full text-left flex items-center gap-3 px-4 py-3 rounded-xl border transition-all ${renk} disabled:cursor-default`}>
                    <span className={`w-8 h-8 shrink-0 rounded-full flex items-center justify-center text-sm font-bold ${dogru ? "bg-green-600 text-white" : secili ? "bg-red-500 text-white" : "bg-gray-100 text-gray-600"}`}>{h}</span>
                    {metinModu ? <span className="text-sm text-gray-700">{soru.secenekler[h]}</span> : <span className="text-sm text-gray-400">Seçenek {h}</span>}
                    {dogru && <span className="ml-auto text-green-600 text-sm">✓</span>}
                    {secili && !dogru && <span className="ml-auto text-red-500 text-sm">✗</span>}
                  </button>
                );
              })}
            </div>

            {/* Cevap anahtarı + çözüm taktiği (cevaptan hemen sonra) */}
            {mevcutCevap && (
              <div className="space-y-3">
                <div className={`rounded-xl px-4 py-3 text-sm font-medium ${mevcutCevap.dogruMu ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                  {mevcutCevap.dogruMu ? "✅ Doğru!" : `❌ Yanlış — Doğru cevap: ${mevcutCevap.dogruCevap}`}
                </div>
                {mevcutCevap.cozumTaktigi && (
                  <div className="rounded-xl px-4 py-3 bg-indigo-50 border border-indigo-100">
                    <div className="text-[11px] font-bold text-indigo-500 uppercase tracking-wide mb-1">💡 Çözüm Taktiği</div>
                    <div className="text-sm text-indigo-900 whitespace-pre-line leading-relaxed">{mevcutCevap.cozumTaktigi}</div>
                  </div>
                )}
                <div className="flex justify-end">
                  {idx + 1 < sorular.length ? (
                    <button onClick={() => setIdx((i) => i + 1)} className="px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700">Sonraki Soru →</button>
                  ) : (
                    <button onClick={() => setBitti(true)} className="px-5 py-2.5 rounded-xl bg-green-600 text-white text-sm font-semibold hover:bg-green-700">Sınavı Bitir ✓</button>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
