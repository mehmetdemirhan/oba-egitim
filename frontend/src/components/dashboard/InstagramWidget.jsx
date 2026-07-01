import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";

/**
 * InstagramWidget — öğretmen dashboard'ında @dogadakiogretmenim beslemesi.
 * Postlar tek tek (önceki/sonraki) gösterilir; OBA içinde beğen/kaydet/yorum +
 * "Instagram'da da yaptım" onay kutuları XP kazandırır.
 *
 * Props: apiBase — `${BACKEND_URL}/api`
 */
export default function InstagramWidget({ apiBase, compact = false }) {
  const [durum, setDurum] = useState("yukleniyor"); // yukleniyor | ok | bos | hata | pasif
  const [postlar, setPostlar] = useState([]);
  const [idx, setIdx] = useState(0);
  const [xpAnim, setXpAnim] = useState(null); // {n, key}
  const [yorumModal, setYorumModal] = useState(null); // {post_id, metin}

  const yukle = useCallback(async () => {
    try {
      const r = await axios.get(`${apiBase}/instagram/postlar`, { params: { limit: 20 } });
      if (r.data?.aktif === false) { setDurum("pasif"); return; }
      const p = r.data?.postlar || [];
      setPostlar(p);
      setDurum(p.length ? "ok" : "bos");
    } catch (e) {
      setDurum("hata");
    }
  }, [apiBase]);

  useEffect(() => { yukle(); }, [yukle]);

  const toplamKazanilan = useMemo(
    () => postlar.reduce((t, p) => t + (p.kullanici_durumu?.kazandigi_xp || 0), 0),
    [postlar]
  );

  const xpGoster = (n) => { if (n > 0) setXpAnim({ n, key: Date.now() + Math.random() }); };

  const guncelleDurum = (post_id, degisim) => {
    setPostlar((liste) => liste.map((p) =>
      p.instagram_post_id === post_id
        ? { ...p, kullanici_durumu: { ...p.kullanici_durumu, ...degisim } }
        : p
    ));
  };

  const etkilesim = async (post, eylem, deger) => {
    try {
      const r = await axios.post(`${apiBase}/instagram/etkilesim`, {
        instagram_post_id: post.instagram_post_id, eylem, deger,
      });
      const yeni = { [eylem]: deger, kazandigi_xp: r.data?.post_toplam_xp ?? post.kullanici_durumu?.kazandigi_xp };
      guncelleDurum(post.instagram_post_id, yeni);
      xpGoster(r.data?.kazandigi_xp || 0);
    } catch (e) { /* sessiz */ }
  };

  const yorumGonder = async () => {
    if (!yorumModal?.metin?.trim()) return;
    try {
      const r = await axios.post(`${apiBase}/instagram/yorum`, {
        instagram_post_id: yorumModal.post_id, yorum: yorumModal.metin.trim(),
      });
      guncelleDurum(yorumModal.post_id, { yorum: yorumModal.metin.trim(), kazandigi_xp: r.data?.post_toplam_xp });
      xpGoster(r.data?.kazandigi_xp || 0);
      setYorumModal(null);
    } catch (e) { /* sessiz */ }
  };

  // Pasif → hiç render etme
  if (durum === "pasif") return null;

  // ── Kompakt varyant: tek satırlık soft kart (dashboard'da en altta) ──
  if (compact) {
    const sonPost = postlar[0];
    const sonTarih = sonPost?.yayin_tarihi
      ? new Date(sonPost.yayin_tarihi).toLocaleDateString("tr-TR", { day: "numeric", month: "short" })
      : "";
    return (
      <div className="bg-gray-50 rounded-2xl border border-gray-100 px-4 py-2.5 flex items-center gap-3">
        <span className="text-lg opacity-70">📷</span>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold text-gray-500">Doğadaki Öğretmenim</div>
          {durum === "ok" && sonPost ? (
            <div className="text-[11px] text-gray-400 truncate">
              Son paylaşım{sonPost.baslik ? `: ${sonPost.baslik}` : ""}{sonTarih ? ` · ${sonTarih}` : ""}
            </div>
          ) : durum === "hata" ? (
            <div className="text-[11px] text-gray-400">Besleme geçici olarak kullanılamıyor</div>
          ) : durum === "yukleniyor" ? (
            <div className="text-[11px] text-gray-300">Yükleniyor…</div>
          ) : (
            <div className="text-[11px] text-gray-400">Henüz paylaşım yok</div>
          )}
        </div>
        {durum === "ok" && sonPost && (
          <a href={sonPost.post_url} target="_blank" rel="noreferrer"
            className="text-[11px] text-pink-500 font-medium shrink-0 hover:underline">Aç →</a>
        )}
      </div>
    );
  }

  const Cerceve = ({ children }) => (
    <div className="bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden"
      style={{ maxHeight: 500 }}>
      <div className="px-4 py-3 bg-gradient-to-r from-pink-500 to-orange-400 text-white">
        <div className="font-bold text-sm flex items-center gap-2">📱 Doğadaki Öğretmenim</div>
        <div className="text-[11px] opacity-90">Instagram'daki son paylaşımlar</div>
      </div>
      <div className="p-3">{children}</div>
    </div>
  );

  if (durum === "yukleniyor") return <Cerceve><div className="py-8 text-center text-gray-400 text-sm">Yükleniyor…</div></Cerceve>;
  if (durum === "hata") return <Cerceve><div className="py-8 text-center text-gray-400 text-sm">Instagram beslemesi geçici olarak kullanılamıyor, sonra tekrar deneyeceğiz.</div></Cerceve>;
  if (durum === "bos") return <Cerceve><div className="py-8 text-center text-gray-400 text-sm">Henüz Instagram paylaşımı yüklenmedi. Yönetici senkronize edince görünecek.</div></Cerceve>;

  const post = postlar[idx] || {};
  const kd = post.kullanici_durumu || {};
  const tarih = post.yayin_tarihi ? new Date(post.yayin_tarihi).toLocaleDateString("tr-TR", { day: "numeric", month: "long" }) : "";

  const OnurKutu = ({ eylem, etiket, xp }) => (
    <label className="flex items-center gap-2 text-[11px] text-gray-600 cursor-pointer">
      <input type="checkbox" checked={!!kd[eylem]} className="w-3.5 h-3.5 accent-pink-500"
        onChange={(e) => etkilesim(post, eylem, e.target.checked)} />
      {etiket} <span className="text-pink-600 font-semibold">(+{xp} XP)</span>
    </label>
  );

  return (
    <Cerceve>
      <div className="relative rounded-xl border border-gray-100 overflow-hidden">
        {/* Görsel */}
        <div className="w-full h-40 bg-gray-100 flex items-center justify-center overflow-hidden">
          {post.medya_url ? (
            <img src={post.medya_url} alt="" className="w-full h-full object-cover"
              onError={(e) => { e.currentTarget.style.display = "none"; }} />
          ) : (
            <span className="text-4xl">🌿</span>
          )}
        </div>

        <div className="p-3 space-y-2">
          {post.baslik && <div className="text-sm text-gray-700 line-clamp-2">{post.baslik}</div>}
          <div className="text-[11px] text-gray-400">{tarih}</div>

          {/* Aksiyonlar */}
          <div className="flex items-center gap-2">
            <button onClick={() => etkilesim(post, "begen", !kd.begen)}
              className={`px-2.5 py-1.5 rounded-xl text-xs font-medium border transition-all ${kd.begen ? "bg-pink-50 border-pink-300 text-pink-600" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
              {kd.begen ? "❤️" : "🤍"} Beğen
            </button>
            <button onClick={() => etkilesim(post, "kaydet", !kd.kaydet)}
              className={`px-2.5 py-1.5 rounded-xl text-xs font-medium border transition-all ${kd.kaydet ? "bg-amber-50 border-amber-300 text-amber-600" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
              🔖 {kd.kaydet ? "Kaydedildi" : "Kaydet"}
            </button>
            <button onClick={() => setYorumModal({ post_id: post.instagram_post_id, metin: kd.yorum || "" })}
              className="px-2.5 py-1.5 rounded-xl text-xs font-medium border border-gray-200 text-gray-600 hover:bg-gray-50">
              💬 {kd.yorum ? "Yorumun" : "Yorum"}
            </button>
          </div>

          {/* Onur kutuları */}
          <div className="space-y-1 pt-1">
            <OnurKutu eylem="onur_ig_begen" etiket="Instagram'da da beğendim" xp={5} />
            <OnurKutu eylem="onur_ig_kaydet" etiket="Instagram'da da kaydettim" xp={8} />
          </div>

          <a href={post.post_url} target="_blank" rel="noreferrer"
            className="inline-block mt-1 px-3 py-1.5 rounded-xl bg-gradient-to-r from-pink-500 to-orange-400 text-white text-xs font-semibold">
            📱 Instagram'da Aç
          </a>
        </div>

        {/* XP animasyonu */}
        {xpAnim && (
          <div key={xpAnim.key} className="absolute top-2 right-2 text-pink-600 font-bold text-sm"
            style={{ animation: "ig-xp 1200ms ease forwards" }}>
            +{xpAnim.n} XP kazandın!
          </div>
        )}
      </div>

      {/* Gezinme */}
      <div className="flex items-center justify-between mt-2 text-xs">
        <button disabled={idx <= 0} onClick={() => setIdx((i) => Math.max(0, i - 1))}
          className="px-2 py-1 rounded-lg border border-gray-200 disabled:opacity-40">← Önceki</button>
        <span className="text-gray-400">{idx + 1} / {postlar.length}</span>
        <button disabled={idx >= postlar.length - 1} onClick={() => setIdx((i) => Math.min(postlar.length - 1, i + 1))}
          className="px-2 py-1 rounded-lg border border-gray-200 disabled:opacity-40">Sonraki →</button>
      </div>

      <div className="text-center text-[11px] text-gray-500 mt-2">
        Bu paylaşımlardan kazandığın: <b className="text-pink-600">{toplamKazanilan} XP</b>
      </div>

      {/* Yorum modalı */}
      {yorumModal && (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4" onClick={() => setYorumModal(null)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-3 border-b font-bold text-gray-800">💬 Yorum</div>
            <div className="p-5 space-y-3">
              <textarea value={yorumModal.metin} rows={3}
                onChange={(e) => setYorumModal((y) => ({ ...y, metin: e.target.value }))}
                placeholder="Yorumunu yaz…"
                className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm outline-none focus:border-pink-400" />
              <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                ℹ️ Yorumunuz yalnızca burada kaydedilir. Instagram'da yorum yapmak için "Instagram'da Aç" butonunu kullanın.
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => setYorumModal(null)} className="px-4 py-2 rounded-xl border border-gray-200 text-sm">İptal</button>
                <button onClick={yorumGonder} className="px-4 py-2 rounded-xl bg-pink-600 text-white text-sm font-semibold hover:bg-pink-700">Gönder</button>
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes ig-xp {0%{opacity:0;transform:translateY(6px) scale(0.8);}30%{opacity:1;transform:translateY(-2px) scale(1.1);}100%{opacity:0;transform:translateY(-18px) scale(1);}}`}</style>
    </Cerceve>
  );
}
