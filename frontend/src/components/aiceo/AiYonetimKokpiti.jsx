import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  LayoutDashboard, Activity, Cpu, GitBranch, Package, Search,
  RefreshCw, AlertTriangle, ChevronRight, ClipboardList, Bot, Gauge,
  MessageSquare, Workflow,
} from "lucide-react";

import AiCeo from "./AiCeo";
import KararZekasi from "./KararZekasi";
import AyazV1Panel from "./AyazV1Panel";
import AiSquadWorkspace from "./AiSquadWorkspace";
import AgentScorecardReal from "./AgentScorecardReal";
import DeployQueuePanel from "./DeployQueuePanel";
import Deniz from "./Deniz";
import PersonaSohbet from "./PersonaSohbet";
import AjanAkislari from "./AjanAkislari";

/**
 * AiYonetimKokpiti — FAZ 1 kabuğu.
 *
 * 7 bağımsız AI bileşenini (Ayda / Karar Zekâsı / Squad / Ayaz / Karne / Deploy / Deniz) TEK
 * kokpitin içinden açılan "detay görünümleri" olarak toplar. Üstte tek durum şeridi (gerçek veri),
 * altında "Bugün Ne Yapmalıyım" öncelik kuyruğu + "Yaşam Döngüsü Zinciri" (Öneri→Karar→Üretim→
 * Ayaz→Deploy→Denetim→Skor, kaynak_oneri_id korelasyonuyla).
 *
 * DÜRÜSTLÜK: tüm sayılar canlı uçlardan; veri yoksa "—" (uydurma yok). Denetim/Skor alt sistemleri
 * agregat çalıştığı için zincir kartında "sistem geneli" olarak işaretlenir.
 */

// Sol menü / detay görünüm kaydı. `key` backend hedef_gorunum ile eşleşir.
const GORUNUMLER = [
  { key: "kokpit", ad: "Kokpit", ikon: LayoutDashboard },
  { key: "ayda", ad: "Ayda — CEO", ikon: Activity },
  { key: "karar", ad: "Karar Zekâsı", ikon: ClipboardList },
  { key: "squad", ad: "AI Squad", ikon: Cpu },
  { key: "ayaz", ad: "Ayaz — Kod Asistanı", ikon: Bot },
  { key: "karne", ad: "Ajan Karnesi", ikon: Gauge },
  { key: "deploy", ad: "Deploy Kuyruğu", ikon: Package },
  { key: "deniz", ad: "Denetim — Deniz", ikon: Search },
  { key: "sohbet", ad: "Persona Sohbeti", ikon: MessageSquare },
  { key: "akislar", ad: "Nasıl Çalışıyor?", ikon: Workflow },
];

// Öncelik kuyruğu kaynak rozetleri
const KAYNAK_ROZET = {
  ayda: { l: "Ayda", c: "bg-indigo-100 text-indigo-700" },
  deniz: { l: "Deniz", c: "bg-rose-100 text-rose-700" },
  squad: { l: "Squad", c: "bg-amber-100 text-amber-700" },
  deploy: { l: "Deploy", c: "bg-cyan-100 text-cyan-700" },
};

// Zincir aşama tanımı: etiket + hangi görünüme götürür + agregat mı (sistem geneli)
const ZINCIR_ASAMALARI = [
  { key: "oneri", ad: "Öneri", gorunum: "ayda" },
  { key: "karar", ad: "Karar", gorunum: "karar" },
  { key: "uretim", ad: "Üretim", gorunum: "squad" },
  { key: "ayaz", ad: "Kod İncelemesi", gorunum: "ayaz", turetilmis: "deploy" },
  { key: "deploy", ad: "Deploy", gorunum: "deploy" },
  { key: "denetim", ad: "Denetim", gorunum: "deniz", global: true },
  { key: "skor", ad: "Skor", gorunum: "karne", global: true },
];

function StatTile({ etiket, deger, alt, renk, onClick }) {
  return (
    <button onClick={onClick}
      className="text-left rounded-xl border border-line bg-surface p-3 hover:border-primary/50 transition-colors">
      <div className="text-[10px] text-subtle uppercase font-semibold">{etiket}</div>
      <div className={`text-2xl font-bold tabular-nums ${renk || "text-content"}`}>{deger}</div>
      {alt && <div className="text-[11px] text-subtle mt-0.5">{alt}</div>}
    </button>
  );
}

