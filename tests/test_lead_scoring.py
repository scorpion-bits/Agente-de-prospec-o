"""E21 — score de leads: perfis, gates de memória comercial, fatores, comando, admin e digest."""

from datetime import UTC, date, datetime, timedelta
from io import StringIO

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.urls import reverse

from core.models import (
    CompanyProfile,
    ContactPoint,
    Interaction,
    Match,
    Municipality,
    Organization,
    PortfolioItem,
    ServiceOffering,
    Suppression,
    Triage,
)
from core.services.evidence import record_evidence
from reports import digest
from scoring.engine import build_context, save_score
from scoring.leads import LeadData, lead_profile_for, score_lead
from scoring.models import Score

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
TODAY = NOW.date()


@pytest.fixture
def world(db):
    call_command("load_services", stdout=StringIO())
    CompanyProfile.objects.create(legal_form="MEI", opened_at=date(2025, 4, 10))
    Municipality.objects.create(
        ibge_code=3503208, name="Araraquara", uf="SP", lat=-21.7845, lon=-48.178
    )
    Municipality.objects.create(
        ibge_code=3506003, name="Bauru", uf="SP", lat=-22.3147, lon=-49.0587
    )
    return build_context(now=NOW)


def org(name, kind="school", **fields):
    fields.setdefault("municipality_name", "Araraquara")
    fields.setdefault("uf", "SP")
    return Organization.objects.create(name=name, kind=kind, **fields)


def match(organization, slug="course_gamedev", strength=0.8, proof=()):
    service = ServiceOffering.objects.get(slug=slug)
    m = Match.objects.create(organization=organization, service=service, strength=strength)
    m.portfolio_refs.set(proof)
    return m


def interact(organization, days_ago, kind="message", outcome="pending", **fields):
    return Interaction.objects.create(
        organization=organization,
        kind=kind,
        outcome=outcome,
        occurred_at=TODAY - timedelta(days=days_ago),
        **fields,
    )


def score(organization, ctx):
    organization.refresh_from_db()
    profile = lead_profile_for(organization)
    return score_lead(organization, profile, ctx, LeadData([organization]))


def factor(result, key):
    return next(row for row in result.breakdown if row["factor"] == key)


class TestProfile:
    def test_sesc_similar_and_school_profiles(self, db):
        assert lead_profile_for(org("SESC Bauru", "sesc")) == "lead.sesc"
        assert (
            lead_profile_for(org("Parecida", "ngo", similarity_tags=["sistema_s"])) == "lead.sesc"
        )
        assert lead_profile_for(org("Unidade", "other", network="SESC-SP")) == "lead.sesc"
        assert lead_profile_for(org("Escola X", "school")) == "lead.school_course"
        assert lead_profile_for(org("Empresa", "company")) is None


class TestMemoryGates:
    def test_never_contacted_is_a_new_lead_with_a_score(self, world):
        school = org("Escola Nova")
        match(school)
        result = score(school, world)
        assert result.total is not None and not result.gated
        assert result.label != Score.Label.ONGOING

    def test_proposal_sent_is_ongoing_never_new(self, world):
        sesc = org("SESC Bauru", "sesc", network="SESC-SP", municipality_name="Bauru")
        match(sesc)
        Interaction.objects.create(
            organization=sesc, kind="proposal_sent", data_status="pending"
        )  # data ainda não confirmada (P2)
        result = score(sesc, world)
        assert result.label == Score.Label.ONGOING
        assert result.total is not None
        assert "não é lead novo" in result.alerts[0]

    def test_recent_contact_is_ongoing_but_old_lost_contact_is_new_again(self, world):
        recent, old = org("Recente"), org("Antiga")
        for school, days in ((recent, 10), (old, 40)):
            match(school)
            interact(school, days, outcome="lost")
        assert score(recent, world).label == Score.Label.ONGOING
        again = score(old, world)
        assert again.label != Score.Label.ONGOING
        assert "perdido" in factor(again, "C")["explanation"]

    def test_do_not_contact_and_suppression_gate(self, world):
        blocked = org("Bloqueada")
        blocked.relationship_status = Organization.RelationshipStatus.DO_NOT_CONTACT
        blocked.save()
        result = score(blocked, world)
        assert result.gated and result.gate_kind == Score.GateKind.DO_NOT_CONTACT
        listed = org("Na lista")
        Suppression.objects.create(kind="organization", value="na lista", reason="pediu")
        assert score(listed, world).gated


