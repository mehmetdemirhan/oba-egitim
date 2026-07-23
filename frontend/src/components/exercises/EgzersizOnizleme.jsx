import React, { useEffect, useState } from "react";
import axios from "axios";
import { getRenderComponent } from "./types";

/**
 * EgzersizOnizleme — bir egzersizi ÖĞRENCİNİN GERÇEKTEN GÖRDÜĞÜ aynı render bileşeniyle
 * (getRenderComponent → AnagramRender/SecmeliRender/HafizaKartiRender…) gösterir. Ayrı bir
 * "özet gösterim" YOKTUR; öğrenci-facing bileşen doğrudan yeniden kullanılır.
 *
 * `onizleme: true` bayrağıyla bir oturum başlatılır → kullanım sayacı artmaz, /bitir'de
 * XP/skor YAZILMAZ. onCevap gerçek motora gider (doğru cevabı vurgulayabilmek için —
 * öğretmenin "doğru cevap gerçekten doğru mu?" kalite kontrolü yapabilmesi için önemli).
 */
export default function EgzersizOnizleme({ apiBase, tip, sinif, icerikId }) {
  const [oturum, setOturum] = useState(null);
  const [soruNo, setSoruNo] = useState(0);
  const [cevaplandi, setCevaplandi] = useState(false);
  const [hata, setHata] = useState(null);

  useEffect(() => {
    let iptal = false;
    setOturum(null); setSoruNo(0); setCevaplandi(false); setHata(null);
    axios.post(`${apiBase}/egzersiz/oturum`, { tip, sinif, icerik_id: icerikId, onizleme: true })
      .then((r) => { if (!iptal) setOturum(r.data); })
      .catch(() => { if (!iptal) setHata("Önizleme başlatılamadı."); });
    return () => { iptal = true; };
  }, [apiBase, tip, sinif, icerikId]);

  const onCevap = async (cevap) => {
    if (!oturum) return { dogru: false, dogru_cevap: null };
    try {
      const r = await axios.post(`${apiBase}/egzersiz/oturum/${oturum.oturum_id || oturum.id}/cevap`, { soru_no: soruNo, cevap });
      setCevaplandi(true);
      return r.data;
    } catch { setCevaplandi(true); return { dogru: false, dogru_cevap: null }; }
  };

  const toplam = oturum?.toplam_soru || 1;
  const sonSoru = soruNo + 1 >= toplam;
  const sonraki = () => { if (!sonSoru) { setSoruNo((n) => n + 1); setCevaplandi(false); } };

  if (hata) return <div className="text-center py-8 text-red-500 text-sm">{hata}</div>;
  if (!oturum) return <div className="text-center py-8 text-subtle text-sm">Önizleme hazırlanıyor…</div>;

  const Render = getRenderComponent(oturum.tip || tip);
  if (!Render) return <div className="text-center py-6 text-subtle text-sm">Bu türün önizleme görünümü yok ({tip}).</div>;

  return (
    <div className="space-y-3">
      {toplam > 1 && (
        <div className="flex items-center justify-end text-[11px] text-subtle">Soru {Math.min(soruNo + 1, toplam)}/{toplam}</div>
      )}
      <Render icerik={oturum.icerik} onCevap={onCevap} soruNo={soruNo} ilerleme={{ mevcut: soruNo + 1, toplam }} />
      {cevaplandi && !sonSoru && (
        <div className="flex justify-end">
          <button onClick={sonraki} className="px-4 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700">Sonraki soru →</button>
        </div>
      )}
    </div>
  );
}
