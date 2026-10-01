"""E05 — conector Devpost: normalização com fixture sintética, filtro, datas e dedupe (sem rede)."""

import json
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from collection import registry
from collection.base import RawItem
from collection.connectors.devpost import (
    DevpostConnector,
    DevpostError,
    clean_url,
    parse_period,
    strip_html,
)
from collection.fetcher import PoliteFetcher
from collection.runner import run_source, runnable_problem
from core.management.commands.load_sources import INITIAL_SOURCES
from core.models import Evidence, Opportunity, Source

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "devpost"
SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def page(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def hackathons(name="hackathons_page1.json"):
    return json.loads(page(name))["hackathons"]


@pytest.fixture
def source():
    return Source.objects.create(
        slug="devpost",
        name="Devpost",
        kind=Source.Kind.API,
        base_url="https://devpost.com/",
        enabled=True,
        robots_ok=True,
        config={"max_api_pages": 3},
    )


def make_fetcher(pages):
    """Servidor falso: robots.txt aberto e uma resposta por número de página."""

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        number = request.url.params.get("page", "1")
        body = pages.get(number, json.dumps({"hackathons": []}))
        return httpx.Response(200, text=body, headers={"content-type": "application/json"})

    return PoliteFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
    )


def normalize(source, data):
    return DevpostConnector(source).normalize(RawItem(data=data, source_url=data.get("url", "")))


class TestParsing:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Sep 01 - Oct 30, 2026", (date(2026, 9, 1), date(2026, 10, 30))),
            ("Dec 15, 2026 - Jan 10, 2027", (date(2026, 12, 15), date(2027, 1, 10))),
            ("Dec 15 - Jan 10, 2027", (date(2026, 12, 15), date(2027, 1, 10))),
            ("Oct 30, 2026", (None, date(2026, 10, 30))),
            ("", (None, None)),
            ("em breve", (None, None)),
            ("Sep 01 - 30, 2026", (None, None)),  # forma não suportada: sem chute
            ("Feb 31 - Mar 02, 2026", (None, None)),
            ("Oct 30, 2026 - Sep 01, 2026", (None, None)),  # fim antes do início
        ],
    )
    def test_period(self, text, expected):
        assert parse_period(text) == expected

    def test_strip_html_and_clean_url(self):
        assert strip_html("$<span data-currency-value>10,000</span>") == "$10,000"
        assert (
            clean_url("http://x.devpost.com/?ref_feature=a&utm_source=b&page=2")
            == "https://x.devpost.com/?page=2"
        )
        assert clean_url("https://evil.example.org/x") == ""
        assert clean_url("") == ""


class TestNormalize:
    def test_maps_an_online_gaming_hackathon(self, source):
        candidate = normalize(source, hackathons()[0])
        fields = candidate.fields
        assert candidate.title == "Exemplo Game Jam Global"
        assert fields["kind"] == "hackathon"
        assert fields["official_url"] == "https://exemplo-game-jam.devpost.com/"
        assert fields["organizer_name"] == "Organizacao Exemplo A"
        assert (fields["modality"], fields["scope"], fields["status"]) == (
            "online",
            "international",
            "open",
        )
        assert fields["categories"] == ["games", "education"]
        assert fields["prize_text"] == "$10,000" and fields["benefits"] == ["prize"]

    def test_dates_use_the_local_timezone(self, source):
        fields = normalize(source, hackathons()[0]).fields
        assert fields["opens_at"].astimezone(SAO_PAULO).isoformat() == "2026-09-01T00:00:00-03:00"
        assert (
            fields["deadline_at"].astimezone(SAO_PAULO).isoformat() == "2026-10-30T23:59:00-03:00"
        )

    def test_unreadable_dates_stay_blank(self, source):
        data = {**hackathons()[0], "submission_period_dates": "TBA"}
        fields = normalize(source, data).fields
        assert fields["opens_at"] is None and fields["deadline_at"] is None

    def test_every_claim_is_observed_with_the_hackathon_url(self, source):
        candidate = normalize(source, hackathons()[0])
        names = {e.field for e in candidate.evidence}
        assert {"title", "organizer_name", "deadline_at", "prize_text", "themes"} <= names
        assert {e.kind for e in candidate.evidence} == {"observed"}
        assert {e.source_url for e in candidate.evidence} == {
            "https://exemplo-game-jam.devpost.com/"
        }

    def test_zero_prize_is_not_recorded(self, source):
        candidate = normalize(source, hackathons()[1])
        assert candidate.fields["prize_text"] == "" and candidate.fields["benefits"] == []

    def test_in_person_in_brazil_is_kept(self, source):
        fields = normalize(source, hackathons()[1]).fields
        assert (fields["modality"], fields["scope"], fields["status"]) == (
            "in_person",
            "national",
            "upcoming",
        )

    @pytest.mark.parametrize(
        ("index", "why"),
        [(2, "presencial fora do Brasil"), (3, "tema fora do filtro"), (4, "só por convite")],
    )
    def test_irrelevant_hackathons_are_ignored(self, source, index, why):
        assert normalize(source, hackathons()[index]) is None, why

    def test_in_person_abroad_is_kept_when_configured(self, source):
        source.config = {**source.config, "allow_in_person": True}
        assert normalize(source, hackathons()[2]) is not None

    def test_keywords_come_from_the_source_config(self, source):
        source.config = {**source.config, "keywords": ["blockchain"]}
        assert normalize(source, hackathons()[3]) is not None
        assert normalize(source, hackathons()[0]) is None

    def test_missing_title_or_foreign_url_is_ignored(self, source):
        assert normalize(source, {**hackathons()[0], "title": ""}) is None
        assert normalize(source, {**hackathons()[0], "url": "https://outro.org/x"}) is None


