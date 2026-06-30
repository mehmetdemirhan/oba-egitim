import React from "react";
import OkumaSecmeliRender from "./OkumaSecmeliRender";

/**
 * 5N1K Soruları render bileşeni.
 * İçerik şeması: { metin, sorular: [{ soru, secenekler, dogru }] }
 * Metni okuyup kim/ne/nerede/ne zaman/neden/nasıl sorularını yanıtlar.
 */
export default function BesNBirKRender(props) {
  return <OkumaSecmeliRender {...props} />;
}
