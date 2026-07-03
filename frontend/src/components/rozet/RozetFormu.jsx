import React, { useState } from "react";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Button } from "../ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../ui/select";

/** Backend core.rozet_kosullari.METRIK_ACIKLAMALARI ile eşleşen metrik listesi. */
export const METRIKLER = {
  teacher: [
    ["icerik_sayisi", "Yayınlanan içerik sayısı"],
    ["kalite_oyu", "Verilen kalite oyu sayısı"],
    ["gorev_atama_sayisi", "Atanan görev sayısı"],
    ["gorev_tamamlanan", "Öğrencilerin tamamladığı görev sayısı"],
    ["ogrenci_ort_streak", "Öğrencilerin ortalama serisi (gün)"],
    ["kur_atlama_sayisi", "Atlattığı kur sayısı"],
    ["veli_anket_sayisi", "Veli anketi sayısı"],
    ["veli_anket_ort", "Veli anketi ortalaması (5üz)"],
    ["veli_tavsiye_orani", "Veli tavsiye oranı (%)"],
    ["gelisim_tamamlama", "Gelişim modülü sayısı"],
    ["mesaj_sayisi", "Gönderilen mesaj sayısı"],
    ["mesaj_ogrenci_veli_kopru", "Hem öğrenci hem veliye mesaj (1)"],
    ["manuel", "Manuel (admin verir)"],
  ],
  student: [
    ["okuma_kayit_sayisi", "Okuma kaydı sayısı"],
    ["okuma_dakikasi", "Toplam okuma dakikası"],
    ["giris_serisi", "Ardışık okuma günü (streak)"],
    ["kitap_sayisi", "Farklı kitap sayısı"],
    ["gorev_tamamlama", "Tamamlanan görev sayısı"],
    ["egzersiz_sayisi", "Egzersiz sayısı"],
    ["egzersiz_tur_sayisi", "Farklı egzersiz türü"],
    ["orman_agac_sayisi", "Orman ağaç sayısı (dk)"],
    ["lig_xp", "Toplam XP (lig)"],
    ["manuel", "Manuel (admin verir)"],
  ],
};

const SEVIYELER = ["bronz", "gumus", "altin", "platin", "elmas"];
const OPERATORLER = [">=", ">", "==", "<=", "<"];

/**
 * RozetFormu — rozet ekle/düzenle. rozet=null → yeni; doluysa düzenleme.
 * Props: rozet, onKaydet(payload), onIptal()
 */
export default function RozetFormu({ rozet, onKaydet, onIptal }) {
  const yeni = !rozet;
  const [f, setF] = useState(() => ({
    kod: rozet?.kod || "",
    rol: rozet?.rol || "student",
    ad: rozet?.ad || "",
    aciklama: rozet?.aciklama || "",
    ikon: rozet?.ikon || "🏅",
    kategori: rozet?.kategori || "",
    seviye: rozet?.seviye || "bronz",
    odul_puan: rozet?.odul_puan ?? 0,
    sira: rozet?.sira ?? 999,
    aktif: rozet?.aktif ?? true,
    metrik: rozet?.kosul?.metrik || "manuel",
    operator: rozet?.kosul?.operator || ">=",
    esik: rozet?.kosul?.esik ?? "",
  }));
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const kaydet = () => {
    if (!f.kod.trim() || !f.ad.trim()) return;
    const kosul =
      f.metrik === "manuel"
        ? { metrik: "manuel", operator: null, esik: null }
        : { metrik: f.metrik, operator: f.operator, esik: Number(f.esik) || 0 };
    onKaydet({
      kod: f.kod.trim(), rol: f.rol, ad: f.ad.trim(), aciklama: f.aciklama,
      ikon: f.ikon, kategori: f.kategori, seviye: f.seviye,
      odul_puan: parseInt(f.odul_puan) || 0, sira: parseInt(f.sira) || 999,
      aktif: f.aktif, kosul,
    });
  };

  const metrikler = METRIKLER[f.rol] || METRIKLER.student;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <Label className="text-[10px]">Kod {yeni ? "*" : "(sabit)"}</Label>
          <Input value={f.kod} disabled={!yeni} onChange={(e) => set("kod", e.target.value)} placeholder="okuma_100" />
        </div>
        <div>
          <Label className="text-[10px]">Rol {yeni ? "" : "(sabit)"}</Label>
          <Select value={f.rol} onValueChange={(v) => set("rol", v)} disabled={!yeni}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="student">Öğrenci</SelectItem>
              <SelectItem value="teacher">Öğretmen</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="col-span-2">
          <Label className="text-[10px]">Ad *</Label>
          <Input value={f.ad} onChange={(e) => set("ad", e.target.value)} placeholder="Kitap Kurdu" />
        </div>
        <div>
          <Label className="text-[10px]">İkon</Label>
          <Input className="text-center" value={f.ikon} onChange={(e) => set("ikon", e.target.value)} />
        </div>
      </div>

      <div>
        <Label className="text-[10px]">Açıklama</Label>
        <Input value={f.aciklama} onChange={(e) => set("aciklama", e.target.value)} placeholder="100 dakika okuma yapan" />
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div>
          <Label className="text-[10px]">Kategori</Label>
          <Input value={f.kategori} onChange={(e) => set("kategori", e.target.value)} placeholder="okuma" />
        </div>
        <div>
          <Label className="text-[10px]">Seviye</Label>
          <Select value={f.seviye} onValueChange={(v) => set("seviye", v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{SEVIYELER.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-[10px]">Ödül Puanı</Label>
          <Input type="number" value={f.odul_puan} onChange={(e) => set("odul_puan", e.target.value)} />
        </div>
      </div>

      {/* Koşul */}
      <div className="bg-gray-50 rounded-lg p-2 space-y-2">
        <Label className="text-[10px] font-semibold">Kazanma Koşulu</Label>
        <div className="grid grid-cols-3 gap-2">
          <div className="col-span-1">
            <Label className="text-[9px]">Metrik</Label>
            <Select value={f.metrik} onValueChange={(v) => set("metrik", v)}>
              <SelectTrigger className="text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                {metrikler.map(([k, a]) => <SelectItem key={k} value={k}>{a}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-[9px]">Operatör</Label>
            <Select value={f.operator} onValueChange={(v) => set("operator", v)} disabled={f.metrik === "manuel"}>
              <SelectTrigger className="text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>{OPERATORLER.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-[9px]">Eşik</Label>
            <Input type="number" value={f.esik} disabled={f.metrik === "manuel"} onChange={(e) => set("esik", e.target.value)} />
          </div>
        </div>
        <p className="text-[10px] text-gray-400">
          Bileşik (AND) koşullar için JSON İçe Aktar kullanın; form tek koşulu düzenler.
        </p>
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-1.5 text-xs">
          <input type="checkbox" checked={f.aktif} onChange={(e) => set("aktif", e.target.checked)} /> Aktif
        </label>
        <div className="flex items-center gap-2">
          <div className="w-16">
            <Label className="text-[9px]">Sıra</Label>
            <Input type="number" value={f.sira} onChange={(e) => set("sira", e.target.value)} />
          </div>
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <Button onClick={kaydet} className="flex-1 bg-blue-600 text-white">💾 Kaydet</Button>
        <Button onClick={onIptal} variant="outline" className="flex-1">İptal</Button>
      </div>
    </div>
  );
}
