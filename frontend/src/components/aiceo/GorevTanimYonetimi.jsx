import React, { useEffect, useState } from "react";
import axios from "axios";
import { Plus, Trash2, Save, ArrowUp, ArrowDown } from "lucide-react";

/**
 * GorevTanimYonetimi — admin, Ayarlar'dan görev listelerini yönetir (D2 + E2):
 * ekle/çıkar/sırala/aktiflik/XP-puan + HEDEF seçimi (sabit switch değil). İki liste:
 * öğretmen deneyim görevleri + yönetici kurulum görevleri.
 */
const LISTELER = [
  {
    ad: "Öğretmen Deneyim Görevleri", uc: "/ai/ceo/deneyim/tanimlar", puanKey: "xp", puanEtiket: "XP",
    hedefler: [["ogrencilerim", "Öğrencilerim"], ["profilim", "Profilim"], ["program", "Program"],
    ["giris-analizi", "Analiz"], ["gorevler", "Görevler"], ["kocum-miran", "Danışmanım Miran"],
    ["gelisim", "Gelişim"], ["mesajlar", "Mesajlar"], ["sss", "SSS/Yardım"], ["dashboard", "Dashboard"]],
  },
  {
    ad: "Yönetici Kurulum Görevleri", uc: "/ai/ceo/yonetici-adimlar/tanimlar", puanKey: "puan", puanEtiket: "Puan",
    hedefler: [["payments", "Muhasebe"], ["ai-ceo", "AI CEO"], ["ai-deniz", "Denetim (Deniz)"],
    ["ayarlar", "Sistem Ayarları"], ["sss-yonetimi", "SSS Yönetimi"], ["dashboard", "Dashboard"], ["moduller", "Modüller"]],
  },
];

function ListeEditor({ apiBase, cfg }) {
  const [gorevler, setGorevler] = useState(null);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [mesaj, setMesaj] = useState("");
  const api = (x) => `${apiBase}${x}`;

  useEffect(() => { axios.get(api(cfg.uc)).then(r => setGorevler(r.data.gorevler || [])).catch(() => setGorevler([])); }, [apiBase]);

  const guncelle = (i, alan, deger) => setGorevler(gs => gs.map((g, k) => k === i ? { ...g, [alan]: deger } : g));
  const sil = (i) => setGorevler(gs => gs.filter((_, k) => k !== i));
  const tasi = (i, yon) => setGorevler(gs => {
    const j = i + yon; if (j < 0 || j >= gs.length) return gs;
    const c = [...gs];[c[i], c[j]] = [c[j], c[i]];
    return c.map((g, k) => ({ ...g, sira: k + 1 }));
  });
  const ekle = () => setGorevler(gs => [...gs, { id: `gorev_${Date.now()}`, baslik: "Yeni görev", aciklama: "", [cfg.puanKey]: 10, sira: gs.length + 1, aktif: true, hedef: cfg.hedefler[0][0] }]);
  const kaydet = async () => {
    setKaydediliyor(true); setMesaj("");
    try { await axios.put(api(cfg.uc), { gorevler: gorevler.map((g, k) => ({ ...g, sira: k + 1 })) }); setMesaj("Kaydedildi ✓"); }
    catch (e) { setMesaj("Kaydedilemedi"); } finally { setKaydediliyor(false); setTimeout(() => setMesaj(""), 2500); }
  };

  if (!gorevler) return <div className="text-sm text-subtle">Yükleniyor…</div>;
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold text-content text-sm">{cfg.ad}</h3>
        <div className="flex items-center gap-2">
          {mesaj && <span className="text-xs text-emerald-600">{mesaj}</span>}
          <button onClick={ekle} className="inline-flex items-center gap-1 text-xs bg-app border border-line rounded-lg px-2 py-1 hover:bg-surface"><Plus className="h-3.5 w-3.5" />Görev ekle</button>
          <button onClick={kaydet} disabled={kaydediliyor} className="inline-flex items-center gap-1 text-xs bg-indigo-600 text-white rounded-lg px-3 py-1 disabled:opacity-60"><Save className="h-3.5 w-3.5" />Kaydet</button>
        </div>
      </div>
      <div className="space-y-2">
        {gorevler.map((g, i) => (
          <div key={g.id || i} className="rounded-lg border border-line p-2 grid grid-cols-1 md:grid-cols-12 gap-2 items-center">
            <input value={g.baslik || ""} onChange={e => guncelle(i, "baslik", e.target.value)} placeholder="Başlık" className="md:col-span-3 px-2 py-1 rounded border border-line text-sm" />
            <input value={g.aciklama || ""} onChange={e => guncelle(i, "aciklama", e.target.value)} placeholder="Açıklama" className="md:col-span-4 px-2 py-1 rounded border border-line text-xs" />
            <select value={g.hedef || ""} onChange={e => guncelle(i, "hedef", e.target.value)} className="md:col-span-2 px-2 py-1 rounded border border-line text-xs">
              {cfg.hedefler.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <input type="number" value={g[cfg.puanKey] ?? 0} onChange={e => guncelle(i, cfg.puanKey, parseInt(e.target.value) || 0)} title={cfg.puanEtiket} className="md:col-span-1 px-2 py-1 rounded border border-line text-xs" />
            <div className="md:col-span-2 flex items-center gap-1 justify-end">
              <label className="text-[11px] flex items-center gap-1"><input type="checkbox" checked={g.aktif !== false} onChange={e => guncelle(i, "aktif", e.target.checked)} />aktif</label>
              <button onClick={() => tasi(i, -1)} className="text-slate-400 hover:text-slate-600"><ArrowUp className="h-3.5 w-3.5" /></button>
              <button onClick={() => tasi(i, 1)} className="text-slate-400 hover:text-slate-600"><ArrowDown className="h-3.5 w-3.5" /></button>
              <button onClick={() => sil(i)} className="text-red-500 hover:text-red-700"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          </div>
        ))}
        {gorevler.length === 0 && <div className="text-sm text-subtle text-center py-3">Görev yok — "Görev ekle" ile başla.</div>}
      </div>
    </div>
  );
}

export default function GorevTanimYonetimi({ apiBase }) {
  return (
    <div className="space-y-4">
      <div className="text-sm text-subtle">Keşif yolu / Sıradaki Adımlar görevlerini buradan yönetin. <b>Hedef</b>, görev tıklanınca gidilecek ekranı belirler.</div>
      {LISTELER.map(cfg => <ListeEditor key={cfg.uc} apiBase={apiBase} cfg={cfg} />)}
    </div>
  );
}
