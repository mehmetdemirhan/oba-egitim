import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { ShieldCheck, Play, CheckCircle2, XCircle, RefreshCw, Copy, Check, RotateCw, ExternalLink } from "lucide-react";
import BilgiIkonu from "../BilgiIkonu";
import { PersonaBalon } from "./Personalar";
import GeriBildirimWidget from "./GeriBildirimWidget";

const ONEM_RENK = { kritik: "border-red-300 bg-red-50 text-red-700", orta: "border-amber-300 bg-amber-50 text-amber-700", dusuk: "border-slate-300 bg-slate-50 text-slate-600" };
const DURUM_ET = { yeni: "Yeni", admin_gecerli: "Geçerli", admin_gecersiz: "Geçersiz", cozuldu: "Çözüldü" };
const OZELLIK_AD = { ceo_analiz: "Ayda analiz", ceo_brifing: "Ayda brifing", ceo_sohbet: "Ayda sohbet", miran_kocluk: "Miran koçluk", miran_muhasebe: "Miran muhasebe", denetim: "Deniz denetim", pazar_arastirma: "Pazar araştırma", etiketsiz: "Etiketsiz (eski)", diger: "Diğer" };

/**
 * Deniz — Denetçi AI (yalnız admin). Ayda'nın çıktılarını bağımsız denetler.
 * Deterministik kontroller + AI denetim turu + admin onaylı iyileştirme notu + karne.
 * Sayfa açılışında AI çağrısı YOK (kayıtlı denetim gösterilir; "Denetle" ile tetiklenir).
 */
