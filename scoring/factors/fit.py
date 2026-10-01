"""F — Fit: compatibilidade com o que a Scorpion Bits sabe fazer (catálogo + portfólio)."""

from __future__ import annotations

from dataclasses import dataclass

from core.models import Opportunity, ServiceOffering
from core.services.normalize import name_key
from scoring.factors import EvidenceIndex, FactorResult, ScoringContext, build, fmt, no_data

FIELDS = ("categories", "description", "requirements_text", "title", "themes")

KEYWORD_BASE = 0.6  # primeira palavra-chave do serviço no texto
KEYWORD_STEP = 0.1  # cada palavra-chave a mais
KEYWORD_MAX = 0.9
CATEGORY_ONLY = 0.45  # só a categoria/tipo da oportunidade aponta para o serviço
UNRELATED = 0.2  # há texto, mas nada conversa com o catálogo
PROOF_BONUS = 0.1  # portfólio público que comprova o serviço

# Categoria da oportunidade -> categorias de serviço que ela sugere.
CATEGORY_SERVICES = {
    "games": {"games", "education"},
    "education": {"education"},
    "technology": {"software", "web"},
    "innovation": {"software", "games"},
}
# Tipo da oportunidade -> categorias de serviço (participar de jam/hackathon = capacidade de jogos).
KIND_SERVICES = {"game_jam": {"games"}, "hackathon": {"software", "games"}}


@dataclass
class FitDetail:
    result: FactorResult
    service: ServiceOffering | None  # serviço mais aderente (usado na checagem de cobertura MEI)


def _text(opp: Opportunity) -> str:
    cats = " ".join(dict(Opportunity.Category.choices).get(c, c) for c in opp.categories)
    return name_key(f"{opp.title} {opp.description} {opp.requirements_text} {cats}")


def _categories(opp: Opportunity) -> set[str]:
    wanted = set(KIND_SERVICES.get(opp.kind, ()))
    for cat in opp.categories:
        wanted |= CATEGORY_SERVICES.get(cat, set())
    return wanted


def _proof(service: ServiceOffering, ctx: ScoringContext):
    return [p for p in ctx.portfolio if any(s.pk == service.pk for s in p.services.all())]


def fit_factor(opp: Opportunity, ctx: ScoringContext, index: EvidenceIndex) -> FitDetail:
    text = f" {_text(opp)} "
    wanted = _categories(opp)
    if not text.strip() and not wanted:
        return FitDetail(no_data("F", "sem texto nem categoria"), None)

    best: tuple[float, ServiceOffering, str] | None = None
    for service in ctx.services:
        terms = [t for t in (name_key(k) for k in service.keywords) if t and f" {t} " in text]
        if terms:
            value = min(KEYWORD_BASE + KEYWORD_STEP * (len(terms) - 1), KEYWORD_MAX)
            why = f"«{terms[0]}»" + (f" e mais {len(terms) - 1}" if len(terms) > 1 else "")
            why = f"texto cita {why}"
        elif service.category in wanted:
            value, why = CATEGORY_ONLY, "categoria/tipo da oportunidade aponta para o serviço"
        else:
            continue
        if best is None or (value, service.slug) > (best[0], best[1].slug):
            best = (value, service, why)

    if best is None:
        result = build(
            "F", UNRELATED, f"nada conversa com o catálogo de serviços: {fmt(UNRELATED)}",
            index, FIELDS,
        )  # fmt: skip
        return FitDetail(result, None)

    value, service, why = best
    proof = _proof(service, ctx)
    if proof:
        value = min(1.0, value + PROOF_BONUS)
        proof_text = "prova no portfólio: " + ", ".join(p.title for p in proof)
    else:
        proof_text = "sem item de portfólio que comprove"
    explanation = f"serviço «{service.name}» ({why}); {proof_text}: {fmt(value)}"
    return FitDetail(build("F", value, explanation, index, FIELDS), service)
