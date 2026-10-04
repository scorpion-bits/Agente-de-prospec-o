"""E27 — conector PNCP: fixture sintética, filtro, datas, valor, cota ME/EPP e erros."""

import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from collection import registry
from collection.base import RawItem
from collection.connectors.pncp import (
    DEFAULT_MODALITIES,
    PncpConnector,
    PncpError,
    edital_url,
    parse_amount,
    parse_moment,
)
from collection.fetcher import PoliteFetcher
from collection.runner import run_source, runnable_problem
from core.management.commands.load_sources import INITIAL_SOURCES
from core.models import Evidence, Opportunity, Source

pytestmark = pytest.mark.django_db

PAYLOAD = json.loads(
    (Path(__file__).parent / "fixtures" / "pncp" / "proposta_sp.json").read_text(encoding="utf-8")
)
ROWS = PAYLOAD["data"]
ONE_MODALITY = [{"code": 6, "name": "Pregão eletrônico"}]


@pytest.fixture
def source():
    return Source.objects.create(
        slug="pncp",
        name="PNCP",
        kind=Source.Kind.API,
        base_url="https://pncp.exemplo.invalid/",
        enabled=True,
        robots_ok=True,
        config={"ufs": ["SP"], "modalities": ONE_MODALITY},
    )


def make_fetcher(*, requests=None, response=None):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if requests is not None:
            requests.append(request.url)
        return response(request) if response else httpx.Response(200, json=PAYLOAD)

    return PoliteFetcher(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
    )


def run(source, **kwargs):
    connector = PncpConnector(source)
    return run_source(source, fetcher=make_fetcher(**kwargs), connector=connector)


def normalize(source, row, modality=None):
    item = RawItem(data={**row, "_modality": modality or ONE_MODALITY[0]}, source_url="")
    return PncpConnector(source).normalize(item)


class TestNormalize:
    def test_maps_a_procurement_with_dates_value_and_link(self, source):
        candidate = normalize(source, ROWS[0])
        fields = candidate.fields
        assert fields["kind"] == "procurement" and fields["status"] == "open"
        assert fields["official_url"] == "https://pncp.gov.br/app/editais/11111111000111/2099/42"
        assert fields["organizer_name"] == "Prefeitura Municipal de Exemploville"
        assert (fields["scope"], fields["uf"], fields["municipality_name"]) == (
            "municipal",
            "SP",
            "Exemploville",
        )
        assert fields["prize_amount_brl"] == Decimal("48500.50")
        assert fields["deadline_at"].year == 2099 and fields["opens_at"].year == 2020
        assert {"games", "education"} <= set(fields["categories"])
        assert "<b>" not in fields["description"] and fields["benefits"] == ["contract"]
        assert candidate.canonical_key == "pncp:11111111000111-1-000042/2099"

    def test_exclusive_small_business_only_when_the_text_says_so(self, source):
        assert normalize(source, ROWS[0]).fields["exclusive_small_business"] is True
        assert normalize(source, ROWS[1]).fields["exclusive_small_business"] is None

    def test_zero_value_is_unknown_not_zero(self, source):
        fields = normalize(source, ROWS[1]).fields
        assert fields["prize_amount_brl"] is None and fields["prize_text"] == ""
        assert fields["status"] == "upcoming" and fields["scope"] == "state"

    def test_credenciamento_is_a_call_for_partners_and_has_no_invented_dates(self, source):
        candidate = normalize(source, ROWS[2])
        assert candidate.fields["kind"] == "call_for_partners"
        assert candidate.fields["opens_at"] is None
        assert "opens_at" not in {e.field for e in candidate.evidence}

    def test_evidence_is_observed_with_the_edital_link(self, source):
        candidate = normalize(source, ROWS[0])
        assert {e.kind for e in candidate.evidence} == {"observed"}
        assert {e.source_url for e in candidate.evidence} == {candidate.fields["official_url"]}
        assert {"organizer_name", "estimated_value_brl", "deadline_at"} <= {
            e.field for e in candidate.evidence
        }

    def test_irrelevant_closed_and_incomplete_are_dropped(self, source):
        assert normalize(source, ROWS[3]) is None  # ar condicionado/veículos
        assert normalize(source, ROWS[4]) is None  # prazo vencido
        assert normalize(source, ROWS[5]) is None  # sem número de controle válido nem link
        assert normalize(source, {**ROWS[0], "objetoCompra": ""}) is None

    def test_include_closed_keeps_expired(self, source):
        source.config = {**source.config, "include_closed": True}
        assert normalize(source, ROWS[4]).fields["status"] == "closed"

    def test_origin_link_is_the_fallback_when_the_control_number_is_odd(self, source):
        row = {**ROWS[5], "linkSistemaOrigem": "https://compras.exemplo.invalid/x"}
        assert normalize(source, row).fields["official_url"].endswith("/x")

    def test_keywords_match_word_starts_ignoring_accents(self, source):
        row = {**ROWS[3], "objetoCompra": "CAPACITAÇÃO de servidores", "informacaoComplementar": ""}
        assert normalize(source, row) is not None
        assert normalize(source, {**row, "objetoCompra": "Compra de cadeiras"}) is None

    @pytest.mark.parametrize(
        ("control", "expected"),
        [
            (
                "11111111000111-1-000042/2099",
                "https://pncp.gov.br/app/editais/11111111000111/2099/42",
            ),
            ("lixo", ""),
        ],
    )
    def test_edital_url(self, control, expected):
        assert edital_url(control) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(1234.5, "1234.50"), ("10", "10.00"), (0, None), (-5, None), (None, None), ("x", None)],
    )
    def test_parse_amount(self, value, expected):
        assert parse_amount(value) == (Decimal(expected) if expected else None)

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2099-05-02T17:00:00", "2099-05-02T17:00:00-03:00"),
            ("2099-05-02T10:00:00Z", "2099-05-02T07:00:00-03:00"),
            ("", None),
            ("breve", None),
        ],
    )
    def test_parse_moment(self, value, expected):
        moment = parse_moment(value)
        assert (moment.isoformat() if moment else None) == expected


