"""Conector genérico `seed_csv`: lê um CSV curado à mão (sem rede).

Configure uma `Source` com `kind=seed_csv` e `config`:

    {"path": "data/seeds/minhas_fontes.csv", "entity": "organization"}   # ou "opportunity"

`path` relativo vale a partir da raiz do repositório. CSV com dados pessoais fica em
`data/private/` (ADR-014). Colunas de organização: name, kind, network, municipality, uf,
website, segment, cnpj, inep_code, source_url. De oportunidade: title, kind, official_url,
organizer_name, description, deadline (AAAA-MM-DD), municipality, uf, source_url.

Evidência: linha com `source_url` vira fato **observado** (método `connector:<slug>`); sem URL é
curadoria humana (**manual**, método `human`), nunca "observado".
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import date, datetime, time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from collection.base import (
    EvidenceDraft,
    OpportunityCandidate,
    OrganizationCandidate,
    RawItem,
    RunContext,
)
from collection.registry import register
from core.models import Opportunity, Organization


class SeedCsvError(ValueError):
    pass


def _choice(choices, value: str, field: str) -> str:
    if not value:
        return choices.values[-1] if "other" in choices.values else ""
    for key, label in choices.choices:
        if value.casefold() in (key.casefold(), str(label).casefold()):
            return key
    raise SeedCsvError(f"{field} {value!r} inválido (use: {', '.join(choices.values)}).")


@register(kind="seed_csv")
class SeedCsvConnector:
    kind = "seed_csv"

    def __init__(self, source):
        self.source = source
        self.slug = source.slug
        config = source.config or {}
        if not config.get("path"):
            raise SeedCsvError('Configure {"path": "..."} na fonte.')
        self.path = Path(config["path"])
        if not self.path.is_absolute():
            self.path = Path(settings.BASE_DIR) / self.path
        self.entity = config.get("entity", "organization")
        if self.entity not in ("organization", "opportunity"):
            raise SeedCsvError('"entity" deve ser "organization" ou "opportunity".')

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        try:
            with self.path.open(encoding="utf-8-sig", newline="") as handle:
                for number, row in enumerate(csv.DictReader(handle), start=2):
                    data = {k: (v or "").strip() for k, v in row.items() if k}
                    if any(data.values()):
                        yield RawItem(
                            data=data,
                            source_url=data.get("source_url", ""),
                            label=f"linha {number}",
                        )
        except OSError as exc:
            raise SeedCsvError(f"Não foi possível ler {self.path.name}: {exc.strerror}") from exc

    def normalize(self, item: RawItem):
        build = self._organization if self.entity == "organization" else self._opportunity
        return build(item.data)

    def _evidence(self, data: dict, values: dict) -> list[EvidenceDraft]:
        url = data.get("source_url", "")
        kind, method = ("observed", "") if url else ("manual", "human")
        return [
            EvidenceDraft(
                field=name,
                value=value,
                kind=kind,
                method=method,
                source_url=url,
                source_name=self.path.name,
            )
            for name, value in values.items()
            if value not in ("", None)
        ]

    def _organization(self, data: dict):
        name = data.get("name", "")
        if not name:
            raise SeedCsvError("name é obrigatório.")
        fields = {
            "kind": _choice(Organization.Kind, data.get("kind", ""), "kind"),
            "network": data.get("network", ""),
            "municipality_name": data.get("municipality", ""),
            "uf": data.get("uf", "").upper(),
            "website": data.get("website", ""),
            "segment": data.get("segment", ""),
            "cnpj": data.get("cnpj", "") or None,
            "inep_code": data.get("inep_code", "") or None,
        }
        fields = {k: v for k, v in fields.items() if v}
        claims = {
            "name": name,
            **{k: v for k, v in fields.items() if k not in ("cnpj", "inep_code")},
        }
        return OrganizationCandidate(
            name=name, fields=fields, evidence=self._evidence(data, claims)
        )

    def _opportunity(self, data: dict):
        title = data.get("title", "")
        if not title:
            raise SeedCsvError("title é obrigatório.")
        fields = {
            "kind": _choice(Opportunity.Kind, data.get("kind", ""), "kind"),
            "official_url": data.get("official_url", ""),
            "organizer_name": data.get("organizer_name", ""),
            "description": data.get("description", ""),
            "municipality_name": data.get("municipality", ""),
            "uf": data.get("uf", "").upper(),
        }
        if data.get("deadline"):
            try:
                day = date.fromisoformat(data["deadline"])
            except ValueError as exc:
                raise SeedCsvError(f"deadline {data['deadline']!r} inválido (AAAA-MM-DD).") from exc
            fields["deadline_at"] = timezone.make_aware(datetime.combine(day, time(23, 59)))
        fields = {k: v for k, v in fields.items() if v}
        claims = {"title": title, **fields}
        if "deadline_at" in claims:
            claims["deadline_at"] = claims["deadline_at"].date().isoformat()
        return OpportunityCandidate(
            title=title, fields=fields, evidence=self._evidence(data, claims)
        )
