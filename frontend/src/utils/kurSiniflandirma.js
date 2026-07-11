// Kur sınıflandırması — EKLENME OLAYINA değil KUR NUMARASINA göre.
//   kur = 1  → "yeni kayıt"            (tabloda MOR dolgu)
//   kur > 1  → "kur atlama / üst kur"  (tabloda YEŞİL dolgu) — ilk kez eklenmiş olsa bile
// Backend'deki _kur_no ile aynı mantık (rakam-dışı temizle → int).

export function kurNo(kur) {
  const n = parseInt(String(kur == null ? "" : kur).replace(/\D/g, ""), 10);
  return Number.isNaN(n) ? null : n;
}

// "yeni" | "ust_kur" | null (belirsiz)
export function kurSinifi(kur) {
  const n = kurNo(kur);
  if (n === 1) return "yeni";
  if (n != null && n > 1) return "ust_kur";
  return null;
}

// Tablo satırı dolgu sınıfı: mor (yeni 1. kur) / yeşil (üst kur) / boş.
export function kurRenkSinifi(kur) {
  const s = kurSinifi(kur);
  if (s === "yeni") return "bg-purple-50";
  if (s === "ust_kur") return "bg-emerald-50";
  return "";
}