class TestCollect:
    def test_collects_and_filters(self, source):
        run_ = run(source)
        assert run_.status == "ok", run_.error_log
        assert Opportunity.objects.count() == 3 and run_.items_new == 3
        assert Evidence.objects.filter(kind="observed").exists()
        assert not Evidence.objects.exclude(kind="observed").exists()

    def test_second_run_does_not_duplicate(self, source):
        run(source)
        assert run(source).items_new == 0 and Opportunity.objects.count() == 3

    def test_request_uses_uf_modality_and_horizon(self, source):
        requests = []
        run(source, requests=requests)
        params = requests[0].params
        assert requests[0].path == "/api/consulta/v1/contratacoes/proposta"
        assert (params["uf"], params["codigoModalidadeContratacao"]) == ("SP", "6")
        assert len(params["dataFinal"]) == 8 and params["pagina"] == "1"
        assert len(requests) == 1  # página curta: uma só

    def test_full_page_asks_for_the_next_one_up_to_the_pages_reported(self, source):
        source.config = {**source.config, "page_size": 2, "max_pages_per_query": 5}
        paged = {**PAYLOAD, "totalPaginas": 2, "data": ROWS[:2]}
        requests = []
        run(source, requests=requests, response=lambda r: httpx.Response(200, json=paged))
        assert [r.params["pagina"] for r in requests] == ["1", "2"]

    def test_204_is_an_empty_result(self, source):
        run_ = run(source, response=lambda r: httpx.Response(204))
        assert run_.status == "ok" and Opportunity.objects.count() == 0

    def test_one_query_per_uf_and_modality_and_failures_are_isolated(self, source):
        source.config = {"ufs": ["SP"], "modalities": [*ONE_MODALITY, DEFAULT_MODALITIES[0]]}

        def response(request):
            if request.url.params["codigoModalidadeContratacao"] == "4":
                return httpx.Response(200, text="<html>manutenção</html>")
            return httpx.Response(200, json=PAYLOAD)

        run_ = run(source, response=response)
        assert run_.status == "partial" and "SP/Concorrência eletrônica" in run_.error_log
        assert Opportunity.objects.count() == 3

    def test_response_without_data_is_an_explicit_error(self, source):
        run_ = run(source, response=lambda r: httpx.Response(200, json={"erro": "x"}))
        assert "sem `data`" in run_.error_log and Opportunity.objects.count() == 0

    def test_dry_run_writes_nothing(self, source):
        run_source(source, fetcher=make_fetcher(), connector=PncpConnector(source), dry_run=True)
        assert Opportunity.objects.count() == 0

    def test_invalid_config_is_an_explicit_error(self, source):
        for config in (
            {"ufs": ["SAO"]},
            {"modalities": [{"name": "sem código"}]},
            {"exclude_patterns": ["("]},
        ):
            source.config = config
            with pytest.raises(PncpError):
                PncpConnector(source)


class TestSetup:
    def test_connector_is_registered_by_slug(self, source):
        assert isinstance(registry.for_source(source), PncpConnector)

    def test_registered_source_starts_disabled_and_unchecked(self):
        spec = next(s for s in INITIAL_SOURCES if s["slug"] == "pncp")
        assert spec["enabled"] is False and not spec.get("robots_ok")
        assert runnable_problem(Source.objects.create(**spec))
