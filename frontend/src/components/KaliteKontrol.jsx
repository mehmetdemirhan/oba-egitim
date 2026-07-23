import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { CheckCircle2, XCircle, RefreshCw, ClipboardCheck, AlertTriangle, Archive, RotateCcw, Save, Sparkles } from "lucide-react";
import EgzersizOnizleme from "./exercises/EgzersizOnizleme";

/**
 * Egzersiz Kalite Kontrol — TEK egzersiz odaklı, sıralı akış. Öğretmen egzersizi
 * öğrencinin gördüğü gerçek bileşenle (EgzersizOnizleme) önizler, değerlendirir,
 * "Kaydet" ile bir sonrakine otomatik geçer. XP geri bildirimi mevcut toast deseniyle.
 */
const SINIF_SECENEK = [1, 2, 3, 4, 5, 6, 7, 8, "lise"];
const sinifEtiket = (s) => (s === "lise" ? "Lise" : `${s}. Sınıf`);

// ── Tek egzersiz: gerçek önizleme + değerlendirme formu ──
function TekEgzersizDegerlendir({ apiBase, egzersiz, onTamam, toast }) {
  const [uygun, setUygun] = useState(null);
  const [siniflar, setSiniflar] = useState([]);
  const [talep, setTalep] = useState("");
  const [kaydet, setKaydet] = useState(false);

  useEffect(() => { setUygun(null); setSiniflar([]); setTalep(""); }, [egzersiz.egzersiz_id]);

  const sinifToggle = (s) => setSiniflar((l) => (l.includes(s) ? l.filter((x) => x !== s) : [...l, s]));

  const gonder = async () => {
    if (uygun === null) { toast({ title: "Uygun / Uygun Değil seçin", variant: "destructive" }); return; }
    if (uygun && siniflar.length === 0) { toast({ title: "En az bir sınıf seviyesi seçin", variant: "destructive" }); return; }
    setKaydet(true);
    try {
      const r = await axios.post(`${apiBase}/egzersiz-kalite/degerlendir`, {
        egzersiz_id: egzersiz.egzersiz_id, uygun,
        uygun_sinif_seviyeleri: uygun ? siniflar : [],
        degisiklik_talebi: talep.trim() || null,
      });
      const xp = r.data.kazanilan_xp || 0;
      toast({ title: `✓ Değerlendirildi  +${xp} XP 🎉`, description: r.data.askiya_alindi ? "Bu egzersiz yeterli olumsuz oyla askıya alındı." : "" });
      onTamam?.(egzersiz.egzersiz_id, xp);
    } catch (e) {
      toast({ title: e?.response?.data?.detail || "Kaydedilemedi", variant: "destructive" });
      if (e?.response?.status === 409) onTamam?.(egzersiz.egzersiz_id, 0);
    } finally { setKaydet(false); }
  };

  return (
    <div className="rounded-2xl border border-line bg-surface p-4 sm:p-5 shadow-sm space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-semibold bg-primary/10 text-primary rounded-full px-2.5 py-0.5">{egzersiz.tip_ad}</span>
        <span className="text-xs text-subtle">{sinifEtiket(egzersiz.sinif)} · {egzersiz.zorluk}{egzersiz.konu ? ` · ${egzersiz.konu}` : ""}</span>
        <span className="ml-auto text-[11px] text-subtle">{egzersiz.toplam_degerlendirme || 0} kez değerlendirildi</span>
      </div>

      {/* Öğrencinin gördüğü GERÇEK egzersiz (ham JSON değil) */}
      <div className="rounded-xl bg-app/60 p-2 sm:p-3">
        <EgzersizOnizleme apiBase={apiBase} tip={egzersiz.tip} sinif={typeof egzersiz.sinif === "number" ? egzersiz.sinif : 3} icerikId={egzersiz.egzersiz_id} />
      </div>

      {/* Değerlendirme */}
      <div className="flex gap-2">
        <button onClick={() => setUygun(true)} className={`flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl border-2 py-2.5 text-sm font-semibold transition ${uygun === true ? "border-green-500 bg-green-50 text-green-700" : "border-line text-subtle hover:border-green-300"}`}>
          <CheckCircle2 className="h-4 w-4" />Uygun
        </button>
        <button onClick={() => setUygun(false)} className={`flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl border-2 py-2.5 text-sm font-semibold transition ${uygun === false ? "border-red-500 bg-red-50 text-red-700" : "border-line text-subtle hover:border-red-300"}`}>
          <XCircle className="h-4 w-4" />Uygun Değil
        </button>
      </div>

      {uygun === true && (
        <div>
          <div className="text-xs text-subtle mb-1">Hangi sınıf seviyeleri için uygun? (çoklu, en az 1)</div>
          <div className="flex flex-wrap gap-1.5">
            {SINIF_SECENEK.map((s) => (
              <button key={s} onClick={() => sinifToggle(s)} className={`px-2.5 py-1 rounded-lg text-xs border ${siniflar.includes(s) ? "bg-primary text-white border-primary" : "bg-app border-line text-subtle"}`}>{sinifEtiket(s)}</button>
            ))}
          </div>
        </div>
      )}

      <textarea value={talep} onChange={(e) => setTalep(e.target.value)} rows={2}
        placeholder="Değişiklik talebi (opsiyonel) — düzeltilmesini istediğiniz nokta…"
        className="w-full px-3 py-2 rounded-lg border border-line text-sm" />

      <button onClick={gonder} disabled={kaydet} className="w-full bg-primary hover:bg-primary-hover text-white rounded-xl py-2.5 text-sm font-semibold disabled:opacity-50 inline-flex items-center justify-center gap-1.5">
        {kaydet ? "Kaydediliyor…" : <>Kaydet ve Sonraki <Sparkles className="h-4 w-4" /></>}
      </button>
    </div>
  );
}

