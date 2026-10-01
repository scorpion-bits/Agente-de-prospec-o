"""Contrato dos conectores (docs/architecture/connectors.md).

Um conector tem duas partes: `fetch` (acessa a fonte, **sem** efeitos no banco além do cache de
`RawDocument` feito pelo fetcher) e `normalize` (função pura, testável com fixtures). O resto —
dedupe, upsert, evidência, `CollectionRun` — é do runner (`collection.runner`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any, Protocol

from core.models import Source

if TYPE_CHECKING:
    from collection.fetcher import PoliteFetcher
    from collection.models import RawDocument


@dataclass
class RunContext:
    source: Source
    fetcher: PoliteFetcher | None = None
    limit: int | None = None
    dry_run: bool = False
    today: date = field(default_factory=date.today)


@dataclass
class RawItem:
    """Um item bruto como saiu da fonte, com o que prova de onde veio."""

    data: dict[str, Any]
    source_url: str = ""
    raw_document: RawDocument | None = None
    label: str = ""  # identificador curto para logs (ex.: "linha 7"); nunca dado pessoal


@dataclass
class EvidenceDraft:
    """Afirmação a registrar via `record_evidence` junto com o upsert."""

    field: str
    value: Any
    kind: str = "observed"
    method: str = ""  # vazio = `connector:<slug da fonte>`
    source_url: str = ""
    source_name: str = ""
    excerpt: str = ""


@dataclass
class OrganizationCandidate:
    """`fields` usa nomes de `Organization`; os de identificação (nome, município, UF, rede, CNPJ,
    INEP, site) entram no dedupe de `core.services.organizations`."""

    name: str
    fields: dict[str, Any] = field(default_factory=dict)
    evidence: list[EvidenceDraft] = field(default_factory=list)


@dataclass
class OpportunityCandidate:
    """`fields` usa nomes de `Opportunity`. `canonical_key` vazia = regra padrão (connectors.md)."""

    title: str
    fields: dict[str, Any] = field(default_factory=dict)
    canonical_key: str = ""
    evidence: list[EvidenceDraft] = field(default_factory=list)


Candidate = OrganizationCandidate | OpportunityCandidate


class Connector(Protocol):
    slug: str  # igual a `Source.slug` (conectores genéricos usam só `kind`)
    kind: str  # api | feed | html_watch | dataset | seed_csv | search

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        """Busca itens brutos. Usa SEMPRE `ctx.fetcher`. Sem efeitos no banco."""

    def normalize(self, item: RawItem) -> Candidate | None:
        """Converte o item em candidato (com evidências). Função pura. `None` = ignorar."""
