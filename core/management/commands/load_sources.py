"""Cria as fontes de coleta iniciais (`Source`) sem sobrescrever o que foi editado no admin.

`sesc-sp-unidades` e `orgs-parecidas-sesc` (CSVs curados, sem rede) já nascem
habilitadas. `inep-escolas` nasce
**desabilitada**: baixe o Catálogo de Escolas do INEP para `data/inep/catalogo_escolas.csv`
(ignorado pelo git), confira os termos e habilite no admin (docs/research/organization-sources.md).
`devpost` (API pública, E05) também nasce **desabilitada** e sem `robots_ok`: confira os termos
e o robots.txt, marque «coleta permitida» e habilite no admin (opportunity-sources.md).
`itch-jams` (listagem pública de game jams, E06) segue a mesma regra.
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
        "slug": "orgs-parecidas-sesc",
        "name": "Organizações parecidas com o SESC (lista curada)",
        "kind": Source.Kind.SEED_CSV,
        "base_url": "https://www.sescsp.org.br/",
        "robots_ok": True,  # arquivo local: nada é baixado
        "reliability": 3,
        "enabled": True,
        "config": {"path": "data/seeds/similar_orgs.csv", "entity": "organization"},
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
    {
        "slug": "devpost",
        "name": "Devpost — hackathons abertos e futuros",
        "kind": Source.Kind.API,
        "base_url": "https://devpost.com/",
        "terms_url": "https://info.devpost.com/terms",
        "license": "Termos do Devpost (uso automatizado não confirmado)",
        "reliability": 4,
        "enabled": False,  # habilite só depois de conferir termos e robots.txt (E01)
        "config": {"max_api_pages": 5, "min_interval_seconds": 5},
    },
    {
        "slug": "itch-jams",
        "name": "itch.io — game jams futuras e em andamento",
        "kind": Source.Kind.HTML_WATCH,
        "base_url": "https://itch.io/jams",
        "terms_url": "https://itch.io/docs/legal/terms",
        "license": "Termos do itch.io (uso automatizado não confirmado)",
        "reliability": 4,
        "enabled": False,  # habilite só depois de conferir termos e robots.txt (E01)
        "config": {"max_listing_pages": 3, "min_interval_seconds": 5},
    },
]


class Command(BaseCommand):
    help = "Cria as fontes iniciais (SESC-SP, parecidas, INEP, Devpost e itch.io) que faltam."

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
