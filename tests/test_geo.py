"""E12 — municípios do IBGE, resolução de localização e perfis de relevância geográfica."""

from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import CommandError, call_command

from core.models import GeoProfile, Municipality, Opportunity, Organization
from core.services.geography import haversine_km, resolve_municipality
from scoring.geo import classify, fmt, geo_relevance, home_municipality

pytestmark = pytest.mark.django_db

# Coordenadas do seed real (sede do município).
PLACES = {
    3503208: ("Araraquara", "SP", -21.7845, -48.178, False),
    3548906: ("São Carlos", "SP", -22.0174, -47.886, False),
    3543402: ("Ribeirão Preto", "SP", -21.1699, -47.8099, False),
    3506003: ("Bauru", "SP", -22.3246, -49.0871, False),
    3525300: ("Jaú", "SP", -22.2964, -48.5578, False),
    3550308: ("São Paulo", "SP", -23.5329, -46.6395, True),
    3501905: ("Américo Brasiliense", "SP", -21.7239, -48.1135, False),
    3304557: ("Rio de Janeiro", "RJ", -22.9129, -43.2003, True),
    2611606: ("Recife", "PE", -8.0539, -34.8811, True),
    4216008: ("São Carlos", "SC", -27.0798, -53.0037, False),
    3543907: ("Rio Claro", "SP", -22.4106, -47.5611, False),
    3170206: ("Uberaba", "MG", -19.7472, -47.9381, False),
}


@pytest.fixture
def places(db):
    return {
        code: Municipality.objects.create(
            ibge_code=code, name=name, uf=uf, lat=lat, lon=lon, is_capital=capital
        )
        for code, (name, uf, lat, lon, capital) in PLACES.items()
    }


@pytest.fixture
def home(places):
    return places[3503208]


def at(places, code, **extra):
    return SimpleNamespace(municipality=places[code], **extra)


class TestMunicipality:
    def test_region_and_keys_are_derived(self, places):
        assert places[3503208].region == "SE"
        assert places[2611606].region == "NE"
        assert places[4216008].region == "S"
        assert places[3503208].name_key == "araraquara"
        assert str(places[3503208]) == "Araraquara/SP"

    def test_same_name_is_allowed_in_different_states_only(self, places):
        from django.db import IntegrityError, transaction

        with pytest.raises(IntegrityError), transaction.atomic():
            Municipality.objects.create(
                ibge_code=3999999, name="são  carlos", uf="SP", lat=-22, lon=-47
            )

    def test_resolve_by_name_and_uf_is_accent_insensitive(self, places):
        assert resolve_municipality("SAO CARLOS", "sp") == places[3548906]
        assert resolve_municipality("Sao Carlos", "SC") == places[4216008]

    def test_homonyms_without_uf_are_not_guessed(self, places):
        assert resolve_municipality("São Carlos") is None
        assert resolve_municipality("Araraquara") == places[3503208]  # nome único
        assert resolve_municipality("Cidade Inexistente", "SP") is None
        assert resolve_municipality("", "SP") is None


class TestAutoResolution:
    def test_organization_gets_its_municipality_on_save(self, places):
        org = Organization.objects.create(name="Escola X", municipality_name="Jau", uf="SP")
        assert org.municipality == places[3525300]

    def test_unknown_or_ambiguous_text_stays_unresolved(self, places):
        org = Organization.objects.create(name="Escola Y", municipality_name="São Carlos")
        assert org.municipality is None
        assert org.municipality_name == "São Carlos"  # o texto original é preservado

    def test_manual_choice_survives_while_it_matches_and_follows_text_changes(self, places):
        org = Organization.objects.create(name="Escola Z", municipality_name="Bauru", uf="SP")
        org.save()
        assert org.municipality == places[3506003]
        org.municipality_name, org.uf = "Recife", "PE"
        org.save()
        assert org.municipality == places[2611606]

    def test_without_text_the_fk_is_kept(self, places):
        org = Organization.objects.create(name="Escola W", municipality=places[3506003])
        org.save()
        assert org.municipality == places[3506003]

    def test_save_with_update_fields_still_persists_the_fk(self, places):
        org = Organization.objects.create(name="Escola V")
        Organization.objects.filter(pk=org.pk).update(municipality_name="Bauru")
        org.refresh_from_db()
        org.save(update_fields=["updated_at"])
        org.refresh_from_db()
        assert org.municipality == places[3506003]  # nome único no país: resolve sem UF

    def test_opportunity_resolves_too(self, places):
        opportunity = Opportunity.objects.create(
            title="Jam", official_url="https://example.org/j", municipality_name="Recife", uf="PE"
        )
        assert opportunity.municipality == places[2611606]