// ── Sıralı akış (tab veya modal içinde) ──
function DegerlendirmeAkisi({ apiBase, egzersizler, toast, onBitti, kompakt }) {
  const [idx, setIdx] = useState(0);
  const [xpToplam, setXpToplam] = useState(0);
  const toplam = egzersizler.length;

  const tamam = (id, xp) => {
    setXpToplam((v) => v + (xp || 0));
    if (idx + 1 >= toplam) { onBitti?.(xpToplam + (xp || 0)); }
    else { setIdx((i) => i + 1); }
  };

  if (idx >= toplam) return null;
  const oran = Math.round((idx / toplam) * 100);

  return (
    <div className={kompakt ? "space-y-3" : "max-w-2xl mx-auto space-y-3"}>
      {/* İlerleme */}
      <div>
        <div className="flex items-center justify-between text-xs text-subtle mb-1">
          <span>{idx} / {toplam} tamamlandı</span>
          {xpToplam > 0 && <span className="text-green-600 font-semibold">+{xpToplam} XP</span>}
        </div>
        <div className="h-1.5 rounded-full bg-app overflow-hidden">
          <div className="h-full bg-gradient-to-r from-primary to-indigo-500 transition-all" style={{ width: `${oran}%` }} />
        </div>
      </div>
      <TekEgzersizDegerlendir key={egzersizler[idx].egzersiz_id} apiBase={apiBase} egzersiz={egzersizler[idx]} toast={toast} onTamam={tamam} />
    </div>
  );
}

