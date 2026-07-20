import React, { useEffect, useState } from "react";
import axios from "axios";

/**
 * VeliAnketPublic — GİRİŞSİZ veli memnuniyet anketi.
 * URL: /veli-anket?token=... (App.js, auth durumundan bağımsız render eder).
 *
 * Girişsiz akış: token backend'de doğrulanır, anket db.veli_anketleri'ne yazılır
 * (mevcut "Veli Değerlendirme Özeti" ile aynı koleksiyon). Token tek kullanımlık.
 * Bayat Authorization header'ından bağımsız kalmak için ayrı axios instance.
 */
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const http = axios.create();

const sarmal = { minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(135deg,#EEF2FF,#FDF2F8)", padding: 16 };
const kart = { background: "#fff", borderRadius: 16, boxShadow: "0 10px 40px rgba(0,0,0,0.08)", padding: 28, width: "100%", maxWidth: 480 };
const btnStil = { width: "100%", padding: "13px", background: "#4F46E5", color: "#fff", border: "none", borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: "pointer", marginTop: 12 };

export default function VeliAnketPublic({ token }) {
  const [durum, setDurum] = useState("kontrol"); // kontrol | form | basari | gecersiz
  const [hataMesaj, setHataMesaj] = useState("");
  const [bilgi, setBilgi] = useState({ ogrenci_ad: "", sorular: [] });
  const [puanlar, setPuanlar] = useState({}); // { [soru_no]: 1..5 }
  const [tavsiye, setTavsiye] = useState(null);
  const [notText, setNotText] = useState("");
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [hata, setHata] = useState("");

  useEffect(() => {
    if (!token) { setDurum("gecersiz"); setHataMesaj("Bağlantı bulunamadı."); return; }
    let aktif = true;
    http.get(`${API}/anketler/anket/${token}`)
      .then((r) => { if (!aktif) return; setBilgi(r.data || {}); setDurum("form"); })
      .catch((e) => { if (!aktif) return; setHataMesaj(e?.response?.data?.detail || "Bağlantı geçersiz veya süresi dolmuş."); setDurum("gecersiz"); });
    return () => { aktif = false; };
  }, [token]);

  const puanSorular = (bilgi.sorular || []).filter((s) => s.tip === "puan");
  const notSoru = (bilgi.sorular || []).find((s) => s.tip === "metin");
  const tavsiyeSoru = (bilgi.sorular || []).find((s) => s.tip === "evet_hayir");

  const gonder = async () => {
    setHata("");
    const eksik = puanSorular.filter((s) => !puanlar[s.no]);
    if (eksik.length > 0) { setHata("Lütfen tüm puanlı soruları yanıtlayın."); return; }
    if (tavsiye === null) { setHata("Lütfen tavsiye sorusunu yanıtlayın."); return; }
    setGonderiliyor(true);
    try {
      const yanitlar = Object.entries(puanlar).map(([no, puan]) => {
        const s = puanSorular.find((q) => q.no === parseInt(no));
        return { soru_no: parseInt(no), puan, kategori: s?.kategori || "" };
      });
      await http.post(`${API}/anketler/anket/${token}`, { yanitlar, tavsiye, not_text: notText });
      setDurum("basari");
    } catch (e) {
      setHata(e?.response?.data?.detail || "Gönderilemedi. Bağlantı süresi dolmuş olabilir.");
    } finally { setGonderiliyor(false); }
  };

  return (
    <div style={sarmal}>
      <div style={kart}>
        <div style={{ textAlign: "center", marginBottom: 18 }}>
          <div style={{ fontSize: 38 }}>⭐</div>
          <h1 style={{ fontSize: 19, fontWeight: 700, color: "#1F2937", margin: "8px 0 0" }}>Öğretmen Değerlendirme Anketi</h1>
          {bilgi.ogrenci_ad && durum === "form" && (
            <p style={{ fontSize: 13, color: "#6B7280", marginTop: 6 }}>{bilgi.ogrenci_ad} için öğretmenini değerlendirin. Yanıtlarınız anonim iletilir.</p>
          )}
        </div>

        {durum === "kontrol" && (<p style={{ textAlign: "center", color: "#6B7280", fontSize: 14 }}>Bağlantı doğrulanıyor…</p>)}

        {durum === "gecersiz" && (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>⚠️</div>
            <p style={{ color: "#4B5563", fontSize: 14, lineHeight: 1.6 }}>{hataMesaj || "Bu anket bağlantısı geçersiz, kullanılmış veya süresi dolmuş."}</p>
          </div>
        )}

        {durum === "form" && (
          <div>
            {puanSorular.map((s) => (
              <div key={s.no} style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 14, color: "#374151", fontWeight: 500 }}>{s.no}. {s.soru}</div>
                <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                  {[1, 2, 3, 4, 5].map((p) => (
                    <button key={p} onClick={() => setPuanlar({ ...puanlar, [s.no]: p })}
                      style={{ width: 40, height: 40, borderRadius: 10, border: "none", cursor: "pointer", fontSize: 18, background: (puanlar[s.no] || 0) >= p ? "#FBBF24" : "#F3F4F6", transform: (puanlar[s.no] || 0) >= p ? "scale(1.08)" : "none", transition: "all .15s" }}>⭐</button>
                  ))}
                </div>
              </div>
            ))}

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 14, color: "#374151", fontWeight: 500 }}>{tavsiyeSoru ? `${tavsiyeSoru.no}. ${tavsiyeSoru.soru}` : "Bu öğretmeni başka velilere tavsiye eder misiniz?"}</div>
              <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
                <button onClick={() => setTavsiye(true)} style={{ flex: 1, padding: "11px", borderRadius: 10, fontSize: 14, fontWeight: 500, cursor: "pointer", border: "1px solid", borderColor: tavsiye === true ? "#22C55E" : "#E5E7EB", background: tavsiye === true ? "#22C55E" : "#fff", color: tavsiye === true ? "#fff" : "#6B7280" }}>👍 Evet</button>
                <button onClick={() => setTavsiye(false)} style={{ flex: 1, padding: "11px", borderRadius: 10, fontSize: 14, fontWeight: 500, cursor: "pointer", border: "1px solid", borderColor: tavsiye === false ? "#EF4444" : "#E5E7EB", background: tavsiye === false ? "#EF4444" : "#fff", color: tavsiye === false ? "#fff" : "#6B7280" }}>👎 Hayır</button>
              </div>
            </div>

            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 14, color: "#374151", fontWeight: 500 }}>{notSoru ? `${notSoru.no}. ${notSoru.soru}` : "Eklemek istediğiniz not (opsiyonel)"}</div>
              <textarea value={notText} onChange={(e) => setNotText(e.target.value)} placeholder="Düşünceleriniz…"
                style={{ width: "100%", minHeight: 64, marginTop: 6, padding: "10px 12px", border: "1px solid #E5E7EB", borderRadius: 10, fontSize: 14, boxSizing: "border-box", resize: "vertical" }} />
            </div>

            {hata && <div style={{ color: "#DC2626", fontSize: 13, marginTop: 8 }}>{hata}</div>}
            <button onClick={gonder} disabled={gonderiliyor} style={{ ...btnStil, opacity: gonderiliyor ? 0.6 : 1 }}>
              {gonderiliyor ? "Gönderiliyor…" : "⭐ Değerlendirmeyi Gönder"}
            </button>
          </div>
        )}

        {durum === "basari" && (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 44, marginBottom: 8 }}>✅</div>
            <p style={{ color: "#4B5563", fontSize: 14, lineHeight: 1.6 }}>Değerlendirmeniz kaydedildi. Katkınız için teşekkür ederiz!</p>
          </div>
        )}
      </div>
    </div>
  );
}
