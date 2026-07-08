// ── Rozet/Hedef ikon çözücü + admin ikon-seçici kaynağı (Faz A + B) ─────────
// Tek doğruluk kaynağı: hem App.js resolver'ı (IkonCoz) hem RozetFormu picker'ı
// (IKON_SECENEKLERI) buradan beslenir.
//
// DB'de ikon iki biçimde olabilir:
//   • Eski kayıtlar → emoji ("🧠")           → EMOJI_AD ile Lucide adına çevrilir
//   • Yeni/düzenlenen kayıtlar → Lucide adı  ("Brain") → doğrudan bileşene çözülür
// Bilinmeyen değer → Award fallback. Veri MİGRASYONU YOK; resolver iki türü de çözer.
import React from "react";
import {
  Award, Book, BookOpen, Brain, Bug, Castle, CheckCircle, ClipboardList,
  Crosshair, Crown, Dumbbell, Eye, Flame, Gem, GraduationCap, Heart, Home,
  Landmark, Leaf, Library, Lightbulb, Link, Map as MapIcon, Medal, MessageCircle,
  Mountain, PenLine, Pin, Rocket, Search, Shield, Sparkles, Sprout, Star, Target,
  ThumbsUp, TreePine, Trophy, Users, Vote, Zap,
} from "lucide-react";

// Ad → Lucide bileşeni (picker'ın seçenek kümesi + resolver'ın ad çözümü)
export const LUCIDE_IKON_HARITA = {
  Award, Book, BookOpen, Brain, Bug, Castle, CheckCircle, ClipboardList,
  Crosshair, Crown, Dumbbell, Eye, Flame, Gem, GraduationCap, Heart, Home,
  Landmark, Leaf, Library, Lightbulb, Link, Map: MapIcon, Medal, MessageCircle,
  Mountain, PenLine, Pin, Rocket, Search, Shield, Sparkles, Sprout, Star, Target,
  ThumbsUp, TreePine, Trophy, Users, Vote, Zap,
};

// Emoji → Lucide adı (geriye dönük uyumluluk; kod noktaları DB ile birebir)
export const EMOJI_AD = {
  "✅": "CheckCircle", "✍️": "PenLine", "⭐": "Star", "🌉": "Link", "🌟": "Sparkles",
  "🌱": "Sprout", "🌳": "TreePine", "🌿": "Leaf", "🎓": "GraduationCap", "🎖️": "Medal",
  "🎯": "Target", "🏅": "Award", "🏔️": "Mountain", "🏛️": "Landmark", "🏠": "Home",
  "🏰": "Castle", "🏹": "Crosshair", "🐛": "Bug", "👁️": "Eye", "👍": "ThumbsUp",
  "👑": "Crown", "💎": "Gem", "💜": "Heart", "💡": "Lightbulb", "💪": "Dumbbell",
  "💫": "Sparkles", "💬": "MessageCircle", "📋": "ClipboardList", "📌": "Pin", "📕": "Book",
  "📖": "BookOpen", "📚": "Library", "🔍": "Search", "🔥": "Flame", "🗳️": "Vote",
  "🗺️": "Map", "🚀": "Rocket", "🛡️": "Shield", "🥇": "Medal", "🥈": "Medal",
  "🦸": "Zap", "🧠": "Brain", "👥": "Users",
};

// deger (emoji VEYA Lucide adı) → Lucide bileşeni. Eşleşme yoksa Award.
export function ikonBilesen(deger) {
  if (!deger) return Award;
  if (LUCIDE_IKON_HARITA[deger]) return LUCIDE_IKON_HARITA[deger];      // Lucide adı
  const ad = EMOJI_AD[deger];
  if (ad && LUCIDE_IKON_HARITA[ad]) return LUCIDE_IKON_HARITA[ad];      // emoji → ad
  return Award;                                                          // fallback
}

// Render bileşeni — ham emoji basmaz, tutarlı ikon dili korunur.
export function IkonCoz({ deger, className = "w-5 h-5", fallback: Fallback }) {
  const Comp = (deger && (LUCIDE_IKON_HARITA[deger]
    || (EMOJI_AD[deger] && LUCIDE_IKON_HARITA[EMOJI_AD[deger]]))) || Fallback || Award;
  return <Comp className={className} aria-hidden="true" />;
}

// Admin ikon-seçici için: {ad, etiket} listesi (arama + tooltip). Sıra = curated.
export const IKON_SECENEKLERI = [
  { ad: "Star", etiket: "Yıldız" },
  { ad: "Award", etiket: "Madalya / Ödül" },
  { ad: "Medal", etiket: "Madalya" },
  { ad: "Trophy", etiket: "Kupa" },
  { ad: "Crown", etiket: "Taç" },
  { ad: "Gem", etiket: "Elmas" },
  { ad: "Sparkles", etiket: "Parıltı" },
  { ad: "Zap", etiket: "Şimşek / Süper" },
  { ad: "Rocket", etiket: "Roket" },
  { ad: "Target", etiket: "Hedef" },
  { ad: "Crosshair", etiket: "Nişan" },
  { ad: "CheckCircle", etiket: "Onay" },
  { ad: "ThumbsUp", etiket: "Beğeni" },
  { ad: "Heart", etiket: "Kalp" },
  { ad: "Flame", etiket: "Alev / Alışkanlık" },
  { ad: "Lightbulb", etiket: "Fikir / İlham" },
  { ad: "Brain", etiket: "Beyin" },
  { ad: "Search", etiket: "Merak / Arama" },
  { ad: "Eye", etiket: "Göz" },
  { ad: "Book", etiket: "Kitap" },
  { ad: "BookOpen", etiket: "Açık Kitap" },
  { ad: "Library", etiket: "Kütüphane" },
  { ad: "Bug", etiket: "Kitap Kurdu" },
  { ad: "GraduationCap", etiket: "Mezuniyet / Uzman" },
  { ad: "PenLine", etiket: "Yazı / İçerik" },
  { ad: "ClipboardList", etiket: "Liste / Editör" },
  { ad: "Pin", etiket: "Raptiye / Görev" },
  { ad: "MessageCircle", etiket: "Mesaj" },
  { ad: "Link", etiket: "Köprü / Bağlantı" },
  { ad: "Vote", etiket: "Oy" },
  { ad: "Shield", etiket: "Kalkan / Kalite" },
  { ad: "Dumbbell", etiket: "Güç / Kararlılık" },
  { ad: "Users", etiket: "Kullanıcılar" },
  { ad: "Home", etiket: "Ev / Aile" },
  { ad: "Landmark", etiket: "Kurum / Bilgi" },
  { ad: "Castle", etiket: "Kale" },
  { ad: "Mountain", etiket: "Dağ / İrade" },
  { ad: "Map", etiket: "Harita / Kâşif" },
  { ad: "Sprout", etiket: "Fidan / İlk Adım" },
  { ad: "Leaf", etiket: "Yaprak" },
  { ad: "TreePine", etiket: "Ağaç / Orman" },
].filter((o) => LUCIDE_IKON_HARITA[o.ad]);
