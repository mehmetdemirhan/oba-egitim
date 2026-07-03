import React from "react";

/** Bir temanın renk önizlemesi + eylemleri. */
const ONIZLEME = ["primary", "surface", "background", "accent", "success", "danger"];
const KATEGORI_RENK = {
  hazir: "bg-blue-100 text-blue-700",
  rol_default: "bg-purple-100 text-purple-700",
  ozel: "bg-gray-100 text-gray-700",
};

export default function TemaKarti({ tema, aktifMi, onDuzenle, onSil, onAktifYap }) {
  const light = tema?.modlar?.light || {};
  const silinemez = ["hazir", "rol_default"].includes(tema?.kategori);
  return (
    <div className={`rounded-xl border p-3 bg-white ${aktifMi ? "ring-2 ring-blue-400 border-blue-300" : "border-gray-200"}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-gray-800">{tema?.ad}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${KATEGORI_RENK[tema?.kategori] || KATEGORI_RENK.ozel}`}>
            {tema?.kategori}
          </span>
          {aktifMi && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 text-green-700">sistem aktif</span>}
        </div>
      </div>
      {/* Renk önizleme daireleri */}
      <div className="flex items-center gap-1.5 mb-2">
        {ONIZLEME.map((t) => (
          <span key={t} title={t} className="w-6 h-6 rounded-full border border-gray-200"
                style={{ backgroundColor: light[t] || "#ccc" }} />
        ))}
        {tema?.hedef_rol && <span className="text-[10px] text-gray-400 ml-1">rol: {tema.hedef_rol}</span>}
      </div>
      {tema?.aciklama && <p className="text-[11px] text-gray-500 mb-2 line-clamp-1">{tema.aciklama}</p>}
      <div className="flex items-center gap-2">
        <button onClick={() => onDuzenle?.(tema)} className="text-[11px] text-blue-600 hover:underline">Düzenle</button>
        {!aktifMi && <button onClick={() => onAktifYap?.(tema)} className="text-[11px] text-green-600 hover:underline">Sistem aktif yap</button>}
        {!silinemez && <button onClick={() => onSil?.(tema)} className="text-[11px] text-red-500 hover:underline ml-auto">Sil</button>}
      </div>
    </div>
  );
}
