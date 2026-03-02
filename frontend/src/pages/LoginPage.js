import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function LoginPage() {
  const { login } = useAuth();
  const [emailOrPhone, setEmailOrPhone] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState("login"); // login | forgot | reset-done
  const [forgotResult, setForgotResult] = useState(null);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!emailOrPhone.trim() || !password.trim()) {
      setError("Lütfen tüm alanları doldurun");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await login(emailOrPhone.trim(), password);
    } catch (err) {
      setError(err.response?.data?.detail || "Giriş başarısız. Bilgilerinizi kontrol edin.");
    } finally {
      setLoading(false);
    }
  };

  const handleForgot = async (e) => {
    e.preventDefault();
    if (!emailOrPhone.trim()) {
      setError("E-posta veya telefon numaranızı girin");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const r = await axios.post(`${API}/auth/forgot-password`, { email_or_phone: emailOrPhone.trim() });
      setForgotResult(r.data);
      setMode("reset-done");
    } catch (err) {
      setError(err.response?.data?.detail || "Kullanıcı bulunamadı");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "linear-gradient(135deg, #FFF7ED 0%, #FEF3C7 50%, #FFEDD5 100%)",
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}>
      <div style={{
        width: "100%",
        maxWidth: 400,
        padding: "0 20px",
      }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            width: 64, height: 64, margin: "0 auto 16px",
            background: "linear-gradient(135deg, #F97316, #EF4444)",
            borderRadius: 16, display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 8px 24px rgba(249,115,22,0.3)",
          }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
            </svg>
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: "#1F2937", margin: 0 }}>Okuma Becerileri Akademisi</h1>
          <p style={{ fontSize: 14, color: "#6B7280", marginTop: 4 }}>Eğitim Yönetim Sistemi</p>
        </div>

        {/* Kart */}
        <div style={{
          background: "white",
          borderRadius: 20,
          padding: 32,
          boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
        }}>
          {mode === "login" && (
            <>
              <h2 style={{ fontSize: 18, fontWeight: 600, color: "#1F2937", marginBottom: 24, textAlign: "center" }}>
                Giriş Yap
              </h2>
              <form onSubmit={handleLogin}>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "#374151", marginBottom: 6 }}>
                    E-posta veya Telefon
                  </label>
                  <input
                    type="text"
                    value={emailOrPhone}
                    onChange={e => { setEmailOrPhone(e.target.value); setError(""); }}
                    placeholder="ornek@email.com veya 05xx..."
                    autoFocus
                    style={{
                      width: "100%", padding: "12px 16px", borderRadius: 12,
                      border: "1.5px solid #E5E7EB", fontSize: 15, outline: "none",
                      transition: "border-color 0.2s",
                      boxSizing: "border-box",
                    }}
                    onFocus={e => e.target.style.borderColor = "#F97316"}
                    onBlur={e => e.target.style.borderColor = "#E5E7EB"}
                  />
                </div>
                <div style={{ marginBottom: 8 }}>
                  <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "#374151", marginBottom: 6 }}>
                    Şifre
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={e => { setPassword(e.target.value); setError(""); }}
                    placeholder="••••••••"
                    style={{
                      width: "100%", padding: "12px 16px", borderRadius: 12,
                      border: "1.5px solid #E5E7EB", fontSize: 15, outline: "none",
                      transition: "border-color 0.2s",
                      boxSizing: "border-box",
                    }}
                    onFocus={e => e.target.style.borderColor = "#F97316"}
                    onBlur={e => e.target.style.borderColor = "#E5E7EB"}
                  />
                </div>
                <div style={{ textAlign: "right", marginBottom: 20 }}>
                  <button type="button" onClick={() => { setMode("forgot"); setError(""); }}
                    style={{ background: "none", border: "none", color: "#F97316", fontSize: 13, cursor: "pointer", fontWeight: 500 }}>
                    Şifremi Unuttum
                  </button>
                </div>
                {error && (
                  <div style={{
                    background: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626",
                    borderRadius: 10, padding: "10px 14px", fontSize: 13, marginBottom: 16, textAlign: "center",
                  }}>{error}</div>
                )}
                <button type="submit" disabled={loading}
                  style={{
                    width: "100%", padding: "14px", borderRadius: 12, border: "none",
                    background: loading ? "#D1D5DB" : "linear-gradient(135deg, #F97316, #EF4444)",
                    color: "white", fontSize: 16, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer",
                    boxShadow: loading ? "none" : "0 4px 16px rgba(249,115,22,0.3)",
                    transition: "all 0.2s",
                  }}>
                  {loading ? "Giriş yapılıyor..." : "Giriş Yap"}
                </button>
              </form>
            </>
          )}

          {mode === "forgot" && (
            <>
              <h2 style={{ fontSize: 18, fontWeight: 600, color: "#1F2937", marginBottom: 8, textAlign: "center" }}>
                Şifremi Unuttum
              </h2>
              <p style={{ fontSize: 13, color: "#6B7280", textAlign: "center", marginBottom: 24 }}>
                Kayıtlı e-posta veya telefon numaranızı girin. Geçici şifre oluşturulacak.
              </p>
              <form onSubmit={handleForgot}>
                <div style={{ marginBottom: 20 }}>
                  <input
                    type="text"
                    value={emailOrPhone}
                    onChange={e => { setEmailOrPhone(e.target.value); setError(""); }}
                    placeholder="E-posta veya telefon numarası"
                    autoFocus
                    style={{
                      width: "100%", padding: "12px 16px", borderRadius: 12,
                      border: "1.5px solid #E5E7EB", fontSize: 15, outline: "none",
                      boxSizing: "border-box",
                    }}
                    onFocus={e => e.target.style.borderColor = "#F97316"}
                    onBlur={e => e.target.style.borderColor = "#E5E7EB"}
                  />
                </div>
                {error && (
                  <div style={{
                    background: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626",
                    borderRadius: 10, padding: "10px 14px", fontSize: 13, marginBottom: 16, textAlign: "center",
                  }}>{error}</div>
                )}
                <button type="submit" disabled={loading}
                  style={{
                    width: "100%", padding: "14px", borderRadius: 12, border: "none",
                    background: loading ? "#D1D5DB" : "linear-gradient(135deg, #3B82F6, #6366F1)",
                    color: "white", fontSize: 15, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer",
                    marginBottom: 12,
                  }}>
                  {loading ? "İşleniyor..." : "Geçici Şifre Gönder"}
                </button>
                <button type="button" onClick={() => { setMode("login"); setError(""); }}
                  style={{
                    width: "100%", padding: "12px", borderRadius: 12,
                    border: "1.5px solid #E5E7EB", background: "white",
                    color: "#374151", fontSize: 14, fontWeight: 500, cursor: "pointer",
                  }}>
                  ← Giriş Ekranına Dön
                </button>
              </form>
            </>
          )}

          {mode === "reset-done" && forgotResult && (
            <>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
                <h2 style={{ fontSize: 18, fontWeight: 600, color: "#1F2937", marginBottom: 8 }}>
                  Geçici Şifre Oluşturuldu
                </h2>
                <p style={{ fontSize: 13, color: "#6B7280", marginBottom: 20 }}>
                  {forgotResult.kullanici} için geçici şifre:
                </p>
                <div style={{
                  background: "#F0FDF4", border: "2px solid #86EFAC", borderRadius: 12,
                  padding: "16px", fontSize: 28, fontWeight: 700, color: "#16A34A",
                  letterSpacing: 4, marginBottom: 16,
                }}>
                  {forgotResult.gecici_sifre}
                </div>
                <p style={{ fontSize: 12, color: "#9CA3AF", marginBottom: 24 }}>
                  Bu şifre ile giriş yapın, ardından şifrenizi değiştirin.
                </p>
              </div>
              <button onClick={() => { setMode("login"); setPassword(""); setError(""); setForgotResult(null); }}
                style={{
                  width: "100%", padding: "14px", borderRadius: 12, border: "none",
                  background: "linear-gradient(135deg, #F97316, #EF4444)",
                  color: "white", fontSize: 15, fontWeight: 600, cursor: "pointer",
                }}>
                Giriş Yap
              </button>
            </>
          )}
        </div>

        {/* Alt bilgi */}
        <p style={{ textAlign: "center", fontSize: 12, color: "#9CA3AF", marginTop: 24 }}>
          © 2026 Okuma Becerileri Akademisi
        </p>
      </div>
    </div>
  );
}
