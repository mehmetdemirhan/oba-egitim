"""core/zaman.py — Projede TEK tarih/zaman kaynağı (timezone-aware UTC).

KURAL (bkz. CLAUDE.md): Tarih ÜRETİMİ yalnız buradan yapılır.
  - simdi()  → HER ZAMAN timezone-aware UTC datetime döndürür.
  - iso()    → aware UTC ISO string (saklama için).
  - aware(x) → karşılaştırma öncesi NORMALİZE guard'ı: datetime veya ISO string alır,
               naive geleni UTC varsayıp aware'e çevirir (Mongo kayıtları UTC'dir),
               aware geleni UTC'ye çevirir. None/çözülemeyen → None.

`datetime.utcnow()` (naive üretir) YASAK — naive/aware karışımı "can't compare
offset-naive and offset-aware datetimes" hatasına ve sessiz yanlış hesaba yol açar.
Karşılaştırmadan önce iki tarafı da aware() ile normalize et.
"""
from datetime import datetime, timezone


def simdi() -> datetime:
    """Şu an — timezone-aware UTC."""
    return datetime.now(timezone.utc)


def iso() -> str:
    """Şu anın aware UTC ISO string'i (saklama)."""
    return simdi().isoformat()


def aware(x):
    """datetime | ISO str | None → aware UTC datetime | None.

    Naive datetime/str → UTC varsayılır (Mongo UTC'dir). Aware → UTC'ye çevrilir.
    """
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        try:
            x = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            # sadece tarih (YYYY-MM-DD) veya beklenmedik format
            try:
                x = datetime.strptime(s[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                return None
    if not isinstance(x, datetime):
        return None
    if x.tzinfo is None:
        return x.replace(tzinfo=timezone.utc)
    return x.astimezone(timezone.utc)


def gun_farki(a, b=None) -> float | None:
    """(a - b) gün farkı; b yoksa simdi(). Her iki taraf aware'e normalize edilir."""
    da = aware(a)
    db = aware(b) if b is not None else simdi()
    if da is None or db is None:
        return None
    return (db - da).total_seconds() / 86400.0
