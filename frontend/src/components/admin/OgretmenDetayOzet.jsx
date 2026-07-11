import React, { useEffect, useState } from "react";
import axios from "axios";

/**
 * OgretmenDetayOzet — admin/koordinatör öğretmen detayı (sekmeli, lazy).
 * Mount olunca (öğretmen kartı açılınca) GET /teachers/{id}/detay-ozet çeker;
 * öğretmen listesinin ilk açılışını yavaşlatmaz. Yalnız MEVCUT verilerden.
 *
 * Sekmeler: Gelişim | Son İşlemler | Aktivite | Finansal (finansal, App.js'ten
 * `finansal` prop'u olarak gelir — payments/öğrenci roster orada hesaplı).
 *
 * Props: teacher {id, ad, soyad}, apiBase, rol, finansal (React node)
 */
const ISLEM_ETIKET = {
  duzenle: "Düzenleme", kur_gecis: "Kur geçişi", kaldir: "Öğrenci kaldırma",
  kalici_sil: "Kalıcı silme", ekle: "Ekleme", olustur: "Oluşturma",
};
const fmtTarih = (t) => { try { return new Date(t).toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" }); } catch { return "—"; } };

function Kart({ children, className = "" }) {
  return <div className={`bg-surface rounded-xl border border-line p-3 ${className}`}>{children}</div>;
}
function Stat({ etiket, deger, renk = "text-content" }) {
  return (
    <Kart className="text-center">
      <div className={`text-2xl font-bold tabular-nums ${renk}`}>{deger}</div>
      <div className="text-xs text-subtle mt-0.5">{etiket}</div>
    </Kart>
  );
}

export default function OgretmenDetayOzet({ teacher, apiBase, rol, finansal }) {
  const [sekme, setSekme] = useState("gelisim");
  const [veri, setVeri] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState("");

  useEffect(() => {
    let aktif = true;
    setYukleniyor(true); setHata("");
    axios.get(`${apiBase}/teachers/${teacher.id}/detay-ozet`)
      .then((r) => aktif && setVeri(r.data))
      .catch((e) => aktif && setHata(e?.response?.data?.detail || "Özet yüklenemedi."))
      .finally(() => aktif && setYukleniyor(false));
    return () => { aktif = false; };
  }, [apiBase, teacher.id]);

  const sekmeler = [
    { v: "gelisim", l: "📈 Gelişim" },
    { v: "islem", l: "🕓 Son İşlemler" },
    { v: "aktivite", l: "📊 Aktivite" },
    { v: "finansal", l: "💰 Finansal" },
  ];

  const g = veri?.gelisim || {};
  const a = veri?.aktivite || {};
  const islemler = veri?.son_islemler || [];

  const yuklemeSatiri = <div className="text-sm text-subtle py-6 text-center">Yükleniyor…</div>;

  return (
    <div className="space-y-3">
      {/* Sekme çubuğu */}
      <div className="flex flex-wrap gap-1.5">
        {sekmeler.map((s) => (
          <button key={s.v} onClick={() => setSekme(s.v)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${sekme === s.v ? "bg-primary text-white border-primary" : "bg-surface text-subtle border-line hover:border-primary"}`}>
            {s.l}
          </button>
        ))}
      </div>

      {hata && <div className="text-sm text-red-500">{hata}</div>}

      {/* GELİŞİM */}
      {sekme === "gelisim" && (yukleniyor ? yuklemeSatiri : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <Stat etiket="Toplam XP" deger={Math.round(g.toplam_xp || 0).toLocaleString("tr-TR")} renk="text-primary" />
            <Stat etiket={`Sıra (${g.toplam_ogretmen || 0} öğretmen)`} deger={g.sira ? `#${g.sira}` : "—"} renk="text-amber-600" />
            <Stat etiket="Rozet" deger={`${g.rozet_sayisi || 0}/${g.toplam_rozet || 0}`} renk="text-green-600" />
          </div>
          {g.motivasyon_mesaji && <div className="text-xs text-subtle italic bg-app rounded-lg px-3 py-2 border border-line">{g.motivasyon_mesaji}</div>}

          {/* XP kırılımı */}
          {g.kirilim && Object.keys(g.kirilim).length > 0 && (
            <Kart>
              <div className="text-xs font-semibold text-subtle mb-2">XP Kırılımı</div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                {[["etkinlik", "Etkinlik"], ["rozet", "Rozet"], ["ogrenci", "Öğrenci"], ["kur", "Kur"], ["veli", "Veli"]].map(([k, l]) => (
                  g.kirilim[k] != null && <span key={k} className="text-content">{l}: <b className="tabular-nums">{Math.round(g.kirilim[k])}</b></span>
                ))}
              </div>
            </Kart>
          )}

          {/* Rozetler */}
          <div>
            <div className="text-xs font-semibold text-subtle mb-2">🏅 Kazanılan Rozetler ({g.rozet_sayisi || 0})</div>
            {(g.rozetler || []).length === 0 ? (
              <div className="text-sm text-subtle">Henüz rozet yok.</div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {g.rozetler.map((r) => (
                  <div key={r.kod} className="flex items-center gap-2 bg-surface border border-line rounded-lg px-2.5 py-1.5" title={fmtTarih(r.kazanma_tarihi)}>
                    <span className="text-lg leading-none">{r.ikon}</span>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-content truncate">{r.ad}</div>
                      <div className="text-[10px] text-subtle">{fmtTarih(r.kazanma_tarihi)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}

      {/* SON İŞLEMLER */}
      {sekme === "islem" && (yukleniyor ? yuklemeSatiri : (
        islemler.length === 0 ? <div className="text-sm text-subtle py-4">Kayıtlı işlem yok.</div> : (
          <div className="space-y-1">
            {islemler.map((it, i) => (
              <div key={i} className="flex items-center gap-2 bg-surface border border-line rounded-lg px-3 py-1.5 text-sm">
                <span className="text-subtle tabular-nums whitespace-nowrap">{fmtTarih(it.tarih)}</span>
                <span className="font-medium text-content">{ISLEM_ETIKET[it.islem] || it.islem}</span>
                {it.hedef_tip && <span className="text-xs text-subtle">· {it.hedef_tip}</span>}
                {it.alan && <span className="text-xs text-subtle truncate">({it.alan}{it.eski != null ? `: ${it.eski}→${it.yeni}` : ""})</span>}
              </div>
            ))}
          </div>
        )
      ))}

      {/* AKTİVİTE */}
      {sekme === "aktivite" && (yukleniyor ? yuklemeSatiri : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <Stat etiket="Aktif Öğrenci" deger={a.ogrenci?.aktif ?? 0} renk="text-green-600" />
            <Stat etiket="Pasif/Arşiv" deger={a.ogrenci?.pasif ?? 0} renk="text-subtle" />
            <Stat etiket="Haftalık Ders" deger={a.ders?.aktif_seri ?? 0} renk="text-primary" />
            <Stat etiket="TIMI Uygulama" deger={a.timi?.toplam ?? 0} renk="text-purple-600" />
          </div>

          {/* Kur dağılımı */}
          {(a.kur_dagilimi || []).length > 0 && (
            <Kart>
              <div className="text-xs font-semibold text-subtle mb-2">Öğrencilerin Kur Dağılımı</div>
              <div className="flex flex-wrap gap-1.5">
                {a.kur_dagilimi.map((kd) => (
                  <span key={kd.kur} className="text-xs bg-app border border-line rounded-full px-2.5 py-1 text-content">
                    {kd.kur === "—" ? "Kur —" : `${kd.kur}. kur`}: <b className="tabular-nums">{kd.sayi}</b>
                  </span>
                ))}
              </div>
            </Kart>
          )}

          {/* Görevler */}
          <Kart>
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-semibold text-subtle">Atadığı Görevler</div>
              <div className="text-xs text-subtle">
                <span className="tabular-nums text-content font-medium">{a.gorev?.tamamlanan ?? 0}/{a.gorev?.atanan ?? 0}</span> tamamlandı (%{a.gorev?.oran ?? 0})
              </div>
            </div>
            {(a.gorev?.son || []).length === 0 ? (
              <div className="text-sm text-subtle">Görev atanmamış.</div>
            ) : (
              <div className="space-y-1">
                {a.gorev.son.map((gr, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-content truncate">{gr.baslik || "—"}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${gr.durum === "tamamlandi" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>
                      {gr.durum === "tamamlandi" ? "Tamamlandı" : "Bekliyor"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Kart>
        </div>
      ))}

      {/* FİNANSAL (App.js'ten gelen mevcut bölüm) */}
      {sekme === "finansal" && <div>{finansal}</div>}
    </div>
  );
}
