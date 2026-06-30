import React from "react";

/**
 * ExerciseSkeleton — egzersiz içeriği yüklenirken gösterilen iskelet (placeholder).
 *
 * "İçerik yükleniyor…" metni yerine, tipin puanlama biçimine göre kabaca egzersiz
 * düzenini taklit eden gri animasyonlu (animate-pulse) kutular gösterir. Böylece
 * algılanan bekleme süresi kısalır ve düzen kaymadan oturuma geçilir.
 *
 * Props:
 *   puanlama — seçili tipin puanlama biçimi ("secmeli" | "eslesme" | "sira" | "serbest")
 *   ad       — seçili tip adı (başlık iskeletinde gösterilir)
 *   ikon     — seçili tip ikonu
 */
const cizgi = "rounded bg-gray-200";

function SecmeliIskelet() {
  return (
    <div className="space-y-3">
      <div className={`h-6 w-3/4 ${cizgi}`} />
      <div className="grid gap-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-100">
            <div className={`w-6 h-6 ${cizgi}`} />
            <div className={`h-4 ${cizgi}`} style={{ width: `${70 - i * 8}%` }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function EslesmeIskelet() {
  return (
    <div className="space-y-4">
      <div className={`h-9 w-32 ${cizgi}`} />
      <div className="grid gap-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={`h-11 ${cizgi}`} />
        ))}
      </div>
    </div>
  );
}

function SiraIskelet() {
  return (
    <div className="space-y-4">
      <div className={`h-4 w-2/3 ${cizgi}`} />
      <div className="min-h-[3rem] rounded-xl border border-dashed border-gray-200 p-3 flex flex-wrap gap-2">
        {[60, 40, 80].map((w, i) => (
          <div key={i} className={`h-7 ${cizgi}`} style={{ width: `${w}px` }} />
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {[70, 50, 90, 60, 75].map((w, i) => (
          <div key={i} className={`h-9 ${cizgi}`} style={{ width: `${w}px` }} />
        ))}
      </div>
    </div>
  );
}

export default function ExerciseSkeleton({ puanlama = "secmeli", ad = "", ikon = "📝" }) {
  let Icerik = SecmeliIskelet;
  if (puanlama === "eslesme") Icerik = EslesmeIskelet;
  else if (puanlama === "sira") Icerik = SiraIskelet;

  return (
    <div className="space-y-3 animate-pulse" aria-busy="true" aria-label="İçerik yükleniyor">
      {/* Üst bar (başlık + ilerleme iskeleti) */}
      <div className="flex items-center justify-between">
        <div className={`h-4 w-10 ${cizgi}`} />
        <div className="text-sm font-semibold text-gray-300 flex items-center gap-1">
          <span>{ikon}</span>
          <span>{ad || "Hazırlanıyor…"}</span>
        </div>
        <div className={`h-4 w-8 ${cizgi}`} />
      </div>
      {/* İlerleme çubuğu iskeleti */}
      <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
        <div className="h-full w-1/4 bg-gray-200" />
      </div>
      {/* Soru gövdesi iskeleti */}
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        <Icerik />
      </div>
      <div className="text-center text-xs text-gray-300">İçerik hazırlanıyor…</div>
    </div>
  );
}
