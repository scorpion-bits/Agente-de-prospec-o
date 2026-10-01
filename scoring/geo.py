"""Relevância geográfica contextual `G ∈ [0,1]` (docs/architecture/geo-relevance.md).

`geo_relevance(item, profile)` devolve `GeoResult` (desempacota como `(valor, explicação)`).
Localização é **fator**, nunca filtro: a única exceção é o *gate* de elegibilidade territorial
explícita de uma oportunidade (`eligible_regions`). Localização desconhecida → `G = 0,5` e
`location_known=False` (o scoring reduz a confiança); nunca se chuta localização.

Os valores de cada perfil ficam em `PROFILES` (dado, não lógica): calibrar = editar a tabela.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from core.models import GeoProfile, Municipality
from core.services.geography import haversine_km
from core.services.normalize import name_key

RING_LABELS = {
    "R0": "base",
    "R1": "vizinhança ou polo prioritário",
    "R2": "interior próximo",
    "R3": "estado da base",
    "R4": "Brasil",
    "R5": "exterior",
}
UNKNOWN_VALUE = 0.5

# Valores calibráveis. `linear`: (km_inicial, valor_inicial, km_final, valor_final) dentro de R2.
PROFILES = {
    GeoProfile.ONSITE_RECURRING: {
        "R0": 1.0,
        "R1": 1.0,
        "R2": {"linear": (40.0, 0.8, 150.0, 0.3)},
        "R3": 0.15,
        "R4": 0.05,
        "R5": 0.05,
    },
    GeoProfile.ONSITE_EVENT: {
        "R0": 1.0,
        "R1": 1.0,
        "R2": 0.7,
        "capital": 0.5,  # capital do estado da base, quando fora de R2
        "R3": 0.3,
        "R4": 0.1,
        "R5": 0.05,
    },
    GeoProfile.REMOTE_SERVICE: {"base": 0.85, "near_bonus": 0.15, "R5": 0.6},
    GeoProfile.EDITAL_SCOPE: {
        "municipal_hub": 1.0,
        "regional": 0.9,
        "state": 0.8,
        "national": 0.7,
        "international": 0.4,
    },
}


@dataclass
class GeoResult:
    value: float | None  # `None` quando `gated`
    explanation: str
    profile: str
    ring: str | None = None
    distance_km: float | None = None
    gated: bool = False
    location_known: bool = True

    def __iter__(self):
        yield self.value
        yield self.explanation


def fmt(value: float) -> str:
    """Número no formato do texto de explicação (vírgula decimal, 2 casas sem zeros à toa)."""
    text = f"{value:.2f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text.replace(".", ",")


def home_municipality() -> Municipality | None:
    return Municipality.objects.filter(ibge_code=settings.HOME_MUNICIPALITY_IBGE).first()


def classify(municipality: Municipality, home: Municipality) -> tuple[str, float, bool]:
    """`(anel, distância em km, é polo)` de `municipality` em relação à base."""
    distance = haversine_km(home.lat, home.lon, municipality.lat, municipality.lon)
    is_hub = municipality.ibge_code in settings.PRIORITY_HUBS_IBGE
    if municipality.pk == home.pk:
        return "R0", 0.0, is_hub
    if is_hub or distance <= settings.GEO_NEAR_KM:
        return "R1", distance, is_hub
    if distance <= settings.GEO_REGIONAL_KM:
        return "R2", distance, is_hub
    if municipality.uf == home.uf:
        return "R3", distance, is_hub
    return "R4", distance, is_hub


def _place(municipality: Municipality, ring: str, distance: float, is_hub: bool) -> str:
    if ring == "R0":
        return f"{municipality} (base, R0)"
    if is_hub:
        return f"{municipality} (polo prioritário, {ring})"
    if ring in ("R1", "R2"):
        return f"{municipality} (≈ {distance:.0f} km, {ring})"
    return f"{municipality} ({RING_LABELS[ring]}, {ring})"


def _unknown(profile: str, why: str = "localização não identificada") -> GeoResult:
    return GeoResult(
        UNKNOWN_VALUE,
        f"{why} — perfil `{profile}`: {fmt(UNKNOWN_VALUE)} (confiança reduzida)",
        profile,
        location_known=False,
    )


def _eligible(regions: list[str], home: Municipality) -> bool:
    """A base cabe em `eligible_regions`? Lista vazia = sem restrição conhecida."""
    if not regions:
        return True
    region_names = {name_key(label): code for code, label in Municipality.Region.choices}
    for raw in regions:
        key = name_key(raw)
        place, _, uf = raw.partition("/")
        if key in ("brasil", "nacional", "todo o brasil"):
            return True
        if raw.strip().upper() == home.uf or key == name_key(home.uf):
            return True
        if name_key(place) == home.name_key and (not uf or uf.strip().upper() == home.uf):
            return True
        if region_names.get(key) == home.region:
            return True
    return False


def _table_value(table: dict, ring: str, distance: float, municipality, home) -> float:
    if ring == "R2" and isinstance(table["R2"], dict):
        d0, v0, d1, v1 = table["R2"]["linear"]
        span = (min(max(distance, d0), d1) - d0) / (d1 - d0)
        return round(v0 + (v1 - v0) * span, 4)
    if ring == "R3" and "capital" in table and municipality.is_capital:
        return table["capital"]
    return table[ring]


def geo_relevance(item, profile: str, *, home: Municipality | None = None) -> GeoResult:
    """Relevância geográfica de `item` (Organization ou Opportunity) sob o `profile`.

    `item` precisa de `.municipality` (pode ser `None`); para `edital_scope` usa também `.scope`
    e `.eligible_regions`. `profile` é um `GeoProfile`.
    """
    profile = GeoProfile(profile)
    if profile == GeoProfile.ONLINE:
        return GeoResult(1.0, "Online — distância irrelevante: 1,0", profile)

    home = home or home_municipality()
    if profile == GeoProfile.EDITAL_SCOPE:
        regions = list(getattr(item, "eligible_regions", None) or [])
        if home is not None and not _eligible(regions, home):
            return GeoResult(
                None,
                f"GATE: edital restrito a proponentes de {', '.join(regions)}",
                profile,
                gated=True,
            )
    municipality = getattr(item, "municipality", None)
    if home is None:
        return _unknown(
            profile, "base (HOME_MUNICIPALITY_IBGE) não carregada: rode load_municipalities"
        )

    if profile == GeoProfile.EDITAL_SCOPE:
        return _edital(item, municipality, home)
    if municipality is None:
        return _unknown(profile)
    ring, distance, is_hub = classify(municipality, home)
    place = _place(municipality, ring, distance, is_hub)

    if profile == GeoProfile.REMOTE_SERVICE:
        table = PROFILES[profile]
        value = table["base"] + (table["near_bonus"] if ring in ("R0", "R1", "R2") else 0.0)
        return GeoResult(
            round(value, 4),
            f"Serviço remoto para {place} — perfil `{profile}`: {fmt(value)}",
            profile,
            ring,
            distance,
        )
    table = PROFILES[profile]
    value = _table_value(table, ring, distance, municipality, home)
    return GeoResult(
        value,
        f"Presencial em {place} — perfil `{profile}`: {fmt(value)}",
        profile,
        ring,
        distance,
    )


def _edital(item, municipality, home) -> GeoResult:
    profile = GeoProfile.EDITAL_SCOPE
    table = PROFILES[profile]
    scope = getattr(item, "scope", "") or ""
    eligible = bool(getattr(item, "eligible_regions", None))
    ring = distance = None
    place = ""
    if municipality is not None:
        ring, distance, is_hub = classify(municipality, home)
        place = _place(municipality, ring, distance, is_hub)
    if scope == "municipal":
        if municipality is None:
            return _unknown(profile, "edital municipal sem município identificado")
        if ring in ("R0", "R1") and (municipality.ibge_code in settings.PRIORITY_HUBS_IBGE):
            value = table["municipal_hub"]
            return GeoResult(
                value,
                f"Edital municipal de {place} — perfil `{profile}`: {fmt(value)}",
                profile,
                ring,
                distance,
            )
        # Município que não é polo: distância pesa como em evento presencial.
        value = _table_value(PROFILES[GeoProfile.ONSITE_EVENT], ring, distance, municipality, home)
        return GeoResult(
            value,
            f"Edital municipal de {place} — distância pesa (perfil `{profile}`): {fmt(value)}",
            profile,
            ring,
            distance,
        )
    key = {"regional": "regional", "state": "state", "national": "national"}.get(scope)
    if scope == "international":
        key = "international"
    if key is None:
        return _unknown(profile, "abrangência do edital não identificada")
    value = table[key]
    labels = {
        "regional": "regional",
        "state": f"estadual {home.uf}",
        "national": "federal",
        "international": "internacional",
    }
    accepts = f", aceita proponentes de {home.name}" if eligible and key != "international" else ""
    return GeoResult(
        value,
        f"Edital {labels[key]}{accepts} — perfil `{profile}`: {fmt(value)}",
        profile,
        ring,
        distance,
    )