export default function Deniz({ apiBase, onNavigate }) {
  const [denetim, setDenetim] = useState(null);
  const [bulgular, setBulgular] = useState([]);
  const [karne, setKarne] = useState(null);
  const [notlar, setNotlar] = useState([]);
  const [maliyet, setMaliyet] = useState(null);
  const [ret, setRet] = useState(null);
  const [sinav, setSinav] = useState(null);
  const [calisiyor, setCalisiyor] = useState(false);
  const api = (p) => `${apiBase}${p}`;

  const yukle = useCallback(async () => {
    const [s, k, n, m, r] = await Promise.all([
      axios.get(api("/ai/ceo/deniz/son")).catch(() => null),
      axios.get(api("/ai/ceo/deniz/karne")).catch(() => null),
      axios.get(api("/ai/ceo/deniz/notlar")).catch(() => null),
      axios.get(api("/ai/ceo/deniz/maliyet")).catch(() => null),
      axios.get(api("/ai/ceo/deniz/ret-otopsisi")).catch(() => null),
    ]);
    if (s) { setDenetim(s.data.denetim); setBulgular(s.data.bulgular || []); }
    if (k) setKarne(k.data.karne);
    if (n) setNotlar(n.data.notlar || []);
    if (m) setMaliyet(m.data.maliyet);
    if (r) setRet(r.data.ret_otopsisi);
  }, [apiBase]);

  const sinavYap = async () => { try { const r = await axios.post(api("/ai/ceo/deniz/sinav")); setSinav(r.data.ok ? r.data.sinav : { hata: r.data.sebep }); await yukle(); } catch (e) { setSinav({ hata: "Sınav çalışmadı" }); } };

  const [seciliBulgu, setSeciliBulgu] = useState(null);
  const [detay, setDetay] = useState(null);
  const [kopyalandi, setKopyalandi] = useState(false);
  const [kontrolSonuc, setKontrolSonuc] = useState(null);
  const [kontrolCalisiyor, setKontrolCalisiyor] = useState(false);

  const bulguAc = async (b) => {
    setSeciliBulgu(b); setDetay(null); setKontrolSonuc(null); setKopyalandi(false);
    try { const r = await axios.get(api(`/ai/ceo/deniz/bulgu/${b.id}`)); setDetay(r.data); } catch (e) {}
  };
  const kopyala = (t) => { try { navigator.clipboard.writeText(t); setKopyalandi(true); setTimeout(() => setKopyalandi(false), 1500); } catch (e) {} };
  const kontrolEt = async () => {
    if (!seciliBulgu) return;
    setKontrolCalisiyor(true);
    try { const r = await axios.post(api(`/ai/ceo/deniz/bulgu/${seciliBulgu.id}/kontrol`)); setKontrolSonuc(r.data); await yukle(); if (r.data.durum === "cozuldu") setSeciliBulgu(s => ({ ...s, durum: "cozuldu" })); }
    catch (e) {} finally { setKontrolCalisiyor(false); }
  };
  // Kanıttan derin link: öğrenci id varsa (yetim kur / arşivli borç / damgasız) Muhasebe'yi o
  // öğrenciye ODAKLAR (satırı süzer+vurgular); yoksa yalnız sekmeye götürür.
  const ornekGit = (o) => { if (onNavigate) onNavigate("payments", o.ogrenci_id || ""); };

  useEffect(() => { yukle(); }, [yukle]);

  const denetle = async () => {
    setCalisiyor(true);
    try { await axios.post(api("/ai/ceo/deniz/denetle")); await yukle(); }
    finally { setCalisiyor(false); }
  };
  const bulguDurum = async (b, durum) => { await axios.put(api(`/ai/ceo/deniz/bulgu/${b.id}/durum`), { durum }); await yukle(); };
  const notOnayla = async (id) => { await axios.post(api(`/ai/ceo/deniz/not/${id}/onayla`)); await yukle(); };
  const notEkle = async () => {
    const metin = denetim?.iyilestirme_plani;
    if (!metin) return;
    await axios.post(api("/ai/ceo/deniz/not"), { metin }); await yukle();
  };

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          <div className="flex-1"><PersonaBalon persona="deniz" mesaj={denetim?.ozet || "Ayda'nın çıktılarını bağımsız denetliyorum. 'Denetle' ile turu başlat."} /></div>
          <button onClick={denetle} disabled={calisiyor} className="inline-flex items-center gap-1.5 bg-slate-700 hover:bg-slate-800 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-xl">
            {calisiyor ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}{calisiyor ? "Denetleniyor…" : "Denetle"}
          </button>
        </div>
      </div>

      {/* Karne */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-bold text-content text-sm flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-slate-600" />Deniz'in Karnesi</h3>
          <BilgiIkonu nasil="Bulgu doğruluğu = admin'in geçerli bulduğu / değerlendirilen bulgu; yakalama değeri = çözülen kritik / toplam kritik; kaçırma = admin'in 'Deniz kaçırdı' işaretleri. Tümü deterministik." ne="Denetçinin gerçekten işe yarayıp yaramadığını (kovma kararı dahil) sayıyla görmek için." />
        </div>
        {karne ? (
          <>
            <div className="text-sm text-content mb-2">{karne.ozet}</div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center">
              {[["Bulgu Doğruluğu", karne.bulgu_dogrulugu, "%"], ["Kritik Yakalama", karne.yakalama_degeri, "%"], ["Sınav Kalitesi", karne.sinav_skoru, "%"], ["Doğrulanamayan Sayı", karne.sayi_dogrulanamayan_orani, "%"], ["Toplam Bulgu", karne.toplam_bulgu, ""], ["Kaçırma", karne.kacirilan_bildirilen, ""]].map(([l, v, u], i) => (
                <div key={i} className="rounded-lg bg-app border border-line p-2"><div className="text-base font-bold tabular-nums">{v == null ? "—" : `${u === "%" ? "%" : ""}${v}`}</div><div className="text-[10px] text-subtle">{l}</div></div>
              ))}
            </div>
          </>
        ) : <div className="text-sm text-subtle">Karne verisi yok.</div>}
      </div>

      {/* Bulgular */}
      <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <h3 className="font-bold text-content text-sm mb-2">Denetim Bulguları</h3>
        {bulgular.length === 0 ? <div className="text-sm text-subtle">Bulgu yok — "Denetle" ile tur başlat.</div> : (
          <div className="space-y-2">
            {bulgular.map(b => (
              <div key={b.id} className={`rounded-lg border p-2 ${b.durum === "cozuldu" ? "border-emerald-300 bg-emerald-50" : ONEM_RENK[b.onem] || "border-line"}`}>
                <div className="flex items-center justify-between gap-2 cursor-pointer" onClick={() => bulguAc(b)}>
                  <span className="text-sm font-medium text-content">{b.durum === "cozuldu" && "✅ "}{b.ozet}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/60 border border-current">{b.onem}</span>
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[10px] text-subtle">{b.tur} · {DURUM_ET[b.durum] || b.durum} · {b.kaynak}</span>
                  {b.durum === "yeni" && (
                    <span className="ml-auto flex gap-2">
                      <button onClick={() => bulguDurum(b, "admin_gecerli")} className="inline-flex items-center gap-0.5 text-[11px] text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />Geçerli</button>
                      <button onClick={() => bulguDurum(b, "admin_gecersiz")} className="inline-flex items-center gap-0.5 text-[11px] text-red-600"><XCircle className="h-3.5 w-3.5" />Geçersiz</button>
                    </span>
                  )}
                  {b.durum === "admin_gecerli" && <button onClick={() => bulguDurum(b, "cozuldu")} className="ml-auto text-[11px] text-indigo-600">Çözüldü işaretle</button>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* S9 güçlendirme: sınav + maliyet + ret otopsisi */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-1"><h3 className="font-bold text-content text-sm">Sınav Düzeni</h3><BilgiIkonu nasil="Doğru cevabı bilinen sentetik durumlar Ayda'ya habersiz verilir; yakalama oranı skorlanır. Sonuçlar gerçek kuyruğa/karneye KARIŞMAZ." ne="Ayda'nın gerçekten doğru teşhis koyup koymadığını sınamak için." /></div>
          <button onClick={sinavYap} className="text-xs bg-slate-700 text-white rounded-lg px-3 py-1.5">Sınav Yap</button>
          {sinav && (sinav.hata ? <div className="text-xs text-amber-600 mt-2">{sinav.hata}</div> : <div className="text-sm mt-2">Skor: <b className="tabular-nums">%{sinav.skor}</b> ({sinav.yakalanan}/{sinav.toplam})</div>)}
        </div>
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-1"><h3 className="font-bold text-content text-sm">Maliyet Denetimi</h3><BilgiIkonu nasil="Tüm AI çağrıları merkezi sayaçtan (model + ay); son ay ≥%100 artış anormal sıçrama sayılır." ne="AI maliyetini izleyip anormal artışları erken görmek için." /></div>
          {maliyet ? <div className="text-sm space-y-0.5"><div>Toplam çağrı: <b className="tabular-nums">{maliyet.toplam_cagri}</b></div><div className="text-xs text-subtle">Grounded: {maliyet.grounded_cagri}</div>{maliyet.anormal_sicrama_yuzde && <div className="text-xs text-red-600">⚠ Son ay +%{maliyet.anormal_sicrama_yuzde} sıçrama</div>}</div> : <div className="text-sm text-subtle">—</div>}
        </div>
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-1"><h3 className="font-bold text-content text-sm">Ret Otopsisi</h3><BilgiIkonu nasil="Reddedilen öneriler 30+ gün sonra ilgili metriğe göre yeniden değerlendirilir: metrik kötüleştiyse 'ret sonrası haklı çıktı', iyiyse 'ret isabetliydi'." ne="Reddetme kararlarının kalibrasyonunu ölçmek için (çift yönlü)." /></div>
          {ret ? <div className="text-sm space-y-0.5"><div>Reddedilen: <b className="tabular-nums">{ret.reddedilen}</b></div><div className="text-xs text-emerald-600">Haklı çıktı: {ret.ret_sonrasi_hakli_cikti}</div><div className="text-xs text-subtle">Ret isabetliydi: {ret.ret_isabetliydi} · Beklemede: {ret.beklemede}</div></div> : <div className="text-sm text-subtle">—</div>}
        </div>
      </div>

      {/* İyileştirme planı → onaylı not (guard) */}
      {(denetim?.iyilestirme_plani || notlar.length > 0) && (
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-1">
            <h3 className="font-bold text-content text-sm">İyileştirme Planı → Ayda'ya Not</h3>
            <BilgiIkonu nasil="Deniz'in iyileştirme planı yalnız admin ONAYIYLA sonraki Ayda analizinin promptuna 'denetim notu' olarak girer." ne="Ayda'yı otomatik değil, kontrollü biçimde iyileştirmek için (oto self-modifikasyon yok)." />
          </div>
          {denetim?.iyilestirme_plani && (
            <div className="text-sm text-content mb-2">{denetim.iyilestirme_plani}
              <button onClick={notEkle} className="ml-2 text-[11px] text-indigo-600 hover:underline">Taslak nota ekle</button>
            </div>
          )}
          {notlar.map(n => (
            <div key={n.id} className="rounded-lg border border-line p-2 text-sm flex items-center justify-between gap-2">
              <span className="flex-1">{n.metin}</span>
              {n.onayli ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">Onaylı</span>
                : <button onClick={() => notOnayla(n.id)} className="text-[11px] text-emerald-700 font-medium">Onayla</button>}
            </div>
          ))}
        </div>
      )}

      {/* ── Bulgu detay modalı (kanıt + çözüm + Kontrol Et) ── */}
      {seciliBulgu && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setSeciliBulgu(null)}>
          <div className="bg-surface rounded-2xl max-w-2xl w-full max-h-[88vh] overflow-auto p-5" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <h3 className="font-bold text-content">{seciliBulgu.ozet}</h3>
                <GeriBildirimWidget apiBase={apiBase} ajan="deniz" kaynakId={seciliBulgu.id} kaynakTur="denetim" kategori={seciliBulgu.tur} />
              </div>
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${ONEM_RENK[seciliBulgu.onem]}`}>{seciliBulgu.onem}</span>
            </div>
            {!detay ? <div className="text-sm text-subtle mt-3">Yükleniyor…</div> : (
              <>
                {/* Kanıt + derin link örnekleri */}
                {(detay.bulgu.kanit?.ornekler || []).length > 0 && (
                  <div className="mt-3">
                    <div className="text-xs font-semibold text-content mb-1">Kanıt</div>
                    <div className="space-y-1 max-h-40 overflow-auto">
                      {detay.bulgu.kanit.ornekler.map((o, i) => (
                        <div key={i} className="flex items-center justify-between text-xs bg-app border border-line rounded px-2 py-1">
                          <span className="tabular-nums">{o.tip}: {o.kur_id || o.ogrenci_id || o.id || o.oneri_id}{o.kalan != null && ` · kalan ${o.kalan}`}{o.sayi != null && ` · sayı ${o.sayi}`}{o.cumle && ` — "${o.cumle}"`}</span>
                          {onNavigate && (o.tip === "kur" || o.tip === "ogrenci" || o.tip === "kayit") && (
                            <button onClick={() => ornekGit(o)} className="inline-flex items-center gap-0.5 text-[11px] text-indigo-600 shrink-0"><ExternalLink className="h-3 w-3" />Git</button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Maliyet: özellik-bazlı çağrı kırılımı (hangi AI özelliği kaç çağrı) */}
                {detay.bulgu.kanit?.ozellik_dagilimi && Object.keys(detay.bulgu.kanit.ozellik_dagilimi).length > 0 && (
                  <div className="mt-3">
                    <div className="text-xs font-semibold text-content mb-1">Özellik bazlı çağrı</div>
                    <div className="rounded border border-line overflow-hidden">
                      {Object.entries(detay.bulgu.kanit.ozellik_dagilimi).map(([oz, n]) => (
                        <div key={oz} className="flex items-center justify-between text-xs px-2 py-1 odd:bg-app">
                          <span>{OZELLIK_AD[oz] || oz}</span><span className="tabular-nums font-medium">{n}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Çözüm önerisi */}
                <div className="mt-3">
                  <div className="text-xs font-semibold text-content mb-1">Çözüm Önerisi</div>
                  <div className="text-sm text-content mb-2">{detay.cozum.oneri}</div>
                  {detay.cozum.tip === "prompt" ? (
                    <div className="relative">
                      <pre className="text-[11px] bg-slate-900 text-slate-100 rounded-lg p-3 overflow-auto whitespace-pre-wrap max-h-56">{detay.cozum.prompt}</pre>
                      <button onClick={() => kopyala(detay.cozum.prompt)} className="absolute top-2 right-2 inline-flex items-center gap-1 text-[11px] bg-slate-700 text-white rounded px-2 py-1">
                        {kopyalandi ? <><Check className="h-3 w-3" />Kopyalandı</> : <><Copy className="h-3 w-3" />Kopyala</>}
                      </button>
                    </div>
                  ) : (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 text-amber-800 text-sm p-3">🛠️ Operasyonel adım: {detay.cozum.adim}</div>
                  )}
                </div>
                {/* Kontrol Et */}
                <div className="mt-4 flex items-center gap-3">
                  <button onClick={kontrolEt} disabled={kontrolCalisiyor} className="inline-flex items-center gap-1.5 bg-indigo-600 disabled:opacity-60 text-white text-sm rounded-lg px-4 py-2">
                    {kontrolCalisiyor ? <RefreshCw className="h-4 w-4 animate-spin" /> : <RotateCw className="h-4 w-4" />}Kontrol Et
                  </button>
                  {kontrolSonuc && (
                    <span className="text-sm">
                      {kontrolSonuc.durum === "cozuldu" ? <span className="text-emerald-600 font-medium">✅ Çözüldü</span>
                        : kontrolSonuc.durum === "sonraki_tur" ? <span className="text-slate-500">Sonraki denetim turuna işaretlendi</span>
                          : <span className="text-amber-600">Henüz çözülmedi — güncel kanıt: {JSON.stringify(kontrolSonuc.guncel_kanit?.sayi ?? kontrolSonuc.guncel_kanit)}</span>}
                    </span>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