class TestDistancesAndRings:
    def test_known_distances_from_araraquara(self, places, home):
        def km(code):
            return haversine_km(home.lat, home.lon, places[code].lat, places[code].lon)

        assert 35 <= km(3548906) <= 45  # São Carlos
        assert 75 <= km(3543402) <= 85  # Ribeirão Preto
        assert 105 <= km(3506003) <= 115  # Bauru (≈ 111 km: a estimativa do doc era 100)
        assert haversine_km(0, 0, 0, 0) == 0

    @pytest.mark.parametrize(
        ("code", "ring"),
        [
            (3503208, "R0"),
            (3548906, "R1"),  # polo
            (3543402, "R1"),  # polo a ~80 km
            (3506003, "R1"),  # polo a ~100 km
            (3501905, "R1"),  # vizinha
            (3525300, "R2"),  # Jaú
            (3543907, "R2"),  # Rio Claro
            (3170206, "R4"),  # Uberaba (MG) a ~200 km
            (3550308, "R3"),  # capital de SP
            (3304557, "R4"),
            (2611606, "R4"),
        ],
    )
    def test_rings(self, places, home, code, ring):
        assert classify(places[code], home)[0] == ring

    def test_settings_drive_hubs_and_radii(self, places, home, settings):
        settings.PRIORITY_HUBS_IBGE = [3503208]
        assert classify(places[3506003], home)[0] == "R2"
        settings.GEO_NEAR_KM = 120.0
        assert classify(places[3506003], home)[0] == "R1"


class TestOnsiteRecurring:
    P = GeoProfile.ONSITE_RECURRING

    def test_hubs_are_full_relevance_even_far(self, places, home):
        value, text = geo_relevance(at(places, 3506003), self.P, home=home)
        assert value == 1.0
        assert (
            text == "Presencial em Bauru/SP (polo prioritário, R1) — perfil `onsite_recurring`: 1,0"
        )

    def test_r2_decays_linearly_from_40_to_150_km(self, places, home):
        value, text = geo_relevance(at(places, 3525300), self.P, home=home)  # Jaú ≈ 70 km
        assert 0.6 <= value <= 0.7
        assert "R2" in text and "km" in text
        farther = geo_relevance(at(places, 3543907), self.P, home=home).value  # Rio Claro ≈ 95 km
        assert 0.3 < farther < value

    def test_the_rest(self, places, home):
        assert geo_relevance(at(places, 3550308), self.P, home=home).value == 0.15
        assert geo_relevance(at(places, 2611606), self.P, home=home).value == 0.05

    def test_home_is_one(self, places, home):
        assert geo_relevance(at(places, 3503208), self.P, home=home).value == 1.0


class TestOnsiteEvent:
    P = GeoProfile.ONSITE_EVENT

    def test_table(self, places, home):
        value = lambda code: geo_relevance(at(places, code), self.P, home=home).value  # noqa: E731
        assert value(3548906) == 1.0
        assert value(3525300) == 0.7
        assert value(3550308) == 0.5  # capital de SP
        assert value(3304557) == 0.1
        assert value(2611606) == 0.1


class TestOnline:
    def test_distance_is_irrelevant_even_without_location(self, db):
        value, text = geo_relevance(SimpleNamespace(municipality=None), GeoProfile.ONLINE)
        assert (value, text) == (1.0, "Online — distância irrelevante: 1,0")


