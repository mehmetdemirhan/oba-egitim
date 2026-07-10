import React, { useEffect, useState } from "react";
import axios from "axios";

/**
 * SifreSifirla — e-postadaki reset linkiyle (login olmadan) açılan yeni-şifre ekranı.
 * URL: /sifre-sifirla?token=... (App.js, user yokken bu bileşeni render eder).
 *
 * Global axios interceptor'ından (401→refresh→reload) ve bayat Authorization
 * header'ından bağımsız kalmak için ayrı bir instance kullanır; reset uçları public.
 */
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const http = axios.create();

const kart = { background: "#fff", borderRadius: 16, boxShadow: "0 10px 40px rgba(0,0,0,0.08)", padding: 32, width: "100%", maxWidth: 400 };
const sarmal = { minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(135deg,#EEF2FF,#FDF2F8)", padding: 16 };
const inputStil = { width: "100%", padding: "12px 14px", border: "1px solid #E5E7EB", borderRadius: 10, fontSize: 14, marginTop: 6, boxSizing: "border-box" };
const btnStil = { width: "100%", padding: "12px", background: "#4F46E5", color: "#fff", border: "none", borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: "pointer", marginTop: 8 };

export default function SifreSifirla({ token }) {
  const [durum, setDurum] = useState("kontrol"); // kontrol | form | basari | gecersiz
  const [sifre, setSifre] = useState("");
  const [sifre2, setSifre2] = useState("");
  const [hata, setHata] = useState("");
  const [yukleniyor, setYukleniyor] = useState(false);

  useEffect(() => {
    if (!token) { setDurum("gecersiz"); return; }
    let aktif = true;
    http.get(`${API}/auth/reset-password/gecerli`, { params: { token } })
      .then((r) => aktif && setDurum(r.data?.gecerli ? "form" : "gecersiz"))
      .catch(() => aktif && setDurum("gecersiz"));
    return () => { aktif = false; };
  }, [token]);

  const gonder = async (e) => {
    e.preventDefault();
    setHata("");
    if (sifre.length < 6) { setHata("Şifre en az 6 karakter olmalı."); return; }
    if (sifre !== sifre2) { setHata("Şifreler eşleşmiyor."); return; }
    setYukleniyor(true);
    try {
      await http.post(`${API}/auth/reset-password`, { token, yeni_sifre: sifre });
      setDurum("basari");
    } catch (err) {
      setHata(err?.response?.data?.detail || "Şifre güncellenemedi. Bağlantı süresi dolmuş olabilir.");
    } finally { setYukleniyor(false); }
  };

  const girise = () => window.location.replace("/");

  return (
    <div style={sarmal}>
      <div style={kart}>
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <div style={{ fontSize: 40 }}>🔐</div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: "#1F2937", margin: "8px 0 0" }}>Şifre Sıfırlama</h1>
        </div>

        {durum === "kontrol" && (
          <p style={{ textAlign: "center", color: "#6B7280", fontSize: 14 }}>Bağlantı doğrulanıyor…</p>
        )}

        {durum === "gecersiz" && (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>⚠️</div>
            <p style={{ color: "#4B5563", fontSize: 14, lineHeight: 1.6, marginBottom: 20 }}>
              Bu şifre sıfırlama bağlantısı geçersiz, kullanılmış veya süresi dolmuş. Lütfen giriş ekranından yeniden talep edin.
            </p>
            <button onClick={girise} style={btnStil}>Girişe Dön</button>
          </div>
        )}

        {durum === "form" && (
          <form onSubmit={gonder}>
            <label style={{ fontSize: 13, color: "#374151", fontWeight: 500 }}>Yeni Şifre
              <input type="password" value={sifre} onChange={(e) => setSifre(e.target.value)} style={inputStil} placeholder="En az 6 karakter" autoFocus />
            </label>
            <label style={{ fontSize: 13, color: "#374151", fontWeight: 500, display: "block", marginTop: 14 }}>Yeni Şifre (Tekrar)
              <input type="password" value={sifre2} onChange={(e) => setSifre2(e.target.value)} style={inputStil} placeholder="Şifreyi tekrar girin" />
            </label>
            {hata && <div style={{ color: "#DC2626", fontSize: 13, marginTop: 12 }}>{hata}</div>}
            <button type="submit" disabled={yukleniyor} style={{ ...btnStil, opacity: yukleniyor ? 0.6 : 1 }}>
              {yukleniyor ? "Kaydediliyor…" : "Şifremi Güncelle"}
            </button>
            <button type="button" onClick={girise} style={{ ...btnStil, background: "transparent", color: "#6B7280", boxShadow: "none", marginTop: 4 }}>İptal</button>
          </form>
        )}

        {durum === "basari" && (
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 44, marginBottom: 8 }}>✅</div>
            <p style={{ color: "#4B5563", fontSize: 14, lineHeight: 1.6, marginBottom: 20 }}>
              Şifreniz başarıyla güncellendi. Yeni şifrenizle giriş yapabilirsiniz.
            </p>
            <button onClick={girise} style={btnStil}>Girişe Dön</button>
          </div>
        )}
      </div>
    </div>
  );
}
