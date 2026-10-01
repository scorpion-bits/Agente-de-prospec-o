"""E09 — conector Mapas Culturais: fixtures sintéticas de 2 instâncias, filtro, datas e erros."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from collection import registry
from collection.base import RawItem
from collection.connectors.mapas_culturais import (
    DEFAULT_INSTANCES,
    MapasCulturaisConnector,
    MapasCulturaisError,
    parse_moment,
)
from collection.fetcher import PoliteFetcher
from collection.runner import run_source, runnable_problem
from core.management.commands.load_sources import INITIAL_SOURCES
from core.models import Evidence, Opportunity, Source

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "mapas_culturais"
NACIONAL = json.loads((FIXTURES / "nacional.json").read_text(encoding="utf-8"))
SP = json.loads((FIXTURES / "sp.json").read_text(encoding="utf-8"))
INSTANCES = [
    {"slug": "nacional", "name": "Mapa Nacional", "base_url": "https://mapa.exemplo.invalid",
     "scope": "national"},
    {"slug": "sp", "name": "Mapa SP", "base_url": "https://mapa.sp.exemplo.invalid",
     "scope": "state", "uf": "SP"},
]  # fmt: skip


@pytest.fixture
def source():
    return Source.objects.create(
        slug="mapas-culturais",
        name="Mapas Culturais",
        kind=Source.Kind.API,
        base_url="https://mapa.exemplo.invalid/",
        enabled=True,
        robots_ok=True,
        config={"instances": INSTANCES},
    )


def make_fetcher(*, broken=(), requests=None):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if requests is not None:
            requests.append(request.url)
        host = request.url.host
        if host in broken:
            return httpx.Response(200, text="<html>manutenção</html>")
        return httpx.Response(200, json=NACIONAL if host == "mapa.exemplo.invalid" else SP)

    return PoliteFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
    )


def run(source, **kwargs):
    return run_source(
        source, fetcher=make_fetcher(**kwargs), connector=MapasCulturaisConnector(source)
    )


def normalize(source, row, instance=0):
    item = RawItem(data={**row, "_instance": INSTANCES[instance]}, source_url=row["singleUrl"])
    return MapasCulturaisConnector(source).normalize(item)


class TestNormalize:
    def test_maps_an_opportunity_with_registration_dates(self, source):
        candidate = normalize(source, NACIONAL[0])
        fields = candidate.fields
        assert candidate.title == "Edital de Jogos Digitais Educativos"
        assert fields["official_url"] == "https://mapa.exemplo.invalid/oportunidade/101/"
        assert fields["organizer_name"] == "Secretaria de Cultura Exemplo"
        assert (fields["kind"], fields["scope"], fields["status"]) == ("edital", "national", "open")
        assert fields["opens_at"].year == 2020 and fields["deadline_at"].day == 30
        assert fields["deadline_at"].hour == 23 and fields["deadline_at"].minute == 59
        assert {"games", "culture"} <= set(fields["categories"])
        assert "<b>" not in fields["description"]
        assert candidate.canonical_key == "mc:mapa.exemplo.invalid|101"

    def test_date_object_with_timezone_and_upcoming_status(self, source):
        fields = normalize(source, NACIONAL[3]).fields
        assert fields["status"] == "upcoming"
        assert fields["opens_at"].isoformat().startswith("2098-06-01T08:00")
        assert fields["organizer_name"] == "Mapa Nacional"  # sem ownerEntity: a instância

    def test_poor_instance_has_no_invented_fields(self, source):
        candidate = normalize(source, SP[0], instance=1)
        fields = candidate.fields
        assert fields["deadline_at"] is None and fields["status"] == "open"
        assert (fields["scope"], fields["uf"]) == ("state", "SP")
        assert {e.field for e in candidate.evidence} >= {"title", "instance", "opens_at"}
        assert "deadline_at" not in {e.field for e in candidate.evidence}

    def test_evidence_is_observed_with_the_instance_link(self, source):
        candidate = normalize(source, NACIONAL[0])
        assert {e.kind for e in candidate.evidence} == {"observed"}
        assert {e.source_url for e in candidate.evidence} == {fields_url(candidate)}
        assert {"areas", "opportunity_type", "deadline_at"} <= {e.field for e in candidate.evidence}

    def test_irrelevant_closed_and_incomplete_are_dropped(self, source):
        assert normalize(source, NACIONAL[1]) is None  # dança: sem palavra-chave
        assert normalize(source, NACIONAL[2]) is None  # prazo vencido
        assert normalize(source, SP[1], instance=1) is None  # concurso de cartazes
        assert normalize(source, {**NACIONAL[0], "id": None}) is None
        assert normalize(source, {**NACIONAL[0], "singleUrl": ""}) is None

    def test_include_closed_keeps_expired(self, source):
        source.config = {**source.config, "include_closed": True}
        assert normalize(source, NACIONAL[2]).fields["status"] == "closed"

    def test_keywords_ignore_accents_and_case(self, source):
        row = {**NACIONAL[1], "name": "EDUCAÇÃO patrimonial"}
        assert normalize(source, row) is not None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2099-05-02 23:59:59.000000", "2099-05-02T23:59:59-03:00"),
            ("2099-05-02T10:00:00Z", "2099-05-02T07:00:00-03:00"),
            ("2099-05-02", "2099-05-02T00:00:00-03:00"),
            ("", None),
            ("breve", None),
            (None, None),
        ],
    )
    def test_parse_moment(self, value, expected):
        moment = parse_moment(value)
        assert (moment.isoformat() if moment else None) == expected


def fields_url(candidate):
    return candidate.fields["official_url"]


class TestCollect:
    def test_collects_both_instances_and_filters(self, source):
        run_ = run(source)
        assert run_.status == "ok", run_.error_log
        titles = set(Opportunity.objects.values_list("title", flat=True))
        assert titles == {
            "Edital de Jogos Digitais Educativos",
            "Chamada de Oficinas de Games (em breve)",
            "Fomento a Oficinas Culturais de Software Livre",
        }
        assert run_.items_new == 3
        assert Evidence.objects.filter(kind="observed").exists()
        assert not Evidence.objects.exclude(kind="observed").exists()

    def test_second_run_does_not_duplicate(self, source):
        run(source)
        again = run(source)
        assert Opportunity.objects.count() == 3
        assert again.items_new == 0

    def test_request_filters_open_registrations_and_paginates(self, source):
        requests = []
        run(source, requests=requests)
        first = requests[0]
        assert first.path == "/api/opportunity/find"
        assert first.params["registrationTo"].startswith("GTE(")
        assert first.params["@page"] == "1" and "@select" in first.params
        assert len(requests) == 2  # páginas curtas: uma por instância

    def test_full_page_asks_for_the_next_one_up_to_the_limit(self, source):
        source.config = {**source.config, "page_size": 1, "max_pages_per_instance": 2}
        requests = []
        run(source, requests=requests)
        pages = [r.params["@page"] for r in requests if r.host == "mapa.exemplo.invalid"]
        assert pages == ["1", "2"]

    def test_dry_run_writes_nothing(self, source):
        run_source(
            source,
            fetcher=make_fetcher(),
            connector=MapasCulturaisConnector(source),
            dry_run=True,
        )
        assert Opportunity.objects.count() == 0

    def test_a_broken_instance_does_not_drop_the_others(self, source):
        run_ = run(source, broken={"mapa.sp.exemplo.invalid"})
        assert run_.status == "partial"
        assert "sp:" in run_.error_log and "não é JSON" in run_.error_log
        assert Opportunity.objects.count() == 2

    def test_non_list_response_is_an_explicit_error(self, source, monkeypatch):
        def handler(request):
            if request.url.path == "/robots.txt":
                return httpx.Response(404)
            return httpx.Response(200, json={"error": "x"})

        fetcher = PoliteFetcher(
            client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
        )
        run_ = run_source(source, fetcher=fetcher, connector=MapasCulturaisConnector(source))
        assert "esperava uma lista" in run_.error_log and Opportunity.objects.count() == 0

    def test_invalid_config_is_an_explicit_error(self, source):
        source.config = {"instances": [{"slug": "x"}]}
        with pytest.raises(MapasCulturaisError):
            MapasCulturaisConnector(source)
        source.config = {"instances": INSTANCES, "exclude_patterns": ["("]}
        with pytest.raises(MapasCulturaisError):
            MapasCulturaisConnector(source)


class TestSetup:
    def test_defaults_have_at_least_two_instances(self):
        assert len(DEFAULT_INSTANCES) >= 2
        assert all(i["base_url"].startswith("https://") for i in DEFAULT_INSTANCES)

    def test_connector_is_registered_by_slug(self, source):
        assert isinstance(registry.for_source(source), MapasCulturaisConnector)

    def test_registered_source_starts_disabled_and_unchecked(self):
        spec = next(s for s in INITIAL_SOURCES if s["slug"] == "mapas-culturais")
        assert spec["enabled"] is False and not spec.get("robots_ok")
        source = Source.objects.create(**{k: v for k, v in spec.items()})
        assert runnable_problem(source)
        assert date.today().year >= 2026
