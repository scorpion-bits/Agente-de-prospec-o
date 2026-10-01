"""Importa o portfólio de um CSV (padrão: data/seeds/portfolio.csv). Idempotente por `slug`.

Itens que já existem são mantidos (o admin pode ter editado); `--update` sobrescreve com o CSV.
Colunas: slug,title,kind,year,description,public_url,url_source,services,capability_tags,public,
status,notes. `services` e `capability_tags` separam valores por `;`; `services` usa os slugs do
catálogo. Linhas com `status` vazio entram como `complete`.
"""

from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import PortfolioItem, ServiceOffering
from core.services.csv_import import choice_value, read_rows

REQUIRED = ("slug", "title", "kind")
STATUS_ALIASES = {
    "": PortfolioItem.DataStatus.COMPLETE,
    "pendente": PortfolioItem.DataStatus.PENDING,
    "descricao_pendente": PortfolioItem.DataStatus.DESCRIPTION_PENDING,
    "confirmar": PortfolioItem.DataStatus.TO_CONFIRM,
}
TRUE_VALUES = {"yes", "sim", "true", "1", "y", "s"}
FALSE_VALUES = {"no", "nao", "não", "false", "0", "n", ""}


def split_list(value):
    return [part.strip() for part in value.split(";") if part.strip()]


class Command(BaseCommand):
    help = "Importa o portfólio (jogos, cursos, sites) de um CSV; idempotente por slug."

    def add_arguments(self, parser):
        parser.add_argument("file", nargs="?", type=Path, default=Path("data/seeds/portfolio.csv"))
        parser.add_argument("--update", action="store_true", help="Sobrescreve itens existentes.")
        parser.add_argument("--dry-run", action="store_true", help="Valida sem gravar.")

    def handle(self, *args, file, update, dry_run, **options):
        rows = read_rows(file, REQUIRED)
        counts = {"criado": 0, "atualizado": 0, "mantido": 0}
        with transaction.atomic():
            for line, row in rows:
                counts[self._import_row(line, row, update)] += 1
            if dry_run:
                transaction.set_rollback(True)
        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            f"{prefix}Portfólio: {counts['criado']} criado(s), {counts['atualizado']} "
            f"atualizado(s), {counts['mantido']} mantido(s)."
        )

    def _import_row(self, line, row, update):
        slug = row["slug"]
        item = PortfolioItem.objects.filter(slug=slug).first()
        if item is not None and not update:
            return "mantido"

        status = row.get("status", "").casefold()
        if status not in STATUS_ALIASES:
            status = choice_value(PortfolioItem.DataStatus, status, "status", line)
        public = row.get("public", "").casefold()
        if public not in TRUE_VALUES | FALSE_VALUES:
            raise CommandError(f"Linha {line}: public {public!r} inválido (use yes ou no).")
        year = row.get("year", "")
        if year and not year.isdigit():
            raise CommandError(f"Linha {line}: year {year!r} inválido.")
        service_slugs = split_list(row.get("services", ""))
        services = list(ServiceOffering.objects.filter(slug__in=service_slugs))
        missing = set(service_slugs) - {s.slug for s in services}
        if missing:
            raise CommandError(
                f"Linha {line}: serviço(s) fora do catálogo: {', '.join(sorted(missing))} "
                "(rode `make seed`)."
            )

        is_new = item is None
        item = item or PortfolioItem(slug=slug)
        item.title = row["title"]
        item.kind = choice_value(PortfolioItem.Kind, row["kind"], "kind", line)
        item.year = int(year) if year else None
        item.description = row.get("description", "")
        item.public_url = row.get("public_url", "")
        item.url_source = row.get("url_source", "")
        item.capability_tags = split_list(row.get("capability_tags", ""))
        item.public = public in TRUE_VALUES
        item.status = STATUS_ALIASES.get(status, status)
        item.notes = row.get("notes", "")
        try:
            item.full_clean()
        except ValidationError as exc:
            raise CommandError(f"Linha {line}: {exc.message_dict}") from exc
        item.save()
        item.services.set(services)
        return "criado" if is_new else "atualizado"
