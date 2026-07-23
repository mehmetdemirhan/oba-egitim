import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
import axios from "axios";
import { Send, Archive, ArchiveRestore, Inbox, PenSquare, ArrowLeft, Search, CornerUpLeft,
  Star, Clock, Paperclip, X, FileText, Image as ImageIcon, Download } from "lucide-react";

/**
 * MesajKutusu — Gmail tarzı iki panel: yıldızlama, erteleme (snooze)+hatırlatma, yanıtla
 * (aynı thread), dosya/görsel eki. SOL sade konuşma listesi; SAĞ okuma paneli + satır-içi
 * yanıt kutusu. Ekler auth'lu uçtan (Authorization header) blob olarak çekilir.
 *
 * Props: user; apiBase; aliciSecenekleri?; sabitAlici? {id, ad}.
 */
const ROL_LABEL = { admin: "Yönetici", coordinator: "Koordinatör", teacher: "Öğretmen", student: "Öğrenci", parent: "Veli", accountant: "Muhasebe" };
const IZINLI = ".jpg,.jpeg,.png,.gif,.pdf,.doc,.docx";

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
const ertelenmis = (m) => m.ertele_zaman && new Date(m.ertele_zaman) > new Date();   // gelecekte → gizli

// Ek görüntüleyici: auth'lu uçtan blob çekip önizler (img) / indirir (belge)
function EkGoster({ apiBase, ek, onBuyut }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let iptal = false, objurl = null;
    if (ek.tur === "gorsel") {
      axios.get(`${apiBase}/mesajlar/ek/${ek.dosya_id}`, { responseType: "blob" })
        .then((r) => { if (!iptal) { objurl = URL.createObjectURL(r.data); setUrl(objurl); } }).catch(() => {});
    }
    return () => { iptal = true; if (objurl) URL.revokeObjectURL(objurl); };
  }, [apiBase, ek.dosya_id, ek.tur]);
  const indir = async () => {
    try {
      const r = await axios.get(`${apiBase}/mesajlar/ek/${ek.dosya_id}`, { responseType: "blob" });
      const u = URL.createObjectURL(r.data); const a = document.createElement("a");
      a.href = u; a.download = ek.ad; a.click(); setTimeout(() => URL.revokeObjectURL(u), 1000);
    } catch {}
  };
  if (ek.tur === "gorsel") {
    return url ? (
      <button onClick={() => onBuyut(url)} className="block">
        <img src={url} alt={ek.ad} className="max-h-40 rounded-lg border border-line object-cover hover:opacity-90" />
      </button>
    ) : <div className="h-24 w-32 rounded-lg bg-app border border-line flex items-center justify-center text-subtle"><ImageIcon className="h-5 w-5" /></div>;
  }
  return (
    <button onClick={indir} className="inline-flex items-center gap-2 rounded-lg border border-line bg-app px-3 py-2 text-sm hover:border-primary">
      <FileText className="h-4 w-4 text-red-500" /><span className="max-w-[160px] truncate">{ek.ad}</span><Download className="h-3.5 w-3.5 text-subtle" />
    </button>
  );
}

