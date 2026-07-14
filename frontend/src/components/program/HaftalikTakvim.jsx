import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import YeniDersModal from "./YeniDersModal";
import DersDetayModal from "./DersDetayModal";

/**
 * HaftalikTakvim — Google Calendar tarzı haftalık ders programı.
 *
 * 7 sütun (Pzt–Paz), 08:00–22:00 saat dilimleri. Dersler renk kodludur:
 *   planlı (mavi), katıldı (yeşil), katılmadı (kırmızı), iptal (gri).
 * Boş slot → "Yeni Ders" modalı; dolu ders → "Ders Detayı" modalı.
 *
 * Props:
 *   apiBase     — `${BACKEND_URL}/api`
 *   user        — aktif kullanıcı (rol)
 *   ogrenciler  — [{id, ad, soyad}] (yeni ders dropdown'u)
 *   ogretmenler — [{id, ad, soyad}] (admin/coordinator: filtre + atama)
 */
const GUNLER = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
const SAATLER = Array.from({ length: 14 }, (_, i) => i + 8); // 08..21
const RENK = {
  planli: "bg-blue-100 text-blue-700 border-blue-300",
  katildi: "bg-green-100 text-green-700 border-green-300",
  katilmadi: "bg-red-100 text-red-700 border-red-300",
  iptal: "bg-gray-100 text-gray-400 border-gray-200 line-through",
};

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const pazartesi = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); const g = (x.getDay() + 6) % 7; x.setDate(x.getDate() - g); return x; };
const ekleGun = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

