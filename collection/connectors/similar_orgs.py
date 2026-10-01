"""Organizações parecidas com o SESC (E17b): redes e instituições com o mesmo perfil de compra.

Lê `data/seeds/similar_orgs.csv` (curadoria manual, sem rede). Colunas: name, kind, network, parent,
municipality, uf, website, tags, source_url, curated_at. `tags` usa `|` e só aceita o vocabulário de
`core.services.similarity`. `parent` liga a unidade à mãe da rede (linha da própria mãe vem antes,
sem município). Só dados institucionais públicos, nunca pessoas
(ADR-014).

Não repita o mesmo `website` em várias unidades: o dedupe por domínio as fundiria.
O site da rede fica
na linha da mãe. Sem `source_url` a evidência é manual (`human`), nunca "observada" (ADR-004).
"""

from __future__ import annotations

from collection.base import EvidenceDraft
from collection.connectors.seed_csv import SeedCsvConnector, SeedCsvError
from collection.registry import register
from core.services.similarity import clean_tags

SLUG = "orgs-parecidas-sesc"


@register(slug=SLUG)
class SimilarOrgsConnector(SeedCsvConnector):
    kind = "seed_csv"
    default_path = "data/seeds/similar_orgs.csv"

    def __init__(self, source):
        super().__init__(source)
        self.entity = "organization"

    def _organization(self, data: dict):
        try:
            tags = clean_tags(data.get("tags", ""))
        except ValueError as exc:
            raise SeedCsvError(str(exc)) from exc
        if not tags:
            raise SeedCsvError("tags é obrigatório (ao menos uma tag de similaridade).")
        candidate = super()._organization(data)
        candidate.fields["similarity_tags"] = tags
        if data.get("parent"):
            candidate.fields["parent_name"] = data["parent"]
        candidate.evidence.append(
            EvidenceDraft(
                field="similarity_tags",
                value=", ".join(tags),
                kind="manual",
                method="human",
                source_name=self.path.name,
            )
        )
        if data.get("curated_at"):
            candidate.evidence.append(
                EvidenceDraft(
                    field="unit_list_curated_at",
                    value=data["curated_at"],
                    kind="manual",
                    method="human",
                    source_name=self.path.name,
                )
            )
        return candidate
