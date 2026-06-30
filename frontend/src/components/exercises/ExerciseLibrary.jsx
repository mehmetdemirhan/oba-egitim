import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { getRenderComponent } from "./types";

/**
 * ExerciseLibrary — öğretmen/koordinatör/admin için kalıcı egzersiz içerik
 * kütüphanesi yönetimi.
 *
 * Tek paylaşımlı havuz: tüm öğretmen/öğrenciler aynı içerikleri görür. Öğretmen
 * bir içeriği beğenmezse "Varyant Üret" ile YENİ bir alternatif oluşturur; eski
 * içerik SİLİNMEZ (aktif kalır). Admin içeriği arşivleyebilir.
 *
 * Props:
 *   apiBase  — `${BACKEND_URL}/api`
 *   userRole — "admin" | "coordinator" | "teacher" (admin'e özel işlemler için)
 */
const LIMIT = 20;
const ROL_ETIKET = { admin: "Yönetici", coordinator: "Koordinatör", teacher: "Öğretmen", system: "Sistem" };

function tarihKisa(s) {
  if (!s) return "—";
  try { return new Date(s).toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "2-digit" }); }
  catch { return "—"; }
}

export default function ExerciseLibrary({ apiBase, userRole = "teacher" }) {
  const admin = userRole === "admin";

  const [tipler, setTipler] = useState([]);
  const [tipFiltre, setTipFiltre] = useState("");
  const [sinifFiltre, setSinifFiltre] = useState("");
  const [durumFiltre, setDurumFiltre] = useState("aktif");
  const [sayfa, setSayfa] = useState(1);

  const [veri, setVeri] = useState({ icerikler: [], toplam: 0, sayfa: 1, sayfa_sayisi: 1 });
  const [yukleniyor, setYukleniyor] = useState(false);
  const [hata, setHata] = useState(null);
  const [varyantYukleniyorId, setVaryantYukleniyorId] = useState(null);

  const [onizleId, setOnizleId] = useState(null); // detay modalı için içerik id

  // Tip dropdown (bir kez)
  useEffect(() => {
    axios.get(`${apiBase}/egzersiz/tipler`)
      .then((r) => setTipler(r.data?.tipler || []))
      .catch(() => setTipler([]));
  }, [apiBase]);

  const listele = useCallback(async (gidilecekSayfa = sayfa) => {
    setYukleniyor(true);
    setHata(null);
    try {
      const r = await axios.get(`${apiBase}/egzersiz/icerikler`, {
        params: {
          tip: tipFiltre || undefined,
          sinif: sinifFiltre || undefined,
          durum: durumFiltre,
          sayfa: gidilecekSayfa,
          limit: LIMIT,
        },
      });
      setVeri(r.data || { icerikler: [], toplam: 0, sayfa: 1, sayfa_sayisi: 1 });
    } catch (e) {
      setHata(e?.response?.status === 403
        ? "Bu alana erişim yetkiniz yok."
        : "Kütüphane yüklenemedi.");
      setVeri({ icerikler: [], toplam: 0, sayfa: 1, sayfa_sayisi: 1 });
    } finally {
      setYukleniyor(false);
    }
  }, [apiBase, tipFiltre, sinifFiltre, durumFiltre, sayfa]);

  // İlk yük + filtre/sayfa değişiminde
  useEffect(() => { listele(sayfa); /* eslint-disable-next-line */ }, [sayfa, durumFiltre]);
  // İlk açılış
  useEffect(() => { listele(1); /* eslint-disable-next-line */ }, []);

  const araClick = () => { setSayfa(1); listele(1); };

  const varyantUret = async (icerik_id) => {
    if (!window.confirm("Bu içeriğin yeni bir varyantını üretmek istiyor musunuz? Eski içerik korunacak.")) return;
    setVaryantYukleniyorId(icerik_id);
    try {
      await axios.post(`${apiBase}/egzersiz/icerik/${icerik_id}/varyant-uret`);
      setSayfa(1);
      await listele(1); // yeni varyant en üstte (olusturma_tarihi'ne göre)
    } catch (e) {
      setHata("Varyant üretilemedi. Lütfen tekrar deneyin.");
    } finally {
      setVaryantYukleniyorId(null);
    }
  };

  const arsivle = async (icerik_id) => {
    if (!window.confirm("Bu içeriği arşivlemek istiyor musunuz? Öğrencilere artık gösterilmez ama kayıt silinmez.")) return;
    try {
      await axios.patch(`${apiBase}/egzersiz/icerik/${icerik_id}/arsivle`);
      await listele(sayfa);
    } catch (e) {
      setHata("Arşivleme başarısız.");
    }
  };

  const sinifSecenek = useMemo(() => [1, 2, 3, 4, 5, 6, 7, 8], []);

  return (
    <div className="space-y-4">
      {/* Bilgi banner'ı */}
      <div className="rounded-2xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
        📚 Bu havuzdaki içerikler tüm öğretmen ve öğrencilerle paylaşılır. Bir içeriği beğenmediyseniz
        <span className="font-semibold"> "Varyant Üret"</span> ile yeni bir alternatif oluşturabilirsiniz; eski içerik silinmez.
      </div>

      {/* Filtre çubuğu */}
      <div className="flex flex-wrap items-end gap-2 bg-white rounded-2xl border border-gray-100 p-3 shadow-sm">
        <label className="text-xs text-gray-600 flex flex-col gap-1">
          Tip
          <select value={tipFiltre} onChange={(e) => setTipFiltre(e.target.value)}
            className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm bg-white min-w-[10rem]">
            <option value="">Tümü</option>
            {tipler.map((t) => <option key={t.id} value={t.id}>{t.ikon} {t.ad}</option>)}
          </select>
        </label>
        <label className="text-xs text-gray-600 flex flex-col gap-1">
          Sınıf
          <select value={sinifFiltre} onChange={(e) => setSinifFiltre(e.target.value)}
            className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm bg-white">
            <option value="">Tümü</option>
            {sinifSecenek.map((s) => <option key={s} value={s}>{s}. sınıf</option>)}
          </select>
        </label>
        <label className="text-xs text-gray-600 flex flex-col gap-1">
          Durum
          <select value={durumFiltre} onChange={(e) => setDurumFiltre(e.target.value)}
            className="px-2 py-1.5 rounded-lg border border-gray-200 text-sm bg-white">
            <option value="aktif">Aktif</option>
            <option value="arsivli">Arşivli</option>
            <option value="hepsi">Hepsi</option>
          </select>
        </label>
        <button onClick={araClick}
          className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition">
          🔍 Ara
        </button>
        <span className="text-xs text-gray-400 ml-auto self-center">{veri.toplam} içerik</span>
      </div>

      {hata && <div className="px-4 py-2 rounded-xl bg-red-50 border border-red-200 text-sm text-red-600">{hata}</div>}

      {/* Tablo */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
              <th className="px-3 py-2 font-semibold">Tip</th>
              <th className="px-3 py-2 font-semibold">Sınıf</th>
              <th className="px-3 py-2 font-semibold">İçerik Özeti</th>
              <th className="px-3 py-2 font-semibold">Üreten</th>
              <th className="px-3 py-2 font-semibold text-center">Kullanım</th>
              <th className="px-3 py-2 font-semibold">Son Kullanım</th>
              <th className="px-3 py-2 font-semibold text-right">İşlem</th>
            </tr>
          </thead>
          <tbody>
            {yukleniyor ? (
              <tr><td colSpan={7} className="px-3 py-10 text-center text-gray-400">Yükleniyor…</td></tr>
            ) : veri.icerikler.length === 0 ? (
              <tr><td colSpan={7} className="px-3 py-10 text-center text-gray-400">Bu filtreyle içerik bulunamadı.</td></tr>
            ) : veri.icerikler.map((i) => (
              <tr key={i.id} className={`border-b border-gray-50 hover:bg-gray-50/60 ${i.durum === "arsivli" ? "opacity-50" : ""}`}>
                <td className="px-3 py-2 whitespace-nowrap">{i.ikon} {i.tip_ad}</td>
                <td className="px-3 py-2">{i.sinif}</td>
                <td className="px-3 py-2 max-w-[20rem]"><span className="line-clamp-2 text-gray-700">{i.ozet || "—"}</span></td>
                <td className="px-3 py-2 whitespace-nowrap text-gray-600">
                  {i.olusturan_ad}
                  {i.olusturan_rol && <span className="text-[10px] text-gray-400 ml-1">({ROL_ETIKET[i.olusturan_rol] || i.olusturan_rol})</span>}
                </td>
                <td className="px-3 py-2 text-center">{i.kullanim_sayisi}</td>
                <td className="px-3 py-2 whitespace-nowrap text-gray-500">{tarihKisa(i.son_kullanim_tarihi)}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center justify-end gap-1">
                    <button onClick={() => setOnizleId(i.id)} title="Önizle"
                      className="px-2 py-1 rounded-lg text-xs border border-gray-200 hover:bg-gray-100">👁</button>
                    <button onClick={() => varyantUret(i.id)} disabled={varyantYukleniyorId === i.id} title="Varyant Üret"
                      className="px-2 py-1 rounded-lg text-xs border border-indigo-200 text-indigo-600 hover:bg-indigo-50 disabled:opacity-40">
                      {varyantYukleniyorId === i.id ? "⏳" : "🔄"}
                    </button>
                    {admin && i.durum !== "arsivli" && (
                      <button onClick={() => arsivle(i.id)} title="Arşivle"
                        className="px-2 py-1 rounded-lg text-xs border border-amber-200 text-amber-600 hover:bg-amber-50">🗑</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Sayfalama */}
      {veri.sayfa_sayisi > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button disabled={sayfa <= 1} onClick={() => setSayfa((s) => Math.max(1, s - 1))}
            className="px-3 py-1.5 rounded-lg border border-gray-200 disabled:opacity-40">← Önceki</button>
          <span className="text-gray-500">{sayfa} / {veri.sayfa_sayisi}</span>
          <button disabled={sayfa >= veri.sayfa_sayisi} onClick={() => setSayfa((s) => Math.min(veri.sayfa_sayisi, s + 1))}
            className="px-3 py-1.5 rounded-lg border border-gray-200 disabled:opacity-40">Sonraki →</button>
        </div>
      )}

      {/* Önizleme modalı */}
      {onizleId && (
        <OnizlemeModal
          apiBase={apiBase}
          icerikId={onizleId}
          admin={admin}
          onClose={() => setOnizleId(null)}
          onKardesSec={(id) => setOnizleId(id)}
          onVaryant={async (id) => { await varyantUret(id); setOnizleId(null); }}
          onArsivle={async (id) => { await arsivle(id); setOnizleId(null); }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Önizleme modalı — içeriğin tam hali + kardeş varyantlar + "dene"
// ─────────────────────────────────────────────────────────────
function OnizlemeModal({ apiBase, icerikId, admin, onClose, onKardesSec, onVaryant, onArsivle }) {
  const [detay, setDetay] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [deneAcik, setDeneAcik] = useState(false);

  useEffect(() => {
    let iptal = false;
    setYukleniyor(true);
    setDeneAcik(false);
    axios.get(`${apiBase}/egzersiz/icerik/${icerikId}`)
      .then((r) => { if (!iptal) setDetay(r.data); })
      .catch(() => { if (!iptal) setDetay(null); })
      .finally(() => { if (!iptal) setYukleniyor(false); });
    return () => { iptal = true; };
  }, [apiBase, icerikId]);

  return (
    <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[88vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        {/* Başlık */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 sticky top-0 bg-white rounded-t-2xl">
          <div className="font-bold text-gray-800">
            {detay ? `${detay.ikon || "📝"} ${detay.tip_ad}` : "İçerik"} {detay && <span className="text-xs font-normal text-gray-400">• {detay.sinif}. sınıf</span>}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-lg">✕</button>
        </div>

        <div className="p-5 space-y-4">
          {yukleniyor ? (
            <div className="text-center py-10 text-gray-400">Yükleniyor…</div>
          ) : !detay ? (
            <div className="text-center py-10 text-gray-400">İçerik yüklenemedi.</div>
          ) : deneAcik ? (
            <IcerikDene apiBase={apiBase} detay={detay} onBitir={() => setDeneAcik(false)} />
          ) : (
            <>
              {/* Üst bilgi */}
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="px-2 py-1 rounded-full bg-gray-100 text-gray-600">Üreten: {detay.olusturan_ad || "—"}</span>
                <span className="px-2 py-1 rounded-full bg-gray-100 text-gray-600">Kullanım: {detay.kullanim_sayisi || 0}</span>
                <span className="px-2 py-1 rounded-full bg-gray-100 text-gray-600">Kaynak: {detay.kaynak || "—"}</span>
                <span className={`px-2 py-1 rounded-full ${detay.durum === "arsivli" ? "bg-amber-100 text-amber-700" : "bg-green-100 text-green-700"}`}>{detay.durum || "aktif"}</span>
                {detay.mock && <span className="px-2 py-1 rounded-full bg-gray-100 text-gray-400">çevrimdışı/mock</span>}
              </div>

              {/* İçeriğin tam hali (statik önizleme) */}
              <IcerikOnizle icerik={detay.icerik} puanlama={detay.puanlama} />

              {/* Kardeş varyantlar */}
              {detay.varyant_sayisi > 1 && (
                <div className="border-t border-gray-100 pt-3">
                  <div className="text-xs font-semibold text-gray-500 mb-2">
                    Bu içeriğin {detay.varyant_sayisi - 1} varyantı daha var:
                  </div>
                  <div className="space-y-1">
                    {detay.kardesler.filter((k) => !k.kendisi).map((k) => (
                      <button key={k.id} onClick={() => onKardesSec(k.id)}
                        className="w-full text-left px-3 py-2 rounded-lg border border-gray-100 hover:border-indigo-200 hover:bg-indigo-50/50 text-xs">
                        <span className="text-gray-700">{k.ozet || "(özet yok)"}</span>
                        <span className="text-gray-400 ml-2">• {k.durum} • {k.kullanim_sayisi} kullanım</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Eylemler */}
              <div className="flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3">
                <button onClick={() => setDeneAcik(true)}
                  className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700">
                  ▶ Bu içeriği dene
                </button>
                <button onClick={() => onVaryant(detay.id)}
                  className="px-4 py-2 rounded-xl border border-indigo-200 text-indigo-600 text-sm font-medium hover:bg-indigo-50">
                  🔄 Varyant Üret
                </button>
                {admin && detay.durum !== "arsivli" && (
                  <button onClick={() => onArsivle(detay.id)}
                    className="px-4 py-2 rounded-xl border border-amber-200 text-amber-600 text-sm font-medium hover:bg-amber-50">
                    🗑 Arşivle
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Statik içerik önizleme — şekle göre okunabilir döküm
// ─────────────────────────────────────────────────────────────
function IcerikOnizle({ icerik, puanlama }) {
  if (!icerik || typeof icerik !== "object") return <div className="text-sm text-gray-400">İçerik yok.</div>;

  const Kutu = ({ children }) => <div className="bg-gray-50 rounded-xl border border-gray-100 p-3 space-y-2">{children}</div>;

  return (
    <Kutu>
      {icerik.metin && (
        <div className="text-[15px] leading-relaxed text-gray-800 whitespace-pre-line bg-white rounded-lg p-3 border border-gray-100">{icerik.metin}</div>
      )}
      {(icerik.merkez || icerik.kelime) && (
        <div className="text-sm"><span className="text-gray-400">Kelime/Merkez: </span><span className="font-semibold">{icerik.merkez || icerik.kelime}</span>
          {icerik.ipucu && <span className="text-gray-400"> — ipucu: {icerik.ipucu}</span>}</div>
      )}
      {(icerik.a || icerik.b) && (
        <div className="text-sm text-gray-700">Karşılaştırma: <b>{icerik.a}</b> ↔ <b>{icerik.b}</b></div>
      )}
      {icerik.hedef && <div className="text-sm text-gray-700">🎯 {icerik.hedef}</div>}
      {Array.isArray(icerik.dogrular) && (
        <div className="text-xs text-gray-600">✅ {icerik.dogrular.join(", ")}{Array.isArray(icerik.yanlislar) && <> &nbsp; ❌ {icerik.yanlislar.join(", ")}</>}</div>
      )}

      {/* Çoktan seçmeli sorular (doğru şık yeşil) */}
      {Array.isArray(icerik.sorular) && icerik.sorular.map((s, i) => (
        <div key={i} className="bg-white rounded-lg p-3 border border-gray-100">
          <div className="text-sm font-semibold text-gray-800 mb-1">{i + 1}. {s.soru}</div>
          <div className="grid gap-1">
            {(s.secenekler || []).map((sec, k) => (
              <div key={k} className={`text-xs px-2 py-1 rounded ${k === s.dogru ? "bg-green-50 text-green-700 font-medium" : "text-gray-600"}`}>
                {String.fromCharCode(65 + k)}) {sec} {k === s.dogru && "✓"}
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Eşleştirme çiftleri */}
      {Array.isArray(icerik.ciftler) && (
        <div className="grid gap-1">
          {icerik.ciftler.map((c, i) => (
            <div key={i} className="text-sm text-gray-700"><b>{c.sol}</b> → {c.sag}</div>
          ))}
        </div>
      )}

      {/* Bulmaca ipucu→cevap */}
      {Array.isArray(icerik.kelimeler) && (
        <div className="grid gap-1">
          {icerik.kelimeler.map((k, i) => (
            <div key={i} className="text-sm text-gray-700">{k.ipucu} → <b>{k.cevap}</b></div>
          ))}
        </div>
      )}

      {/* Sıralama (doğru sıra) */}
      {Array.isArray(icerik.dogru_sira) && (
        <div className="text-sm text-gray-700">
          <span className="text-gray-400">Doğru sıra: </span>
          {icerik.dogru_sira.map((idx, p) => {
            const ogeler = icerik.parcalar || icerik.olaylar || [];
            return <span key={p}>{p > 0 ? " → " : ""}{ogeler[idx]}</span>;
          })}
        </div>
      )}

      <div className="text-[10px] text-gray-300 pt-1">Puanlama: {puanlama || "secmeli"}</div>
    </Kutu>
  );
}

// ─────────────────────────────────────────────────────────────
// İçeriği gerçek motorla dene (öğretmen önizlemesi, tek seferlik oturum)
// ─────────────────────────────────────────────────────────────
function IcerikDene({ apiBase, detay, onBitir }) {
  const [oturum, setOturum] = useState(null);
  const [soruNo, setSoruNo] = useState(0);
  const [cevaplandi, setCevaplandi] = useState(false);
  const [bitti, setBitti] = useState(false);
  const [hata, setHata] = useState(null);

  useEffect(() => {
    let iptal = false;
    axios.post(`${apiBase}/egzersiz/oturum`, { tip: detay.tip, sinif: detay.sinif, icerik_id: detay.id })
      .then((r) => { if (!iptal) setOturum(r.data); })
      .catch(() => { if (!iptal) setHata("Deneme başlatılamadı."); });
    return () => { iptal = true; };
  }, [apiBase, detay]);

  const onCevap = async (cevap) => {
    if (!oturum) return { dogru: false, dogru_cevap: null };
    try {
      const r = await axios.post(`${apiBase}/egzersiz/oturum/${oturum.oturum_id}/cevap`, { soru_no: soruNo, cevap });
      setCevaplandi(true);
      return r.data;
    } catch {
      setCevaplandi(true);
      return { dogru: false, dogru_cevap: null };
    }
  };

  const sonraki = () => {
    const toplam = oturum?.toplam_soru || 1;
    if (soruNo + 1 < toplam) { setSoruNo((n) => n + 1); setCevaplandi(false); }
    else { setBitti(true); }
  };

  if (hata) return <div className="text-center py-8 text-red-500 text-sm">{hata}</div>;
  if (!oturum) return <div className="text-center py-8 text-gray-400 text-sm">Hazırlanıyor…</div>;

  if (bitti) {
    return (
      <div className="text-center py-8 space-y-3">
        <div className="text-3xl">✅</div>
        <div className="text-sm text-gray-600">Önizleme tamamlandı.</div>
        <button onClick={onBitir} className="px-4 py-2 rounded-xl border border-gray-200 text-sm">← Önizlemeye dön</button>
      </div>
    );
  }

  const Render = getRenderComponent(oturum.tip);
  const toplam = oturum.toplam_soru || 1;
  const sonSoru = soruNo + 1 >= toplam;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-gray-400">
        <button onClick={onBitir} className="hover:text-gray-700">← Önizleme</button>
        <span>{Math.min(soruNo + 1, toplam)}/{toplam}</span>
      </div>
      {Render ? (
        <Render icerik={oturum.icerik} onCevap={onCevap} soruNo={soruNo} ilerleme={{ mevcut: soruNo + 1, toplam }} />
      ) : (
        <div className="text-center py-8 text-gray-400 text-sm">Bu türün görünümü yok.</div>
      )}
      {(cevaplandi || !Render) && (
        <div className="flex justify-end">
          <button onClick={sonraki} className="px-5 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700">
            {sonSoru ? "Bitir ✓" : "Sonraki →"}
          </button>
        </div>
      )}
    </div>
  );
}
