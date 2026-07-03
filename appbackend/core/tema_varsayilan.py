"""Tema sistemi — varsayılan hazır temalar (tek doğruluk kaynağı).

Her tema `modlar.light` ve `modlar.dark` içerir; her mod aşağıdaki 12 token'a
sahiptir. Bu değerler frontend'de CSS değişkenlerine (--primary, --surface …)
uygulanır. Nötr token'ların (background/surface/text/text_secondary/border)
LIGHT değerleri, mevcut arayüzün gri iskeletiyle EŞLEŞİR — böylece migration
sonrası light görünüm değişmez.

Sistem varsayılanı: "deniz" (mavi). Öğrenci rol varsayılanı: "ogrenci_cream".
"""

# Token alan listesi (şema doğrulama + form için)
TOKEN_ALANLARI = [
    "primary", "primary_hover", "secondary", "background", "surface",
    "text", "text_secondary", "border", "accent", "danger", "success", "warning",
]


def _tema(kod, ad, aciklama, kategori, hedef_rol, light, dark):
    return {
        "kod": kod, "ad": ad, "aciklama": aciklama,
        "kategori": kategori, "hedef_rol": hedef_rol,
        "modlar": {"light": light, "dark": dark},
    }


# Ortak nötr açık değerler (mevcut gri iskelet ile eşleşir)
_NOTR_LIGHT = {
    "background": "#F9FAFB", "surface": "#FFFFFF",
    "text": "#1F2937", "text_secondary": "#6B7280", "border": "#E5E7EB",
    "danger": "#DC2626", "success": "#16A34A", "warning": "#D97706",
}
_NOTR_DARK = {
    "background": "#0F172A", "surface": "#1E293B",
    "text": "#F1F5F9", "text_secondary": "#94A3B8", "border": "#334155",
    "danger": "#EF4444", "success": "#22C55E", "warning": "#F59E0B",
}


TEMALAR = [
    # ── Deniz (mavi) — SİSTEM VARSAYILANI ──
    _tema(
        "deniz", "Deniz Mavisi", "Ferah, güven veren mavi tonları", "hazir", None,
        {**_NOTR_LIGHT, "primary": "#2563EB", "primary_hover": "#1D4ED8",
         "secondary": "#64748B", "accent": "#0EA5E9"},
        {**_NOTR_DARK, "primary": "#3B82F6", "primary_hover": "#2563EB",
         "secondary": "#94A3B8", "accent": "#38BDF8"},
    ),
    # ── Orman (emerald) ──
    _tema(
        "orman", "Orman Yeşili", "Büyümeyi ve başarıyı çağrıştıran yeşil", "hazir", None,
        {**_NOTR_LIGHT, "background": "#F0FDF4", "border": "#D1FAE5",
         "primary": "#059669", "primary_hover": "#047857",
         "secondary": "#64748B", "accent": "#10B981"},
        {**_NOTR_DARK, "background": "#052E16", "surface": "#14311F", "border": "#166534",
         "primary": "#10B981", "primary_hover": "#059669",
         "secondary": "#94A3B8", "accent": "#34D399", "text_secondary": "#A7F3D0"},
    ),
    # ── Gün Batımı (turuncu/sıcak) — mevcut marka rengi ──
    _tema(
        "gun_batimi", "Gün Batımı", "OBA marka kimliği: sıcak turuncu-kırmızı", "hazir", None,
        {**_NOTR_LIGHT, "background": "#FFF7ED", "border": "#FED7AA",
         "primary": "#F97316", "primary_hover": "#EA580C",
         "secondary": "#78716C", "accent": "#EF4444"},
        {**_NOTR_DARK, "background": "#1C1917", "surface": "#292524", "border": "#44403C",
         "primary": "#FB923C", "primary_hover": "#F97316",
         "secondary": "#A8A29E", "accent": "#F87171", "text_secondary": "#D6D3D1"},
    ),
    # ── Gece Yarısı (mor) ──
    _tema(
        "gece_yarisi", "Gece Yarısı", "Zarif mor tonları, gece dostu", "hazir", None,
        {**_NOTR_LIGHT, "background": "#FAF5FF", "border": "#E9D5FF",
         "primary": "#7C3AED", "primary_hover": "#6D28D9",
         "secondary": "#6B7280", "accent": "#A855F7"},
        {**_NOTR_DARK, "background": "#1E1B2E", "surface": "#2A2540", "border": "#4C1D95",
         "primary": "#A78BFA", "primary_hover": "#8B5CF6",
         "secondary": "#9CA3AF", "accent": "#C084FC", "text_secondary": "#C4B5FD"},
    ),
    # ── Öğrenci Cream — ÖĞRENCİ ROL VARSAYILANI (mevcut sıcak/cream palet) ──
    _tema(
        "ogrenci_cream", "Öğrenci Cream", "Sıcak, çocuk dostu krem tonları", "rol_default", "student",
        {"background": "#FFFBEB", "surface": "#FFFEF9",
         "text": "#422006", "text_secondary": "#78716C", "border": "#FDE68A",
         "primary": "#F59E0B", "primary_hover": "#D97706",
         "secondary": "#92826B", "accent": "#FB923C",
         "danger": "#DC2626", "success": "#16A34A", "warning": "#D97706"},
        {**_NOTR_DARK, "background": "#1C1917", "surface": "#292524", "border": "#44403C",
         "primary": "#FBBF24", "primary_hover": "#F59E0B",
         "secondary": "#A8A29E", "accent": "#FCD34D", "text": "#FEF3C7", "text_secondary": "#D6D3D1"},
    ),
]

# Sistem geneli varsayılan tema kodu (kullanıcı/rol tercihi yoksa)
SISTEM_VARSAYILAN_TEMA = "deniz"

# Rol → varsayılan tema kodu (kullanıcı tercihi yoksa)
ROL_VARSAYILAN_TEMA = {
    "student": "ogrenci_cream",
}


def tema_getir(kod):
    return next((t for t in TEMALAR if t["kod"] == kod), None)
