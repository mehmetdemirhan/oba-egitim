import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { MessageSquare, Save, Check, X, Info } from "lucide-react";

/**
 * KanalAyarlari — SMS (Netgsm) + WhatsApp Cloud API kimlik bilgileri admin panelinden.
 * Sırlar (şifre/token/verify token) write-only: kayıtlıysa "••••" gösterilir, boş
 * bırakılırsa mevcut korunur; yeni değer girilirse güncellenir. Kimlik dolunca kanal
 * OTOMATİK "kurulu" olur. Props: apiBase, onKayit (üst panelin kanal rozetlerini tazeler).
 */
function Alan({ label, ...p }) {
  return (
    <label className="block">
      <span className="text-xs text-subtle">{label}</span>
      <input {...p} className="w-full border border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
    </label>
  );
}

function KuruluRozet({ kurulu }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs border ${kurulu ? "bg-green-50 border-green-200 text-green-700" : "bg-gray-50 border-line text-subtle"}`}>
      {kurulu ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}{kurulu ? "kurulu" : "kurulmadı"}
    </span>
  );
}

export default function KanalAyarlari({ apiBase, onKayit }) {
  const { toast } = useToast();
  const [ayar, setAyar] = useState(null);
  const [sms, setSms] = useState({});
  const [wa, setWa] = useState({});
  const [kaydediyor, setKaydediyor] = useState("");

  const yukle = useCallback(async () => {
    try {
      const r = await axios.get(`${apiBase}/funnel/ayarlar`);
      setAyar(r.data);
      setSms({ username: r.data.sms.username || "", header: r.data.sms.header || "", partner_code: r.data.sms.partner_code || "", base_url: r.data.sms.base_url || "", iys_filter: !!r.data.sms.iys_filter, password: "" });
      setWa({ phone_id: r.data.whatsapp.phone_id || "", base_url: r.data.whatsapp.base_url || "", default_template: r.data.whatsapp.default_template || "", default_lang: r.data.whatsapp.default_lang || "tr", token: "", webhook_verify_token: "" });
    } catch { toast({ title: "Ayarlar yüklenemedi", variant: "destructive" }); }
  }, [apiBase, toast]);

  useEffect(() => { yukle(); }, [yukle]);

  const kaydet = async (kanal) => {
    setKaydediyor(kanal);
    try {
      if (kanal === "sms") {
        const g = { username: sms.username, header: sms.header, partner_code: sms.partner_code, base_url: sms.base_url, iys_filter: sms.iys_filter };
        if (sms.password) g.password = sms.password;  // boşsa mevcut korunur
        await axios.put(`${apiBase}/funnel/ayarlar/sms`, g);
      } else {
        const g = { phone_id: wa.phone_id, base_url: wa.base_url, default_template: wa.default_template, default_lang: wa.default_lang };
        if (wa.token) g.token = wa.token;
        if (wa.webhook_verify_token) g.webhook_verify_token = wa.webhook_verify_token;
        await axios.put(`${apiBase}/funnel/ayarlar/whatsapp`, g);
      }
      toast({ title: `${kanal.toUpperCase()} ayarları kaydedildi` });
      await yukle();
      onKayit?.();  // üst panel kanal rozetlerini tazele
    } catch (e) {
      toast({ title: "Kaydedilemedi", description: e?.response?.data?.detail || "", variant: "destructive" });
    } finally { setKaydediyor(""); }
  };

  if (!ayar) return null;
  const sirYer = (dolu) => (dolu ? "•••••• (kayıtlı — değiştirmek için gir)" : "girilmedi");

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-2 text-xs text-subtle bg-app border border-line rounded-xl p-3">
        <Info className="h-4 w-4 mt-0.5 shrink-0" />
        <span>Kimlik bilgileri sunucuda saklanır; şifre/token gibi <b>sırlar burada tekrar gösterilmez</b> (yalnız "kayıtlı"). Boş bırakılan sır alanı mevcut değeri korur. Kimlik dolunca kanal otomatik <b>kurulu</b> olur.</span>
      </div>

      {/* SMS (Netgsm) */}
      <div className="bg-surface border border-line rounded-2xl p-4 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-content flex items-center gap-2"><MessageSquare className="h-5 w-5" />SMS (Netgsm)</h3>
          <KuruluRozet kurulu={ayar.sms.kurulu} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Alan label="Kullanıcı adı" value={sms.username} onChange={(e) => setSms({ ...sms, username: e.target.value })} placeholder="Netgsm kullanıcı adı" />
          <Alan label="Şifre" type="password" value={sms.password} onChange={(e) => setSms({ ...sms, password: e.target.value })} placeholder={sirYer(ayar.sms.sifre_dolu)} autoComplete="new-password" />
          <Alan label="Başlık (msgheader)" value={sms.header} onChange={(e) => setSms({ ...sms, header: e.target.value })} placeholder="Onaylı SMS başlığı" />
          <Alan label="Partner kodu (ops.)" value={sms.partner_code} onChange={(e) => setSms({ ...sms, partner_code: e.target.value })} />
          <Alan label="Base URL" value={sms.base_url} onChange={(e) => setSms({ ...sms, base_url: e.target.value })} placeholder="https://api.netgsm.com.tr" />
          <label className="flex items-center gap-2 text-sm self-end pb-2">
            <input type="checkbox" checked={sms.iys_filter} onChange={(e) => setSms({ ...sms, iys_filter: e.target.checked })} />
            <span>İYS filtresi (pazarlama SMS'te)</span>
          </label>
        </div>
        <div className="flex justify-end">
          <button onClick={() => kaydet("sms")} disabled={kaydediyor === "sms"} className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white text-sm px-4 py-2 rounded-xl disabled:opacity-50">
            <Save className="h-4 w-4" />{kaydediyor === "sms" ? "Kaydediliyor…" : "SMS Ayarlarını Kaydet"}
          </button>
        </div>
      </div>

      {/* WhatsApp Cloud API */}
      <div className="bg-surface border border-line rounded-2xl p-4 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-content flex items-center gap-2"><MessageSquare className="h-5 w-5 text-emerald-600" />WhatsApp Cloud API</h3>
          <KuruluRozet kurulu={ayar.whatsapp.kurulu} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Alan label="Kalıcı Erişim Token'ı" type="password" value={wa.token} onChange={(e) => setWa({ ...wa, token: e.target.value })} placeholder={sirYer(ayar.whatsapp.token_dolu)} autoComplete="new-password" />
          <Alan label="Telefon Numarası ID (phone_id)" value={wa.phone_id} onChange={(e) => setWa({ ...wa, phone_id: e.target.value })} placeholder="Meta phone number id" />
          <Alan label="Varsayılan şablon adı" value={wa.default_template} onChange={(e) => setWa({ ...wa, default_template: e.target.value })} placeholder="bilgilendirme" />
          <Alan label="Şablon dili" value={wa.default_lang} onChange={(e) => setWa({ ...wa, default_lang: e.target.value })} placeholder="tr" />
          <Alan label="Webhook Verify Token" type="password" value={wa.webhook_verify_token} onChange={(e) => setWa({ ...wa, webhook_verify_token: e.target.value })} placeholder={sirYer(ayar.whatsapp.verify_token_dolu)} autoComplete="new-password" />
          <Alan label="Base URL" value={wa.base_url} onChange={(e) => setWa({ ...wa, base_url: e.target.value })} placeholder="https://graph.facebook.com/v20.0" />
        </div>
        <p className="text-[11px] text-subtle">Webhook URL (Meta paneline): <code>{apiBase}/funnel/whatsapp/webhook</code> — Verify Token yukarıdakiyle aynı olmalı. Onaylı bir şablon gerekir.</p>
        <div className="flex justify-end">
          <button onClick={() => kaydet("whatsapp")} disabled={kaydediyor === "whatsapp"} className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white text-sm px-4 py-2 rounded-xl disabled:opacity-50">
            <Save className="h-4 w-4" />{kaydediyor === "whatsapp" ? "Kaydediliyor…" : "WhatsApp Ayarlarını Kaydet"}
          </button>
        </div>
      </div>
    </div>
  );
}
