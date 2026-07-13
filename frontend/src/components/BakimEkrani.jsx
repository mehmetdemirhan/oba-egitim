import React from "react";
import { Wrench, Clock } from "lucide-react";

/**
 * BakimEkrani — bakım açıkken admin-dışı kullanıcılara gösterilen şık, sakin,
 * kurumsal ekran (hata görünümü değil). Props: mesaj, tahminiBitis, onYonetici(opsiyonel).
 */
export default function BakimEkrani({ mesaj, tahminiBitis, onYonetici }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100 p-6">
      <div className="max-w-md w-full bg-white rounded-3xl shadow-xl border border-slate-200 p-8 text-center">
        <div className="mx-auto w-16 h-16 rounded-2xl bg-amber-100 flex items-center justify-center mb-5">
          <Wrench className="h-8 w-8 text-amber-600" />
        </div>
        <h1 className="text-xl font-bold text-slate-800 mb-3">Kısa bir bakımdayız</h1>
        <p className="text-slate-600 leading-relaxed">
          {mesaj || "Sistemimiz kısa bir bakımdan geçiyor. En kısa sürede tekrar hizmetinizdeyiz. Anlayışınız için teşekkür ederiz."}
        </p>
        {tahminiBitis && (
          <div className="mt-5 inline-flex items-center gap-2 text-sm text-slate-500 bg-slate-50 rounded-full px-4 py-1.5">
            <Clock className="h-4 w-4" />Tahmini bitiş: <b className="text-slate-700">{tahminiBitis}</b>
          </div>
        )}
        {onYonetici && (
          <button onClick={onYonetici}
                  className="block mx-auto mt-8 text-xs text-slate-400 hover:text-slate-600 underline">
            Yönetici girişi
          </button>
        )}
      </div>
    </div>
  );
}
