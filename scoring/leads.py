"""Pontuação de leads (E21): organizações com os perfis `lead.sesc` e `lead.school_course`.

Mesmo motor das oportunidades (`combine`, confiança K, breakdown), com fatores de organização
(`scoring/factors/lead.py`) e gates de memória comercial (ADR-012): opt-out barra; quem já foi
contatado (ou foi há menos de `RECONTACT_DAYS`) recebe nota mas sai como «em andamento», nunca
como lead novo. Sem IA e sem rede.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import Q

from core.models import CompanyProfile, Interaction, Match, Organization
from core.services.suppression import SuppressionIndex
from scoring.engine import ScoreResult, combine
from scoring.factors import EvidenceIndex, ScoringContext
from scoring.factors import lead as lead_factors
from scoring.models import Score
from scoring.profiles import RECONTACT_DAYS, label_for

_Status = Organization.RelationshipStatus
# Qualquer contato já feito: a organização nunca volta como «lead novo».
IN_PROGRESS_STATUSES = {
    _Status.CONTACTED,
    _Status.IN_CONVERSATION,
    _Status.PROPOSAL_SENT,
    _Status.CLIENT,
}


def lead_profile_for(org: Organization) -> str | None:
    """`lead.sesc` (SESC e parecidas), `lead.school_course` (escolas) ou `None` (não é lead)."""
    if org.kind == Organization.Kind.SESC or org.similarity_tags:
        return "lead.sesc"
    if org.network.lower().startswith("sesc"):
        return "lead.sesc"
    if org.kind == Organization.Kind.SCHOOL:
        return "lead.school_course"
    return None


def lead_queryset():
    return Organization.objects.filter(
        Q(kind__in=[Organization.Kind.SESC, Organization.Kind.SCHOOL])
        | Q(network__istartswith="sesc")
        | Q(similarity_tags__len__gt=0)
    ).select_related("municipality")


class LeadData:
    """Leitura em lote do que é por organização: matches, última interação, opt-out, case SESC."""

    def __init__(self, orgs: list[Organization]):
        ids = [o.pk for o in orgs]
        self.matches: dict[int, list[Match]] = defaultdict(list)
        matches = Match.objects.filter(organization_id__in=ids, service__active=True)
        for match in matches.select_related("service").prefetch_related("portfolio_refs"):
            self.matches[match.organization_id].append(match)
        self.last: dict[int, Interaction] = {}
        for item in Interaction.objects.filter(organization_id__in=ids):  # mais recente primeiro
            self.last.setdefault(item.organization_id, item)
        self.suppression = SuppressionIndex.load()
        self.sesc_case = Organization.objects.filter(
            kind=Organization.Kind.SESC, relationship_status=_Status.CLIENT
        ).exists()


def _is_ongoing(org: Organization, today) -> str:
    """Motivo de estar «em andamento», ou vazio se pode ser lead novo."""
    if org.relationship_status in IN_PROGRESS_STATUSES:
        return f"já houve contato: {org.get_relationship_status_display().lower()}"
    last = org.last_interaction_at
    overdue = org.next_action_at is not None and org.next_action_at <= today
    if last is not None and today - last < timedelta(days=RECONTACT_DAYS) and not overdue:
        return f"último contato há menos de {RECONTACT_DAYS} dias"
    return ""


def score_lead(org: Organization, profile: str, ctx: ScoringContext, data: LeadData) -> ScoreResult:
    result = ScoreResult(profile=profile)
    if data.suppression.organization_blocked(org):
        result.gate_kind = Score.GateKind.DO_NOT_CONTACT
        result.gate_reason = "organização em opt-out ou marcada como «não contatar»"
        return result

    matches = data.matches.get(org.pk, [])
    best = lead_factors.main_match(matches)
    company: CompanyProfile | None = ctx.company
    mei = company is not None and company.legal_form == "MEI"
    chance, alerts = lead_factors.chance_factor(
        org, best, data.last.get(org.pk), sesc_case=data.sesc_case, mei_form=mei
    )
    index = EvidenceIndex(org.evidence_items.all())
    factors = [
        lead_factors.value_factor(best),
        lead_factors.fit_factor(best),
        chance,
        lead_factors.timing_factor(org, profile, ctx),
        lead_factors.access_factor(org, best, ctx, index),
        lead_factors.lightness_factor(),
    ]
    total, k, raw_sum, breakdown = combine(profile, factors)
    result.alerts = alerts
    if best is None:
        result.alerts.append("sem match com o catálogo: rode `make match`")
    if not (org.municipality_id):
        result.alerts.append("localização não identificada: o acesso usa valor neutro")
    result.total, result.confidence, result.raw_sum = total, round(k, 4), round(raw_sum, 4)
    result.breakdown = breakdown
    result.label = label_for(total)
    why = _is_ongoing(org, ctx.today)
    if why:
        result.label = Score.Label.ONGOING
        result.alerts.insert(0, f"em andamento ({why}): não é lead novo")
    return result
