"""L — Leveza: inverso do esforço (`effort_estimate`)."""

from __future__ import annotations

from core.models import Opportunity
from scoring.factors import EvidenceIndex, FactorResult, build, fmt, no_data

FIELDS = ("effort_estimate", "requirements_text", "participation_cost_text")
EFFORT_VALUE = {"low": 1.0, "medium": 0.6, "high": 0.25}


def lightness_factor(opp: Opportunity, index: EvidenceIndex) -> FactorResult:
    value = EFFORT_VALUE.get(opp.effort_estimate)
    if value is None:
        return no_data("L", "esforço desconhecido")
    label = dict(Opportunity.Effort.choices)[opp.effort_estimate].lower()
    return build("L", value, f"esforço {label}: {fmt(value)}", index, FIELDS)
