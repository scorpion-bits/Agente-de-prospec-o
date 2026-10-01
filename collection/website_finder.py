"""Descoberta de site oficial (E18): busca → páginas dos candidatos → validação → gravação.

A validação é do `extraction/website.py` (pura). Aqui ficam a rede (busca com cache e
`PoliteFetcher`) e os efeitos: `website`, `website_status` e evidências. Sem IA.
"""

from __future__ import annotations

from collection.fetcher import FetchError, PoliteFetcher
from collection.search.base import SearchProvider
from core.models import Organization
from core.services.evidence import record_evidence
from core.services.normalize import normalize_domain
from extraction.website import (
    MAX_CANDIDATES,
    CandidateVerdict,
    Decision,
    decide,
    evaluate_candidate,
    is_blocked_domain,
)

METHOD = "rule:website_match"
STATUS = Organization.WebsiteStatus


def build_query(organization: Organization) -> str:
    return " ".join(
        part
        for part in (organization.name, organization.municipality_name, organization.uf)
        if part
    )


def known_domains() -> dict[str, int]:
    """Domínio → pk das organizações que já têm site (um domínio só pode ser de uma organização)."""
    domains = {}
    for pk, website in Organization.objects.exclude(website="").values_list("pk", "website"):
        if domain := normalize_domain(website):
            domains.setdefault(domain, pk)
    return domains


def find_website(
    organization: Organization,
    provider: SearchProvider,
    fetcher: PoliteFetcher,
    *,
    taken: dict[str, int] | None = None,
) -> Decision:
    """Procura o site de `organization` sem gravar nada na organização (só cache de busca/páginas).

    Levanta `SearchError` se a busca falhar (a organização fica como estava, para nova tentativa).
    """
    results = provider.search(build_query(organization))
    verdicts: list[CandidateVerdict] = []
    seen_domains: set[str] = set()
    for result in results:
        domain = normalize_domain(result.url)
        if domain in seen_domains or is_blocked_domain(result.url):
            continue
        if len(seen_domains) >= MAX_CANDIDATES:
            break
        seen_domains.add(domain)
        try:
            html = fetcher.fetch(result.url).text
        except FetchError:  # robots, bloqueio, 404, binário, limite: não dá para conferir a página
            html = None
        verdicts.append(
            evaluate_candidate(
                result,
                name=organization.name,
                municipality=organization.municipality_name,
                page_html=html,
            )
        )
    decision = decide(verdicts)
    if decision.status == STATUS.FOUND:
        owner = (taken or {}).get(normalize_domain(decision.url))
        if owner is not None and owner != organization.pk:
            return Decision(
                STATUS.AMBIGUOUS,
                "",
                None,
                [decision.chosen],
                "domínio já usado por outra organização (rede ou duplicata?)",
            )
    return decision


def apply_decision(organization: Organization, decision: Decision, *, provider_name: str):
    """Grava o resultado: site + situação + evidência (inferida por regra, ADR-004)."""
    organization.website_status = decision.status
    if decision.status == STATUS.FOUND:
        organization.website = decision.url
        organization.save(update_fields=["website", "website_status", "updated_at"])
        chosen = decision.chosen
        record_evidence(
            organization,
            "website",
            decision.url,
            kind="inferred",
            method=METHOD,
            source_url=chosen.url,
            source_name=f"busca:{provider_name}",
            excerpt=chosen.excerpt,
            source_text=chosen.page_text,
        )
        return
    organization.save(update_fields=["website_status", "updated_at"])
    if decision.status == STATUS.AMBIGUOUS:  # o humano decide entre os candidatos
        for candidate in (decision.candidates or [])[:MAX_CANDIDATES]:
            record_evidence(
                organization,
                "website_candidate",
                candidate.url,
                kind="inferred",
                method=METHOD,
                source_url=candidate.url,
                source_name=f"busca:{provider_name}",
            )