class TestRemoteService:
    P = GeoProfile.REMOTE_SERVICE

    def test_never_zero_by_distance_and_near_bonus(self, places, home):
        far = geo_relevance(at(places, 2611606), self.P, home=home)
        near = geo_relevance(at(places, 3525300), self.P, home=home)
        assert far.value == 0.85
        assert near.value == 1.0
        assert (
            far.explanation
            == "Serviço remoto para Recife/PE (Brasil, R4) — perfil `remote_service`: 0,85"
        )


class TestEditalScope:
    P = GeoProfile.EDITAL_SCOPE

    def edital(self, places, scope, regions=(), code=3503208):
        return at(places, code, scope=scope, eligible_regions=list(regions))

    def test_scope_table(self, places, home):
        expected = {"regional": 0.9, "state": 0.8, "national": 0.7, "international": 0.4}
        for scope, value in expected.items():
            assert geo_relevance(self.edital(places, scope), self.P, home=home).value == value

    def test_municipal_edital_of_a_hub_is_full(self, places, home):
        value, text = geo_relevance(
            self.edital(places, "municipal", code=3506003), self.P, home=home
        )
        assert value == 1.0 and "polo prioritário" in text

    def test_municipal_edital_elsewhere_weighs_distance(self, places, home):
        value = geo_relevance(
            self.edital(places, "municipal", code=3304557), self.P, home=home
        ).value
        assert value == 0.1

    @pytest.mark.parametrize(
        "regions",
        [["SP"], ["Araraquara"], ["Araraquara/SP"], ["Sudeste"], ["Brasil"], ["RJ", "SP"]],
    )
    def test_eligible_when_the_base_is_covered(self, places, home, regions):
        result = geo_relevance(self.edital(places, "state", regions), self.P, home=home)
        assert not result.gated and result.value == 0.8
        assert "aceita proponentes de Araraquara" in result.explanation

    @pytest.mark.parametrize("regions", [["RJ"], ["Recife/PE"], ["Nordeste"], ["Araraquara/MG"]])
    def test_gate_when_the_base_is_not_covered(self, places, home, regions):
        result = geo_relevance(self.edital(places, "state", regions), self.P, home=home)
        assert result.gated and result.value is None
        assert result.explanation.startswith("GATE: edital restrito a proponentes de")

    def test_empty_regions_means_no_known_restriction(self, places, home):
        assert not geo_relevance(self.edital(places, "national"), self.P, home=home).gated

    def test_unknown_scope_is_neutral(self, places, home):
        result = geo_relevance(self.edital(places, ""), self.P, home=home)
        assert result.value == 0.5 and not result.location_known


class TestMissingData:
    @pytest.mark.parametrize(
        "profile", [GeoProfile.ONSITE_RECURRING, GeoProfile.ONSITE_EVENT, GeoProfile.REMOTE_SERVICE]
    )
    def test_unknown_location_is_neutral_with_reduced_confidence(self, places, home, profile):
        result = geo_relevance(SimpleNamespace(municipality=None), profile, home=home)
        assert result.value == 0.5
        assert not result.location_known
        assert "localização não identificada" in result.explanation

    def test_missing_home_is_explained_not_guessed(self, db):
        result = geo_relevance(SimpleNamespace(municipality=None), GeoProfile.ONSITE_EVENT)
        assert result.value == 0.5 and "load_municipalities" in result.explanation

    def test_result_unpacks_as_value_and_explanation(self, places, home):
        value, explanation = geo_relevance(at(places, 3503208), GeoProfile.ONSITE_EVENT, home=home)
        assert value == 1.0 and "base, R0" in explanation

    def test_number_format(self):
        assert [fmt(x) for x in (1.0, 0.66, 0.5, 0.05, 0.3)] == [
            "1,0",
            "0,66",
            "0,5",
            "0,05",
            "0,3",
        ]

    def test_home_municipality_comes_from_settings(self, places, settings):
        assert home_municipality() == places[3503208]
        settings.HOME_MUNICIPALITY_IBGE = 3550308
        assert home_municipality() == places[3550308]


