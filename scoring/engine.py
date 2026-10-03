"""Motor de pontuação de oportunidades (E13): gates → fatores → confiança → total.

Determinístico (mesma entrada → mesmo score), sem IA e sem rede (ADR-006). Os pesos vêm de
`scoring/profiles.py`; cada `Score` guarda a versão com que foi calculado.

    Score = round(100 × K × Σ wᵢ·fᵢ),   K = 0,7 + 0,3 × q
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from core.models import (
    CompanyProfile,
    Evidence,
    Opportunity,
    PortfolioItem,
    ServiceOffering,
    Triage,
)
from scoring.eligibility import check_eligibility
from scoring.factors import EvidenceIndex, FactorResult, ScoringContext
from scoring.factors.access import access_factor, geo_for
from scoring.factors.chance import chance_factor
from scoring.factors.fit import fit_factor
from scoring.factors.lightness import lightness_factor
from scoring.factors.timing import timing_factor
from scoring.factors.value import value_factor
from scoring.gates import check_gates
from scoring.geo import home_municipality
from scoring.matching import load_portfolio
from scoring.models import Score
from scoring.profiles import (
    FACTOR_LABELS,
    FACTORS,
    K_BASE,
    K_RANGE,
    SCORING_VERSION,
    WEIGHTS,
    label_for,
    profile_for_kind,
)


@dataclass
class ScoreResult:
    profile: str
    total: int | None = None
    label: str = Score.Label.GATED
    confidence: float | None = None
    raw_sum: float | None = None
    gate_kind: str = ""
    gate_reason: str = ""
    breakdown: list[dict] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)

    @property
    def gated(self) -> bool:
        return self.total is None


def build_context(now=None) -> ScoringContext:
    """Lê uma vez o que é comum a todas as oportunidades da rodada."""
    return ScoringContext(
        now=now or timezone.now(),
        company=CompanyProfile.get(),
        services=list(ServiceOffering.objects.filter(active=True)),
        portfolio=list(
            PortfolioItem.objects.filter(pk__in=[p.pk for p in load_portfolio()]).prefetch_related(
                "services"
            )
        ),
        home=home_municipality(),
    )


def confidence(factors: list[FactorResult]) -> float:
    """`K = 0,7 + 0,3 × q`; q = média do suporte (observado 1 · inferido 0,5 · sem evidência 0)."""
    q = sum(f.support for f in factors) / len(factors)
    return K_BASE + K_RANGE * q


def combine(profile: str, factors: list[FactorResult]) -> tuple[int, float, float, list[dict]]:
    """Soma ponderada e confiança. Devolve `(total, K, soma, breakdown)`."""
    weights = WEIGHTS[profile]
    by_key = {f.factor: f for f in factors}
    breakdown, raw_sum = [], 0.0
    for key in FACTORS:
        result = by_key[key]
        points = result.value * weights[key]
        raw_sum += points
        breakdown.append(
            {
                "factor": key,
                "label": FACTOR_LABELS[key],
                "raw": result.value,
                "weight": weights[key],
                "points": round(points * 100, 2),
                "explanation": result.explanation,
                "evidence_ids": result.evidence_ids,
                "support": result.support,
            }
        )
    k = confidence(factors)
    return round(100 * k * raw_sum), k, raw_sum, breakdown


def score_opportunity(
    opp: Opportunity, ctx: ScoringContext, index: EvidenceIndex | None = None
) -> ScoreResult:
    if index is None:
        index = EvidenceIndex(_evidence_of(opp))
    profile = profile_for_kind(opp.kind)
    fit = fit_factor(opp, ctx, index)
    eligibility = check_eligibility(opp, ctx.company, fit.service, ctx.today)
    geo = geo_for(opp, ctx)

    result = ScoreResult(profile=profile, alerts=list(eligibility.alerts))
    gate = check_gates(opp, ctx.now, geo, eligibility)
    if gate is not None:
        result.gate_kind, result.gate_reason = gate.kind, gate.reason
        return result

    factors = [
        value_factor(opp, index),
        fit.result,
        chance_factor(opp, eligibility, index),
        timing_factor(opp, ctx, index),
        access_factor(opp, geo, index),
        lightness_factor(opp, index),
    ]
    total, k, raw_sum, breakdown = combine(profile, factors)
    if not geo.location_known:
        result.alerts.append("localização não identificada: o acesso usa valor neutro")
    result.total, result.confidence, result.raw_sum = total, round(k, 4), round(raw_sum, 4)
    result.label = label_for(total)
    result.breakdown = breakdown
    return result


def _evidence_of(opp: Opportunity):
    content_type = ContentType.objects.get_for_model(Opportunity)
    return Evidence.objects.filter(content_type=content_type, object_id=opp.pk)


def is_discarded(entity) -> bool:
    """Já descartada pelo humano: fora do digest, não recalcula (docs/architecture/scoring.md)."""
    content_type = ContentType.objects.get_for_model(type(entity))
    return Triage.objects.filter(
        content_type=content_type, object_id=entity.pk, status=Triage.Status.DISCARDED
    ).exists()


@transaction.atomic
def save_score(entity, result: ScoreResult, ctx: ScoringContext) -> Score:
    """Grava (ou substitui) o `Score` de uma oportunidade ou organização."""
    content_type = ContentType.objects.get_for_model(type(entity))
    score, _ = Score.objects.update_or_create(
        content_type=content_type,
        object_id=entity.pk,
        defaults={
            "profile": result.profile,
            "scoring_version": SCORING_VERSION,
            "total": result.total,
            "label": result.label,
            "confidence": result.confidence,
            "gated": result.gated,
            "gate_kind": result.gate_kind,
            "gate_reason": result.gate_reason,
            "breakdown": result.breakdown,
            "alerts": result.alerts,
            "raw_sum": result.raw_sum,
            "computed_at": ctx.now,
        },
    )
    return score
