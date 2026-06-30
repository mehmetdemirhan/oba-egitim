import React from "react";
import OkumaSecmeliRender from "./OkumaSecmeliRender";

/**
 * Tahmin Et render bileşeni.
 * İçerik şeması: { metin, sorular } — ortak okuduğunu anlama akışı.
 */
export default function TahminEtRender(props) {
  return <OkumaSecmeliRender {...props} />;
}
