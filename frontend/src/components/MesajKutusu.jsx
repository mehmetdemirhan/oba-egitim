import React, { useEffect, useState, useCallback, useMemo } from "react";
import axios from "axios";
import { Send, Archive, ArchiveRestore, Inbox, PenSquare, ArrowLeft, Search, CornerUpLeft } from "lucide-react";

/**
 * MesajKutusu — Gmail tarzı iki panelli mesaj kutusu (tüm rollerde ortak).
 * SOL: gönderen/konuşma listesi (sade, taranabilir; okunmamış = kalın + nokta).
 * SAĞ: seçili mesajın tam içeriği, rahat tipografi. Okununca "Arşivle" görünür;
 * arşivlenen gelen kutusundan kalkar, ayrı "Arşiv" görünümünden erişilir.
 *
 * Props: user; apiBase; aliciSecenekleri? [{id, ad, rol, rolLabel}] (yoksa /auth/users);
 *        sabitAlici? {id, ad} (öğrenci/veli gibi tek muhataplı roller için).
 */
const ROL_LABEL = { admin: "Yönetici", coordinator: "Koordinatör", teacher: "Öğretmen", student: "Öğrenci", parent: "Veli", accountant: "Muhasebe" };

function zaman(t) {
  if (!t) return "";
  try {
    const d = new Date(t); const now = new Date();
    const ayni = d.toDateString() === now.toDateString();
    return ayni ? d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
                : d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
  } catch { return ""; }
}
const basHarf = (ad) => (ad || "?").trim().charAt(0).toLocaleUpperCase("tr");
const AVATAR_RENK = ["bg-indigo-100 text-indigo-700", "bg-emerald-100 text-emerald-700", "bg-amber-100 text-amber-700", "bg-rose-100 text-rose-700", "bg-sky-100 text-sky-700", "bg-violet-100 text-violet-700"];
const renkSec = (s) => AVATAR_RENK[(s || "").split("").reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR_RENK.length];

