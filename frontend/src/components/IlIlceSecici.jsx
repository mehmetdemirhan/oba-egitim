import React, { useId } from "react";
import { ILLER, ilceListesi } from "../data/turkiyeIlIlce";

/**
 * IlIlceSecici — aranabilir il (81) + ile göre dolan ilçe seçici (statik veri).
 * datalist ile hem arama hem serbest giriş. Props: il, ilce, onIl(v), onIlce(v),
 * labelli (varsayılan true). İl değişince ilçe otomatik temizlenir (üst bileşende
 * onIl içinde onIlce('') çağrılması önerilir; bu bileşen de değişimde ilçe'yi sıfırlar).
 */
export default function IlIlceSecici({ il = "", ilce = "", onIl, onIlce, labelli = true }) {
  const uid = useId();
  const ilListId = `il-${uid}`;
  const ilceListId = `ilce-${uid}`;
  const ilceler = ilceListesi(il);

  const cls = "w-full border border-line rounded-lg px-3 py-2 text-sm bg-surface";

  return (
    <div className="grid grid-cols-2 gap-2">
      <div>
        {labelli && <label className="text-xs font-medium text-subtle">İl</label>}
        <input list={ilListId} value={il} placeholder="İl ara/seç"
          onChange={(e) => { const v = e.target.value; onIl?.(v); if (v !== il) onIlce?.(""); }}
          className={cls} />
        <datalist id={ilListId}>{ILLER.map((i) => <option key={i} value={i} />)}</datalist>
      </div>
      <div>
        {labelli && <label className="text-xs font-medium text-subtle">İlçe</label>}
        <input list={ilceListId} value={ilce} placeholder={il ? "İlçe ara/seç" : "Önce il seçin"}
          disabled={!il}
          onChange={(e) => onIlce?.(e.target.value)}
          className={`${cls} disabled:opacity-60`} />
        <datalist id={ilceListId}>{ilceler.map((i) => <option key={i} value={i} />)}</datalist>
      </div>
    </div>
  );
}
