import React, { useState } from "react";
import axios from "axios";
import { ThumbsUp, ThumbsDown, Check } from "lucide-react";

/**
 * GeriBildirimWidget — her AI çıktısının altına 👍/👎 + opsiyonel "neden yanlıştı/eksikti" (FAZ 4, madde 12).
 * Kayıt: POST /ai/ceo/geri-bildirim {ajan, kaynak_id, kaynak_tur, puan, duzeltme_metni, kategori}.
 * Olumsuz'da düzeltme metni kutusu açılır (opsiyonel). Gönderildikten sonra teşekkür gösterir.
 */
export default function GeriBildirimWidget({ apiBase, ajan, kaynakId, kaynakTur, kategori }) {
  const [puan, setPuan] = useState(null);      // "olumlu" | "olumsuz"
  const [metin, setMetin] = useState("");
  const [gonderildi, setGonderildi] = useState(false);
  const [acik, setAcik] = useState(false);

  const gonder = async (secilenPuan, duzeltme = "") => {
    try {
      await axios.post(`${apiBase}/ai/ceo/geri-bildirim`, {
        ajan, kaynak_id: kaynakId, kaynak_tur: kaynakTur, kategori,
        puan: secilenPuan, duzeltme_metni: duzeltme,
      });
      setGonderildi(true);
    } catch (e) { /* sessiz — geri bildirim kritik yol değil */ }
  };

  const tikla = (p) => {
    setPuan(p);
    if (p === "olumsuz") { setAcik(true); }
    else { gonder("olumlu"); }
  };

  if (gonderildi) return (
    <div className="mt-1.5 text-[10px] text-emerald-700 inline-flex items-center gap-1"><Check className="h-3 w-3" />Geri bildirim için teşekkürler.</div>
  );

  return (
    <div className="mt-1.5">
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-subtle">Yararlı mıydı?</span>
        <button onClick={() => tikla("olumlu")} title="Olumlu"
          className={`p-1 rounded border ${puan === "olumlu" ? "bg-emerald-50 border-emerald-300 text-emerald-700" : "border-line text-subtle hover:text-emerald-600"}`}>
          <ThumbsUp className="h-3 w-3" />
        </button>
        <button onClick={() => tikla("olumsuz")} title="Olumsuz"
          className={`p-1 rounded border ${puan === "olumsuz" ? "bg-rose-50 border-rose-300 text-rose-700" : "border-line text-subtle hover:text-rose-600"}`}>
          <ThumbsDown className="h-3 w-3" />
        </button>
      </div>
      {acik && (
        <div className="mt-1.5 flex gap-1.5">
          <input value={metin} onChange={(e) => setMetin(e.target.value)} placeholder="(opsiyonel) neden yanlıştı/eksikti?"
            className="flex-1 bg-app border border-line rounded px-2 py-1 text-[11px] text-content outline-none focus:border-primary/40" />
          <button onClick={() => gonder("olumsuz", metin)} className="text-[11px] bg-primary text-white rounded px-2 py-1">Gönder</button>
        </div>
      )}
    </div>
  );
}
