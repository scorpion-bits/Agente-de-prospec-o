"""E17 — rede SESC-SP (CSV curado) e escolas privadas do INEP (dataset local)."""

import csv
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

from collection import registry
from collection.connectors import inep_schools
from collection.connectors.inep_schools import InepError, map_headers, pretty_name
from collection.runner import run_source, runnable_problem
from core.models import Evidence, Interaction, Municipality, Organization, Source

pytestmark = pytest.mark.django_db

HEADER = (
    "Restrição de Atendimento;Escola;Código INEP;UF;Município;Localização;"
    "Dependência Administrativa;Endereço;Telefone;Porte da Escola;"
    "Etapas e Modalidade de Ensino Oferecidas;Latitude;Longitude\n"
)


@pytest.fixture
def municipalities():
    rows = [
        (3503208, "Araraquara", "SP", -21.7845, -48.1780),
        (3548906, "São Carlos", "SP", -22.0175, -47.8908),
        (3506003, "Bauru", "SP", -22.3246, -49.0871),
        (3550308, "São Paulo", "SP", -23.5329, -46.6395),
    ]
    for code, name, uf, lat, lon in rows:
        Municipality.objects.create(
            ibge_code=code, name=name, uf=uf, region="SE", lat=lat, lon=lon, is_capital=False
        )


def inep_source(tmp_path, rows: str, *, header=HEADER, **config):
    path = tmp_path / "catalogo.csv"
    path.write_text(header + rows, encoding="utf-8")
    return Source.objects.create(
        slug="inep-escolas",
        name="INEP",
        kind=Source.Kind.DATASET,
        base_url="https://www.gov.br/inep/catalogo",
        enabled=True,
        config={"path": str(path), **config},
    )


ROWS = (
    "Em atividade;COLEGIO ALFA DE ARARAQUARA;35000001;SP;Araraquara;Urbana;Privada;"
    "RUA A, 10;(16) 3333-0001;Média;Ensino Fundamental, Ensino Médio;-21,78;-48,17\n"
    "Em atividade;ESCOLA PUBLICA BETA;35000002;SP;Araraquara;Urbana;Municipal;RUA B;;;;;\n"
    "Paralisada;COLEGIO GAMA;35000003;SP;Araraquara;Urbana;Privada;RUA C;;;;;\n"
    "Em atividade;COLEGIO DELTA;35000004;SP;São Paulo;Urbana;Privada;RUA D;;;;;\n"
    "Em atividade;COLEGIO EPSILON;35000005;SP;São Carlos;Urbana;Privada;RUA E;;;"
    "Educação Infantil;;\n"
)


