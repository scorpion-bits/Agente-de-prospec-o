"""E07 — conector genérico `html_watch`: parser, filtros, diff antes/depois (sem rede)."""

from pathlib import Path

import httpx
import pytest

from collection import registry
from collection.connectors.html_watch import (
    HtmlWatchConnector,
    HtmlWatchError,
    extract_links,
    parse_html,
    select,
)
from collection.fetcher import PoliteFetcher
from collection.runner import run_source, runnable_problem
from core.management.commands.load_sources import INITIAL_SOURCES
from core.models import Evidence, Opportunity, Source

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "html_watch"
PAGE_URL = "https://exemplo.example.gov.br/chamadas"
CONFIG = {
    "url": PAGE_URL,
    "selector": "main .lista-chamadas",
    "link_patterns": ["/chamadas/", "chamada"],
    "exclude_patterns": ["/noticias/"],
    "same_host": True,
    "opportunity": {"organizer_name": "Instituição Exemplo", "scope": "state", "uf": "SP"},
}


def page(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_source(**config):
    return Source.objects.create(
        slug="exemplo-chamadas",
        name="Exemplo — chamadas",
        kind=Source.Kind.HTML_WATCH,
        base_url=PAGE_URL,
        enabled=True,
        robots_ok=True,
        config={**CONFIG, **config},
    )


@pytest.fixture
def source():
    return make_source()


def make_fetcher(body):
    """`body` pode ser uma string ou uma função sem argumentos (para trocar a página entre runs)."""

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        text = body() if callable(body) else body
        return httpx.Response(200, text=text, headers={"content-type": "text/html; charset=utf-8"})

    return PoliteFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
    )


def titles(source):
    return sorted(Opportunity.objects.values_list("title", flat=True))


class TestParsing:
    def test_tolerates_unclosed_li_and_skips_scripts(self):
        links = extract_links(page("chamadas_antes.html"), base_url=PAGE_URL)
        urls = [link["url"] for link in links]
        assert "https://exemplo.example.gov.br/chamadas/edital-jogos-2099" in urls
        assert not any("script-link" in u for u in urls)  # dentro de <script>
        # sem seletor: o «conteúdo principal» exclui header, nav e footer
        assert not any(k in u for u in urls for k in ("sobre", "menu-chamadas", "rodape"))
        assert not any(u.startswith(("mailto:", "#")) for u in urls)

    def test_excerpt_is_the_enclosing_block_only(self):
        links = extract_links(page("chamadas_antes.html"), base_url=PAGE_URL, selector="main")
        first = next(link for link in links if "edital-jogos" in link["url"])
        assert first["excerpt"] == "Edital de Jogos Eletrônicos 2099 inscrições abertas"

    def test_selector_subset(self):
        root = parse_html(page("chamadas_antes.html"))
        assert len(select(root, "main ul")) == 1
        assert len(select(root, "div.lista-chamadas li")) == 6
        assert len(select(root, "ul, p")) == 2
        assert select(root, ".nao-existe") == []
        assert select(root, "footer a")[0].text().startswith("Chamadas no rodapé")
        with pytest.raises(HtmlWatchError):
            select(root, "ul > li")

    def test_selector_without_match_falls_back_to_main_content(self):
        links = extract_links(page("chamadas_antes.html"), base_url=PAGE_URL, selector=".sumiu")
        assert links and all(link["fallback"] for link in links)

    def test_links_are_absolute_without_fragment_and_not_repeated(self):
        html = '<a href="/a#x">Link número um aqui</a><a href="/a">Link número um aqui</a>'
        links = extract_links(html, base_url="https://x.example.org/p/")
        assert [link["url"] for link in links] == ["https://x.example.org/a"]


class TestFilters:
    def accepted(self, source):
        connector = HtmlWatchConnector(source)
        links = extract_links(page("chamadas_antes.html"), base_url=PAGE_URL, selector="main")
        return [link["title"] for link in links if connector.accepts(link, PAGE_URL)]

    def test_patterns_exclude_same_host_and_min_title(self, source):
        assert self.accepted(source) == [
            "Edital de Jogos Eletrônicos 2099",
            "Chamada de Inovação 2099",
        ]

    def test_without_patterns_and_same_host_everything_long_enough_passes(self):
        src = make_source(link_patterns=[], exclude_patterns=[], same_host=False)
        assert len(self.accepted(src)) == 4  # «Ver» (curto demais) cai; mailto e âncora nem entram

    def test_keywords_match_title_or_url(self):
        src = make_source(link_patterns=[], keywords=["edital"])
        assert self.accepted(src) == ["Edital de Jogos Eletrônicos 2099"]

    def test_invalid_config_is_explicit(self):
        with pytest.raises(HtmlWatchError, match="link_patterns"):
            HtmlWatchConnector(make_source(link_patterns=["("]))
        with pytest.raises(HtmlWatchError, match="opportunity"):
            HtmlWatchConnector(
                Source(slug="x", kind="html_watch", config={"opportunity": {"a": 1}})
            )


