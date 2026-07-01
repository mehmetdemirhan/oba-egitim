import React, { useEffect, useState } from "react";
import axios from "axios";

/**
 * InstagramAyarlari — yönetici: manuel senkronizasyon, son senkron tarihi,
 * toplam post ve widget aktif/pasif toggle.
 *
 * Props: apiBase — `${BACKEND_URL}/api`
 */
function tarihUzun(s) {
  if (!s) return "Henüz senkronize edilmedi";
  try { return new Date(s).toLocaleString("tr-TR"); } catch { return "—"; }
}

export default function InstagramAyarlari({ apiBase }) {
  const [durum, setDurum] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [senkronIsliyor, setSenkronIsliyor] = useState(false);
  const [toast, setToast] = useState(null);

  const toastGoster = (tip, metin) => { setToast({ tip, metin }); setTimeout(() => setToast(null), 4000); };

  const getir = async () => {
    setYukleniyor(true);
    try {
      const r = await axios.get(`${apiBase}/instagram/durum`);
      setDurum(r.data);
    } catch { toastGoster("hata", "Durum yüklenemedi."); }
    finally { setYukleniyor(false); }
  };

  useEffect(() => { getir(); /* eslint-disable-next-line */ }, []);

  const senkronize = async () => {
    setSenkronIsliyor(true);
    try {
      const r = await axios.post(`${apiBase}/instagram/senkronize`);
      toastGoster("ok", `✅ ${r.data.yeni} yeni, ${r.data.mevcut} mevcut post. Toplam: ${r.data.toplam}`);
      getir();
    } catch (e) {
      toastGoster("hata", e?.response?.status === 503
        ? "Instagram beslemesi (RSS servisi) şu an kullanılamıyor. Sonra tekrar deneyin."
        : "Senkronizasyon başarısız.");
    } finally { setSenkronIsliyor(false); }
  };

  const aktifDegistir = async () => {
    try {
      const r = await axios.put(`${apiBase}/instagram/durum`, { aktif: !durum?.aktif });
      setDurum(r.data);
    } catch { toastGoster("hata", "Değiştirilemedi."); }
  };

  if (yukleniyor) return <div className="text-center py-10 text-gray-400 text-sm">Yükleniyor…</div>;

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border shadow-sm p-5 space-y-4">
        <div>
          <h4 className="font-bold text-gray-800 flex items-center gap-2">📱 Instagram Beslemesi</h4>
          <p className="text-sm text-gray-500">@dogadakiogretmenim paylaşımları öğretmen dashboard'ında gösterilir.</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-50 rounded-xl p-3">
            <div className="text-xs text-gray-400">Toplam Paylaşım</div>
            <div className="text-2xl font-bold text-gray-800">{durum?.toplam_post ?? 0}</div>
          </div>
          <div className="bg-gray-50 rounded-xl p-3">
            <div className="text-xs text-gray-400">Son Senkronizasyon</div>
            <div className="text-sm font-medium text-gray-700 mt-1">{tarihUzun(durum?.son_senkron)}</div>
          </div>
        </div>

        <div className="flex items-center justify-between bg-gray-50 rounded-xl p-3">
          <div>
            <div className="text-sm font-medium text-gray-700">Widget Görünürlüğü</div>
            <div className="text-xs text-gray-400">Öğretmenlere gösterilsin mi?</div>
          </div>
          <button onClick={aktifDegistir}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold ${durum?.aktif ? "bg-green-100 text-green-700" : "bg-gray-200 text-gray-500"}`}>
            {durum?.aktif ? "✓ Aktif" : "Pasif"}
          </button>
        </div>

        <button onClick={senkronize} disabled={senkronIsliyor}
          className="w-full px-4 py-2.5 rounded-xl bg-gradient-to-r from-pink-500 to-orange-400 text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50">
          {senkronIsliyor ? "Senkronize ediliyor…" : "🔄 Şimdi Senkronize Et"}
        </button>
        <p className="text-[11px] text-gray-400 text-center">
          RSS köprüsü (RSSHub/rss.app) 3. parti servistir; geçici olarak kapalı olabilir.
        </p>
      </div>

      {toast && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-[80] px-4 py-2 rounded-xl text-sm font-medium shadow-lg ${toast.tip === "ok" ? "bg-green-600 text-white" : "bg-red-600 text-white"}`}>
          {toast.metin}
        </div>
      )}
    </div>
  );
}