class TestFactors:
    def test_value_from_catalog_ticket_and_no_match_is_neutral_fit_zero(self, world):
        school = org("Escola")
        assert factor(score(school, world), "F")["raw"] == 0.0
        assert "sem dado" in factor(score(school, world), "V")["explanation"]
        match(school)
        service = ServiceOffering.objects.get(slug="course_gamedev")
        service.typical_ticket_min_brl, service.typical_ticket_max_brl = 8000, 12000
        service.save()
        value = factor(score(school, world), "V")
        assert value["raw"] == 0.55 and "R$ 10.000" in value["explanation"]

    def test_fit_cites_portfolio_proof(self, world):
        school = org("Escola")
        item = PortfolioItem.objects.create(slug="gl", title="Game Lab", kind="course", public=True)
        match(school, strength=0.9, proof=[item])
        fit = factor(score(school, world), "F")
        assert fit["raw"] == 0.9 and "Game Lab" in fit["explanation"]

    def test_same_network_as_client_raises_chance(self, world):
        client = org("SESC Araraquara", "sesc", network="SESC-SP")
        interact(client, 200, kind="course_delivered", outcome="won")
        sesc = org("SESC Bauru", "sesc", network="SESC-SP")
        similar = org("Parecida", "ngo", similarity_tags=["sistema_s"])
        plain = org("Escola")
        for o in (sesc, similar, plain):
            match(o)
        chance = {o.name: factor(score(o, world), "C")["raw"] for o in (sesc, similar, plain)}
        assert chance["SESC Bauru"] > chance["Parecida"] > chance["Escola"]

    def test_mei_not_covered_service_lowers_chance_and_alerts(self, world):
        school = org("Escola")
        match(school, slug="custom_software")
        result = score(school, world)
        assert any("exigiria ME" in a for a in result.alerts)

    def test_school_season_and_follow_up(self, world, monkeypatch):
        school = org("Escola")
        match(school)
        assert factor(score(school, world), "T")["raw"] == 0.95  # outubro
        march = build_context(now=datetime(2026, 3, 10, 12, tzinfo=UTC))
        assert factor(score(school, march), "T")["raw"] == 0.5
        interact(school, 30, outcome="lost", next_action="ligar", next_action_at=TODAY)
        due = factor(score(school, march.__class__(**{**march.__dict__, "now": NOW})), "T")
        assert "follow-up" in due["explanation"]
        sesc = org("SESC", "sesc")
        assert "SESC a confirmar" in factor(score(sesc, world), "T")["explanation"]

    def test_access_prefers_reachable_nearby_leads(self, world):
        near, far = org("Perto"), org("Longe", municipality_name="Bauru")
        for o in (near, far):
            match(o)
        ev = record_evidence(
            near, "contact", "x", kind="observed", method="regex:test",
            source_url="https://e.org", excerpt="secretaria@e.org",
        )  # fmt: skip
        ContactPoint.objects.create(
            organization=near, kind="email", value="secretaria@escola.org", evidence=ev
        )
        a_near, a_far = factor(score(near, world), "A"), factor(score(far, world), "A")
        assert a_near["raw"] > a_far["raw"]
        assert "e-mail/telefone" in a_near["explanation"]
        assert "nenhuma forma de contato" in a_far["explanation"]

    def test_breakdown_has_six_factors_and_reproduces(self, world):
        school = org("Escola")
        match(school)
        first, second = score(school, world), score(school, world)
        assert [r["factor"] for r in first.breakdown] == list("VFCTAL")
        assert first.total == second.total and first.confidence <= 1.0


