"""E17b — organizações parecidas com o SESC (CSV curado, tags de similaridade)."""

import csv
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.urls import reverse

from collection.runner import run_source
from core.models import Evidence, Interaction, Organization, Source
from core.services.similarity import SIMILARITY_TAGS, clean_tags

pytestmark = pytest.mark.django_db

SEED = Path(settings.BASE_DIR) / "data/seeds/similar_orgs.csv"
HEADER = "name,kind,network,parent,municipality,uf,website,tags,source_url,curated_at\n"


def seed_rows():
    return list(csv.DictReader(SEED.open(encoding="utf-8")))


def source_with(tmp_path, body: str):
    path = tmp_path / "similar.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return Source.objects.create(
        slug="orgs-parecidas-sesc",
        name="Parecidas",
        kind=Source.Kind.SEED_CSV,
        enabled=True,
        robots_ok=True,
        config={"path": str(path), "entity": "organization"},
    )


class TestSeed:
    def test_has_at_least_20_orgs_in_the_hubs_with_valid_tags(self):
        rows = seed_rows()
        units = [r for r in rows if r["municipality"]]
        assert len(units) >= 20
        hubs = {"Araraquara", "São Carlos", "Ribeirão Preto", "Bauru"}
        assert len({r["municipality"] for r in units} & hubs) == 4
        for row in rows:
            assert clean_tags(row["tags"]), row["name"]
        assert len({r["name"] for r in rows}) == len(rows)

    def test_every_org_has_an_official_url_itself_or_through_its_network(self):
        rows = seed_rows()
        network_sites = {r["name"] for r in rows if r["website"] and not r["municipality"]}
        for row in rows:
            assert row["website"] or row["parent"] in network_sites, row["name"]

    def test_websites_are_not_repeated_so_domain_dedupe_cannot_merge_units(self):
        sites = [r["website"] for r in seed_rows() if r["website"]]
        assert len(sites) == len(set(sites))

    def test_no_personal_data(self):
        for row in seed_rows():
            assert "@" not in "".join(row.values())


class TestTags:
    def test_clean_tags(self):
        assert clean_tags("Sistema_S | educacao_nao_formal|sistema_s|") == [
            "sistema_s",
            "educacao_nao_formal",
        ]

    def test_unknown_tag_is_rejected(self):
        with pytest.raises(ValueError, match="inventada"):
            clean_tags("sistema_s|inventada")


class TestCollect:
    def test_seed_collect_creates_units_under_network_parents(self):
        call_command("load_sources", stdout=StringIO())
        run = run_source(Source.objects.get(slug="orgs-parecidas-sesc"))
        assert run.status == "ok" and run.items_failed == 0
        senac = Organization.objects.get(name="SENAC-SP")
        unit = Organization.objects.get(name="SENAC Bauru")
        assert unit.parent == senac and unit.network == "SENAC-SP"
        assert unit.similarity_tags == ["sistema_s", "educacao_nao_formal"]
        evidence = Evidence.objects.filter(object_id=unit.pk, field="similarity_tags").get()
        assert (evidence.kind, evidence.method) == ("manual", "human")
        assert Organization.objects.filter(similarity_tags__len__gt=0).count() == run.items_seen

    def test_second_run_is_idempotent(self):
        call_command("load_sources", stdout=StringIO())
        source = Source.objects.get(slug="orgs-parecidas-sesc")
        run_source(source)
        total = Organization.objects.count()
        again = run_source(source)
        assert (again.items_new, again.items_updated) == (0, 0)
        assert Organization.objects.count() == total

    def test_known_org_keeps_history_and_gets_tags_without_losing_manual_ones(self, tmp_path):
        existing = Organization.objects.create(
            name="SENAC Bauru",
            kind="other",
            network="SENAC-SP",
            municipality_name="Bauru",
            similarity_tags=["baixa_prioridade"],
        )
        Interaction.objects.create(
            organization=existing,
            kind=Interaction.Kind.PROPOSAL_SENT,
            occurred_at="2026-09-01",
            summary="Proposta enviada",
        )
        source = source_with(
            tmp_path,
            "SENAC Bauru,other,SENAC-SP,SENAC-SP,Bauru,SP,,sistema_s,,2026-10-01\n",
        )
        run = run_source(source)
        assert run.items_new == 0 and run.items_updated == 1
        existing.refresh_from_db()
        assert Organization.objects.filter(name="SENAC Bauru").count() == 1
        assert existing.similarity_tags == ["baixa_prioridade", "sistema_s"]
        assert existing.relationship_status == "proposal_sent"
        assert existing.parent.name == "SENAC-SP"

    def test_unknown_tag_fails_only_that_row(self, tmp_path):
        source = source_with(
            tmp_path,
            "Org Boa,other,,,Bauru,SP,,sistema_s,,2026-10-01\n"
            "Org Ruim,other,,,Bauru,SP,,tag_inventada,,2026-10-01\n"
            "Org Sem Tag,other,,,Bauru,SP,,,,2026-10-01\n",
        )
        run = run_source(source)
        assert (run.items_new, run.items_failed) == (1, 2)
        assert not Organization.objects.filter(name="Org Ruim").exists()

    def test_load_sources_creates_enabled_local_source(self):
        call_command("load_sources", stdout=StringIO())
        source = Source.objects.get(slug="orgs-parecidas-sesc")
        assert source.enabled and source.robots_ok and source.kind == "seed_csv"


class TestAdminFilter:
    def test_filters_similar_to_sesc(self, admin_client):
        Organization.objects.create(name="Parecida", similarity_tags=["sistema_s"])
        Organization.objects.create(name="Outra", similarity_tags=["ciencia_cultura"])
        Organization.objects.create(name="Escola Comum")
        url = reverse("admin:core_organization_changelist")

        def names(query):
            response = admin_client.get(url, query)
            return {o.name for o in response.context["cl"].result_list}

        assert names({"similar": "any"}) == {"Parecida", "Outra"}
        assert names({"similar": "sistema_s"}) == {"Parecida"}
        assert names({}) == {"Parecida", "Outra", "Escola Comum"}

    def test_every_tag_has_a_label(self):
        assert all(SIMILARITY_TAGS.values())
