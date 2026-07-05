// ─────────────────────────────────────────────────────────────
// src/context/AuthContext.js  (DÜZELTİLMİŞ)
// ─────────────────────────────────────────────────────────────
import React, { createContext, useContext, useState, useEffect } from "react";
import axios from "axios";

const AuthContext = createContext(null);
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// ── Otomatik token yenileme (kalıcı 45 günlük oturum) ──
// Access token 401 verince refresh ile sessizce yenilenir ve istek tekrarlanır.
let _yenilemePromise = null;
axios.interceptors.response.use(
  (r) => r,
  async (error) => {
    const orig = error.config || {};
    const rt = localStorage.getItem("oba_refresh");
    const url = String(orig.url || "");
    const atlansin = url.includes("/auth/refresh") || url.includes("/auth/login");
    if (error.response?.status === 401 && rt && !orig._retry && !atlansin) {
      orig._retry = true;
      try {
        if (!_yenilemePromise) _yenilemePromise = axios.post(`${API}/auth/refresh`, { refresh_token: rt });
        const { data } = await _yenilemePromise;
        _yenilemePromise = null;
        localStorage.setItem("oba_token", data.access_token);
        axios.defaults.headers.common["Authorization"] = `Bearer ${data.access_token}`;
        orig.headers = orig.headers || {};
        orig.headers["Authorization"] = `Bearer ${data.access_token}`;
        return axios(orig);
      } catch (e) {
        _yenilemePromise = null;
        localStorage.removeItem("oba_token");
        localStorage.removeItem("oba_refresh");
        delete axios.defaults.headers.common["Authorization"];
        window.location.reload(); // oturum gerçekten bitti → giriş ekranı
      }
    }
    return Promise.reject(error);
  }
);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("oba_token"));
  const [loading, setLoading] = useState(true);

  // Token değişince header'ı set et
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common["Authorization"];
    }
  }, [token]);

  // ★ DÜZELTİLDİ: dependency [token] eklendi + header verify öncesi garanti set ediliyor
  useEffect(() => {
    const verifyToken = async () => {
      if (!token) {
        setLoading(false);
        return;
      }

      // ★ Race condition düzeltmesi: header'ın kesinlikle set olduğundan emin ol
      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;

      try {
        const response = await axios.get(`${API}/auth/me`);
        setUser(response.data);
      } catch (error) {
        console.error("Token doğrulama hatası:", error?.response?.status);
        // ★ DÜZELTİLDİ: logout() yerine inline temizlik (stale closure riski yok)
        localStorage.removeItem("oba_token");
        delete axios.defaults.headers.common["Authorization"];
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    verifyToken();
  }, [token]); // ★ DÜZELTİLDİ: dependency eklendi

  const login = async (emailOrPhone, password) => {
    let response;
    try {
      // Yeni backend format (email_or_phone)
      response = await axios.post(`${API}/auth/login`, { email_or_phone: emailOrPhone, password });
    } catch (err) {
      if (err.response?.status === 422) {
        // Eski backend format (email) — fallback
        response = await axios.post(`${API}/auth/login`, { email: emailOrPhone, password });
      } else {
        throw err;
      }
    }
    const { access_token, user: userData, refresh_token } = response.data;

    localStorage.setItem("oba_token", access_token);
    if (refresh_token) localStorage.setItem("oba_refresh", refresh_token);
    axios.defaults.headers.common["Authorization"] = `Bearer ${access_token}`;
    setToken(access_token);
    setUser(userData);
    return userData;
  };

  const logout = async () => {
    // Sunucuda refresh token'ı iptal et (bu cihazın oturumunu kapat)
    const rt = localStorage.getItem("oba_refresh");
    if (rt) { try { await axios.post(`${API}/auth/logout`, { refresh_token: rt }); } catch (e) {} }
    localStorage.removeItem("oba_token");
    localStorage.removeItem("oba_refresh");
    delete axios.defaults.headers.common["Authorization"];
    setToken(null);
    setUser(null);
  };

  // Kullanıcıyı backend'den yeniden çek (ör. şifre değişince sifre_degistirme_zorunlu güncellensin)
  const refreshUser = async () => {
    try {
      const r = await axios.get(`${API}/auth/me`);
      setUser(r.data);
      return r.data;
    } catch (e) { return null; }
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export default AuthContext;
