"""E24 — rascunho de abordagem: fatos, validador, A/B, opt-out e admin (sem rede)."""

import json
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse

from core.models import (
    Interaction,
    Match,
    OutreachDraft,
    PortfolioItem,
    ServiceOffering,
)
from core.services.evidence import record_evidence
from core.services.outreach import (
    DraftOutput,
    OutreachBlocked,
    OutreachError,
    build_facts,
    generate_draft,
    validate_draft,
)
from core.services.suppression import register_opt_out
from llm.providers.fake import FakeProvider
from llm.router import AIService
from llm.types import DataClass

pytestmark = pytest.mark.django_db

PORTFOLIO_URL = "https://scorpionbits.itch.io/astrodash"


@pytest.fixture
def world(organization):
    call_command("load_services", stdout=StringIO())
    service = ServiceOffering.objects.get(slug="course_gamedev")
    item = PortfolioItem.objects.create(
        slug="astrodash",
        title="AstroDash",
        kind="game",
        year=2025,
        public=True,
        public_url=PORTFOLIO_URL,
        status="complete",
    )
    match = Match.objects.create(
        organization=organization,
        service=service,
        strength=0.8,
        reasons=[{"text": "Escolas procuram extracurricular de tecnologia", "kind": "inferred"}],
    )
    match.portfolio_refs.add(item)
    return organization, service


def paid(replies, name="anthropic"):
    return FakeProvider(replies, name=name, billing="money")


def ai_with(*replies, name="anthropic"):
    return AIService(providers={name: paid(replies, name)})


def good_reply(facts):
    ids = {f["kind"]: f["id"] for f in facts}
    return json.dumps(
        {
            "subject": "Oficina de jogos para a Escola Exemplo",
            "body": f"Olá! Somos a Scorpion Bits (scorpionbits.com). Veja: {PORTFOLIO_URL}",
            "claims": [
                {"text": "Somos a Scorpion Bits", "about": "scorpion", "facts": [ids["intro"]]},
                {"text": "AstroDash", "about": "scorpion", "facts": [ids["portfolio"]]},
            ],
        }
    )


def facts_of(organization, service):
    match = Match.objects.filter(organization=organization, service=service).first()
    return build_facts(organization, service, match)


class TestFacts:
    def test_only_public_proof_observed_evidence_and_no_contacts(self, world):
        organization, service = world
        record_evidence(
            organization,
            "website",
            "https://escola.example",
            kind="observed",
            source_url="https://escola.example",
            excerpt="Oferecemos robótica no contraturno",
            method="connector:test",
        )
        record_evidence(
            organization,
            "contact.email",
            "x@escola.example",
            kind="observed",
            source_url="https://escola.example/contato",
            excerpt="x@escola.example",
            method="connector:test",
        )
        PortfolioItem.objects.create(slug="privado", title="Segredo", kind="game", public=False)
        facts = facts_of(organization, service)
        texts = " | ".join(f.text for f in facts)
        assert "robótica no contraturno" in texts
        assert "@" not in texts and "Segredo" not in texts
        assert {f.kind for f in facts} >= {"intro", "record", "observed", "offer", "portfolio"}

    def test_history_makes_it_a_follow_up(self, world):
        organization, service = world
        Interaction.objects.create(
            organization=organization,
            kind="proposal_sent",
            occurred_at=date(2026, 9, 10),
            service=service,
        )
        plan = generate_draft(organization, ai=ai_with(), strategies=["rules"])
        assert plan.mode == "follow_up"
        assert "proposta" in plan.body.lower()
        assert "10/09/2026" in plan.body


class TestValidator:
    def facts(self, world):
        return facts_of(*world)

    def check(self, world, **fields):
        base = {"subject": "Oi", "body": "Olá", "claims": []}
        out = DraftOutput.model_validate({**base, **fields})
        return validate_draft(out, self.facts(world), "email")

    def test_claim_without_facts_or_with_unknown_fact_is_rejected(self, world):
        issues = self.check(
            world,
            claims=[
                {"text": "a", "about": "recipient", "facts": []},
                {"text": "b", "about": "recipient", "facts": ["F99"]},
            ],
        )
        assert any("sem fato citado" in i for i in issues)
        assert any("inexistente" in i for i in issues)

    def test_claim_about_recipient_cannot_rest_on_portfolio_or_hypothesis(self, world):
        facts = self.facts(world)
        hyp = next(f for f in facts if f.kind == "hypothesis")
        issues = self.check(world, claims=[{"text": "x", "about": "recipient", "facts": [hyp.id]}])
        assert any("tipo certo" in i for i in issues)

    def test_invented_link_number_and_contact_are_rejected(self, world):
        record = next(f for f in self.facts(world) if f.kind == "record")
        claims = [{"text": "x", "about": "recipient", "facts": [record.id]}]
        assert any(
            "link" in i for i in self.check(world, body="Veja https://outro.com/x", claims=claims)
        )
        assert any(
            "número" in i for i in self.check(world, body="Atendemos 30 escolas", claims=claims)
        )
        assert any(
            "e-mail" in i for i in self.check(world, body="Escreva a fulano@x.com", claims=claims)
        )

    def test_whatsapp_has_no_subject_and_valid_draft_passes(self, world):
        facts = self.facts(world)
        ids = {f.kind: f.id for f in facts}
        out = DraftOutput.model_validate(
            {
                "subject": "",
                "body": f"Aqui é a Scorpion Bits, veja {PORTFOLIO_URL}",
                "claims": [
                    {"text": "a", "about": "scorpion", "facts": [ids["intro"], ids["portfolio"]]}
                ],
            }
        )
        assert validate_draft(out, facts, "whatsapp") == []
        out.subject = "Assunto"
        assert any("assunto" in i for i in validate_draft(out, facts, "whatsapp"))


