import React from "react";
import { Star, Film, BookOpen, Play, ExternalLink } from "lucide-react";

/**
 * MedyaKart — film/kitap için estetik afişli kart (afiş/kapak + ad + puan rozeti +
 * kısa konu). Tasarım diliyle uyumlu; hem içerik havuzunda hem öğrenci görev detayında
 * kullanılır. Sunucuda saklanan görseller /api/... yolundadır → apiBase ile çözülür.
 *
 * Props:
 *   tur: "film" | "kitap"
 *   baslik, konu, gorsel (afiş/kapak URL), puan, yil, sure, yazar
 *   izleLink (film opsiyonel izleme linki), link (bilgi/kaynak linki)
 *   apiBase (görsel URL çözümü için), kompakt (küçük varyant)
 */
export default function MedyaKart({ tur = "film", baslik, konu, gorsel, puan, yil, sure, yazar, izleLink, link, apiBase = "", kompakt = false }) {
  const gorselUrl = !gorsel ? "" : (gorsel.startsWith("/api/") ? `${(apiBase || "").replace(/\/api$/, "")}${gorsel}` : gorsel);
  const Ikon = tur === "kitap" ? BookOpen : Film;
  const afisW = kompakt ? "w-16" : "w-24 sm:w-28";

  return (
    <div className="flex gap-3 rounded-2xl border border-line bg-surface shadow-sm overflow-hidden">
      {/* Afiş / kapak */}
      <div className={`${afisW} shrink-0 bg-gradient-to-br from-slate-200 to-slate-300 dark:from-slate-700 dark:to-slate-800 flex items-center justify-center relative`}>
        {gorselUrl ? (
          <img src={gorselUrl} alt={baslik} className="w-full h-full object-cover" loading="lazy"
               onError={(e) => { e.currentTarget.style.display = "none"; }} />
        ) : (
          <Ikon className="h-8 w-8 text-slate-400" />
        )}
        {puan && (
          <div className="absolute top-1 left-1 inline-flex items-center gap-0.5 bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full shadow">
            <Star className="h-2.5 w-2.5 fill-white" />{puan}
          </div>
        )}
      </div>

      {/* Bilgi */}
      <div className="flex-1 min-w-0 py-2.5 pr-3">
        <div className="flex items-center gap-1.5 text-[11px] text-subtle mb-0.5">
          <Ikon className="h-3 w-3" />{tur === "kitap" ? "Kitap" : "Film"}
          {yil && <span>• {yil}</span>}
          {sure && <span>• {sure}</span>}
          {yazar && <span className="truncate">• {yazar}</span>}
        </div>
        <div className="font-bold text-content text-sm leading-snug line-clamp-1">{baslik || "—"}</div>
        {konu && <p className={`text-xs text-subtle mt-1 ${kompakt ? "line-clamp-2" : "line-clamp-3"}`}>{konu}</p>}
        {(izleLink || link) && (
          <div className="flex items-center gap-2 mt-2">
            {izleLink && (
              <a href={izleLink} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-red-600 text-white text-xs font-semibold hover:bg-red-700">
                <Play className="h-3 w-3" />İzle
              </a>
            )}
            {link && (
              <a href={link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline">
                <ExternalLink className="h-3 w-3" />{tur === "kitap" ? "Detay" : "Film sayfası"}
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