class TestSescSp:
    def test_seed_csv_has_one_unit_per_row_with_no_personal_data(self):
        path = Path(settings.BASE_DIR) / "data/seeds/sesc_sp.csv"
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        names = [r["name"] for r in rows]
        assert len(rows) == len(set(names)) >= 40
        assert {"SESC Araraquara", "SESC Bauru", "SESC Ribeirão Preto", "SESC São Carlos"} <= set(
            names
        )
        assert all(r["curated_at"] and r["uf"] == "SP" for r in rows)
        assert set(rows[0]) == {"name", "municipality", "uf", "website", "source_url", "curated_at"}

    def test_collect_creates_units_under_the_network_parent(self, municipalities):
        call_command("load_sources", stdout=StringIO())
        source = Source.objects.get(slug="sesc-sp-unidades")
        assert runnable_problem(source) is None
        run = run_source(source)
        assert run.status == "ok" and run.items_failed == 0
        parent = Organization.objects.get(name="SESC-SP", parent=None)
        units = Organization.objects.filter(parent=parent)
        assert units.count() == run.items_new
        bauru = units.get(name="SESC Bauru")
        assert (bauru.kind, bauru.network, bauru.uf) == ("sesc", "SESC-SP", "SP")
        assert bauru.municipality.name == "Bauru"
        assert bauru.first_seen_source == source
        evidence = Evidence.objects.filter(object_id=bauru.pk, field="unit_list_curated_at").get()
        assert (evidence.kind, evidence.method, evidence.value) == (
            "manual",
            "human",
            "2026-10-01",
        )

    def test_already_contacted_units_are_recognised_not_duplicated(self, municipalities):
        call_command("load_sources", stdout=StringIO())
        existing = Organization.objects.create(
            name="SESC Sao Carlos", kind="sesc", network="SESC-SP", municipality_name="Sao Carlos"
        )
        Interaction.objects.create(
            organization=existing,
            kind=Interaction.Kind.PROPOSAL_SENT,
            occurred_at="2026-09-01",
            summary="Proposta enviada",
        )
        run_source(Source.objects.get(slug="sesc-sp-unidades"))
        assert Organization.objects.filter(network="SESC-SP", name__icontains="Carlos").count() == 1
        existing.refresh_from_db()
        assert existing.relationship_status == "proposal_sent"
        assert existing.parent.name == "SESC-SP"
        assert existing.first_seen_source is None  # não reescreve a origem de quem já existia

    def test_second_run_is_idempotent(self, municipalities):
        call_command("load_sources", stdout=StringIO())
        source = Source.objects.get(slug="sesc-sp-unidades")
        run_source(source)
        total = Organization.objects.count()
        again = run_source(source)
        assert (again.items_new, again.items_updated) == (0, 0)
        assert Organization.objects.count() == total

    def test_load_sources_keeps_admin_edits(self):
        call_command("load_sources", stdout=StringIO())
        Source.objects.filter(slug="inep-escolas").update(enabled=True, reliability=2)
        call_command("load_sources", stdout=StringIO())
        source = Source.objects.get(slug="inep-escolas")
        assert source.enabled and source.reliability == 2
        assert Source.objects.get(slug="inep-escolas").kind == "dataset"


class TestInepHelpers:
    def test_pretty_name(self):
        assert pretty_name("COLEGIO NOSSA SENHORA DE FATIMA") == "Colegio Nossa Senhora de Fatima"
        assert pretty_name("Colégio São José") == "Colégio São José"

    def test_headers_mapped_by_name_not_position(self):
        shuffled = ["Latitude", "Dependência Administrativa", "UF", "Município", "Código INEP"]
        with pytest.raises(InepError, match="escola"):
            map_headers(shuffled)
        mapping = map_headers([*shuffled, "ESCOLA"])
        assert mapping["inep_code"] == "Código INEP" and mapping["name"] == "ESCOLA"

    def test_microdata_column_names_are_accepted(self):
        mapping = map_headers(
            ["CO_ENTIDADE", "NO_ENTIDADE", "SG_UF", "NO_MUNICIPIO", "TP_DEPENDENCIA"]
        )
        assert mapping["dependency"] == "TP_DEPENDENCIA"
        assert inep_schools.is_private("4") and not inep_schools.is_private("3")

    def test_active_rules(self):
        assert inep_schools.is_active("Escola em atividade")
        assert inep_schools.is_active("1") and inep_schools.is_active(None)
        assert not inep_schools.is_active("Paralisada")
        assert not inep_schools.is_active("Extinta (ano anterior)")


