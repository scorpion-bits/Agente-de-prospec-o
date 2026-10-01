"""T — Timing: a janela certa (prazo ou início do evento)."""

from __future__ import annotations

from django.utils import timezone

from core.models import Opportunity
from scoring.factors import EvidenceIndex, FactorResult, ScoringContext, build, fmt, no_data

FIELDS = ("deadline_at", "opens_at", "starts_at")

# (dias restantes até, valor): a primeira faixa que cabe vale; fora delas, `FAR_VALUE`.
DAY_BANDS = ((4, 0.1), (6, 0.5), (14, 0.85), (45, 0.95), (90, 0.7))
FAR_VALUE = 0.5


def _days_value(days: int) -> float:
    return next((v for limit, v in DAY_BANDS if days <= limit), FAR_VALUE)


def timing_factor(opp: Opportunity, ctx: ScoringContext, index: EvidenceIndex) -> FactorResult:
    if opp.deadline_at is not None:
        days = (timezone.localtime(opp.deadline_at).date() - ctx.today).days
        what = "prazo"
    elif opp.starts_at is not None:
        days = (timezone.localtime(opp.starts_at).date() - ctx.today).days
        what = "início"
    else:
        return no_data("T", "sem prazo nem data de início")
    value = _days_value(days)
    note = " (apertado demais)" if days <= 4 else ""
    unit = "dia" if days == 1 else "dias"
    return build("T", value, f"{what} em {days} {unit}{note}: {fmt(value)}", index, FIELDS)