class TestRun:
    def run(self, source, body, **kwargs):
        return run_source(source, fetcher=make_fetcher(body), **kwargs)

    def test_registered_for_the_kind(self, source):
        assert isinstance(registry.for_source(source), HtmlWatchConnector)
        # o itch.io (conector por slug) continua valendo sobre o genérico
        itch = Source(slug="itch-jams", kind=Source.Kind.HTML_WATCH)
        assert not isinstance(registry.for_source(itch), HtmlWatchConnector)

    def test_first_run_creates_candidates_with_evidence(self, source):
        run = self.run(source, page("chamadas_antes.html"))
        assert (run.status, run.items_seen, run.items_new) == ("ok", 2, 2)
        opp = Opportunity.objects.get(title="Edital de Jogos Eletrônicos 2099")
        assert opp.kind == "edital" and opp.status == "unknown"
        assert opp.official_url == "https://exemplo.example.gov.br/chamadas/edital-jogos-2099"
        assert (opp.organizer_name, opp.scope, opp.uf) == ("Instituição Exemplo", "state", "SP")
        assert not (opp.deadline_at or opp.opens_at)  # datas só na E11
        evidence = Evidence.objects.get(object_id=opp.pk, field="title")
        assert evidence.kind == "observed" and evidence.method == "connector:exemplo-chamadas"
        assert "inscrições abertas" in evidence.excerpt
        assert evidence.raw_document_id is not None

    def test_rerun_without_change_finds_nothing_new(self, source):
        self.run(source, page("chamadas_antes.html"))
        run = self.run(source, page("chamadas_antes.html"))
        assert (run.status, run.items_new, run.items_updated) == ("ok", 0, 0)
        assert Opportunity.objects.count() == 2

    def test_before_after_detects_exactly_the_new_link(self, source):
        state = {"html": page("chamadas_antes.html")}
        fetcher = make_fetcher(lambda: state["html"])
        run_source(source, fetcher=fetcher)
        state["html"] = page("chamadas_depois.html")
        run = run_source(source, fetcher=fetcher)
        assert (run.items_new, run.items_updated) == (1, 0)
        assert titles(source) == [
            "Chamada de Inovação 2099",
            "Credenciamento de oficineiros 2099",
            "Edital de Jogos Eletrônicos 2099",
        ]

    def test_tracking_params_do_not_duplicate(self, source):
        self.run(source, page("chamadas_antes.html"))
        assert Opportunity.objects.filter(canonical_key__contains="inovacao-2099").count() == 1
        assert "utm_" not in Opportunity.objects.get(title="Chamada de Inovação 2099").canonical_key

    def test_dry_run_writes_nothing(self, source):
        run = self.run(source, page("chamadas_antes.html"), dry_run=True)
        assert run.items_new == 2 and Opportunity.objects.count() == 0

    def test_javascript_only_page_is_an_explicit_error(self, source):
        run = self.run(source, page("so_javascript.html"))
        assert run.status == "error"
        assert "Resposta inesperada" in run.error_log and "JavaScript" in run.error_log
        assert Opportunity.objects.count() == 0

    def test_missing_url_is_an_explicit_error(self):
        src = Source.objects.create(slug="sem-url", name="x", kind="html_watch", enabled=True)
        run = self.run(src, "<a href='/a'>Link longo o bastante</a>")
        assert run.status == "error" and "config.url" in run.error_log

    def test_max_links_caps_the_run(self):
        src = make_source(max_links=1)
        assert self.run(src, page("chamadas_antes.html")).items_seen == 1


class TestInitialSources:
    WATCHED = [e for e in INITIAL_SOURCES if e["kind"] == Source.Kind.HTML_WATCH and "config" in e]

    def test_at_least_five_pages_configured_without_page_specific_code(self):
        generic = [e for e in self.WATCHED if e["slug"] != "itch-jams"]
        assert len(generic) >= 5
        for entry in generic:
            assert entry["config"].get("url") or entry["base_url"]
            source = Source(**{k: v for k, v in entry.items()})
            assert isinstance(registry.for_source(source), HtmlWatchConnector)

    def test_start_disabled_and_unverified(self):
        for entry in self.WATCHED:
            assert entry["enabled"] is False and not entry.get("robots_ok", False)
            source = Source(**entry)
            assert runnable_problem(source) is not None