export default function HaftalikTakvim({ apiBase, user, ogrenciler = [], ogretmenler = [] }) {
  const yonetici = user?.role === "admin" || user?.role === "coordinator";
  const [haftaRef, setHaftaRef] = useState(() => pazartesi(new Date()));
  const [dersler, setDersler] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [seciliOgretmen, setSeciliOgretmen] = useState("");
  const [yeniModal, setYeniModal] = useState(null); // {tarih, saat}
  const [detay, setDetay] = useState(null);        // ders objesi

  const gunTarihleri = useMemo(() => Array.from({ length: 7 }, (_, i) => iso(ekleGun(haftaRef, i))), [haftaRef]);
  const bugun = iso(new Date());

  const yukle = useCallback(async () => {
    setYukleniyor(true);
    try {
      const params = { baslangic: gunTarihleri[0], bitis: gunTarihleri[6] };
      if (yonetici && seciliOgretmen) params.ogretmen_id = seciliOgretmen;
      const r = await axios.get(`${apiBase}/ders/program`, { params });
      setDersler(r.data?.dersler || []);
    } catch (e) {
      setDersler([]);
    } finally {
      setYukleniyor(false);
    }
  }, [apiBase, gunTarihleri, yonetici, seciliOgretmen]);

  useEffect(() => { yukle(); }, [yukle]);

  // (tarih|saat) → ders listesi
  const haritala = useMemo(() => {
    const m = {};
    for (const d of dersler) {
      const sa = parseInt((d.baslangic_saati || "0").split(":")[0], 10);
      const k = `${d.tarih}|${sa}`;
      (m[k] = m[k] || []).push(d);
    }
    return m;
  }, [dersler]);

  const haftaEtiketi = `${new Date(gunTarihleri[0]).toLocaleDateString("tr-TR", { day: "numeric", month: "short" })} – ${new Date(gunTarihleri[6]).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" })}`;

  return (
    <div className="space-y-3">
      {/* Üst kontrol */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1">
          <button onClick={() => setHaftaRef((d) => ekleGun(d, -7))} className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-sm hover:bg-gray-50">‹</button>
          <button onClick={() => setHaftaRef(pazartesi(new Date()))} className="px-3 py-1.5 rounded-lg border border-gray-200 text-sm hover:bg-gray-50">Bugün</button>
          <button onClick={() => setHaftaRef((d) => ekleGun(d, 7))} className="px-2.5 py-1.5 rounded-lg border border-gray-200 text-sm hover:bg-gray-50">›</button>
        </div>
        <div className="text-sm font-semibold text-gray-700">{haftaEtiketi}</div>
        {yonetici && (
          <select value={seciliOgretmen} onChange={(e) => setSeciliOgretmen(e.target.value)}
            className="ml-auto px-2 py-1.5 rounded-lg border border-gray-200 text-sm bg-white">
            <option value="">Tüm öğretmenler</option>
            {ogretmenler.map((o) => <option key={o.id} value={o.id}>{`${o.ad || ""} ${o.soyad || ""}`.trim()}</option>)}
          </select>
        )}
        {yukleniyor && <span className="text-xs text-gray-400">yükleniyor…</span>}
      </div>

      {/* Açıklama (renk lejantı) */}
      <div className="flex flex-wrap gap-3 text-xs text-gray-500">
        {[["planli", "Planlı"], ["katildi", "Katıldı"], ["katilmadi", "Katılmadı"], ["iptal", "İptal"]].map(([k, l]) => (
          <span key={k} className="flex items-center gap-1"><span className={`w-3 h-3 rounded border ${RENK[k]}`} />{l}</span>
        ))}
      </div>

      {/* Takvim ızgarası */}
      <div className="overflow-x-auto bg-white rounded-2xl border border-gray-100 shadow-sm">
        <div className="grid min-w-[760px]" style={{ gridTemplateColumns: "56px repeat(7, minmax(100px, 1fr))" }}>
          {/* Başlık satırı */}
          <div className="border-b border-gray-100" />
          {GUNLER.map((g, i) => {
            const t = gunTarihleri[i];
            const bugunMu = t === bugun;
            return (
              <div key={i} className={`border-b border-l border-gray-100 px-1 py-2 text-center ${bugunMu ? "bg-indigo-50" : ""}`}>
                <div className="text-xs font-semibold text-gray-600">{g}</div>
                <div className={`text-[11px] ${bugunMu ? "text-indigo-600 font-bold" : "text-gray-400"}`}>{new Date(t).getDate()}</div>
              </div>
            );
          })}

          {/* Saat satırları */}
          {SAATLER.map((saat) => (
            <React.Fragment key={saat}>
              <div className="border-b border-gray-50 text-[11px] text-gray-400 text-right pr-1 pt-1">{String(saat).padStart(2, "0")}:00</div>
              {gunTarihleri.map((t, ci) => {
                const liste = haritala[`${t}|${saat}`] || [];
                return (
                  <div key={ci} onClick={() => liste.length === 0 && setYeniModal({ tarih: t, saat: `${String(saat).padStart(2, "0")}:00` })}
                    className={`relative border-b border-l border-gray-50 min-h-[44px] p-0.5 ${liste.length === 0 ? "cursor-pointer hover:bg-gray-50/60" : ""}`}>
                    {liste.map((d) => (
                      <button key={d.id} onClick={(e) => { e.stopPropagation(); setDetay(d); }}
                        className={`block w-full text-left mb-0.5 px-1.5 py-1 rounded-md border text-[11px] leading-tight ${RENK[d.durum] || RENK.planli}`}>
                        <div className="font-semibold truncate">{d.ogrenci_ad}</div>
                        <div className="opacity-80">{d.baslangic_saati}-{d.bitis_saati}</div>
                      </button>
                    ))}
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>

      {yeniModal && (
        <YeniDersModal apiBase={apiBase} user={user} ogrenciler={ogrenciler} ogretmenler={ogretmenler}
          varsayilan={yeniModal} onKapat={() => setYeniModal(null)} onKaydedildi={yukle} />
      )}
      {detay && (
        <DersDetayModal apiBase={apiBase} ders={detay} ogrenciler={ogrenciler} onKapat={() => setDetay(null)} onGuncellendi={yukle} />
      )}
    </div>
  );
}
