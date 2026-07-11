import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { useToast } from "../hooks/use-toast";
import {
  ChevronDown, ChevronRight, Plus, Trash2, AlertTriangle, Search,
} from "lucide-react";

/**
 * OdemeTablosu — Excel-benzeri satır içi düzenlenebilir ödeme tablosu.
 * MuhasebePaneli ve admin Muhasebe sekmesi AYNI bileşeni paylaşır (kopya yok).
 *
 * Öğrenci tarafı KUR-KAYDI bazlıdır: her satır bir kur kaydıdır (kur kaydı olmayan
 * öğrenci tek satır). "Ödenen" öğrencinin toplam ödemesinden FIFO türetilir (backend),
 * o yüzden burada salt-okunurdur; tahsilat, satır detayındaki ödeme geçmişinden eklenir.
 *
 * Satır alanları (backend /muhasebe/kisiler):
 *   {id(satır=kur kaydı), kisi_id(öğrenci/öğretmen — PATCH hedefi), kur_ucreti_id,
 *    kayit_zamani, ogretmen_ad, ad, soyad, sinif, kur, veli_ad, veli_soyad, veli_telefon,
 *    yapilmasi_gereken_odeme(Beklenen), yapilan_odeme(Ödenen), kalan, muhasebe_notu}
 */

const formatTL = (v) =>
  new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 0 }).format(Number(v || 0));
const formatTarih = (t) => {
  if (!t) return "—";
  try { return new Date(t).toLocaleDateString("tr-TR"); } catch { return "—"; }
};
const isoGun = (t) => { try { return (t || "").slice(0, 10); } catch { return ""; } };

// Tek hücre — tıkla-düzenle; Enter/blur kaydeder, Esc iptal.
function EditableCell({ value, kind = "text", format, align = "left", editable = true, onSave, placeholder }) {
  const [editing, setEditing] = useState(false);
  const [taslak, setTaslak] = useState(value ?? "");
  const ref = useRef(null);
  useEffect(() => { setTaslak(value ?? ""); }, [value]);
  useEffect(() => { if (editing && ref.current) { ref.current.focus(); ref.current.select?.(); } }, [editing]);

  const hiza = align === "right" ? "text-right" : "text-left";
  const kaydet = async () => {
    setEditing(false);
    if (String(taslak) === String(value ?? "")) return;
    const ok = await onSave(taslak);
    if (!ok) setTaslak(value ?? "");
  };
  const iptal = () => { setTaslak(value ?? ""); setEditing(false); };

  if (!editable) {
    return <td className={`px-3 py-2 ${kind === "number" ? "tabular-nums" : ""} text-subtle ${hiza}`}>{format ? format(value) : (value || "—")}</td>;
  }
  if (!editing) {
    return (
      <td onClick={() => setEditing(true)} title="Düzenlemek için tıklayın"
        className={`px-3 py-2 ${hiza} cursor-pointer hover:bg-blue-50 hover:ring-1 hover:ring-inset hover:ring-blue-200 ${kind === "number" ? "tabular-nums" : ""}`}>
        {format ? format(value) : (value || <span className="text-slate-300">{placeholder || "—"}</span>)}
      </td>
    );
  }
  return (
    <td className={`px-1 py-1 ${hiza}`}>
      <input ref={ref}
        type={kind === "number" ? "number" : kind === "date" ? "date" : "text"}
        min={kind === "number" ? "0" : undefined}
        value={kind === "date" ? isoGun(taslak) : taslak}
        onChange={(e) => setTaslak(e.target.value)}
        onBlur={kaydet}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); kaydet(); }
          else if (e.key === "Escape") { e.preventDefault(); iptal(); }
        }}
        className={`w-full border border-primary rounded px-2 py-1 text-sm outline-none ${kind === "number" ? "tabular-nums text-right" : ""}`} />
    </td>
  );
}

