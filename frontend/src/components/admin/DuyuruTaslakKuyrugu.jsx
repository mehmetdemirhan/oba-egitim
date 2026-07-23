import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Sparkles, RefreshCw, Check, X, ScanLine } from "lucide-react";

/**
 * DuyuruTaslakKuyrugu — "Yeni Ne Var" otomasyon ajanının ürettiği changelog
 * taslaklarının admin onay kuyruğu (metin öneri kuyruğu deseniyle tutarlı).
 * Admin düzenleyebilir, onaylayabilir (→ Yeni Ne Var'da yayınlanır) veya reddedebilir.
 * "Şimdi Tara" ile 24 saatlik döngü beklenmeden git geçmişi taranır.
 */
export default function DuyuruTaslakKuyrugu({ apiBase, toast }) {
  const [liste, setListe] = useState([]);
  const [yuk, setYuk] = useState(false);
  const [tara, setTara] = useState(false);
  const [duzen, setDuzen] = useState({}); // id → {baslik, icerik}

  const yukle = useCallback(async () => {
    setYuk(true);
    try {
      const r = await axios.get(`${apiBase}/duyuru-taslak`);
      setListe(r.data.taslaklar || []);
      const d = {}; (r.data.taslaklar || []).forEach((t) => { d[t.id] = { baslik: t.baslik || "", icerik: t.icerik || "" }; });
      setDuzen(d);
    } catch (e) { setListe([]); } finally { setYuk(false); }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  const simdiTara = async () => {
    setTara(true);
    try {
      const r = await axios.post(`${apiBase}/duyuru-taslak/tara`);
      const d = r.data;
      const ozet = `${d.taranan_commit} commit · ${d.teknik_elenen} teknik elendi · ${d.aday} aday · ${d.olusan_taslak} taslak${d.ai_durum && d.ai_durum !== "ok" ? ` · AI: ${d.ai_durum}` : ""}${d.hata ? ` · ⚠ ${d.hata}` : ""}`;
      toast({ title: d.olusan_taslak > 0 ? `🔎 ${d.olusan_taslak} yeni taslak` : "🔎 Tarama tamam (yeni taslak yok)", description: ozet });
      yukle();
    } catch (e) { toast({ title: "Tarama başarısız", description: e?.response?.data?.detail || "GitHub/AI erişimi gerekli", variant: "destructive" }); }
    finally { setTara(false); }
  };
  const onayla = async (id) => {
    try { await axios.post(`${apiBase}/duyuru-taslak/${id}/onayla`, duzen[id] || {}); toast({ title: "✅ Yayınlandı", description: "Yeni Ne Var bölümüne eklendi." }); yukle(); }
    catch (e) { toast({ title: "Onaylanamadı", variant: "destructive" }); }
  };
  const reddet = async (id) => {
    try { await axios.post(`${apiBase}/duyuru-taslak/${id}/reddet`); toast({ title: "Reddedildi" }); yukle(); }
    catch (e) { toast({ title: "İşlem başarısız", variant: "destructive" }); }
  };
  const alan = (id, k, v) => setDuzen((d) => ({ ...d, [id]: { ...(d[id] || {}), [k]: v } }));

  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="h-5 w-5 text-primary" />
        <div>
          <div className="font-semibold text-content">Yeni Ne Var — Otomatik Taslaklar</div>
          <div className="text-xs text-subtle">Ajan, git geçmişindeki kullanıcıya görünür değişiklikleri changelog taslağına çevirir. Onaylayınca yayınlanır.</div>
        </div>
        <div className="ml-auto flex gap-2">
          <button onClick={yukle} disabled={yuk} className="inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-2.5 py-1.5 text-xs"><RefreshCw className={`h-3.5 w-3.5 ${yuk ? "animate-spin" : ""}`} />Yenile</button>
          <button onClick={simdiTara} disabled={tara} className="inline-flex items-center gap-1.5 bg-primary text-white rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-50"><ScanLine className={`h-3.5 w-3.5 ${tara ? "animate-pulse" : ""}`} />{tara ? "Taranıyor…" : "Şimdi Tara"}</button>
        </div>
      </div>

      {liste.length === 0 ? (
        <div className="text-center text-sm text-subtle py-8">Onay bekleyen taslak yok. "Şimdi Tara" ile yeni değişiklikleri tarayabilirsiniz.</div>
      ) : (
        <div className="space-y-3">
          {liste.map((t) => (
            <div key={t.id} className="rounded-xl border border-line p-3 bg-app/40">
              <input value={(duzen[t.id] || {}).baslik || ""} onChange={(e) => alan(t.id, "baslik", e.target.value)}
                className="w-full px-2 py-1.5 rounded-lg border border-line text-sm font-semibold mb-2" placeholder="Başlık" />
              <textarea value={(duzen[t.id] || {}).icerik || ""} onChange={(e) => alan(t.id, "icerik", e.target.value)} rows={2}
                className="w-full px-2 py-1.5 rounded-lg border border-line text-sm" placeholder="İçerik" />
              <div className="flex items-center gap-2 mt-2">
                <span className="text-[10px] text-subtle bg-app rounded px-1.5 py-0.5">🤖 ajan · {t.tarih}</span>
                <div className="ml-auto flex gap-2">
                  <button onClick={() => reddet(t.id)} className="inline-flex items-center gap-1 text-red-600 border border-red-200 rounded-lg px-2.5 py-1 text-xs hover:bg-red-50"><X className="h-3.5 w-3.5" />Reddet</button>
                  <button onClick={() => onayla(t.id)} className="inline-flex items-center gap-1 bg-green-600 text-white rounded-lg px-3 py-1 text-xs font-semibold hover:bg-green-700"><Check className="h-3.5 w-3.5" />Onayla & Yayınla</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
