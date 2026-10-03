"""A — Acesso: dá para chegar lá? Relevância geográfica `G` × contatabilidade."""

from __future__ import annotations

from core.models import ContactPoint, GeoProfile, Opportunity
from scoring.factors import EvidenceIndex, FactorResult, ScoringContext, build, fmt
from scoring.geo import GeoResult, geo_relevance

FIELDS = ("municipality_name", "modality", "scope", "eligible_regions", "location")
EDITAL_KINDS = {"edital", "program", "contest", "procurement", "call_for_partners"}

# Contatabilidade: a melhor via de chegar ao organizador (só contatos `usable()`, LGPD).
CONTACT_DIRECT = 1.0  # e-mail ou telefone institucional
CONTACT_FORM = 0.7  # só formulário ou rede social
CONTACT_OFFICIAL_URL = 0.8  # inscrição pela página oficial da oportunidade
CONTACT_NONE = 0.3


def geo_profile_for(opp: Opportunity) -> str:
    if opp.modality == Opportunity.Modality.ONLINE:
        return GeoProfile.ONLINE
    if opp.kind in EDITAL_KINDS:
        return GeoProfile.EDITAL_SCOPE
    return GeoProfile.ONSITE_EVENT


def geo_for(opp: Opportunity, ctx: ScoringContext) -> GeoResult:
    return geo_relevance(opp, geo_profile_for(opp), home=ctx.home)


def contact_kinds(organization_id: int | None) -> set[str]:
    """Tipos dos contatos `usable()` (opt-out respeitado) da organização."""
    if not organization_id:
        return set()
    return set(
        ContactPoint.objects.usable()
        .filter(organization_id=organization_id)
        .values_list("kind", flat=True)
    )


def contactability(opp: Opportunity) -> tuple[float, str]:
    kinds = contact_kinds(opp.organizer_id)
    if kinds & {ContactPoint.Kind.EMAIL, ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP}:
        return CONTACT_DIRECT, "organizador com e-mail/telefone institucional"
    if opp.official_url:
        return CONTACT_OFFICIAL_URL, "inscrição pela página oficial"
    if kinds:
        return CONTACT_FORM, "organizador só com formulário ou rede social"
    return CONTACT_NONE, "nenhuma forma de contato conhecida"


def access_factor(opp: Opportunity, geo: GeoResult, index: EvidenceIndex) -> FactorResult:
    contact, contact_text = contactability(opp)
    value = (geo.value if geo.value is not None else 0.0) * contact
    explanation = f"{geo.explanation}; {contact_text} ({fmt(contact)}): {fmt(value)}"
    return build("A", value, explanation, index, FIELDS, known=geo.location_known)