class TestCollect:
    PAGES = {"1": page("hackathons_page1.json"), "2": page("hackathons_page2.json")}

    def run(self, source, **kwargs):
        return run_source(source, fetcher=make_fetcher(self.PAGES), **kwargs)

    def test_collects_relevant_hackathons_and_stops_at_the_last_page(self, source):
        result = self.run(source)
        assert result.status == "ok"
        # 5 itens na página 1 + 1 novo na página 2 (o repetido é descartado no fetch)
        assert result.items_seen == 6
        titles = set(Opportunity.objects.values_list("title", flat=True))
        assert titles == {
            "Exemplo Game Jam Global",
            "Hackathon Social Futuro",
            "Open Source Education Sprint",
        }
        assert Evidence.objects.filter(method="connector:devpost").exists()

    def test_second_run_does_not_duplicate(self, source):
        self.run(source)
        count = Opportunity.objects.count()
        again = self.run(source)
        assert Opportunity.objects.count() == count
        assert again.items_new == 0

    def test_tracking_params_do_not_create_a_duplicate(self, source):
        # a página 1 traz o link com `ref_feature`; a 2 traz o mesmo hackathon sem ele
        self.run(source)
        assert Opportunity.objects.filter(title="Exemplo Game Jam Global").count() == 1

    def test_dry_run_writes_nothing(self, source):
        self.run(source, dry_run=True)
        assert not Opportunity.objects.exists()

    def test_changed_deadline_updates_the_same_opportunity(self, source):
        self.run(source)
        changed = json.loads(self.PAGES["1"])
        changed["hackathons"][0]["submission_period_dates"] = "Sep 01 - Nov 15, 2026"
        pages = {"1": json.dumps(changed), "2": json.dumps({"hackathons": []})}
        result = run_source(source, fetcher=make_fetcher(pages))
        assert result.items_updated >= 1
        jam = Opportunity.objects.get(title="Exemplo Game Jam Global")
        assert jam.deadline_at.astimezone(SAO_PAULO).date() == date(2026, 11, 15)

    def test_malformed_json_fails_the_source_with_a_clear_error(self, source):
        result = run_source(source, fetcher=make_fetcher({"1": "<html>mudou</html>"}))
        assert result.status == "error"
        assert "Resposta inesperada" in result.error_log

    def test_max_api_pages_is_respected(self, source):
        source.config = {"max_api_pages": 1}
        result = self.run(source)
        assert result.items_seen == 5


class TestRegistration:
    def test_registered_by_slug(self, source):
        assert isinstance(registry.for_source(source), DevpostConnector)

    def test_page_url_asks_for_open_and_upcoming(self, source):
        url = DevpostConnector(source).page_url(2)
        assert url.startswith("https://devpost.com/api/hackathons?")
        assert "status%5B%5D=open" in url and "status%5B%5D=upcoming" in url and "page=2" in url

    def test_initial_source_is_disabled_until_a_human_checks_the_terms(self):
        entry = next(s for s in INITIAL_SOURCES if s["slug"] == "devpost")
        assert entry["enabled"] is False and not entry.get("robots_ok")
        source = Source.objects.create(**entry)
        assert "desabilitada" in runnable_problem(source)
        source.enabled = True
        assert "robots" in runnable_problem(source)

    def test_error_type_is_exported(self):
        assert issubclass(DevpostError, ValueError)