export default function MesajKutusu({ user, apiBase, aliciSecenekleri, sabitAlici }) {
  const [mesajlar, setMesajlar] = useState([]);
  const [kullanicilar, setKullanicilar] = useState([]);
  const [gorunum, setGorunum] = useState("gelen");  // gelen | giden | arsiv
  const [seciliId, setSeciliId] = useState(null);
  const [ara, setAra] = useState("");
  const [yaz, setYaz] = useState(false);
  const [alici, setAlici] = useState(sabitAlici?.id || "");
  const [form, setForm] = useState({ konu: "", icerik: "" });
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [mobilDetay, setMobilDetay] = useState(false);

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${apiBase}/mesajlar`); setMesajlar(Array.isArray(r.data) ? r.data : []); } catch { setMesajlar([]); }
    if (!aliciSecenekleri && !sabitAlici) {
      try { const r = await axios.get(`${apiBase}/auth/users`); setKullanicilar(Array.isArray(r.data) ? r.data : []); } catch { setKullanicilar([]); }
    }
  }, [apiBase, aliciSecenekleri, sabitAlici]);
  useEffect(() => { fetchAll(); }, [fetchAll]);

  const aliciListesi = useMemo(() => aliciSecenekleri || kullanicilar.filter((u) => u.id !== user.id).map((u) => ({
    id: u.id, ad: `${u.ad || ""} ${u.soyad || ""}`.trim(), rol: u.role, rolLabel: ROL_LABEL[u.role] || u.role,
  })), [aliciSecenekleri, kullanicilar, user.id]);

  const gelen = useMemo(() => mesajlar.filter((m) => m.alici_id === user.id && !m.arsiv), [mesajlar, user.id]);
  const arsiv = useMemo(() => mesajlar.filter((m) => m.alici_id === user.id && m.arsiv), [mesajlar, user.id]);
  const giden = useMemo(() => mesajlar.filter((m) => m.gonderen_id === user.id), [mesajlar, user.id]);
  const okunmamis = gelen.filter((m) => !m.okundu).length;

  const aktifListe = gorunum === "gelen" ? gelen : gorunum === "arsiv" ? arsiv : giden;
  const filtreli = useMemo(() => {
    const q = ara.trim().toLocaleLowerCase("tr");
    const l = [...aktifListe].sort((a, b) => new Date(b.tarih || 0) - new Date(a.tarih || 0));
    if (!q) return l;
    return l.filter((m) => `${m.gonderen_ad || ""} ${m.alici_ad || ""} ${m.konu || ""} ${m.icerik || ""}`.toLocaleLowerCase("tr").includes(q));
  }, [aktifListe, ara]);

  const secili = filtreli.find((m) => m.id === seciliId) || null;

  const ac = async (m) => {
    setSeciliId(m.id); setMobilDetay(true);
    if (gorunum !== "giden" && !m.okundu) {
      try { await axios.put(`${apiBase}/mesajlar/${m.id}/okundu`); setMesajlar((ms) => ms.map((x) => x.id === m.id ? { ...x, okundu: true } : x)); } catch {}
    }
  };
  const arsivle = async (id, deger) => {
    try { await axios.put(`${apiBase}/mesajlar/${id}/arsiv`, { arsiv: deger }); setMesajlar((ms) => ms.map((x) => x.id === id ? { ...x, arsiv: deger } : x)); if (seciliId === id) { setSeciliId(null); setMobilDetay(false); } } catch {}
  };
  const gonder = async (e) => {
    e.preventDefault();
    if (!alici || !form.icerik.trim()) return;
    setGonderiliyor(true);
    try {
      await axios.post(`${apiBase}/mesajlar`, { alici_id: alici, konu: form.konu, icerik: form.icerik });
      setForm({ konu: "", icerik: "" }); if (!sabitAlici) setAlici(""); setYaz(false); setGorunum("giden"); fetchAll();
    } catch {} finally { setGonderiliyor(false); }
  };
  const yanitla = (m) => { setAlici(m.gonderen_id); setForm({ konu: m.konu ? `Re: ${m.konu}` : "", icerik: "" }); setYaz(true); };

  const kisiAdi = (m) => gorunum === "giden" ? (m.alici_ad || aliciListesi.find((a) => a.id === m.alici_id)?.ad || "Alıcı") : (m.gonderen_ad || "Gönderen");

  const gorunumler = [
    { v: "gelen", l: "Gelen", ikon: Inbox, badge: okunmamis },
    { v: "giden", l: "Gönderilen", ikon: Send },
    { v: "arsiv", l: "Arşiv", ikon: Archive, badge: 0 },
  ];

  return (
    <div className="rounded-2xl border border-line bg-surface overflow-hidden">
      {/* Üst şerit */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-line">
        <div className="flex gap-1">
          {gorunumler.map((g) => (
            <button key={g.v} onClick={() => { setGorunum(g.v); setSeciliId(null); setMobilDetay(false); }}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition ${gorunum === g.v ? "bg-primary/10 text-primary font-semibold" : "text-subtle hover:bg-app"}`}>
              <g.ikon className="h-4 w-4" />{g.l}
              {g.badge > 0 && <span className="text-[10px] bg-primary text-white rounded-full px-1.5 min-w-[16px] text-center">{g.badge}</span>}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="hidden sm:flex items-center gap-1.5 bg-app rounded-lg px-2 py-1.5 w-44">
            <Search className="h-3.5 w-3.5 text-subtle" />
            <input value={ara} onChange={(e) => setAra(e.target.value)} placeholder="Ara" className="bg-transparent outline-none text-sm w-full" />
          </div>
          <button onClick={() => { setYaz(true); setAlici(sabitAlici?.id || ""); }} className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white rounded-lg px-3 py-1.5 text-sm font-semibold">
            <PenSquare className="h-4 w-4" /><span className="hidden sm:inline">Yeni</span>
          </button>
        </div>
      </div>

      {/* İki panel */}
      <div className="flex" style={{ minHeight: 420 }}>
        {/* SOL: liste */}
        <div className={`w-full md:w-80 border-r border-line overflow-y-auto ${mobilDetay ? "hidden md:block" : "block"}`} style={{ maxHeight: "70vh" }}>
          {filtreli.length === 0 ? (
            <div className="p-8 text-center text-sm text-subtle">{gorunum === "arsiv" ? "Arşiv boş." : gorunum === "giden" ? "Gönderilmiş mesaj yok." : "Gelen kutusu boş."}</div>
          ) : filtreli.map((m) => {
            const okunmamis = gorunum !== "giden" && !m.okundu;
            const ad = kisiAdi(m);
            return (
              <button key={m.id} onClick={() => ac(m)}
                className={`w-full text-left flex gap-3 px-3 py-3 border-b border-line/50 transition ${seciliId === m.id ? "bg-primary/5" : "hover:bg-app"}`}>
                <div className={`h-9 w-9 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 ${renkSec(ad)}`}>{basHarf(ad)}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-sm truncate ${okunmamis ? "font-bold text-content" : "text-content"}`}>{ad}</span>
                    <span className="ml-auto text-[11px] text-subtle shrink-0">{zaman(m.tarih)}</span>
                  </div>
                  {m.konu && <div className={`text-xs truncate ${okunmamis ? "font-semibold text-content" : "text-subtle"}`}>{m.konu}</div>}
                  <div className="text-xs text-subtle truncate">{(m.icerik || "").replace(/\s+/g, " ").slice(0, 60)}</div>
                </div>
                {okunmamis && <span className="h-2 w-2 rounded-full bg-primary shrink-0 mt-1.5" />}
              </button>
            );
          })}
        </div>

        {/* SAĞ: okuma paneli */}
        <div className={`flex-1 ${mobilDetay ? "block" : "hidden md:block"}`}>
          {secili ? (
            <div className="p-5 max-w-2xl">
              <button onClick={() => { setMobilDetay(false); setSeciliId(null); }} className="md:hidden inline-flex items-center gap-1 text-sm text-subtle mb-3"><ArrowLeft className="h-4 w-4" />Geri</button>
              <div className="flex items-start gap-3 mb-4">
                <div className={`h-11 w-11 rounded-full flex items-center justify-center text-lg font-semibold shrink-0 ${renkSec(kisiAdi(secili))}`}>{basHarf(kisiAdi(secili))}</div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-content">{kisiAdi(secili)}</div>
                  <div className="text-xs text-subtle">{new Date(secili.tarih).toLocaleString("tr-TR")}</div>
                </div>
                <div className="flex gap-1">
                  {gorunum !== "giden" && <button onClick={() => yanitla(secili)} title="Yanıtla" className="p-2 rounded-lg text-subtle hover:bg-app"><CornerUpLeft className="h-4 w-4" /></button>}
                  {secili.alici_id === user.id && (
                    secili.arsiv
                      ? <button onClick={() => arsivle(secili.id, false)} title="Arşivden çıkar" className="p-2 rounded-lg text-subtle hover:bg-app"><ArchiveRestore className="h-4 w-4" /></button>
                      : <button onClick={() => arsivle(secili.id, true)} title="Arşivle" className="p-2 rounded-lg text-subtle hover:bg-app"><Archive className="h-4 w-4" /></button>
                  )}
                </div>
              </div>
              {secili.konu && <h3 className="text-lg font-bold text-content mb-3">{secili.konu}</h3>}
              <div className="text-[15px] leading-relaxed text-content whitespace-pre-wrap">{secili.icerik}</div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-subtle p-8" style={{ minHeight: 420 }}>
              <Inbox className="h-10 w-10 mb-2 opacity-40" />
              <div className="text-sm">Okumak için soldan bir mesaj seçin.</div>
            </div>
          )}
        </div>
      </div>

      {/* Yeni mesaj / yanıt (overlay) */}
      {yaz && (
        <div className="fixed inset-0 z-[80] bg-black/40 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={() => setYaz(false)}>
          <form onSubmit={gonder} className="bg-surface w-full sm:max-w-lg sm:rounded-2xl rounded-t-2xl shadow-xl p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
            <div className="font-bold text-content">Yeni Mesaj</div>
            {sabitAlici ? (
              <div className="text-sm text-subtle">Alıcı: <b className="text-content">{sabitAlici.ad}</b></div>
            ) : (
              <select value={alici} onChange={(e) => setAlici(e.target.value)} className="w-full px-3 py-2 rounded-lg border border-line text-sm">
                <option value="">Alıcı seçin…</option>
                {["admin", "coordinator", "teacher", "student", "parent", "accountant"].map((rol) => {
                  const grup = aliciListesi.filter((k) => k.rol === rol);
                  if (!grup.length) return null;
                  return <optgroup key={rol} label={ROL_LABEL[rol] || rol}>{grup.map((k) => <option key={k.id} value={k.id}>{k.ad}</option>)}</optgroup>;
                })}
              </select>
            )}
            <input value={form.konu} onChange={(e) => setForm({ ...form, konu: e.target.value })} placeholder="Konu" className="w-full px-3 py-2 rounded-lg border border-line text-sm" />
            <textarea value={form.icerik} onChange={(e) => setForm({ ...form, icerik: e.target.value })} required placeholder="Mesajınız…" rows={6} className="w-full px-3 py-2 rounded-lg border border-line text-sm" />
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setYaz(false)} className="px-3 py-1.5 rounded-lg border border-line text-sm text-subtle">Vazgeç</button>
              <button type="submit" disabled={gonderiliyor || !alici || !form.icerik.trim()} className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-50"><Send className="h-4 w-4" />{gonderiliyor ? "Gönderiliyor…" : "Gönder"}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
