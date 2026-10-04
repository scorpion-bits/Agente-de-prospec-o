"""E25 — conector de empresas do CNPJ aberto: fixture sintética em CSV e ZIP, filtros e LGPD."""

import zipfile
from io import StringIO

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command

from collection import registry
from collection.connectors import cnpj_estabelecimentos as cnpj_mod
from collection.connectors.cnpj_estabelecimentos import (
    CnpjError,
    cnae_map,
    find_files,
    load_municipality_names,
    parse_date,
)
from collection.runner import run_source, runnable_problem
from core.models import Evidence, Municipality, Organization, Source
from core.services.normalize import _cnpj_check_digit, is_valid_cnpj

pytestmark = pytest.mark.django_db


def make_cnpj(base12: str) -> str:
    d1 = _cnpj_check_digit(base12, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    d2 = _cnpj_check_digit(base12 + d1, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return base12 + d1 + d2


def row(base12, *, fantasy="AGENCIA ALFA", status="02", cnae="7311400", uf="SP", tom="7013"):
    cnpj = make_cnpj(base12)
    cells = [""] * 30
    cells[0:3] = [cnpj[:8], cnpj[8:12], cnpj[12:]]
    cells[3] = "1"
    cells[4] = fantasy
    cells[5] = status
    cells[10] = "20150310"
    cells[11] = cnae
    cells[13:19] = ["RUA", "DAS FLORES", "10", "SALA 2", "CENTRO", "14800000"]
    cells[19] = uf
    cells[20] = tom
    cells[21:28] = ["16", "33330000", "", "", "", "", "contato@alfa.example"]
    return ";".join(f'"{c}"' for c in cells) + "\n"


MUNICIPIOS = '"7013";"ARARAQUARA"\n"6219";"SAO PAULO"\n"6291";"SAO CARLOS"\n'
ROWS = [
    row("123456780001", fantasy="AGENCIA ALFA"),  # entra
    row("123456780002", status="08"),  # baixada
    row("123456780003", cnae="4781400"),  # CNAE fora dos grupos
    row("123456780004", tom="6219"),  # São Paulo: fora do escopo
    row("123456780005", fantasy=""),  # sem nome fantasia (MEI/PF)
    row("123456780006", cnae="8593700", fantasy="IDIOMAS BETA", tom="6291"),  # entra
    row("123456780007", uf="MG"),  # UF fora do escopo
    "linha;quebrada\n",
]


@pytest.fixture
def municipalities():
    for code, name, lat, lon in [
        (3503208, "Araraquara", -21.7845, -48.1780),
        (3548906, "São Carlos", -22.0175, -47.8908),
        (3550308, "São Paulo", -23.5329, -46.6395),
    ]:
        Municipality.objects.create(
            ibge_code=code, name=name, uf="SP", region="SE", lat=lat, lon=lon, is_capital=False
        )


@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "Municipios.csv").write_bytes(MUNICIPIOS.encode("latin-1"))
    with zipfile.ZipFile(tmp_path / "Estabelecimentos0.zip", "w") as archive:
        archive.writestr("K3241.K03200Y0.D60000.ESTABELE", "".join(ROWS).encode("latin-1"))
    return tmp_path


def source_for(data_dir, **config):
    return Source.objects.create(
        slug="cnpj-estabelecimentos",
        name="CNPJ",
        kind=Source.Kind.DATASET,
        base_url="https://dadosabertos.rfb.gov.br/CNPJ/",
        enabled=True,
        config={
            "path": str(data_dir),
            "municipios_path": str(data_dir / "Municipios.csv"),
            "municipalities": ["Araraquara/SP", "São Carlos/SP"],
            **config,
        },
    )


class TestHelpers:
    def test_fixture_cnpjs_are_valid(self):
        assert is_valid_cnpj(make_cnpj("123456780001"))

    def test_parse_date(self):
        assert parse_date("20150310") == "2015-03-10"
        assert (
            parse_date("0") == "" and parse_date("00000000") == "" and parse_date("20151399") == ""
        )

    def test_cnae_map_is_data_with_known_groups(self):
        groups = {entry["group"] for entry in cnae_map().values()}
        assert groups == {"marketing", "courses", "publishing", "events", "web"}
        assert all(len(cnae) == 7 and entry["services"] for cnae, entry in cnae_map().items())

    def test_find_files_errors_clearly(self, tmp_path):
        with pytest.raises(CnpjError, match="Nenhum arquivo"):
            find_files(str(tmp_path))

    def test_municipios_table_is_required(self, tmp_path):
        with pytest.raises(CnpjError, match="Municipios"):
            load_municipality_names(str(tmp_path / "nao-existe.csv"))


class TestCollect:
    def test_imports_only_active_in_scope_with_trade_name(self, municipalities, data_dir):
        source = source_for(data_dir)
        assert runnable_problem(source) is None
        run = run_source(source)
        assert run.status == "ok" and run.items_failed == 0 and run.items_new == 2
        alfa = Organization.objects.get(cnpj=make_cnpj("123456780001"))
        assert (alfa.name, alfa.kind, alfa.cnae_main, alfa.uf) == (
            "Agencia Alfa",
            "company",
            "7311400",
            "SP",
        )
        assert alfa.segment == "Agência de publicidade"
        assert alfa.municipality.name == "Araraquara"
        assert Organization.objects.get(cnpj=make_cnpj("123456780006")).municipality.name == (
            "São Carlos"
        )

    def test_privacy_nothing_personal_is_stored(self, municipalities, data_dir):
        run_source(source_for(data_dir))
        alfa = Organization.objects.get(cnpj=make_cnpj("123456780001"))
        assert alfa.address == "" and alfa.contact_points.count() == 0
        stored = " ".join(str(e.value) for e in Evidence.objects.filter(object_id=alfa.pk)).lower()
        for leaked in ("contato@alfa", "33330000", "flores", "14800000"):
            assert leaked not in stored

    def test_evidence_observed_and_service_hint_inferred(self, municipalities, data_dir):
        run_source(source_for(data_dir))
        alfa = Organization.objects.get(cnpj=make_cnpj("123456780001"))
        by_field = {e.field: e for e in Evidence.objects.filter(object_id=alfa.pk)}
        assert by_field["registration_status"].kind == "observed"
        assert by_field["activity_start_date"].value == "2015-03-10"
        hint = by_field["service_hint"]
        assert hint.kind == "inferred" and hint.method == "rule:cnae_services"
        assert "7311400" in hint.excerpt and hint.value == ["jogos_publicitarios", "gamificacao"]

    def test_groups_and_scope_are_configurable(self, municipalities, data_dir):
        run = run_source(source_for(data_dir, groups=["courses"], municipalities=["Araraquara/SP"]))
        assert run.items_new == 0  # o curso fica em São Carlos; o marketing, fora do grupo
        run = run_source(source_for_second(data_dir))
        assert run.items_new == 1

    def test_rerun_is_idempotent_and_dedupes_by_cnpj(self, municipalities, data_dir):
        source = source_for(data_dir)
        run_source(source)
        again = run_source(source)
        assert (again.items_new, again.items_updated) == (0, 0)
        assert Organization.objects.count() == 2

    def test_plain_csv_and_limit(self, municipalities, data_dir):
        (data_dir / "Estabelecimentos0.zip").unlink()
        (data_dir / "Estabelecimentos1.csv").write_bytes("".join(ROWS).encode("latin-1"))
        run = run_source(source_for(data_dir), limit=1)
        assert run.items_new == 1

    def test_unknown_group_is_rejected(self, data_dir):
        with pytest.raises(ImproperlyConfigured, match="desconhecidos"):
            registry.for_source(source_for(data_dir, groups=["inexistente"]))

    def test_missing_files_fail_the_run_not_the_process(self, municipalities, tmp_path):
        run = run_source(source_for(tmp_path))
        assert run.status == "error"


def source_for_second(data_dir):
    Source.objects.all().delete()
    return source_for(data_dir, groups=["courses"], municipalities=["São Carlos/SP"])


class TestSeed:
    def test_source_is_disabled_by_default_and_registered(self):
        call_command("load_sources", stdout=StringIO())
        source = Source.objects.get(slug="cnpj-estabelecimentos")
        assert not source.enabled
        assert registry.for_source(source).path == "data/cnpj"
        assert cnpj_mod.SLUG == source.slug
