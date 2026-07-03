# Tema Migration Kriteri — Renk → Semantik Token Haritası

Bu belge, `App.js` ve bileşenlerdeki en yaygın sabit Tailwind renk class'larının
hangi **semantik token class'ına** dönüştürüleceğini tanımlar. FAZ 2'deki migration
bu haritaya göre uygulanır.

## İlke

- **Nötr token'ların LIGHT değerleri mevcut renklerle EŞLEŞİR** → light modda görünüm
  değişmez. Değişen tek şey: renk artık `var(--token)`'dan gelir, sabit değil.
- **DARK değerler** `.dark` seçicisinde tanımlıdır → dark mode "bedavaya" çalışır.
- **`OgrenciPaneli` (App.js ~4891–6860) MIGRE EDİLMEZ** — cream paleti korunur.
- Renkli aksanlar (buton/başarı/uyarı) token'a taşınır; içerik-özel renkler
  (gamification bölge renkleri, AI karakter renkleri, rozet seviye rozetleri) DOKUNULMAZ.

## Harita (en yaygın ~30 kombinasyon)

### Yüzeyler & zemin
| Mevcut | Yeni semantik class | Token | Light değer |
|---|---|---|---|
| `bg-white` | `bg-surface` | `--surface` | `#FFFFFF` |
| `bg-gray-50` | `bg-bg-app` | `--background` | `#F9FAFB` |
| `bg-gray-100` | `bg-muted` | `--border` | `#E5E7EB` |

### Metin
| `text-gray-900` / `text-gray-800` / `text-gray-700` | `text-content` | `--text` | `#1F2937` |
| `text-gray-600` / `text-gray-500` / `text-gray-400` | `text-muted-fg` | `--text-secondary` | `#6B7280` |

### Kenarlık
| `border-gray-200` / `border-gray-100` / `border-gray-300` | `border-default` | `--border` | `#E5E7EB` |

### Marka / birincil (mavi → primary)
| `bg-blue-600` / `bg-blue-500` | `bg-primary` | `--primary` | `#2563EB` |
| `hover:bg-blue-700` / `hover:bg-blue-600` | `hover:bg-primary-hover` | `--primary-hover` | `#1D4ED8` |
| `text-blue-600` / `text-blue-700` | `text-primary` | `--primary` | `#2563EB` |
| `border-blue-500` | `border-primary` | `--primary` | — |

### Durum renkleri
| `bg-red-600` / `bg-red-500` | `bg-danger` | `--danger` | `#DC2626` |
| `text-red-600` / `text-red-500` / `text-red-700` | `text-danger` | `--danger` | — |
| `bg-green-600` / `bg-green-500` | `bg-success` | `--success` | `#16A34A` |
| `text-green-600` / `text-green-700` | `text-success` | `--success` | — |
| `bg-yellow-500` / `bg-amber-500` | `bg-warning` | `--warning` | `#D97706` |
| `text-yellow-600` / `text-amber-600` | `text-warning` | `--warning` | — |

## Migration yöntemi (FAZ 2)

1. `index.css`'e `:root` (light) + `.dark` + `[data-role=...]` token blokları eklenir.
2. `tailwind.config.js`'e semantik renk aliasları eklenir (`primary`, `surface`,
   `content`, `danger` …) → `var(--token)`'a bağlanır.
3. `App.js`'te panel bazlı (Admin/Öğretmen/Veli) **kontrollü** class değişimi yapılır.
   **OgrenciPaneli hariç.** Değişim `scripts/tema_migrate.py` ile satır-aralığı kısıtlı
   regex + build doğrulaması ile uygulanır.
4. Nötr değerler eşleştiği için light görünüm değişmez; dark değerler devreye girince
   `.dark` sınıfıyla koyu tema çalışır.

## Kapsam notu (dürüstlük)

App.js ~3.700 renkli utility içerir. Bu migration **yapısal nötrleri + en yaygın
aksanları** hedefler (yüksek etki, düşük risk). İçerik-özel renkler ve nadir tonlar
bilinçli olarak bırakılır; light modda görünmez, dark modda küçük tutarsızlıklar
kalabilir (sonraki iterasyonda ele alınır). Bu, "tek seferde 3.700 yeri değiştir"
riskini almadan tema+dark mode'u işler hale getirir.
