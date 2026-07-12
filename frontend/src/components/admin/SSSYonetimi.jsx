import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { useToast } from "../../hooks/use-toast";
import { HelpCircle, RefreshCw, Send, Trash2, Plus, Check, X } from "lucide-react";

/**
 * SSSYonetimi — koordinatör + admin SSS yönetim paneli.
 * Cevap bekleyen sorular kuyruğu (yayınla / kişiye yanıtla / reddet) + yayın
 * kayıtları yönetimi (düzenle / sıra / rol-kategori / yayından kaldır / sil) +
 * doğrudan SSS ekleme. Props: apiBase, onBekleyenDegisti(sayi).
 */
const ROL_ETIKET = { teacher: "Öğretmen", parent: "Veli", student: "Öğrenci", herkes: "Herkes" };
const SECILEBILIR_ROLLER = ["herkes", "teacher", "parent", "student"];

const tarihStr = (t) => { try { return new Date(t).toLocaleString("tr-TR"); } catch { return t; } };
const inp = "border border-line rounded-lg px-2 py-1.5 text-sm bg-surface";

function RolSecici({ roller, onChange }) {
  const toggle = (r) => {
    if (r === "herkes") { onChange(["herkes"]); return; }
    let yeni = roller.filter((x) => x !== "herkes");
    yeni = yeni.includes(r) ? yeni.filter((x) => x !== r) : [...yeni, r];
    onChange(yeni.length ? yeni : ["herkes"]);
  };
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {SECILEBILIR_ROLLER.map((r) => (
        <label key={r} className="inline-flex items-center gap-1 text-xs cursor-pointer">
          <input type="checkbox" checked={roller.includes(r)} onChange={() => toggle(r)} />
          {ROL_ETIKET[r]}
        </label>
      ))}
    </div>
  );
}

export default function SSSYonetimi({ apiBase, onBekleyenDegisti }) {
  const { toast } = useToast();
  const [kategoriler, setKategoriler] = useState([]);
  const [bekleyen, setBekleyen] = useState([]);
  const [yayin, setYayin] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(false);

  const yukle = useCallback(async () => {
    setYukleniyor(true);
    try {
      const [bR, yR] = await Promise.all([
        axios.get(`${apiBase}/sss/bekleyen`),
        axios.get(`${apiBase}/sss/yonetim`),
      ]);
      const bek = bR.data?.kayitlar || [];
      setBekleyen(bek);
      setYayin(yR.data?.kayitlar || []);
      setKategoriler(yR.data?.kategoriler || []);
      if (onBekleyenDegisti) onBekleyenDegisti(bek.length);
    } catch {
      toast({ title: "SSS verileri yüklenemedi", variant: "destructive" });
    } finally {
      setYukleniyor(false);
    }
  }, [apiBase, toast, onBekleyenDegisti]);

  useEffect(() => { yukle(); }, [yukle]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-bold text-content inline-flex items-center gap-2">
            <HelpCircle className="h-6 w-6" />SSS Yönetimi
          </h2>
          <p className="text-sm text-subtle">Cevap bekleyen sorular ve yayındaki soru-cevaplar.</p>
        </div>
        <button onClick={yukle} className="inline-flex items-center gap-1 border border-line rounded-lg px-3 py-1.5 text-sm hover:bg-app">
          <RefreshCw className="h-4 w-4" />Yenile
        </button>
      </div>

      {/* Cevap bekleyen kuyruğu */}
      <section className="space-y-3">
        <h3 className="text-lg font-bold text-content">
          Cevap bekleyenler {bekleyen.length > 0 && <span className="ml-1 px-2 py-0.5 rounded-full bg-red-500 text-white text-xs font-bold">{bekleyen.length}</span>}
        </h3>
        {yukleniyor && <p className="text-subtle text-sm">Yükleniyor…</p>}
        {!yukleniyor && bekleyen.length === 0 && <p className="text-subtle text-sm">Bekleyen soru yok.</p>}
        <div className="space-y-3">
          {bekleyen.map((s) => (
            <BekleyenKart key={s.id} soru={s} apiBase={apiBase} kategoriler={kategoriler} onDone={yukle} />
          ))}
        </div>
      </section>

      {/* Doğrudan ekleme */}
      <DogrudanEkle apiBase={apiBase} kategoriler={kategoriler} onDone={yukle} />

      {/* Yayın kayıtları yönetimi */}
      <section className="space-y-3">
        <h3 className="text-lg font-bold text-content">Yayındaki SSS ({yayin.length})</h3>
        {yayin.length === 0 && <p className="text-subtle text-sm">Henüz yayın kaydı yok.</p>}
        <div className="space-y-2">
          {yayin.map((k) => (
            <YayinKart key={k.id} kayit={k} apiBase={apiBase} kategoriler={kategoriler} onDone={yukle} />
          ))}
        </div>
      </section>
    </div>
  );
}

