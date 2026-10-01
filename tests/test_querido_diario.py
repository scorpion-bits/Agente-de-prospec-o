"""E08 — conector Querido Diário: fixture sintética, filtro, janela, dedupe e cobertura."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from django.utils import timezone

from collection import registry
from collection.base import RawItem
from collection.connectors.querido_diario import (
    DEFAULT_MUNICIPALITIES,
    DEFAULT_QUERIES,
    QueridoDiarioConnector,
    QueridoDiarioError,
    canonical_key,
    clean_text,
    excerpt_hash,
    kind_for,
)
from collection.fetcher import PoliteFetcher
from collection.models import CollectionRun
from collection.runner import run_source, runnable_problem
from core.management.commands.load_sources import INITIAL_SOURCES
from core.models import Evidence, Opportunity, Source

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "querido_diario"
TODAY = date(2099, 3, 20)


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


GAZETTES = fixture("gazettes_query.json")["gazettes"]
PROBE = fixture("gazettes_probe.json")


@pytest.fixture
def source():
    return Source.objects.create(
        slug="querido-diario",
        name="Querido Diário",
        kind=Source.Kind.API,
        base_url="https://queridodiario.ok.org.br/",
        enabled=True,
        robots_ok=True,
        config={"queries": [{"name": "a", "query": "oficina"}, {"name": "b", "query": "curso"}]},
    )


def make_fetcher(*, no_coverage=(), requests=None):
    """API simulada: consulta (`querystring`) pagina a fixture; sondagem devolve 1 diário."""

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        params = request.url.params
        if requests is not None:
            requests.append(dict(params.multi_items()))
        if params.get("querystring"):
            offset, size = int(params.get("offset", 0)), int(params.get("size", 50))
            body = {"total_gazettes": len(GAZETTES), "gazettes": GAZETTES[offset : offset + size]}
        elif params.get("territory_ids") in no_coverage:
            body = {"total_gazettes": 0, "gazettes": []}
        else:
            body = PROBE
        return httpx.Response(200, json=body)

    return PoliteFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
    )


def run(source, **kwargs):
    return run_source(
        source, fetcher=make_fetcher(**kwargs), connector=QueridoDiarioConnector(source)
    )


def item(data):
    return RawItem(data=data, source_url=data.get("url", ""))


def normalize(source, **overrides):
    gazette = {**GAZETTES[0], "excerpt": clean_text(GAZETTES[0]["excerpts"][0]), **overrides}
    gazette.pop("excerpts")
    return QueridoDiarioConnector(source).normalize(item(gazette))


class TestNormalize:
    def test_maps_an_occurrence(self, source):
        candidate = normalize(source)
        fields = candidate.fields
        assert candidate.title.startswith(
            "Diário Oficial de Araraquara em 10/03/2099: A Prefeitura"
        )
        assert "<em>" not in candidate.title and "<em>" not in fields["description"]
        assert fields["kind"] == "call_for_partners"  # chamamento + credenciamento + oficineiros
        assert fields["official_url"] == "https://exemplo.invalid/araraquara/2099-03-10.pdf"
        assert (fields["scope"], fields["uf"], fields["status"]) == ("municipal", "SP", "unknown")
        assert fields["municipality_name"] == "Araraquara"
        assert fields["organizer_name"] == "Prefeitura de Araraquara"
        assert fields["categories"] == ["games"]
        assert candidate.canonical_key == canonical_key(
            "3503208", date(2099, 3, 10), fields["description"]
        )

    def test_dates_are_not_invented(self, source):
        fields = normalize(source).fields
        assert not {"opens_at", "deadline_at", "starts_at", "ends_at"} & set(fields)

    def test_every_claim_is_observed_with_the_gazette_pdf(self, source):
        candidate = normalize(source)
        assert {"title", "municipality_name", "published_at", "edition", "gazette_url"} <= {
            e.field for e in candidate.evidence
        }
        assert {e.kind for e in candidate.evidence} == {"observed"}
        assert {e.source_url for e in candidate.evidence} == {
            "https://exemplo.invalid/araraquara/2099-03-10.pdf"
        }
        assert all("chamamento" in e.excerpt for e in candidate.evidence)

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Edital de licitação para curso", "procurement"),
            ("pregão eletrônico", "procurement"),
            ("Chamamento público para oficina", "call_for_partners"),
            ("Aldir Blanc: edital de fomento", "edital"),
        ],
    )
    def test_kind_by_rule(self, text, expected):
        assert kind_for(text) == expected

    def test_sports_false_positive_is_excluded(self, source):
        assert normalize(source, excerpt="Abertura dos Jogos Abertos com futebol") is None

    def test_exclusions_come_from_the_source_config(self, source):
        source.config = {"exclude_patterns": []}
        assert normalize(source, excerpt="Abertura dos Jogos Abertos") is not None
        source.config = {"exclude_patterns": ["chamamento"]}
        assert normalize(source) is None

    @pytest.mark.parametrize(
        "bad",
        [
            {"territory_id": "3999999"},  # fora da configuração
            {"excerpt": ""},
            {"date": "ontem"},
            {"url": ""},
        ],
    )
    def test_incomplete_or_foreign_items_are_ignored(self, source, bad):
        assert normalize(source, **bad) is None

    def test_key_ignores_case_and_spacing_of_the_excerpt(self):
        assert excerpt_hash("Oficina  de JOGOS") == excerpt_hash("oficina de jogos")
        assert excerpt_hash("a") != excerpt_hash("b")


class TestWindow:
    def window(self, source):
        return QueridoDiarioConnector(source).window_start(TODAY)

    def test_first_run_uses_the_initial_window(self, source):
        assert self.window(source) == TODAY - timedelta(days=60)
        source.config = {"initial_days": 10}
        assert self.window(source) == TODAY - timedelta(days=10)

    def make_run(self, source, status, *, days_ago, dry_run=False):
        run_ = CollectionRun.objects.create(source=source, status=status, dry_run=dry_run)
        stamp = datetime(2099, 3, 20, 12, tzinfo=UTC) - timedelta(days=days_ago)
        CollectionRun.objects.filter(pk=run_.pk).update(started_at=stamp)

    def test_incremental_starts_at_the_last_completed_run_with_overlap(self, source):
        self.make_run(source, "ok", days_ago=5)
        assert self.window(source) == date(2099, 3, 14)  # dia 15 menos 1 de sobreposição

    def test_failed_partial_and_dry_runs_do_not_advance_the_window(self, source):
        self.make_run(source, "ok", days_ago=9)
        self.make_run(source, "partial", days_ago=3)
        self.make_run(source, "error", days_ago=2)
        self.make_run(source, "ok", days_ago=1, dry_run=True)
        assert self.window(source) == date(2099, 3, 10)

    def test_requests_carry_the_window_and_all_territories(self, source):
        sent = []
        five_days_ago = timezone.now() - timedelta(days=5)
        past = CollectionRun.objects.create(source=source, status="ok")
        CollectionRun.objects.filter(pk=past.pk).update(started_at=five_days_ago)
        source.config = {"queries": [{"name": "a", "query": "oficina"}]}
        run(source, requests=sent)
        searches = [r for r in sent if "querystring" in r]
        assert len(searches) == 1 and searches[0]["querystring"] == "oficina"
        expected = timezone.localtime(five_days_ago).date() - timedelta(days=1)
        assert searches[0]["published_since"] == expected.isoformat()


class TestCollect:
    def test_collects_dedupes_across_queries_and_filters(self, source):
        result = run(source)
        assert result.status == "ok", result.error_log
        # 5 trechos únicos nas duas consultas iguais; esporte e município de fora caem no normalize
        assert result.items_seen == 5 and result.items_new == 3
        titles = list(Opportunity.objects.values_list("title", flat=True))
        assert len(titles) == 3 and not any("Jogos" in t or "Fora" in t for t in titles)
        assert set(Opportunity.objects.values_list("kind", flat=True)) == {
            "call_for_partners",
            "procurement",
            "edital",
        }
        assert Evidence.objects.filter(method="connector:querido-diario").exists()

    def test_second_run_does_not_duplicate(self, source):
        run(source)
        again = run(source)
        assert again.items_new == 0
        assert Opportunity.objects.count() == 3

    def test_paginates_until_a_short_page(self, source):
        source.config = {"queries": [{"name": "a", "query": "x"}], "page_size": 2}
        sent = []
        run(source, requests=sent)
        assert [r["offset"] for r in sent if "querystring" in r] == ["0", "2"]

    def test_max_pages_per_query_limits_requests(self, source):
        source.config = {
            "queries": [{"name": "a", "query": "x"}],
            "page_size": 1,
            "max_pages_per_query": 2,
        }
        sent = []
        run(source, requests=sent)
        assert len([r for r in sent if "querystring" in r]) == 2

    def test_dry_run_writes_nothing(self, source):
        result = run_source(
            source,
            fetcher=make_fetcher(),
            connector=QueridoDiarioConnector(source),
            dry_run=True,
        )
        assert result.items_new == 3 and Opportunity.objects.count() == 0

    def test_uncovered_municipality_is_reported_and_the_rest_is_kept(self, source):
        result = run(source, no_coverage=("3529302",))
        assert result.status == "partial"
        assert "Matão (3529302)" in result.error_log and "html_watch" in result.error_log
        assert "Araraquara" not in result.error_log
        assert Opportunity.objects.count() == 3

    def test_unexpected_response_is_an_explicit_error(self, source):
        def handler(request):
            return (
                httpx.Response(404)
                if request.url.path == "/robots.txt"
                else httpx.Response(200, json={"erro": "x"})
            )

        fetcher = PoliteFetcher(
            client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
        )
        result = run_source(source, fetcher=fetcher, connector=QueridoDiarioConnector(source))
        assert result.status == "error" and "Resposta inesperada" in result.error_log

    def test_invalid_exclusion_regex_is_an_explicit_error(self, source):
        source.config = {"exclude_patterns": ["("]}
        with pytest.raises(QueridoDiarioError):
            QueridoDiarioConnector(source)


class TestSetup:
    def test_defaults_cover_the_four_hubs_and_eight_queries(self):
        codes = {m["ibge_code"] for m in DEFAULT_MUNICIPALITIES}
        assert {"3503208", "3548906", "3543402", "3506003"} <= codes
        assert len(DEFAULT_QUERIES) == 8

    def test_default_municipalities_match_the_ibge_table(self):
        from core.models import Municipality

        Municipality.objects.all().count()  # tabela vem do `load_municipalities`
        from django.core.management import call_command

        call_command("load_municipalities", verbosity=0)
        for entry in DEFAULT_MUNICIPALITIES:
            municipality = Municipality.objects.get(ibge_code=entry["ibge_code"])
            assert municipality.name == entry["name"] and municipality.uf == "SP"

    def test_registered_source_starts_disabled_and_unchecked(self):
        entry = next(s for s in INITIAL_SOURCES if s["slug"] == "querido-diario")
        assert entry["enabled"] is False and not entry.get("robots_ok")
        assert entry["config"]["max_pages"] >= 60  # 8 consultas × páginas + sondagens
        source = Source(**{k: v for k, v in entry.items()})
        assert runnable_problem(source) is not None
        assert isinstance(registry.for_source(source), QueridoDiarioConnector)
