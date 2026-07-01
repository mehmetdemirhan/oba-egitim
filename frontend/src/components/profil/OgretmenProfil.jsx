import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";

/**
 * OgretmenProfil — öğretmenin kendi profilini görüntüleyip düzenlediği sayfa.
 * Üstte avatar + temel bilgi kartı; altında 3 alt-sekme (Kişisel / Profesyonel /
 * Ayarlar) ve sabit "Kaydet" butonu. Profil fotoğrafı yükleme dahil.
 *
 * Props: apiBase — `${BACKEND_URL}/api`
 */
const ALANLAR_DUZENLENEBILIR = [
  "ad", "soyad", "brans", "telefon", "dogum_tarihi", "adres", "sehir",
  "kisa_biyografi", "egitim_gecmisi", "deneyim_yili", "sertifikalar",
  "bildirim_tercihleri", "profil_fotografi",
];

const BILDIRIM_ETIKET = {
  email: "E-posta bildirimleri",
  push: "Push bildirimleri",
  veli_mesaji: "Veli mesajları",
  ogrenci_mesaji: "Öğrenci mesajları",
  admin_duyuru: "Yönetici duyuruları",
};

function tarihKisa(s) {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" }); }
  catch { return "—"; }
}

export default function OgretmenProfil({ apiBase }) {
  const backendUrl = useMemo(() => (apiBase || "").replace(/\/api\/?$/, ""), [apiBase]);
  const [profil, setProfil] = useState(null);
  const [form, setForm] = useState(null);
  const [tab, setTab] = useState("kisisel");
  const [yukleniyor, setYukleniyor] = useState(true);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [fotoYukleniyor, setFotoYukleniyor] = useState(false);
  const [toast, setToast] = useState(null); // {tip:"ok"|"hata", metin}
  const fotoInputRef = useRef(null);

  // Şifre değiştirme
  const [sifre, setSifre] = useState({ eski: "", yeni: "", yeni2: "" });
  const [sifreMesaj, setSifreMesaj] = useState(null);

  const toastGoster = (tip, metin) => {
    setToast({ tip, metin });
    setTimeout(() => setToast(null), 3000);
  };

  useEffect(() => {
    let iptal = false;
    (async () => {
      setYukleniyor(true);
      try {
        const r = await axios.get(`${apiBase}/ogretmen/profil`);
        if (!iptal) { setProfil(r.data); setForm(r.data); }
      } catch (e) {
        if (!iptal) toastGoster("hata", "Profil yüklenemedi.");
      } finally {
        if (!iptal) setYukleniyor(false);
      }
    })();
    return () => { iptal = true; };
  }, [apiBase]);

  const alan = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const kaydet = async () => {
    if (!form) return;
    setKaydediliyor(true);
    try {
      const govde = {};
      for (const k of ALANLAR_DUZENLENEBILIR) if (k in form) govde[k] = form[k];
      const r = await axios.put(`${apiBase}/ogretmen/profil`, govde);
      setProfil(r.data); setForm(r.data);
      toastGoster("ok", "✅ Bilgileriniz güncellendi");
    } catch (e) {
      toastGoster("hata", "Kaydedilemedi, tekrar deneyin.");
    } finally {
      setKaydediliyor(false);
    }
  };

  const fotoSec = () => fotoInputRef.current?.click();

  const fotoYukle = async (e) => {
    const dosya = e.target.files?.[0];
    if (!dosya) return;
    if (dosya.size > 2 * 1024 * 1024) { toastGoster("hata", "Dosya en fazla 2MB olabilir."); return; }
    const fd = new FormData();
    fd.append("dosya", dosya);
    setFotoYukleniyor(true);
    try {
      const r = await axios.post(`${apiBase}/ogretmen/profil/foto`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const url = r.data?.profil_fotografi_url;
      setForm((f) => ({ ...f, profil_fotografi: url }));
      setProfil((p) => ({ ...p, profil_fotografi: url }));
      toastGoster("ok", "✅ Fotoğraf güncellendi");
    } catch (err) {
      toastGoster("hata", "Fotoğraf yüklenemedi.");
    } finally {
      setFotoYukleniyor(false);
      if (fotoInputRef.current) fotoInputRef.current.value = "";
    }
  };

  const sifreDegistir = async () => {
    setSifreMesaj(null);
    if (!sifre.eski || !sifre.yeni) { setSifreMesaj({ tip: "hata", m: "Alanları doldurun." }); return; }
    if (sifre.yeni.length < 4) { setSifreMesaj({ tip: "hata", m: "Yeni şifre en az 4 karakter olmalı." }); return; }
    if (sifre.yeni !== sifre.yeni2) { setSifreMesaj({ tip: "hata", m: "Yeni şifreler eşleşmiyor." }); return; }
    try {
      await axios.post(`${apiBase}/auth/change-password`, { old_password: sifre.eski, new_password: sifre.yeni });
      setSifre({ eski: "", yeni: "", yeni2: "" });
      setSifreMesaj({ tip: "ok", m: "✅ Şifre güncellendi." });
    } catch (e) {
      setSifreMesaj({ tip: "hata", m: e?.response?.data?.detail || "Şifre değiştirilemedi." });
    }
  };

  if (yukleniyor) return <div className="text-center py-16 text-gray-400 text-sm">Yükleniyor…</div>;
  if (!form) return <div className="text-center py-16 text-gray-400 text-sm">Profil yüklenemedi.</div>;

  const fotoSrc = form.profil_fotografi ? `${backendUrl}${form.profil_fotografi}` : null;
  const bio = form.kisa_biyografi || "";

  const Girdi = ({ label, k, tip = "text", readonly = false, ph = "" }) => (
    <div>
      <label className="text-xs font-medium text-gray-500">{label}</label>
      <input
        type={tip}
        value={form[k] ?? ""}
        onChange={(e) => alan(k, e.target.value)}
        readOnly={readonly}
        placeholder={ph}
        className={`w-full mt-1 px-3 py-2 rounded-xl border text-sm ${readonly ? "bg-gray-100 text-gray-500 border-gray-200" : "border-gray-200 focus:border-indigo-400 outline-none"}`}
      />
    </div>
  );

  return (
    <div className="space-y-4 pb-24">
      {/* ── Profil kartı ── */}
      <div className="bg-white rounded-2xl shadow-sm border p-5 flex items-center gap-5 flex-wrap">
        <div className="relative">
          <div className="w-28 h-28 rounded-2xl overflow-hidden bg-indigo-50 border flex items-center justify-center">
            {fotoSrc ? (
              <img src={fotoSrc} alt="Profil" className="w-full h-full object-cover" />
            ) : (
              <span className="text-4xl">👩‍🏫</span>
            )}
          </div>
          <button onClick={fotoSec} disabled={fotoYukleniyor}
            className="absolute -bottom-2 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-indigo-600 text-white text-[11px] font-medium shadow hover:bg-indigo-700 disabled:opacity-50">
            {fotoYukleniyor ? "…" : "Değiştir"}
          </button>
          <input ref={fotoInputRef} type="file" accept="image/jpeg,image/png" onChange={fotoYukle} className="hidden" />
        </div>
        <div className="min-w-0">
          <div className="text-xl font-bold text-gray-800">{form.ad} {form.soyad}</div>
          <div className="text-sm text-gray-500">{form.brans || "—"}{form.seviye ? ` • ${form.seviye}` : ""}</div>
          <div className="text-sm text-gray-500 mt-1">📞 {form.telefon || "—"}</div>
          <div className="text-xs text-gray-400 mt-1">📅 Katılım: {tarihKisa(form.katilim_tarihi)}</div>
        </div>
      </div>

      {/* ── Alt-sekmeler ── */}
      <div className="flex gap-2 flex-wrap">
        {[{ v: "kisisel", l: "Kişisel Bilgiler" }, { v: "profesyonel", l: "Profesyonel" }, { v: "ayarlar", l: "Ayarlar" }].map((t) => (
          <button key={t.v} onClick={() => setTab(t.v)}
            className={`px-4 py-2 rounded-xl text-sm font-medium border transition-all ${tab === t.v ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"}`}>
            {t.l}
          </button>
        ))}
      </div>

      {/* ── KİŞİSEL ── */}
      {tab === "kisisel" && (
        <div className="bg-white rounded-2xl shadow-sm border p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
          <Girdi label="Ad" k="ad" />
          <Girdi label="Soyad" k="soyad" />
          <Girdi label="E-posta (değiştirilemez)" k="email" readonly />
          <Girdi label="Telefon" k="telefon" />
          <Girdi label="Doğum Tarihi" k="dogum_tarihi" tip="date" />
          <Girdi label="Şehir" k="sehir" />
          <div className="md:col-span-2">
            <label className="text-xs font-medium text-gray-500">Adres</label>
            <textarea value={form.adres || ""} onChange={(e) => alan("adres", e.target.value)} rows={2}
              className="w-full mt-1 px-3 py-2 rounded-xl border border-gray-200 text-sm focus:border-indigo-400 outline-none" />
          </div>
        </div>
      )}

      {/* ── PROFESYONEL ── */}
      {tab === "profesyonel" && (
        <div className="bg-white rounded-2xl shadow-sm border p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Girdi label="Branş" k="brans" />
            <Girdi label="Deneyim Yılı" k="deneyim_yili" tip="number" />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-500">Kısa Biyografi <span className="text-gray-400">({bio.length}/500)</span></label>
            <textarea value={bio} maxLength={500} rows={3}
              onChange={(e) => alan("kisa_biyografi", e.target.value)}
              className="w-full mt-1 px-3 py-2 rounded-xl border border-gray-200 text-sm focus:border-indigo-400 outline-none" />
          </div>

          <DinamikListe
            baslik="Eğitim Geçmişi"
            ogeler={form.egitim_gecmisi || []}
            alanlar={[{ k: "okul", ph: "Okul" }, { k: "bolum", ph: "Bölüm" }, { k: "yil", ph: "Yıl", tip: "number" }]}
            onDegis={(list) => alan("egitim_gecmisi", list)}
          />
          <DinamikListe
            baslik="Sertifikalar"
            ogeler={form.sertifikalar || []}
            alanlar={[{ k: "ad", ph: "Sertifika adı" }, { k: "kurum", ph: "Kurum" }, { k: "yil", ph: "Yıl", tip: "number" }]}
            onDegis={(list) => alan("sertifikalar", list)}
          />
        </div>
      )}

      {/* ── AYARLAR ── */}
      {tab === "ayarlar" && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl shadow-sm border p-5">
            <h4 className="text-sm font-bold text-gray-700 mb-3">🔔 Bildirim Tercihleri</h4>
            <div className="space-y-2">
              {Object.keys(BILDIRIM_ETIKET).map((k) => (
                <label key={k} className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox"
                    checked={!!(form.bildirim_tercihleri || {})[k]}
                    onChange={(e) => alan("bildirim_tercihleri", { ...(form.bildirim_tercihleri || {}), [k]: e.target.checked })}
                    className="w-4 h-4 accent-indigo-600" />
                  {BILDIRIM_ETIKET[k]}
                </label>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border p-5">
            <h4 className="text-sm font-bold text-gray-700 mb-3">🔒 Şifre Değiştir</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input type="password" placeholder="Mevcut şifre" value={sifre.eski}
                onChange={(e) => setSifre((s) => ({ ...s, eski: e.target.value }))}
                className="px-3 py-2 rounded-xl border border-gray-200 text-sm outline-none focus:border-indigo-400" />
              <input type="password" placeholder="Yeni şifre" value={sifre.yeni}
                onChange={(e) => setSifre((s) => ({ ...s, yeni: e.target.value }))}
                className="px-3 py-2 rounded-xl border border-gray-200 text-sm outline-none focus:border-indigo-400" />
              <input type="password" placeholder="Yeni şifre (tekrar)" value={sifre.yeni2}
                onChange={(e) => setSifre((s) => ({ ...s, yeni2: e.target.value }))}
                className="px-3 py-2 rounded-xl border border-gray-200 text-sm outline-none focus:border-indigo-400" />
            </div>
            {sifreMesaj && (
              <div className={`text-xs mt-2 ${sifreMesaj.tip === "ok" ? "text-green-600" : "text-red-600"}`}>{sifreMesaj.m}</div>
            )}
            <button onClick={sifreDegistir}
              className="mt-3 px-4 py-2 rounded-xl bg-gray-800 text-white text-sm font-medium hover:bg-gray-900">
              Şifreyi Değiştir
            </button>
          </div>
        </div>
      )}

      {/* ── Sabit Kaydet ── */}
      <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40">
        <button onClick={kaydet} disabled={kaydediliyor}
          className="px-6 py-3 rounded-2xl bg-indigo-600 text-white text-sm font-bold shadow-lg hover:bg-indigo-700 disabled:opacity-60">
          {kaydediliyor ? "Kaydediliyor…" : "💾 Değişiklikleri Kaydet"}
        </button>
      </div>

      {/* ── Toast ── */}
      {toast && (
        <div className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl text-sm font-medium shadow-lg ${toast.tip === "ok" ? "bg-green-600 text-white" : "bg-red-600 text-white"}`}>
          {toast.metin}
        </div>
      )}
    </div>
  );
}

// ── Dinamik liste (eğitim/sertifika) ──
function DinamikListe({ baslik, ogeler, alanlar, onDegis }) {
  const ekle = () => onDegis([...(ogeler || []), Object.fromEntries(alanlar.map((a) => [a.k, ""]))]);
  const sil = (i) => onDegis(ogeler.filter((_, idx) => idx !== i));
  const degis = (i, k, v) => onDegis(ogeler.map((o, idx) => (idx === i ? { ...o, [k]: v } : o)));

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-xs font-medium text-gray-500">{baslik}</label>
        <button onClick={ekle} className="text-xs px-2 py-1 rounded-lg border border-indigo-200 text-indigo-600 hover:bg-indigo-50">+ Ekle</button>
      </div>
      <div className="space-y-2">
        {(ogeler || []).length === 0 && <div className="text-xs text-gray-400">Henüz eklenmedi.</div>}
        {(ogeler || []).map((o, i) => (
          <div key={i} className="flex gap-2 items-center">
            {alanlar.map((a) => (
              <input key={a.k} type={a.tip || "text"} placeholder={a.ph} value={o[a.k] ?? ""}
                onChange={(e) => degis(i, a.k, a.tip === "number" ? e.target.value : e.target.value)}
                className="flex-1 min-w-0 px-2 py-1.5 rounded-lg border border-gray-200 text-sm outline-none focus:border-indigo-400" />
            ))}
            <button onClick={() => sil(i)} className="text-red-400 hover:text-red-600 text-sm px-1">✕</button>
          </div>
        ))}
      </div>
    </div>
  );
}
