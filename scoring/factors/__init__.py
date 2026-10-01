"""Fatores de pontuação: funções puras `(oportunidade, contexto) -> FactorResult` (E13).

Cada fator devolve valor em [0, 1], explicação legível e as evidências que o sustentam. Fator
sem dado vale `NEUTRAL` e diz «sem dado» (a confiança `K` cai, ver `scoring/engine.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from core.models import (
    CompanyProfile,
    Evidence,
    Municipality,
    PortfolioItem,
    ServiceOffering,
)

NEUTRAL = 0.5


@dataclass
class FactorResult:
    factor: str
    value: float
    explanation: str
    evidence_ids: list[int] = field(default_factory=list)
    support: float = 0.0  # 1 observado/manual · 0,5 inferido · 0 sem evidência


class EvidenceIndex:
    """Evidências por campo: a melhor é a observada/manual, depois a mais recente."""

    def __init__(self, items):
        rank = {Evidence.Kind.OBSERVED: 2, Evidence.Kind.MANUAL: 2, Evidence.Kind.INFERRED: 1}
        self.by_field: dict[str, Evidence] = {}
        for item in items:
            current = self.by_field.get(item.field)
            key = (rank.get(item.kind, 0), item.retrieved_at)
            if current is None or key > (rank.get(current.kind, 0), current.retrieved_at):
                self.by_field[item.field] = item

    def support(self, fields: tuple[str, ...]) -> tuple[float, list[int]]:
        found = [self.by_field[f] for f in fields if f in self.by_field]
        if not found:
            return 0.0, []
        strong = any(e.kind != Evidence.Kind.INFERRED for e in found)
        return (1.0 if strong else 0.5), sorted(e.pk for e in found)


@dataclass
class ScoringContext:
    """Dados compartilhados por todas as oportunidades de uma rodada (lidos uma vez)."""

    now: datetime = field(default_factory=timezone.now)
    company: CompanyProfile | None = None
    services: list[ServiceOffering] = field(default_factory=list)
    portfolio: list[PortfolioItem] = field(default_factory=list)
    home: Municipality | None = None

    @property
    def today(self):
        return timezone.localtime(self.now).date()


def fmt(value: float) -> str:
    text = f"{value:.2f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text.replace(".", ",")


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def brl(value: Decimal | float) -> str:
    whole = f"{float(value):,.0f}".replace(",", ".")
    return f"R$ {whole}"


def build(
    factor: str,
    value: float,
    explanation: str,
    index: EvidenceIndex,
    fields: tuple[str, ...],
    *,
    known: bool = True,
) -> FactorResult:
    """Monta o resultado com o suporte de evidência (zero se o fator está sem dado)."""
    support, ids = index.support(fields) if known else (0.0, [])
    return FactorResult(factor, round(clamp(value), 4), explanation, ids, support)


def no_data(factor: str, what: str) -> FactorResult:
    return FactorResult(factor, NEUTRAL, f"sem dado ({what}): {fmt(NEUTRAL)}", [], 0.0)
