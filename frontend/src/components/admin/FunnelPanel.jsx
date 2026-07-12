import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { Send, Users, FileText, Clock, Check, X, AlertTriangle, Plus, Trash2 } from "lucide-react";

/**
 * FunnelPanel — Veli Mesajları / Funnel (admin + muhasebe).
 * Onaylı kuyruk: hiçbir mesaj insan onayı olmadan gitmez. KVKK: onaysız veliye
 * pazarlama gönderilmez. Kanal kurulmadıysa "kurulmadı" görünür.
 *
 * Bölümler: Segmentler (kampanya başlat) · Şablonlar · Gönderimler (geçmiş).
 * Kampanya akışı: segment + şablon → TASLAK önizleme (alıcı/onay/maliyet) →
 * "Onayla ve Gönder".
 */
const TUR_RENK = { pazarlama: "bg-purple-100 text-purple-700", hizmet: "bg-blue-100 text-blue-700" };
const ONAY_RENK = { var: "bg-green-100 text-green-700", yok: "bg-gray-100 text-gray-600", ret: "bg-red-100 text-red-700" };
const ONAY_ET = { var: "Onaylı", yok: "Onaysız", ret: "Ret" };
const DURUM_RENK = { kuyrukta: "text-green-600", onaysiz: "text-gray-400", gonderildi: "text-green-600", hata: "text-red-600" };

