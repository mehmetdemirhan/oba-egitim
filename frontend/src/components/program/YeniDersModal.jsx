import React, { useMemo, useState } from "react";
import axios from "axios";

/**
 * YeniDersModal — tek seferlik ya da haftalık seri ders oluşturma.
 *
 * Props:
 *   apiBase     — `${BACKEND_URL}/api`
 *   user        — aktif kullanıcı (rol: teacher → öğretmen gizli/otomatik)
 *   ogrenciler  — [{id, ad, soyad}] öğrenci listesi (dropdown)
 *   ogretmenler — [{id, ad, soyad}] (yalnızca admin/coordinator için)
 *   varsayilan  — { tarih: "YYYY-MM-DD", saat: "HH:00" } tıklanan slot
 *   onKapat()   — modalı kapat
 *   onKaydedildi() — başarı sonrası (takvimi yenile)
 */
const GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];

function gunHesapla(isoTarih) {
  const [y, m, d] = (isoTarih || "").split("-").map(Number);
  if (!y) return 0;
  return (new Date(y, m - 1, d).getDay() + 6) % 7; // Pazartesi=0
}
function saatArti(hhmm, dakika) {
  const [h, m] = hhmm.split(":").map(Number);
  const t = h * 60 + m + dakika;
  return `${String(Math.floor(t / 60) % 24).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}

export default function YeniDersModal({ apiBase, user, ogrenciler = [], ogretmenler = [], varsayilan = {}, onKapat, onKaydedildi }) {
  const teacherRol = user?.role === "teacher";
  const baslangicSaati = varsayilan.saat || "15:00";

  const [tekrar, setTekrar] = useState("tek"); // tek | seri
  const [ogretmenId, setOgretmenId] = useState(teacherRol ? "" : (ogretmenler[0]?.id || ""));
  const [ogrenciId, setOgrenciId] = useState("");
  const [tarih, setTarih] = useState(varsayilan.tarih || "");
  const [gun, setGun] = useState(gunHesapla(varsayilan.tarih));
  const [bas, setBas] = useState(baslangicSaati);
  const [bit, setBit] = useState(saatArti(baslangicSaati, 60));
  const [bitisTarihi, setBitisTarihi] = useState("");
  const [not, setNot] = useState("");
  const [hata, setHata] = useState(null);
  const [kaydediyor, setKaydediyor] = useState(false);

  const ogrenciAd = (o) => `${o.ad || ""} ${o.soyad || ""}`.trim();

  const gecerli = useMemo(() => {
    if (!ogrenciId) return false;
    if (!teacherRol && !ogretmenId) return false;
    if (bit <= bas) return false;
    if (tekrar === "tek" && !tarih) return false;
    if (tekrar === "seri" && !tarih) return false;
    return true;
  }, [ogrenciId, ogretmenId, teacherRol, bit, bas, tekrar, tarih]);

  const kaydet = async () => {
    if (!gecerli || kaydediyor) return;
    setKaydediyor(true);
    setHata(null);
    try {
      if (tekrar === "tek") {
        await axios.post(`${apiBase}/ders/oturum`, {
          ogrenci_id: ogrenciId, tarih, baslangic_saati: bas, bitis_saati: bit,
          not, ...(teacherRol ? {} : { ogretmen_id: ogretmenId }),
        });
      } else {
        await axios.post(`${apiBase}/ders/seri`, {
          ogrenci_id: ogrenciId, gun, baslangic_saati: bas, bitis_saati: bit,
          baslangic_tarihi: tarih, bitis_tarihi: bitisTarihi || null, not,
          ...(teacherRol ? {} : { ogretmen_id: ogretmenId }),
        });
      }
      onKaydedildi?.();
      onKapat?.();
    } catch (e) {
      const st = e?.response?.status;
      setHata(st === 409 ? (e.response.data?.detail || "Çakışma var.")
        : st === 400 ? (e.response.data?.detail || "Geçersiz bilgi.")
        : "Ders kaydedilemedi.");
    } finally {
      setKaydediyor(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4" onClick={onKapat}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          <div className="font-bold text-gray-800">📅 Yeni Ders</div>
          <button onClick={onKapat} className="text-gray-400 hover:text-gray-700 text-lg">✕</button>
        </div>

        <div className="p-5 space-y-3">
          {/* Tekrar tipi */}
          <div className="flex gap-2">
            {[{ v: "tek", l: "Tek seferlik" }, { v: "seri", l: "Haftalık seri" }].map((t) => (
              <button key={t.v} onClick={() => setTekrar(t.v)}
                className={`flex-1 px-3 py-2 rounded-xl text-sm font-medium border ${tekrar === t.v ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-600 border-gray-200"}`}>
                {t.l}
              </button>
            ))}
          </div>

          {/* Öğretmen (admin) */}
          {!teacherRol && (
            <label className="block text-xs text-gray-600">
              Öğretmen
              <select value={ogretmenId} onChange={(e) => setOgretmenId(e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white">
                <option value="">Seçin…</option>
                {ogretmenler.map((o) => <option key={o.id} value={o.id}>{ogrenciAd(o)}</option>)}
              </select>
            </label>
          )}

          {/* Öğrenci */}
          <label className="block text-xs text-gray-600">
            Öğrenci
            <select value={ogrenciId} onChange={(e) => setOgrenciId(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white">
              <option value="">Seçin…</option>
              {ogrenciler.map((o) => <option key={o.id} value={o.id}>{ogrenciAd(o)}</option>)}
            </select>
          </label>

          {/* Seri ise gün seçimi */}
          {tekrar === "seri" && (
            <label className="block text-xs text-gray-600">
              Haftanın günü
              <select value={gun} onChange={(e) => setGun(Number(e.target.value))}
                className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white">
                {GUNLER.map((g, i) => <option key={i} value={i}>{g}</option>)}
              </select>
            </label>
          )}

          {/* Tarih */}
          <label className="block text-xs text-gray-600">
            {tekrar === "seri" ? "Başlangıç tarihi (ilk hafta)" : "Tarih"}
            <input type="date" value={tarih} onChange={(e) => { setTarih(e.target.value); if (tekrar === "seri") setGun(gunHesapla(e.target.value)); }}
              className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" />
          </label>

          {/* Saatler */}
          <div className="flex gap-2">
            <label className="flex-1 text-xs text-gray-600">
              Başlangıç
              <input type="time" step="900" value={bas} onChange={(e) => setBas(e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" />
            </label>
            <label className="flex-1 text-xs text-gray-600">
              Bitiş
              <input type="time" step="900" value={bit} onChange={(e) => setBit(e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" />
            </label>
          </div>

          {/* Seri bitiş tarihi (opsiyonel) */}
          {tekrar === "seri" && (
            <label className="block text-xs text-gray-600">
              Bitiş tarihi (opsiyonel — boş = süresiz)
              <input type="date" value={bitisTarihi} onChange={(e) => setBitisTarihi(e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" />
            </label>
          )}

          <label className="block text-xs text-gray-600">
            Not (opsiyonel)
            <input value={not} onChange={(e) => setNot(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" />
          </label>

          {hata && <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-600">{hata}</div>}

          <div className="flex justify-end gap-2 pt-1">
            <button onClick={onKapat} className="px-4 py-2 rounded-xl border border-gray-200 text-sm text-gray-600">Vazgeç</button>
            <button onClick={kaydet} disabled={!gecerli || kaydediyor}
              className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold disabled:opacity-40 hover:bg-indigo-700">
              {kaydediyor ? "Kaydediliyor…" : "Kaydet"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
