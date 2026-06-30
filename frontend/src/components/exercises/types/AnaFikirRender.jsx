import React from "react";
import OkumaSecmeliRender from "./OkumaSecmeliRender";

/**
 * Ana Fikir Bulma render bileşeni.
 * İçerik şeması: { metin, sorular } — ortak okuduğunu anlama akışı.
 */
export default function AnaFikirRender(props) {
  return <OkumaSecmeliRender {...props} />;
}
