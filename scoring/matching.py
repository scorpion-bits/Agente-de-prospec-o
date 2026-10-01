"""Matching serviço ↔ organização ↔ portfólio por regras (E20, ADR-027).

Sem IA. As regras são dados (`scoring/match_rules.py`); este módulo só as aplica. Cada `Match`
guarda motivos legíveis (a hipótese é `inferred`; os fatos que a sustentam citam a evidência
quando existe) e o portfólio que prova a capacidade (ADR-012). No máximo `MAX_MATCHES` por
organização, os mais fortes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction

from core.models import Evidence, Match, Organization, PortfolioItem, ServiceOffering
from core.services.normalize import name_key
from scoring.match_rules import RULES

METHOD = "rules_v1"
MAX_MATCHES = 3
NO_PROOF_FACTOR = 0.7
MAX_EVIDENCE_TEXTS = 200


@dataclass
class Candidate:
    service: ServiceOffering
    strength: float
    reasons: list[dict] = field(default_factory=list)
    proof: list[PortfolioItem] = field(default_factory=list)


class _Facts:
    """Fatos da organização, lidos uma vez (evidências e textos normalizados)."""

    def __init__(self, organization: Organization):
        self.org = organization
        self.evidence = {e.field: e for e in organization.evidence_items.order_by("retrieved_at")}
        stages = self.evidence.get("education_stages")
        self.stages = [name_key(s) for s in (stages.value if stages else []) or [] if s]
        self.stages_evidence = stages
        self.name_text = name_key(f"{organization.name} {organization.segment}")
        self._texts: list[tuple[str, Evidence | None]] | None = None

    def texts(self):
        if self._texts is None:
            items = [(self.name_text, None)]
            for item in self.org.evidence_items.exclude(excerpt="")[:MAX_EVIDENCE_TEXTS]:
                items.append((name_key(item.excerpt), item))
            self._texts = items
        return self._texts


def _check(cond: dict, facts: _Facts) -> list[dict] | None:
    """Fatos que sustentam a condição, ou `None` se ela não vale."""
    org, found = facts.org, []
    if "kinds" in cond:
        if org.kind not in cond["kinds"]:
            return None
        found.append(
            {"text": f"Tipo da organização: {org.get_kind_display()}.", "kind": "observed"}
        )
    if "tags_any" in cond:
        hit = [t for t in org.similarity_tags if t in cond["tags_any"]]
        if not hit:
            return None
        found.append({"text": f"Tags de similaridade: {', '.join(hit)}.", "kind": "observed"})
    if "network_any" in cond:
        if org.network not in cond["network_any"]:
            return None
        found.append({"text": f"Rede: {org.network}.", "kind": "observed"})
    if "stages_any" in cond or "stages_exact" in cond:
        any_ = cond.get("stages_any", [])
        exact = cond.get("stages_exact", [])
        hit = [s for s in facts.stages if s in exact or any(p in s for p in any_)]
        if not hit:
            return None
        ev = facts.stages_evidence
        found.append(
            {
                "text": "Etapas de ensino informadas: " + ", ".join(ev.value) + ".",
                "kind": "observed",
                "evidence_id": ev.pk,
            }
        )
    if "name_any" in cond:
        if not any(p in facts.name_text for p in cond["name_any"]):
            return None
        found.append({"text": "O nome ou segmento indica a área.", "kind": "observed"})
    if "keywords_any" in cond:
        for text, ev in facts.texts():
            term = next((k for k in cond["keywords_any"] if k in text), None)
            if term:
                reason = {"text": f"Texto da fonte cita «{term}».", "kind": "observed"}
                if ev is not None:
                    reason["evidence_id"] = ev.pk
                found.append(reason)
                break
        else:
            return None
    if "website_status" in cond:
        if org.website_status != cond["website_status"]:
            return None
        found.append(
            {"text": f"Situação do site: {org.get_website_status_display()}.", "kind": "observed"}
        )
    return found if found else None


def find_proof(spec: dict, portfolio: list[PortfolioItem]) -> list[PortfolioItem]:
    tags, kinds = set(spec.get("tags_any", [])), set(spec.get("kinds", []))
    return [
        item
        for item in portfolio
        if (not tags or tags & set(item.capability_tags)) and (not kinds or item.kind in kinds)
    ]


def load_portfolio() -> list[PortfolioItem]:
    """Só itens públicos e já confirmados servem de prova (não se cita o que não é público)."""
    return list(
        PortfolioItem.objects.filter(public=True).exclude(
            status=PortfolioItem.DataStatus.TO_CONFIRM
        )
    )


def match_organization(
    organization: Organization,
    services: dict[str, ServiceOffering],
    portfolio: list[PortfolioItem],
    rules=RULES,
) -> list[Candidate]:
    facts = _Facts(organization)
    best: dict[str, Candidate] = {}
    for rule in rules:
        supports = None
        for cond in rule["when"]:
            supports = _check(cond, facts)
            if supports:
                break
        if not supports:
            continue
        proof = find_proof(rule.get("proof", {}), portfolio)
        strength = rule["strength"] * (1 if proof else NO_PROOF_FACTOR)
        for slug in rule["services"]:
            service = services.get(slug)
            if service is None:
                continue
            reasons = [{"text": rule["reason"], "kind": "inferred", "evidence_id": None}] + [
                {"evidence_id": None, **s} for s in supports
            ]
            reasons.append(
                {
                    "text": (
                        "Prova: " + ", ".join(p.title for p in proof) + "."
                        if proof
                        else "Sem item de portfólio que comprove: força reduzida."
                    ),
                    "kind": "observed" if proof else "inferred",
                    "evidence_id": None,
                }
            )
            current = best.get(slug)
            if current is None or strength > current.strength:
                best[slug] = Candidate(service, round(strength, 3), reasons, proof)
    ranked = sorted(best.values(), key=lambda c: (-c.strength, c.service.slug))
    return ranked[:MAX_MATCHES]


@transaction.atomic
def save_matches(organization: Organization, candidates: list[Candidate]) -> tuple[int, int, int]:
    """Grava (criados, atualizados, removidos); remove matches `rules_v1` que deixaram de valer."""
    keep = {c.service.pk for c in candidates}
    stale = Match.objects.filter(organization=organization, method=METHOD).exclude(
        service_id__in=keep
    )
    removed = stale.count()
    stale.delete()
    created = updated = 0
    for cand in candidates:
        match, was_created = Match.objects.update_or_create(
            organization=organization,
            service=cand.service,
            method=METHOD,
            defaults={"strength": cand.strength, "reasons": cand.reasons},
        )
        match.portfolio_refs.set(cand.proof)
        created += was_created
        updated += not was_created
    return created, updated, removed
