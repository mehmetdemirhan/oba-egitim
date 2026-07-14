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

// Analiz havuzundan rastgele bir okuma metni getirir (yeni 150 havuz).
// Dönüş: { metin, yukleniyor, hata, yenile }
export function useOkumaMetni(minKelime = 40) {
  const [metin, setMetin] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState("");

  const yenile = useCallback(async () => {
    setYukleniyor(true); setHata("");
    try {
      const r = await axios.get(`${API}/diagnostic/texts`, { params: { bolum: "analiz" } });
      const liste = Array.isArray(r.data) ? r.data.filter((m) => m?.icerik) : [];
      if (!liste.length) { setHata("Havuzda okuma metni bulunamadı. Yönetici 'Akıcı Okuma metinlerini yükle' ile ekleyebilir."); setMetin(null); return; }
      const uygun = liste.filter((m) => kelimelereBol(m.icerik).length >= minKelime);
      const havuz = uygun.length ? uygun : liste;
      // Math.random burada güvenli (deterministik resume gereği yok — istemci tarafı)
      setMetin(havuz[Math.floor(Math.random() * havuz.length)]);
    } catch (e) {
      setHata(e?.response?.data?.detail || "Metin yüklenemedi.");
      setMetin(null);
    } finally {
      setYukleniyor(false);
    }
  }, [minKelime]);

  useEffect(() => { yenile(); }, [yenile]);

  return { metin, yukleniyor, hata, yenile };
}
