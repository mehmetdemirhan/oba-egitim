# -*- coding: utf-8 -*-
"""AI Squad prompt kataloğu smoke — saf prompt/sözleşme modülü (route/DB/exec yok).

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_squad_prompts_smoke.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0


def check(k, m):
    global _gecen, _kalan
    if k:
        _gecen += 1; print(f"  [GECTI] {m}")
    else:
        _kalan += 1; print(f"  [KALDI] {m}")


def run():
    from modules.ai_ceo import squad_prompts as sp

    # 3 ajanın promtu dönüyor + kimlik işareti içeriyor
    for aid, imza in (("atlas", "Baş Yazılım Mimarı"), ("lina", "UI/UX Mimarı"), ("nova", "Kalite Güvence")):
        p = sp.get_agent_prompt(aid)
        check(isinstance(p, str) and imza in p and "ÇIKTI SÖZLEŞMESİ (JSON)" in p, f"get_agent_prompt('{aid}') → dolu prompt + JSON sözleşmesi")

    # Büyük/küçük harf + boşluk toleransı
    check(sp.get_agent_prompt("  ATLAS ") == sp.ATLAS_SYSTEM_PROMPT, "get_agent_prompt normalize (case/space)")

    # Bilinmeyen ID → ValueError
    try:
        sp.get_agent_prompt("ayaz")  # ayaz bir Squad prompt-ajanı değil
        check(False, "bilinmeyen ID ValueError vermeli")
    except ValueError:
        check(True, "bilinmeyen ID → ValueError")

    # Kimlik meta verisi yalnız kimlik (metrik/skor SIZMAMALI = uydurma yok)
    ids = {a["id"] for a in sp.SQUAD_AJANLAR}
    yasakli = {"skor", "score", "success_rate", "dismissal", "puan"}
    alanlar = {k for a in sp.SQUAD_AJANLAR for k in a}
    check(ids == {"atlas", "lina", "nova"} and not (alanlar & yasakli),
          "SQUAD_AJANLAR yalnız kimlik (id/ad/rol) — sahte metrik yok")

    # Nova dürüstlük guardrail'i: 'tahmini/ölçüm değil' ibaresi promtta var
    check("ölçüm değil" in sp.NOVA_SYSTEM_PROMPT and "tahmini" in sp.NOVA_SYSTEM_PROMPT.lower(),
          "Nova promtu sayısal skorları 'tahmin, ölçüm değil' diye işaretliyor")


if __name__ == "__main__":
    run()
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
