"""Cria as fontes de coleta iniciais (`Source`) sem sobrescrever o que foi editado no admin.

`sesc-sp-unidades` e `orgs-parecidas-sesc` (CSVs curados, sem rede) já nascem
habilitadas. `inep-escolas` nasce
**desabilitada**: baixe o Catálogo de Escolas do INEP para `data/inep/catalogo_escolas.csv`
(ignorado pelo git), confira os termos e habilite no admin (docs/research/organization-sources.md).
`devpost` (API pública, E05) também nasce **desabilitada** e sem `robots_ok`: confira os termos
e o robots.txt, marque «coleta permitida» e habilite no admin (opportunity-sources.md).
`itch-jams` (listagem pública de game jams, E06), `querido-diario` (API de diários oficiais, E08,
ADR-031), `mapas-culturais` (editais culturais, E09, ADR-032) e `pncp` (contratações, E27,
ADR-041) e `cnpj-estabelecimentos` (empresas por CNAE, E25, ADR-043)
seguem a mesma regra. As páginas monitoradas pelo `html_watch` genérico (E07, ADR-030)
também nascem **desabilitadas**, e as URLs são de memória/da pesquisa: confirme cada uma (e o
`selector`, se a listagem tiver área própria) antes de habilitar.
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
    {
        "slug": "querido-diario",
        "name": "Querido Diário — diários oficiais dos polos",
        "kind": Source.Kind.API,
        "base_url": "https://queridodiario.ok.org.br/",
        "terms_url": "https://docs.queridodiario.ok.org.br/pt-br/latest/utilizando/api-publica/",
        "license": "Dados abertos (OKBR); termos da API não conferidos",
        "reliability": 4,
        "enabled": False,  # habilite só depois de conferir termos e robots.txt (E01)
        "config": {"max_pages": 120, "min_interval_seconds": 2},
    },
    {
        "slug": "mapas-culturais",
        "name": "Mapas Culturais — editais (nacional e SP)",
        "kind": Source.Kind.API,
        "base_url": "https://mapa.cultura.gov.br/",
        "terms_url": "https://docs.mapasculturais.org/",
        "license": "Dados abertos; termos de cada instância não conferidos",
        "reliability": 4,
        "enabled": False,  # habilite só depois de conferir instâncias, termos e robots.txt (P20)
        "config": {"max_pages_per_instance": 4, "min_interval_seconds": 3},
    },
    {
        "slug": "pncp",
        "name": "PNCP — contratações com propostas abertas (SP)",
        "kind": Source.Kind.API,
        "base_url": "https://pncp.gov.br/",
        "terms_url": "https://www.gov.br/pncp/pt-br/acesso-a-informacao/manuais",
        "license": "Dados abertos (Lei 14.133); termos da API não conferidos",
        "reliability": 5,
        "enabled": False,  # habilite só depois de conferir parâmetros, termos e robots.txt (P29)
        "config": {"ufs": ["SP"], "max_pages_per_query": 4, "min_interval_seconds": 3},
    },
    {
        "slug": "cnpj-estabelecimentos",
        "name": "Receita Federal — empresas ativas da região por CNAE",
        "kind": Source.Kind.DATASET,
        "base_url": "https://dadosabertos.rfb.gov.br/CNPJ/",
        "license": "Dados abertos (Receita Federal)",
        "reliability": 4,
        "enabled": False,  # baixe os .zip à mão em data/cnpj e habilite (P31)
        "config": {
            "path": "data/cnpj",
            "groups": ["marketing", "courses", "publishing", "events"],
            "max_km": 150,
        },
    },
]


CALL_WORDS = ["edital", "editais", "chamada", "chamamento", "credenciamento", "inscri", "seleção"]


def watched_page(slug, name, url, *, reliability=4, keywords=None, **opportunity):
    """Fonte do `html_watch` genérico: só configuração, nenhum código por página (E07)."""
    return {
        "slug": slug,
        "name": name,
        "kind": Source.Kind.HTML_WATCH,
        "base_url": url,
        "reliability": reliability,
        "enabled": False,  # habilite só depois de conferir termos, robots.txt e a URL (P18)
        "config": {
            "url": url,
            "keywords": keywords if keywords is not None else CALL_WORDS,
            "min_interval_seconds": 5,
            "opportunity": {"kind": "edital", **opportunity},
        },
    }


INITIAL_SOURCES += [
    watched_page(
        "fapesp-pipe",
        "FAPESP — chamadas do PIPE",
        "https://fapesp.br/pipe/chamadas",
        reliability=5,
        keywords=[],  # a página já é só de chamadas
        organizer_name="FAPESP",
        scope="state",
        uf="SP",
        categories=["innovation", "technology"],
    ),
    watched_page(
        "proac-editais",
        "Secretaria de Cultura SP — ProAC e PNAB (editais)",
        "https://www.cultura.sp.gov.br/sec_cultura/Fomento/Fomento_Editais_e_PNAB",
        reliability=5,
        organizer_name="Secretaria de Cultura, Economia e Indústria Criativas de SP",
        scope="state",
        uf="SP",
        categories=["culture"],
    ),
    watched_page(
        "oficinas-culturais",
        "Oficinas Culturais do Estado de SP — chamadas",
        "https://oficinasculturais.org.br/",
        reliability=5,
        organizer_name="Oficinas Culturais do Estado de SP",
        kind="call_for_partners",
        scope="state",
        uf="SP",
        categories=["culture", "education"],
    ),
    watched_page(
        "sebrae-sp-editais",
        "Sebrae-SP — editais e programas",
        "https://www.sebraesp.com.br/",
        organizer_name="Sebrae-SP",
        scope="state",
        uf="SP",
        categories=["entrepreneurship"],
    ),
    watched_page(
        "inovativa-chamadas",
        "InovAtiva Brasil — chamadas",
        "https://www.inovativabrasil.com.br/",
        reliability=5,
        kind="program",
        organizer_name="InovAtiva Brasil",
        scope="national",
        categories=["innovation", "entrepreneurship"],
    ),
    *[
        watched_page(
            f"prefeitura-{slug}-editais",
            f"Prefeitura de {city} — editais e chamamentos",
            url,
            reliability=4,
            organizer_name=f"Prefeitura de {city}",
            scope="municipal",
            uf="SP",
            municipality_name=city,
            categories=["culture", "education"],
        )
        for slug, city, url in (
            ("araraquara", "Araraquara", "https://www.araraquara.sp.gov.br/"),
            ("sao-carlos", "São Carlos", "https://www.saocarlos.sp.gov.br/"),
            ("ribeirao-preto", "Ribeirão Preto", "https://www.ribeiraopreto.sp.gov.br/"),
            ("bauru", "Bauru", "https://www.bauru.sp.gov.br/"),
        )
    ],
]


class Command(BaseCommand):
    help = (
        "Cria as fontes iniciais (SESC-SP, parecidas, INEP, Devpost, itch.io, Querido Diário e "
        "páginas) que faltam."
    )

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