export default function MesajKutusu({ user, apiBase, aliciSecenekleri, sabitAlici }) {
  const [mesajlar, setMesajlar] = useState([]);
  const [kullanicilar, setKullanicilar] = useState([]);
  const [gorunum, setGorunum] = useState("gelen");  // gelen | yildiz | ertele | giden | arsiv
  const [seciliId, setSeciliId] = useState(null);
  const [ara, setAra] = useState("");
  const [yaz, setYaz] = useState(false);
  const [alici, setAlici] = useState(sabitAlici?.id || "");
  const [form, setForm] = useState({ konu: "", icerik: "" });
  const [ekler, setEkler] = useState([]);              // compose ekleri
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [mobilDetay, setMobilDetay] = useState(false);
  const [yanit, setYanit] = useState("");              // satır-içi yanıt metni
  const [yanitEkler, setYanitEkler] = useState([]);
  const [erteleAcik, setErteleAcik] = useState(false);
  const [erteleDeger, setErteleDeger] = useState("");
  const [buyukResim, setBuyukResim] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(false);
  const dosyaRef = useRef(null);
  const yanitDosyaRef = useRef(null);

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

  const gelen = useMemo(() => mesajlar.filter((m) => m.alici_id === user.id && !m.arsiv && !ertelenmis(m)), [mesajlar, user.id]);
  const yildizli = useMemo(() => mesajlar.filter((m) => m.yildiz && (m.alici_id === user.id || m.gonderen_id === user.id)), [mesajlar, user.id]);
  const ertelenen = useMemo(() => mesajlar.filter((m) => m.alici_id === user.id && ertelenmis(m)), [mesajlar, user.id]);
  const arsiv = useMemo(() => mesajlar.filter((m) => m.alici_id === user.id && m.arsiv), [mesajlar, user.id]);
  const giden = useMemo(() => mesajlar.filter((m) => m.gonderen_id === user.id), [mesajlar, user.id]);
  const okunmamis = gelen.filter((m) => !m.okundu).length;

  const aktifListe = { gelen, yildiz: yildizli, ertele: ertelenen, giden, arsiv }[gorunum] || gelen;
  const filtreli = useMemo(() => {
    const q = ara.trim().toLocaleLowerCase("tr");
    // Zamanı gelmiş ertelemeler (bugün due olmuş) gelen kutusunda ÜSTTE
    const l = [...aktifListe].sort((a, b) => {
      if (gorunum === "gelen") {
        const ad = a.ertele_zaman ? 1 : 0, bd = b.ertele_zaman ? 1 : 0;
        if (ad !== bd) return bd - ad;   // ertelemesi dolan üstte
      }
      return new Date(b.tarih || 0) - new Date(a.tarih || 0);
    });
    if (!q) return l;
    return l.filter((m) => `${m.gonderen_ad || ""} ${m.alici_ad || ""} ${m.konu || ""} ${m.icerik || ""}`.toLocaleLowerCase("tr").includes(q));
  }, [aktifListe, ara, gorunum]);

  const secili = filtreli.find((m) => m.id === seciliId) || mesajlar.find((m) => m.id === seciliId) || null;

  const guncelle = (id, patch) => setMesajlar((ms) => ms.map((x) => x.id === id ? { ...x, ...patch } : x));

  const ac = async (m) => {
    setSeciliId(m.id); setMobilDetay(true); setErteleAcik(false); setYanit(""); setYanitEkler([]);
    if (gorunum !== "giden" && !m.okundu && m.alici_id === user.id) {
      try { await axios.put(`${apiBase}/mesajlar/${m.id}/okundu`); guncelle(m.id, { okundu: true }); } catch {}
    }
  };
  const arsivle = async (id, deger) => {
    try { await axios.put(`${apiBase}/mesajlar/${id}/arsiv`, { arsiv: deger }); guncelle(id, { arsiv: deger }); if (seciliId === id) { setSeciliId(null); setMobilDetay(false); } } catch {}
  };
  const yildizla = async (m) => {
    try { await axios.put(`${apiBase}/mesajlar/${m.id}/yildiz`, { yildiz: !m.yildiz }); guncelle(m.id, { yildiz: !m.yildiz }); } catch {}
  };
  const erteleKaydet = async (zaman) => {
    if (!secili) return;
    try { await axios.put(`${apiBase}/mesajlar/${secili.id}/ertele`, { ertele_zaman: zaman }); guncelle(secili.id, { ertele_zaman: zaman }); setErteleAcik(false); if (zaman) { setSeciliId(null); setMobilDetay(false); } } catch {}
  };
  // Hazır erteleme seçenekleri
  const erteleSecenek = (saatSonra) => { const d = new Date(); d.setHours(d.getHours() + saatSonra); return d.toISOString(); };

  const ekYukle = async (dosyalar, hedef) => {
    const set = hedef === "yanit" ? setYanitEkler : setEkler;
    setYukleniyor(true);
    for (const d of dosyalar) {
      const fd = new FormData(); fd.append("dosya", d);
      try { const r = await axios.post(`${apiBase}/mesajlar/ek-yukle`, fd, { headers: { "Content-Type": "multipart/form-data" } }); set((e) => [...e, r.data]); }
      catch (err) { alert(err?.response?.data?.detail || "Yükleme başarısız"); }
    }
    setYukleniyor(false);
  };

  const gonder = async (e) => {
    e.preventDefault();
    if (!alici || (!form.icerik.trim() && ekler.length === 0)) return;
    setGonderiliyor(true);
    try {
      await axios.post(`${apiBase}/mesajlar`, { alici_id: alici, konu: form.konu, icerik: form.icerik, ekler });
      setForm({ konu: "", icerik: "" }); setEkler([]); if (!sabitAlici) setAlici(""); setYaz(false); setGorunum("giden"); fetchAll();
    } catch {} finally { setGonderiliyor(false); }
  };
  const yanitGonder = async () => {
    if (!secili || (!yanit.trim() && yanitEkler.length === 0)) return;
    setGonderiliyor(true);
    try {
      // Yanıt aynı thread'e: alıcı = mesajın karşı tarafı; rol-görünen-ad backend'de korunur
      const hedef = secili.gonderen_id === user.id ? secili.alici_id : secili.gonderen_id;
      await axios.post(`${apiBase}/mesajlar`, { alici_id: hedef, konu: secili.konu ? (secili.konu.startsWith("Re:") ? secili.konu : `Re: ${secili.konu}`) : "", icerik: yanit, ekler: yanitEkler });
      setYanit(""); setYanitEkler([]); fetchAll();
    } catch {} finally { setGonderiliyor(false); }
  };

  const kisiAdi = (m) => gorunum === "giden" ? (m.alici_ad || aliciListesi.find((a) => a.id === m.alici_id)?.ad || "Alıcı")
    : (m.alici_id === user.id ? (m.gonderen_ad || "Gönderen") : (m.alici_ad || "Alıcı"));

  const gorunumler = [
    { v: "gelen", l: "Gelen", ikon: Inbox, badge: okunmamis },
    { v: "yildiz", l: "Yıldızlılar", ikon: Star, badge: 0 },
    { v: "ertele", l: "Ertelenenler", ikon: Clock, badge: ertelenen.length },
    { v: "giden", l: "Gönderilen", ikon: Send },
    { v: "arsiv", l: "Arşiv", ikon: Archive, badge: 0 },
  ];

  return (
    <div className="rounded-2xl border border-line bg-surface overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-line overflow-x-auto">
        <div className="flex gap-1">
          {gorunumler.map((g) => (
            <button key={g.v} onClick={() => { setGorunum(g.v); setSeciliId(null); setMobilDetay(false); }}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition ${gorunum === g.v ? "bg-primary/10 text-primary font-semibold" : "text-subtle hover:bg-app"}`}>
              <g.ikon className="h-4 w-4" />{g.l}
              {g.badge > 0 && <span className="text-[10px] bg-primary text-white rounded-full px-1.5 min-w-[16px] text-center">{g.badge}</span>}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="hidden sm:flex items-center gap-1.5 bg-app rounded-lg px-2 py-1.5 w-40">
            <Search className="h-3.5 w-3.5 text-subtle" />
            <input value={ara} onChange={(e) => setAra(e.target.value)} placeholder="Ara" className="bg-transparent outline-none text-sm w-full" />
          </div>
          <button onClick={() => { setYaz(true); setAlici(sabitAlici?.id || ""); setEkler([]); }} className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary-hover text-white rounded-lg px-3 py-1.5 text-sm font-semibold">
            <PenSquare className="h-4 w-4" /><span className="hidden sm:inline">Yeni</span>
          </button>
        </div>
      </div>

      <div className="flex" style={{ minHeight: 440 }}>
        {/* SOL liste */}
        <div className={`w-full md:w-80 border-r border-line overflow-y-auto ${mobilDetay ? "hidden md:block" : "block"}`} style={{ maxHeight: "72vh" }}>
          {filtreli.length === 0 ? (
            <div className="p-8 text-center text-sm text-subtle">Bu görünümde mesaj yok.</div>
          ) : filtreli.map((m) => {
            const yeni = gorunum !== "giden" && !m.okundu && m.alici_id === user.id;
            const ad = kisiAdi(m);
            const due = gorunum === "gelen" && m.ertele_zaman;   // ertelemesi dolan
            return (
              <button key={m.id} onClick={() => ac(m)}
                className={`w-full text-left flex gap-3 px-3 py-3 border-b border-line/50 transition ${seciliId === m.id ? "bg-primary/5" : "hover:bg-app"} ${due ? "border-l-2 border-l-amber-400" : ""}`}>
                <div className={`h-9 w-9 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 ${renkSec(ad)}`}>{basHarf(ad)}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    {m.yildiz && <Star className="h-3 w-3 text-amber-400 fill-amber-400 shrink-0" />}
                    <span className={`text-sm truncate ${yeni ? "font-bold text-content" : "text-content"}`}>{ad}</span>
                    <span className="ml-auto text-[11px] text-subtle shrink-0">{due ? "⏰" : ""}{zaman(m.tarih)}</span>
                  </div>
                  {m.konu && <div className={`text-xs truncate ${yeni ? "font-semibold text-content" : "text-subtle"}`}>{m.konu}</div>}
                  <div className="text-xs text-subtle truncate flex items-center gap-1">{(m.ekler || []).length > 0 && <Paperclip className="h-3 w-3 shrink-0" />}{(m.icerik || "").replace(/\s+/g, " ").slice(0, 55) || "(ek)"}</div>
                </div>
                {yeni && <span className="h-2 w-2 rounded-full bg-primary shrink-0 mt-1.5" />}
              </button>
            );
          })}
        </div>

        {/* SAĞ okuma paneli */}
        <div className={`flex-1 flex flex-col ${mobilDetay ? "flex" : "hidden md:flex"}`}>
          {secili ? (
            <>
              <div className="p-5 max-w-2xl flex-1 overflow-y-auto" style={{ maxHeight: "72vh" }}>
                <button onClick={() => { setMobilDetay(false); setSeciliId(null); }} className="md:hidden inline-flex items-center gap-1 text-sm text-subtle mb-3"><ArrowLeft className="h-4 w-4" />Geri</button>
                <div className="flex items-start gap-3 mb-4">
                  <div className={`h-11 w-11 rounded-full flex items-center justify-center text-lg font-semibold shrink-0 ${renkSec(kisiAdi(secili))}`}>{basHarf(kisiAdi(secili))}</div>
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold text-content">{kisiAdi(secili)}</div>
                    <div className="text-xs text-subtle">{new Date(secili.tarih).toLocaleString("tr-TR")}</div>
                  </div>
                  <div className="flex gap-1 relative">
                    <button onClick={() => yildizla(secili)} title="Yıldızla" className={`p-2 rounded-lg hover:bg-app ${secili.yildiz ? "text-amber-400" : "text-subtle"}`}><Star className={`h-4 w-4 ${secili.yildiz ? "fill-amber-400" : ""}`} /></button>
                    {secili.alici_id === user.id && <button onClick={() => setErteleAcik((v) => !v)} title="Ertele" className={`p-2 rounded-lg hover:bg-app ${secili.ertele_zaman ? "text-amber-500" : "text-subtle"}`}><Clock className="h-4 w-4" /></button>}
                    {gorunum !== "giden" && <button onClick={() => { setYanit(""); document.getElementById("yanit-kutu")?.focus(); }} title="Yanıtla" className="p-2 rounded-lg text-subtle hover:bg-app"><CornerUpLeft className="h-4 w-4" /></button>}
                    {secili.alici_id === user.id && (secili.arsiv
                      ? <button onClick={() => arsivle(secili.id, false)} title="Arşivden çıkar" className="p-2 rounded-lg text-subtle hover:bg-app"><ArchiveRestore className="h-4 w-4" /></button>
                      : <button onClick={() => arsivle(secili.id, true)} title="Arşivle" className="p-2 rounded-lg text-subtle hover:bg-app"><Archive className="h-4 w-4" /></button>)}
                    {erteleAcik && (
                      <div className="absolute right-0 top-11 z-20 bg-surface border border-line rounded-xl shadow-lg p-3 w-64" onClick={(e) => e.stopPropagation()}>
                        <div className="text-xs font-semibold text-content mb-2">Ertele</div>
                        <div className="grid grid-cols-2 gap-1.5 mb-2">
                          <button onClick={() => erteleKaydet(erteleSecenek(3))} className="text-xs bg-app rounded-lg py-1.5 hover:bg-primary/10">3 saat</button>
                          <button onClick={() => erteleKaydet(erteleSecenek(24))} className="text-xs bg-app rounded-lg py-1.5 hover:bg-primary/10">Yarın</button>
                          <button onClick={() => erteleKaydet(erteleSecenek(72))} className="text-xs bg-app rounded-lg py-1.5 hover:bg-primary/10">3 gün</button>
                          <button onClick={() => erteleKaydet(erteleSecenek(168))} className="text-xs bg-app rounded-lg py-1.5 hover:bg-primary/10">Gelecek hafta</button>
                        </div>
                        <input type="datetime-local" value={erteleDeger} onChange={(e) => setErteleDeger(e.target.value)} className="w-full text-xs border border-line rounded-lg px-2 py-1.5 mb-2" />
                        <div className="flex gap-1.5">
                          <button onClick={() => erteleDeger && erteleKaydet(new Date(erteleDeger).toISOString())} className="flex-1 text-xs bg-primary text-white rounded-lg py-1.5">Ertele</button>
                          {secili.ertele_zaman && <button onClick={() => erteleKaydet(null)} className="flex-1 text-xs border border-line rounded-lg py-1.5 text-red-600">İptal et</button>}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                {secili.ertele_zaman && <div className="text-[11px] text-amber-600 mb-2">⏰ Ertelendi: {new Date(secili.ertele_zaman).toLocaleString("tr-TR")}</div>}
                {secili.konu && <h3 className="text-lg font-bold text-content mb-3">{secili.konu}</h3>}
                <div className="text-[15px] leading-relaxed text-content whitespace-pre-wrap">{secili.icerik}</div>
                {(secili.ekler || []).length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {secili.ekler.map((ek) => <EkGoster key={ek.dosya_id} apiBase={apiBase} ek={ek} onBuyut={setBuyukResim} />)}
                  </div>
                )}
              </div>

              {/* Satır-içi yanıt kutusu */}
              {gorunum !== "giden" && (
                <div className="border-t border-line p-3 bg-app/40">
                  <div className="flex items-end gap-2">
                    <textarea id="yanit-kutu" value={yanit} onChange={(e) => setYanit(e.target.value)} rows={2}
                      placeholder={`${kisiAdi(secili)} kişisine yanıt yaz…`} className="flex-1 px-3 py-2 rounded-lg border border-line text-sm resize-none" />
                    <input ref={yanitDosyaRef} type="file" accept={IZINLI} multiple className="hidden" onChange={(e) => { ekYukle(Array.from(e.target.files), "yanit"); e.target.value = ""; }} />
                    <button onClick={() => yanitDosyaRef.current?.click()} title="Ek" className="p-2 rounded-lg border border-line text-subtle hover:text-content"><Paperclip className="h-4 w-4" /></button>
                    <button onClick={yanitGonder} disabled={gonderiliyor || (!yanit.trim() && yanitEkler.length === 0)} className="inline-flex items-center gap-1 bg-primary text-white rounded-lg px-3 py-2 text-sm font-semibold disabled:opacity-50"><Send className="h-4 w-4" /></button>
                  </div>
                  {yanitEkler.length > 0 && <div className="flex flex-wrap gap-1.5 mt-2">{yanitEkler.map((ek, i) => (<span key={i} className="inline-flex items-center gap-1 text-xs bg-surface border border-line rounded-lg px-2 py-1">{ek.tur === "gorsel" ? <ImageIcon className="h-3 w-3" /> : <FileText className="h-3 w-3" />}{ek.ad.slice(0, 20)}<button onClick={() => setYanitEkler((e) => e.filter((_, j) => j !== i))}><X className="h-3 w-3" /></button></span>))}</div>}
                </div>
              )}
            </>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-subtle p-8" style={{ minHeight: 440 }}>
              <Inbox className="h-10 w-10 mb-2 opacity-40" /><div className="text-sm">Okumak için soldan bir mesaj seçin.</div>
            </div>
          )}
        </div>
      </div>

      {/* Yeni mesaj */}
      {yaz && (
        <div className="fixed inset-0 z-[80] bg-black/40 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={() => setYaz(false)}>
          <form onSubmit={gonder} className="bg-surface w-full sm:max-w-lg sm:rounded-2xl rounded-t-2xl shadow-xl p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
            <div className="font-bold text-content">Yeni Mesaj</div>
            {sabitAlici ? <div className="text-sm text-subtle">Alıcı: <b className="text-content">{sabitAlici.ad}</b></div> : (
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
            <textarea value={form.icerik} onChange={(e) => setForm({ ...form, icerik: e.target.value })} placeholder="Mesajınız…" rows={6} className="w-full px-3 py-2 rounded-lg border border-line text-sm" />
            <input ref={dosyaRef} type="file" accept={IZINLI} multiple className="hidden" onChange={(e) => { ekYukle(Array.from(e.target.files), "yeni"); e.target.value = ""; }} />
            {ekler.length > 0 && <div className="flex flex-wrap gap-1.5">{ekler.map((ek, i) => (<span key={i} className="inline-flex items-center gap-1 text-xs bg-app border border-line rounded-lg px-2 py-1">{ek.tur === "gorsel" ? <ImageIcon className="h-3 w-3" /> : <FileText className="h-3 w-3" />}{ek.ad.slice(0, 22)}<button type="button" onClick={() => setEkler((e) => e.filter((_, j) => j !== i))}><X className="h-3 w-3" /></button></span>))}</div>}
            <div className="flex gap-2 justify-between items-center">
              <button type="button" onClick={() => dosyaRef.current?.click()} disabled={yukleniyor} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-line text-sm text-subtle hover:text-content"><Paperclip className="h-4 w-4" />{yukleniyor ? "Yükleniyor…" : "Ek ekle"}</button>
              <div className="flex gap-2">
                <button type="button" onClick={() => setYaz(false)} className="px-3 py-1.5 rounded-lg border border-line text-sm text-subtle">Vazgeç</button>
                <button type="submit" disabled={gonderiliyor || !alici || (!form.icerik.trim() && ekler.length === 0)} className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-50"><Send className="h-4 w-4" />{gonderiliyor ? "…" : "Gönder"}</button>
              </div>
            </div>
          </form>
        </div>
      )}

      {/* Görsel büyütme */}
      {buyukResim && (
        <div className="fixed inset-0 z-[90] bg-black/80 flex items-center justify-center p-4" onClick={() => setBuyukResim(null)}>
          <img src={buyukResim} alt="" className="max-h-[90vh] max-w-[90vw] rounded-lg" />
        </div>
      )}
    </div>
  );
}