class TestCommand:
    def run(self, *args):
        out = StringIO()
        call_command("rescore", *args, stdout=out)
        return out.getvalue()

    def test_scores_leads_and_ignores_non_leads(self, world):
        school = org("Escola")
        match(school)
        org("Empresa", "company")
        out = self.run("--target", "leads")
        assert "Leads: 1" in out
        stored = Score.objects.get()
        assert stored.entity == school and stored.profile == "lead.school_course"

    def test_dry_run_limit_profile_and_discard(self, world):
        school = org("Escola")
        sesc = org("SESC Bauru", "sesc")
        assert "simulado" in self.run("--target", "leads", "--dry-run")
        assert Score.objects.count() == 0
        assert "Leads: 1" in self.run("--profile", "lead.sesc")
        assert Score.objects.get().entity == sesc
        Triage.objects.create(
            content_type=ContentType.objects.get_for_model(Organization),
            object_id=school.pk,
            status="discarded",
            discard_reason="not_relevant",
        )
        assert "pulados): 1" in self.run("--profile", "lead.school_course")

    def test_save_replaces_the_single_row(self, world):
        school = org("Escola")
        for _ in range(2):
            save_score(school, score(school, world), world)
        assert Score.objects.count() == 1


class TestAdmin:
    @pytest.fixture
    def admin_client(self, client, django_user_model):
        client.force_login(django_user_model.objects.create_superuser("adm", "a@e.org", "x"))
        return client

    def test_organization_list_orders_by_score_and_shows_breakdown(self, admin_client, world):
        school = org("Escola")
        match(school)
        call_command("rescore", "--target", "leads", stdout=StringIO())
        base = reverse("admin:core_organization_changelist")
        for order in ("", "?o=-10", "?o=10"):
            assert admin_client.get(base + order).status_code == 200
        detail = admin_client.get(reverse("admin:core_organization_change", args=[school.pk]))
        html = detail.content.decode()
        assert detail.status_code == 200 and "Soma ponderada" in html and "Valor" in html


class TestDigest:
    def test_new_leads_and_ongoing_sections_are_separate(self, world):
        fresh = org("Escola Nova")
        match(fresh)
        sesc = org("SESC Bauru", "sesc", network="SESC-SP")
        match(sesc)
        Interaction.objects.create(organization=sesc, kind="proposal_sent", data_status="pending")
        call_command("rescore", "--target", "leads", stdout=StringIO())
        d = digest.build(base_url="https://x.test")
        assert [r["name"] for r in d.leads["new"]] == ["Escola Nova"]
        assert [r["name"] for r in d.leads["ongoing"]] == ["SESC Bauru"]
        text = digest.render_markdown(d)
        assert "## Leads da semana (1)" in text and "## Em andamento (1)" in text
        assert "Escola Nova" in digest.render_html(d)

    def test_gated_discarded_and_ignored_leads_never_show(self, world):
        gone = org("Descartada")
        blocked = org("Bloqueada")
        blocked.relationship_status = "do_not_contact"
        blocked.save()
        for o in (gone, blocked):
            match(o)
        call_command("rescore", "--target", "leads", stdout=StringIO())
        Triage.objects.create(
            content_type=ContentType.objects.get_for_model(Organization),
            object_id=gone.pk,
            status="discarded",
            discard_reason="not_relevant",
        )
        d = digest.build(base_url="https://x.test")
        assert d.leads["new"] == [] and d.leads["ongoing"] == []

    def test_suggested_contact_respects_opt_out(self, world):
        school = org("Escola", website="https://escola.example")
        match(school)
        ev = record_evidence(
            school, "contact", "x", kind="observed", method="regex:test",
            source_url="https://escola.example", excerpt="oi@escola.example",
        )  # fmt: skip
        ContactPoint.objects.create(
            organization=school, kind="email", value="oi@escola.example", evidence=ev
        )
        call_command("rescore", "--target", "leads", stdout=StringIO())
        assert (
            "oi@escola.example"
            in digest.build(base_url="https://x.test").leads["new"][0]["contact"]
        )
        Suppression.objects.create(kind="email", value="oi@escola.example", reason="pediu")
        row = digest.build(base_url="https://x.test").leads["new"][0]
        assert "oi@escola.example" not in row["contact"]
