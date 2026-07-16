import React from "react";

/**
 * Personalar — AI CEO modülünün iki personası için TELİFSİZ, elde üretilmiş düz-çizim
 * (flat) SVG avatarları + ortak UI konfigürasyonu (ad, renk, üslup etiketi).
 *
 * AYDA  = CEO / yönetim danışmanı — mavi-kurumsal, takım elbiseli, güven veren.
 * MİRAN = Öğretmen koçu (Ayda'nın alt-AI'ı) — amber-sıcak, samimi, motive edici.
 *
 * Not: sistem promptları/veri kapsamı BACKEND'de (appbackend/modules/ai_ceo/personalar.py).
 * Burası yalnız görsel + etiket katmanı; iki taraf ad/renk açısından tutarlı tutulur.
 */

export const PERSONA_UI = {
  ayda: {
    ad: "Ayda",
    unvan: "AI CEO",
    renk: "#2563eb",        // mavi-kurumsal
    renkAcik: "#dbeafe",
    uslup: "Kurumsal, net, sayı veren yönetici dili",
    selam: "Merhaba, ben Ayda. Sistemi sizin için 360° analiz ediyorum.",
  },
  miran: {
    ad: "Miran",
    unvan: "Öğretmen Koçu",
    renk: "#d97706",        // amber-sıcak
    renkAcik: "#fef3c7",
    uslup: "Sıcak, motive edici, kırıcı olmayan koç dili",
    selam: "Selam, ben Miran! Bu hafta sana özel birkaç önerim var.",
  },
};

// ── AYDA — mavi blazer, düz saç, kurumsal duruş ──
export function AydaAvatar({ size = 48, ring = true, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className={className}
      role="img" aria-label="Ayda — AI CEO avatarı">
      <defs>
        <linearGradient id="ayda-bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#eff6ff" />
          <stop offset="1" stopColor="#dbeafe" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="49" fill="url(#ayda-bg)" stroke={ring ? "#2563eb" : "none"} strokeWidth={ring ? 2 : 0} />
      {/* omuz + blazer */}
      <path d="M20 100 Q20 74 50 74 Q80 74 80 100 Z" fill="#1e3a8a" />
      <path d="M50 74 L44 100 M50 74 L56 100" stroke="#1e40af" strokeWidth="1.5" fill="none" />
      {/* gömlek yaka */}
      <path d="M42 76 L50 86 L58 76 L54 74 L46 74 Z" fill="#f8fafc" />
      {/* boyun */}
      <rect x="45" y="64" width="10" height="12" rx="4" fill="#e8b48c" />
      {/* yüz */}
      <circle cx="50" cy="50" r="17" fill="#f2c19b" />
      {/* saç — düz bob */}
      <path d="M31 50 Q30 28 50 27 Q70 28 69 50 Q69 44 63 42 Q60 33 50 33 Q40 33 37 42 Q31 44 31 50 Z" fill="#3b2f2a" />
      <path d="M32 50 Q31 62 35 66 L37 54 Z" fill="#3b2f2a" />
      <path d="M68 50 Q69 62 65 66 L63 54 Z" fill="#3b2f2a" />
      {/* gözler */}
      <circle cx="43" cy="49" r="1.8" fill="#2b2b2b" />
      <circle cx="57" cy="49" r="1.8" fill="#2b2b2b" />
      <path d="M40 45 Q43 43 46 45 M54 45 Q57 43 60 45" stroke="#5b4636" strokeWidth="1.2" fill="none" strokeLinecap="round" />
      {/* gülümseme — güven veren, ölçülü */}
      <path d="M45 57 Q50 61 55 57" stroke="#a15c4a" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  );
}

// ── MİRAN — amber, at kuyruğu, samimi gülümseme ──
export function MiranAvatar({ size = 48, ring = true, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className={className}
      role="img" aria-label="Miran — Öğretmen Koçu avatarı">
      <defs>
        <linearGradient id="miran-bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fffbeb" />
          <stop offset="1" stopColor="#fef3c7" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="49" fill="url(#miran-bg)" stroke={ring ? "#d97706" : "none"} strokeWidth={ring ? 2 : 0} />
      {/* omuz + sıcak renk kazak */}
      <path d="M20 100 Q20 74 50 74 Q80 74 80 100 Z" fill="#c2410c" />
      <path d="M42 75 Q50 82 58 75 L58 100 L42 100 Z" fill="#ea580c" />
      {/* boyun */}
      <rect x="45" y="64" width="10" height="12" rx="4" fill="#e8b48c" />
      {/* yüz */}
      <circle cx="50" cy="50" r="17" fill="#f4c9a0" />
      {/* at kuyruğu — yandan */}
      <path d="M69 44 Q80 48 78 62 Q76 70 71 70 Q75 60 68 52 Z" fill="#6b4423" />
      {/* saç üst */}
      <path d="M31 50 Q30 27 50 26 Q71 27 69 50 Q69 43 62 41 Q59 32 50 32 Q41 32 38 41 Q31 43 31 50 Z" fill="#6b4423" />
      {/* gözler — daha canlı */}
      <circle cx="43" cy="49" r="2" fill="#2b2b2b" />
      <circle cx="57" cy="49" r="2" fill="#2b2b2b" />
      <path d="M40 45 Q43 43 46 45 M54 45 Q57 43 60 45" stroke="#5b4636" strokeWidth="1.2" fill="none" strokeLinecap="round" />
      {/* yanak allık — sıcaklık */}
      <circle cx="39" cy="55" r="3" fill="#f59e8c" opacity="0.5" />
      <circle cx="61" cy="55" r="3" fill="#f59e8c" opacity="0.5" />
      {/* geniş samimi gülümseme */}
      <path d="M43 56 Q50 63 57 56" stroke="#a15c4a" strokeWidth="1.8" fill="none" strokeLinecap="round" />
    </svg>
  );
}

export function PersonaAvatar({ persona = "ayda", ...props }) {
  return persona === "miran" ? <MiranAvatar {...props} /> : <AydaAvatar {...props} />;
}

/**
 * PersonaBalon — avatar + konuşma balonu (sayfa üstü karşılama / kısa mesaj).
 */
export function PersonaBalon({ persona = "ayda", mesaj, size = 64 }) {
  const p = PERSONA_UI[persona] || PERSONA_UI.ayda;
  return (
    <div className="flex items-start gap-3">
      <PersonaAvatar persona={persona} size={size} />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-bold text-content">{p.ad}</span>
          <span className="text-[10px] uppercase tracking-wide font-semibold px-1.5 py-0.5 rounded"
            style={{ background: p.renkAcik, color: p.renk }}>{p.unvan}</span>
        </div>
        <div className="mt-1 relative inline-block rounded-2xl rounded-tl-sm px-3 py-2 text-sm text-content shadow-sm border"
          style={{ background: p.renkAcik + "66", borderColor: p.renkAcik }}>
          {mesaj || p.selam}
        </div>
      </div>
    </div>
  );
}

/** PersonaRozet — kart/bildirim köşesi için küçük avatar + ad rozeti. */
export function PersonaRozet({ persona = "ayda" }) {
  const p = PERSONA_UI[persona] || PERSONA_UI.ayda;
  return (
    <span className="inline-flex items-center gap-1 rounded-full pl-0.5 pr-2 py-0.5 text-[11px] font-semibold"
      style={{ background: p.renkAcik, color: p.renk }}>
      <PersonaAvatar persona={persona} size={18} ring={false} />
      {p.ad}
    </span>
  );
}
