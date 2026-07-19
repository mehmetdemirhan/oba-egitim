import React, { useState } from "react";
import axios from "axios";

/**
 * DersDetayModal — bir ders oturumunun detayı + eylemleri.
 *
 * Eylemler (öğretmen/admin):
 *   - Saati Değiştir (taşı): tarih+saat + SEBEP zorunlu
 *   - Yoklama Gir: katıldı / katılmadı / iptal + not
 *   - (seri ise) Seriyi Sonlandır: sebep zorunlu
 *
 * Planlı (henüz DB'de olmayan) dersler için id "seri:{seri_id}:{tarih}" sanal
 * referansıdır; backend ilk eylemde otomatik materyalize eder.
 *
 * Props: apiBase, ders, onKapat, onGuncellendi
 */
const DURUM_ETIKET = { planli: "Planlı", katildi: "Katıldı", katilmadi: "Katılmadı", iptal: "İptal" };

export default function DersDetayModal({ apiBase, ders, ogrenciler = [], onKapat, onGuncellendi }) {
  const [mod, setMod] = useState(null); // null | "tasi" | "yoklama" | "seri-iptal" | "ogrenci" | "kalici-sil"
  const [tarih, setTarih] = useState(ders.tarih);
  const [bas, setBas] = useState(ders.baslangic_saati);
  const [bit, setBit] = useState(ders.bitis_saati);
  const [sebep, setSebep] = useState("");
  const [yeniOgrenci, setYeniOgrenci] = useState("");
  const [yoklamaDurum, setYoklamaDurum] = useState("katildi");
  const [yoklamaNot, setYoklamaNot] = useState("");
  const [hata, setHata] = useState(null);
  const [bekliyor, setBekliyor] = useState(false);
  const ogrenciAd = (o) => `${o.ad || ""} ${o.soyad || ""}`.trim();

  const calistir = async (fn) => {
    setBekliyor(true); setHata(null);
    try { await fn(); onGuncellendi?.(); onKapat?.(); }
    catch (e) {
      const st = e?.response?.status;
      setHata(st === 409 ? (e.response.data?.detail || "Çakışma var.")
        : st === 400 ? (e.response.data?.detail || "Geçersiz bilgi.")
        : st === 403 ? "Bu ders üzerinde yetkiniz yok."
        : "İşlem başarısız.");
    } finally { setBekliyor(false); }
  };

  const tasi = () => {
    if (!sebep.trim()) { setHata("Sebep zorunludur."); return; }
    calistir(() => axios.put(`${apiBase}/ders/oturum/${encodeURIComponent(ders.id)}/tasi`, {
      tarih, baslangic_saati: bas, bitis_saati: bit, sebep,
    }));
  };
  const yoklama = () => calistir(() => axios.post(`${apiBase}/ders/oturum/${encodeURIComponent(ders.id)}/yoklama`, {
    durum: yoklamaDurum, not: yoklamaNot,
  }));
  const seriIptal = () => {
    if (!sebep.trim()) { setHata("Sebep zorunludur."); return; }
    calistir(() => axios.delete(`${apiBase}/ders/seri/${ders.seri_id}?sebep=${encodeURIComponent(sebep)}`));
  };
  const ogrenciDegistir = () => {
    if (!yeniOgrenci) { setHata("Yeni öğrenci seçin."); return; }
    if (!sebep.trim()) { setHata("Sebep zorunludur."); return; }
    calistir(() => axios.put(`${apiBase}/ders/seri/${ders.seri_id}`, { ogrenci_id: yeniOgrenci, sebep }));
  };
  const kaliciSil = () => {
    calistir(() => axios.delete(`${apiBase}/ders/seri/${ders.seri_id}?kalici=true&sebep=${encodeURIComponent(sebep || "Yanlış giriş")}`));
  };
  const kaliciSilTekli = () => {
    calistir(() => axios.delete(`${apiBase}/ders/oturum/${encodeURIComponent(ders.id)}?kalici=true&sebep=${encodeURIComponent(sebep || "Yanlış giriş")}`));
  };

  return (
    <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4" onClick={onKapat}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
          <div className="font-bold text-gray-800">📘 Ders Detayı</div>
          <button onClick={onKapat} className="text-gray-400 hover:text-gray-700 text-lg">✕</button>
        </div>

        <div className="p-5 space-y-3">
          {/* Bilgiler */}
          <div className="bg-gray-50 rounded-xl p-3 space-y-1 text-sm">
            <div><span className="text-gray-400">Öğrenci: </span><b>{ders.ogrenci_ad}</b></div>
            <div><span className="text-gray-400">Öğretmen: </span>{ders.ogretmen_ad}</div>
            <div><span className="text-gray-400">Tarih: </span>{ders.tarih} • {ders.baslangic_saati}-{ders.bitis_saati}</div>
            <div><span className="text-gray-400">Durum: </span>{DURUM_ETIKET[ders.durum] || ders.durum}</div>
            {ders.seri_id && <div className="text-xs text-indigo-500">🔁 Haftalık serinin bir dersi</div>}
            {ders.tasima_sebebi && <div className="text-xs text-amber-600">↪ Taşıma sebebi: {ders.tasima_sebebi}</div>}
            {ders.orijinal_tarih && <div className="text-[11px] text-gray-400">Önceki tarih: {ders.orijinal_tarih}</div>}
            {ders.yoklama_notu && <div className="text-xs text-gray-500">Yoklama notu: {ders.yoklama_notu}</div>}
          </div>

          {hata && <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-600">{hata}</div>}

          {/* Eylem seçimi */}
          {!mod && (
            <div className="grid gap-2">
              <button onClick={() => setMod("tasi")} className="px-4 py-2 rounded-xl border border-indigo-200 text-indigo-600 text-sm font-medium hover:bg-indigo-50">🕑 Saati Değiştir</button>
              <button onClick={() => setMod("yoklama")} className="px-4 py-2 rounded-xl border border-green-200 text-green-600 text-sm font-medium hover:bg-green-50">✅ Yoklama Gir</button>
              {ders.seri_id && (
                <button onClick={() => setMod("ogrenci")} className="px-4 py-2 rounded-xl border border-blue-200 text-blue-600 text-sm font-medium hover:bg-blue-50">👤 Öğrenciyi Değiştir</button>
              )}
              {ders.seri_id && (
                <button onClick={() => setMod("seri-iptal")} className="px-4 py-2 rounded-xl border border-red-200 text-red-600 text-sm font-medium hover:bg-red-50">🗑 Seriyi Sonlandır</button>
              )}
              {ders.seri_id && (
                <button onClick={() => setMod("kalici-sil")} className="px-4 py-2 rounded-xl border border-red-300 text-red-700 text-sm font-medium hover:bg-red-50">⛔ Kalıcı Sil (yanlış giriş)</button>
              )}
              {!ders.seri_id && (
                <button onClick={() => setMod("kalici-sil-tekli")} className="px-4 py-2 rounded-xl border border-red-300 text-red-700 text-sm font-medium hover:bg-red-50">⛔ Kalıcı Sil (yanlış giriş)</button>
              )}
            </div>
          )}

          {/* Öğrenci değiştir */}
          {mod === "ogrenci" && (
            <div className="space-y-2">
              <div className="text-sm text-gray-600">Bu program yanlış öğrenciye girildiyse doğru öğrenciyi seçin. Seri ve gelecek dersler yeni öğrenciye taşınır.</div>
              <label className="block text-xs text-gray-600">Yeni öğrenci <span className="text-red-500">*</span>
                <select value={yeniOgrenci} onChange={(e) => setYeniOgrenci(e.target.value)} className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm">
                  <option value="">— Öğrenci seçin —</option>
                  {ogrenciler.map((o) => <option key={o.id} value={o.id}>{ogrenciAd(o)}</option>)}
                </select></label>
              <label className="block text-xs text-gray-600">Sebep <span className="text-red-500">*</span>
                <textarea value={sebep} onChange={(e) => setSebep(e.target.value)} rows={2} placeholder="Neden değiştiriliyor?"
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" /></label>
              <div className="flex justify-end gap-2">
                <button onClick={() => setMod(null)} className="px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600">Geri</button>
                <button onClick={ogrenciDegistir} disabled={bekliyor} className="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold disabled:opacity-40">Değiştir</button>
              </div>
            </div>
          )}

          {/* Kalıcı sil (yanlış giriş) */}
          {mod === "kalici-sil" && (
            <div className="space-y-2">
              <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-2.5">⚠️ Bu ders serisi ve tüm dersleri <b>kalıcı olarak silinecek</b> (geri alınamaz). Yanlış girilen program için kullanın; öğrenciye bildirim gönderilmez.</div>
              <label className="block text-xs text-gray-600">Sebep (opsiyonel)
                <input value={sebep} onChange={(e) => setSebep(e.target.value)} placeholder="Yanlış giriş"
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" /></label>
              <div className="flex justify-end gap-2">
                <button onClick={() => setMod(null)} className="px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600">Geri</button>
                <button onClick={kaliciSil} disabled={bekliyor} className="px-4 py-2 rounded-xl bg-red-700 text-white text-sm font-semibold disabled:opacity-40">Kalıcı Sil</button>
              </div>
            </div>
          )}

          {/* Kalıcı sil — TEKLİ ders (yanlış giriş) */}
          {mod === "kalici-sil-tekli" && (
            <div className="space-y-2">
              <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-2.5">⚠️ Bu tekli ders <b>kalıcı olarak silinecek</b> (geri alınamaz). Yanlış girilen ders için kullanın; öğrenciye bildirim gönderilmez.</div>
              <label className="block text-xs text-gray-600">Sebep (opsiyonel)
                <input value={sebep} onChange={(e) => setSebep(e.target.value)} placeholder="Yanlış giriş"
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" /></label>
              <div className="flex justify-end gap-2">
                <button onClick={() => setMod(null)} className="px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600">Geri</button>
                <button onClick={kaliciSilTekli} disabled={bekliyor} className="px-4 py-2 rounded-xl bg-red-700 text-white text-sm font-semibold disabled:opacity-40">Kalıcı Sil</button>
              </div>
            </div>
          )}

          {/* Taşı */}
          {mod === "tasi" && (
            <div className="space-y-2">
              <label className="block text-xs text-gray-600">Yeni tarih
                <input type="date" value={tarih} onChange={(e) => setTarih(e.target.value)} className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" /></label>
              <div className="flex gap-2">
                <label className="flex-1 text-xs text-gray-600">Başlangıç
                  <input type="time" step="900" value={bas} onChange={(e) => setBas(e.target.value)} className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" /></label>
                <label className="flex-1 text-xs text-gray-600">Bitiş
                  <input type="time" step="900" value={bit} onChange={(e) => setBit(e.target.value)} className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" /></label>
              </div>
              <label className="block text-xs text-gray-600">Sebep <span className="text-red-500">*</span>
                <textarea value={sebep} onChange={(e) => setSebep(e.target.value)} rows={2} placeholder="Neden taşınıyor?"
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" /></label>
              <div className="flex justify-end gap-2">
                <button onClick={() => setMod(null)} className="px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600">Geri</button>
                <button onClick={tasi} disabled={bekliyor} className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold disabled:opacity-40">Kaydet</button>
              </div>
            </div>
          )}

          {/* Yoklama */}
          {mod === "yoklama" && (
            <div className="space-y-2">
              <div className="flex gap-2">
                {[{ v: "katildi", l: "✅ Katıldı" }, { v: "katilmadi", l: "❌ Katılmadı" }, { v: "iptal", l: "🚫 İptal" }].map((t) => (
                  <button key={t.v} onClick={() => setYoklamaDurum(t.v)}
                    className={`flex-1 px-2 py-2 rounded-xl text-xs font-medium border ${yoklamaDurum === t.v ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-600 border-gray-200"}`}>{t.l}</button>
                ))}
              </div>
              <label className="block text-xs text-gray-600">Not (opsiyonel)
                <input value={yoklamaNot} onChange={(e) => setYoklamaNot(e.target.value)} className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" /></label>
              <div className="flex justify-end gap-2">
                <button onClick={() => setMod(null)} className="px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600">Geri</button>
                <button onClick={yoklama} disabled={bekliyor} className="px-4 py-2 rounded-xl bg-green-600 text-white text-sm font-semibold disabled:opacity-40">Kaydet</button>
              </div>
            </div>
          )}

          {/* Seri iptal */}
          {mod === "seri-iptal" && (
            <div className="space-y-2">
              <div className="text-sm text-gray-600">Bu haftalık ders serisi sonlandırılacak (geçmiş kayıtlar korunur).</div>
              <label className="block text-xs text-gray-600">Sebep <span className="text-red-500">*</span>
                <textarea value={sebep} onChange={(e) => setSebep(e.target.value)} rows={2}
                  className="mt-1 w-full px-3 py-2 rounded-lg border border-gray-200 text-sm" /></label>
              <div className="flex justify-end gap-2">
                <button onClick={() => setMod(null)} className="px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600">Geri</button>
                <button onClick={seriIptal} disabled={bekliyor} className="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-semibold disabled:opacity-40">Sonlandır</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
