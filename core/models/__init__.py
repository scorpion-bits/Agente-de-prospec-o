"""Modelos de dados de `core` — ver docs/architecture/data-model.md.

O módulo virou pacote na E03b (eram ~1.000 linhas); os nomes públicos continuam importáveis de
`core.models`, então nenhum import existente muda e não há migration.

Decisões herdadas da E03:
- `Evidence` e `Triage` apontam para a entidade por `GenericForeignKey` (ADR-017).
- Listas de strings são `ArrayField` do PostgreSQL; JSON só para estruturas aninhadas (ADR-018).
- Município: `municipality_name` + `uf` guardam o texto como veio da fonte; `municipality` (FK, E12)
  é a versão resolvida pela tabela do IBGE, preenchida ao salvar quando o nome e a UF casam.
- `Interaction`, `PortfolioItem` e `CompanyProfile` (E03b): memória comercial, portfólio e perfil.
- `Evidence.raw_document` entra na E04, junto com `RawDocument`.
- Identificadores externos únicos e opcionais ficam NULL (nunca "") quando ausentes.
"""

from core.models.catalog import Match, ServiceOffering
from core.models.common import (
    ENTITY_CHOICES,
    ENTITY_MODELS,
    EVIDENCE_FIELD_PATTERN,
    EVIDENCE_METHOD_PATTERN,
    UF_VALIDATOR,
    UNIT_INTERVAL,
    GeoProfile,
    LegalForm,
    missing_entity_error,
)
from core.models.company import CompanyProfile
from core.models.contact import ContactPoint, Suppression
from core.models.evidence import Evidence, Triage
from core.models.interaction import FollowUp, Interaction
from core.models.municipality import UF_BY_IBGE_CODE, Municipality
from core.models.opportunity import Opportunity
from core.models.organization import Organization
from core.models.portfolio import PortfolioItem
from core.models.source import Source

__all__ = [
    "ENTITY_CHOICES",
    "ENTITY_MODELS",
    "EVIDENCE_FIELD_PATTERN",
    "EVIDENCE_METHOD_PATTERN",
    "UF_BY_IBGE_CODE",
    "UF_VALIDATOR",
    "UNIT_INTERVAL",
    "CompanyProfile",
    "ContactPoint",
    "Evidence",
    "FollowUp",
    "GeoProfile",
    "Interaction",
    "LegalForm",
    "Match",
    "Municipality",
    "Opportunity",
    "Organization",
    "PortfolioItem",
    "ServiceOffering",
    "Source",
    "Suppression",
    "Triage",
    "missing_entity_error",
]
