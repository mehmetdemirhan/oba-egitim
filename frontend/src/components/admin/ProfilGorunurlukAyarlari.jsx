import React, { useEffect, useState } from "react";
import axios from "axios";

/**
 * ProfilGorunurlukAyarlari — yönetici, öğretmen profil alanlarının kimler
 * tarafından görülebileceğini ayarlar. (Ayarlar → Öğretmen Profil Görünürlüğü)
 *
 * Props: apiBase — `${BACKEND_URL}/api`
 */
const ALAN_ETIKET = {
  profil_fotografi: "Profil Fotoğrafı",
  dogum_tarihi: "Doğum Tarihi",
  adres: "Adres",
  sehir: "Şehir",
  kisa_biyografi: "Kısa Biyografi",
  egitim_gecmisi: "Eğitim Geçmişi",
  deneyim_yili: "Deneyim Yılı",
  sertifikalar: "Sertifikalar",
  katilim_tarihi: "Katılım Tarihi",
  bildirim_tercihleri: "Bildirim Tercihleri",
};

const SECENEKLER = [
  { v: "herkes", l: "Herkes" },
  { v: "veli", l: "Veli" },
  { v: "admin", l: "Sadece Yönetici" },
];

export default function ProfilGorunurlukAyarlari({ apiBase }) {
  const [ayarlar, setAyarlar] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [toast, setToast] = useState(null);

  const toastGoster = (tip, metin) => { setToast({ tip, metin }); setTimeout(() => setToast(null), 3000); };

  useEffect(() => {
    let iptal = false;
    (async () => {
      setYukleniyor(true);
      try {
        const r = await axios.get(`${apiBase}/admin/profil-gorunurluk`);
        if (!iptal) setAyarlar(r.data?.ayarlar || {});
      } catch (e) {
        if (!iptal) toastGoster("hata", "Ayarlar yüklenemedi.");
      } finally {
        if (!iptal) setYukleniyor(false);
      }
    })();
    return () => { iptal = true; };
  }, [apiBase]);

  const degis = (alan, deger) => setAyarlar((a) => ({ ...a, [alan]: deger }));

  const kaydet = async () => {
    setKaydediliyor(true);
    try {
      // bildirim_tercihleri hariç (sadece_kendisi, düzenlenemez)
      const gonder = {};
      for (const k of Object.keys(ALAN_ETIKET)) {
        if (k !== "bildirim_tercihleri" && ayarlar[k]) gonder[k] = ayarlar[k];
      }
      const r = await axios.put(`${apiBase}/admin/profil-gorunurluk`, { ayarlar: gonder });
      setAyarlar(r.data?.ayarlar || ayarlar);
      toastGoster("ok", "✅ Görünürlük ayarları kaydedildi");
    } catch (e) {
      toastGoster("hata", "Kaydedilemedi.");
    } finally {
      setKaydediliyor(false);
    }
  };

  if (yukleniyor) return <div className="text-center py-12 text-gray-400 text-sm">Yükleniyor…</div>;
  if (!ayarlar) return <div className="text-center py-12 text-gray-400 text-sm">Ayarlar yüklenemedi.</div>;

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl shadow-sm border overflow-hidden">
        <div className="px-5 py-3 border-b bg-gray-50">
          <h4 className="font-bold text-gray-800">👁️ Öğretmen Profil Görünürlüğü</h4>
          <p className="text-xs text-gray-500 mt-0.5">Her alanın veli/öğrenci tarafında kimlere görüneceğini belirleyin.</p>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400 border-b">
              <th className="px-5 py-2 font-semibold">Alan</th>
              <th className="px-5 py-2 font-semibold">Kim Görebilir?</th>
            </tr>
          </thead>
          <tbody>
            {Object.keys(ALAN_ETIKET).map((alan) => (
              <tr key={alan} className="border-b border-gray-50 last:border-0">
                <td className="px-5 py-2.5 text-gray-700">{ALAN_ETIKET[alan]}</td>
                <td className="px-5 py-2.5">
                  {alan === "bildirim_tercihleri" ? (
                    <span className="text-xs text-gray-400 italic">(Sadece kendisi)</span>
                  ) : (
                    <select value={ayarlar[alan] || "admin"} onChange={(e) => degis(alan, e.target.value)}
                      className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm bg-white outline-none focus:border-indigo-400">
                      {SECENEKLER.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
                    </select>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button onClick={kaydet} disabled={kaydediliyor}
        className="px-5 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-60">
        {kaydediliyor ? "Kaydediliyor…" : "💾 Kaydet"}
      </button>

      {toast && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl text-sm font-medium shadow-lg ${toast.tip === "ok" ? "bg-green-600 text-white" : "bg-red-600 text-white"}`}>
          {toast.metin}
        </div>
      )}
    </div>
  );
}
