"""Catálogo de serviços como dado: fixture, carga idempotente e proteção das edições do admin."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import Organization, ServiceOffering

pytestmark = pytest.mark.django_db

PLANNED_SLUGS = {
    "course_gamedev",
    "workshop_gamedev",
    "game_jam_org",
    "extracurricular_school",
    "indie_game",
    "educational_game",
    "institutional_game",
    "gamification",
    "custom_software",
    "web_app",
    "landing_page",
    "institutional_site",
}
# ADR-015: valores iniciais de cobertura pelo MEI (o contador ajusta no admin).
MEI_COVERAGE = {
    "covered": {"course_gamedev", "workshop_gamedev", "extracurricular_school"},
    "verify": {
        "game_jam_org",
        "gamification",
        "educational_game",
        "institutional_game",
        "indie_game",
    },
    "not_covered": {"custom_software", "web_app", "landing_page", "institutional_site"},
}


def run(*args):
    out = StringIO()
    call_command("load_services", *args, stdout=out)
    return out.getvalue()


class TestFixture:
    def test_loaddata_loads_the_twelve_planned_services(self):
        call_command("loaddata", "services", verbosity=0)
        assert set(ServiceOffering.objects.values_list("slug", flat=True)) == PLANNED_SLUGS

    def test_loaddata_twice_updates_instead_of_duplicating(self):
        call_command("loaddata", "services", verbosity=0)
        call_command("loaddata", "services", verbosity=0)
        assert ServiceOffering.objects.count() == 12

    def test_mei_coverage_follows_adr_015(self):
        run()
        for coverage, slugs in MEI_COVERAGE.items():
            found = set(
                ServiceOffering.objects.filter(mei_coverage=coverage).values_list("slug", flat=True)
            )
            assert found == slugs, coverage
        assert sum(len(s) for s in MEI_COVERAGE.values()) == 12

    def test_every_service_is_valid_and_usable_for_matching(self):
        run()
        valid_kinds = set(Organization.Kind.values)
        for service in ServiceOffering.objects.all():
            service.full_clean()
            assert service.keywords, service.slug
            assert service.description, service.slug
            assert service.active
            assert set(service.target_org_kinds) <= valid_kinds, service.slug

    def test_geo_profiles_follow_the_geo_relevance_doc(self):
        run()
        profiles = dict(ServiceOffering.objects.values_list("slug", "geo_profile"))
        assert profiles["course_gamedev"] == "onsite_recurring"
        assert profiles["workshop_gamedev"] == "onsite_recurring"
        assert profiles["extracurricular_school"] == "onsite_recurring"
        assert profiles["game_jam_org"] == "onsite_event"
        assert profiles["indie_game"] == "online"
        for slug in ("custom_software", "web_app", "landing_page", "institutional_site"):
            assert profiles[slug] == "remote_service"

    def test_no_prices_are_shipped_in_the_public_repository(self):
        """Valores comerciais ficam no banco (repositório público — ADR-014), não na fixture."""
        run()
        assert not ServiceOffering.objects.exclude(typical_ticket_min_brl=None).exists()
        assert not ServiceOffering.objects.exclude(typical_ticket_max_brl=None).exists()


class TestLoadServicesCommand:
    def test_creates_the_catalog(self):
        assert "12 criado(s), 0 atualizado(s), 0 mantido(s)" in run()
        assert ServiceOffering.objects.count() == 12

    def test_second_run_changes_nothing(self):
        run()
        assert "0 criado(s), 0 atualizado(s), 12 mantido(s)" in run()

    def test_edits_made_in_the_admin_are_not_overwritten(self):
        run()
        # o contador decidiu: software sob encomenda passa a ser coberto (ex.: após virar ME)
        ServiceOffering.objects.filter(slug="custom_software").update(
            mei_coverage="covered", active=False
        )
        run()
        service = ServiceOffering.objects.get(slug="custom_software")
        assert (service.mei_coverage, service.active) == ("covered", False)

    def test_missing_services_are_added_without_touching_existing_ones(self):
        run()
        ServiceOffering.objects.filter(slug="web_app").delete()
        ServiceOffering.objects.filter(slug="landing_page").update(name="Nome editado")
        assert "1 criado(s), 0 atualizado(s), 11 mantido(s)" in run()
        assert ServiceOffering.objects.get(slug="landing_page").name == "Nome editado"

    def test_update_flag_overwrites_on_request(self):
        run()
        ServiceOffering.objects.filter(slug="custom_software").update(mei_coverage="covered")
        assert "0 criado(s), 12 atualizado(s), 0 mantido(s)" in run("--update")
        assert ServiceOffering.objects.get(slug="custom_software").mei_coverage == "not_covered"

    def test_unknown_field_fails_loudly_and_loads_nothing(self, tmp_path):
        entry = {"model": "core.serviceoffering", "fields": {"slug": "x", "name": "X"}}
        bad = {
            "model": "core.serviceoffering",
            "fields": {
                "slug": "y",
                "name": "Y",
                "category": "web",
                "geo_profile": "online",
                "oops": 1,
            },
        }
        entry["fields"].update({"category": "web", "geo_profile": "online"})
        path = tmp_path / "bad.json"
        path.write_text(json.dumps([entry, bad]), encoding="utf-8")
        with pytest.raises(CommandError, match="oops"):
            run("--file", str(path))
        assert ServiceOffering.objects.count() == 0  # tudo ou nada

    def test_invalid_value_fails_validation_and_loads_nothing(self, tmp_path):
        bad = {
            "model": "core.serviceoffering",
            "fields": {"slug": "x", "name": "X", "category": "web", "geo_profile": "edital_scope"},
        }
        path = tmp_path / "bad.json"
        path.write_text(json.dumps([bad]), encoding="utf-8")
        with pytest.raises(Exception, match="geo_profile"):
            run("--file", str(path))
        assert ServiceOffering.objects.count() == 0

    def test_unexpected_model_and_unreadable_file_are_reported(self, tmp_path):
        path = tmp_path / "other.json"
        path.write_text(json.dumps([{"model": "auth.user", "fields": {}}]), encoding="utf-8")
        with pytest.raises(CommandError, match="inesperada"):
            run("--file", str(path))
        with pytest.raises(CommandError, match="Não foi possível ler"):
            run("--file", str(tmp_path / "missing.json"))
