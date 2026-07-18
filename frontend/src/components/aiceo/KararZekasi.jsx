import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Sparkles, RefreshCw, Activity, CheckCircle, XCircle, ShieldAlert, PlayCircle, GraduationCap } from "lucide-react";
import { PersonaBalon } from "./Personalar";

/**
 * KararZekasi — Ayda Kurumsal Karar Zekâsı (Faz 2). GERÇEK sistem fotoğrafından kanıtlı
 * yapılandırılmış teklif → karar → uygula (pilot) → öğrenme. Uçlar /ai/ceo/karar/*.
 * Determinizm: sayılar gerçek fotoğraftan; AI yoksa deterministik taslak (uydurma yok).
 */
const DURUM_ET = { awaiting_decision: "Karar bekliyor", approved: "Onaylı", rejected: "Reddedildi", implemented: "Uygulamada" };
const DURUM_RENK = {
  awaiting_decision: "bg-amber-100 text-amber-700", approved: "bg-blue-100 text-blue-700",
  rejected: "bg-red-100 text-red-700", implemented: "bg-emerald-100 text-emerald-700",
};

export default function KararZekasi({ apiBase, user }) {
  const [durum, setDurum] = useState(null);
  const [secili, setSecili] = useState(null);
  const [seviye, setSeviye] = useState(1);
  const [yuk, setYuk] = useState("");
  const [mesaj, setMesaj] = useState("");
  const isAdmin = user?.role === "admin";
  const api = (x) => `${apiBase}${x}`;

  const yukle = useCallback(async () => {
    try {
      const r = await axios.get(api("/ai/ceo/karar/durum"));
      setDurum(r.data);
      const ilk = (r.data.son_teklifler || [])[0];
      setSecili(s => s || ilk || null);
    } catch (e) {}
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  const tarat = async () => {
    setYuk("tarat"); setMesaj("");
    try {
      const r = await axios.post(api("/ai/ceo/karar/teklif-uret"));
      setSecili(r.data.teklif);
      setMesaj(r.data.teklif?._kaynak === "ai" ? "Ayda derin analizi tamamladı, yeni karar belgesi hazır." : "AI kullanılamadı — gerçek metrikten deterministik taslak üretildi.");
      await yukle();
    } catch (e) { setMesaj("Analiz başarısız: " + (e.response?.data?.detail || e.message)); }
    finally { setYuk(""); }
  };

  const karar = async (id, k) => {
    setYuk(k); try { await axios.post(api(`/ai/ceo/karar/teklif/${id}/karar`), { karar: k }); await sonrasi(id); } catch (e) { hata(e); } finally { setYuk(""); }
  };
  const uygula = async (id) => {
    setYuk("uygula"); try { await axios.post(api(`/ai/ceo/karar/teklif/${id}/uygula`)); await sonrasi(id); } catch (e) { hata(e); } finally { setYuk(""); }
  };
  const ogrenmeKaydet = async (id) => {
    const actual = window.prompt("Deney gerçek sonucu (birincil metrik değeri):");
    if (actual === null) return;
    const lesson = window.prompt("Çıkarılan ders (kurumsal hafızaya pattern adayı):") || "";
    setYuk("ogrenme");
    try { await axios.post(api(`/ai/ceo/karar/teklif/${id}/ogrenme`), { actual_result: parseFloat(actual) || null, lesson }); await sonrasi(id); setMesaj("Öğrenme kaydedildi; ders kurumsal hafızaya onay için eklendi."); }
    catch (e) { hata(e); } finally { setYuk(""); }
  };
  const olcumCalistir = async (id) => {
    setYuk("olcum");
    try { const r = await axios.post(api("/ai/ceo/karar/olcum-calistir")); setMesaj(`Checkpoint ölçümü çalıştı (${r.data.guncellenen_teklif} teklif güncellendi).`); await sonrasi(id); }
    catch (e) { hata(e); } finally { setYuk(""); }
  };
  const sonrasi = async (id) => { await yukle(); const r = await axios.get(api(`/ai/ceo/karar/teklif/${id}`)); setSecili(r.data); };
  const hata = (e) => setMesaj("İşlem başarısız: " + (e.response?.data?.detail || e.message));

  if (!durum) return <div className="text-sm text-subtle p-4">Karar Zekâsı yükleniyor…</div>;
  const t = secili;
  const tl = (v) => (v == null ? "—" : Number(v).toLocaleString("tr-TR"));

  return (
    <div className="space-y-4">
      {/* Başlık + tarama */}
      <div className="flex items-center justify-between flex-wrap gap-3 rounded-2xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-center gap-3">
          <PersonaBalon persona="ayda" mesaj="Kurumsal Karar Zekâsı — segment bazlı derin tarama, hipotez ve kontrollü pilot." size={44} />
        </div>
        <div className="flex items-center gap-2">
          {durum.saglik?.skor != null && <span className="text-xs text-subtle">Sağlık <b className="text-content">{durum.saglik.skor}</b> · Veri kalitesi <b>%{durum.veri_kalitesi}</b></span>}
          <button onClick={tarat} disabled={!!yuk} className="inline-flex items-center gap-1.5 bg-indigo-600 disabled:opacity-60 text-white text-sm rounded-lg px-4 py-2">
            {yuk === "tarat" ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}Derin Tarat (AI)
          </button>
        </div>
      </div>

      {mesaj && <div className="text-sm rounded-lg bg-app border border-line px-3 py-2">{mesaj}</div>}

      {/* Metrik ihlalleri (gerçek) */}
      {(durum.ihlaller || []).length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-3">
          <div className="text-xs font-semibold text-amber-800 mb-1.5 flex items-center gap-1"><ShieldAlert className="h-4 w-4" />Eşik altı metrikler (gerçek)</div>
          <div className="flex flex-wrap gap-2">
            {durum.ihlaller.map(i => (
              <span key={i.key} className="text-xs bg-surface border border-amber-200 rounded-lg px-2 py-1">{i.ad}: <b>{i.deger}</b> <span className="text-subtle">(eşik {i.esik}, sapma %{i.sapma_yuzde})</span></span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Teklif kuyruğu */}
        <div className="rounded-2xl border border-line bg-surface p-3 shadow-sm">
          <div className="text-xs font-semibold text-subtle uppercase mb-2">Karar Belgeleri</div>
          <div className="space-y-2 max-h-[28rem] overflow-auto">
            {(durum.son_teklifler || []).length === 0 && <div className="text-sm text-subtle py-6 text-center">Henüz teklif yok — "Derin Tarat" ile üret.</div>}
            {(durum.son_teklifler || []).map(x => (
              <button key={x.id} onClick={() => { setSecili(x); setSeviye(1); }}
                className={`w-full text-left p-3 rounded-lg border transition ${secili?.id === x.id ? "border-indigo-300 bg-indigo-50/50" : "border-line hover:bg-app"}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-content line-clamp-1">{x.title}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${DURUM_RENK[x.status] || "bg-app"}`}>{DURUM_ET[x.status] || x.status}</span>
                </div>
                <div className="text-[11px] text-subtle line-clamp-2 mt-0.5">{x.problem?.statement}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Detay — 3 seviye */}
        <div className="lg:col-span-2 rounded-2xl border border-line bg-surface shadow-sm overflow-hidden">
          {!t ? <div className="p-10 text-center text-subtle text-sm">Bir karar belgesi seçin.</div> : (
            <>
              <div className="flex border-b border-line">
                {[[1, "Yönetici Özeti"], [2, "Karar Dosyası"], [3, "Öğrenme & Denetim"]].map(([n, l]) => (
                  <button key={n} onClick={() => setSeviye(n)} className={`flex-1 py-2.5 text-xs font-semibold ${seviye === n ? "text-primary border-b-2 border-primary" : "text-subtle"}`}>{l}</button>
                ))}
              </div>
              <div className="p-4 space-y-4">
                {t._kaynak === "deterministik" && <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">Deterministik taslak (AI yok/ayrıştırılamadı) — sayılar gerçek metrikten, uydurma yok.</div>}

                {seviye === 1 && (
                  <>
                    <div className="border-l-4 border-red-400 pl-3">
                      <div className="text-[11px] font-bold uppercase text-subtle">Sorun</div>
                      <div className="text-sm font-semibold text-content">{t.problem?.statement}</div>
                      <div className="text-xs text-red-600 mt-0.5">Yıllık tahmini kayıp: {t.problem?.estimated_annual_loss != null ? tl(t.problem.estimated_annual_loss) + " ₺" : "—"} · Önem: {t.problem?.severity_score ?? "—"}</div>
                    </div>
                    <div className="border-l-4 border-emerald-400 pl-3">
                      <div className="text-[11px] font-bold uppercase text-subtle">Önerilen aksiyon</div>
                      <div className="text-sm font-bold text-emerald-700">{t.recommendation?.selected_alternative}</div>
                      <div className="text-sm text-content mt-0.5">{t.recommendation?.rationale}</div>
                      <div className="text-xs text-subtle mt-0.5">Güven: {t.recommendation?.confidence ?? "—"}</div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 bg-app rounded-xl p-3 border border-line">
                      <div><div className="text-[11px] text-subtle">Bütçe</div><div className="font-bold text-content">{t.implementation?.estimated_cost != null ? tl(t.implementation.estimated_cost) + " ₺" : "—"}</div></div>
                      <div><div className="text-[11px] text-subtle">Hedef</div><div className="font-bold text-emerald-700">{t.measurement?.primary_metric} → {t.measurement?.target ?? "—"}</div></div>
                    </div>
                    {isAdmin && (
                      <div className="flex flex-wrap gap-2 pt-2 border-t border-line">
                        {t.status === "awaiting_decision" && <>
                          <button onClick={() => karar(t.id, "approved")} disabled={!!yuk} className="inline-flex items-center gap-1 bg-emerald-600 text-white text-sm rounded-lg px-3 py-2"><CheckCircle className="h-4 w-4" />Onayla</button>
                          <button onClick={() => karar(t.id, "rejected")} disabled={!!yuk} className="inline-flex items-center gap-1 bg-red-600 text-white text-sm rounded-lg px-3 py-2"><XCircle className="h-4 w-4" />Reddet</button>
                        </>}
                        {t.status === "approved" && <button onClick={() => uygula(t.id)} disabled={!!yuk} className="inline-flex items-center gap-1 bg-indigo-600 text-white text-sm rounded-lg px-3 py-2"><PlayCircle className="h-4 w-4" />Deneyi Başlat (uygula)</button>}
                        {t.status === "implemented" && <>
                          <button onClick={() => olcumCalistir(t.id)} disabled={!!yuk} className="inline-flex items-center gap-1 bg-teal-600 text-white text-sm rounded-lg px-3 py-2"><Activity className="h-4 w-4" />Ölçümü Çalıştır</button>
                          <button onClick={() => ogrenmeKaydet(t.id)} disabled={!!yuk} className="inline-flex items-center gap-1 bg-slate-700 text-white text-sm rounded-lg px-3 py-2"><GraduationCap className="h-4 w-4" />Sonucu Kaydet (öğrenme)</button>
                        </>}
                      </div>
                    )}
                  </>
                )}

                {seviye === 2 && (
                  <>
                    <div>
                      <div className="text-[11px] font-bold uppercase text-subtle mb-1.5">Kanıtlar (gerçek metrik)</div>
                      <div className="space-y-1.5">
                        {(t.evidence || []).map((e, i) => (
                          <div key={i} className="text-xs bg-app border border-line rounded-lg px-2 py-1.5">{e.metric} · {e.segment}: <b>{e.current}</b> {e.previous != null && <span className="text-subtle">(önce {e.previous})</span>} · güven {e.confidence} · veri kalitesi %{e.data_quality_score}</div>
                        ))}
                        {(t.evidence || []).length === 0 && <div className="text-xs text-subtle">Kanıt yok.</div>}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] font-bold uppercase text-subtle mb-1.5">Hipotezler & test</div>
                      {(t.hypotheses || []).map((h, i) => (
                        <div key={i} className="text-xs bg-app border border-line rounded-lg px-2 py-1.5 mb-1"><b>{h.statement}</b> <span className="text-[10px] bg-emerald-100 text-emerald-700 rounded px-1">{h.support}</span><div className="text-subtle">Test: {h.test}</div></div>
                      ))}
                    </div>
                    <div>
                      <div className="text-[11px] font-bold uppercase text-subtle mb-1.5">Alternatifler</div>
                      {(t.alternatives || []).map((a, i) => (
                        <div key={i} className="text-xs flex items-center justify-between border border-line rounded-lg px-2 py-1.5 mb-1"><span>{a.name}</span><span className="text-subtle">maliyet {a.cost != null ? tl(a.cost) : "—"} · efor {a.effort} · etki {a.expected_effect} · risk {a.risk}</span></div>
                      ))}
                    </div>
                    <div className="bg-app border border-line rounded-xl p-3 text-xs grid grid-cols-2 sm:grid-cols-3 gap-2">
                      <div><span className="text-subtle block">Pilot</span>{t.implementation?.pilot_size ?? "—"}</div>
                      <div><span className="text-subtle block">Süre</span>{t.implementation?.duration_days ?? "—"} gün</div>
                      <div><span className="text-subtle block">Kontrol noktaları</span>{(t.measurement?.checkpoints || []).join(", ") || "—"}</div>
                      <div className="col-span-2 sm:col-span-3"><span className="text-subtle block">Durdurma koşulları</span>{(t.measurement?.stop_conditions || []).join("; ") || "—"}</div>
                    </div>
                    {t.status === "implemented" && (
                      <div>
                        <div className="text-[11px] font-bold uppercase text-subtle mb-1.5 flex items-center gap-1"><Activity className="h-3.5 w-3.5 text-indigo-500" />Otomatik Segment Ölçümleri (Pilot / Kontrol · gerçek metrik)</div>
                        {t.deney_gruplari && <div className="text-[11px] text-subtle mb-1.5">Kilitli deney kitlesi: 🚀 {t.deney_gruplari.pilot} pilot · ⚖️ {t.deney_gruplari.kontrol} kontrol</div>}
                        {(t.measurement?.olcumler || []).length === 0 ? (
                          <div className="text-xs text-subtle">Henüz ölçüm yok — kontrol noktası günü geldikçe segment farkları otomatik kilitlenir (ya da "Ölçümü Çalıştır").</div>
                        ) : (
                          <div className="space-y-2.5">
                            {(t.measurement.olcumler || []).map((o, i) => {
                              const bar = (yuzde, renk) => yuzde == null ? null : (
                                <div className="mt-1 flex items-center gap-2">
                                  <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden"><div className={`h-1.5 rounded-full ${renk}`} style={{ width: `${Math.max(0, Math.min(100, yuzde))}%` }} /></div>
                                  <span className="shrink-0 text-[10px] font-bold text-subtle">%{yuzde}</span>
                                </div>
                              );
                              return (
                                <div key={i} className="text-xs bg-app border border-line rounded-xl p-2.5 space-y-2">
                                  <div className="flex items-center justify-between font-semibold text-content border-b border-line pb-1">
                                    <span>🎯 Gün {o.gun} {o.baseline != null && <span className="text-subtle font-normal">(baz {o.baseline} → hedef {o.target ?? "—"})</span>}</span>
                                    <span className="text-[10px] text-subtle font-normal">{o.tarih ? new Date(o.tarih).toLocaleDateString("tr-TR") : ""}</span>
                                  </div>
                                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                                    <div className="p-2 rounded bg-emerald-50 border border-emerald-100">
                                      <div className="flex justify-between font-medium text-emerald-800"><span>🚀 Pilot</span><b>{o.pilot_deger ?? "—"}</b></div>
                                      {bar(o.pilot_ilerleme_yuzde, "bg-emerald-500")}
                                    </div>
                                    <div className="p-2 rounded bg-app border border-line">
                                      <div className="flex justify-between font-medium text-subtle"><span>⚖️ Kontrol</span><b>{o.kontrol_deger ?? "—"}</b></div>
                                      {bar(o.kontrol_ilerleme_yuzde, "bg-slate-400")}
                                    </div>
                                  </div>
                                  {o.net_etki != null ? (
                                    <div className="text-[11px] pt-0.5 flex justify-between font-medium"><span className="text-subtle">Net deney etkisi (pilot − kontrol):</span><b className={o.net_etki >= 0 ? "text-indigo-700" : "text-red-600"}>{o.net_etki > 0 ? "+" : ""}{o.net_etki} puan</b></div>
                                  ) : (
                                    <div className="text-[10px] text-subtle">Bu metrik için segment kaynağı yok — kurum-geneli değer gösterildi (net etki hesaplanamaz).</div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}

                {seviye === 3 && (
                  <div className="space-y-3">
                    {t.learning ? (
                      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-sm">
                        <div className="font-semibold text-emerald-800 mb-1">Öğrenme</div>
                        <div>Beklenen: <b>{t.learning.expected_result ?? "—"}</b> · Gerçek: <b>{t.learning.actual_result ?? "—"}</b> · Gerçek maliyet: {t.learning.execution_cost_actual != null ? tl(t.learning.execution_cost_actual) + " ₺" : "—"}</div>
                        {t.learning.lesson && <div className="mt-1 text-content">Ders: {t.learning.lesson}</div>}
                      </div>
                    ) : <div className="text-xs text-subtle">Deney tamamlanınca öğrenme (beklenen vs gerçek + ders) burada görünür.</div>}

                    {/* Faz 2.5: Otonom ajan araç günlüğü (gerçek DB alt sorguları) */}
                    <div>
                      <div className="text-[11px] font-bold uppercase text-subtle mb-1.5 flex items-center gap-1"><Activity className="h-3.5 w-3.5 text-indigo-500" />Otonom Ajan Araç Günlüğü (Tool Execution)</div>
                      {(t.arac_gunlugu || []).length === 0 ? (
                        <div className="text-xs text-subtle">Bu teklif ajan araçları tetiklenmeden (veya deterministik olarak) üretildi.</div>
                      ) : (
                        <div className="space-y-1.5">
                          {(t.arac_gunlugu || []).map((a, i) => (
                            <div key={i} className="text-[11px] bg-app border border-line rounded-lg p-2">
                              <div className="font-mono text-indigo-600 font-semibold">{a.tool}({Object.entries(a.arguments || {}).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join("/") : v}`).join(", ")})</div>
                              {a.tool === "compare_periods" && a.result && (
                                <div className="text-subtle mt-0.5">güncel {a.result.current_value ?? "—"} · önceki {a.result.previous_value ?? "—"} · Δ {a.result.delta ?? "—"} · {a.result.trend}</div>
                              )}
                              {a.tool === "find_segments" && (
                                <div className="text-subtle mt-0.5">{(a.result || []).length === 0 ? "ortalamadan anlamlı sapan segment yok" : (a.result || []).map((s, j) => <span key={j} className="inline-block mr-2">{s.segment}: {s.value} (%{s.sapma_yuzde}, n={s.sample_size})</span>)}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="bg-app border border-line rounded-xl p-3 font-mono text-[11px] text-subtle space-y-1">
                      <div>persona: Ayda · analiz: 6_katmanlı · ajan: {(t.arac_gunlugu || []).length} araç</div>
                      <div>tarih: {t.tarih}</div>
                      <div>kaynak: {t._kaynak || "—"} · veri_kalitesi: %{t.veri_kalitesi ?? "—"} · fotograf_id: {t.fotograf_id || "—"}</div>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
