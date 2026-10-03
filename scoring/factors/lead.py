"""Fatores de lead (E21): `(organização, match principal, contexto) -> FactorResult`.

Mesmas seis letras das oportunidades (`scoring/profiles.py`), com insumos de organização:
ticket do serviço, força do match, memória comercial, sazonalidade, geo e contatabilidade.
Dado digitado por pessoas (catálogo, interações) conta como suporte 1; o match é hipótese (0,5).
"""

from __future__ import annotations

from decimal import Decimal

from core.models import ContactPoint, GeoProfile, Interaction, Match, Organization, ServiceOffering
from scoring.eligibility import PENALTY_NOT_COVERED, PENALTY_VERIFY
from scoring.factors import (
    NEUTRAL,
    EvidenceIndex,
    FactorResult,
    ScoringContext,
    brl,
    build,
    clamp,
    fmt,
    no_data,
)
from scoring.factors.access import (
    CONTACT_DIRECT,
    CONTACT_FORM,
    CONTACT_NONE,
    contact_kinds,
)
from scoring.factors.chance import BASE, _relationship
from scoring.factors.value import AMOUNT_BANDS
from scoring.geo import geo_relevance
from scoring.profiles import FOLLOW_UP_AHEAD_DAYS, FOLLOW_UP_VALUE, SEASONALITY

GEO_FIELDS = ("municipality_name", "location", "address")
SIMILAR_TO_CASE_BONUS = 0.05
POSITIVE_REPLY_BONUS = 0.1
NO_REPLY_PENALTY = -0.05
MONTHS = (
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro"
).split()


def ticket_of(service: ServiceOffering) -> Decimal | None:
    """Ticket típico: o ponto médio da faixa (ou o único limite informado)."""
    low, high = service.typical_ticket_min_brl, service.typical_ticket_max_brl
    if low is not None and high is not None:
        return (low + high) / 2
    return high if high is not None else low


def main_match(matches: list[Match]) -> Match | None:
    """O match mais forte (empate: o de maior ticket). V, F, A e a cobertura MEI partem dele."""
    if not matches:
        return None
    return max(matches, key=lambda m: (m.strength, ticket_of(m.service) or Decimal(0)))


def value_factor(match: Match | None) -> FactorResult:
    if match is None:
        return no_data("V", "nenhum serviço do catálogo combina com a organização")
    ticket = ticket_of(match.service)
    if ticket is None:
        return no_data("V", f"o serviço «{match.service.name}» está sem ticket no catálogo")
    value = next(v for floor, v in AMOUNT_BANDS if ticket >= floor)
    text = f"ticket típico de «{match.service.name}» ≈ {brl(ticket)} (catálogo): {fmt(value)}"
    return FactorResult("V", value, text, [], 1.0)


def fit_factor(match: Match | None) -> FactorResult:
    if match is None:
        return FactorResult(
            "F", 0.0, "nenhum match com o catálogo (rode `make match`): 0,0", [], 0.0
        )
    proof = [p.title for p in match.portfolio_refs.all()]
    proof_text = (
        f"; prova no portfólio: {', '.join(proof)}" if proof else "; sem prova no portfólio"
    )
    ids = sorted({r["evidence_id"] for r in match.reasons if r.get("evidence_id")})
    text = f"match com «{match.service.name}», força {fmt(match.strength)}{proof_text}"
    return FactorResult("F", round(clamp(match.strength), 4), text, ids, 1.0 if ids else 0.5)


def chance_factor(
    org: Organization,
    match: Match | None,
    last: Interaction | None,
    *,
    sesc_case: bool,
    mei_form: bool,
) -> tuple[FactorResult, list[str]]:
    """Chance: base 0,5 ± relacionamento, rede com case, resposta anterior e cobertura MEI."""
    steps = _relationship(org)
    alerts: list[str] = []
    if (
        sesc_case
        and org.similarity_tags
        and org.kind != "sesc"
        and "sesc" not in org.network.lower()
    ):
        steps.append((SIMILAR_TO_CASE_BONUS, "parecida com o SESC, que já nos contratou"))
    if last is not None and last.outcome == Interaction.Outcome.POSITIVE:
        steps.append((POSITIVE_REPLY_BONUS, "a última interação teve resposta positiva"))
    elif last is not None and last.outcome == Interaction.Outcome.NO_RESPONSE:
        steps.append((NO_REPLY_PENALTY, "a última tentativa ficou sem resposta"))
    known = bool(steps)
    service = match.service if match is not None else None
    if mei_form and service is not None:
        coverage = ServiceOffering.MeiCoverage
        if service.mei_coverage == coverage.NOT_COVERED:
            steps.append((PENALTY_NOT_COVERED, f"«{service.name}» exigiria ME (fora do MEI)"))
            alerts.append(f"o serviço «{service.name}» exigiria ME (fora das atividades do MEI)")
        elif service.mei_coverage == coverage.VERIFY:
            steps.append(
                (PENALTY_VERIFY, f"confirmar com o contador se o MEI cobre «{service.name}»")
            )
    value = clamp(BASE + sum(delta for delta, _ in steps))
    if steps:
        parts = "; ".join(f"{'+' if d > 0 else '−'}{fmt(abs(d))} {why}" for d, why in steps)
        text = f"base {fmt(BASE)}; {parts} = {fmt(value)}"
    else:
        text = f"sem sinais a favor nem contra: {fmt(value)}"
    return FactorResult("C", round(value, 4), text, [], 1.0 if known else 0.0), alerts


def timing_factor(org: Organization, profile: str, ctx: ScoringContext) -> FactorResult:
    """Timing: sazonalidade do perfil e follow-up vencendo (vale o maior dos dois)."""
    parts, value, support = [], NEUTRAL, 0.0
    season = SEASONALITY.get(profile)
    if season:
        month = ctx.today.month
        value, support = season[month], 0.5
        parts.append(f"sazonalidade escolar em {MONTHS[month - 1]}: {fmt(value)}")
    else:
        parts.append("sem sazonalidade conhecida para o perfil (SESC a confirmar na E01b)")
    due = org.next_action_at
    if due is not None and (due - ctx.today).days <= FOLLOW_UP_AHEAD_DAYS:
        late = (ctx.today - due).days
        when = f"vencido há {late} dias" if late > 0 else "vence em breve"
        parts.append(f"follow-up {when}: {fmt(FOLLOW_UP_VALUE)}")
        value, support = max(value, FOLLOW_UP_VALUE), 1.0
    return FactorResult("T", round(value, 4), "; ".join(parts) + f" → {fmt(value)}", [], support)


def contactability(org: Organization) -> tuple[float, str]:
    kinds = contact_kinds(org.pk)
    if kinds & {ContactPoint.Kind.EMAIL, ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP}:
        return CONTACT_DIRECT, "e-mail/telefone institucional conhecido"
    if kinds:
        return CONTACT_FORM, "só formulário ou rede social"
    return CONTACT_NONE, "nenhuma forma de contato conhecida"


def access_factor(
    org: Organization, match: Match | None, ctx: ScoringContext, index: EvidenceIndex
) -> FactorResult:
    profile = match.service.geo_profile if match else GeoProfile.ONSITE_RECURRING
    geo = geo_relevance(org, profile, home=ctx.home)
    contact, contact_text = contactability(org)
    value = (geo.value if geo.value is not None else 0.0) * contact
    text = f"{geo.explanation}; {contact_text} ({fmt(contact)}): {fmt(value)}"
    return build("A", value, text, index, GEO_FIELDS, known=geo.location_known)


def lightness_factor() -> FactorResult:
    return no_data("L", "esforço do serviço não está no catálogo")
