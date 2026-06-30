import React from "react";
import SiralamaRender from "./SiralamaRender";

/**
 * Hikâye Olay Sıralama render bileşeni.
 * İçerik şeması: { olaylar: ["olay cümlesi", ...], dogru_sira: [indeks, ...] }
 * Olayları gerçekleşme sırasına koyar; ortak SiralamaRender'ı kullanır.
 */
export default function OlaySiralamaRender({ icerik, onCevap }) {
  return (
    <SiralamaRender
      ogeler={icerik?.olaylar || []}
      onCevap={onCevap}
      etiket="Olayları gerçekleşme sırasına göre dizmek için sırayla tıkla:"
    />
  );
}
