"""C — Chance: probabilidade de sucesso (elegibilidade, concorrência provável, relacionamento)."""

from __future__ import annotations

from core.models import Opportunity, Organization
from scoring.eligibility import Eligibility
from scoring.factors import EvidenceIndex, FactorResult, build, clamp, fmt

FIELDS = (
    "eligible_legal_forms",
    "requires_legal_entity",
    "exclusive_small_business",
    "min_company_age_months",
    "required_cnaes",
    "scope",
)
BASE = 0.5

# Concorrência provável pela abrangência: aberto ao mundo ↓, local ↑.
SCOPE_ADJUST = {
    "municipal": (0.1, "abrangência municipal: menos concorrência"),
    "regional": (0.1, "abrangência regional: menos concorrência"),
    "national": (-0.05, "abrangência nacional: concorrência maior"),
    "international": (-0.15, "abrangência internacional: concorrência muito maior"),
}
# Relacionamento do organizador com a Scorpion Bits (memória comercial, ADR-012).
RELATIONSHIP_ADJUST = {
    "client": (0.25, "organizador já é cliente"),
    "proposal_sent": (0.15, "já enviamos proposta ao organizador"),
    "in_conversation": (0.15, "já conversamos com o organizador"),
    "contacted": (0.05, "já contatamos o organizador"),
    "lost": (-0.15, "relacionamento com o organizador consta como perdido"),
}
SAME_NETWORK_BONUS = 0.15


def _relationship(organizer: Organization | None) -> list[tuple[float, str]]:
    if organizer is None:
        return []
    out = []
    if organizer.relationship_status in RELATIONSHIP_ADJUST:
        out.append(RELATIONSHIP_ADJUST[organizer.relationship_status])
    if organizer.network and organizer.relationship_status != "client":
        same = (
            Organization.objects.filter(
                network=organizer.network,
                relationship_status=Organization.RelationshipStatus.CLIENT,
            )
            .exclude(pk=organizer.pk)
            .exists()
        )
        if same:
            out.append(
                (SAME_NETWORK_BONUS, f"mesma rede ({organizer.network}) de quem já nos contratou")
            )
    return out


def chance_factor(opp: Opportunity, eligibility: Eligibility, index: EvidenceIndex) -> FactorResult:
    steps = list(eligibility.adjustments)
    if opp.scope in SCOPE_ADJUST:
        steps.append(SCOPE_ADJUST[opp.scope])
    steps += _relationship(opp.organizer)

    raw = BASE + sum(delta for delta, _ in steps)
    value = clamp(raw)
    if steps:
        parts = "; ".join(f"{'+' if d > 0 else '−'}{fmt(abs(d))} {why}" for d, why in steps)
        explanation = f"base {fmt(BASE)}; {parts} = {fmt(value)}"
    else:
        explanation = f"sem sinais a favor nem contra: {fmt(value)}"
    known = bool(steps) or any(
        (
            opp.eligible_legal_forms,
            opp.exclusive_small_business is not None,
            opp.min_company_age_months,
            opp.required_cnaes,
            opp.requires_legal_entity != Opportunity.LegalEntityRequirement.UNKNOWN,
        )
    )
    return build("C", value, explanation, index, FIELDS, known=known)