export default function AiYonetimKokpiti({ apiBase, user, onNavigate, baslangicGorunum }) {
  const api = (p) => `${apiBase}${p}`;
  const [gorunum, setGorunum] = useState(baslangicGorunum || "kokpit");
  const [odak, setOdak] = useState(null); // tıklanan kaydın id'si (detayda odak ipucu)
  const [ozet, setOzet] = useState(null);
  const [oncelik, setOncelik] = useState(null);
  const [zincir, setZincir] = useState(null);
  const [yuk, setYuk] = useState(false);

  // Dış path'ten (ai-deniz gibi) gelen başlangıç görünümünü uygula (geriye dönük uyum)
  useEffect(() => { if (baslangicGorunum) setGorunum(baslangicGorunum); }, [baslangicGorunum]);

  const kokpitYukle = useCallback(async () => {
    setYuk(true);
    try {
      const [o, p, z] = await Promise.all([
        axios.get(api("/ai/ceo/kokpit/ozet")).then(r => r.data).catch(() => null),
        axios.get(api("/ai/ceo/kokpit/oncelik")).then(r => r.data).catch(() => null),
        axios.get(api("/ai/ceo/kokpit/zincir")).then(r => r.data).catch(() => null),
      ]);
      setOzet(o); setOncelik(p); setZincir(z);
    } finally { setYuk(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase]);

  useEffect(() => { if (gorunum === "kokpit") kokpitYukle(); }, [gorunum, kokpitYukle]);

  // Detay görünümüne git (opsiyonel kayıt odağı ile)
  const gitDetay = (hedefGorunum, kayitId) => { setOdak(kayitId || null); setGorunum(hedefGorunum); };

  // Detay bileşenini seç
  const detayBilesen = () => {
    switch (gorunum) {
      case "ayda": return <AiCeo apiBase={apiBase} />;
      case "karar": return <KararZekasi apiBase={apiBase} user={user} />;
      case "squad": return <AiSquadWorkspace apiBase={apiBase} />;
      case "ayaz": return <AyazV1Panel apiBase={apiBase} user={user} />;
      case "karne": return <AgentScorecardReal apiBase={apiBase} />;
      case "deploy": return <DeployQueuePanel apiBase={apiBase} user={user} />;
      case "deniz": return <Deniz apiBase={apiBase} onNavigate={onNavigate} />;
      case "sohbet": return <PersonaSohbet apiBase={apiBase} user={user} />;
      case "akislar": return <AjanAkislari />;
      default: return null;
    }
  };

  const s = ozet || {};
  const deniz = s.deniz || {};

  return (
    <div className="flex flex-col lg:flex-row gap-4">
      {/* Sol menü */}
      <nav className="lg:w-52 shrink-0 flex lg:flex-col gap-1 overflow-x-auto rounded-2xl border border-line bg-surface p-2">
        {GORUNUMLER.map(g => {
          const Icon = g.ikon;
          const aktif = gorunum === g.key;
          return (
            <button key={g.key} onClick={() => { setOdak(null); setGorunum(g.key); }}
              className={"flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all " +
                (aktif ? "bg-primary text-white shadow-sm" : "text-subtle hover:bg-app")}>
              <Icon className="h-4 w-4 shrink-0" />{g.ad}
            </button>
          );
        })}
      </nav>

      {/* Ana alan */}
      <div className="flex-1 min-w-0">
        {gorunum === "kokpit" ? (
          <div className="space-y-4">
            {/* Başlık + yenile */}
            <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <LayoutDashboard className="h-5 w-5 text-primary" />
                <div>
                  <div className="font-semibold text-content">AI Yönetim Kokpiti</div>
                  <div className="text-xs text-subtle">Tüm AI ekibi tek bakışta — gerçek veriden, uydurma yok.</div>
                </div>
              </div>
              <button onClick={kokpitYukle} disabled={yuk}
                className="inline-flex items-center gap-1.5 bg-app border border-line rounded-lg px-3 py-1.5 text-sm">
                <RefreshCw className={`h-4 w-4 ${yuk ? "animate-spin" : ""}`} />Yenile
              </button>
            </div>

            {/* Durum şeridi */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
              <StatTile etiket="Ayda Sağlık" onClick={() => gitDetay("ayda")}
                deger={s.ayda_saglik != null ? `%${s.ayda_saglik}` : "—"}
                alt="sistem sağlık skoru" renk="text-emerald-600" />
              <StatTile etiket="Denetim (açık)" onClick={() => gitDetay("deniz")}
                deger={deniz.acik_bulgu != null ? deniz.acik_bulgu : "—"}
                alt={`${deniz.kritik_bulgu || 0} kritik/yüksek`} renk="text-rose-600" />
              <StatTile etiket="Squad Aktif" onClick={() => gitDetay("squad")}
                deger={s.squad_aktif_pipeline != null ? s.squad_aktif_pipeline : "—"}
                alt="çalışan pipeline" renk="text-indigo-600" />
              <StatTile etiket="Deploy Bekleyen" onClick={() => gitDetay("deploy")}
                deger={s.deploy_bekleyen != null ? s.deploy_bekleyen : "—"}
                alt="entegrasyon kuyruğu" renk="text-cyan-600" />
              <StatTile etiket="Kritik Ajan" onClick={() => gitDetay("karne")}
                deger={s.kritik_risk_ajan != null ? `${s.kritik_risk_ajan}/${s.ajan_sayisi || 0}` : "—"}
                alt="risk: kritik" renk="text-amber-600" />
            </div>

            {/* Bugün Ne Yapmalıyım — öncelik kuyruğu (ilk görülen) */}
            <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                <div className="font-semibold text-content">Bugün Ne Yapmalıyım</div>
                <span className="text-xs text-subtle">({oncelik?.toplam ?? 0} aksiyon — önem sırasına göre)</span>
              </div>
              {!oncelik ? <div className="text-sm text-subtle">Yükleniyor…</div>
                : oncelik.toplam === 0 ? <div className="text-sm text-subtle">Bekleyen kritik aksiyon yok. 🎉</div>
                : (
                  <ul className="space-y-1.5">
                    {oncelik.ogeler.slice(0, 20).map((o, i) => {
                      const rz = KAYNAK_ROZET[o.kaynak] || { l: o.kaynak, c: "bg-slate-200 text-slate-600" };
                      return (
                        <li key={`${o.kaynak}-${o.id}-${i}`}>
                          <button onClick={() => gitDetay(o.hedef_gorunum, o.id)}
                            className="w-full text-left flex items-center gap-3 rounded-lg border border-line bg-app px-3 py-2 hover:border-primary/50 transition-colors">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold shrink-0 ${rz.c}`}>{rz.l}</span>
                            <div className="min-w-0 flex-1">
                              <div className="text-sm font-medium text-content truncate">{o.baslik}</div>
                              <div className="text-[11px] text-subtle truncate">{o.aciklama}</div>
                            </div>
                            {o.yas_gun != null && <span className="text-[11px] text-subtle tabular-nums shrink-0">{o.yas_gun}g</span>}
                            <span className="text-[10px] text-subtle tabular-nums shrink-0 w-8 text-right">{o.oncelik_puani}</span>
                            <ChevronRight className="h-4 w-4 text-subtle shrink-0" />
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
            </div>

            {/* Yaşam Döngüsü Zinciri */}
            <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
              <div className="flex items-center gap-2 mb-1">
                <GitBranch className="h-4 w-4 text-primary" />
                <div className="font-semibold text-content">Yaşam Döngüsü Zinciri</div>
              </div>
              <div className="text-[11px] text-subtle mb-3">
                Öneri → Karar → Üretim → Kod İncelemesi → Deploy → Denetim → Skor.
                {zincir?.not ? ` ${zincir.not}` : ""}
              </div>
              {!zincir ? <div className="text-sm text-subtle">Yükleniyor…</div>
                : zincir.sayi === 0 ? <div className="text-sm text-subtle">Henüz zincir kaydı yok (bir karar dosyası üretildiğinde belirir).</div>
                : (
                  <div className="space-y-3">
                    {zincir.zincirler.map((z, zi) => (
                      <div key={z.karar?.id || zi} className="rounded-xl border border-line bg-app p-2 overflow-x-auto">
                        <div className="flex items-center gap-1 min-w-max">
                          {ZINCIR_ASAMALARI.map((asama, ai) => {
                            const veri = asama.turetilmis ? z[asama.turetilmis] : z[asama.key];
                            const dolu = asama.global ? true : !!(veri && veri.var);
                            const durum = veri?.durum;
                            return (
                              <React.Fragment key={asama.key}>
                                {ai > 0 && <ChevronRight className="h-3.5 w-3.5 text-subtle shrink-0" />}
                                <button onClick={() => gitDetay(asama.gorunum, veri?.id)}
                                  className={"shrink-0 rounded-lg border px-2.5 py-1.5 text-left transition-colors " +
                                    (dolu ? "border-primary/40 bg-surface hover:border-primary"
                                          : "border-dashed border-line bg-transparent opacity-60")}>
                                  <div className="text-[10px] uppercase font-semibold text-subtle flex items-center gap-1">
                                    {asama.ad}{asama.global && <span className="text-[8px] px-1 rounded bg-slate-200 text-slate-500">sistem</span>}
                                  </div>
                                  <div className="text-[11px] text-content max-w-[130px] truncate">
                                    {asama.global ? "genel durum" : (dolu ? (durum || "kayıt var") : "—")}
                                  </div>
                                </button>
                              </React.Fragment>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Detay üst çubuğu: geri + odak ipucu */}
            <div className="flex items-center gap-2 flex-wrap">
              <button onClick={() => { setOdak(null); setGorunum("kokpit"); }}
                className="inline-flex items-center gap-1.5 text-sm text-subtle hover:text-content">
                <LayoutDashboard className="h-4 w-4" />Kokpite dön
              </button>
              {odak && (
                <span className="text-[11px] px-2 py-0.5 rounded bg-app border border-line text-subtle">
                  Odak kaydı: <span className="font-mono text-content">{String(odak).slice(0, 24)}</span>
                </span>
              )}
            </div>
            {detayBilesen()}
          </div>
        )}
      </div>
    </div>
  );
}
