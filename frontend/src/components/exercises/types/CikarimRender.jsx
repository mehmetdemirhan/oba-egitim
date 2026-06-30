import React from "react";
import OkumaSecmeliRender from "./OkumaSecmeliRender";

/**
 * Çıkarım Yapma render bileşeni.
 * İçerik şeması: { metin, sorular } — ortak okuduğunu anlama akışı.
 */
export default function CikarimRender(props) {
  return <OkumaSecmeliRender {...props} />;
}
