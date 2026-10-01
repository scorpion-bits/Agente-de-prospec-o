"""E20 — matching por regras: cada regra com caso positivo e negativo, motivos e prova."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from core.models import Match, Organization, PortfolioItem, ServiceOffering
from core.services.evidence import record_evidence
from scoring.match_rules import RULES
from scoring.matching import MAX_MATCHES, load_portfolio, match_organization, save_matches

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog(db):
    call_command("load_services", stdout=StringIO())
    return {s.slug: s for s in ServiceOffering.objects.all()}


@pytest.fixture
def portfolio(catalog):
    game_lab = PortfolioItem.objects.create(
        slug="game-lab",
        title="Game Lab",
        kind="course",
        public=True,
        status="pending",
        capability_tags=["jogos", "ensino_presencial"],
    )
    astro = PortfolioItem.objects.create(
        slug="astrodash", title="AstroDash", kind="game", public=True, capability_tags=["jogos"]
    )
    PortfolioItem.objects.create(
        slug="site",
        title="Site",
        kind="website",
        public=True,
        status="to_confirm",
        capability_tags=["web"],
    )
    PortfolioItem.objects.create(
        slug="secret", title="Privado", kind="game", public=False, capability_tags=["jogos"]
    )
    return {"game_lab": game_lab, "astro": astro}


def org(name="Org", **fields):
    fields.setdefault("kind", Organization.Kind.OTHER)
    return Organization.objects.create(name=name, **fields)


def run(organization, catalog, portfolio_items=None):
    items = load_portfolio() if portfolio_items is None else portfolio_items
    return {c.service.slug: c for c in match_organization(organization, catalog, items)}


class TestRules:
    def test_sesc_gets_courses_with_game_lab_as_proof(self, catalog, portfolio):
        got = run(org("SESC Bauru", kind="sesc"), catalog)
        assert set(got) == {"course_gamedev", "workshop_gamedev", "game_jam_org"}
        assert got["course_gamedev"].proof == [portfolio["game_lab"]]
        assert got["course_gamedev"].strength == 0.9

    def test_similar_to_sesc_by_tag(self, catalog, portfolio):
        got = run(
            org("Casa de Cultura", kind="public_body", similarity_tags=["cultural_publico"]),
            catalog,
        )
        assert "workshop_gamedev" in got

    def test_unrelated_org_has_no_match(self, catalog, portfolio):
        assert run(org("Padaria", kind="company", website_status="found"), catalog) == {}

    def test_school_upper_grades_positive_and_negative(self, catalog, portfolio):
        school = org("Colégio A", kind="school")
        record_evidence(
            school,
            "education_stages",
            ["Ensino Fundamental - Anos Finais", "Ensino Médio"],
            kind="observed",
            method="connector:inep-escolas",
            source_url="https://inep.gov.br/x",
        )
        got = run(school, catalog)
        assert {"extracurricular_school", "course_gamedev"} <= set(got)
        assert got["extracurricular_school"].strength == 0.8
        ev_ids = [r.get("evidence_id") for r in got["extracurricular_school"].reasons]
        assert any(ev_ids)

        infantil = org("Escolinha", kind="school")
        record_evidence(
            infantil,
            "education_stages",
            ["Educação Infantil", "Ensino Fundamental - Anos Iniciais"],
            kind="observed",
            method="connector:inep-escolas",
            source_url="https://inep.gov.br/y",
        )
        got = run(infantil, catalog)
        assert "extracurricular_school" not in got
        assert set(got) == {"workshop_gamedev"}  # só o fallback fraco

    def test_plain_fundamental_counts_as_upper_grades(self, catalog, portfolio):
        school = org("Escola B", kind="school")
        record_evidence(
            school,
            "education_stages",
            ["Ensino Fundamental", "Ensino Médio"],
            kind="observed",
            method="connector:x",
            source_url="https://inep.gov.br/z",
        )
        assert "extracurricular_school" in run(school, catalog)

    def test_technical_school_by_tag_and_by_name(self, catalog, portfolio):
        assert "course_gamedev" in run(
            org("SENAI X", similarity_tags=["educacao_tecnica"]), catalog
        )
        assert "workshop_gamedev" in run(org("Escola Técnica Y", kind="school"), catalog)
        assert run(org("Mercado Z", kind="company"), catalog) == {}

    def test_mentions_games_via_evidence_excerpt(self, catalog, portfolio):
        company = org("Edtech", kind="company")
        ev = record_evidence(
            company,
            "about",
            "sobre",
            kind="observed",
            method="regex:about",
            source_url="https://edtech.example/sobre",
            excerpt="Trabalhamos com gamificação e jogos educativos desde 2015",
        )
        got = run(company, catalog)
        assert set(got) == {"educational_game", "gamification"}
        assert got["gamification"].proof == [portfolio["astro"]]
        assert any(r.get("evidence_id") == ev.pk for r in got["gamification"].reasons)
        assert run(org("Outra", kind="company"), catalog) == {}

    def test_no_website_is_weak_and_unconfirmed_site_is_not_proof(self, catalog, portfolio):
        got = run(org("Sem site", kind="company", website_status="not_found"), catalog)
        assert set(got) == {"institutional_site"}
        match = got["institutional_site"]
        assert match.proof == []  # item web está «a confirmar»
        assert match.strength == pytest.approx(0.35 * 0.7, abs=1e-3)
        assert run(org("Com site", kind="company", website_status="found"), catalog) == {}


class TestEngine:
    def test_private_portfolio_is_never_cited(self, catalog, portfolio):
        got = run(org("SESC", kind="sesc"), catalog)
        titles = {p.title for c in got.values() for p in c.proof}
        assert "Privado" not in titles

    def test_without_portfolio_strength_drops_and_reason_says_so(self, catalog):
        got = run(org("SESC", kind="sesc"), catalog, portfolio_items=[])
        cand = got["course_gamedev"]
        assert cand.proof == []
        assert cand.strength == pytest.approx(0.63)
        assert "Sem item de portfólio" in cand.reasons[-1]["text"]

    def test_reasons_are_readable_and_hypothesis_is_inferred(self, catalog, portfolio):
        reasons = run(org("SESC", kind="sesc"), catalog)["course_gamedev"].reasons
        assert reasons[0]["kind"] == "inferred"
        assert all(r["text"] for r in reasons)
        assert reasons[-1]["text"].startswith("Prova: Game Lab")

    def test_at_most_three_matches_strongest_first(self, catalog, portfolio):
        school = org(
            "Escola Técnica Completa",
            kind="school",
            website_status="not_found",
            similarity_tags=["educacao_tecnica", "cultural_publico"],
        )
        record_evidence(
            school,
            "education_stages",
            ["Ensino Médio"],
            kind="observed",
            method="connector:x",
            source_url="https://inep.gov.br/w",
        )
        got = list(match_organization(school, catalog, load_portfolio()))
        assert len(got) == MAX_MATCHES
        assert [c.strength for c in got] == sorted((c.strength for c in got), reverse=True)

    def test_inactive_or_missing_service_is_ignored(self, catalog, portfolio):
        catalog.pop("workshop_gamedev")
        assert "workshop_gamedev" not in run(org("SESC", kind="sesc"), catalog)

    def test_new_rule_in_data_needs_no_engine_change(self, catalog, portfolio):
        rules = [
            {
                "id": "x",
                "when": [{"network_any": ["Rede Z"]}],
                "services": ["web_app"],
                "strength": 0.5,
                "reason": "Regra nova.",
                "proof": {},
            }
        ]
        got = match_organization(org("Z1", network="Rede Z"), catalog, [], rules=rules)
        assert [c.service.slug for c in got] == ["web_app"]

    def test_all_rule_services_exist_in_catalog(self, catalog):
        slugs = {s for rule in RULES for s in rule["services"]}
        assert slugs <= set(catalog)


class TestSaveAndCommand:
    def test_save_is_idempotent_and_removes_stale(self, catalog, portfolio):
        sesc = org("SESC", kind="sesc")
        cands = match_organization(sesc, catalog, load_portfolio())
        assert save_matches(sesc, cands) == (3, 0, 0)
        assert save_matches(sesc, cands) == (0, 3, 0)
        match = Match.objects.get(organization=sesc, service=catalog["course_gamedev"])
        assert list(match.portfolio_refs.all()) == [portfolio["game_lab"]]
        assert save_matches(sesc, cands[:1]) == (0, 1, 2)
        assert Match.objects.filter(organization=sesc).count() == 1

    def test_command_every_sesc_and_school_has_a_match(self, catalog, portfolio):
        org("SESC A", kind="sesc")
        org("Escola A", kind="school")
        org("Padaria", kind="company", website_status="found")
        out = StringIO()
        call_command("match_services", stdout=out)
        text = out.getvalue()
        assert "analisadas: 3; com ≥ 1 match: 2" in text
        assert (
            Match.objects.filter(organization__kind__in=["sesc", "school"])
            .values("organization")
            .distinct()
            .count()
            == 2
        )
        assert "SESC A" not in text  # logs públicos: sem nomes

    def test_dry_run_writes_nothing(self, catalog, portfolio):
        org("SESC A", kind="sesc")
        call_command("match_services", "--dry-run", stdout=StringIO())
        assert Match.objects.count() == 0

    def test_empty_catalog_is_an_error(self, db):
        with pytest.raises(CommandError):
            call_command("match_services", stdout=StringIO())
