"""Contagem de organizações por município (só números: seguro para logs públicos e STATUS)."""

from django.core.management.base import BaseCommand
from django.db.models import Count

from core.models import Organization


class Command(BaseCommand):
    help = "Conta organizações de um tipo por município (ex.: `count_organizations school`)."

    def add_arguments(self, parser):
        parser.add_argument("kind", choices=Organization.Kind.values)
        parser.add_argument("--top", type=int, default=0, help="Só os N municípios com mais.")

    def handle(self, *args, kind, top, **options):
        rows = (
            Organization.objects.filter(kind=kind)
            .values("municipality_name", "uf")
            .annotate(total=Count("pk"))
            .order_by("-total", "municipality_name")
        )
        rows = list(rows[:top] if top else rows)
        total = Organization.objects.filter(kind=kind).count()
        for row in rows:
            place = f"{row['municipality_name'] or '(sem município)'}/{row['uf'] or '?'}"
            self.stdout.write(f"{place}: {row['total']}")
        self.stdout.write(f"Total de {kind}: {total}")
