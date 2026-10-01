"""Carrega o catálogo inicial de serviços sem sobrescrever o que foi editado no admin.

O catálogo é **dado** (`ServiceOffering`), editável no admin: o contador ajusta a cobertura do MEI
(ADR-015), por exemplo. Por isso este comando só **cria** o que falta; sobrescrever é opt-in
(`--update`). (`loaddata services` também funciona, mas sobrescreve tudo sem avisar.)
"""

import json
from pathlib import Path

from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import ServiceOffering

DEFAULT_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "services.json"


class Command(BaseCommand):
    help = (
        "Carrega o catálogo inicial de serviços (core/fixtures/services.json). Serviços que já "
        "existem são mantidos; use --update para sobrescrevê-los com o arquivo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file", type=Path, default=DEFAULT_FIXTURE, help="Outro arquivo no formato fixture."
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Sobrescreve os serviços existentes (descarta edições feitas no admin).",
        )

    def handle(self, *args, file, update, **options):
        try:
            entries = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Não foi possível ler {file}: {exc}") from exc

        created = updated = kept = 0
        with transaction.atomic():
            for entry in entries:
                if entry.get("model") != "core.serviceoffering":
                    raise CommandError(f"Entrada inesperada em {file}: {entry.get('model')!r}.")
                fields = dict(entry["fields"])
                slug = fields.pop("slug")
                service = ServiceOffering.objects.filter(slug=slug).first()
                if service is not None and not update:
                    kept += 1
                    continue
                is_new = service is None
                service = service or ServiceOffering(slug=slug)
                for name, value in fields.items():
                    try:
                        ServiceOffering._meta.get_field(name)
                    except FieldDoesNotExist as exc:
                        raise CommandError(f"Campo desconhecido em {slug}: {name!r}.") from exc
                    setattr(service, name, value)
                service.full_clean()
                service.save()
                if is_new:
                    created += 1
                else:
                    updated += 1
        self.stdout.write(
            f"Catálogo de serviços: {created} criado(s), {updated} atualizado(s), "
            f"{kept} mantido(s)."
        )