export default function OdemeTablosu({ tip, kisiler, payments, apiBase, onDegisim }) {
  const { toast } = useToast();
  const [arama, setArama] = useState("");
  const [acik, setAcik] = useState(null);
  const [silDialog, setSilDialog] = useState(null);
  const [kurForm, setKurForm] = useState({ kur_adi: "", tutar: "", baslangic_tarihi: "" });

  const ogrenciMi = tip === "ogrenci";

  const filtreli = useMemo(() => {
    const q = arama.trim().toLocaleLowerCase("tr");
    if (!q) return kisiler;
    return kisiler.filter((k) =>
      `${k.ad} ${k.soyad} ${k.veli_ad || ""} ${k.veli_soyad || ""} ${k.kur || ""} ${k.sinif || ""}`.toLocaleLowerCase("tr").includes(q));
  }, [kisiler, arama]);

  // Ödemeler kişi (öğrenci/öğretmen) bazında — kur satırları aynı kisi_id'yi paylaşır
  const kisiOdemeleri = useCallback(
    (kisiId) => payments.filter((p) => p.tip === tip && p.kisi_id === kisiId)
      .sort((a, b) => new Date(b.tarih) - new Date(a.tarih)),
    [payments, tip]
  );

  const req = async (fn, hataBaslik = "Kaydedilemedi") => {
    try { await fn(); onDegisim?.(); return true; }
    catch (e) { toast({ title: hataBaslik, description: e?.response?.data?.detail || "", variant: "destructive" }); return false; }
  };

  // Kişi (öğrenci/öğretmen) alanı — PATCH /muhasebe/kisi/{tip}/{kisi_id}
  const alanKaydet = (kisiId, alan, deger) =>
    req(() => axios.patch(`${apiBase}/muhasebe/kisi/${tip}/${kisiId}`, { [alan]: deger }));
  const isimKaydet = (kisiId, adAlan, soyadAlan, tamAd) => {
    const p = String(tamAd).trim().split(/\s+/);
    const ad = p.shift() || "";
    return req(() => axios.patch(`${apiBase}/muhasebe/kisi/${tip}/${kisiId}`, { [adAlan]: ad, [soyadAlan]: p.join(" ") }));
  };
  // Kur satırında "Kuru" — kur kaydı varsa kur-ücreti PATCH, yoksa öğrenci.kur
  const kurAdiKaydet = (k, yeniAd) =>
    k.kur_ucreti_id
      ? req(() => axios.patch(`${apiBase}/muhasebe/kur-ucreti/${k.kur_ucreti_id}`, { kur_adi: yeniAd }))
      : alanKaydet(k.kisi_id, "kur", yeniAd);
  // Kur satırında "Beklenen" — kur kaydı varsa kur tutarı, yoksa öğrenci toplamı
  const beklenenKaydet = (k, yeniTutar) =>
    k.kur_ucreti_id
      ? req(() => axios.patch(`${apiBase}/muhasebe/kur-ucreti/${k.kur_ucreti_id}`, { tutar: parseFloat(yeniTutar) || 0 }))
      : alanKaydet(k.kisi_id, "yapilmasi_gereken_odeme", yeniTutar);

  const odemeSil = async () => {
    if (await req(() => axios.delete(`${apiBase}/payments/${silDialog.id}`), "Silinemedi")) {
      setSilDialog(null); toast({ title: "Ödeme silindi" });
    }
  };
  const odemeEkle = (kisiId) =>
    req(() => axios.post(`${apiBase}/payments`, { tip, kisi_id: kisiId, miktar: 0, aciklama: "" }))
      .then((ok) => ok && toast({ title: "Boş ödeme satırı eklendi", description: "Tutarı/tarihi hücreden düzenleyin." }));

  const kurUcretiEkle = async (kisiId) => {
    const tutar = parseFloat(kurForm.tutar);
    if (!kurForm.kur_adi.trim() || !tutar || tutar <= 0) {
      toast({ title: "Kur adı ve geçerli tutar gerekli", variant: "destructive" }); return;
    }
    const ok = await req(() => axios.post(`${apiBase}/muhasebe/ogrenci/${kisiId}/kur-ucreti`, {
      kur_adi: kurForm.kur_adi.trim(), tutar, baslangic_tarihi: kurForm.baslangic_tarihi || undefined,
    }), "Kur ücreti eklenemedi");
    if (ok) { setKurForm({ kur_adi: "", tutar: "", baslangic_tarihi: "" }); toast({ title: "Kur ücreti eklendi", description: "Yeni satır olarak eklendi." }); }
  };

  const kolonSayisi = ogrenciMi ? 12 : 7;

  return (
    <div className="space-y-3">
      <div className="relative max-w-xs">
        <Search className="h-4 w-4 text-subtle absolute left-3 top-1/2 -translate-y-1/2" />
        <input value={arama} onChange={(e) => setArama(e.target.value)} placeholder="Kişi / kur / sınıf ara…"
          className="pl-9 pr-3 py-1.5 text-sm border border-line rounded-lg bg-surface w-full focus:outline-none focus:ring-2 focus:ring-primary" />
      </div>

      <div className="border border-line rounded-2xl shadow-sm overflow-x-auto bg-surface">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-subtle border-b border-line bg-app whitespace-nowrap">
              <th className="px-3 py-2 w-8"></th>
              {ogrenciMi ? (
                <>
                  <th className="px-3 py-2">Kayıt Zamanı</th>
                  <th className="px-3 py-2">Öğretmeni</th>
                  <th className="px-3 py-2">Öğrenci Adı Soyadı</th>
                  <th className="px-3 py-2">Sınıfı</th>
                  <th className="px-3 py-2">Kuru</th>
                  <th className="px-3 py-2">Veli Adı Soyadı</th>
                  <th className="px-3 py-2">Telefon</th>
                  <th className="px-3 py-2 text-right">Beklenen</th>
                  <th className="px-3 py-2 text-right">Ödenen</th>
                  <th className="px-3 py-2 text-right">Kalan</th>
                  <th className="px-3 py-2">Açıklama</th>
                </>
              ) : (
                <>
                  <th className="px-3 py-2">Öğretmen</th>
                  <th className="px-3 py-2">Telefon</th>
                  <th className="px-3 py-2 text-right">Ödenecek</th>
                  <th className="px-3 py-2 text-right">Ödenen</th>
                  <th className="px-3 py-2 text-right">Kalan</th>
                  <th className="px-3 py-2">Açıklama</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {filtreli.length === 0 && <tr><td colSpan={kolonSayisi} className="px-3 py-8 text-center text-subtle">Kayıt yok.</td></tr>}
            {filtreli.map((k) => {
              const acikMi = acik === k.id;
              const odemeler = kisiOdemeleri(k.kisi_id);
              return (
                <React.Fragment key={k.id}>
                  <tr className="border-b border-line">
                    <td className="px-3 py-2">
                      <button onClick={() => { setAcik(acikMi ? null : k.id); setKurForm({ kur_adi: "", tutar: "", baslangic_tarihi: "" }); }}
                        className="text-subtle hover:text-content" aria-label="Detay">
                        {acikMi ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </button>
                    </td>

                    {ogrenciMi ? (
                      <>
                        <td className="px-3 py-2 text-subtle whitespace-nowrap">{formatTarih(k.kayit_zamani)}</td>
                        <td className="px-3 py-2 text-subtle whitespace-nowrap">{k.ogretmen_ad || "—"}</td>
                        <EditableCell value={`${k.ad || ""} ${k.soyad || ""}`.trim()} placeholder="Ad Soyad"
                          onSave={(v) => isimKaydet(k.kisi_id, "ad", "soyad", v)} />
                        <EditableCell value={k.sinif} placeholder="Sınıf"
                          onSave={(v) => alanKaydet(k.kisi_id, "sinif", v)} />
                        <EditableCell value={k.kur} placeholder="Kur"
                          onSave={(v) => kurAdiKaydet(k, v)} />
                        <EditableCell value={`${k.veli_ad || ""} ${k.veli_soyad || ""}`.trim()} placeholder="Veli"
                          onSave={(v) => isimKaydet(k.kisi_id, "veli_ad", "veli_soyad", v)} />
                        <EditableCell value={k.veli_telefon} placeholder="Telefon"
                          onSave={(v) => alanKaydet(k.kisi_id, "veli_telefon", v)} />
                        <EditableCell value={k.yapilmasi_gereken_odeme} kind="number" align="right" format={formatTL}
                          onSave={(v) => beklenenKaydet(k, v)} />
                        <td className="px-3 py-2 text-right tabular-nums text-subtle">{formatTL(k.yapilan_odeme)}</td>
                        <td className={`px-3 py-2 text-right tabular-nums font-medium ${k.kalan > 0 ? "text-amber-600" : "text-subtle"}`}>{formatTL(k.kalan)}</td>
                        <EditableCell value={k.muhasebe_notu} placeholder="Not ekle" kind="text"
                          onSave={(v) => alanKaydet(k.kisi_id, "muhasebe_notu", v)} />
                      </>
                    ) : (
                      <>
                        <EditableCell value={`${k.ad || ""} ${k.soyad || ""}`.trim()} placeholder="Ad Soyad"
                          onSave={(v) => isimKaydet(k.kisi_id, "ad", "soyad", v)} />
                        <td className="px-3 py-2 text-subtle whitespace-nowrap">{k.telefon || "—"}</td>
                        <EditableCell value={k.yapilmasi_gereken_odeme} kind="number" align="right" format={formatTL}
                          onSave={(v) => alanKaydet(k.kisi_id, "yapilmasi_gereken_odeme", v)} />
                        <EditableCell value={k.yapilan_odeme} kind="number" align="right" format={formatTL}
                          onSave={(v) => alanKaydet(k.kisi_id, "yapilan_odeme", v)} />
                        <td className={`px-3 py-2 text-right tabular-nums font-medium ${k.kalan > 0 ? "text-amber-600" : "text-subtle"}`}>{formatTL(k.kalan)}</td>
                        <EditableCell value={k.muhasebe_notu} placeholder="Not ekle" kind="text"
                          onSave={(v) => alanKaydet(k.kisi_id, "muhasebe_notu", v)} />
                      </>
                    )}
                  </tr>

                  {acikMi && (
                    <tr className="bg-app/40">
                      <td colSpan={kolonSayisi} className="px-4 py-3 space-y-4">
                        {/* Ödeme geçmişi (kişi bazında — vergi bilgisiyle) */}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium text-subtle">Ödeme Geçmişi ({odemeler.length}){ogrenciMi && " — brüt tahsilat"}</span>
                            <button onClick={() => odemeEkle(k.kisi_id)}
                              className="inline-flex items-center gap-1 text-xs border border-line px-2 py-1 rounded-lg hover:bg-surface">
                              <Plus className="h-3.5 w-3.5" />Ödeme satırı ekle
                            </button>
                          </div>
                          {odemeler.length === 0 ? (
                            <div className="text-xs text-subtle">Kayıtlı ödeme yok.</div>
                          ) : (
                            <div className="space-y-1">
                              {odemeler.map((p) => (
                                <div key={p.id} className="flex items-center gap-2 text-sm bg-surface border border-line rounded-lg px-2 py-1">
                                  <input type="number" min="0" defaultValue={p.miktar} title="Brüt tahsilat"
                                    onBlur={async (e) => { const v = parseFloat(e.target.value); if (v >= 0 && v !== p.miktar) { await req(() => axios.put(`${apiBase}/payments/${p.id}`, { miktar: v }), "Güncellenemedi"); } }}
                                    className="w-24 tabular-nums text-right border border-line rounded px-2 py-0.5" />
                                  <input type="date" defaultValue={isoGun(p.tarih)}
                                    onBlur={async (e) => { if (e.target.value && e.target.value !== isoGun(p.tarih)) { await req(() => axios.put(`${apiBase}/payments/${p.id}`, { tarih: e.target.value }), "Güncellenemedi"); } }}
                                    className="tabular-nums border border-line rounded px-2 py-0.5 text-xs" />
                                  {ogrenciMi && p.vergi != null && (
                                    <span className="text-[11px] text-subtle whitespace-nowrap">vergi {formatTL(p.vergi)} • net {formatTL(p.net)}</span>
                                  )}
                                  <input defaultValue={p.aciklama || ""} placeholder="Açıklama"
                                    onBlur={async (e) => { if (e.target.value !== (p.aciklama || "")) { await req(() => axios.put(`${apiBase}/payments/${p.id}`, { aciklama: e.target.value }), "Güncellenemedi"); } }}
                                    className="flex-1 border border-line rounded px-2 py-0.5 text-xs" />
                                  <button onClick={() => setSilDialog({ id: p.id, aciklama: `${formatTL(p.miktar)} — ${formatTarih(p.tarih)}` })}
                                    className="text-slate-400 hover:text-red-600" aria-label="Sil"><Trash2 className="h-4 w-4" /></button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Kur ücreti (yalnız öğrenci) — yeni satır oluşturur */}
                        {ogrenciMi && (
                          <div className="border-t border-line pt-3">
                            <div className="text-xs font-medium text-subtle mb-2">Yeni Kur Ücreti Ekle (yeni satır)</div>
                            <div className="flex flex-wrap items-end gap-2">
                              <input value={kurForm.kur_adi} onChange={(e) => setKurForm({ ...kurForm, kur_adi: e.target.value })}
                                placeholder="Kur / dönem (örn. Kur 3)" className="border border-line rounded-lg px-3 py-1.5 text-sm" />
                              <input type="number" min="0" value={kurForm.tutar} onChange={(e) => setKurForm({ ...kurForm, tutar: e.target.value })}
                                placeholder="Tutar" className="w-28 border border-line rounded-lg px-3 py-1.5 text-sm tabular-nums" />
                              <input type="date" value={kurForm.baslangic_tarihi} onChange={(e) => setKurForm({ ...kurForm, baslangic_tarihi: e.target.value })}
                                className="border border-line rounded-lg px-3 py-1.5 text-sm" />
                              <button onClick={() => kurUcretiEkle(k.kisi_id)}
                                className="inline-flex items-center gap-1 bg-primary hover:bg-primary-hover text-white text-sm px-3 py-1.5 rounded-lg">
                                <Plus className="h-4 w-4" />Ekle
                              </button>
                            </div>
                            <div className="text-[11px] text-subtle mt-1">Yeni kur, tabloda kendi temiz satırı olarak görünür; beklenen toplama yansır.</div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {silDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSilDialog(null)}>
          <div className="bg-surface rounded-2xl shadow-lg border border-line p-5 max-w-sm w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 text-red-600 font-semibold mb-2"><AlertTriangle className="h-5 w-5" />Ödemeyi Sil</div>
            <p className="text-sm text-subtle mb-3">Bu ödeme silinecek ve kişinin bakiyesi güncellenecek. Geri alınamaz.</p>
            <div className="text-sm text-content bg-app border border-line rounded-lg px-3 py-2 mb-4">{silDialog.aciklama}</div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setSilDialog(null)} className="px-3 py-1.5 rounded-lg text-sm text-subtle hover:bg-app">Vazgeç</button>
              <button onClick={odemeSil} className="px-3 py-1.5 rounded-lg text-sm bg-red-600 hover:bg-red-700 text-white">Sil</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
