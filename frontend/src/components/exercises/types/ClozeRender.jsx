import React from "react";
import SecmeliRender from "./SecmeliRender";

/**
 * Boşluk doldurma (cloze) render bileşeni.
 * İçerik şeması: { sorular: [{ soru: "... ___ ...", secenekler, dogru }] }
 * Boşluğu ('___') görsel olarak vurgular; gerisi ortak seçmeli akışıdır.
 */
function soruGoster(soru) {
  const parcalar = (soru?.soru || "").split("___");
  return (
    <div className="text-lg font-bold text-gray-900 mb-4 leading-relaxed">
      {parcalar.map((p, i) => (
        <React.Fragment key={i}>
          {p}
          {i < parcalar.length - 1 && (
            <span className="inline-block align-middle mx-1 px-6 py-0.5 rounded-md bg-indigo-50 border-b-2 border-indigo-300" />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

export default function ClozeRender(props) {
  return <SecmeliRender {...props} soruGoster={soruGoster} />;
}