class TestLoadCommands:
    def load(self, *args):
        out = StringIO()
        call_command("load_municipalities", *args, stdout=out)
        return out.getvalue()

    def test_real_seed_loads_idempotently_with_araraquara_confirmed(self):
        assert "total 5571" in self.load()
        assert Municipality.objects.count() == 5571  # 5.570 municípios + Distrito Federal
        araraquara = Municipality.objects.get(ibge_code=3503208)
        assert (araraquara.name, araraquara.uf) == ("Araraquara", "SP")
        again = self.load()
        assert "0 criado(s)" in again and Municipality.objects.count() == 5571
        assert Municipality.objects.filter(is_capital=True).count() == 27
        assert Municipality.objects.filter(uf="SP").count() == 645

    def test_real_seed_distances_and_rings_match_the_doc(self):
        self.load()
        home = home_municipality()
        rings = {
            name: classify(Municipality.objects.get(name=name, uf="SP"), home)
            for name in ("São Carlos", "Ribeirão Preto", "Bauru")
        }
        assert all(ring == "R1" for ring, _, _ in rings.values())
        assert 35 <= rings["São Carlos"][1] <= 45
        assert 75 <= rings["Ribeirão Preto"][1] <= 85
        assert 105 <= rings["Bauru"][1] <= 115

    def test_bad_files_are_friendly_errors(self, tmp_path):
        with pytest.raises(CommandError, match="Não foi possível ler"):
            self.load(str(tmp_path / "nada.csv"))
        bad = tmp_path / "m.csv"
        bad.write_text("codigo_ibge,nome\n1,2\n")
        with pytest.raises(CommandError, match="faltam as colunas"):
            self.load(str(bad))
        header = "codigo_ibge,nome,uf,latitude,longitude,capital\n"
        for row, message in [
            ("abc,X,SP,-22,-48,0\n", "inválidos"),
            ("3503208,Araraquara,SP,-22,48,0\n", "fora do Brasil"),
            ("12,Araraquara,SP,-22,-48,0\n", "inválidos"),
        ]:
            bad.write_text(header + row)
            with pytest.raises(CommandError, match=message):
                self.load(str(bad))
        assert Municipality.objects.count() == 0

    def test_missing_home_or_hubs_fail_the_load_and_roll_back(self, tmp_path):
        only = tmp_path / "m.csv"
        only.write_text(
            "codigo_ibge,nome,uf,latitude,longitude,capital\n"
            "3503208,Araraquara,SP,-21.78,-48.17,0\n"
        )
        with pytest.raises(CommandError, match="Base/polos fora da carga"):
            self.load(str(only))
        assert Municipality.objects.count() == 0

    def test_uf_comes_from_the_ibge_code_when_the_column_is_blank(self, tmp_path, settings):
        settings.HOME_MUNICIPALITY_IBGE = 3503208
        settings.PRIORITY_HUBS_IBGE = [3503208]
        path = tmp_path / "m.csv"
        path.write_text(
            "codigo_ibge,nome,uf,latitude,longitude,capital\n3503208,Araraquara,,-21.78,-48.17,0\n"
        )
        self.load(str(path))
        assert Municipality.objects.get().uf == "SP"

    def test_resolve_command_backfills_text_only_records(self, places):
        org = Organization.objects.create(name="Escola A")
        Organization.objects.filter(pk=org.pk).update(municipality_name="Jaú", uf="SP")
        Organization.objects.create(name="Escola B")  # sem texto: ignorada
        ambiguous = Organization.objects.create(name="Escola C")
        Organization.objects.filter(pk=ambiguous.pk).update(municipality_name="São Carlos")
        out = StringIO()
        call_command("resolve_municipalities", stdout=out)
        org.refresh_from_db()
        ambiguous.refresh_from_db()
        assert org.municipality == places[3525300]
        assert ambiguous.municipality is None
        assert "1 resolvida(s), 1 sem correspondência" in out.getvalue()
