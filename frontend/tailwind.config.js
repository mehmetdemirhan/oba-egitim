/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Poppins", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        poppins: ["Poppins", "system-ui", "sans-serif"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      colors: {
        // ── Semantik tema token'ları (migration hedefi) ──
        primary: {
          DEFAULT: "var(--primary)",
          hover: "var(--primary-hover)",
          foreground: "#ffffff",
        },
        secondary: { DEFAULT: "var(--secondary)", foreground: "#ffffff" },
        surface: "var(--surface)",          // bg-surface  (kart/panel yüzeyi = beyaz)
        app: "var(--background)",            // bg-app      (sayfa zemini = gri-50)
        content: "var(--text)",             // text-content (ana metin)
        subtle: "var(--text-secondary)",    // text-subtle  (ikincil metin)
        line: "var(--border)",              // border-line  (kenarlık)
        accent: { DEFAULT: "var(--accent)", foreground: "#ffffff" },
        danger: "var(--danger)",
        success: "var(--success)",
        warning: "var(--warning)",
        // ── shadcn/ui uyumluluğu (ui bileşenleri artık düzgün çalışır) ──
        destructive: { DEFAULT: "var(--danger)", foreground: "#ffffff" },
        muted: { DEFAULT: "var(--background)", foreground: "var(--text-secondary)" },
        input: "var(--border)",
        ring: "var(--primary)",
        // Select/Dropdown/Popover içerik yüzeyi. Tanımsızken bg-popover ölü sınıftı
        // → açılan liste ŞEFFAF kalıp altındaki form alanlarıyla iç içe görünüyordu.
        // Yüzey = kart yüzeyi (--surface), metin = ana metin (--text); light/dark oto.
        popover: { DEFAULT: "var(--surface)", foreground: "var(--text)" },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