class TestGenerate:
    def test_rules_strategy_is_valid_cited_and_free(self, world):
        organization, service = world
        draft = generate_draft(organization, ai=ai_with(), strategies=["rules"])
        assert draft.status == "valid" and draft.strategy == "rules" and draft.cost_usd == 0
        assert PORTFOLIO_URL in draft.body and "Escola Exemplo" in draft.body
        assert draft.claims and all(c["facts"] for c in draft.claims)
        assert draft.mode == "first_contact" and draft.service == service

    def test_whatsapp_rules_is_short_without_subject(self, world):
        draft = generate_draft(world[0], channel="whatsapp", ai=ai_with(), strategies=["rules"])
        assert draft.subject == "" and draft.status == "valid"
        assert len(draft.body.split()) <= 70

    def test_llm_draft_is_used_and_internal_data_goes_only_to_paid(self, world):
        organization, service = world
        facts = [f.__dict__ for f in facts_of(organization, service)]
        provider = paid([good_reply(facts)])
        ai = AIService(providers={"anthropic": provider})
        draft = generate_draft(organization, ai=ai, strategies=["anthropic:claude-sonnet-5-5"])
        assert draft.status == "valid" and draft.strategy == "anthropic:claude-sonnet-5-5"
        assert draft.cost_usd > 0
        # só os fatos viajam: nenhum contato nem texto livre de interação
        prompt = provider.requests[0][1].prompt
        assert "F1 [intro]" in prompt and "Escola Exemplo" in prompt

    def test_free_provider_never_receives_the_internal_input(self, world):
        free = FakeProvider([], name="gemini-free", billing="free", classes=(DataClass.PUBLIC,))
        ai = AIService(providers={"gemini-free": free})
        draft = generate_draft(
            world[0], ai=ai, strategies=["gemini-free:gemini-3.1-flash-lite", "rules"]
        )
        assert free.requests == [] and draft.strategy == "rules"
        assert "dado" in json.dumps(draft.attempts, ensure_ascii=False)

    def test_invalid_llm_falls_back_to_rules_and_logs_why(self, world):
        bad = json.dumps(
            {
                "body": "Atendemos 500 escolas!",
                "claims": [{"text": "x", "about": "scorpion", "facts": ["F1"]}],
            }
        )
        ai = ai_with(bad)
        draft = generate_draft(world[0], ai=ai, strategies=["anthropic:claude-sonnet-5-5", "rules"])
        assert draft.strategy == "rules" and draft.status == "valid"
        assert draft.attempts[0]["result"] == ["número que não está nos fatos"]

    def test_ab_mode_keeps_the_rejected_draft_without_fallback(self, world):
        bad = json.dumps({"body": "Atendemos 500 escolas!", "claims": []})
        draft = generate_draft(
            world[0],
            ai=ai_with(bad),
            strategies=["anthropic:claude-sonnet-5-5"],
            fallback=False,
        )
        assert draft.status == "rejected" and draft.validation_issues

    def test_no_match_and_no_service_is_an_error(self, organization):
        with pytest.raises(OutreachError):
            generate_draft(organization, ai=ai_with(), strategies=["rules"])

    def test_opt_out_organization_is_blocked(self, world):
        organization, _ = world
        register_opt_out(organization, "pediu")
        organization.refresh_from_db()
        with pytest.raises(OutreachBlocked):
            generate_draft(organization, ai=ai_with(), strategies=["rules"])
        assert not OutreachDraft.objects.exists()

    def test_proposal_already_sent_is_not_pitched_again(self, world):
        organization, service = world
        Interaction.objects.create(
            organization=organization,
            kind="proposal_sent",
            occurred_at=date(2026, 9, 1),
            service=service,
        )
        draft = generate_draft(organization, ai=ai_with(), strategies=["rules"])
        assert "Queremos conversar sobre" not in draft.body
        assert draft.status == "valid"


class TestCommandAndAdmin:
    def test_command_generates_compares_and_reports(self, world):
        organization, _ = world
        out = StringIO()
        call_command("draft_outreach", org=[organization.pk], stdout=out)
        assert "rascunho" in out.getvalue()
        draft = OutreachDraft.objects.get()
        draft.rating = "usable"
        draft.save()
        out = StringIO()
        call_command("draft_outreach", report=True, stdout=out)
        assert "usáveis" in out.getvalue()

    def test_admin_action_redirects_to_the_draft(self, world, admin_client):
        organization, _ = world
        response = admin_client.post(
            reverse("admin:core_organization_changelist"),
            {"action": "draft_outreach", "_selected_action": [organization.pk]},
        )
        draft = OutreachDraft.objects.get()
        assert response.status_code == 302
        assert response.url == reverse("admin:core_outreachdraft_change", args=[draft.pk])
        page = admin_client.get(response.url)
        assert page.status_code == 200 and "Escola Exemplo" in page.content.decode()

    def test_admin_action_warns_when_blocked(self, world, admin_client):
        organization, _ = world
        register_opt_out(organization, "pediu")
        response = admin_client.post(
            reverse("admin:core_organization_changelist"),
            {"action": "draft_outreach", "_selected_action": [organization.pk]},
            follow=True,
        )
        assert "opt-out" in response.content.decode()
        assert not OutreachDraft.objects.exists()
