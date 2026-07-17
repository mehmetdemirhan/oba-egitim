import React, { useEffect, useState } from "react";
import axios from "axios";
import { ThumbsUp, ThumbsDown, Mail } from "lucide-react";
import { PersonaBalon, MiranAvatar, PERSONA_UI } from "./Personalar";

/**
 * KocumMiran — öğretmen panelinde koçluk kartı (sıcak ton). YALNIZ öğretmenin kendi
 * verisine dayalı koçluk + faydalı/faydasız geri bildirim + onaylı performans mektupları.
 * (Ayda burada HİÇ görünmez — persona sızıntısı yok.)
 */
export default function KocumMiran({ apiBase, onNavigate }) {
  const [miran, setMiran] = useState(null);
  const [mektuplar, setMektuplar] = useState([]);
  const [deneyim, setDeneyim] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [geriBildirim, setGeriBildirim] = useState(null);
  const p = PERSONA_UI.miran;
  const api = (x) => `${apiBase}${x}`;

  useEffect(() => {
    (async () => {
      try {
        const [m, l, d] = await Promise.all([
          axios.get(api("/ai/ceo/miran/benim")).catch(() => null),
          axios.get(api("/ai/ceo/mektuplarim")).catch(() => null),
          axios.get(api("/ai/ceo/deneyim/benim")).catch(() => null),
        ]);
        if (m) setMiran(m.data.miran);
        if (l) setMektuplar(l.data.mektuplar || []);
        if (d) setDeneyim(d.data.deneyim);
      } finally { setYukleniyor(false); }
    })();
  }, [apiBase]);

  const bildir = async (faydali) => {
    if (!miran) return;
    try { await axios.post(api(`/ai/ceo/miran/${miran.id}/geri-bildirim`), { faydali }); setGeriBildirim(faydali); } catch (e) { /* */ }
  };

  return (
    <div className="space-y-4 max-w-3xl">
      {/* Sistem-Deneyim Görevleri (XP'li keşif yolu) */}
      {deneyim && deneyim.toplam > 0 && (
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-bold text-content text-sm">🎯 Keşif Yolu <span className="text-xs text-subtle">({deneyim.biten}/{deneyim.toplam})</span></h3>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: p.renkAcik, color: p.renk }}>⭐ {deneyim.kazanilan_xp} XP</span>
          </div>
          <div className="h-2 bg-app rounded-full overflow-hidden mb-2"><div className="h-full rounded-full" style={{ width: `${deneyim.ilerleme_yuzde}%`, background: p.renk }} /></div>
          {deneyim.siradaki && (
            <button onClick={() => onNavigate && deneyim.siradaki.hedef && onNavigate(deneyim.siradaki.hedef)}
              className="w-full text-left rounded-xl p-3 mb-2 hover:ring-2 hover:ring-amber-200 transition" style={{ background: p.renkAcik + "55" }}>
              <div className="text-xs font-semibold flex items-center justify-between" style={{ color: p.renk }}>Sıradaki adımın hazır! ✨ {deneyim.siradaki.hedef && <span className="text-[11px]">→ git</span>}</div>
              <div className="text-sm font-medium text-content mt-0.5">{deneyim.siradaki.baslik}</div>
              <div className="text-xs text-subtle">{deneyim.siradaki.aciklama} · +{deneyim.siradaki.xp} XP</div>
            </button>
          )}
          <div className="space-y-1">
            {deneyim.gorevler.map(g => (
              <button key={g.id} onClick={() => onNavigate && g.hedef && onNavigate(g.hedef)}
                className={`w-full flex items-center gap-2 text-sm text-left rounded px-1 py-0.5 ${g.hedef ? "hover:bg-app" : ""}`}>
                <span className={g.tamamlandi ? "text-emerald-600" : "text-slate-300"}>{g.tamamlandi ? "✅" : "⬜"}</span>
                <span className={g.tamamlandi ? "text-subtle line-through" : "text-content"}>{g.baslik}</span>
                {g.hedef && <span className="text-[10px] text-indigo-500">↗</span>}
                <span className="ml-auto text-[11px] text-subtle">+{g.xp} XP</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-2xl border p-4 shadow-sm" style={{ borderColor: p.renkAcik, background: p.renkAcik + "40" }}>
        {yukleniyor ? <div className="text-sm text-subtle py-6 text-center">Miran koçluk notlarını hazırlıyor…</div> : miran ? (
          <>
            <PersonaBalon persona="miran" mesaj={miran.icerik?.selam} size={64} />
            <div className="mt-3 space-y-2">
              {(miran.icerik?.oneriler || []).map((o, i) => (
                <div key={i} className="rounded-xl bg-surface border border-line p-3">
                  <div className="font-semibold text-content text-sm">{o.baslik}</div>
                  <div className="text-sm text-subtle mt-0.5">{o.aciklama}</div>
                </div>
              ))}
            </div>
            {miran.icerik?.kapanis && <div className="mt-3 text-sm font-medium" style={{ color: p.renk }}>{miran.icerik.kapanis}</div>}
            <div className="mt-3 pt-3 border-t flex items-center gap-3" style={{ borderColor: p.renkAcik }}>
              <span className="text-xs text-subtle">Bu koçluk faydalı oldu mu?</span>
              <button onClick={() => bildir(true)} className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border ${geriBildirim === true ? "bg-emerald-100 text-emerald-700 border-emerald-200" : "border-line hover:bg-app"}`}><ThumbsUp className="h-3.5 w-3.5" />Faydalı</button>
              <button onClick={() => bildir(false)} className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border ${geriBildirim === false ? "bg-red-100 text-red-600 border-red-200" : "border-line hover:bg-app"}`}><ThumbsDown className="h-3.5 w-3.5" />Faydasız</button>
              {geriBildirim !== null && <span className="text-xs" style={{ color: p.renk }}>Teşekkürler! 🙌</span>}
            </div>
          </>
        ) : <div className="flex items-center gap-3"><MiranAvatar size={48} /><span className="text-sm text-subtle">Miran şu an koçluk üretemiyor. Birazdan tekrar dene.</span></div>}
      </div>

      {mektuplar.length > 0 && (
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
          <h3 className="font-bold text-content text-sm mb-2 flex items-center gap-1.5"><Mail className="h-4 w-4" style={{ color: p.renk }} />Yönetimden Mektuplar</h3>
          <div className="space-y-3">
            {mektuplar.map(m => (
              <div key={m.id} className="rounded-xl border border-line p-3 text-sm space-y-1">
                <div>{m.icerik?.selamlama}</div>
                <div className="text-content">{m.icerik?.guclu_yonler}</div>
                <div className="text-subtle">{m.icerik?.gelisim_alanlari}</div>
                <div className="font-medium" style={{ color: p.renk }}>{m.icerik?.kapanis}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
