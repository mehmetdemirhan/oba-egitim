// Hızlı Okuma egzersizleri ortak yardımcıları.
// Metin kaynağı: Analiz havuzu (yeni 150 Akıcı Okuma metni). GET /diagnostic/texts
// bolum='analiz' (okuma_parcalari hariç) döner; rastgele, yeterince uzun bir metin seçilir.
import { useCallback, useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function kelimelereBol(icerik) {
  return (icerik || "").trim().split(/\s+/).filter(Boolean);
}

// Kelimeleri N'li gruplara böl → [["a","b"],["c","d"],...]
export function gruplara(kelimeler, boyut) {
  const g = [];
  for (let i = 0; i < kelimeler.length; i += boyut) g.push(kelimeler.slice(i, i + boyut));
  return g;
}

// Analiz havuzundan (onaylanmış 150 Akıcı Okuma metni) okuma metni getirir.
// Kullanıcı isterse listeden SEÇER (sec), isterse rastgele yeniler (yenile).
// Dönüş: { metin, liste, sec, yukleniyor, hata, yenile }
export function useOkumaMetni(minKelime = 40) {
  const [metin, setMetin] = useState(null);
  const [liste, setListe] = useState([]);      // seçilebilir onaylı metinler (dropdown için)
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState("");

  const yenile = useCallback(async () => {
    setYukleniyor(true); setHata("");
    try {
      const r = await axios.get(`${API}/diagnostic/texts`, { params: { bolum: "analiz" } });
      const tumu = Array.isArray(r.data) ? r.data.filter((m) => m?.icerik) : [];
      if (!tumu.length) { setHata("Havuzda okuma metni bulunamadı. Yönetici 'Akıcı Okuma metinlerini yükle' ile ekleyebilir."); setMetin(null); setListe([]); return; }
      const uygun = tumu.filter((m) => kelimelereBol(m.icerik).length >= minKelime);
      const havuz = uygun.length ? uygun : tumu;
      setListe(havuz);
      // Varsayılan: rastgele bir metin (kullanıcı listeden değiştirebilir)
      setMetin(havuz[Math.floor(Math.random() * havuz.length)]);
    } catch (e) {
      setHata(e?.response?.data?.detail || "Metin yüklenemedi.");
      setMetin(null); setListe([]);
    } finally {
      setYukleniyor(false);
    }
  }, [minKelime]);

  useEffect(() => { yenile(); }, [yenile]);

  // Kullanıcının listeden seçtiği metne geç (id ile)
  const sec = useCallback((id) => {
    setListe((mevcut) => {
      const bulunan = mevcut.find((m) => m.id === id);
      if (bulunan) setMetin(bulunan);
      return mevcut;
    });
  }, []);

  return { metin, liste, sec, yukleniyor, hata, yenile };
}

// Ortak metin seçici dropdown — onaylı havuz metinlerinden kullanıcı seçer.
export function MetinSecici({ liste, metin, sec, yenile, className = "" }) {
  if (!liste || liste.length === 0) return null;
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <select value={metin?.id || ""} onChange={(e) => sec(e.target.value)}
        className="flex-1 min-w-0 px-2 py-1.5 rounded-lg border border-gray-200 text-sm bg-white">
        {liste.map((m) => (
          <option key={m.id} value={m.id}>{m.baslik || "Başlıksız"} ({kelimelereBol(m.icerik).length} kelime)</option>
        ))}
      </select>
      <button onClick={yenile} type="button" className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-sm shrink-0" title="Rastgele metin">🔄</button>
    </div>
  );
}
