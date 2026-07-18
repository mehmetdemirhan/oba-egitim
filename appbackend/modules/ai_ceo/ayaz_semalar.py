"""Ayaz v1.5 (GÜVENLİ) — Pydantic şemaları.

Not: Bu güvenli sürümde AI kodu SÜREÇ İÇİNDE exec EDİLMEZ ve OTOMATİK deploy YAPILMAZ. Bu yüzden
tehlikeli 'demo_endpoint/demo_method/demo_request' alanları KASITLI olarak yoktur. Ayaz yalnızca
kod taslağı + risk/etki analizi üretir; canlıya alma insan onaylı ve mevcut patch_manager
(patch_security AST + sürüm arşivi + rollback) pipeline'ı üzerinden yapılır.
"""
from pydantic import BaseModel, Field


class AyazTaskRequest(BaseModel):
    talep: str = Field(..., min_length=5, max_length=4000, description="Doğal dil yazılım talebi")


class AyazTaskResponse(BaseModel):
    kod: str = Field(..., min_length=1, description="Üretilen Python kaynak kodu (self-contained modül)")
    aciklama: str = Field(default="", max_length=2000, description="Kodun kısa açıklaması")
    degisen_dosyalar: list[str] = Field(default_factory=list)
    risk_seviyesi: str = Field(default="orta", pattern="^(dusuk|orta|yuksek)$")
    etki_alani: str = Field(default="", max_length=500)
    tahmini_sure_dk: int = Field(default=15, ge=0, le=100000)
