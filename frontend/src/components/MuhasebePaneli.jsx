import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Card, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { useToast } from "../hooks/use-toast";
import {
  Wallet, TrendingUp, TrendingDown, Clock, Plus, Trash2, Edit2, LogOut,
  Search, ChevronDown, ChevronRight, Users, GraduationCap, AlertTriangle,
} from "lucide-react";

/**
 * MuhasebePaneli — "accountant" rolüne özel SADE ödeme paneli.
 * Yalnızca öğrenci tahsilatları ve öğretmen ödemeleri; eğitim/CRM içeriği YOK,
 * sekme çubuğu YOK. Tam yetki: görüntüleme + kayıt + düzeltme + silme.
 * Backend: GET /muhasebe/ozet, GET /muhasebe/kisiler, /payments (CRUD).
 */
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatTL = (v) =>
  new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 0 }).format(Number(v || 0));
const formatTarih = (t) => {
  if (!t) return "—";
  try { return new Date(t).toLocaleDateString("tr-TR"); } catch { return "—"; }
};
const bugunISO = () => new Date().toISOString().slice(0, 10);

// KPI kartı — sol renk şeritli, tabular sayı, Lucide ikon.
function KpiKart({ Ikon, etiket, tutar, vurgu }) {
  const renk = {
    blue: "border-l-blue-500 text-blue-600",
    green: "border-l-emerald-500 text-emerald-600",
    amber: "border-l-amber-500 text-amber-600",
    slate: "border-l-slate-400 text-slate-600",
  }[vurgu] || "border-l-slate-400 text-slate-600";
  return (
    <Card className="border border-line shadow-sm">
      <CardContent className={`p-4 border-l-4 rounded-l-none ${renk.split(" ")[0]}`}>
        <div className="flex items-center gap-1.5 text-xs text-subtle mb-1">
          <Ikon className={`h-4 w-4 ${renk.split(" ")[1]}`} />{etiket}
        </div>
        <div className={`text-2xl font-bold tabular-nums ${renk.split(" ")[1]}`}>{formatTL(tutar)}</div>
      </CardContent>
    </Card>
  );
}

