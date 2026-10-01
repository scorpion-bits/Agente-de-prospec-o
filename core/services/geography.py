"""Geografia: resolução de municípios, distância e anéis (docs/architecture/geo-relevance.md)."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from core.services.normalize import name_key

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em linha reta entre dois pontos, em km."""
    d_lat, d_lon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def resolve_municipality(name: str | None, uf: str | None = None):
    """O `Municipality` que casa com (nome normalizado, UF); `None` se não casa ou é ambíguo.

    Sem UF só resolve nomes **únicos** no país (ex.: "Araraquara"); "São Carlos" sem UF é ambíguo.
    Nunca chuta: homônimos exigem a UF.
    """
    from core.models import Municipality

    key = name_key(name)
    if not key:
        return None
    candidates = Municipality.objects.filter(name_key=key)
    uf = (uf or "").strip().upper()
    if uf:
        return candidates.filter(uf=uf).first()
    found = list(candidates[:2])
    return found[0] if len(found) == 1 else None


def resolve_location(instance, save_kwargs: dict) -> None:
    """Preenche `instance.municipality` a partir de `municipality_name`/`uf`, se possível.

    Mantém uma escolha manual (FK já preenchida que continua combinando com o texto) e
    re-resolve se o texto mudou. Com `update_fields`, inclui a FK para ela ser gravada.
    """
    current = instance.municipality if instance.municipality_id else None
    text = name_key(instance.municipality_name)
    if current is not None and (not text or (current.name_key, current.uf) == (text, instance.uf)):
        return
    if not text:
        return
    resolved = resolve_municipality(instance.municipality_name, instance.uf)
    if resolved is None or resolved.pk == instance.municipality_id:
        return
    instance.municipality = resolved
    fields = save_kwargs.get("update_fields")
    if fields is not None and "municipality" not in fields:
        save_kwargs["update_fields"] = [*fields, "municipality"]
