"""Importa o histórico comercial de um CSV **privado** (padrão: data/private/interactions.csv).

O arquivo tem dados pessoais (cargo do contato) e nunca vai para o git (ADR-014): comece copiando
`data/seeds/interactions.template.csv` para `data/private/interactions.csv` e preenchendo. A saída
deste comando traz só contagens, porque logs do GitHub Actions são públicos.

Colunas: organization_name,network,municipality,uf,occurred_at,kind,channel,service_slug,
contact_role,summary,outcome,next_action,next_action_at,data_status,notes.

- Organizações passam por `get_or_create_organization` (dedupe: nunca duplica uma já conhecida).
  Com `network`, a unidade recebe como `parent` a organização da rede (ex.: SESC-SP).
- Linhas `data_status=pendente` entram **sem datas inventadas** e podem ser completadas depois:
  rodar de novo com a data preenchida atualiza o registro pendente, sem duplicar.
- Registros já confirmados não são tocados (use `--update` para sobrescrever).
- A chave de uma interação é (organização, tipo, resumo).
"""

from datetime import date
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Interaction, Organization, ServiceOffering
from core.services.csv_import import choice_value, read_rows
from core.services.organizations import get_or_create_organization

REQUIRED = ("organization_name", "kind")
PENDING_WORDS = {"pendente", "pending"}
NETWORK_ORG_DEFAULTS = {"similarity_tags": ["sistema_s"]}


def parse_date(value, field, line):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CommandError(f"Linha {line}: {field} {value!r} inválido (use AAAA-MM-DD).") from exc


def org_kind(name):
    return Organization.Kind.SESC if name.strip().upper().startswith("SESC") else None


class Command(BaseCommand):
    help = "Importa interações (memória comercial) de um CSV privado; idempotente."

    def add_arguments(self, parser):
        parser.add_argument(
            "file", nargs="?", type=Path, default=Path("data/private/interactions.csv")
        )
        parser.add_argument("--update", action="store_true", help="Sobrescreve já confirmados.")
        parser.add_argument("--dry-run", action="store_true", help="Valida sem gravar.")

    def handle(self, *args, file, update, dry_run, **options):
        rows = read_rows(file, REQUIRED)
        counts = {"organizations": 0, "criada": 0, "atualizada": 0, "mantida": 0}
        with transaction.atomic():
            for line, row in rows:
                self._import_row(line, row, update, counts)
            if dry_run:
                transaction.set_rollback(True)
        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            f"{prefix}Interações: {counts['criada']} criada(s), {counts['atualizada']} "
            f"atualizada(s), {counts['mantida']} mantida(s); "
            f"{counts['organizations']} organização(ões) nova(s)."
        )

    def _organization(self, line, row, counts):
        name = row.get("organization_name", "")
        if not name:
            raise CommandError(f"Linha {line}: organization_name é obrigatório.")
        network = row.get("network", "")
        kind = org_kind(name) or (org_kind(network) if network else None)
        defaults = {"kind": kind} if kind else {}
        parent = None
        if network:
            parent, created = get_or_create_organization(
                network,
                network=network,
                defaults={**defaults, **(NETWORK_ORG_DEFAULTS if kind else {})},
            )
            counts["organizations"] += created
        try:
            organization, created = get_or_create_organization(
                name,
                municipality_name=row.get("municipality", ""),
                uf=row.get("uf", ""),
                network=network,
                defaults=defaults,
            )
        except ValidationError as exc:
            raise CommandError(f"Linha {line}: {exc.message_dict}") from exc
        counts["organizations"] += created
        if parent and organization.parent_id is None and organization.pk != parent.pk:
            organization.parent = parent
            organization.save(update_fields=["parent", "updated_at"])
        return organization

    def _import_row(self, line, row, update, counts):
        kind = choice_value(Interaction.Kind, row["kind"], "kind", line)
        channel = choice_value(
            Interaction.Channel, row.get("channel", ""), "channel", line, blank_ok=True
        )
        outcome = choice_value(
            Interaction.Outcome, row.get("outcome", "") or "pending", "outcome", line
        )
        pending = row.get("data_status", "").casefold() in PENDING_WORDS
        occurred_at = parse_date(row.get("occurred_at", ""), "occurred_at", line)
        next_action_at = parse_date(row.get("next_action_at", ""), "next_action_at", line)
        service = None
        if row.get("service_slug"):
            service = ServiceOffering.objects.filter(slug=row["service_slug"]).first()
            if service is None:
                raise CommandError(
                    f"Linha {line}: serviço {row['service_slug']!r} fora do catálogo."
                )
        organization = self._organization(line, row, counts)
        summary = row.get("summary", "")

        interaction = Interaction.objects.filter(
            organization=organization, kind=kind, summary=summary
        ).first()
        if interaction is not None:
            completing = interaction.data_status == Interaction.DataStatus.PENDING and not pending
            if not (update or completing):
                counts["mantida"] += 1
                return
        is_new = interaction is None
        interaction = interaction or Interaction(organization=organization, kind=kind)
        interaction.summary = summary
        interaction.channel = channel
        interaction.service = service
        interaction.contact_name_role = row.get("contact_role", "")
        interaction.outcome = outcome
        interaction.occurred_at = occurred_at
        interaction.next_action = row.get("next_action", "")
        interaction.next_action_at = next_action_at
        interaction.data_status = (
            Interaction.DataStatus.PENDING if pending else Interaction.DataStatus.CONFIRMED
        )
        try:
            interaction.full_clean()
        except ValidationError as exc:
            raise CommandError(f"Linha {line}: {exc.message_dict}") from exc
        interaction.save()
        counts["criada" if is_new else "atualizada"] += 1
