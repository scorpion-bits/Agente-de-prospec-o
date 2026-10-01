"""Gates: o que é impossível não compete com o que é possível (docs/architecture/scoring.md)."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from core.models import Opportunity
from scoring.eligibility import Eligibility
from scoring.geo import GeoResult
from scoring.models import Score

DEADLINE_PASSED = "prazo vencido em {when:%d/%m/%Y}"


@dataclass
class Gate:
    kind: str
    reason: str


def check_gates(opp: Opportunity, now, geo: GeoResult, eligibility: Eligibility) -> Gate | None:
    """Primeiro gate que vale, ou `None`. A ordem é a do documento: prazo, território, empresa."""
    if opp.deadline_at is not None and opp.deadline_at < now:
        return Gate(
            Score.GateKind.EXPIRED, DEADLINE_PASSED.format(when=timezone.localtime(opp.deadline_at))
        )
    if opp.deadline_at is None:
        if opp.status == Opportunity.Status.CLOSED:
            return Gate(Score.GateKind.EXPIRED, "situação «encerrada» e sem prazo informado")
        past = opp.ends_at or opp.starts_at
        if past is not None and past < now:
            return Gate(
                Score.GateKind.EXPIRED, f"já aconteceu em {timezone.localtime(past):%d/%m/%Y}"
            )
    if geo.gated:
        return Gate(Score.GateKind.TERRITORY, geo.explanation.removeprefix("GATE: "))
    if eligibility.gate:
        return Gate(Score.GateKind.COMPANY_REQUIREMENT, eligibility.gate)
    return None
