import React from "react";

/**
 * KelimeGezmeceMascot — basit, sevimli bulut-yüzü maskotu (inline SVG).
 *
 * Orijinal Kelime Gezmece'de yoktur; modern çocuk uygulaması (Sago Mini / Pok Pok)
 * hissi için eklenmiştir. Tek renk (temaya uygun pastel) + 2 göz + gülümseme.
 *
 * Props:
 *   renk   — temaya uygun pastel dolgu (hex)
 *   durum  — "idle" | "zipla" | "kutla" | "kink"
 *   tetik  — sayaç; değişince tek seferlik animasyon (zıpla/kutla/kink) yeniden oynar
 *   boyut  — px (varsayılan 76)
 */
export default function KelimeGezmeceMascot({
  renk = "#A7E8BD",
  durum = "idle",
  tetik = 0,
  boyut = 76,
}) {
  // Tek seferlik animasyonlar için key ile yeniden mount → animasyon yeniden oynar.
  const animKey = `${durum}-${tetik}`;
  const animAd =
    durum === "zipla"
      ? "kgm-zipla 480ms ease"
      : durum === "kutla"
      ? "kgm-kutla 1000ms ease"
      : durum === "kink"
      ? "kgm-idle 3s ease-in-out infinite"
      : "kgm-idle 3s ease-in-out infinite";

  const kinkli = durum === "kink";

  return (
    <div
      style={{ width: boyut, height: boyut, pointerEvents: "none" }}
      aria-hidden="true"
    >
      <div
        key={animKey}
        style={{
          width: "100%",
          height: "100%",
          transformOrigin: "center bottom",
          animation: animAd,
        }}
      >
        {/* Kutlama yıldızları */}
        {durum === "kutla" && (
          <div style={{ position: "absolute", inset: 0 }}>
            {[0, 1, 2, 3].map((i) => (
              <span
                key={i}
                style={{
                  position: "absolute",
                  left: "50%",
                  top: "40%",
                  fontSize: 14,
                  animation: `kgm-yildiz 900ms ease ${i * 60}ms forwards`,
                  ["--kgm-ac"]: `${i * 90 + 20}deg`,
                }}
              >
                ⭐
              </span>
            ))}
          </div>
        )}

        <svg viewBox="0 0 100 100" width="100%" height="100%">
          {/* Bulut gövdesi */}
          <path
            d="M28 68 Q10 68 12 52 Q6 40 20 36 Q22 20 40 24 Q50 10 66 22 Q86 20 84 40 Q96 48 84 62 Q86 72 72 70 Z"
            fill={renk}
          />
          {/* Gözler */}
          <ellipse
            cx="40"
            cy="46"
            rx="4"
            ry={kinkli ? 1 : 5}
            fill="#3D405B"
          />
          <ellipse
            cx="60"
            cy="46"
            rx="4"
            ry={kinkli ? 1 : 5}
            fill="#3D405B"
          />
          {/* Yanak */}
          <circle cx="32" cy="55" r="3.5" fill="#FFB5A7" opacity="0.8" />
          <circle cx="68" cy="55" r="3.5" fill="#FFB5A7" opacity="0.8" />
          {/* Gülümseme */}
          <path
            d="M42 57 Q50 65 58 57"
            fill="none"
            stroke="#3D405B"
            strokeWidth="3"
            strokeLinecap="round"
          />
        </svg>
      </div>

      <style>{`
        @keyframes kgm-idle {
          0%,100% { transform: scale(1); }
          50% { transform: scale(1.03); }
        }
        @keyframes kgm-zipla {
          0% { transform: translateY(0); }
          40% { transform: translateY(-12px); }
          70% { transform: translateY(0) scaleY(0.94); }
          100% { transform: translateY(0); }
        }
        @keyframes kgm-kutla {
          0% { transform: rotate(0) scale(1); }
          25% { transform: rotate(-10deg) scale(1.1); }
          50% { transform: rotate(10deg) scale(1.15); }
          75% { transform: rotate(-6deg) scale(1.1); }
          100% { transform: rotate(0) scale(1); }
        }
        @keyframes kgm-yildiz {
          0% { transform: translate(-50%, -50%) rotate(var(--kgm-ac)) translateY(0) scale(0.4); opacity: 0; }
          40% { opacity: 1; }
          100% { transform: translate(-50%, -50%) rotate(var(--kgm-ac)) translateY(-34px) scale(1); opacity: 0; }
        }
      `}</style>
    </div>
  );
}
