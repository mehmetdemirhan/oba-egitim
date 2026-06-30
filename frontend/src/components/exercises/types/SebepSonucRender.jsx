import React from "react";
import OkumaSecmeliRender from "./OkumaSecmeliRender";

/**
 * Sebep-Sonuç İlişkisi render bileşeni.
 * İçerik şeması: { metin, sorular } — ortak okuduğunu anlama akışı.
 */
export default function SebepSonucRender(props) {
  return <OkumaSecmeliRender {...props} />;
}