// ── Öğretmen paneli: Kalite Kontrol sekmesi ──
export function KaliteKontrolSekmesi({ apiBase, user, toast }) {
  const [veri, setVeri] = useState(null);
  const [yuk, setYuk] = useState(false);
  const [bitti, setBitti] = useState(null); // {xp}

  const yukle = useCallback(async () => {
    setYuk(true); setBitti(null);
    try {
      const r = await axios.get(`${apiBase}/egzersiz-kalite/kuyruk?limit=5`);
      setVeri(r.data);
    } catch (e) { setVeri({ egzersizler: [], toplam_bekleyen: 0 }); } finally { setYuk(false); }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <ClipboardCheck className="h-5 w-5 text-primary" />
        <div>
          <div className="font-bold text-content">Egzersiz Kalite Kontrol</div>
          <div className="text-xs text-subtle">Egzersizleri tek tek önizleyip değerlendir. Her değerlendirme XP kazandırır.</div>
        </div>
        <button onClick={yukle} disabled={yuk} className="ml-auto inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-3 py-1.5 text-sm"><RefreshCw className={`h-4 w-4 ${yuk ? "animate-spin" : ""}`} />Yenile</button>
      </div>

      {bitti ? (
        <div className="max-w-2xl mx-auto text-center py-10 bg-surface rounded-2xl border border-line">
          <div className="text-4xl mb-2">✅</div>
          <div className="font-bold text-content">Bugünkü kalite kontrolünü tamamladın!</div>
          {bitti.xp > 0 && <div className="text-green-600 font-semibold mt-1">+{bitti.xp} XP kazandın 🎉</div>}
          <div className="text-xs text-subtle mt-2">Katkın için teşekkürler — egzersiz havuzu senin sayende daha iyi.</div>
          <button onClick={yukle} className="mt-4 inline-flex items-center gap-1.5 bg-primary text-white rounded-lg px-4 py-2 text-sm font-semibold">Devam et →</button>
        </div>
      ) : veri && veri.egzersizler.length === 0 ? (
        <div className="max-w-2xl mx-auto text-center text-subtle py-10 bg-surface rounded-2xl border border-line">🎉 Şu an değerlendirilecek egzersiz kalmadı. Sonra tekrar bakın.</div>
      ) : veri && veri.egzersizler.length > 0 ? (
        <DegerlendirmeAkisi apiBase={apiBase} egzersizler={veri.egzersizler} toast={toast} onBitti={(xp) => setBitti({ xp })} />
      ) : (
        <div className="text-center text-subtle py-10">Yükleniyor…</div>
      )}
    </div>
  );
}

// ── Günlük hatırlatma modalı (öğretmen; günde bir kez) ──
export function GunlukKaliteModal({ apiBase, user, toast }) {
  const [acik, setAcik] = useState(false);
  const [egzersizler, setEgzersizler] = useState([]);
  const [bitti, setBitti] = useState(null);
  const gunKey = `kalite_reminder_${user?.id}_${new Date().toDateString()}`;

  useEffect(() => {
    if (!user?.id || user.role !== "teacher") return;
    if (localStorage.getItem(gunKey)) return;
    axios.get(`${apiBase}/egzersiz-kalite/kuyruk?limit=3`).then((r) => {
      if ((r.data?.egzersizler || []).length > 0) { setEgzersizler(r.data.egzersizler); setAcik(true); }
      else localStorage.setItem(gunKey, "1");
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const kapat = () => { localStorage.setItem(gunKey, "1"); setAcik(false); };

  if (!acik) return null;
  return (
    <div className="fixed inset-0 z-[80] bg-black/50 flex items-start justify-center p-4 overflow-y-auto" onClick={kapat}>
      <div className="bg-app rounded-2xl shadow-xl w-full max-w-lg my-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 p-4 border-b border-line">
          <ClipboardCheck className="h-5 w-5 text-primary" />
          <div className="font-bold text-content">Günlük Kalite Kontrol</div>
          <button onClick={kapat} className="ml-auto text-sm text-subtle hover:text-content px-2">Daha sonra ✕</button>
        </div>
        <div className="p-4">
          {bitti ? (
            <div className="text-center py-6">
              <div className="text-4xl mb-2">✅</div>
              <div className="font-bold text-content">Tamamlandı!</div>
              {bitti.xp > 0 && <div className="text-green-600 font-semibold mt-1">+{bitti.xp} XP 🎉</div>}
              <button onClick={kapat} className="mt-4 bg-primary text-white rounded-lg px-4 py-2 text-sm font-semibold">Kapat</button>
            </div>
          ) : (
            <>
              <p className="text-xs text-subtle mb-3">Birkaç egzersizi değerlendirerek kaliteyi yükseltmemize yardım edin. İstemezseniz "Daha sonra" ile kapatabilirsiniz.</p>
              <DegerlendirmeAkisi apiBase={apiBase} egzersizler={egzersizler} toast={toast} kompakt onBitti={(xp) => setBitti({ xp })} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Admin/koordinatör: Kalite Kontrol Bekleyenler kuyruğu + eşik ayarları ──
export function KaliteBekleyenler({ apiBase, toast }) {
  const [veri, setVeri] = useState(null);
  const [yuk, setYuk] = useState(false);
  const [ayar, setAyar] = useState(null);
  const [ayarKaydet, setAyarKaydet] = useState(false);
  const [onizle, setOnizle] = useState(null); // açık önizleme egzersiz_id

  const yukle = useCallback(async () => {
    setYuk(true);
    try {
      const [b, a] = await Promise.all([
        axios.get(`${apiBase}/egzersiz-kalite/bekleyenler`),
        axios.get(`${apiBase}/egzersiz-kalite/ayarlar`),
      ]);
      setVeri(b.data); setAyar(a.data);
    } catch (e) { /* yut */ } finally { setYuk(false); }
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  const karar = async (id, tip) => {
    try {
      await axios.post(`${apiBase}/egzersiz-kalite/${id}/${tip}`);
      toast({ title: tip === "aktif-et" ? "✓ Tekrar aktifleştirildi" : "🗑️ Kalıcı olarak kaldırıldı" });
      yukle();
    } catch (e) { toast({ title: "İşlem başarısız", variant: "destructive" }); }
  };
  const ayarSave = async () => {
    setAyarKaydet(true);
    try { const r = await axios.put(`${apiBase}/egzersiz-kalite/ayarlar`, ayar); setAyar(r.data.degerler); toast({ title: "✅ Eşikler kaydedildi" }); }
    catch (e) { toast({ title: "Kaydedilemedi", variant: "destructive" }); } finally { setAyarKaydet(false); }
  };

  return (
    <div className="space-y-5">
      {ayar && (
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="font-semibold text-content mb-3">Kalite Kontrol Eşikleri</div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <label className="text-xs text-subtle">Otomatik askıya alma (kaç olumsuz oy)
              <input type="number" min="1" value={ayar.askiya_alma_esigi} onChange={(e) => setAyar({ ...ayar, askiya_alma_esigi: parseInt(e.target.value) || 1 })} className="mt-1 w-full px-3 py-2 rounded-lg border border-line text-sm" />
            </label>
            <label className="text-xs text-subtle">Sınıf uygunluğu (kaç "uygun" oyu)
              <input type="number" min="1" value={ayar.sinif_uygunluk_esigi} onChange={(e) => setAyar({ ...ayar, sinif_uygunluk_esigi: parseInt(e.target.value) || 1 })} className="mt-1 w-full px-3 py-2 rounded-lg border border-line text-sm" />
            </label>
            <label className="text-xs text-subtle">Doğrulanmış rozeti (kaç "uygun")
              <input type="number" min="1" value={ayar.dogrulama_esigi} onChange={(e) => setAyar({ ...ayar, dogrulama_esigi: parseInt(e.target.value) || 1 })} className="mt-1 w-full px-3 py-2 rounded-lg border border-line text-sm" />
            </label>
          </div>
          <button onClick={ayarSave} disabled={ayarKaydet} className="mt-3 inline-flex items-center gap-1.5 bg-primary text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"><Save className="h-4 w-4" />Kaydet</button>
        </div>
      )}

      <div className="flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 text-amber-500" />
        <div className="font-semibold text-content">Askıya Alınan Egzersizler {veri ? `(${veri.toplam})` : ""}</div>
        <button onClick={yukle} disabled={yuk} className="ml-auto inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-3 py-1.5 text-sm"><RefreshCw className={`h-4 w-4 ${yuk ? "animate-spin" : ""}`} />Yenile</button>
      </div>
      {veri && veri.egzersizler.length === 0 ? (
        <div className="text-center text-subtle py-8 bg-surface rounded-2xl border border-line">Askıda egzersiz yok.</div>
      ) : (
        <div className="space-y-3">
          {(veri?.egzersizler || []).map((e) => (
            <div key={e.egzersiz_id} className="rounded-2xl border border-amber-200 bg-amber-50/40 p-4">
              <div className="flex items-center gap-2 flex-wrap mb-2">
                <span className="text-xs font-semibold bg-primary/10 text-primary rounded-full px-2 py-0.5">{e.tip_ad}</span>
                <span className="text-xs text-subtle">{sinifEtiket(e.sinif)} · {e.zorluk}</span>
                <span className="text-xs text-red-600">{e.uygun_degil_sayisi} uygun değil · {e.degisiklik_talebi_sayisi} değişiklik talebi</span>
                <button onClick={() => setOnizle(onizle === e.egzersiz_id ? null : e.egzersiz_id)} className="ml-auto text-xs text-primary hover:underline">{onizle === e.egzersiz_id ? "Önizlemeyi kapat" : "Önizle"}</button>
              </div>
              {onizle === e.egzersiz_id && (
                <div className="bg-surface rounded-lg p-2 mb-2">
                  <EgzersizOnizleme apiBase={apiBase} tip={e.tip} sinif={typeof e.sinif === "number" ? e.sinif : 3} icerikId={e.egzersiz_id} />
                </div>
              )}
              {e.degerlendirmeler.some((d) => d.degisiklik_talebi) && (
                <div className="mb-2 space-y-1">
                  <div className="text-xs font-semibold text-content">Değişiklik Talepleri:</div>
                  {e.degerlendirmeler.filter((d) => d.degisiklik_talebi).map((d, i) => (
                    <div key={i} className="text-xs text-content bg-surface rounded px-2 py-1 border border-line">
                      <b>{d.ogretmen_ad || "Öğretmen"}:</b> {d.degisiklik_talebi}
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <button onClick={() => karar(e.egzersiz_id, "aktif-et")} className="inline-flex items-center gap-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg px-3 py-1.5 text-sm"><RotateCcw className="h-4 w-4" />Düzeltildi · Tekrar Aktif Et</button>
                <button onClick={() => karar(e.egzersiz_id, "retire")} className="inline-flex items-center gap-1.5 bg-app border border-line text-red-600 rounded-lg px-3 py-1.5 text-sm"><Archive className="h-4 w-4" />Kalıcı Kaldır</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
