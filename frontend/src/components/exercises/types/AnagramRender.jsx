import React, { useMemo, useState, useEffect } from "react";

/**
 * Anagram render bileşeni (puanlama = serbest, istemci tarafı puanlar).
 * İçerik şeması: { kelime: "kalem", karisik: "m-l-a-e-k", ipucu: "..." }
 *
 * Öğrenci karışık harf taşlarına tıklayarak kelimeyi kurar; "Kontrol Et" ile
 * kurduğu kelime hedef kelimeyle (Türkçe küçük harf) karşılaştırılır ve sonuç
 * tek seferde onCevap(dogruMu) ile motora bildirilir.
 *
 * Render sözleşmesi: { icerik, onCevap }
 */
const trKucuk = (s) => (s || "").toLocaleLowerCase("tr").replace(/\s+/g, "");

export default function AnagramRender({ icerik, onCevap }) {
  const kelime = icerik?.kelime || "";
  const ipucu = icerik?.ipucu || "";

  // Harf taşları: önce "karisik", yoksa kelimeyi deterministik karıştır.
  const harfler = useMemo(() => {
    const raw = icerik?.karisik
      ? String(icerik.karisik).split(/[-\s]+/).filter(Boolean)
      : kelime.split("");
    return raw.map((h, i) => ({ id: i, harf: h }));
  }, [icerik, kelime]);

  const [secili, setSecili] = useState([]); // taş id'leri (kuruluş sırası)
  const [sonuc, setSonuc] = useState(null);

  useEffect(() => {
    setSecili([]);
    setSonuc(null);
  }, [harfler]);

  const kullanildi = (id) => secili.includes(id);
  const tamam = secili.length === harfler.length && harfler.length > 0;
  const kurulan = secili.map((id) => harfler.find((h) => h.id === id)?.harf).join("");

  const tasEkle = (id) => {
    if (sonuc || kullanildi(id)) return;
    setSecili((s) => [...s, id]);
  };
  const geriAl = () => { if (!sonuc) setSecili((s) => s.slice(0, -1)); };
  const sifirla = () => { if (!sonuc) setSecili([]); };

  const gonder = async () => {
    if (!tamam || sonuc) return;
    const dogru = trKucuk(kurulan) === trKucuk(kelime);
    const r = await onCevap(dogru);
    setSonuc({ dogru, ...(r || {}) });
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 shadow-sm">
        <div className="text-sm text-gray-500 mb-1">Harfleri sıralayarak gizli kelimeyi bul:</div>
        {ipucu && (
          <div className="text-xs text-indigo-600 bg-indigo-50 inline-block px-3 py-1 rounded-full mb-3">
            💡 {ipucu}
          </div>
        )}

        {/* Kurulan kelime */}
        <div className="min-h-[3rem] flex flex-wrap gap-2 p-3 rounded-xl bg-indigo-50/60 border border-dashed border-indigo-200 mb-4">
          {secili.length === 0 && (
            <span className="text-sm text-gray-400 self-center">Harf taşlarına tıkla…</span>
          )}
          {secili.map((id, pos) => (
            <span key={pos} className="w-9 h-9 flex items-center justify-center rounded-lg bg-white border border-indigo-200 text-lg font-bold text-indigo-700 shadow-sm uppercase">
              {harfler.find((h) => h.id === id)?.harf}
            </span>
          ))}
        </div>

        {/* Harf havuzu */}
        <div className="flex flex-wrap gap-2">
          {harfler.map((h) => (
            <button
              key={h.id}
              onClick={() => tasEkle(h.id)}
              disabled={kullanildi(h.id) || !!sonuc}
              className={`w-10 h-10 flex items-center justify-center rounded-lg border text-lg font-bold uppercase transition-all ${
                kullanildi(h.id)
                  ? "border-gray-200 bg-gray-100 text-gray-300"
                  : "border-gray-300 bg-white text-gray-800 hover:bg-gray-50"
              }`}>
              {h.harf}
            </button>
          ))}
        </div>

        {!sonuc && (
          <div className="flex items-center gap-2 mt-4">
            <button onClick={gonder} disabled={!tamam}
              className="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold disabled:opacity-40 hover:bg-indigo-700 transition">
              Kontrol Et
            </button>
            <button onClick={geriAl} disabled={!secili.length}
              className="px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600 disabled:opacity-40">
              Geri Al
            </button>
            <button onClick={sifirla} disabled={!secili.length}
              className="px-3 py-2 rounded-xl border border-gray-200 text-sm text-gray-600 disabled:opacity-40">
              Sıfırla
            </button>
          </div>
        )}

        {sonuc && (
          <div className={`mt-4 px-4 py-3 rounded-xl text-sm font-medium ${
            sonuc.dogru ? "bg-green-50 text-green-700 border border-green-200"
                        : "bg-red-50 text-red-700 border border-red-200"}`}>
            {sonuc.dogru ? "✓ Doğru! Kelime: " : "✗ Doğru kelime: "}
            <span className="font-bold uppercase">{kelime}</span>
          </div>
        )}
      </div>
    </div>
  );
}
