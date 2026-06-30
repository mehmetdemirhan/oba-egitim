import React from "react";
import SiralamaRender from "./SiralamaRender";

/**
 * Karışık Cümle Sıralama render bileşeni.
 * İçerik şeması: { parcalar: ["kelime", ...], dogru_sira: [indeks, ...] }
 * Kelimeleri sıralayarak anlamlı cümle kurar; ortak SiralamaRender'ı kullanır.
 */
export default function CumleSiralamaRender({ icerik, onCevap }) {
  return (
    <SiralamaRender
      ogeler={icerik?.parcalar || []}
      onCevap={onCevap}
      etiket="Kelimeleri sıralayarak anlamlı bir cümle oluştur:"
    />
  );
}
