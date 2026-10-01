"""Modelos de dados de `core` — ver docs/architecture/data-model.md.

O módulo virou pacote na E03b (eram ~1.000 linhas); os nomes públicos continuam importáveis de
`core.models`, então nenhum import existente muda e não há migration.

Decisões herdadas da E03:
- `Evidence` e `Triage` apontam para a entidade por `GenericForeignKey` (ADR-017).
- Listas de strings são `ArrayField` do PostgreSQL; JSON só para estruturas aninhadas (ADR-018).
- Município é provisório (`municipality_name` + `uf`) até a E12 trazer a tabela do IBGE.
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
from core.models.contact import ContactPoint, Suppression
from core.models.evidence import Evidence, Triage
from core.models.opportunity import Opportunity
from core.models.organization import Organization
from core.models.source import Source

__all__ = [
    "ENTITY_CHOICES",
    "ENTITY_MODELS",
    "EVIDENCE_FIELD_PATTERN",
    "EVIDENCE_METHOD_PATTERN",
    "UF_VALIDATOR",
    "UNIT_INTERVAL",
    "ContactPoint",
    "Evidence",
    "GeoProfile",
    "LegalForm",
    "Match",
    "Opportunity",
    "Organization",
    "ServiceOffering",
    "Source",
    "Suppression",
    "Triage",
    "missing_entity_error",
]
