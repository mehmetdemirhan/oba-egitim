import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { swKaydet } from "./lib/push";
import PWAKur from "./components/PWAKur";

// Web Push + PWA service worker'ı kaydet
swKaydet();

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <AuthProvider>
      <ThemeProvider>
        <App />
        <PWAKur />
      </ThemeProvider>
    </AuthProvider>
  </React.StrictMode>,
);
