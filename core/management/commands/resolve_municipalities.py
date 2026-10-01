"""Preenche `municipality` (FK do IBGE) de organizações e oportunidades que só têm o texto.

Casa por (nome normalizado, UF); sem UF só resolve nomes únicos no país; homônimo ambíguo fica
sem município (nunca chuta). Não mexe em quem já tem município. Saída: só contagens.
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Opportunity, Organization
from core.services.geography import resolve_municipality


class Command(BaseCommand):
    help = "Resolve o município (IBGE) de organizações e oportunidades a partir do nome e da UF."

    def handle(self, *args, **options):
        for model in (Organization, Opportunity):
            pending = model.objects.filter(municipality__isnull=True).exclude(
                Q(municipality_name="")
            )
            resolved = unresolved = 0
            for item in pending.iterator():
                found = resolve_municipality(item.municipality_name, item.uf)
                if found is None:
                    unresolved += 1
                    continue
                model.objects.filter(pk=item.pk).update(municipality=found)
                resolved += 1
            self.stdout.write(
                f"{model._meta.verbose_name_plural}: {resolved} resolvida(s), "
                f"{unresolved} sem correspondência."
            )
