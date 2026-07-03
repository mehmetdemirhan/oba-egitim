import React, { useState } from "react";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Button } from "../ui/button";

/** Backend core.tema_varsayilan.TOKEN_ALANLARI ile eşleşen 12 token. */
export const TOKENLAR = [
  ["primary", "Birincil"], ["primary_hover", "Birincil (hover)"], ["secondary", "İkincil"],
  ["background", "Zemin"], ["surface", "Yüzey"], ["text", "Metin"],
  ["text_secondary", "İkincil metin"], ["border", "Kenarlık"], ["accent", "Vurgu"],
  ["danger", "Tehlike"], ["success", "Başarı"], ["warning", "Uyarı"],
];

const BOS_MOD = TOKENLAR.reduce((a, [k]) => ({ ...a, [k]: "#888888" }), {});

/** Renk seçici satırı */
function RenkSatiri({ token, label, deger, onChange }) {
  return (
    <div className="flex items-center gap-2">
      <input type="color" value={deger || "#888888"} onChange={(e) => onChange(token, e.target.value)}
             className="w-8 h-8 rounded border border-gray-200 cursor-pointer p-0" />
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-gray-600 truncate">{label}</div>
        <Input value={deger || ""} onChange={(e) => onChange(token, e.target.value)} className="h-6 text-[11px] px-1" />
      </div>
    </div>
  );
}

/**
 * TemaFormu — tema ekle/düzenle. light + dark sekmeleri, renk pickerlar, canlı önizleme.
 * Props: tema (null=yeni), onKaydet(payload), onIptal()
 */
export default function TemaFormu({ tema, onKaydet, onIptal }) {
  const yeni = !tema;
  const [f, setF] = useState(() => ({
    kod: tema?.kod || "",
    ad: tema?.ad || "",
    aciklama: tema?.aciklama || "",
    kategori: tema?.kategori || "ozel",
    hedef_rol: tema?.hedef_rol || "",
  }));
  const [modlar, setModlar] = useState(() => ({
    light: { ...BOS_MOD, ...(tema?.modlar?.light || {}) },
    dark: { ...BOS_MOD, ...(tema?.modlar?.dark || {}) },
  }));
  const [sekme, setSekme] = useState("light");

  const setAlan = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const setToken = (token, v) => setModlar((p) => ({ ...p, [sekme]: { ...p[sekme], [token]: v } }));

  const kaydet = () => {
    if (!f.kod.trim() || !f.ad.trim()) return;
    onKaydet({
      kod: f.kod.trim(), ad: f.ad.trim(), aciklama: f.aciklama,
      kategori: f.kategori, hedef_rol: f.hedef_rol || null, modlar,
    });
  };

  const p = modlar[sekme];
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <div><Label className="text-[10px]">Kod {yeni ? "*" : "(sabit)"}</Label>
          <Input value={f.kod} disabled={!yeni} onChange={(e) => setAlan("kod", e.target.value)} placeholder="deniz_koyu" /></div>
        <div><Label className="text-[10px]">Ad *</Label>
          <Input value={f.ad} onChange={(e) => setAlan("ad", e.target.value)} placeholder="Deniz Koyu" /></div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div><Label className="text-[10px]">Açıklama</Label>
          <Input value={f.aciklama} onChange={(e) => setAlan("aciklama", e.target.value)} /></div>
        <div><Label className="text-[10px]">Hedef rol (ops.)</Label>
          <Input value={f.hedef_rol} onChange={(e) => setAlan("hedef_rol", e.target.value)} placeholder="student / boş" /></div>
      </div>

      {/* light / dark sekmeleri */}
      <div className="flex gap-1 border-b">
        {["light", "dark"].map((m) => (
          <button key={m} onClick={() => setSekme(m)}
            className={`px-3 py-1 text-xs font-medium ${sekme === m ? "border-b-2 border-blue-500 text-blue-600" : "text-gray-500"}`}>
            {m === "light" ? "☀️ Açık" : "🌙 Koyu"}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 max-h-64 overflow-y-auto pr-1">
        {TOKENLAR.map(([token, label]) => (
          <RenkSatiri key={token} token={token} label={label} deger={p[token]} onChange={setToken} />
        ))}
      </div>

      {/* Canlı önizleme */}
      <div className="rounded-lg p-3 border" style={{ backgroundColor: p.background, color: p.text, borderColor: p.border }}>
        <div className="text-xs mb-2" style={{ color: p.text_secondary }}>Önizleme ({sekme})</div>
        <div className="rounded-md p-2 mb-2" style={{ backgroundColor: p.surface, border: `1px solid ${p.border}` }}>
          <span style={{ color: p.text }}>Kart yüzeyi</span>
        </div>
        <div className="flex gap-2">
          <span className="px-2 py-1 rounded text-white text-xs" style={{ backgroundColor: p.primary }}>Birincil</span>
          <span className="px-2 py-1 rounded text-white text-xs" style={{ backgroundColor: p.success }}>Başarı</span>
          <span className="px-2 py-1 rounded text-white text-xs" style={{ backgroundColor: p.danger }}>Tehlike</span>
        </div>
      </div>

      <div className="flex gap-2">
        <Button onClick={kaydet} className="flex-1 bg-blue-600 text-white">💾 Kaydet</Button>
        <Button onClick={onIptal} variant="outline" className="flex-1">İptal</Button>
      </div>
    </div>
  );
}
