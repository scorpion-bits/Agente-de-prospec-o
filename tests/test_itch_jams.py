"""E06 — conector itch.io (game jams): fixture sintética, filtro, datas e dedupe (sem rede)."""

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from collection import registry
from collection.base import RawItem
from collection.connectors.itch_jams import (
    ItchError,
    ItchJamsConnector,
    clean_jam_url,
    parse_joined,
    parse_listing,
    parse_stamp,
)
from collection.fetcher import PoliteFetcher
from collection.runner import run_source, runnable_problem
from core.management.commands.load_sources import INITIAL_SOURCES
from core.models import Evidence, Opportunity, Source

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "itch_jams"
NOW = datetime(2026, 10, 1, tzinfo=UTC)


def page(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def source():
    return Source.objects.create(
        slug="itch-jams",
        name="itch.io jams",
        kind=Source.Kind.HTML_WATCH,
        base_url="https://itch.io/jams",
        enabled=True,
        robots_ok=True,
    )


PAGES = {
    ("/jams/upcoming", "1"): page("upcoming_page1.html"),
    ("/jams/upcoming", "2"): page("upcoming_page2.html"),
    ("/jams/in-progress", "1"): page("in_progress_page1.html"),
}


def make_fetcher(pages=PAGES):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        key = (request.url.path, request.url.params.get("page", "1"))
        body = pages.get(key, "<html><body></body></html>")
        return httpx.Response(200, text=body, headers={"content-type": "text/html; charset=utf-8"})

    return PoliteFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
    )


def connector(source):
    return ItchJamsConnector(source, now=lambda: NOW)


def cells():
    return parse_listing(page("upcoming_page1.html"))


def normalize(source, cell, listing="upcoming"):
    item = RawItem(data={**cell, "listing": listing}, source_url=cell["url"])
    return connector(source).normalize(item)


class TestParsing:
    def test_listing_cells(self):
        found = cells()
        assert [c["title"] for c in found] == [
            "Jam Brasileira Exemplo",
            "Mega Jam Exemplo",
            "Jam Relampago Exemplo",
            "Jam Pequena Exemplo",
            "Jam Godot Sem Data",
        ]
        first = found[0]
        assert first["url"] == "https://itch.io/jam/jam-brasileira-exemplo"
        assert first["host"] == "Estudio Exemplo A"
        assert first["dates"] == ["2099-03-06 15:00:00", "2099-03-09 15:00:00"]
        assert first["joined"] == 12
        assert found[1]["joined"] == 1234 and found[4]["joined"] is None

    def test_page_without_jams_is_empty(self):
        assert parse_listing("<html>nada</html>") == []

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("/jam/abc", "https://itch.io/jam/abc"),
            ("https://itch.io/jam/abc?ref=x#y", "https://itch.io/jam/abc"),
            ("https://outro.org/jam/abc", ""),
            ("https://itch.io/jams/upcoming", ""),
            ("", ""),
        ],
    )
    def test_clean_jam_url(self, url, expected):
        assert clean_jam_url(url) == expected

    def test_stamp_and_joined(self):
        assert parse_stamp("2099-03-06 15:00:00") == datetime(2099, 3, 6, 15, tzinfo=UTC)
        assert parse_stamp("amanhã") is None and parse_stamp("2099-13-40 00:00:00") is None
        assert parse_joined("1,234") == 1234 and parse_joined("1.234") == 1234
        assert parse_joined("x") is None


