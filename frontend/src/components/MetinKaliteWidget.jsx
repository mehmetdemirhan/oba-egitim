import React, { useState, useEffect } from "react";
import axios from "axios";
import { Star, Check, Sparkles } from "lucide-react";

/**
 * MetinKaliteWidget — öğretmen bir metni kullandıktan sonra 1-5 yıldız kalite puanı verir.
 * FARKLI metne İLK puanda XP kazanır (anti-farm). Çok kötü (ort<2 & oy≥2) metinler admin denetimine düşer.
 * apiBase = `${BACKEND}/api`. Uçlar: /metin-kalite/geri-bildirim, /metin-kalite/durum/{id}.
 */
export default function MetinKaliteWidget({ apiBase, metinId, metinBaslik, onDone }) {
  const [yildiz, setYildiz] = useState(0);
  const [hover, setHover] = useState(0);
  const [yorum, setYorum] = useState("");
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [sonuc, setSonuc] = useState(null); // {xp_kazanildi, ilk_mi}

  useEffect(() => {
    // Öğretmen bu metni daha önce puanladıysa ön-doldur (güncelleyebilir)
    let iptal = false;
    axios.get(`${apiBase}/metin-kalite/durum/${metinId}`)
      .then((r) => { if (!iptal && r.data?.benim) { setYildiz(r.data.benim.yildiz || 0); setYorum(r.data.benim.yorum || ""); } })
      .catch(() => {});
    return () => { iptal = true; };
  }, [apiBase, metinId]);

  const gonder = async () => {
    if (!yildiz || gonderiliyor) return;
    setGonderiliyor(true);
    try {
      const r = await axios.post(`${apiBase}/metin-kalite/geri-bildirim`, { metin_id: metinId, yildiz, yorum });
      setSonuc(r.data);
    } catch (e) { /* sessiz — kritik yol değil */ } finally { setGonderiliyor(false); }
  };

  if (sonuc) return (
    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800 flex items-center gap-2">
      <Check className="h-4 w-4" />
      Kalite geri bildirimin kaydedildi.
      {sonuc.xp_kazanildi > 0
        ? <span className="inline-flex items-center gap-1 font-semibold"><Sparkles className="h-4 w-4" />+{sonuc.xp_kazanildi} XP</span>
        : <span className="text-emerald-600">(bu metni daha önce puanlamıştın — güncellendi)</span>}
      {onDone && <button onClick={onDone} className="ml-auto text-xs underline">Kapat</button>}
    </div>
  );

  const etiket = ["", "Çok kötü", "Kötü", "Orta", "İyi", "Çok iyi"][hover || yildiz] || "";
  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
      <div className="flex items-center gap-2 mb-1">
        <Star className="h-4 w-4 text-amber-500" />
        <div className="font-semibold text-content text-sm">Bu metnin kalitesini puanla</div>
        <span className="text-[11px] text-subtle ml-auto">+XP kazan · içerik kalitesini denetle</span>
      </div>
      {metinBaslik && <div className="text-xs text-subtle mb-2">“{metinBaslik}”</div>}
      <div className="flex items-center gap-1 mb-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(0)} onClick={() => setYildiz(n)}
            className="p-0.5" title={`${n} yıldız`}>
            <Star className={`h-7 w-7 transition-colors ${(hover || yildiz) >= n ? "fill-amber-400 text-amber-400" : "text-slate-300"}`} />
          </button>
        ))}
        <span className="text-xs text-subtle ml-2 w-16">{etiket}</span>
      </div>
      <input value={yorum} onChange={(e) => setYorum(e.target.value)} placeholder="(opsiyonel) neden bu puanı verdin?"
        className="w-full bg-surface border border-line rounded-lg px-2.5 py-1.5 text-sm text-content outline-none focus:border-amber-400 mb-2" />
      <div className="flex items-center gap-2">
        <button onClick={gonder} disabled={!yildiz || gonderiliyor}
          className="inline-flex items-center gap-1.5 bg-amber-500 disabled:opacity-50 text-white text-sm rounded-lg px-4 py-1.5 font-medium">
          {gonderiliyor ? "Gönderiliyor…" : "Puanı Gönder"}
        </button>
        {onDone && <button onClick={onDone} className="text-xs text-subtle underline">Şimdi değil</button>}
      </div>
    </div>
  );
}
