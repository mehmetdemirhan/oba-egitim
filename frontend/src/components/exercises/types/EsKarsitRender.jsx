import React from "react";
import SecmeliRender from "./SecmeliRender";

/**
 * Eş ve karşıt anlamlılar render bileşeni.
 * İçerik şeması: { sorular: [{ soru, secenekler, dogru }] }
 * Standart çoktan seçmeli akış; ortak SecmeliRender'ı kullanır.
 */
export default function EsKarsitRender(props) {
  return <SecmeliRender {...props} />;
}
