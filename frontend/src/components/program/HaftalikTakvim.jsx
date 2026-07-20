import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import YeniDersModal from "./YeniDersModal";
import DersDetayModal from "./DersDetayModal";

/**
 * HaftalikTakvim — Google Calendar tarzı haftalık ders programı + SÜRÜKLE-BIRAK.
 *
 * 7 sütun (Pzt–Paz), 08:00–21:00 saat dilimleri. Dersler renk kodludur.
 * İKİ atama yöntemi (biri diğerinin YERİNE değil, YANINDA):
 *   1) Tıkla: boş slot → "Yeni Ders" modalı; dolu ders → "Ders Detayı" modalı.
 *   2) Sürükle-bırak: kenar çubuğundaki öğrenci chip'ini bir saat hücresine bırak
 *      → o güne/saate haftalık seri açılır (ders 40 dk sabit, bitiş otomatik).
 *      Yerleşik dersi başka hücreye sürükle → o oturumu taşı. Kenar çubuğuna geri
 *      sürükle → programdan çıkar. Çakışma (409) net uyarı ile engellenir.
 *
 * Props:
 *   apiBase, user, ogrenciler [{id,ad,soyad,ogretmen_id}], ogretmenler [{id,ad,soyad}]
 */
const GUNLER = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
const SAATLER = Array.from({ length: 14 }, (_, i) => i + 8); // 08..21
const DERS_DK = 40; // ders süresi sabit 40 dakika
const RENK = {
  planli: "bg-blue-100 text-blue-700 border-blue-300",
  katildi: "bg-green-100 text-green-700 border-green-300",
  katilmadi: "bg-red-100 text-red-700 border-red-300",
  iptal: "bg-gray-100 text-gray-400 border-gray-200 line-through",
};

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const pazartesi = (d) => { const x = new Date(d); x.setHours(0, 0, 0, 0); const g = (x.getDay() + 6) % 7; x.setDate(x.getDate() - g); return x; };
const ekleGun = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const gunNo = (isoTarih) => { const [y, m, d] = (isoTarih || "").split("-").map(Number); return y ? (new Date(y, m - 1, d).getDay() + 6) % 7 : 0; };
// "HH:00" başlangıcına 40 dk ekleyerek bitişi hesapla (11:00 → 11:40).
const saatArti = (hhmm, dk) => { const [h, m] = hhmm.split(":").map(Number); const t = h * 60 + m + dk; return `${String(Math.floor(t / 60) % 24).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`; };

