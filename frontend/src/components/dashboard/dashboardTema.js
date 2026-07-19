// Dashboard — tek semantik renk paleti + veri-yoğunluğu yardımcıları.
// TÜM dashboard grafikleri bu paletten beslenir (önceden her grafik kendi
// rastgele rengini kullanıyordu → tutarsız). Renkler light+dark'ta okunur.

export const GRAFIK = {
  bilgi:   "#3b82f6", // birincil seri: gelir, tahsilat, yeni kayıt
  basari:  "#10b981", // pozitif: yenileme, net, kur atlayan, alacak
  uyari:   "#f59e0b", // dikkat: öğretmen ödemesi, orta risk
  tehlike: "#ef4444", // negatif: vergi, borç, yüksek risk
  vurgu:   "#8b5cf6", // ikincil kategorik: yenileme kuru
  notr:    "#94a3b8", // belirsiz / veri yok
  // Izgara ve eksen — yarı saydam nötr, iki temada da görünür
  izgara:  "rgba(148,163,184,.22)",
  eksen:   "rgba(120,130,145,.95)",
};

// Kategorik seri için sıralı palet (donut/bar dilimleri)
export const SERI = [GRAFIK.bilgi, GRAFIK.basari, GRAFIK.vurgu, GRAFIK.uyari, GRAFIK.tehlike, GRAFIK.notr];

// recharts eksen/tick ortak stili
export const EKSEN_TICK = { fontSize: 11, fill: GRAFIK.eksen };

// Bir zaman serisinde (12 ay) ANLAMLI dolu ay sayısı — anahtarlardan biri
// bile sıfır-dışı ise o ay "dolu" sayılır.
export function doluAySayisi(data, anahtarlar) {
  if (!Array.isArray(data)) return 0;
  return data.filter((d) =>
    anahtarlar.some((k) => {
      const v = d?.[k];
      return v != null && Number(v) !== 0;
    })
  ).length;
}

// Trend grafiğinin gösterilmesi için gereken en az dolu ay (artık kullanılmıyor —
// grafikler MEVCUT veriyi hemen yansıtır; bkz. anlamliDilim).
export const MIN_AY = 3;

// Zaman serisini VERİ OLAN aralığa kırp: ilk dolu aydan son dolu aya kadar.
// Böylece 12 aylık boş eksen gösterilmez; grafik mevcut veriyi yansıtır ve
// zaman geçtikçe kendiliğinden büyür. Hiç veri yoksa [] döner.
export function anlamliDilim(data, anahtarlar) {
  if (!Array.isArray(data) || data.length === 0) return [];
  let ilk = -1, son = -1;
  data.forEach((d, i) => {
    if (anahtarlar.some((k) => d?.[k] != null && Number(d[k]) !== 0)) {
      if (ilk < 0) ilk = i;
      son = i;
    }
  });
  if (ilk < 0) return [];
  return data.slice(ilk, son + 1);
}
