"""AI CEO modülü — Ayda (yönetim CEO'su) + Miran (öğretmen koçu).

Veri temelli, görsel 360° sistem danışmanı. Alt bileşenler:
  personalar  — iki persona tek konfigürasyon (ad, avatar, üslup, veri kapsamı)
  fotograf    — deterministik sistem fotoğrafı + KVKK + otonom envanter
  analiz      — Ayda analizi + öneriler + dayanak (halüsinasyon) doğrulama
  raporlar    — günlük/haftalık/aylık + PDF
  sohbet      — "Ayda'ya Sor" (rapor bağlamlı)
  mektup      — öğretmen performans mektupları + ONAY akışı
  miran       — öğretmen koçu (öğretmen paneli)
  karne       — Ayda'nın deterministik karnesi
  anomali     — kural bazlı anomali uyarıları
  hedef       — hedef takibi (gauge)

Tüm alt-router'lar tek `router` altında toplanır; registry.json `ai_ceo` yükler.
"""
from fastapi import APIRouter

from . import (fotograf, analiz, raporlar, sohbet, mektup, miran, karne, anomali, hedef,
               pazar, kuyruk, yonetim, plan, deniz, deneyim, analitik, nps)

router = APIRouter()
for _alt in (fotograf, analiz, raporlar, sohbet, mektup, miran, karne, anomali, hedef,
             pazar, kuyruk, yonetim, plan, deniz, deneyim, analitik, nps):
    router.include_router(_alt.router)