export default function HaftalikTakvim({ apiBase, user, ogrenciler = [], ogretmenler = [] }) {
  const yonetici = user?.role === "admin" || user?.role === "coordinator";
  const [haftaRef, setHaftaRef] = useState(() => pazartesi(new Date()));
  const [dersler, setDersler] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [seciliOgretmen, setSeciliOgretmen] = useState("");
  const [yeniModal, setYeniModal] = useState(null); // {tarih, saat}
  const [detay, setDetay] = useState(null);        // ders objesi
  const [uyari, setUyari] = useState(null);        // {tip:'hata'|'ok', mesaj}
  const [suruklenen, setSuruklenen] = useState(null); // görsel geri bildirim

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

  const bildir = (tip, mesaj) => { setUyari({ tip, mesaj }); setTimeout(() => setUyari(null), 4000); };

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

  // Kenar çubuğu öğrenci listesi: öğretmen kendi öğrencileri; yönetici seçili
  // öğretmenin öğrencileri (öğretmen seçilmemişse liste boş → uyarı).
  const chipOgrenciler = useMemo(() => {
    const aktif = ogrenciler.filter((o) => !o.arsivli);
    if (!yonetici) return aktif;
    return seciliOgretmen ? aktif.filter((o) => o.ogretmen_id === seciliOgretmen) : [];
  }, [ogrenciler, yonetici, seciliOgretmen]);

  const haftaEtiketi = `${new Date(gunTarihleri[0]).toLocaleDateString("tr-TR", { day: "numeric", month: "short" })} – ${new Date(gunTarihleri[6]).toLocaleDateString("tr-TR", { day: "numeric", month: "short", year: "numeric" })}`;
  const ad = (o) => `${o.ad || ""} ${o.soyad || ""}`.trim();

  // ── Sürükle-bırak yükleri ──
  const dtAl = (e) => { try { return JSON.parse(e.dataTransfer.getData("text/plain") || "{}"); } catch { return {}; } };
  const dtVer = (e, veri) => { e.dataTransfer.setData("text/plain", JSON.stringify(veri)); e.dataTransfer.effectAllowed = "move"; };

  const hataYaz = (e2, varsayilan) => {
    const st = e2?.response?.status;
    bildir("hata", st === 409 ? (e2.response.data?.detail || "Çakışma: bu saatte başka ders var.")
      : st === 400 ? (e2.response.data?.detail || "Geçersiz bilgi.") : varsayilan);
  };

  // Öğrenci chip'i boş hücreye → haftalık seri (40 dk)
  const ogrenciBirak = async (tarih, saat) => {
    const o = suruklenen?.ogrenci;
    if (!o) return;
    const bas = `${String(saat).padStart(2, "0")}:00`;
    try {
      await axios.post(`${apiBase}/ders/seri`, {
        ogrenci_id: o.id, gun: gunNo(tarih), baslangic_saati: bas, bitis_saati: saatArti(bas, DERS_DK),
        baslangic_tarihi: tarih, bitis_tarihi: null, not: "",
        ...(yonetici ? { ogretmen_id: seciliOgretmen } : {}),
      });
      bildir("ok", `${ad(o)} → ${GUNLER[gunNo(tarih)]} ${bas} eklendi (40 dk).`);
      yukle();
    } catch (e2) { hataYaz(e2, "Ders eklenemedi."); }
  };

  // Yerleşik dersi başka hücreye → o oturumu taşı (40 dk, sebep otomatik)
  const dersBirak = async (tarih, saat) => {
    const d = suruklenen?.ders;
    if (!d) return;
    const sa = parseInt((d.baslangic_saati || "0").split(":")[0], 10);
    if (d.tarih === tarih && sa === saat) return; // aynı yer
    const bas = `${String(saat).padStart(2, "0")}:00`;
    try {
      await axios.put(`${apiBase}/ders/oturum/${d.id}/tasi`, {
        tarih, baslangic_saati: bas, bitis_saati: saatArti(bas, DERS_DK),
        sebep: "Sürükle-bırak ile taşındı",
      });
      bildir("ok", `${d.ogrenci_ad} dersi taşındı.`);
      yukle();
    } catch (e2) { hataYaz(e2, "Ders taşınamadı."); }
  };

  // Kenar çubuğuna geri sürükleyerek programdan çıkar
  const dersSil = async (d) => {
    const seriId = d.seri_id || (String(d.id).startsWith("seri:") ? String(d.id).split(":")[1] : null);
    try {
      if (seriId) {
        if (!window.confirm(`${d.ogrenci_ad} için haftalık ders (seri) sonlandırılsın mı?`)) return;
        await axios.delete(`${apiBase}/ders/seri/${seriId}`, { params: { sebep: "Sürükle-bırak ile programdan çıkarıldı" } });
      } else {
        if (!window.confirm(`${d.ogrenci_ad} dersi programdan çıkarılsın mı?`)) return;
        await axios.delete(`${apiBase}/ders/oturum/${d.id}`, { params: { sebep: "Sürükle-bırak ile programdan çıkarıldı" } });
      }
      bildir("ok", `${d.ogrenci_ad} programdan çıkarıldı.`);
      yukle();
    } catch (e2) { hataYaz(e2, "Çıkarılamadı."); }
  };

  const hucreyeBirak = (tarih, saat, dolu) => (e) => {
    e.preventDefault();
    if (suruklenen?.tur === "ogrenci" && !dolu) ogrenciBirak(tarih, saat);
    else if (suruklenen?.tur === "ders") dersBirak(tarih, saat);
    setSuruklenen(null);
  };

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
            {ogretmenler.map((o) => <option key={o.id} value={o.id}>{ad(o)}</option>)}
          </select>
        )}
        {yukleniyor && <span className="text-xs text-gray-400">yükleniyor…</span>}
      </div>

      {uyari && (
        <div className={`px-3 py-2 rounded-lg text-sm border ${uyari.tip === "hata" ? "bg-red-50 border-red-200 text-red-700" : "bg-green-50 border-green-200 text-green-700"}`}>
          {uyari.tip === "hata" ? "⚠ " : "✓ "}{uyari.mesaj}
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-3">
        {/* Kenar çubuğu: sürüklenebilir öğrenci chip'leri + bırakınca sil bölgesi */}
        <div className="lg:w-52 shrink-0">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-3"
            onDragOver={(e) => { if (suruklenen?.tur === "ders") e.preventDefault(); }}
            onDrop={(e) => { e.preventDefault(); if (suruklenen?.tur === "ders" && suruklenen.ders) dersSil(suruklenen.ders); setSuruklenen(null); }}>
            <div className="text-xs font-semibold text-gray-600 mb-2">Öğrenciler <span className="text-gray-400 font-normal">· sürükleyip bırak</span></div>
            {yonetici && !seciliOgretmen ? (
              <div className="text-xs text-gray-400 py-3">Öğrenci atamak için önce üstten bir öğretmen seçin.</div>
            ) : chipOgrenciler.length === 0 ? (
              <div className="text-xs text-gray-400 py-3">Öğrenci yok.</div>
            ) : (
              <div className="flex flex-wrap lg:flex-col gap-1.5 max-h-[60vh] overflow-y-auto">
                {chipOgrenciler.map((o) => (
                  <div key={o.id} draggable
                    onDragStart={(e) => { setSuruklenen({ tur: "ogrenci", ogrenci: o }); dtVer(e, { tur: "ogrenci", id: o.id }); }}
                    onDragEnd={() => setSuruklenen(null)}
                    className="cursor-grab active:cursor-grabbing select-none px-2.5 py-1.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-medium hover:bg-indigo-100 truncate"
                    title={`${ad(o)} — sürükleyip takvime bırak`}>
                    ⠿ {ad(o)}
                  </div>
                ))}
              </div>
            )}
            <div className="mt-2 pt-2 border-t border-gray-100 text-[10px] text-gray-400 leading-snug">
              Dersi buraya geri sürükleyerek programdan çıkarabilirsin.
            </div>
          </div>
        </div>

        {/* Takvim ızgarası */}
        <div className="flex-1 overflow-x-auto bg-white rounded-2xl border border-gray-100 shadow-sm">
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
                  const dolu = liste.length > 0;
                  const surukleAktif = suruklenen && (suruklenen.tur === "ders" || (suruklenen.tur === "ogrenci" && !dolu));
                  return (
                    <div key={ci}
                      onClick={() => !dolu && setYeniModal({ tarih: t, saat: `${String(saat).padStart(2, "0")}:00` })}
                      onDragOver={(e) => { if (surukleAktif) e.preventDefault(); }}
                      onDrop={hucreyeBirak(t, saat, dolu)}
                      className={`relative border-b border-l border-gray-50 min-h-[44px] p-0.5 transition-colors ${!dolu ? "cursor-pointer hover:bg-gray-50/60" : ""} ${surukleAktif ? "outline-dashed outline-1 outline-indigo-300 bg-indigo-50/40" : ""}`}>
                      {liste.map((d) => (
                        <button key={d.id} draggable
                          onDragStart={(e) => { e.stopPropagation(); setSuruklenen({ tur: "ders", ders: d }); dtVer(e, { tur: "ders", id: d.id }); }}
                          onDragEnd={() => setSuruklenen(null)}
                          onClick={(e) => { e.stopPropagation(); setDetay(d); }}
                          className={`block w-full text-left mb-0.5 px-1.5 py-1 rounded-md border text-[11px] leading-tight cursor-grab active:cursor-grabbing ${RENK[d.durum] || RENK.planli}`}>
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
      </div>

      {/* Renk lejantı */}
      <div className="flex flex-wrap gap-3 text-xs text-gray-500">
        {[["planli", "Planlı"], ["katildi", "Katıldı"], ["katilmadi", "Katılmadı"], ["iptal", "İptal"]].map(([k, l]) => (
          <span key={k} className="flex items-center gap-1"><span className={`w-3 h-3 rounded border ${RENK[k]}`} />{l}</span>
        ))}
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