export default function MuhasebePaneli({ user, logout }) {
  const { toast } = useToast();
  const [ozet, setOzet] = useState(null);
  const [kisiler, setKisiler] = useState({ ogrenciler: [], ogretmenler: [] });
  const [payments, setPayments] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [sekme, setSekme] = useState("ogrenci"); // "ogrenci" | "ogretmen"
  const [arama, setArama] = useState("");
  const [acikKisi, setAcikKisi] = useState(null); // geçmiş açık olan kişi id

  // Ödeme kaydet/düzelt dialogu
  const [odemeDialog, setOdemeDialog] = useState(null); // {mod:"yeni"|"duzelt", ...}
  const [silDialog, setSilDialog] = useState(null); // {id, aciklama}

  const veriYukle = useCallback(async () => {
    setYukleniyor(true);
    try {
      const [o, k, p] = await Promise.all([
        axios.get(`${API}/muhasebe/ozet`),
        axios.get(`${API}/muhasebe/kisiler`),
        axios.get(`${API}/payments`),
      ]);
      setOzet(o.data);
      setKisiler(k.data || { ogrenciler: [], ogretmenler: [] });
      setPayments(Array.isArray(p.data) ? p.data : []);
    } catch {
      toast({ title: "Veriler yüklenemedi", variant: "destructive" });
    } finally {
      setYukleniyor(false);
    }
  }, [toast]);

  useEffect(() => { veriYukle(); }, [veriYukle]);

  const liste = sekme === "ogrenci" ? kisiler.ogrenciler : kisiler.ogretmenler;
  const filtreli = useMemo(() => {
    const q = arama.trim().toLocaleLowerCase("tr");
    if (!q) return liste;
    return liste.filter((k) => `${k.ad} ${k.soyad}`.toLocaleLowerCase("tr").includes(q));
  }, [liste, arama]);

  // Kişi başına ödemeler (tip + kisi_id)
  const kisiOdemeleri = useCallback(
    (kisiId) => payments.filter((p) => p.tip === sekme && p.kisi_id === kisiId)
      .sort((a, b) => new Date(b.tarih) - new Date(a.tarih)),
    [payments, sekme]
  );
  const sonOdeme = (kisiId) => {
    const o = kisiOdemeleri(kisiId);
    return o.length ? o[0].tarih : null;
  };

  const odemeKaydet = async () => {
    const d = odemeDialog;
    const miktar = parseFloat(d.miktar);
    if (!d.kisi_id || !miktar || miktar <= 0) { toast({ title: "Kişi ve geçerli tutar gerekli", variant: "destructive" }); return; }
    try {
      if (d.mod === "duzelt") {
        await axios.put(`${API}/payments/${d.id}`, { miktar, aciklama: d.aciklama, tarih: d.tarih || undefined });
      } else {
        await axios.post(`${API}/payments`, { tip: sekme, kisi_id: d.kisi_id, miktar, aciklama: d.aciklama, tarih: d.tarih || undefined });
      }
      setOdemeDialog(null);
      toast({ title: d.mod === "duzelt" ? "Ödeme güncellendi" : "Ödeme kaydedildi" });
      await veriYukle();
    } catch {
      toast({ title: "İşlem başarısız", variant: "destructive" });
    }
  };

  const odemeSil = async () => {
    try {
      await axios.delete(`${API}/payments/${silDialog.id}`);
      setSilDialog(null);
      toast({ title: "Ödeme silindi" });
      await veriYukle();
    } catch {
      toast({ title: "Silinemedi", variant: "destructive" });
    }
  };

  const tabButon = (id, etiket, Ikon) => (
    <button onClick={() => { setSekme(id); setAcikKisi(null); setArama(""); }}
      className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all ${sekme === id ? "bg-primary text-white border-primary" : "bg-surface text-subtle border-line hover:bg-app"}`}>
      <Ikon className="h-4 w-4" />{etiket}
    </button>
  );

  const ogr = ozet?.ogrenci || {}; const ogt = ozet?.ogretmen || {};

  return (
    <div className="min-h-dvh bg-app">
      {/* Header — sekme çubuğu YOK */}
      <header className="bg-surface border-b border-line">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center h-9 w-9 rounded-xl bg-primary text-white"><Wallet className="h-5 w-5" /></span>
            <div>
              <div className="font-bold text-content leading-tight">OBA Muhasebe</div>
              <div className="text-xs text-subtle">{user?.ad} {user?.soyad}</div>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={logout} className="text-subtle">
            <LogOut className="h-4 w-4 mr-1" />Çıkış
          </Button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* KPI kartları */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <KpiKart Ikon={TrendingUp} etiket="Beklenen Tahsilat" tutar={ogr.beklenen} vurgu="blue" />
          <KpiKart Ikon={Wallet} etiket="Tahsil Edilen" tutar={ogr.tahsil_edilen} vurgu="green" />
          <KpiKart Ikon={Clock} etiket="Bekleyen Tahsilat" tutar={ogr.bekleyen} vurgu="amber" />
          <KpiKart Ikon={TrendingDown} etiket="Öğretmene Ödenecek" tutar={ogt.odenecek} vurgu="slate" />
          <KpiKart Ikon={Wallet} etiket="Öğretmene Ödenen" tutar={ogt.odenen} vurgu="green" />
        </div>

        {/* Sekmeler */}
        <div className="flex gap-2">
          {tabButon("ogrenci", "Öğrenci Ödemeleri", GraduationCap)}
          {tabButon("ogretmen", "Öğretmen Ödemeleri", Users)}
        </div>

        {/* Araç çubuğu */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="h-4 w-4 text-subtle absolute left-3 top-1/2 -translate-y-1/2" />
            <Input value={arama} onChange={(e) => setArama(e.target.value)} placeholder="Kişi ara…" className="pl-9" />
          </div>
          <Button onClick={() => setOdemeDialog({ mod: "yeni", kisi_id: "", miktar: "", aciklama: "", tarih: bugunISO() })}
            className="bg-primary hover:bg-primary-hover text-white">
            <Plus className="h-4 w-4 mr-1" />Ödeme Kaydet
          </Button>
        </div>

        {/* Kişi tablosu */}
        <Card className="border border-line shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-subtle border-b border-line bg-app">
                  <th className="px-4 py-2 w-8"></th>
                  <th className="px-4 py-2">Ad Soyad</th>
                  <th className="px-4 py-2 text-right">{sekme === "ogrenci" ? "Beklenen" : "Ödenecek"}</th>
                  <th className="px-4 py-2 text-right">Ödenen</th>
                  <th className="px-4 py-2 text-right">Kalan</th>
                  <th className="px-4 py-2">Son Ödeme</th>
                </tr>
              </thead>
              <tbody>
                {yukleniyor && <tr><td colSpan={6} className="px-4 py-8 text-center text-subtle">Yükleniyor…</td></tr>}
                {!yukleniyor && filtreli.length === 0 && <tr><td colSpan={6} className="px-4 py-8 text-center text-subtle">Kayıt yok.</td></tr>}
                {!yukleniyor && filtreli.map((k) => {
                  const acik = acikKisi === k.id;
                  const odemeler = kisiOdemeleri(k.id);
                  return (
                    <React.Fragment key={k.id}>
                      <tr className="border-b border-line hover:bg-app/50">
                        <td className="px-4 py-2">
                          <button onClick={() => setAcikKisi(acik ? null : k.id)} className="text-subtle hover:text-content" aria-label="Geçmiş">
                            {acik ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                          </button>
                        </td>
                        <td className="px-4 py-2 text-content font-medium">{k.ad} {k.soyad}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-content">{formatTL(k.yapilmasi_gereken_odeme)}</td>
                        <td className="px-4 py-2 text-right tabular-nums text-emerald-600">{formatTL(k.yapilan_odeme)}</td>
                        <td className={`px-4 py-2 text-right tabular-nums font-medium ${k.kalan > 0 ? "text-amber-600" : "text-subtle"}`}>{formatTL(k.kalan)}</td>
                        <td className="px-4 py-2 text-subtle tabular-nums">{formatTarih(sonOdeme(k.id))}</td>
                      </tr>
                      {acik && (
                        <tr className="bg-app/40">
                          <td colSpan={6} className="px-4 py-3">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs font-medium text-subtle">Ödeme Geçmişi ({odemeler.length})</span>
                              <Button size="sm" variant="outline" className="h-7 text-xs"
                                onClick={() => setOdemeDialog({ mod: "yeni", kisi_id: k.id, miktar: "", aciklama: "", tarih: bugunISO() })}>
                                <Plus className="h-3.5 w-3.5 mr-1" />Bu kişiye ödeme
                              </Button>
                            </div>
                            {odemeler.length === 0 ? (
                              <div className="text-xs text-subtle py-2">Kayıtlı ödeme yok.</div>
                            ) : (
                              <div className="space-y-1">
                                {odemeler.map((p) => (
                                  <div key={p.id} className="flex items-center gap-3 text-sm bg-surface border border-line rounded-lg px-3 py-1.5">
                                    <span className="tabular-nums font-medium text-content w-24 text-right">{formatTL(p.miktar)}</span>
                                    <span className="tabular-nums text-subtle text-xs w-24">{formatTarih(p.tarih)}</span>
                                    <span className="text-subtle text-xs flex-1 truncate">{p.aciklama || "—"}</span>
                                    <button onClick={() => setOdemeDialog({ mod: "duzelt", id: p.id, kisi_id: k.id, miktar: String(p.miktar), aciklama: p.aciklama || "", tarih: (p.tarih || "").slice(0, 10) })}
                                      className="text-slate-400 hover:text-primary" aria-label="Düzelt"><Edit2 className="h-4 w-4" /></button>
                                    <button onClick={() => setSilDialog({ id: p.id, aciklama: `${formatTL(p.miktar)} — ${formatTarih(p.tarih)}` })}
                                      className="text-slate-400 hover:text-red-600" aria-label="Sil"><Trash2 className="h-4 w-4" /></button>
                                  </div>
                                ))}
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
        </Card>
      </main>

      {/* Ödeme kaydet / düzelt dialogu */}
      <Dialog open={!!odemeDialog} onOpenChange={(o) => !o && setOdemeDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{odemeDialog?.mod === "duzelt" ? "Ödeme Düzelt" : "Ödeme Kaydet"}</DialogTitle>
            <DialogDescription>{sekme === "ogrenci" ? "Öğrenci tahsilatı" : "Öğretmen ödemesi"}</DialogDescription>
          </DialogHeader>
          {odemeDialog && (
            <div className="space-y-3">
              {odemeDialog.mod !== "duzelt" && (
                <div>
                  <Label className="text-xs">Kişi</Label>
                  <Select value={odemeDialog.kisi_id} onValueChange={(v) => setOdemeDialog({ ...odemeDialog, kisi_id: v })}>
                    <SelectTrigger><SelectValue placeholder="Kişi seçin" /></SelectTrigger>
                    <SelectContent>
                      {liste.map((k) => <SelectItem key={k.id} value={k.id}>{k.ad} {k.soyad}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Tutar (₺)</Label>
                  <Input type="number" min="0" step="1" value={odemeDialog.miktar}
                    onChange={(e) => setOdemeDialog({ ...odemeDialog, miktar: e.target.value })} />
                </div>
                <div>
                  <Label className="text-xs">Tarih</Label>
                  <Input type="date" value={odemeDialog.tarih}
                    onChange={(e) => setOdemeDialog({ ...odemeDialog, tarih: e.target.value })} />
                </div>
              </div>
              <div>
                <Label className="text-xs">Açıklama</Label>
                <Input value={odemeDialog.aciklama} placeholder="Opsiyonel"
                  onChange={(e) => setOdemeDialog({ ...odemeDialog, aciklama: e.target.value })} />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => setOdemeDialog(null)}>İptal</Button>
                <Button onClick={odemeKaydet} className="bg-primary hover:bg-primary-hover text-white">Kaydet</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Silme onay dialogu */}
      <Dialog open={!!silDialog} onOpenChange={(o) => !o && setSilDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600"><AlertTriangle className="h-5 w-5" />Ödemeyi Sil</DialogTitle>
            <DialogDescription>Bu ödeme kaydı silinecek ve kişinin bakiyesi güncellenecek. Bu işlem geri alınamaz.</DialogDescription>
          </DialogHeader>
          <div className="text-sm text-content bg-app border border-line rounded-lg px-3 py-2">{silDialog?.aciklama}</div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setSilDialog(null)}>Vazgeç</Button>
            <Button onClick={odemeSil} className="bg-red-600 hover:bg-red-700 text-white">Sil</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
