"""Rede SESC-SP: uma `Organization(kind=sesc, network="SESC-SP")` por unidade, filha de "SESC-SP".

Lê `data/seeds/sesc_sp.csv` (curadoria manual, sem rede). Colunas: name, municipality, uf, website,
source_url, curated_at (AAAA-MM-DD). Só dados institucionais públicos: nada de nomes ou contatos de
pessoas (ADR-014). A lista envelhece: `curated_at` vira evidência manual de cada unidade.

Unidades já contatadas (E03b) são reconhecidas pelo dedupe (nome + município + rede).
"""

from __future__ import annotations

from collection.base import EvidenceDraft
from collection.connectors.seed_csv import SeedCsvConnector, SeedCsvError
from collection.registry import register

SLUG = "sesc-sp-unidades"
NETWORK = "SESC-SP"


@register(slug=SLUG)
class SescSpConnector(SeedCsvConnector):
    kind = "seed_csv"
    default_path = "data/seeds/sesc_sp.csv"

    def __init__(self, source):
        super().__init__(source)
        self.entity = "organization"

    def _organization(self, data: dict):
        if not data.get("municipality"):
            raise SeedCsvError("municipality é obrigatório.")
        data = {**data, "kind": "sesc", "network": NETWORK, "uf": data.get("uf") or "SP"}
        candidate = super()._organization(data)
        candidate.fields["parent_name"] = NETWORK
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