class TestNormalize:
    def test_maps_a_jam_with_start_and_end(self, source):
        candidate = normalize(source, cells()[0])
        fields = candidate.fields
        assert candidate.title == "Jam Brasileira Exemplo"
        assert fields["kind"] == "game_jam"
        assert fields["official_url"] == "https://itch.io/jam/jam-brasileira-exemplo"
        assert fields["organizer_name"] == "Estudio Exemplo A"
        assert (fields["modality"], fields["status"]) == ("online", "upcoming")
        assert fields["categories"] == ["games"]
        assert fields["opens_at"] == datetime(2099, 3, 6, 15, tzinfo=UTC)
        assert fields["deadline_at"] == datetime(2099, 3, 9, 15, tzinfo=UTC)

    def test_a_single_date_means_start_when_upcoming_and_end_when_in_progress(self, source):
        upcoming = normalize(source, cells()[1]).fields
        assert (
            upcoming["opens_at"] == datetime(2099, 4, 1, tzinfo=UTC) and not upcoming["deadline_at"]
        )
        running = parse_listing(page("in_progress_page1.html"))[0]
        fields = normalize(source, running, listing="in-progress").fields
        assert fields["status"] == "open" and fields["opens_at"] is None
        assert fields["deadline_at"] == datetime(2099, 2, 20, 12, tzinfo=UTC)
        assert fields["categories"] == ["games", "education"]

    def test_unreadable_dates_stay_blank(self, source):
        fields = normalize(source, cells()[4]).fields  # sem datas, mas com palavra-chave
        assert fields["opens_at"] is None and fields["deadline_at"] is None

    def test_every_claim_is_observed_with_the_jam_url(self, source):
        candidate = normalize(source, cells()[0])
        assert {"title", "organizer_name", "opens_at", "deadline_at", "participants"} <= {
            e.field for e in candidate.evidence
        }
        assert {e.kind for e in candidate.evidence} == {"observed"}
        assert {e.source_url for e in candidate.evidence} == {
            "https://itch.io/jam/jam-brasileira-exemplo"
        }

    @pytest.mark.parametrize(
        ("index", "why"),
        [(2, "só 12 h de duração"), (3, "3 inscritos e sem palavra-chave")],
    )
    def test_irrelevant_jams_are_ignored(self, source, index, why):
        assert normalize(source, cells()[index]) is None, why

    def test_finished_jam_is_ignored(self, source):
        old = {**cells()[1], "dates": ["2020-01-01 00:00:00", "2020-01-05 00:00:00"]}
        assert normalize(source, old) is None

    def test_duration_filter_comes_from_the_source_config(self, source):
        assert normalize(source, cells()[2]) is None  # 12 h < 48 h
        source.config = {"min_duration_hours": 1}
        assert normalize(source, cells()[2]) is not None  # 900 inscritos

    def test_keywords_come_from_the_source_config(self, source):
        source.config = {"keywords": ["pequena"]}
        assert normalize(source, cells()[3]) is not None
        assert normalize(source, cells()[0]) is None  # 12 inscritos e sem a palavra

    def test_missing_title_or_foreign_url_is_ignored(self, source):
        assert normalize(source, {**cells()[0], "title": ""}) is None
        assert normalize(source, {**cells()[0], "url": "https://outro.org/jam/x"}) is None


class TestCollect:
    def run(self, source, **kwargs):
        return run_source(source, fetcher=make_fetcher(), connector=connector(source), **kwargs)

    def test_collects_relevant_jams_and_stops_at_repeated_pages(self, source):
        result = self.run(source)
        assert result.status == "ok"
        assert result.items_seen == 6  # 5 da página 1 + 1 em andamento (a repetida some no fetch)
        titles = set(Opportunity.objects.values_list("title", flat=True))
        assert titles == {
            "Jam Brasileira Exemplo",
            "Mega Jam Exemplo",
            "Jam Godot Sem Data",
            "Jam Educacao em Andamento",
        }
        assert Evidence.objects.filter(method="connector:itch-jams").exists()

    def test_second_run_does_not_duplicate(self, source):
        self.run(source)
        count = Opportunity.objects.count()
        again = self.run(source)
        assert Opportunity.objects.count() == count and again.items_new == 0

    def test_dry_run_writes_nothing(self, source):
        self.run(source, dry_run=True)
        assert not Opportunity.objects.exists()

    def test_changed_end_date_updates_the_same_opportunity(self, source):
        self.run(source)
        changed = {**PAGES}
        changed[("/jams/upcoming", "1")] = PAGES[("/jams/upcoming", "1")].replace(
            "2099-03-09 15:00:00", "2099-03-12 15:00:00"
        )
        result = run_source(source, fetcher=make_fetcher(changed), connector=connector(source))
        assert result.items_updated >= 1
        jam = Opportunity.objects.get(title="Jam Brasileira Exemplo")
        assert jam.deadline_at == datetime(2099, 3, 12, 15, tzinfo=UTC)

    def test_changed_markup_fails_the_source_with_a_clear_error(self, source):
        pages = {("/jams/upcoming", "1"): "<html><body><p>layout novo</p></body></html>"}
        result = run_source(source, fetcher=make_fetcher(pages), connector=connector(source))
        assert result.status == "error" and "Resposta inesperada" in result.error_log

    def test_max_listing_pages_is_respected(self, source):
        source.config = {"max_listing_pages": 1, "listing_urls": ["https://itch.io/jams/upcoming"]}
        result = run_source(source, fetcher=make_fetcher(), connector=connector(source))
        assert result.items_seen == 5

    def test_run_reports_where_the_time_went(self, source):
        assert "busca" in self.run(source).timing


class TestRegistration:
    def test_registered_by_slug(self, source):
        assert isinstance(registry.for_source(source), ItchJamsConnector)

    def test_initial_source_is_disabled_until_a_human_checks_the_terms(self):
        entry = next(s for s in INITIAL_SOURCES if s["slug"] == "itch-jams")
        assert entry["enabled"] is False and not entry.get("robots_ok")
        source = Source.objects.create(**entry)
        assert "desabilitada" in runnable_problem(source)
        source.enabled = True
        assert "robots" in runnable_problem(source)

    def test_error_type_is_exported(self):
        assert issubclass(ItchError, ValueError)
