import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { Activity, RefreshCw, AlertTriangle, Save } from "lucide-react";
import IslemKayitlari from "./IslemKayitlari";

/**
 * Loglar — yönetici log ekranı (admin + koordinatör).
 * Grafikler tek özet uçtan (/loglar/ozet), canlı akış tablosu ayrı sayfalı uçtan
 * (/loglar/giris). İşlem Kayıtları (audit) görünümü Ayarlar'dan buraya taşındı.
 * Props: apiBase.
 */
const ROL_ETIKET = {
  admin: "Yönetici", coordinator: "Koordinatör", teacher: "Öğretmen",
  student: "Öğrenci", parent: "Veli", accountant: "Muhasebe",
};
const ROL_RENK = {
  admin: "#6366f1", coordinator: "#0ea5e9", teacher: "#059669",
  student: "#f59e0b", parent: "#ec4899", accountant: "#ef4444",
};
const TIP_ETIKET = {
  login_basarili: "Başarılı giriş", login_basarisiz: "Başarısız giriş",
  logout: "Çıkış", token_yenile: "Oturum yenileme",
};
// Mongo $dayOfWeek: 1=Pazar .. 7=Cumartesi
const GUN_KISA = ["", "Paz", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt"];
const PIE_RENK = ["#6366f1", "#0ea5e9", "#059669", "#f59e0b", "#ec4899", "#ef4444"];

const tarihStr = (t) => { try { return new Date(t).toLocaleString("tr-TR"); } catch { return t; } };

export default function Loglar({ apiBase }) {
  const { toast } = useToast();
  const [ozet, setOzet] = useState(null);
  const [ozetYukleniyor, setOzetYukleniyor] = useState(false);

  // ── Özet (grafikler) ──
  const ozetYukle = useCallback(async () => {
    setOzetYukleniyor(true);
    try {
      const r = await axios.get(`${apiBase}/loglar/ozet`);
      setOzet(r.data || null);
    } catch {
      toast({ title: "Log özeti yüklenemedi", variant: "destructive" });
    } finally {
      setOzetYukleniyor(false);
    }
  }, [apiBase, toast]);

  useEffect(() => { ozetYukle(); }, [ozetYukle]);

  // Günlük aktif kullanıcı: [{gun, rol, sayi}] → [{gun, <rol>:sayi, ...}]
  const { aktifData, aktifRoller } = useMemo(() => {
    const satirlar = ozet?.gunluk_aktif || [];
    const gunMap = {};
    const roller = new Set();
    satirlar.forEach(({ gun, rol, sayi }) => {
      if (!gunMap[gun]) gunMap[gun] = { gun };
      gunMap[gun][rol || "?"] = sayi;
      if (rol) roller.add(rol);
    });
    const data = Object.values(gunMap).sort((a, b) => a.gun.localeCompare(b.gun));
    return { aktifData: data, aktifRoller: Array.from(roller) };
  }, [ozet]);

  // Isı haritası: 7 gün × 24 saat grid + en yoğun hücre
  const { isiGrid, isiMax } = useMemo(() => {
    const grid = {};
    let mx = 0;
    (ozet?.isi_haritasi || []).forEach(({ gun, saat, sayi }) => {
      grid[`${gun}_${saat}`] = sayi;
      if (sayi > mx) mx = sayi;
    });
    return { isiGrid: grid, isiMax: mx };
  }, [ozet]);

  const bugunRol = useMemo(
    () => (ozet?.bugun_rol || []).map((r) => ({ ...r, ad: ROL_ETIKET[r.rol] || r.rol || "?" })),
    [ozet]);

  const islemHacmi = useMemo(() => (ozet?.islem_hacmi || []).slice(0, 12), [ozet]);
  const uyarilar = ozet?.uyarilar || [];
  const esik = ozet?.esik || { sayi: 5, dakika: 15 };

  const isiRenk = (v) => {
    if (!v) return "var(--app, #f3f4f6)";
    const oran = isiMax ? v / isiMax : 0;
    // açık → koyu indigo
    const alpha = 0.15 + oran * 0.85;
    return `rgba(99, 102, 241, ${alpha.toFixed(2)})`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-bold text-content inline-flex items-center gap-2">
            <Activity className="h-6 w-6" />Loglar
          </h2>
          <p className="text-sm text-subtle">Giriş/çıkış hareketleri, güvenlik uyarıları ve işlem kayıtları.</p>
        </div>
        <button onClick={ozetYukle} className="inline-flex items-center gap-1 border border-line rounded-lg px-3 py-1.5 text-sm hover:bg-app">
          <RefreshCw className="h-4 w-4" />Yenile
        </button>
      </div>

      {/* Eşik uyarıları */}
      {uyarilar.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
          <div className="flex items-center gap-2 text-red-700 font-bold mb-2">
            <AlertTriangle className="h-5 w-5" />Şüpheli giriş denemeleri
            <span className="text-xs font-normal text-red-500">(son {esik.dakika} dk içinde {esik.sayi}+ başarısız)</span>
          </div>
          <ul className="text-sm text-red-700 space-y-1">
            {uyarilar.map((u, i) => (
              <li key={i} className="tabular-nums">
                <span className="font-semibold">{u.ip || "—"}</span>
                {u.email && <span className="text-red-500"> · {u.email}</span>}
                <span className="ml-2 px-1.5 py-0.5 rounded bg-red-500 text-white text-xs font-bold">{u.sayi} deneme</span>
                <span className="ml-2 text-xs text-red-400">son: {tarihStr(u.son)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {ozetYukleniyor && <div className="text-center text-subtle py-8">Grafikler yükleniyor…</div>}

      {/* Grafik ızgarası */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Günlük aktif kullanıcı */}
        <div className="bg-surface border border-line rounded-2xl shadow-sm p-4">
          <h3 className="text-sm font-bold text-content mb-3">Günlük aktif kullanıcı (30 gün)</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={aktifData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="gun" fontSize={10} tickFormatter={(g) => g?.slice(5)} />
                <YAxis fontSize={11} allowDecimals={false} />
                <Tooltip />
                <Legend iconType="circle" />
                {aktifRoller.map((rol) => (
                  <Line key={rol} type="monotone" dataKey={rol} name={ROL_ETIKET[rol] || rol}
                        stroke={ROL_RENK[rol] || "#94a3b8"} strokeWidth={2} dot={false} connectNulls />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bugünkü rol dağılımı */}
        <div className="bg-surface border border-line rounded-2xl shadow-sm p-4">
          <h3 className="text-sm font-bold text-content mb-3">Bugünkü girişler — rol dağılımı</h3>
          <div className="h-56">
            {bugunRol.length === 0 ? (
              <div className="h-full flex items-center justify-center text-subtle text-sm">Bugün giriş yok.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={bugunRol} dataKey="sayi" nameKey="ad" cx="50%" cy="50%" outerRadius={80} label>
                    {bugunRol.map((r, i) => <Cell key={i} fill={ROL_RENK[r.rol] || PIE_RENK[i % PIE_RENK.length]} />)}
                  </Pie>
                  <Tooltip />
                  <Legend iconType="circle" />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Başarısız giriş çizgisi */}
        <div className="bg-surface border border-line rounded-2xl shadow-sm p-4">
          <h3 className="text-sm font-bold text-content mb-3">Başarısız giriş denemeleri (30 gün)</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={ozet?.basarisiz_gunluk || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="gun" fontSize={10} tickFormatter={(g) => g?.slice(5)} />
                <YAxis fontSize={11} allowDecimals={false} />
                <Tooltip />
                <Line type="monotone" dataKey="sayi" name="Başarısız" stroke="#ef4444" strokeWidth={2} dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* İşlem hacmi */}
        <div className="bg-surface border border-line rounded-2xl shadow-sm p-4">
          <h3 className="text-sm font-bold text-content mb-3">İşlem hacmi — olay türü (30 gün)</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={islemHacmi}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="islem" fontSize={9} interval={0} angle={-30} textAnchor="end" height={50} />
                <YAxis fontSize={11} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="sayi" name="İşlem" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Saatlik yoğunluk ısı haritası + kullanım süresi (yan yana) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="bg-surface border border-line rounded-2xl shadow-sm p-4 lg:col-span-2">
        <h3 className="text-sm font-bold text-content mb-3">Saatlik yoğunluk (gün × saat, son 30 gün)</h3>
        <div className="overflow-x-auto">
          <table className="border-collapse">
            <thead>
              <tr>
                <th className="w-10"></th>
                {Array.from({ length: 24 }, (_, s) => (
                  <th key={s} className="text-[9px] text-subtle font-normal w-5 text-center">{s}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[2, 3, 4, 5, 6, 7, 1].map((g) => ( // Pzt→Paz sıralı
                <tr key={g}>
                  <td className="text-[10px] text-subtle pr-1 whitespace-nowrap">{GUN_KISA[g]}</td>
                  {Array.from({ length: 24 }, (_, s) => {
                    const v = isiGrid[`${g}_${s}`] || 0;
                    return (
                      <td key={s} className="p-0.5">
                        <div title={`${GUN_KISA[g]} ${s}:00 — ${v} giriş`}
                             className="w-4 h-4 rounded-sm border border-line/40"
                             style={{ backgroundColor: isiRenk(v) }} />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Kullanıcıların Geçirdiği Süre */}
      <div className="bg-surface border border-line rounded-2xl shadow-sm p-4">
        <h3 className="text-sm font-bold text-content mb-1 inline-flex items-center gap-1">
          Kullanıcıların Geçirdiği Süre
          <span title="Ortalama oturum süresi: giriş→çıkış çiftlerinden hesaplanır. Çıkış yoksa son aktiviteye (token yenileme) göre tahmin edilir; tahmin en fazla 20 dk varsayılır. Son 30 gün."
                className="text-subtle cursor-help">ⓘ</span>
        </h3>
        <p className="text-xs text-subtle mb-3">Ortalama oturum (son 30 gün)</p>
        <div className="text-center mb-3">
          <div className="text-3xl font-bold text-indigo-600 tabular-nums">{ozet?.oturum_sure?.ortalama_dk ?? 0}<span className="text-base font-medium text-subtle"> dk</span></div>
          <div className="text-xs text-subtle">{ozet?.oturum_sure?.toplam_oturum ?? 0} oturum</div>
        </div>
        <div className="space-y-1.5">
          {(ozet?.oturum_sure?.rol_bazli || []).map((r) => (
            <div key={r.rol} className="flex items-center justify-between text-sm">
              <span className="text-subtle">{ROL_ETIKET[r.rol] || r.rol || "?"}</span>
              <span className="text-content tabular-nums"><b>{r.ortalama_dk}</b> dk <span className="text-xs text-subtle">({r.oturum_sayisi})</span></span>
            </div>
          ))}
          {(!ozet?.oturum_sure?.rol_bazli || ozet.oturum_sure.rol_bazli.length === 0) && (
            <p className="text-xs text-subtle text-center py-2">Yeterli oturum verisi yok.</p>
          )}
        </div>
      </div>
      </div>

      {/* Canlı akış tablosu */}
      <GirisTablosu apiBase={apiBase} />

      {/* Saklama ayarı */}
      <SaklamaAyari apiBase={apiBase} />

      {/* İşlem Kayıtları (Ayarlar'dan taşındı) */}
      <IslemKayitlari apiBase={apiBase} />
    </div>
  );
}

// ── Giriş logu canlı akış tablosu (filtreli + sayfalı) ──
function GirisTablosu({ apiBase }) {
  const { toast } = useToast();
  const [kayitlar, setKayitlar] = useState([]);
  const [toplam, setToplam] = useState(0);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [skip, setSkip] = useState(0);
  const LIMIT = 50;
  const [f, setF] = useState({ tarih_bas: "", tarih_bit: "", rol: "", tip: "", kullanici_ara: "" });

  const yukle = useCallback(async () => {
    setYukleniyor(true);
    try {
      const params = { skip, limit: LIMIT };
      Object.entries(f).forEach(([k, v]) => { if (v) params[k] = v; });
      const r = await axios.get(`${apiBase}/loglar/giris`, { params });
      setKayitlar(r.data?.kayitlar || []);
      setToplam(r.data?.toplam || 0);
    } catch {
      toast({ title: "Giriş kayıtları yüklenemedi", variant: "destructive" });
    } finally {
      setYukleniyor(false);
    }
  }, [apiBase, skip, f, toast]);

  useEffect(() => { yukle(); }, [yukle]);

  const filtreDegis = (k, v) => { setSkip(0); setF((o) => ({ ...o, [k]: v })); };
  const sayfaSon = Math.max(0, Math.ceil(toplam / LIMIT) - 1);
  const sayfa = Math.floor(skip / LIMIT);

  const inp = "border border-line rounded-lg px-2 py-1.5 text-sm bg-surface";

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-bold text-content">Giriş/çıkış akışı</h3>
      <div className="flex items-center gap-2 flex-wrap">
        <input type="date" value={f.tarih_bas} onChange={(e) => filtreDegis("tarih_bas", e.target.value)} className={inp} title="Başlangıç" />
        <input type="date" value={f.tarih_bit} onChange={(e) => filtreDegis("tarih_bit", e.target.value)} className={inp} title="Bitiş" />
        <select value={f.rol} onChange={(e) => filtreDegis("rol", e.target.value)} className={inp}>
          <option value="">Tüm roller</option>
          {Object.entries(ROL_ETIKET).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={f.tip} onChange={(e) => filtreDegis("tip", e.target.value)} className={inp}>
          <option value="">Tüm olaylar</option>
          {Object.entries(TIP_ETIKET).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input type="text" placeholder="Kullanıcı / e-posta / IP ara" value={f.kullanici_ara}
               onChange={(e) => filtreDegis("kullanici_ara", e.target.value)} className={`${inp} flex-1 min-w-[160px]`} />
        <button onClick={yukle} className="inline-flex items-center gap-1 border border-line rounded-lg px-3 py-1.5 text-sm hover:bg-app">
          <RefreshCw className="h-4 w-4" />Yenile
        </button>
      </div>

      <div className="bg-surface border border-line rounded-2xl shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-subtle border-b border-line bg-app">
              <th className="px-3 py-2 whitespace-nowrap">Zaman</th>
              <th className="px-3 py-2">Kullanıcı</th>
              <th className="px-3 py-2">Rol</th>
              <th className="px-3 py-2">Olay</th>
              <th className="px-3 py-2">Detay</th>
              <th className="px-3 py-2">IP</th>
            </tr>
          </thead>
          <tbody>
            {yukleniyor && <tr><td colSpan={6} className="px-3 py-6 text-center text-subtle">Yükleniyor…</td></tr>}
            {!yukleniyor && kayitlar.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-subtle">Kayıt yok.</td></tr>}
            {!yukleniyor && kayitlar.map((k) => (
              <tr key={k.id} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-subtle whitespace-nowrap tabular-nums">{tarihStr(k.olusturma)}</td>
                <td className="px-3 py-2 text-content">{k.kullanici_ad || (k.denenen_email ? <span className="text-red-500">{k.denenen_email}</span> : "—")}</td>
                <td className="px-3 py-2 text-subtle">{ROL_ETIKET[k.rol] || k.rol || "—"}</td>
                <td className="px-3 py-2">
                  <span className={k.tip === "login_basarisiz" ? "text-red-600 font-medium" : "text-content"}>
                    {TIP_ETIKET[k.tip] || k.tip}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-subtle max-w-[220px] truncate" title={k.ua || ""}>{k.ua || "—"}</td>
                <td className="px-3 py-2 text-subtle tabular-nums">{k.ip || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-subtle">
        <span>Toplam {toplam} kayıt</span>
        <div className="flex items-center gap-2">
          <button disabled={sayfa <= 0} onClick={() => setSkip(Math.max(0, skip - LIMIT))}
                  className="border border-line rounded-lg px-3 py-1 disabled:opacity-40 hover:bg-app">Önceki</button>
          <span className="tabular-nums">{sayfa + 1} / {sayfaSon + 1}</span>
          <button disabled={sayfa >= sayfaSon} onClick={() => setSkip(skip + LIMIT)}
                  className="border border-line rounded-lg px-3 py-1 disabled:opacity-40 hover:bg-app">Sonraki</button>
        </div>
      </div>
    </div>
  );
}

// ── Saklama süresi (TTL) ayarı ──
function SaklamaAyari({ apiBase }) {
  const { toast } = useToast();
  const [gun, setGun] = useState(90);
  const [kayit, setKayit] = useState(false);

  useEffect(() => {
    axios.get(`${apiBase}/loglar/saklama`).then((r) => setGun(r.data?.gun || 90)).catch(() => {});
  }, [apiBase]);

  const kaydet = async () => {
    setKayit(true);
    try {
      await axios.put(`${apiBase}/loglar/saklama`, { gun: Number(gun) });
      toast({ title: "Saklama süresi güncellendi" });
    } catch (e) {
      toast({ title: "Güncellenemedi", description: e?.response?.data?.detail, variant: "destructive" });
    } finally {
      setKayit(false);
    }
  };

  return (
    <div className="bg-surface border border-line rounded-2xl shadow-sm p-4 flex items-center gap-3 flex-wrap">
      <div className="flex-1 min-w-[220px]">
        <h3 className="text-sm font-bold text-content">Giriş logu saklama süresi</h3>
        <p className="text-xs text-subtle">Bu süreden eski giriş/çıkış kayıtları otomatik silinir (DB şişmesin).</p>
      </div>
      <div className="flex items-center gap-2">
        <input type="number" min={1} max={3650} value={gun} onChange={(e) => setGun(e.target.value)}
               className="border border-line rounded-lg px-2 py-1.5 text-sm bg-surface w-24" />
        <span className="text-sm text-subtle">gün</span>
        <button onClick={kaydet} disabled={kayit}
                className="inline-flex items-center gap-1 bg-indigo-600 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-indigo-700 disabled:opacity-50">
          <Save className="h-4 w-4" />Kaydet
        </button>
      </div>
    </div>
  );
}
