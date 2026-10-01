"""Cria as fontes de coleta iniciais (`Source`) sem sobrescrever o que foi editado no admin.

`sesc-sp-unidades` (CSV curado, sem rede) já nasce habilitada. `inep-escolas` nasce
**desabilitada**: baixe o Catálogo de Escolas do INEP para `data/inep/catalogo_escolas.csv`
(ignorado pelo git), confira os termos e habilite no admin (docs/research/organization-sources.md).
"""

from django.core.management.base import BaseCommand

from core.models import Source

INITIAL_SOURCES = [
    {
        "slug": "sesc-sp-unidades",
        "name": "SESC-SP — unidades (lista curada)",
        "kind": Source.Kind.SEED_CSV,
        "base_url": "https://www.sescsp.org.br/",
        "robots_ok": True,  # arquivo local: nada é baixado
        "reliability": 4,
        "enabled": True,
        "config": {"path": "data/seeds/sesc_sp.csv", "entity": "organization"},
    },
    {
        "slug": "inep-escolas",
        "name": "INEP — Catálogo de Escolas (privadas ativas da região)",
        "kind": Source.Kind.DATASET,
        "base_url": (
            "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/inep-data/"
            "catalogo-de-escolas"
        ),
        "license": "Dados abertos (INEP)",
        "reliability": 5,
        "enabled": False,
        "config": {"path": "data/inep/catalogo_escolas.csv", "max_km": 150},
    },
]


class Command(BaseCommand):
    help = "Cria as fontes iniciais (SESC-SP e INEP) que ainda não existem."

    def handle(self, *args, **options):
        created = 0
        for entry in INITIAL_SOURCES:
            _, was_created = Source.objects.get_or_create(
                slug=entry["slug"], defaults={k: v for k, v in entry.items() if k != "slug"}
            )
            created += was_created
        self.stdout.write(
            f"Fontes: {created} criada(s), {len(INITIAL_SOURCES) - created} já existiam."
        )