export default function FunnelPanel({ apiBase }) {
  const { toast } = useToast();
  const [bolum, setBolum] = useState("segmentler");
  const [kanallar, setKanallar] = useState([]);
  const [segmentler, setSegmentler] = useState([]);
  const [ayar, setAyar] = useState({});
  const [sablonlar, setSablonlar] = useState([]);
  const [degiskenler, setDegiskenler] = useState([]);
  const [gonderimler, setGonderimler] = useState([]);
  const [taslak, setTaslak] = useState(null);      // aktif önizlenen gönderim
  const [cikarilan, setCikarilan] = useState([]);  // taslakta çıkarılan ogrenci_id'ler
  const [seciliSablon, setSeciliSablon] = useState({}); // {segment: sablon_id}
  const [sablonForm, setSablonForm] = useState({ ad: "", kanal: "sms", tur: "pazarlama", metin: "" });
  const [yukleniyor, setYukleniyor] = useState(false);

  const yukle = useCallback(async () => {
    try { const r = await axios.get(`${apiBase}/funnel/kanallar`); setKanallar(r.data?.kanallar || []); } catch (e) {}
    try { const r = await axios.get(`${apiBase}/funnel/segmentler`); setSegmentler(r.data?.segmentler || []); setAyar(r.data?.ayar || {}); } catch (e) {}
    try { const r = await axios.get(`${apiBase}/funnel/sablonlar`); setSablonlar(r.data?.sablonlar || []); setDegiskenler(r.data?.degiskenler || []); } catch (e) {}
    try { const r = await axios.get(`${apiBase}/funnel/gonderim`); setGonderimler(r.data?.gonderimler || []); } catch (e) {}
  }, [apiBase]);
  useEffect(() => { yukle(); }, [yukle]);

  const kanalKurulu = (ad) => kanallar.find((k) => k.ad === ad)?.kurulu;

  // ── Kampanya taslağı oluştur ──
  const taslakOlustur = async (segment, cikar = []) => {
    const sablon_id = seciliSablon[segment];
    if (!sablon_id) { toast({ title: "Önce şablon seçin", variant: "destructive" }); return; }
    setYukleniyor(true);
    try {
      const r = await axios.post(`${apiBase}/funnel/gonderim`, { segment, sablon_id, cikar_ogrenci_ids: cikar });
      setTaslak(r.data); setCikarilan(cikar); setBolum("taslak");
    } catch (e) { toast({ title: "Taslak oluşturulamadı", description: e?.response?.data?.detail || "", variant: "destructive" }); }
    finally { setYukleniyor(false); }
  };

  const aliciCikar = (ogrenci_id) => taslakOlustur(taslak.segment, [...cikarilan, ogrenci_id]);

  const onaySet = async (telefon, durum) => {
    try {
      await axios.put(`${apiBase}/funnel/onay`, { telefon, durum });
      if (taslak) await taslakOlustur(taslak.segment, cikarilan); // onay değişince taslağı tazele
    } catch (e) { toast({ title: "Onay kaydedilemedi", variant: "destructive" }); }
  };

  const onaylaGonder = async () => {
    if (!window.confirm(`${taslak.ozet?.kuyrukta || 0} kişiye ${taslak.kanal.toUpperCase()} gönderilecek. Onaylıyor musunuz?`)) return;
    setYukleniyor(true);
    try {
      const r = await axios.post(`${apiBase}/funnel/gonderim/${taslak.id}/onayla`);
      toast({ title: "Gönderim tamamlandı", description: `Gönderilen: ${r.data?.ozet?.gonderildi || 0}, Hata: ${r.data?.ozet?.hata || 0}` });
      setTaslak(null); setBolum("gonderimler"); yukle();
    } catch (e) { toast({ title: "Gönderilemedi", description: e?.response?.data?.detail || "", variant: "destructive" }); }
    finally { setYukleniyor(false); }
  };

  const sablonKaydet = async () => {
    if (!sablonForm.ad.trim() || !sablonForm.metin.trim()) { toast({ title: "Ad ve metin gerekli", variant: "destructive" }); return; }
    try {
      await axios.post(`${apiBase}/funnel/sablonlar`, sablonForm);
      setSablonForm({ ad: "", kanal: "sms", tur: "pazarlama", metin: "" }); yukle();
      toast({ title: "Şablon eklendi" });
    } catch (e) { toast({ title: "Eklenemedi", description: e?.response?.data?.detail || "", variant: "destructive" }); }
  };
  const sablonSil = async (id) => { try { await axios.delete(`${apiBase}/funnel/sablonlar/${id}`); yukle(); } catch (e) {} };

  const Sekme = ({ id, ikon: Ikon, children }) => (
    <button onClick={() => { setBolum(id); if (id !== "taslak") setTaslak(null); }}
      className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all ${bolum === id ? "bg-primary text-white border-primary" : "bg-surface text-subtle border-line hover:bg-app"}`}>
      <Ikon className="h-4 w-4" />{children}
    </button>
  );

  return (
    <div className="space-y-4">
      {/* Kanal durumu */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {kanallar.map((k) => (
          <span key={k.ad} className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full border ${k.kurulu ? "bg-green-50 border-green-200 text-green-700" : "bg-gray-50 border-line text-subtle"}`}>
            {k.kurulu ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
            {k.ad.toUpperCase()} · {k.kurulu ? "kurulu" : "kurulmadı"} · {k.birim_ucret}₺
          </span>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <Sekme id="segmentler" ikon={Users}>Segmentler</Sekme>
        <Sekme id="sablonlar" ikon={FileText}>Şablonlar ({sablonlar.length})</Sekme>
        <Sekme id="gonderimler" ikon={Clock}>Gönderimler</Sekme>
      </div>

      {/* SEGMENTLER — kampanya başlat */}
      {bolum === "segmentler" && (
        <div className="grid gap-3 sm:grid-cols-2">
          {segmentler.map((s) => (
            <div key={s.ad} className="bg-surface border border-line rounded-xl p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-content">{s.baslik}</span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${TUR_RENK[s.tur]}`}>{s.tur}</span>
              </div>
              <p className="text-xs text-subtle">{s.aciklama}</p>
              <div className="text-sm">Alıcı: <b className="tabular-nums">{s.alici_sayisi ?? "—"}</b>{s.ad === "elle" && <span className="text-xs text-subtle"> (tablodan işaretle)</span>}</div>
              {s.ad !== "elle" && (
                <div className="flex gap-2">
                  <select value={seciliSablon[s.ad] || ""} onChange={(e) => setSeciliSablon((p) => ({ ...p, [s.ad]: e.target.value }))}
                    className="flex-1 text-sm border border-line rounded-lg px-2 py-1.5 bg-app">
                    <option value="">Şablon seç…</option>
                    {sablonlar.filter((t) => t.durum !== "pasif").map((t) => <option key={t.id} value={t.id}>{t.ad} ({t.tur}/{t.kanal})</option>)}
                  </select>
                  <button onClick={() => taslakOlustur(s.ad)} disabled={yukleniyor || !s.alici_sayisi}
                    className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-medium disabled:opacity-40">Hazırla</button>
                </div>
              )}
            </div>
          ))}
          {(ayar.yenileme_gun || ayar.odeme_gun) && (
            <p className="text-[11px] text-subtle sm:col-span-2">Ayar: yenileme {ayar.yenileme_gun}g · ödeme {ayar.odeme_gun}g (Ayarlar'dan değişebilir).</p>
          )}
        </div>
      )}

      {/* TASLAK — onay kuyruğu önizleme */}
      {bolum === "taslak" && taslak && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3 bg-app border border-line rounded-xl p-3">
            <div className="text-sm"><b>{taslak.ozet?.toplam}</b> alıcı · <b className="text-green-600">{taslak.ozet?.kuyrukta}</b> gönderilecek · <span className="text-subtle">{taslak.ozet?.onaysiz} onaysız</span></div>
            <div className="text-sm">Tahmini maliyet: <b className="tabular-nums">{taslak.tahmini_maliyet}₺</b> ({taslak.kanal.toUpperCase()})</div>
            <div className="ml-auto flex gap-2">
              <button onClick={() => { setTaslak(null); setBolum("segmentler"); }} className="px-3 py-1.5 rounded-lg border border-line text-sm">Vazgeç</button>
              <button onClick={onaylaGonder} disabled={yukleniyor || !taslak.ozet?.kuyrukta || !kanalKurulu(taslak.kanal)}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-green-600 text-white text-sm font-medium disabled:opacity-40">
                <Send className="h-4 w-4" />Onayla ve Gönder
              </button>
            </div>
          </div>
          {!kanalKurulu(taslak.kanal) && (
            <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              <AlertTriangle className="h-4 w-4" />{taslak.kanal.toUpperCase()} kanalı kurulmadı — gönderim yapılamaz (env kimlik bilgisi gerekli).
            </div>
          )}
          <div className="border border-line rounded-xl overflow-x-auto bg-surface">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs text-subtle border-b border-line bg-app">
                <th className="px-3 py-2">Veli / Öğrenci</th><th className="px-3 py-2">Telefon</th><th className="px-3 py-2">Onay</th>
                <th className="px-3 py-2">Durum</th><th className="px-3 py-2">Mesaj</th><th className="px-3 py-2"></th>
              </tr></thead>
              <tbody>
                {(taslak.alicilar || []).map((a, i) => (
                  <tr key={i} className="border-b border-gray-50">
                    <td className="px-3 py-2"><div className="font-medium text-content">{a.veli_adi || "—"}</div><div className="text-[11px] text-subtle">{a.ogrenci_adi}</div></td>
                    <td className="px-3 py-2 tabular-nums text-subtle">{a.telefon || "—"}</td>
                    <td className="px-3 py-2">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${ONAY_RENK[a.onay_durum] || ONAY_RENK.yok}`}>{ONAY_ET[a.onay_durum] || a.onay_durum}</span>
                      {a.onay_durum !== "var" && <button onClick={() => onaySet(a.telefon, "var")} title="Onay al" className="ml-1 text-[10px] text-primary hover:underline">onay+</button>}
                    </td>
                    <td className={`px-3 py-2 text-xs font-medium ${DURUM_RENK[a.durum] || ""}`}>{a.durum}</td>
                    <td className="px-3 py-2 text-xs text-subtle max-w-xs truncate" title={a.mesaj}>{a.mesaj}</td>
                    <td className="px-3 py-2"><button onClick={() => aliciCikar(a.ogrenci_id)} title="Listeden çıkar" className="text-subtle hover:text-red-600"><X className="h-3.5 w-3.5" /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ŞABLONLAR */}
      {bolum === "sablonlar" && (
        <div className="space-y-3">
          <div className="bg-surface border border-line rounded-xl p-3 space-y-2">
            <div className="text-sm font-semibold text-content">Yeni Şablon</div>
            <div className="grid gap-2 sm:grid-cols-3">
              <input value={sablonForm.ad} onChange={(e) => setSablonForm((p) => ({ ...p, ad: e.target.value }))} placeholder="Ad" className="border border-line rounded-lg px-2 py-1.5 text-sm bg-app" />
              <select value={sablonForm.kanal} onChange={(e) => setSablonForm((p) => ({ ...p, kanal: e.target.value }))} className="border border-line rounded-lg px-2 py-1.5 text-sm bg-app">
                <option value="sms">SMS</option><option value="whatsapp">WhatsApp</option>
              </select>
              <select value={sablonForm.tur} onChange={(e) => setSablonForm((p) => ({ ...p, tur: e.target.value }))} className="border border-line rounded-lg px-2 py-1.5 text-sm bg-app">
                <option value="pazarlama">Pazarlama (onay şart)</option><option value="hizmet">Hizmet (onaysıza gider, ret'e saygı)</option>
              </select>
            </div>
            <textarea value={sablonForm.metin} onChange={(e) => setSablonForm((p) => ({ ...p, metin: e.target.value }))} rows={3}
              placeholder="Mesaj metni…" className="w-full border border-line rounded-lg px-2 py-1.5 text-sm bg-app" />
            <div className="flex items-center justify-between">
              <div className="text-[11px] text-subtle">Değişkenler: {degiskenler.join("  ")}</div>
              <button onClick={sablonKaydet} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-white text-sm"><Plus className="h-4 w-4" />Ekle</button>
            </div>
          </div>
          <div className="space-y-1">
            {sablonlar.length === 0 && <div className="text-sm text-subtle py-4 text-center">Şablon yok.</div>}
            {sablonlar.map((t) => (
              <div key={t.id} className="flex items-start gap-2 bg-surface border border-line rounded-lg px-3 py-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2"><span className="font-medium text-content text-sm">{t.ad}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${TUR_RENK[t.tur]}`}>{t.tur}</span>
                    <span className="text-[10px] text-subtle">{t.kanal}</span></div>
                  <div className="text-xs text-subtle mt-0.5 truncate">{t.metin}</div>
                </div>
                <button onClick={() => sablonSil(t.id)} className="text-subtle hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* GÖNDERİMLER — geçmiş */}
      {bolum === "gonderimler" && (
        <div className="space-y-1">
          {gonderimler.length === 0 && <div className="text-sm text-subtle py-4 text-center">Gönderim yok.</div>}
          {gonderimler.map((g) => (
            <div key={g.id} className="flex flex-wrap items-center gap-3 bg-surface border border-line rounded-lg px-3 py-2 text-sm">
              <span className="font-medium text-content">{g.segment}</span>
              <span className="text-[10px] text-subtle">{g.kanal} · {g.tur}</span>
              <span className={`text-[10px] px-2 py-0.5 rounded-full ${g.durum === "tamamlandi" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{g.durum}</span>
              {g.ozet && <span className="text-xs text-subtle tabular-nums">gönderildi {g.ozet.gonderildi ?? 0} · hata {g.ozet.hata ?? 0} · onaysız {g.ozet.onaysiz ?? 0}</span>}
              <span className="ml-auto text-[11px] text-subtle">{(g.olusturma_tarihi || "").slice(0, 10)} · {g.tahmini_maliyet}₺</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
