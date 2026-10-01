"""Carrega o perfil da empresa (linha única) a partir do seed não sensível.

O CNPJ e o e-mail de contato vêm do ambiente (`COMPANY_CNPJ`, `CONTACT_EMAIL`), nunca do git
(ADR-014). Se o perfil já existe, só completa CNPJ e e-mail em branco; `--update` sobrescreve com
o arquivo (descarta edições do admin, ex.: ajustes do contador).
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import CompanyProfile

FILE_FIELDS = (
    "legal_form",
    "status",
    "opened_at",
    "hq_municipality",
    "hq_uf",
    "annual_revenue_cap_brl",
    "website",
    "activity_mode",
    "primary_cnae",
    "cnaes",
    "notes",
)


class Command(BaseCommand):
    help = "Carrega o perfil da empresa de um JSON (padrão: data/seeds/company_profile.json)."

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            nargs="?",
            type=Path,
            default=Path("data/seeds/company_profile.json"),
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Sobrescreve um perfil existente com o arquivo (descarta edições do admin).",
        )

    def handle(self, *args, file, update, **options):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Não foi possível ler {file}: {exc}") from exc
        unknown = set(data) - set(FILE_FIELDS) - {"_comment"}
        if unknown:
            raise CommandError(f"Campos desconhecidos em {file}: {', '.join(sorted(unknown))}.")

        with transaction.atomic():
            profile = CompanyProfile.get()
            created = profile is None
            profile = profile or CompanyProfile.get_or_new()
            if created or update:
                for name in FILE_FIELDS:
                    if name in data:
                        setattr(profile, name, data[name])
            if settings.COMPANY_CNPJ and (update or not profile.cnpj):
                profile.cnpj = settings.COMPANY_CNPJ
            if settings.CONTACT_EMAIL and (update or not profile.contact_email):
                profile.contact_email = settings.CONTACT_EMAIL
            try:
                profile.full_clean()
            except ValidationError as exc:
                raise CommandError(f"Perfil inválido: {exc.message_dict}") from exc
            profile.save()

        state = "criado" if created else ("atualizado" if update else "mantido")
        cnpj = "preenchido" if profile.cnpj else "em branco (defina COMPANY_CNPJ no .env)"
        self.stdout.write(f"Perfil da empresa {state}; CNPJ {cnpj}.")