// ── Bekleyen soru kartı ──
function BekleyenKart({ soru, apiBase, kategoriler, onDone }) {
  const { toast } = useToast();
  const [cevap, setCevap] = useState("");
  const [soruDuzenli, setSoruDuzenli] = useState(soru.soru || "");
  const [kategori, setKategori] = useState(soru.kategori || "Genel");
  const [roller, setRoller] = useState(["herkes"]);
  const [mesgul, setMesgul] = useState(false);

  const gonder = async (aksiyon) => {
    if ((aksiyon === "yayinla" || aksiyon === "kisisel") && !cevap.trim()) {
      toast({ title: "Cevap boş olamaz", variant: "destructive" }); return;
    }
    setMesgul(true);
    try {
      await axios.post(`${apiBase}/sss/bekleyen/${soru.id}/yanitla`, {
        aksiyon, cevap, soru_duzenli: soruDuzenli, kategori, roller,
      });
      const mesajlar = { yayinla: "Yayınlandı", kisisel: "Kişiye yanıtlandı", reddet: "Reddedildi" };
      toast({ title: mesajlar[aksiyon] || "Tamam" });
      onDone();
    } catch (e) {
      toast({ title: "İşlem başarısız", description: e?.response?.data?.detail, variant: "destructive" });
    } finally {
      setMesgul(false);
    }
  };

  return (
    <div className="bg-surface border border-line rounded-2xl shadow-sm p-4 space-y-3">
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <div className="text-sm">
          <span className="font-semibold text-content">{soru.soran_ad || "—"}</span>
          <span className="text-xs text-subtle ml-2">{ROL_ETIKET[soru.soran_rol] || soru.soran_rol}</span>
          <span className="text-xs text-subtle ml-2">· {soru.kategori}</span>
          <span className="text-xs text-subtle ml-2">· {tarihStr(soru.olusturma)}</span>
        </div>
      </div>
      <p className="text-content bg-app rounded-lg p-2 text-sm">{soru.soru}</p>

      <textarea value={cevap} onChange={(e) => setCevap(e.target.value)} rows={3}
                placeholder="Cevabınızı yazın…" className={`${inp} w-full`} />

      {/* Yayın seçenekleri */}
      <div className="border-t border-line pt-2 space-y-2">
        <p className="text-xs text-subtle font-medium">Yayınlarsan (soranın adı yayında görünmez):</p>
        <input type="text" value={soruDuzenli} onChange={(e) => setSoruDuzenli(e.target.value)}
               placeholder="Yayınlanacak soru metni (düzenlenebilir)" className={`${inp} w-full`} />
        <div className="flex items-center gap-3 flex-wrap">
          <select value={kategori} onChange={(e) => setKategori(e.target.value)} className={inp}>
            {kategoriler.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <RolSecici roller={roller} onChange={setRoller} />
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <button disabled={mesgul} onClick={() => gonder("yayinla")}
                className="inline-flex items-center gap-1 bg-emerald-600 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-emerald-700 disabled:opacity-50">
          <Send className="h-4 w-4" />Yayınla
        </button>
        <button disabled={mesgul} onClick={() => gonder("kisisel")}
                className="inline-flex items-center gap-1 border border-line rounded-lg px-3 py-1.5 text-sm hover:bg-app disabled:opacity-50">
          <Check className="h-4 w-4" />Sadece kişiye yanıtla
        </button>
        <button disabled={mesgul} onClick={() => gonder("reddet")}
                className="inline-flex items-center gap-1 text-red-600 border border-red-200 rounded-lg px-3 py-1.5 text-sm hover:bg-red-50 disabled:opacity-50">
          <X className="h-4 w-4" />Reddet
        </button>
      </div>
    </div>
  );
}

// ── Doğrudan SSS ekleme ──
function DogrudanEkle({ apiBase, kategoriler, onDone }) {
  const { toast } = useToast();
  const [acik, setAcik] = useState(false);
  const [soru, setSoru] = useState("");
  const [cevap, setCevap] = useState("");
  const [kategori, setKategori] = useState("Genel");
  const [roller, setRoller] = useState(["herkes"]);
  const [mesgul, setMesgul] = useState(false);

  const ekle = async () => {
    if (!soru.trim() || !cevap.trim()) { toast({ title: "Soru ve cevap gerekli", variant: "destructive" }); return; }
    setMesgul(true);
    try {
      await axios.post(`${apiBase}/sss`, { soru, cevap, kategori, roller });
      toast({ title: "SSS eklendi" });
      setSoru(""); setCevap(""); setRoller(["herkes"]); setAcik(false);
      onDone();
    } catch (e) {
      toast({ title: "Eklenemedi", description: e?.response?.data?.detail, variant: "destructive" });
    } finally {
      setMesgul(false);
    }
  };

  if (!acik) {
    return (
      <button onClick={() => setAcik(true)} className="inline-flex items-center gap-1 border border-dashed border-line rounded-lg px-3 py-2 text-sm text-subtle hover:bg-app">
        <Plus className="h-4 w-4" />Doğrudan SSS ekle
      </button>
    );
  }
  return (
    <div className="bg-surface border border-line rounded-2xl shadow-sm p-4 space-y-2">
      <h3 className="text-sm font-bold text-content">Doğrudan SSS ekle</h3>
      <input type="text" value={soru} onChange={(e) => setSoru(e.target.value)} placeholder="Soru" className={`${inp} w-full`} />
      <textarea value={cevap} onChange={(e) => setCevap(e.target.value)} rows={3} placeholder="Cevap" className={`${inp} w-full`} />
      <div className="flex items-center gap-3 flex-wrap">
        <select value={kategori} onChange={(e) => setKategori(e.target.value)} className={inp}>
          {kategoriler.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <RolSecici roller={roller} onChange={setRoller} />
      </div>
      <div className="flex items-center gap-2">
        <button disabled={mesgul} onClick={ekle} className="bg-indigo-600 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-indigo-700 disabled:opacity-50">Ekle</button>
        <button onClick={() => setAcik(false)} className="border border-line rounded-lg px-3 py-1.5 text-sm hover:bg-app">Vazgeç</button>
      </div>
    </div>
  );
}

// ── Yayın kaydı yönetim kartı ──
function YayinKart({ kayit, apiBase, kategoriler, onDone }) {
  const { toast } = useToast();
  const [duzenle, setDuzenle] = useState(false);
  const [d, setD] = useState({
    soru: kayit.soru || "", cevap: kayit.cevap || "", kategori: kayit.kategori || "Genel",
    roller: kayit.roller || ["herkes"], sira: kayit.sira ?? 0, aktif: kayit.aktif !== false,
  });

  const kaydet = async () => {
    try {
      await axios.put(`${apiBase}/sss/${kayit.id}`, d);
      toast({ title: "Güncellendi" });
      setDuzenle(false); onDone();
    } catch (e) {
      toast({ title: "Güncellenemedi", description: e?.response?.data?.detail, variant: "destructive" });
    }
  };

  const aktifToggle = async () => {
    try {
      await axios.put(`${apiBase}/sss/${kayit.id}`, { aktif: !(kayit.aktif !== false) });
      onDone();
    } catch { toast({ title: "İşlem başarısız", variant: "destructive" }); }
  };

  const sil = async () => {
    try {
      await axios.delete(`${apiBase}/sss/${kayit.id}`);
      toast({ title: "Silindi" }); onDone();
    } catch { toast({ title: "Silinemedi", variant: "destructive" }); }
  };

  const siraDegis = async (yon) => {
    try {
      await axios.put(`${apiBase}/sss/${kayit.id}`, { sira: (kayit.sira ?? 0) + yon });
      onDone();
    } catch { /* yut */ }
  };

  if (duzenle) {
    return (
      <div className="bg-surface border border-indigo-200 rounded-2xl shadow-sm p-4 space-y-2">
        <input type="text" value={d.soru} onChange={(e) => setD({ ...d, soru: e.target.value })} className={`${inp} w-full`} />
        <textarea value={d.cevap} onChange={(e) => setD({ ...d, cevap: e.target.value })} rows={3} className={`${inp} w-full`} />
        <div className="flex items-center gap-3 flex-wrap">
          <select value={d.kategori} onChange={(e) => setD({ ...d, kategori: e.target.value })} className={inp}>
            {kategoriler.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <RolSecici roller={d.roller} onChange={(r) => setD({ ...d, roller: r })} />
          <label className="inline-flex items-center gap-1 text-xs">
            <input type="checkbox" checked={d.aktif} onChange={(e) => setD({ ...d, aktif: e.target.checked })} />Yayında
          </label>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={kaydet} className="bg-indigo-600 text-white rounded-lg px-3 py-1.5 text-sm hover:bg-indigo-700">Kaydet</button>
          <button onClick={() => setDuzenle(false)} className="border border-line rounded-lg px-3 py-1.5 text-sm hover:bg-app">Vazgeç</button>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-surface border rounded-2xl shadow-sm p-3 ${kayit.aktif === false ? "border-line/50 opacity-60" : "border-line"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-content">{kayit.soru}</p>
          <p className="text-xs text-subtle mt-1 line-clamp-2">{kayit.cevap}</p>
          <div className="flex items-center gap-2 mt-1 text-[11px] text-subtle flex-wrap">
            <span className="px-1.5 py-0.5 rounded bg-app">{kayit.kategori}</span>
            <span>{(kayit.roller || []).map((r) => ROL_ETIKET[r] || r).join(", ")}</span>
            <span>sıra: {kayit.sira ?? 0}</span>
            {kayit.aktif === false && <span className="text-red-500">yayında değil</span>}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button onClick={() => siraDegis(-1)} title="Öne al" className="px-1.5 py-1 border border-line rounded hover:bg-app text-xs">▲</button>
          <button onClick={() => siraDegis(1)} title="Geri al" className="px-1.5 py-1 border border-line rounded hover:bg-app text-xs">▼</button>
          <button onClick={aktifToggle} className="px-2 py-1 border border-line rounded hover:bg-app text-xs">
            {kayit.aktif === false ? "Yayına al" : "Kaldır"}
          </button>
          <button onClick={() => setDuzenle(true)} className="px-2 py-1 border border-line rounded hover:bg-app text-xs">Düzenle</button>
          <button onClick={sil} className="px-1.5 py-1 border border-red-200 text-red-600 rounded hover:bg-red-50"><Trash2 className="h-3.5 w-3.5" /></button>
        </div>
      </div>
    </div>
  );
}