class TestInepConnector:
    def test_imports_only_private_active_schools_in_scope(self, tmp_path, municipalities):
        source = inep_source(tmp_path, ROWS)
        assert runnable_problem(source) is None  # arquivo local: sem rede, sem robots_ok
        run = run_source(source)
        assert (run.status, run.items_seen, run.items_new) == ("ok", 2, 2)
        names = set(Organization.objects.values_list("name", flat=True))
        assert names == {"Colegio Alfa de Araraquara", "Colegio Epsilon"}

    def test_school_fields_and_observed_evidence(self, tmp_path, municipalities):
        run_source(inep_source(tmp_path, ROWS))
        school = Organization.objects.get(inep_code="35000001")
        assert school.kind == "school" and school.municipality.name == "Araraquara"
        assert school.address == "RUA A, 10" and school.lat == pytest.approx(-21.78)
        evidence = {e.field: e for e in Evidence.objects.filter(object_id=school.pk)}
        assert evidence["education_stages"].value == ["Ensino Fundamental", "Ensino Médio"]
        assert evidence["phone"].value == "(16) 3333-0001"
        assert evidence["administrative_dependency"].value == "Privada"
        assert all(e.kind == "observed" and e.source_url for e in evidence.values())
        assert evidence["inep_code"].method == "connector:inep-escolas"

    def test_idempotent_by_inep_code(self, tmp_path, municipalities):
        source = inep_source(tmp_path, ROWS)
        run_source(source)
        again = run_source(source)
        assert (again.items_new, again.items_updated, again.items_failed) == (0, 0, 0)
        assert Organization.objects.filter(kind="school").count() == 2

    def test_known_school_without_inep_code_gets_it_filled_not_duplicated(
        self, tmp_path, municipalities
    ):
        manual = Organization.objects.create(
            name="Colegio Alfa de Araraquara",
            kind="school",
            municipality_name="Araraquara",
            uf="SP",
        )
        run = run_source(inep_source(tmp_path, ROWS))
        assert run.items_new == 1 and run.items_updated == 1
        manual.refresh_from_db()
        assert manual.inep_code == "35000001"
        assert Organization.objects.filter(name__icontains="alfa").count() == 1

    def test_scope_can_be_set_by_municipality_list(self, tmp_path, municipalities):
        source = inep_source(tmp_path, ROWS, municipalities=["São Paulo/SP"])
        run_source(source)
        assert list(Organization.objects.values_list("name", flat=True)) == ["Colegio Delta"]

    def test_max_km_keeps_priority_hubs_but_drops_other_far_municipalities(
        self, tmp_path, municipalities
    ):
        rows = ROWS + "Em atividade;COLEGIO OMEGA;35000006;SP;Bauru;;Privada;RUA F;;;;;\n"
        Municipality.objects.filter(name="Bauru").update(ibge_code=3506999)  # deixa de ser polo
        run_source(inep_source(tmp_path, rows, max_km=10))
        assert set(Organization.objects.values_list("name", flat=True)) == {
            "Colegio Alfa de Araraquara",
            "Colegio Epsilon",  # São Carlos é polo prioritário
        }

    def test_changed_layout_fails_loudly_and_imports_nothing(self, tmp_path, municipalities):
        source = inep_source(tmp_path, "x;y\n", header="Coluna A;Coluna B\n")
        run = run_source(source)
        assert run.status == "error" and "Colunas obrigatórias" in run.error_log
        assert Organization.objects.count() == 0

    def test_missing_file_is_an_actionable_error(self, tmp_path, municipalities):
        source = inep_source(tmp_path, ROWS)
        Path(source.config["path"]).unlink()
        run = run_source(source)
        assert run.status == "error" and "Baixe o Catálogo" in run.error_log

    def test_latin1_semicolon_file(self, tmp_path, municipalities):
        source = inep_source(tmp_path, "")
        Path(source.config["path"]).write_bytes(
            (HEADER + "Em atividade;COLÉGIO ZETA;35000009;SP;Araraquara;;Privada;;;;;;\n").encode(
                "latin-1"
            )
        )
        run_source(source)
        assert Organization.objects.get(inep_code="35000009").name == "Colégio Zeta"

    def test_bad_row_does_not_stop_the_rest(self, tmp_path, municipalities):
        rows = "Em atividade;SEM CODIGO;;SP;Araraquara;;Privada;;;;;;\n" + ROWS
        run = run_source(inep_source(tmp_path, rows))
        assert (run.status, run.items_failed, run.items_new) == ("partial", 1, 2)
        assert "sem código INEP" in run.error_log

    def test_registered_for_the_source_slug(self, tmp_path):
        connector = registry.for_source(inep_source(tmp_path, ROWS))
        assert isinstance(connector, inep_schools.InepSchoolsConnector)

    def test_remote_url_source_still_requires_robots_ok(self):
        source = Source(
            slug="x", kind="dataset", enabled=True, config={"url": "https://example.org/a.csv"}
        )
        assert "robots" in runnable_problem(source)


class TestCountOrganizations:
    def test_counts_by_municipality_without_names(self, tmp_path, municipalities):
        run_source(inep_source(tmp_path, ROWS))
        out = StringIO()
        call_command("count_organizations", "school", stdout=out)
        text = out.getvalue()
        assert "Araraquara/SP: 1" in text and "São Carlos/SP: 1" in text
        assert "Total de school: 2" in text and "Colegio" not in text
