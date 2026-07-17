"""AI CEO — küçük ortak yardımcılar (döngüsel importsuz)."""


def metrik_al(fotograf: dict, yol: str, varsayilan=None):
    """Fotoğraftan noktalı yol ile değer okur: 'muhasebe.tahsil_edilen'."""
    cur = fotograf or {}
    for parca in yol.split("."):
        if isinstance(cur, dict) and parca in cur:
            cur = cur[parca]
        else:
            return varsayilan
    return cur


# Kategori → karne isabet ölçümünde bakılacak headline metrik + yön (artış iyi mi?)
KATEGORI_METRIK = {
    "tahsilat": ("muhasebe.tahsil_edilen", "artis"),
    "ogretmen_gelisimi": ("ogretmen.yenileme_orani_yuzde", "artis"),
    "ogrenci_memnuniyeti": ("ogretmen.veli_memnuniyeti_5uzerinden", "artis"),
    "buyume": ("ogrenci.aktif", "artis"),
    "urun_iyilestirme": ("kullanim.gorev_tamamlama_yuzde", "artis"),
}
